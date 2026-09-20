"""
Safe, Opt-in Local LLM Engine Bridge (DeepSeek-R1 / Qwen2.5 / Ollama).

CRITICAL SAFETY DESIGN:
  1. STRICTLY OPT-IN: Defaults to FALSE. Never starts Ollama automatically to prevent system freezing/hanging.
  2. ZERO OVERHEAD: When disabled, consumes 0 MB RAM, 0% CPU, and makes 0 network calls.
  3. FAST-FAIL TIMEOUT: When enabled, probes localhost:11434 with a strict 1.5s timeout.
     If offline, falls back instantly to Gemini Live WebSocket & Gemini Cloud.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Generator, Optional

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"


def _load_config() -> Dict[str, Any]:
    """Load configuration from config/api_keys.json safely."""
    if _CONFIG_PATH.exists():
        try:
            return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_config(cfg: Dict[str, Any]) -> bool:
    """Save configuration to config/api_keys.json safely."""
    try:
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CONFIG_PATH.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
        return True
    except Exception as e:
        print(f"[LocalLLMBridge] Config save error: {e}")
        return False


def is_local_llm_enabled() -> bool:
    """
    Check if Local LLM execution is explicitly enabled.
    Defaults to FALSE for system safety and zero freeze risk.
    """
    env_val = os.environ.get("ENABLE_LOCAL_LLM", "").strip().lower()
    if env_val in ("1", "true", "yes"):
        return True

    cfg = _load_config()
    return bool(cfg.get("enable_local_llm", False))


def set_local_llm_enabled(enabled: bool) -> bool:
    """Enable or disable Local LLM bridge in configuration."""
    cfg = _load_config()
    cfg["enable_local_llm"] = bool(enabled)
    return _save_config(cfg)


def get_local_llm_config() -> Dict[str, Any]:
    """Retrieve local LLM settings (URL, model, timeout). Unified with custom UI config."""
    cfg = _load_config()
    # Fallback to custom_llm_url if local_llm_url is not specifically set
    raw_url = str(cfg.get("local_llm_url") or cfg.get("custom_llm_url") or "http://localhost:11434").strip()
    if not raw_url:
        raw_url = "http://localhost:11434"
    if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
        raw_url = "http://" + raw_url
    url = raw_url.rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3]  # Strip /v1 for native Ollama API probes
        
    raw_model = str(cfg.get("local_llm_model") or cfg.get("custom_llm_model") or "llama3.2").strip()
    model = raw_model if raw_model else "llama3.2"
    
    return {
        "enabled": is_local_llm_enabled(),
        "url": url,
        "model": model,
        "timeout": float(cfg.get("local_llm_timeout", 1.5)),
    }


def check_local_llm_health(timeout: float = 1.5) -> Dict[str, Any]:
    """
    Probe the local Ollama instance with a strict fast timeout (1.5s).
    Returns health status without hanging the caller.
    """
    cfg = get_local_llm_config()
    url = f"{cfg['url']}/api/version"
    t0 = time.monotonic()

    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            return {
                "online": True,
                "version": data.get("version", "unknown"),
                "latency_ms": latency_ms,
                "url": cfg["url"],
                "model": cfg["model"],
            }
    except Exception as e:
        return {
            "online": False,
            "error": str(e),
            "url": cfg["url"],
            "model": cfg["model"],
        }


_last_offline_time: float = 0.0
_OFFLINE_COOLDOWN: float = 30.0


def generate_local_llm(
    prompt: str,
    system_prompt: str = "",
    timeout: Optional[float] = None,
) -> Optional[str]:
    """
    Query the local LLM (Ollama) safely.
    If disabled or offline, returns None immediately so JARVIS routes to Gemini Cloud/Live.
    Includes a 30s cooldown cache to avoid repeated 1.5s socket timeouts when Ollama is not running.
    """
    global _last_offline_time
    if not is_local_llm_enabled():
        return None

    now = time.monotonic()
    if (now - _last_offline_time) < _OFFLINE_COOLDOWN:
        return None

    cfg = get_local_llm_config()
    if not cfg.get("url") or not cfg["url"].startswith("http"):
        return None
    to = timeout or cfg["timeout"]

    payload = {
        "model": cfg["model"],
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "top_p": 0.9,
        }
    }
    if system_prompt:
        payload["system"] = system_prompt

    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{cfg['url']}/api/generate",
        data=data_bytes,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=to) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            ans = result.get("response", "").strip()
            _last_offline_time = 0.0
            return ans if ans else None
    except Exception as e:
        _last_offline_time = time.monotonic()
        if isinstance(e, urllib.error.URLError) and "10061" in str(e):
            print(f"[LocalLLMBridge] Local engine not running on {cfg['url']}. Cooldown active for 30s.")
        else:
            print(f"[LocalLLMBridge] Request failed ({e}). Cooldown active for 30s.")
        return None
