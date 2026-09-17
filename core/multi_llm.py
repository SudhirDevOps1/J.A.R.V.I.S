"""
Multi-Provider LLM Engine for SudhirDevOps1 AI.

Supports:
  0. Gemini Web (FREE, Anonymous) -> free_proxy_enabled: true [NO API KEY NEEDED]
  1. Groq (Ultra-fast Llama 3.3 70B, zero 503s) -> groq_api_key
  2. OpenRouter (DeepSeek R1/V3, Claude 3.5, Llama 3.3) -> openrouter_api_key
  3. DeepSeek Direct API -> deepseek_api_key
  4. Custom OpenAI-Compatible Endpoints (Ollama, LM Studio, vLLM, LocalAI) -> custom_llm_url, custom_llm_api_key, custom_llm_model
  5. Google Gemini API (with multi-key rotation) -> gemini_api_key / gemini_api_keys[]
  6. Smart LLM Cache (SQLite) -> llm_cache_enabled: true
"""
import json
import os
import sys
import time
from pathlib import Path

import requests

# ─── Optional free proxy + cache ─────────────────────────────────────────────
try:
    from core.gemini_free_proxy import is_running as _proxy_is_running, get_url as _proxy_url
    _HAS_FREE_PROXY = True
except ImportError:
    _HAS_FREE_PROXY = False
    def _proxy_is_running(): return False
    def _proxy_url(): return "http://127.0.0.1:8081/v1"

try:
    from core.llm_cache import get as _cache_get, set as _cache_set, TTL as _TTL
    _HAS_CACHE = True
except ImportError:
    _HAS_CACHE = False
    def _cache_get(p, prov=""): return None
    def _cache_set(p, r, ttl, prov=""): pass
    class _TTL:
        NO_CACHE = 0; NEWS = 1800; WEATHER = 600; SEARCH = 900; GENERAL = 0; FACTS = 3600

# Round-robin index for multi-key Gemini rotation (module-level, shared across instances)
_gemini_key_index = 0
_gemini_key_lock = __import__("threading").Lock()


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


class LLMResponse:
    def __init__(self, text: str):
        self.text = text


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


class MultiLLMClient:
    def __init__(self, preferred_provider: str = None, model: str = None):
        cfg = _load_config()
        self.gemini_key = cfg.get("gemini_api_key", "").strip()
        self.groq_key = cfg.get("groq_api_key", "").strip()
        self.openrouter_key = cfg.get("openrouter_api_key", "").strip()
        self.deepseek_key = cfg.get("deepseek_api_key", "").strip()

        # Custom endpoint support (e.g. Ollama http://localhost:11434/v1, LM Studio, vLLM)
        self.custom_url = (cfg.get("custom_llm_url") or cfg.get("openai_url") or "").strip()
        self.custom_key = (cfg.get("custom_llm_api_key") or cfg.get("openai_api_key") or "dummy-key").strip()
        self.custom_model = cfg.get("custom_llm_model") or "llama3.2"

        # ── Free proxy (gemini-web anonymous mode) ────────────────────────────
        self.free_proxy_enabled = cfg.get("free_proxy_enabled", True)
        self.free_proxy_port = int(cfg.get("free_proxy_port", 8081))
        self.free_proxy_model = cfg.get("free_proxy_model", "gemini-3.7-flash")

        # ── Multi-key Gemini rotation ─────────────────────────────────────────
        # Supports both single key (gemini_api_key) and key pool (gemini_api_keys: [])
        _pool = cfg.get("gemini_api_keys", [])
        if isinstance(_pool, list):
            _pool = [k.strip() for k in _pool if k.strip()]
        else:
            _pool = []
        if self.gemini_key and self.gemini_key not in _pool:
            _pool.insert(0, self.gemini_key)
        self.gemini_key_pool = _pool

        # ── Cache settings ────────────────────────────────────────────────────
        self.cache_enabled = _HAS_CACHE and cfg.get("llm_cache_enabled", True)

        # Determine active provider
        self.provider = (preferred_provider or cfg.get("preferred_llm_provider", "")).lower().strip()
        if not self.provider:
            if self.free_proxy_enabled and _proxy_is_running():
                self.provider = "gemini-web"
            elif self.groq_key:
                self.provider = "groq"
            elif self.openrouter_key:
                self.provider = "openrouter"
            elif self.deepseek_key:
                self.provider = "deepseek"
            elif self.custom_url:
                self.provider = "custom"
            else:
                self.provider = "gemini"

        self.model = model

    def _next_gemini_key(self) -> str:
        """Round-robin through the Gemini API key pool. Returns empty string if pool empty."""
        global _gemini_key_index
        if not self.gemini_key_pool:
            return ""
        with _gemini_key_lock:
            key = self.gemini_key_pool[_gemini_key_index % len(self.gemini_key_pool)]
            _gemini_key_index += 1
        return key

    def generate_content(self, prompt: str, cache_ttl: int = 0) -> LLMResponse:
        """
        Universal generate_content interface matching Gemini / OpenAI API.

        Args:
            prompt: Text prompt to send to the LLM.
            cache_ttl: Cache time-to-live in seconds. 0 = no cache.
                       Use TTL constants from core.llm_cache: TTL.NEWS, TTL.WEATHER, etc.
        """
        prompt = str(prompt)

        # ── Cache check (before any API call) ─────────────────────────────────
        if self.cache_enabled and cache_ttl > 0:
            cached = _cache_get(prompt, self.provider)
            if cached is not None:
                return LLMResponse(cached)

        # ── Helper to save result to cache ────────────────────────────────────
        def _maybe_cache(result: LLMResponse) -> LLMResponse:
            if self.cache_enabled and cache_ttl > 0 and result.text:
                _cache_set(prompt, result.text, cache_ttl, self.provider)
            return result

        # ── 0. Gemini-Web Free Proxy (Anonymous, no API key needed) ───────────
        if self.free_proxy_enabled and _proxy_is_running():
            model = self.model or self.free_proxy_model
            endpoint = f"http://127.0.0.1:{self.free_proxy_port}/v1/chat/completions"
            try:
                res = requests.post(
                    endpoint,
                    headers={"Authorization": "Bearer none", "Content-Type": "application/json"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                    },
                    timeout=90,
                )
                if res.status_code == 200:
                    out = res.json()["choices"][0]["message"]["content"]
                    return _maybe_cache(LLMResponse(out))
                else:
                    print(f"[MultiLLM] GeminiWeb HTTP {res.status_code}: {res.text[:120]} — falling back")
            except Exception as e:
                print(f"[MultiLLM] GeminiWeb proxy error: {e} — falling back")

        # 1. Custom Provider (Ollama / LM Studio / LocalAI / Private Endpoints)
        if (self.provider in ("custom", "openai", "local", "ollama")) and self.custom_url:
            model = self.model or self.custom_model
            endpoint = self.custom_url.rstrip("/")
            if not endpoint.endswith("/chat/completions"):
                endpoint = f"{endpoint}/chat/completions" if endpoint.endswith("/v1") else f"{endpoint}/v1/chat/completions"

            try:
                res = requests.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {self.custom_key}", "Content-Type": "application/json"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                    },
                    timeout=60,
                )
                if res.status_code == 200:
                    out = res.json()["choices"][0]["message"]["content"]
                    return _maybe_cache(LLMResponse(out))
                else:
                    print(f"[MultiLLM] Custom Provider HTTP {res.status_code}: {res.text[:180]} — falling back to Gemini")
            except Exception as e:
                print(f"[MultiLLM] Custom Provider failed: {e} — falling back to Gemini")

        # 2. Groq Provider (Ultra-fast)
        if self.provider == "groq" and self.groq_key:
            model = self.model or "llama-3.3-70b-versatile"
            try:
                res = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                    },
                    timeout=30,
                )
                if res.status_code == 200:
                    out = res.json()["choices"][0]["message"]["content"]
                    return _maybe_cache(LLMResponse(out))
                else:
                    print(f"[MultiLLM] Groq HTTP {res.status_code}: {res.text[:180]} — falling back to Gemini")
            except Exception as e:
                print(f"[MultiLLM] Groq request failed: {e} — falling back to Gemini")

        # 3. OpenRouter Provider (DeepSeek R1, Claude, GPT-4o, etc.)
        if self.provider == "openrouter" and self.openrouter_key:
            model = self.model or "meta-llama/llama-3.3-70b-instruct"
            try:
                res = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.openrouter_key}",
                        "HTTP-Referer": "https://github.com/SudhirDevOps1",
                        "X-Title": "SudhirDevOps1 AI",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                    },
                    timeout=45,
                )
                if res.status_code == 200:
                    out = res.json()["choices"][0]["message"]["content"]
                    return _maybe_cache(LLMResponse(out))
                else:
                    print(f"[MultiLLM] OpenRouter HTTP {res.status_code}: {res.text[:180]} — falling back to Gemini")
            except Exception as e:
                print(f"[MultiLLM] OpenRouter failed: {e} — falling back to Gemini")

        # 4. DeepSeek Direct Provider
        if self.provider == "deepseek" and self.deepseek_key:
            model = self.model or "deepseek-chat"
            try:
                res = requests.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.deepseek_key}", "Content-Type": "application/json"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                    },
                    timeout=45,
                )
                if res.status_code == 200:
                    out = res.json()["choices"][0]["message"]["content"]
                    return _maybe_cache(LLMResponse(out))
                else:
                    print(f"[MultiLLM] DeepSeek HTTP {res.status_code}: {res.text[:180]} — falling back to Gemini")
            except Exception as e:
                print(f"[MultiLLM] DeepSeek request failed: {e} — falling back to Gemini")

        # 5. Google Gemini (Default / Fallback) with multi-key rotation + resilience
        if self.gemini_key_pool:
            from google import genai

            candidate_models = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
            if self.model and self.model not in candidate_models:
                candidate_models.insert(0, self.model)

            last_err = None
            # Try each key in pool with round-robin
            keys_to_try = list(self.gemini_key_pool)
            for api_key in keys_to_try:
                client = genai.Client(api_key=api_key)
                for m in candidate_models:
                    for attempt in range(2):
                        try:
                            resp = client.models.generate_content(model=m, contents=prompt)
                            return _maybe_cache(LLMResponse(resp.text or ""))
                        except Exception as e:
                            err_str = str(e).lower()
                            last_err = e
                            if "429" in err_str or "quota" in err_str or "rate" in err_str:
                                # This key is rate-limited, try next key
                                print(f"[MultiLLM] Gemini key ...{api_key[-6:]} rate-limited → trying next key")
                                break
                            elif "503" in err_str or "unavailable" in err_str or "high demand" in err_str:
                                time.sleep(1.5)
                                continue
                            elif "404" in err_str:
                                break  # Model not found, try next model
                            else:
                                time.sleep(1.0)
                    else:
                        continue
                    break  # Key rate-limited, try next key

            raise RuntimeError(f"All LLM providers failed. Last Gemini error: {last_err}")

        raise ValueError("No valid LLM provider configured. Set free_proxy_enabled:true or add a gemini_api_key in config/api_keys.json.")


def get_llm_model(preferred_provider: str = None, model: str = None) -> MultiLLMClient:
    return MultiLLMClient(preferred_provider=preferred_provider, model=model)


def test_llm_provider(
    provider: str,
    api_key: str = "",
    custom_url: str = "",
    custom_model: str = "",
) -> tuple[bool, str, float]:
    """Test API key and latency for a given provider.
    Returns (success: bool, status_message: str, latency_ms: float).
    """
    prov = (provider or "").lower().strip()
    cfg = _load_config()
    t0 = time.perf_counter()

    try:
        if prov in ("gemini-web", "free", "free-proxy"):
            port = int(cfg.get("free_proxy_port", 8081))
            try:
                resp = requests.get(f"http://127.0.0.1:{port}/health", timeout=3.0)
                lat = (time.perf_counter() - t0) * 1000.0
                if resp.status_code == 200 and resp.json().get("status") == "ok":
                    return True, "Gemini Web FREE (Anonymous)", lat
                return False, f"Proxy not responding (HTTP {resp.status_code})", lat
            except requests.exceptions.ConnectionError:
                lat = (time.perf_counter() - t0) * 1000.0
                return False, "Proxy not running (start_proxy() not called)", lat

        elif prov == "groq":
            key = api_key.strip() or cfg.get("groq_api_key", "").strip()
            if not key:
                return False, "Missing Groq API Key", 0.0
            resp = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=6.0,
            )
            lat = (time.perf_counter() - t0) * 1000.0
            if resp.status_code == 200:
                return True, "Groq Live (~350 tok/s)", lat
            return False, f"Groq Error {resp.status_code}", lat

        elif prov == "openrouter":
            key = api_key.strip() or cfg.get("openrouter_api_key", "").strip()
            if not key:
                return False, "Missing OpenRouter API Key", 0.0
            resp = requests.get(
                "https://openrouter.ai/api/v1/auth/key",
                headers={"Authorization": f"Bearer {key}"},
                timeout=6.0,
            )
            lat = (time.perf_counter() - t0) * 1000.0
            if resp.status_code == 200:
                return True, "OpenRouter Live (R1 / V3)", lat
            return False, f"OpenRouter Error {resp.status_code}", lat

        elif prov == "deepseek":
            key = api_key.strip() or cfg.get("deepseek_api_key", "").strip()
            if not key:
                return False, "Missing DeepSeek API Key", 0.0
            resp = requests.get(
                "https://api.deepseek.com/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=6.0,
            )
            lat = (time.perf_counter() - t0) * 1000.0
            if resp.status_code == 200:
                return True, "DeepSeek Live", lat
            return False, f"DeepSeek Error {resp.status_code}", lat

        elif prov == "gemini":
            key = api_key.strip() or cfg.get("gemini_api_key", "").strip()
            if not key:
                return False, "Missing Gemini API Key", 0.0
            # Test key validity directly via Google Gemini REST API to eliminate socket conflicts and WinError 10013
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
            resp = requests.get(url, timeout=5.0)
            lat = (time.perf_counter() - t0) * 1000.0
            if resp.status_code == 200:
                return True, "Gemini 2.5 Flash Live", lat
            elif resp.status_code in (400, 401, 403):
                return False, f"Invalid API Key ({resp.status_code})", lat
            return False, f"Gemini HTTP {resp.status_code}", lat

        elif prov in ("custom", "ollama", "local"):
            url = (custom_url.strip() or cfg.get("custom_llm_url", "")).rstrip("/")
            if not url:
                url = "http://localhost:11434"
            # Try /v1/models or /api/tags
            target_url = f"{url}/models" if "/v1" in url else f"{url}/api/tags"
            resp = requests.get(target_url, timeout=4.0)
            lat = (time.perf_counter() - t0) * 1000.0
            if resp.status_code == 200:
                return True, "Local AI / Ollama Live", lat
            return False, f"Endpoint Error {resp.status_code}", lat

        else:
            return False, f"Unknown provider: {provider}", 0.0

    except Exception as e:
        lat = (time.perf_counter() - t0) * 1000.0
        err_msg = str(e)
        if "timeout" in err_msg.lower():
            return False, "Connection Timeout", lat
        return False, f"Failed: {err_msg[:40]}", lat


def fetch_provider_models(
    provider: str,
    api_key: str = "",
    custom_url: str = "",
) -> list[str]:
    """Dynamically query the provider's API to fetch all available models.
    Returns list of model IDs/names.
    """
    prov = (provider or "").lower().strip()
    cfg = _load_config()

    try:
        if prov == "groq":
            key = api_key.strip() or cfg.get("groq_api_key", "").strip()
            if not key:
                return ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "deepseek-r1-distill-llama-70b"]
            resp = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=5.0,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                models = [m["id"] for m in data if "id" in m and not m["id"].startswith("whisper")]
                return sorted(models) if models else ["llama-3.3-70b-versatile"]

        elif prov == "openrouter":
            key = api_key.strip() or cfg.get("openrouter_api_key", "").strip()
            headers = {"Authorization": f"Bearer {key}"} if key else {}
            resp = requests.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=6.0)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                models = [m["id"] for m in data if "id" in m]
                # Filter top models first
                popular = [m for m in models if any(x in m for x in ("deepseek", "llama-3.3", "claude-3.5", "gpt-4o"))]
                return popular[:20] if popular else models[:20]

        elif prov == "deepseek":
            key = api_key.strip() or cfg.get("deepseek_api_key", "").strip()
            if not key:
                return ["deepseek-chat", "deepseek-reasoner"]
            resp = requests.get(
                "https://api.deepseek.com/models",
                headers={"Authorization": f"Bearer {key}"},
                timeout=5.0,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                models = [m["id"] for m in data if "id" in m]
                return models if models else ["deepseek-chat", "deepseek-reasoner"]

        elif prov == "gemini":
            key = api_key.strip() or cfg.get("gemini_api_key", "").strip()
            if key:
                try:
                    from google import genai
                    client = genai.Client(api_key=key)
                    models = []
                    for m in client.models.list():
                        name = getattr(m, "name", "")
                        clean_name = name.replace("models/", "")
                        if "gemini" in clean_name.lower():
                            models.append(clean_name)
                    if models:
                        return sorted(models)
                except Exception:
                    pass
            return ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-2.5-pro"]

        elif prov in ("custom", "ollama", "local"):
            url = (custom_url.strip() or cfg.get("custom_llm_url", "")).rstrip("/")
            if not url:
                url = "http://localhost:11434"
            try:
                # Try ollama /api/tags
                resp = requests.get(f"{url}/api/tags", timeout=3.0)
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", []) if "name" in m]
                    if models:
                        return models
                # Try OpenAI-compatible /v1/models
                resp = requests.get(f"{url}/v1/models", timeout=3.0)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    models = [m["id"] for m in data if "id" in m]
                    if models:
                        return models
            except Exception:
                pass
            return ["llama3.2", "qwen2.5-coder", "mistral"]

    except Exception:
        pass

    return ["default"]


