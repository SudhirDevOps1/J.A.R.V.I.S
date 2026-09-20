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
import concurrent.futures
import json
import os
import sys
import time
from pathlib import Path

import requests

# ─── Optional free proxy + cache ─────────────────────────────────────────────
try:
    from core.gemini_free_proxy import is_running as _proxy_is_running, get_url as _proxy_url, get_auth_token as _proxy_token
    _HAS_FREE_PROXY = True
except ImportError:
    _HAS_FREE_PROXY = False
    def _proxy_is_running(): return False
    def _proxy_url(): return "http://127.0.0.1:8081/v1"
    def _proxy_token(): return ""

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

# Per-key 429 cooldown: a rate-limited key is skipped for 5 minutes instead of
# being hammered on every query. Thread-safe; best-effort (never breaks routing).
_key_cooldown_until: dict[str, float] = {}
_key_cooldown_lock = __import__("threading").Lock()
_KEY_COOLDOWN_SECS = 300.0


def _key_in_cooldown(api_key: str) -> bool:
    try:
        with _key_cooldown_lock:
            until = _key_cooldown_until.get(api_key, 0.0)
        return bool(until) and time.monotonic() < until
    except Exception:
        return False


def _cool_key_down(api_key: str) -> None:
    try:
        with _key_cooldown_lock:
            _key_cooldown_until[api_key] = time.monotonic() + _KEY_COOLDOWN_SECS
    except Exception:
        pass


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
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    try:  # ADDITIVE: ENC blobs transparent (plaintext passthrough)
        from core.secret_vault import decrypt_dict
        return decrypt_dict(data)
    except Exception:
        return data if isinstance(data, dict) else {}


def _selected_proxy_version() -> int:
    """Which free-proxy implementation the config flag selects (1=v1, 2=v2)."""
    try:
        v = int((_load_config().get("proxy_version", 1)) or 1)
        return v if v in (1, 2) else 1
    except Exception:
        return 1


def _proxy_active_is_running() -> bool:
    """True if the SELECTED proxy version is running (v1 flag reads v1, v2 flag reads v2)."""
    if _selected_proxy_version() == 2:
        try:
            from core.gemini_free_proxy_v2 import is_running as _running_v2
            return bool(_running_v2())
        except Exception:
            return False
    try:
        return bool(_proxy_is_running())
    except Exception:
        return False


def _proxy_active_token() -> str:
    """Bearer token for the SELECTED proxy version ('' if unavailable)."""
    if _selected_proxy_version() == 2:
        try:
            from core.gemini_free_proxy_v2 import get_auth_token as _token_v2
            return _token_v2() or ""
        except Exception:
            return ""
    try:
        return _proxy_token() or ""
    except Exception:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Complete Provider Registry & Model Catalog
# ─────────────────────────────────────────────────────────────────────────────
PROVIDER_REGISTRY: dict[str, dict] = {
    "cerebras": {
        "name": "Cerebras Cloud (Ultra-Fast ~2,000 tok/s)",
        "url": "https://api.cerebras.ai/v1",
        "key_field": "cerebras_api_key",
        "default_model": "llama-3.3-70b",
        "models": ["llama-3.3-70b", "llama3.1-8b", "llama3.1-70b"],
        "requires_key": True,
        "placeholder": "csk-...",
        "desc": "1M tokens/day, 30 RPM. World's fastest inference engine.",
    },
    "groq": {
        "name": "Groq LPU (Ultra-Fast ~350-1000 tok/s)",
        "url": "https://api.groq.com/openai/v1",
        "key_field": "groq_api_key",
        "default_model": "llama-3.3-70b-versatile",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "deepseek-r1-distill-llama-70b", "gemma2-9b-it"],
        "requires_key": True,
        "placeholder": "gsk_...",
        "desc": "30 RPM, 1K RPD. Highly reliable and ultra low-latency.",
    },
    "openrouter": {
        "name": "OpenRouter (20+ Free Models & Unified API)",
        "url": "https://openrouter.ai/api/v1",
        "key_field": "openrouter_api_key",
        "default_model": "deepseek/deepseek-r1:free",
        "models": [
            "deepseek/deepseek-r1:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemini-2.0-flash-exp:free",
            "mistralai/mistral-7b-instruct:free",
            "qwen/qwen-2.5-72b-instruct",
            "meta-llama/llama-3.1-8b-instruct:free",
        ],
        "requires_key": True,
        "placeholder": "sk-or-...",
        "desc": "One key for 200+ models. Free models indicated with :free suffix.",
    },
    "gemini": {
        "name": "Google Gemini (Gemini 2.0 / 1.5 Flash)",
        "url": "https://generativelanguage.googleapis.com",
        "key_field": "gemini_api_key",
        "default_model": "gemini-2.0-flash",
        "models": ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro"],
        "requires_key": True,
        "placeholder": "AIzaSy...",
        "desc": "1M token context window, live audio and vision.",
    },
    "gemini-web": {
        "name": "Gemini Web FREE (Built-in Anonymous Proxy - 0 Key)",
        "url": "http://127.0.0.1:8081/v1",
        "key_field": "free_proxy_token",
        "default_model": "gemini-3.7-flash",
        "models": ["gemini-3.7-flash", "gemini-2.0-flash", "gemini-2.0-pro"],
        "requires_key": False,
        "placeholder": "None needed (runs locally)",
        "desc": "100% Free, zero tokens, zero credit card.",
    },
    "nvidia": {
        "name": "NVIDIA NIM (70+ Models, 1000 Free Calls/mo)",
        "url": "https://integrate.api.nvidia.com/v1",
        "key_field": "nvidia_api_key",
        "default_model": "meta/llama-3.3-70b-instruct",
        "models": [
            "meta/llama-3.3-70b-instruct",
            "deepseek-ai/deepseek-r1",
            "mistralai/mistral-large-2-instruct",
            "nvidia/nemotron-4-340b-instruct",
        ],
        "requires_key": True,
        "placeholder": "nvapi-...",
        "desc": "1000 API calls/model/month, enterprise-grade inference.",
    },
    "mistral": {
        "name": "Mistral AI (Codestral & Mistral - 1B tok/mo)",
        "url": "https://api.mistral.ai/v1",
        "key_field": "mistral_api_key",
        "default_model": "mistral-small-latest",
        "models": [
            "mistral-small-latest",
            "codestral-latest",
            "mistral-large-latest",
            "open-mistral-nemo",
        ],
        "requires_key": True,
        "placeholder": "mis_...",
        "desc": "1B tokens/month, 500K TPM. GDPR-compliant European AI.",
    },
    "cloudflare": {
        "name": "Cloudflare Workers AI (10K Neurons/day Free)",
        "url": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
        "key_field": "cloudflare_api_key",
        "default_model": "@cf/meta/llama-3.3-70b-instruct",
        "models": [
            "@cf/meta/llama-3.3-70b-instruct",
            "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b",
            "@cf/mistral/mistral-7b-instruct-v0.1",
            "@cf/qwen/qwen1.5-14b-chat-awq",
        ],
        "requires_key": True,
        "placeholder": "Bearer token...",
        "desc": "Serverless edge AI, no credit card required.",
    },
    "cohere": {
        "name": "Cohere (Command-R & RAG Embeddings)",
        "url": "https://api.cohere.com/v2",
        "key_field": "cohere_api_key",
        "default_model": "command-r-plus-08-2024",
        "models": ["command-r-plus-08-2024", "command-r-08-2024", "command-light"],
        "requires_key": True,
        "placeholder": "co_...",
        "desc": "1,000 calls/month free. Best for RAG & structured citations.",
    },
    "zhipu": {
        "name": "Zhipu AI / Z.AI (GLM-4-Flash Permanent Free)",
        "url": "https://open.bigmodel.cn/api/paas/v4",
        "key_field": "zhipu_api_key",
        "default_model": "glm-4-flash",
        "models": ["glm-4-flash", "glm-4-plus", "glm-4-air", "glm-4"],
        "requires_key": True,
        "placeholder": "api_key.token...",
        "desc": "GLM-4.7-Flash with 200K context, permanently free.",
    },
    "github": {
        "name": "GitHub Models (Free GPT-4o, DeepSeek-R1, Llama 4)",
        "url": "https://models.inference.ai.azure.com",
        "key_field": "github_token",
        "default_model": "gpt-4o-mini",
        "models": [
            "gpt-4o-mini",
            "gpt-4o",
            "DeepSeek-R1",
            "Meta-Llama-3.3-70B-Instruct",
            "Phi-3.5-mini-instruct",
        ],
        "requires_key": True,
        "placeholder": "ghp_... or github_pat_...",
        "desc": "Access cutting-edge models directly using your GitHub token.",
    },
    "huggingface": {
        "name": "Hugging Face Inference API (500K+ Models)",
        "url": "https://api-inference.huggingface.co/v1",
        "key_field": "huggingface_token",
        "default_model": "meta-llama/Llama-3.2-3B-Instruct",
        "models": [
            "meta-llama/Llama-3.2-3B-Instruct",
            "Qwen/Qwen2.5-72B-Instruct",
            "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
            "mistralai/Mistral-7B-Instruct-v0.3",
        ],
        "requires_key": True,
        "placeholder": "hf_...",
        "desc": "Largest open-source catalog with free serverless inference.",
    },
    "sambanova": {
        "name": "SambaNova Cloud (Free Llama 3.1 405B & 70B)",
        "url": "https://api.sambanova.ai/v1",
        "key_field": "sambanova_api_key",
        "default_model": "Meta-Llama-3.1-405B-Instruct",
        "models": [
            "Meta-Llama-3.1-405B-Instruct",
            "Meta-Llama-3.3-70B-Instruct",
            "DeepSeek-R1",
            "Meta-Llama-3.1-8B-Instruct",
        ],
        "requires_key": True,
        "placeholder": "samba_...",
        "desc": "20 RPM, 200K tokens/day. Mammoth 405B model available free.",
    },
    "kluster": {
        "name": "Kluster AI (DeepSeek R1, Llama, Qwen3)",
        "url": "https://api.kluster.ai/v1",
        "key_field": "kluster_api_key",
        "default_model": "deepseek-ai/DeepSeek-R1",
        "models": [
            "deepseek-ai/DeepSeek-R1",
            "meta-llama/Llama-3.3-70B-Instruct",
            "Qwen/Qwen2.5-72B-Instruct",
        ],
        "requires_key": True,
        "placeholder": "kluster_...",
        "desc": "$5 free credits + permanent free tier for batch tasks.",
    },
    "llm7": {
        "name": "LLM7.io (Zero-Friction, No Signup Needed)",
        "url": "https://api.llm7.io/v1",
        "key_field": "llm7_token",
        "default_model": "llama-3.3-70b",
        "models": ["llama-3.3-70b", "deepseek-r1", "gpt-4o-mini"],
        "requires_key": False,
        "placeholder": "Optional token (30-120 RPM)",
        "desc": "Instant zero-friction API without requiring sign up.",
    },
    "freellmapi": {
        "name": "FreeLLMAPI Aggregator (1.7B Tokens/mo, Failover)",
        "url": "https://api.freellmapi.com/v1",
        "key_field": "freellmapi_key",
        "default_model": "auto",
        "models": ["auto", "gpt-4o-mini", "deepseek-v3", "claude-3-haiku", "llama-3.3-70b"],
        "requires_key": True,
        "placeholder": "freellm_...",
        "desc": "Automatic failover across 14+ providers, eliminates 429 errors.",
    },
    "orcarouter": {
        "name": "OrcaRouter ($0 / token, 200+ Free Models)",
        "url": "https://api.orcarouter.com/v1",
        "key_field": "orcarouter_key",
        "default_model": "auto",
        "models": ["auto", "deepseek-r1", "llama-3.3-70b", "mistral-small"],
        "requires_key": True,
        "placeholder": "orca_...",
        "desc": "Free model routing tier with zero markup.",
    },
    "vercel": {
        "name": "Vercel AI Gateway (Unified Multi-Provider)",
        "url": "https://ai.gateway.vercel.dev/v1",
        "key_field": "vercel_gateway_key",
        "default_model": "auto",
        "models": ["auto", "openai/gpt-4o-mini", "anthropic/claude-3-5-sonnet", "meta/llama-3.3-70b"],
        "requires_key": True,
        "placeholder": "vercel_...",
        "desc": "Zero markup gateway with BYOK failover.",
    },
    "freetheai": {
        "name": "FreeTheAi (60+ Community Models, Free Forever)",
        "url": "https://api.freetheai.com/v1",
        "key_field": "freetheai_key",
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "llama-3.3-70b", "qwen-2.5-72b"],
        "requires_key": True,
        "placeholder": "ftai_...",
        "desc": "Community-run Discord signup, free forever.",
    },
    "omniroute": {
        "name": "OmniRoute Gateway (Local 352+ Providers, 1200+ Models)",
        "url": "http://localhost:20128/v1",
        "key_field": "omniroute_token",
        "default_model": "auto",
        "models": ["auto", "gpt-4o", "claude-3.5-sonnet", "gemini-2.0-flash", "deepseek-r1"],
        "requires_key": False,
        "placeholder": "None needed (localhost:20128)",
        "desc": "Universal local gateway. Auto-switches across 350+ backends.",
    },
    "deepseek": {
        "name": "DeepSeek Direct (DeepSeek-V3 / R1 Official)",
        "url": "https://api.deepseek.com/v1",
        "key_field": "deepseek_api_key",
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "requires_key": True,
        "placeholder": "sk-...",
        "desc": "Official DeepSeek endpoint for V3 and Reasoner R1.",
    },
    "custom": {
        "name": "Custom / Local AI (Ollama, LM Studio, vLLM)",
        "url": "http://localhost:11434/v1",
        "key_field": "custom_llm_api_key",
        "default_model": "llama3.2",
        "models": ["llama3.2", "qwen2.5-coder", "mistral", "deepseek-r1"],
        "requires_key": False,
        "placeholder": "Optional key (Ollama uses dummy)",
        "desc": "Run 100% locally on your own GPU/CPU without internet.",
    },
}


class MultiLLMClient:
    def __init__(self, preferred_provider: str = None, model: str = None):
        cfg = _load_config()
        self.gemini_key = cfg.get("gemini_api_key", "").strip()
        self.groq_key = cfg.get("groq_api_key", "").strip()
        self.openrouter_key = cfg.get("openrouter_api_key", "").strip()
        self.deepseek_key = cfg.get("deepseek_api_key", "").strip()

        # ── Load all registered provider keys dynamically ──────────────
        self.provider_keys = {}
        for pid, meta in PROVIDER_REGISTRY.items():
            kfield = meta.get("key_field")
            if kfield:
                self.provider_keys[pid] = cfg.get(kfield, "").strip()

        self.selected_models = cfg.get("selected_models", {})
        if not isinstance(self.selected_models, dict):
            self.selected_models = {}

        # ── Legacy single custom endpoint (kept for backward compat) ──────────
        self.custom_url = (cfg.get("custom_llm_url") or cfg.get("openai_url") or "").strip()
        self.custom_key = (cfg.get("custom_llm_api_key") or cfg.get("openai_api_key") or "dummy-key").strip()
        self.custom_model = cfg.get("custom_llm_model") or "llama3.2"

        # ── Multi Custom Providers (new: named, prioritized, enable/disable) ──
        _raw_providers = cfg.get("custom_providers", [])
        if isinstance(_raw_providers, list):
            # Normalize + sort by priority (lower number = higher priority)
            self.custom_providers = sorted(
                [p for p in _raw_providers
                 if isinstance(p, dict) and p.get("url", "").strip() and p.get("enabled", True)],
                key=lambda p: int(p.get("priority", 99))
            )
        else:
            self.custom_providers = []

        # ── OmniRoute (auto-detect on localhost:20128) ────────────────────────
        self.omniroute_auto_detect = cfg.get("omniroute_auto_detect", True)
        self.omniroute_url = "http://localhost:20128/v1"
        self._omniroute_checked = False
        self._omniroute_running = False

        # ── Free proxy (gemini-web anonymous mode) ────────────────────────────
        self.free_proxy_enabled = cfg.get("free_proxy_enabled", True)
        self.free_proxy_port = int(cfg.get("free_proxy_port", 8081))
        self.free_proxy_model = cfg.get("free_proxy_model", "gemini-3.7-flash")

        # ── Multi-key Gemini rotation ─────────────────────────────────────────
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
            if self.omniroute_auto_detect and self._check_omniroute():
                self.provider = "omniroute"
            elif self.free_proxy_enabled and _proxy_active_is_running():
                self.provider = "gemini-web"
            elif self.custom_providers:
                self.provider = "custom-list"
            elif self.provider_keys.get("cerebras"):
                self.provider = "cerebras"
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

        # Determine active model
        if model:
            self.model = model
        elif self.provider in self.selected_models:
            self.model = self.selected_models[self.provider]
        elif self.provider in PROVIDER_REGISTRY:
            self.model = PROVIDER_REGISTRY[self.provider].get("default_model")
        else:
            self.model = self.custom_model

    def _check_omniroute(self) -> bool:
        """Check if OmniRoute is running on localhost:20128. Cached per instance."""
        if self._omniroute_checked:
            return self._omniroute_running
        self._omniroute_checked = True
        try:
            resp = requests.get(f"{self.omniroute_url.rstrip('/v1')}/health",
                                timeout=1.5)
            if resp.status_code == 200:
                self._omniroute_running = True
                return True
            # Non-200 (e.g. 404 = some OTHER service on this port) proves
            # nothing — verify with the real /v1/models endpoint instead.
            resp = requests.get(f"{self.omniroute_url}/models", timeout=1.5)
            self._omniroute_running = resp.status_code == 200
        except Exception:
            try:
                # Try /v1/models as fallback health check
                resp = requests.get(f"{self.omniroute_url}/models", timeout=1.5)
                self._omniroute_running = resp.status_code == 200
            except Exception:
                self._omniroute_running = False
        return self._omniroute_running

    def _try_openai_endpoint(self, url: str, api_key: str, model: str, prompt: str,
                              timeout: int = 60, provider_name: str = "custom") -> str | None:
        """
        Shared helper: call any OpenAI-compatible /v1/chat/completions endpoint.
        Returns response text on success, None on failure (caller handles fallback).
        """
        endpoint = url.rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            endpoint = (f"{endpoint}/chat/completions"
                        if endpoint.endswith("/v1")
                        else f"{endpoint}/v1/chat/completions")
        key = api_key.strip() or "dummy-key"
        mdl = (model or "gpt-3.5-turbo").strip()
        try:
            res = requests.post(
                endpoint,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": mdl, "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.3},
                timeout=timeout,
            )
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]
            else:
                print(f"[MultiLLM] {provider_name} HTTP {res.status_code}: {res.text[:120]}")
        except Exception as e:
            print(f"[MultiLLM] {provider_name} failed: {e}")
        return None

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
        # Both v1 and v2 require the proxy bearer token (no longer "none"):
        # it is generated at proxy start and read here version-aware.
        if self.free_proxy_enabled and _proxy_active_is_running():
            model = self.model or self.free_proxy_model
            endpoint = f"http://127.0.0.1:{self.free_proxy_port}/v1/chat/completions"
            try:
                res = requests.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {_proxy_active_token() or 'none'}",
                             "Content-Type": "application/json"},
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

        # ── 0-A. OmniRoute Gateway (352+ providers, auto-fallback, localhost:20128) ──
        if self.omniroute_auto_detect and self._check_omniroute():
            model = self.model or "auto"
            out = self._try_openai_endpoint(
                self.omniroute_url, "omniroute", model, prompt,
                timeout=90, provider_name="OmniRoute"
            )
            if out:
                return _maybe_cache(LLMResponse(out))
            print("[MultiLLM] OmniRoute failed — falling back to next provider")

        # ── 0-B. Custom Providers List (named, prioritized) ────────────────────
        for cp in self.custom_providers:
            name = cp.get("name", "Custom")
            url  = cp.get("url", "").strip()
            key  = cp.get("api_key", "") or "dummy-key"
            mdl  = self.model or cp.get("model", "gpt-3.5-turbo")
            if not url:
                continue
            out = self._try_openai_endpoint(url, key, mdl, prompt,
                                             timeout=75, provider_name=name)
            if out:
                return _maybe_cache(LLMResponse(out))
            print(f"[MultiLLM] {name} failed — trying next provider")

        # ── 0-C. Registered Providers (Cerebras, Groq, NVIDIA, Mistral, GitHub, SambaNova, etc.) ──
        if self.provider in PROVIDER_REGISTRY and self.provider not in ("gemini", "gemini-web"):
            reg = PROVIDER_REGISTRY[self.provider]
            p_key = self.provider_keys.get(self.provider) or "dummy-key"
            p_model = self.model or reg.get("default_model")
            p_url = reg.get("url")
            out = self._try_openai_endpoint(
                p_url, p_key, p_model, prompt, timeout=60, provider_name=reg.get("name", self.provider)
            )
            if out:
                return _maybe_cache(LLMResponse(out))
            print(f"[MultiLLM] {self.provider} failed — attempting secondary fallback")

        # 1. Legacy Single Custom Provider (Ollama / LM Studio / LocalAI / Private Endpoints)
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

            candidate_models = [
                "gemini-flash-latest",
                "gemini-2.5-flash-lite",
                "gemini-2.5-flash",
                "gemini-3.7-flash",
                "gemini-1.5-flash",
                "gemini-2.0-flash",
            ]
            if self.model and self.model not in candidate_models:
                candidate_models.insert(0, self.model)

            last_err = None
            keys_to_try = list(self.gemini_key_pool)

            def _attempt_with_key(api_key):
                """Try every candidate model with ONE key (runs in a worker thread).

                Returns response text on success, None if this key is
                exhausted/rate-limited, raises the key's last error otherwise.
                Per-key model fallback order is unchanged — only the keys now
                race each other instead of queueing up sequentially."""
                if _key_in_cooldown(api_key):
                    return None  # 429'd recently — don't hammer, let others race
                client = genai.Client(api_key=api_key)
                key_last_err = None
                for m in candidate_models:
                    for attempt in range(2):
                        try:
                            resp = client.models.generate_content(model=m, contents=prompt)
                            return resp.text or ""
                        except Exception as e:
                            err_str = str(e).lower()
                            key_last_err = e
                            if "429" in err_str or "quota" in err_str or "rate" in err_str:
                                # This key is rate-limited (masked log, never full key)
                                try:
                                    from core.secret_vault import mask_secret
                                    _km = mask_secret(api_key)
                                except Exception:
                                    _km = "***"
                                _cool_key_down(api_key)
                                print(f"[MultiLLM] Gemini key {_km} rate-limited "
                                      f"(cooling {_KEY_COOLDOWN_SECS:.0f}s) → trying next key")
                                return None
                            elif "503" in err_str or "unavailable" in err_str or "high demand" in err_str:
                                time.sleep(1.5)
                                continue
                            elif "404" in err_str or "not found" in err_str:
                                break  # Model deprecated/not found, advance to next candidate model
                            else:
                                time.sleep(1.0)
                if key_last_err is not None:
                    raise key_last_err
                return None

            # Race all keys in parallel — first success wins. The old code tried
            # keys strictly sequentially (up to 50+ blocking HTTP calls ≈ a
            # minute worst case before failing); now total latency is bounded by
            # one overall deadline no matter how many keys are pooled.
            _deadline = 60.0
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max(1, len(keys_to_try)),
                thread_name_prefix="gemini-key",
            ) as _ex:
                _pending = {_ex.submit(_attempt_with_key, k): k for k in keys_to_try}
                try:
                    for _fut in concurrent.futures.as_completed(_pending, timeout=_deadline):
                        try:
                            _out = _fut.result()
                        except Exception as e:
                            last_err = e
                            continue
                        if _out:
                            for _p in _pending:
                                _p.cancel()
                            return _maybe_cache(LLMResponse(_out))
                        # None → this key exhausted/rate-limited; keep waiting for the rest
                except concurrent.futures.TimeoutError:
                    print(f"[MultiLLM] Gemini key race timed out after {_deadline:.0f}s")

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

        elif prov in ("omniroute", "omni-route", "omni"):
            port = 20128
            try:
                resp = requests.get(f"http://localhost:{port}/v1/models", timeout=3.0)
                lat = (time.perf_counter() - t0) * 1000.0
                if resp.status_code == 200:
                    count = len(resp.json().get("data", []))
                    return True, f"OmniRoute Live ({count} models available)", lat
                return False, f"OmniRoute HTTP {resp.status_code}", lat
            except requests.exceptions.ConnectionError:
                lat = (time.perf_counter() - t0) * 1000.0
                return False, "OmniRoute not running. Install: npm i -g omniroute", lat

        elif prov in ("custom_provider", "custom-provider"):
            # Test a specific custom provider by URL
            url = custom_url.strip()
            if not url:
                return False, "No URL provided", 0.0
            test_url = url.rstrip("/")
            if not test_url.endswith("/models"):
                test_url = (f"{test_url}/models"
                            if test_url.endswith("/v1")
                            else f"{test_url}/v1/models")
            try:
                key = api_key.strip() or "dummy-key"
                resp = requests.get(test_url,
                                    headers={"Authorization": f"Bearer {key}"},
                                    timeout=5.0)
                lat = (time.perf_counter() - t0) * 1000.0
                if resp.status_code == 200:
                    return True, f"Endpoint Live ({url[:30]}...)", lat
                return False, f"HTTP {resp.status_code}", lat
            except Exception as e:
                lat = (time.perf_counter() - t0) * 1000.0
                return False, str(e)[:40], lat

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

        elif prov in PROVIDER_REGISTRY:
            reg = PROVIDER_REGISTRY[prov]
            kfield = reg.get("key_field", f"{prov}_api_key")
            key = api_key.strip() or cfg.get(kfield, "").strip()
            if not key and kfield:
                return False, f"Missing {reg.get('name', prov)} API Key", 0.0

            base_url = reg.get("url", "")
            if "/chat/completions" in base_url:
                models_url = base_url.replace("/chat/completions", "/models")
            elif base_url.endswith("/v1"):
                models_url = f"{base_url}/models"
            else:
                models_url = f"{base_url.rstrip('/')}/models"

            headers = {"Content-Type": "application/json"}
            if key:
                headers["Authorization"] = f"Bearer {key}"
            if prov == "openrouter":
                headers["HTTP-Referer"] = "https://github.com/SudhirDevOps1"
                headers["X-Title"] = "SudhirDevOps1 AI"

            try:
                resp = requests.get(models_url, headers=headers, timeout=5.0)
                lat = (time.perf_counter() - t0) * 1000.0
                if resp.status_code == 200:
                    return True, f"{reg.get('name', prov)} Live", lat
                elif resp.status_code in (401, 403):
                    return False, f"Invalid API Key ({resp.status_code})", lat

                # Fallback: lightweight single-token prompt test
                chat_url = base_url if "/chat/completions" in base_url else (f"{base_url}/chat/completions" if base_url.endswith("/v1") else f"{base_url}/v1/chat/completions")
                body = {
                    "model": reg.get("default_model", ""),
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1
                }
                c_resp = requests.post(chat_url, headers=headers, json=body, timeout=5.0)
                lat = (time.perf_counter() - t0) * 1000.0
                if c_resp.status_code == 200:
                    return True, f"{reg.get('name', prov)} Live", lat
                return False, f"{reg.get('name', prov)} HTTP {c_resp.status_code}", lat
            except Exception as ex:
                lat = (time.perf_counter() - t0) * 1000.0
                return False, f"Connection Failed: {str(ex)[:35]}", lat

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
            return ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro"]

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

        elif prov in ("omniroute", "omni-route", "omni"):
            try:
                resp = requests.get("http://localhost:20128/v1/models", timeout=4.0)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    models = [m["id"] for m in data if "id" in m]
                    if models:
                        return models[:50]  # Limit to 50 - OmniRoute has 1200+ models
            except Exception:
                pass
            return ["auto", "gpt-4o", "claude-3.5-sonnet", "gemini-2.0-flash", "deepseek-r1"]

        elif prov in ("custom_provider", "custom-provider"):
            url = custom_url.strip().rstrip("/")
            if not url:
                return ["default"]
            key = api_key.strip() or "dummy-key"
            try:
                test_url = (f"{url}/models"
                            if url.endswith("/v1")
                            else f"{url}/v1/models")
                resp = requests.get(test_url,
                                    headers={"Authorization": f"Bearer {key}"},
                                    timeout=4.0)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    if data:
                        return [m["id"] for m in data if "id" in m][:30]
                resp2 = requests.get(f"{url.rstrip('/v1')}/api/tags", timeout=3.0)
                if resp2.status_code == 200:
                    return [m["name"] for m in resp2.json().get("models", []) if "name" in m]
            except Exception:
                pass
            return ["auto"]

        elif prov in PROVIDER_REGISTRY:
            reg = PROVIDER_REGISTRY[prov]
            curated = list(reg.get("models", []))
            kfield = reg.get("key_field", f"{prov}_api_key")
            key = api_key.strip() or cfg.get(kfield, "").strip()
            base_url = reg.get("url", "")
            if base_url:
                models_url = (
                    base_url.replace("/chat/completions", "/models")
                    if "/chat/completions" in base_url
                    else (f"{base_url}/models" if base_url.endswith("/v1") else f"{base_url.rstrip('/')}/models")
                )
                headers = {"Authorization": f"Bearer {key}"} if key else {}
                try:
                    resp = requests.get(models_url, headers=headers, timeout=4.0)
                    if resp.status_code == 200:
                        data = resp.json().get("data", [])
                        fetched = [
                            m["id"]
                            for m in data
                            if "id" in m and not str(m["id"]).startswith("whisper")
                        ]
                        if fetched:
                            combined = []
                            for m in curated + fetched:
                                if m not in combined:
                                    combined.append(m)
                            return combined[:60]
                except Exception:
                    pass
            return curated if curated else [reg.get("default_model", "default")]

    except Exception:
        pass

    return ["default"]


