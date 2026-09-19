"""
core/gemini_free_proxy.py -- Embedded Gemini Web-to-OpenAI Proxy for J.A.R.V.I.S.

Based on Sophomoresty/gemini-web2api (MIT License).
Runs locally on 127.0.0.1 (localhost only) -- NOT exposed to network.

Anonymous mode: gemini-3.7-flash works WITHOUT cookies (100% free).
Cookie mode:    Set config/gemini_cookies.json for Pro model access.
"""
import json
import urllib.request
import urllib.parse
import time
import ssl
import sys
import uuid
import re
import os
import hashlib
import threading
import secrets
from pathlib import Path
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

__version__ = "1.1.0-jarvis"

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()
COOKIE_FILE = BASE_DIR / "config" / "gemini_cookies.json"

CONFIG = {
    "port": 8081,
    "host": "127.0.0.1",
    "retry_attempts": 3,
    "retry_delay_sec": 2,
    "request_timeout_sec": 120,
    "gemini_bl": "boq_assistant-bard-web-server_20260716.08_p0",
    "auth_user": None,
    "xsrf_token": None,
    "default_model": "gemini-3.7-flash",
    "log_requests": False,
    "cookie_file": None,
    "proxy": None,
    "temporary_chats": True,
    "auth_token": None,  # Optional bearer token for API access
}

MODELS = {
    "gemini-3.7-flash": {"mode": 1, "think": 4, "desc": "Latest Flash (Free, Anonymous)"},
    "gemini-3.6-flash": {"mode": 1, "think": 4, "desc": "Flash (Free, Anonymous)"},
    "gemini-3.5-flash": {"mode": 1, "think": 4, "desc": "Flash alias (Free, Anonymous)"},
    "gemini-3.5-flash-thinking": {"mode": 2, "think": 0, "desc": "Deep thinking mode"},
    "gemini-3.1-pro":   {"mode": 3, "think": 4, "desc": "Pro (requires cookie)"},
    "gemini-auto":      {"mode": 4, "think": 4, "desc": "Auto model selection"},
    "gemini-flash-lite":{"mode": 6, "think": 4, "desc": "Lightweight fast"},
}

_server: Optional[HTTPServer] = None
_server_thread: Optional[threading.Thread] = None
_running = False


def _log(msg: str):
    if CONFIG["log_requests"]:
        sys.stderr.write(f"[GeminiProxy] {time.strftime('%H:%M:%S')} {msg}\n")
        sys.stderr.flush()


def _check_auth(handler) -> bool:
    """Check Authorization header for bearer token if configured."""
    auth_token = CONFIG.get("auth_token")
    if not auth_token:
        return True
    auth_header = handler.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        handler._send_json(401, {"error": "Unauthorized: Bearer token required"})
        return False
    token = auth_header[7:].strip()
    if token != auth_token:
        handler._send_json(401, {"error": "Unauthorized: Invalid token"})
        return False
    return True


def _load_cookie() -> tuple:
    cf = CONFIG.get("cookie_file")
    if not cf or not os.path.exists(cf):
        return "", None
    try:
        with open(cf, "r", encoding="utf-8") as f:
            data = json.load(f)
        cookie_str = data.get("cookie", "").strip()
        sapisid = data.get("sapisid", "").strip() or None
        if not cookie_str:
            return "", None
        if not sapisid:
            pairs = dict(p.split("=", 1) for p in cookie_str.split("; ") if "=" in p)
            sapisid = pairs.get("SAPISID") or None
        return cookie_str, sapisid
    except Exception as e:
        _log(f"Cookie load error: {e}")
        return "", None


def _make_sapisidhash(sapisid: str) -> str:
    ts = int(time.time())
    h = hashlib.sha1(f"{ts} {sapisid} https://gemini.google.com".encode()).hexdigest()
    return f"SAPISIDHASH {ts}_{h}"


def _account_prefix() -> str:
    auth_user = CONFIG.get("auth_user")
    if auth_user is None or auth_user == "":
        return ""
    return f"/u/{auth_user}"


def _fetch_latest_bl() -> Optional[str]:
    try:
        req = urllib.request.Request(
            "https://gemini.google.com/app",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        ctx = ssl.create_default_context()
        resp = urllib.request.urlopen(req, context=ctx, timeout=12)
        html = resp.read().decode("utf-8", errors="replace")
        m = re.search(r'(boq_assistant-bard-web-server_\d+\.\d+_p\d+)', html)
        if m:
            return m.group(1)
    except Exception as e:
        _log(f"BL fetch failed: {e}")
    return None


def _update_bl_if_needed() -> bool:
    new_bl = _fetch_latest_bl()
    if new_bl and new_bl != CONFIG["gemini_bl"]:
        _log(f"BL updated: {CONFIG['gemini_bl']} -> {new_bl}")
        CONFIG["gemini_bl"] = new_bl
        return True
    return False


def _gemini_stream_generate(prompt: str, model_id: int, think_mode: int) -> str:
    inner = [None] * 80
    inner[0] = [prompt, 0, None, None, None, None, 0]
    inner[1] = ["en"]
    inner[2] = ["", "", "", None, None, None, None, None, None, ""]
    inner[6] = [0]
    inner[7] = 1
    inner[10] = 1
    inner[11] = 0
    inner[17] = [[think_mode]]
    inner[18] = 0
    inner[27] = 1
    inner[30] = [4]
    inner[41] = [1]
    inner[45] = 1
    inner[53] = 0
    inner[59] = str(uuid.uuid4())
    inner[61] = []
    inner[68] = 1
    inner[79] = model_id

    outer = [None, json.dumps(inner)]
    params = {"f.req": json.dumps(outer)}
    if CONFIG.get("xsrf_token"):
        params["at"] = CONFIG["xsrf_token"]
    body = urllib.parse.urlencode(params).encode()
    reqid = int(time.time()) % 1000000
    prefix = _account_prefix()
    url = (
        f"https://gemini.google.com{prefix}/_/BardChatUi/data/"
        "assistant.lamda.BardFrontendService/StreamGenerate"
        f"?bl={CONFIG['gemini_bl']}&hl=en&_reqid={reqid}&rt=c"
    )
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://gemini.google.com",
        "Referer": f"https://gemini.google.com{prefix}/app",
        "X-Same-Domain": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    if prefix:
        headers["X-Goog-AuthUser"] = str(CONFIG["auth_user"])

    cookie_str, sapisid = _load_cookie()
    if cookie_str:
        headers["Cookie"] = cookie_str
    if sapisid:
        headers["Authorization"] = _make_sapisidhash(sapisid)

    last_err = None
    for attempt in range(CONFIG["retry_attempts"]):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            ctx = ssl.create_default_context()
            resp = urllib.request.urlopen(req, context=ctx, timeout=CONFIG["request_timeout_sec"])
            return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code == 405 and _update_bl_if_needed():
                reqid = int(time.time()) % 1000000
                url = (
                    f"https://gemini.google.com{prefix}/_/BardChatUi/data/"
                    "assistant.lamda.BardFrontendService/StreamGenerate"
                    f"?bl={CONFIG['gemini_bl']}&hl=en&_reqid={reqid}&rt=c"
                )
                last_err = e
                continue
            last_err = e
            if attempt < CONFIG["retry_attempts"] - 1:
                time.sleep(CONFIG["retry_delay_sec"])
        except Exception as e:
            last_err = e
            if attempt < CONFIG["retry_attempts"] - 1:
                time.sleep(CONFIG["retry_delay_sec"])
    raise RuntimeError(f"Gemini request failed: {last_err}")


def _parse_response(raw: str) -> str:
    candidates = []
    try:
        lines = raw.split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.isdigit():
                continue
            try:
                data = json.loads(line)
                if isinstance(data, list) and len(data) >= 1:
                    inner_str = data[0][2] if len(data[0]) > 2 else None
                    if not inner_str:
                        continue
                    inner = json.loads(inner_str)
                    try:
                        text = inner[4][0][1][0]
                        if text and isinstance(text, str) and text.strip():
                            candidates.append(text.strip())
                    except (IndexError, TypeError, KeyError):
                        pass
                    try:
                        candidate = inner[0][0]
                        if candidate and isinstance(candidate, str) and len(candidate.strip()) > 3:
                            candidates.append(candidate.strip())
                    except (IndexError, TypeError):
                        pass
            except (json.JSONDecodeError, IndexError, TypeError):
                continue
    except Exception:
        pass
    if candidates:
        return max(candidates, key=len)
    matches = re.findall(r'"([^"]{10,})"', raw)
    if matches:
        return max(matches, key=len)
    return ""


class _GeminiHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        if CONFIG["log_requests"]:
            _log(f"{self.address_string()} - {format % args}")

    def _send_json(self, code: int, obj: dict):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not _check_auth(self):
            return
        if self.path in ("/v1/models", "/v1/models/"):
            model_list = [
                {"id": m, "object": "model", "created": 1700000000,
                 "owned_by": "gemini-web", "description": info["desc"]}
                for m, info in MODELS.items()
            ]
            self._send_json(200, {"object": "list", "data": model_list})
        elif self.path == "/health":
            self._send_json(200, {"status": "ok", "version": __version__})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        if not _check_auth(self):
            return
        if self.path not in ("/v1/chat/completions", "/chat/completions"):
            self._send_json(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception as e:
            self._send_json(400, {"error": f"Bad request: {e}"})
            return

        model_id_str = body.get("model", CONFIG["default_model"])
        model_info = MODELS.get(model_id_str, MODELS["gemini-3.7-flash"])
        mode = model_info["mode"]
        think = model_info["think"]

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
            raw = _gemini_stream_generate(prompt, mode, think)
            text = _parse_response(raw)
            if not text:
                raise RuntimeError("Empty response")
        except Exception as e:
            _log(f"Generate error: {e}")
            self._send_json(500, {"error": {"message": str(e), "type": "server_error", "code": 500}})
            return

        self._send_json(200, {
            "id": f"gemweb-{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_id_str,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        })

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()


class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def start_proxy(port: int = 8081, silent: bool = True) -> bool:
    global _server, _server_thread, _running
    if _running:
        return True
    CONFIG["port"] = port
    CONFIG["log_requests"] = not silent
    if COOKIE_FILE.exists():
        CONFIG["cookie_file"] = str(COOKIE_FILE)
    # Generate auth token if not provided
    if not CONFIG.get("auth_token"):
        CONFIG["auth_token"] = secrets.token_urlsafe(32)
        if not silent:
            print(f"[GeminiProxy] Auth token: {CONFIG['auth_token']}")
    try:
        _server = _ThreadedHTTPServer(("127.0.0.1", port), _GeminiHandler)
        _server_thread = threading.Thread(
            target=_server.serve_forever, daemon=True, name="GeminiProxyServer")
        _server_thread.start()
        _running = True
        threading.Thread(target=_update_bl_if_needed, daemon=True, name="GeminiProxyBLRefresh").start()
        if not silent:
            print(f"[GeminiProxy] Started on http://127.0.0.1:{port}/v1")
        return True
    except OSError as e:
        print(f"[GeminiProxy] Failed to start on port {port}: {e}")
        _running = False
        return False
    except Exception as e:
        print(f"[GeminiProxy] Unexpected error: {e}")
        _running = False
        return False


def stop_proxy():
    global _server, _running
    if _server:
        try:
            _server.shutdown()
        except Exception:
            pass
        _server = None
    _running = False


def is_running() -> bool:
    return _running


def get_url() -> str:
    return f"http://127.0.0.1:{CONFIG['port']}/v1"


def quick_test() -> bool:
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{CONFIG['port']}/health",
            headers={"User-Agent": "JARVIS-HealthCheck"})
        resp = urllib.request.urlopen(req, timeout=3)
        data = json.loads(resp.read())
        return data.get("status") == "ok"
    except Exception:
        return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Gemini Free Proxy Server")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    print(f"[GeminiProxy] Starting on http://127.0.0.1:{args.port}/v1")
    start_proxy(port=args.port, silent=not args.verbose)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_proxy()
