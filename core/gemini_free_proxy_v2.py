"""
core/gemini_free_proxy_v2.py -- Gemini Web-to-OpenAI Proxy v2 for J.A.R.V.I.S.

Side-by-side alternative to gemini_free_proxy.py (v1). Selected via the
`proxy_version` config flag (1 = v1 default, 2 = v2 canary).

v2 improvements over v1 (transport layer only):
  - GET /metrics — request counts, per-model stats, latency, errors (auth-gated)
  - Per-IP rate limiting (sliding window, 429 + Retry-After instead of meltdown)
  - Bearer auth REQUIRED on every endpoint except /health
  - ProxyConfig dataclass + async create_app() factory (test-friendly)
  - Thread-safe metrics / limiter (Lock-guarded)

Deliberately NOT duplicated: the Gemini web protocol itself
(StreamGenerate framing, response parsing, MODELS catalog, cookie/BL state)
is imported from v1 and shared. Protocol tuning stays single-source in
v1.CONFIG; v2 owns only transport concerns. No circular import: v1 never
imports v2.

Runs on 127.0.0.1 (localhost only) — NOT exposed to the network.
"""
from __future__ import annotations

import json
import secrets
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Optional

# ── Shared protocol (single source — see module docstring) ──────────────────
from core.gemini_free_proxy import (
    _gemini_stream_generate,
    _parse_response,
    MODELS,
)

__version__ = "2.0.0-jarvis"


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


# ── Config ───────────────────────────────────────────────────────────────────

@dataclass
class ProxyConfig:
    port: int = 8081
    host: str = "127.0.0.1"
    auth_token: str = ""              # auto-generated when empty
    rate_limit_per_min: int = 120     # per-IP sliding window; 0 = unlimited
    request_timeout_sec: int = 90     # client-facing HTTP timeout hint
    default_model: str = "gemini-3.7-flash"
    log_requests: bool = False

    def ensure_token(self) -> str:
        if not self.auth_token:
            self.auth_token = secrets.token_urlsafe(32)
        return self.auth_token


# ── Metrics (thread-safe) ────────────────────────────────────────────────────

class _Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = time.monotonic()
        self._total = 0
        self._errors = 0
        self._latency_sum = 0.0
        self._by_endpoint: dict[str, int] = {}
        self._by_model: dict[str, int] = {}
        self._rate_limited = 0

    def record(self, endpoint: str, model: str = "", latency: float = 0.0,
               ok: bool = True, rate_limited: bool = False) -> None:
        with self._lock:
            self._total += 1
            self._latency_sum += max(0.0, latency)
            self._by_endpoint[endpoint] = self._by_endpoint.get(endpoint, 0) + 1
            if model:
                self._by_model[model] = self._by_model.get(model, 0) + 1
            if not ok:
                self._errors += 1
            if rate_limited:
                self._rate_limited += 1

    def snapshot(self) -> dict:
        with self._lock:
            avg_ms = (self._latency_sum / self._total * 1000.0) if self._total else 0.0
            return {
                "proxy": "v2",
                "version": __version__,
                "uptime_sec": round(time.monotonic() - self._started, 1),
                "total_requests": self._total,
                "errors": self._errors,
                "rate_limited": self._rate_limited,
                "avg_latency_ms": round(avg_ms, 1),
                "by_endpoint": dict(self._by_endpoint),
                "by_model": dict(self._by_model),
            }


# ── Rate limiter (per-IP sliding window, thread-safe) ────────────────────────

class _RateLimiter:
    def __init__(self, per_min: int) -> None:
        self._per_min = max(0, int(per_min or 0))
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = {}

    def allow(self, ip: str) -> bool:
        if self._per_min <= 0:
            return True
        now = time.monotonic()
        window = 60.0
        with self._lock:
            hits = [t for t in self._hits.get(ip, []) if now - t < window]
            if len(hits) >= self._per_min:
                self._hits[ip] = hits
                return False
            hits.append(now)
            self._hits[ip] = hits[-self._per_min:]
            return True


# ── Handler factory (per-app binding — no shared class state) ───────────────

class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def _make_handler(config: ProxyConfig, metrics: _Metrics, limiter: _RateLimiter):
    """Build a request-handler class bound to one app's config/metrics/limiter."""

    class _BoundHandler(BaseHTTPRequestHandler):
        server_version = "GeminiProxyV2"

        def log_message(self, format, *args):  # noqa: A002 (stdlib signature)
            if config.log_requests:
                sys.stderr.write(f"[GeminiProxyV2] {time.strftime('%H:%M:%S')} "
                                 f"{self.address_string()} - {format % args}\n")
                sys.stderr.flush()

        # -- helpers ------------------------------------------------------
        def _send_json(self, code: int, obj: dict, extra: dict | None = None):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _authed(self) -> bool:
            want = config.auth_token or ""
            if not want:
                return True  # no token configured → open (dev/test only)
            got = (self.headers.get("Authorization", "") or "")
            if not got.startswith("Bearer "):
                return False
            # Constant-time compare so tokens can't be probed byte-by-byte.
            return secrets.compare_digest(got[7:].strip(), want)

        def _client_ip(self) -> str:
            try:
                return (self.client_address[0] if self.client_address else "127.0.0.1")
            except Exception:
                return "127.0.0.1"

        # -- routes --------------------------------------------------------
        def do_GET(self):
            t0 = time.perf_counter()
            # /health is intentionally OPEN (load balancers, UI toggle, tests).
            if self.path == "/health":
                metrics.record("GET /health", latency=time.perf_counter() - t0, ok=True)
                self._send_json(200, {"status": "ok", "version": __version__, "proxy": "v2"})
                return
            if self.path == "/metrics":
                if not self._authed():
                    metrics.record("GET /metrics", latency=time.perf_counter() - t0, ok=False)
                    self._send_json(401, {"error": "Unauthorized: Bearer token required"})
                    return
                metrics.record("GET /metrics", latency=time.perf_counter() - t0, ok=True)
                self._send_json(200, metrics.snapshot())
                return
            if not self._authed():
                metrics.record("GET " + self.path, latency=time.perf_counter() - t0, ok=False)
                self._send_json(401, {"error": "Unauthorized: Bearer token required"})
                return
            if self.path in ("/v1/models", "/v1/models/"):
                model_list = [
                    {"id": m, "object": "model", "created": 1700000000,
                     "owned_by": "gemini-web", "description": info["desc"]}
                    for m, info in MODELS.items()
                ]
                metrics.record("GET /v1/models", latency=time.perf_counter() - t0, ok=True)
                self._send_json(200, {"object": "list", "data": model_list})
                return
            metrics.record("GET " + self.path, latency=time.perf_counter() - t0, ok=False)
            self._send_json(404, {"error": "Not found"})

        def do_POST(self):
            t0 = time.perf_counter()
            if self.path not in ("/v1/chat/completions", "/chat/completions"):
                metrics.record("POST " + self.path, latency=time.perf_counter() - t0, ok=False)
                self._send_json(404, {"error": "Not found"})
                return
            # Rate-limit BEFORE auth so a leaked-token flood still gets shaped.
            if not limiter.allow(self._client_ip()):
                metrics.record("POST " + self.path, latency=time.perf_counter() - t0,
                               ok=False, rate_limited=True)
                self._send_json(429, {"error": "Rate limit exceeded, slow down."},
                                extra={"Retry-After": "5"})
                return
            if not self._authed():
                metrics.record("POST " + self.path, latency=time.perf_counter() - t0, ok=False)
                self._send_json(401, {"error": "Unauthorized: Bearer token required"})
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
            except Exception as e:
                metrics.record("POST " + self.path, latency=time.perf_counter() - t0, ok=False)
                self._send_json(400, {"error": f"Bad request: {e}"})
                return

            model_id_str = body.get("model", config.default_model)
            model_info = MODELS.get(model_id_str, MODELS["gemini-3.7-flash"])
            messages = body.get("messages", [])
            parts = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        c.get("text", "") for c in content
                        if isinstance(c, dict) and c.get("type") == "text"
                    )
                if role == "system":
                    parts.append(f"[System]: {content}")
                elif role == "user":
                    parts.append(f"[User]: {content}")
                elif role == "assistant":
                    parts.append(f"[Assistant]: {content}")
            prompt = "\n".join(parts) if parts else "Hello"

            try:
                import uuid as _uuid
                raw = _gemini_stream_generate(prompt, model_info["mode"], model_info["think"])
                text = _parse_response(raw)
                if not text:
                    raise RuntimeError("Empty response")
            except Exception as e:
                metrics.record("POST " + self.path, model=model_id_str,
                               latency=time.perf_counter() - t0, ok=False)
                self._send_json(500, {"error": {"message": str(e),
                                                "type": "server_error", "code": 500}})
                return

            metrics.record("POST " + self.path, model=model_id_str,
                           latency=time.perf_counter() - t0, ok=True)
            self._send_json(200, {
                "id": f"gemweb2-{_uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model_id_str,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            })

        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()

    return _BoundHandler


# ── App handle + factory ─────────────────────────────────────────────────────

class _ProxyApp:
    """Running v2 instance. Returned by create_app() and start_proxy()."""

    def __init__(self, config: ProxyConfig, server: HTTPServer,
                 thread: threading.Thread, metrics: _Metrics) -> None:
        self.config = config
        self._server = server
        self._thread = thread
        self._metrics = metrics

    @property
    def url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}/v1"

    def metrics_snapshot(self) -> dict:
        return self._metrics.snapshot()

    def stop(self) -> None:
        try:
            self._server.shutdown()
        except Exception:
            pass
        try:
            self._server.server_close()
        except Exception:
            pass


async def create_app(config: Optional[ProxyConfig] = None) -> _ProxyApp:
    """Build + start a v2 proxy on config.port. Async so callers can
    `asyncio.run(create_app(...))`; the server itself runs in a daemon thread.

    Raises OSError if the port is taken (e.g. v1 already on 8081 — use 8082
    for side-by-side testing).
    """
    cfg = config or ProxyConfig()
    cfg.ensure_token()
    metrics = _Metrics()
    limiter = _RateLimiter(cfg.rate_limit_per_min)
    handler = _make_handler(cfg, metrics, limiter)
    server = _ThreadedHTTPServer((cfg.host, cfg.port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True,
                              name=f"GeminiProxyV2-{cfg.port}")
    thread.start()
    return _ProxyApp(cfg, server, thread, metrics)


# ── Module singleton (mirrors the v1 API for main.py / UI wiring) ───────────

_singleton: Optional[_ProxyApp] = None
_singleton_lock = threading.Lock()


def start_proxy(port: int = 8081, silent: bool = True) -> bool:
    global _singleton
    with _singleton_lock:
        if _singleton is not None:
            return True
        cfg = ProxyConfig(port=port, log_requests=not silent)
        cfg.ensure_token()
        try:
            metrics = _Metrics()
            limiter = _RateLimiter(cfg.rate_limit_per_min)
            handler = _make_handler(cfg, metrics, limiter)
            server = _ThreadedHTTPServer((cfg.host, cfg.port), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True,
                                      name="GeminiProxyV2Server")
            thread.start()
            _singleton = _ProxyApp(cfg, server, thread, metrics)
            if not silent:
                print(f"[GeminiProxyV2] Started on http://{cfg.host}:{cfg.port}/v1 "
                      f"(auth token: {cfg.auth_token})")
            return True
        except OSError as e:
            print(f"[GeminiProxyV2] Failed to start on port {port}: {e}")
            return False
        except Exception as e:
            print(f"[GeminiProxyV2] Unexpected error: {e}")
            return False


def stop_proxy() -> None:
    global _singleton
    with _singleton_lock:
        if _singleton is not None:
            try:
                _singleton.stop()
            except Exception:
                pass
            _singleton = None


def is_running() -> bool:
    return _singleton is not None


def get_url() -> str:
    if _singleton is not None:
        return _singleton.url
    return "http://127.0.0.1:8081/v1"


def get_auth_token() -> str:
    if _singleton is not None:
        return _singleton.config.auth_token or ""
    return ""


def quick_test(port: int = 8081) -> bool:
    """GET /health (open endpoint) — True when a v2 instance answers."""
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/health",
            headers={"User-Agent": "JARVIS-HealthCheck"})
        resp = urllib.request.urlopen(req, timeout=3)
        data = json.loads(resp.read())
        return data.get("status") == "ok"
    except Exception:
        return False


if __name__ == "__main__":
    import argparse
    import asyncio
    parser = argparse.ArgumentParser(description="Gemini Free Proxy v2 Server")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    app = asyncio.run(create_app(ProxyConfig(port=args.port, log_requests=args.verbose)))
    print(f"[GeminiProxyV2] Started on {app.url} (token: {app.config.auth_token})")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        app.stop()
