import json
import os
import sys
import threading as _th
from pathlib import Path

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR    = get_base_dir()
CONFIG_DIR  = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"

# ── Safe-write helpers (additive, bina kuch hataye) ──────────────────────────
# Har config write se pehle timestamped .bak backup + tmp-file + os.replace
# atomic write taaki crash par config corrupt na ho. Purana logic untouched.
def _backup_config() -> str | None:
    """api_keys.json ka timestamped backup banata hai. Returns backup path ya None."""
    try:
        if not CONFIG_FILE.exists():
            return None
        from datetime import datetime as _dt
        import shutil as _sh
        ensure_config_dir()
        ts = _dt.now().strftime("%Y%m%d-%H%M%S")
        bak = CONFIG_DIR / f"api_keys.json.bak-{ts}"
        _sh.copy2(str(CONFIG_FILE), str(bak))
        # purane backups max 5 rakho, baaki untouched (delete sirf apne banaye .bak-*)
        try:
            olds = sorted(CONFIG_DIR.glob("api_keys.json.bak-*"))
            for _old in olds[:-5]:
                try:
                    _old.unlink()
                except Exception:
                    pass
        except Exception:
            pass
        return str(bak)
    except Exception:
        return None


def _atomic_write_json(path: Path, data: dict) -> None:
    """Tmp-file + os.replace atomic write (crash-safe)."""
    import tempfile as _tf
    ensure_config_dir()
    fd, _tmp = _tf.mkstemp(dir=str(path.parent), prefix=path.name + ".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as _f:
            json.dump(data, _f, indent=4)
        os.replace(_tmp, path)
    except Exception:
        try:
            if os.path.exists(_tmp):
                os.remove(_tmp)
        except Exception:
            pass
        raise
    finally:
        # Additive: secrets chmod 600 (Windows par ignore, kuch hataya nahi)
        try:
            _secure_secret_perms(path)
        except Exception:
            pass


def _secure_secret_perms(path: Path) -> None:
    """api_keys.json etc par 0o600 lagao + rotate warning (additive, no delete)."""
    try:
        if os.name != "nt":
            os.chmod(path, 0o600)
    except Exception:
        pass

def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def config_exists() -> bool:
    return CONFIG_FILE.exists()

def save_api_keys(gemini_api_key: str) -> None:
    # Routed via _patch_config: backup + file-lock + atomic write (indent cosmetic only)
    _patch_config(gemini_api_key=gemini_api_key.strip())

def load_api_keys() -> dict:
    """Load config with secrets transparently decrypted (in-memory only).
    Disk stays encrypted (ENC blobs); every existing reader keeps working."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ Failed to load api_keys.json: {e}")
        return {}
    try:
        from core.secret_vault import decrypt_dict
        return decrypt_dict(data)
    except Exception:
        return data if isinstance(data, dict) else {}

def get_gemini_key() -> str | None:
    return load_api_keys().get("gemini_api_key")

def is_configured() -> bool:
    key = get_gemini_key()
    return bool(key and len(key) > 15)


def get_assistant_name() -> str:
    """Return the configured assistant name, or 'JARVIS' if not set."""
    return load_api_keys().get("assistant_name", "JARVIS") or "JARVIS"


def get_app_name() -> str:
    """Return the configured app name, or 'SudhirDevOps1 AI' if not set."""
    return load_api_keys().get("app_name", "SudhirDevOps1 AI") or "SudhirDevOps1 AI"


def get_protocol_name() -> str:
    """Return the configured protocol name, or 'DevOps' if not set."""
    return load_api_keys().get("app_protocol", "DevOps") or "DevOps"


def get_version() -> str:
    """Return the application version string."""
    try:
        from core.version import __version__
        return __version__
    except Exception:
        return "1.0.0"


def get_user_name() -> str:
    """Return the configured user name for addressing."""
    return load_api_keys().get("user_name", "")


def save_assistant_config(assistant_name: str, user_name: str) -> None:
    """Persist assistant name and user name to config."""
    _patch_config(assistant_name=assistant_name.strip() or "JARVIS",
                  user_name=user_name.strip())


# ── Assistant voice ──────────────────────────────────────────────────────────
# Gemini Live prebuilt voices. Names are proper nouns — identical in every
# language, so this list is safe to show verbatim in any locale.
AVAILABLE_VOICES = ["Charon", "Puck", "Kore", "Fenrir", "Aoede"]
DEFAULT_VOICE    = "Charon"


def get_voice() -> str:
    """Return the configured Live voice, falling back to the default if unset
    or if the stored value is not a voice we recognise."""
    v = load_api_keys().get("voice_name", DEFAULT_VOICE) or DEFAULT_VOICE
    return v if v in AVAILABLE_VOICES else DEFAULT_VOICE


def save_voice(voice_name: str) -> None:
    """Persist the chosen Live voice. Unknown names collapse to the default so a
    bad value can never reach the API and break the session."""
    v = (voice_name or "").strip()
    _patch_config(voice_name=v if v in AVAILABLE_VOICES else DEFAULT_VOICE)


def get_wake_word_enabled() -> bool:
    """Whether local wake-word gating is on (assistant sleeps until 'Hey Jarvis')."""
    return load_api_keys().get("wake_word_enabled", False)


def save_wake_word_enabled(enabled: bool) -> None:
    _patch_config(wake_word_enabled=bool(enabled))


def get_brief_enabled() -> bool:
    return load_api_keys().get("morning_brief_enabled", True)


def save_brief_enabled(enabled: bool) -> None:
    _patch_config(morning_brief_enabled=enabled)


# ── Audio devices ────────────────────────────────────────────────────────────
# Stored as device NAMES, not sounddevice indices. Indices shift every time a
# USB device is plugged in or removed, so a saved index silently starts pointing
# at a different microphone. The empty string means "system default", which is
# both the factory setting and what an unresolvable saved device falls back to —
# so unplugging a headset degrades to the built-in speakers instead of crashing.

_CONFIG_LOCK = _th.Lock()


def _patch_config(**fields) -> None:
    """Read-modify-write one or more keys in api_keys.json.

    Every setter in this file open-coded this. Collapsing it here means a new
    setting is one line, and there is one place where a corrupt config file is
    handled instead of nine. File-lock + backup + atomic write (crash-safe)."""
    with _CONFIG_LOCK:
        ensure_config_dir()
        data: dict = {}
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        # ADDITIVE: secret-looking values encrypted at rest (ENC blobs on disk).
        # Plaintext readers unaffected (load decrypts); non-secrets untouched.
        # Nested dicts (obsidian_config, plugin_config) handled recursively.
        try:
            from core.secret_vault import is_secret_key, encrypt_value

            def _enc_walk(obj):
                if isinstance(obj, dict):
                    return {k: (encrypt_value(v) if isinstance(v, str) and is_secret_key(str(k)) and v.strip() else _enc_walk(v)) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [_enc_walk(x) for x in obj]
                return obj

            fields = _enc_walk(dict(fields))
        except Exception:
            pass
        data.update(fields)
        try:
            _backup_config()
        except Exception:
            pass
        try:
            _atomic_write_json(CONFIG_FILE, data)
        except Exception:
            CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")


def get_input_device() -> str:
    """Microphone device name, or '' for the system default."""
    return (load_api_keys().get("input_device", "") or "").strip()


def save_input_device(name: str) -> None:
    _patch_config(input_device=(name or "").strip())


def get_output_device() -> str:
    """Speaker device name, or '' for the system default."""
    return (load_api_keys().get("output_device", "") or "").strip()


def save_output_device(name: str) -> None:
    _patch_config(output_device=(name or "").strip())


def get_plugin_enabled(plugin_name: str) -> bool:
    """Plugins are enabled by default the moment they're discovered (opt-out model)."""
    return load_api_keys().get("plugins_enabled", {}).get(plugin_name, True)


# ── Per-plugin settings ("tokens" / connection details) ───────────────────────
# Generic store so a plugin can declare its own config fields (PLUGIN_SETTINGS)
# and the settings UI renders + persists them WITHOUT any core edit — keeping the
# drop-in model intact. Values live under plugin_config[<namespace>][<key>].
# A namespace defaults to the plugin name, but a suite of plugins (e.g. the
# printer control/watchdog/autoeject trio) can share ONE namespace.
def get_plugin_config(namespace: str) -> dict:
    """All stored values for a namespace (empty dict if none set yet)."""
    cfg = load_api_keys().get("plugin_config")
    val = cfg.get(namespace) if isinstance(cfg, dict) else None
    return dict(val) if isinstance(val, dict) else {}


def get_plugin_setting(namespace: str, key: str, default=None):
    """A single value from a namespace, or `default` if unset."""
    return get_plugin_config(namespace).get(key, default)


def save_plugin_config(namespace: str, values: dict) -> None:
    """Merge `values` into a namespace's stored config (read-modify-write, like
    every other helper here). Only the provided keys are touched."""
    cfg = load_api_keys().get("plugin_config")
    pc = dict(cfg) if isinstance(cfg, dict) else {}
    cur = pc.get(namespace)
    if not isinstance(cur, dict):
        cur = {}
    cur.update(values)
    pc[namespace] = cur
    _patch_config(plugin_config=pc)


def save_plugin_enabled(plugin_name: str, enabled: bool) -> None:
    cfg = load_api_keys().get("plugins_enabled")
    plugins_cfg = dict(cfg) if isinstance(cfg, dict) else {}
    plugins_cfg[plugin_name] = enabled
    _patch_config(plugins_enabled=plugins_cfg)


def get_sfx_enabled() -> bool:
    """Return whether UI Stark sound effects are enabled (default: True)."""
    return bool(load_api_keys().get("sfx_enabled", True))


def save_sfx_enabled(enabled: bool) -> None:
    """Persist UI Stark sound effects setting."""
    _patch_config(sfx_enabled=bool(enabled))


def get_tts_engine() -> str:
    """Return current TTS engine ('gemini_live', 'edgetts', 'kokoro').
    Piper removed per user request — stored piper* auto-migrates to Edge."""
    eng = (load_api_keys().get("tts_engine", "gemini_live") or "gemini_live").lower()
    if eng in ("piper_hindi", "piper", "piper_hi"):
        return "edgetts"
    return eng


def save_tts_engine(engine_name: str) -> None:
    """Persist chosen TTS engine."""
    _patch_config(tts_engine=(engine_name or "gemini_live").strip().lower())


def get_avatar_mode() -> str:
    """Return chosen avatar mode ('celestial', 'reactor', 'orb', 'matrix', 'nova'). Default: 'reactor'."""
    mode = (load_api_keys().get("avatar_mode", "reactor") or "reactor").lower().strip()
    return mode if mode in ("celestial", "reactor", "orb", "matrix", "nova") else "reactor"


def save_avatar_mode(mode: str) -> None:
    """Persist chosen avatar mode."""
    _patch_config(avatar_mode=(mode or "reactor").strip().lower())


def get_particle_density() -> int:
    """Return configured particle count (default: 200, range: 50-350)."""
    try:
        val = int(load_api_keys().get("particle_density", 200))
        return max(50, min(350, val))
    except (ValueError, TypeError):
        return 200


def save_particle_density(count: int) -> None:
    """Persist configured particle density."""
    _patch_config(particle_density=max(50, min(350, int(count))))


def get_hud_fx() -> dict:
    """Return HUD visual effect toggles."""
    default_fx = {
        "scanlines": False,
        "shockwaves": True,
        "starfield": True,
        "particles": True,
        "photons": True,
        "spectrum": True,
        "brackets": True,
        "meteors": True,     # ambient shooting-star streaks (voice-boosted)
        "trails": True,      # comet trails behind orbiting photons
    }
    cfg = load_api_keys().get("hud_fx")
    if isinstance(cfg, dict):
        default_fx.update(cfg)
    return default_fx


def save_hud_fx(fx: dict) -> None:
    """Persist HUD visual effect toggles."""
    cur = get_hud_fx()
    cur.update(fx)
    _patch_config(hud_fx=cur)


def get_anim_mode() -> str:
    """Return animation dynamics mode ('reactive', 'subtle', 'kinetic'). Default: 'reactive'."""
    val = (load_api_keys().get("anim_mode", "reactive") or "reactive").lower().strip()
    return val if val in ("reactive", "subtle", "kinetic") else "reactive"


def save_anim_mode(mode: str) -> None:
    """Persist animation dynamics mode."""
    _patch_config(anim_mode=(mode or "reactive").strip().lower())


def get_hud_glow() -> int:
    """Return HUD glow / bloom intensity (default: 60, range: 10-100)."""
    try:
        val = int(load_api_keys().get("hud_glow", 60))
        return max(10, min(100, val))
    except (ValueError, TypeError):
        return 60


def save_hud_glow(intensity: int) -> None:
    """Persist HUD glow intensity."""
    _patch_config(hud_glow=max(10, min(100, int(intensity))))


def get_persona_mode() -> str:
    """Return active persona mode ('jarvis', 'teacher', 'companion', 'devops'). Default: 'jarvis'."""
    val = (load_api_keys().get("persona_mode", "jarvis") or "jarvis").lower().strip()
    return val if val in ("jarvis", "teacher", "companion", "devops") else "jarvis"


def save_persona_mode(mode: str) -> None:
    """Persist active persona mode."""
    _patch_config(persona_mode=(mode or "jarvis").strip().lower())


def get_assistant_gender() -> str:
    """Return assistant grammatical/voice gender ('male', 'female'). Default: 'male'."""
    val = (load_api_keys().get("assistant_gender", "") or "").lower().strip()
    if val in ("male", "female"):
        return val
    # If companion persona, default to female, otherwise male
    return "female" if get_persona_mode() == "companion" else "male"


def save_assistant_gender(gender: str) -> None:
    """Persist assistant gender ('male', 'female')."""
    _patch_config(assistant_gender=(gender or "male").strip().lower())


def get_edge_voice() -> str:
    """Return selected Edge-TTS neural voice."""
    cfg_voice = load_api_keys().get("edge_voice", "")
    if cfg_voice:
        return cfg_voice.strip()
    # Default based on gender
    return "hi-IN-SwaraNeural" if get_assistant_gender() == "female" else "hi-IN-MadhurNeural"


def save_edge_voice(voice: str) -> None:
    """Persist Edge-TTS neural voice."""
    _patch_config(edge_voice=(voice or "").strip())


def get_edge_pitch() -> str:
    """Return configured voice pitch (e.g. '+0Hz', '+5Hz', '-5Hz'). Default is '+0Hz' for natural human tone."""
    cfg_pitch = (load_api_keys().get("edge_pitch") or "").strip()
    if cfg_pitch:
        return cfg_pitch
    return "+0Hz"


def save_edge_pitch(pitch: str) -> None:
    """Persist voice pitch."""
    _patch_config(edge_pitch=(pitch or "+0Hz").strip())


def get_edge_rate() -> str:
    """Return speech rate (e.g. '+0%', '+10%', '-5%'). Default: '+0%'."""
    val = (load_api_keys().get("edge_rate") or "+0%").strip()
    return val if val else "+0%"


def save_edge_rate(rate: str) -> None:
    """Persist speech rate."""
    _patch_config(edge_rate=(rate or "+0%").strip())


def get_preferred_language() -> str:
    """Return preferred conversation language ('hinglish', 'hindi', 'english', 'auto'). Default: 'hinglish'."""
    val = (load_api_keys().get("preferred_language") or "hinglish").lower().strip()
    return val if val in ("hinglish", "hindi", "english", "auto") else "hinglish"


def save_preferred_language(lang: str) -> None:
    """Persist preferred conversation language."""
    _patch_config(preferred_language=(lang or "hinglish").strip().lower())


def _auto_detect_obsidian_settings() -> dict | None:
    """Auto-detect Obsidian vault and Local REST API key from local system."""
    appdata = os.environ.get("APPDATA", "")
    obs_json = Path(appdata) / "obsidian" / "obsidian.json" if appdata else None
    vault_candidates = []
    if obs_json and obs_json.exists():
        try:
            vdata = json.loads(obs_json.read_text(encoding="utf-8"))
            for v_info in vdata.get("vaults", {}).values():
                vpath = v_info.get("path")
                if vpath and Path(vpath).exists():
                    vault_candidates.append(Path(vpath))
        except Exception:
            pass

    for fallback in [Path(r"E:\obsidian"), Path(r"E:\obsidian\vaults")]:
        if fallback.exists() and fallback not in vault_candidates:
            vault_candidates.append(fallback)

    for v in vault_candidates:
        plugin_data = v / ".obsidian" / "plugins" / "obsidian-local-rest-api" / "data.json"
        if plugin_data.exists():
            try:
                p_cfg = json.loads(plugin_data.read_text(encoding="utf-8"))
                api_key = p_cfg.get("apiKey", "")
                if api_key:
                    use_insecure = p_cfg.get("enableInsecureServer", False)
                    port = p_cfg.get("insecurePort", 27123) if use_insecure else p_cfg.get("port", 27124)
                    return {
                        "api_key": api_key,
                        "port": port,
                        "vault_path": str(v),
                        "use_https": not use_insecure,
                        "enabled": True,
                    }
            except Exception:
                pass
    return None


def get_obsidian_config() -> dict:
    """Return Obsidian Local REST API and local vault configuration."""
    default_cfg = {
        "enabled": True,
        "api_key": "",
        "port": 27123,
        "vault_path": "",
        "use_https": False,
    }
    cur = load_api_keys().get("obsidian_config")
    if isinstance(cur, dict):
        default_cfg.update(cur)

    # Auto-detect from local Obsidian installation if api_key or vault_path is empty
    if not default_cfg.get("api_key") or not default_cfg.get("vault_path"):
        detected = _auto_detect_obsidian_settings()
        if detected:
            default_cfg.update(detected)
            _patch_config(obsidian_config=default_cfg)

    return default_cfg


def save_obsidian_config(cfg: dict) -> None:
    """Persist Obsidian configuration."""
    cur = get_obsidian_config()
    cur.update(cfg)
    _patch_config(obsidian_config=cur)


def get_all_selected_models() -> dict[str, str]:
    """Return dictionary of selected models mapped per provider."""
    raw = load_api_keys().get("selected_models", {})
    return dict(raw) if isinstance(raw, dict) else {}


def get_selected_model(provider: str) -> str:
    """Return configured model for a specific provider, or empty string."""
    models = get_all_selected_models()
    return models.get(provider.lower().strip(), "")


def save_selected_model(provider: str, model: str) -> None:
    """Save chosen model for a specific provider."""
    models = get_all_selected_models()
    models[provider.lower().strip()] = model.strip()
    _patch_config(selected_models=models, custom_llm_model=model.strip())


def get_edge_reflex_enabled() -> bool:
    """Return whether Tier 1 Needle 2 Edge Reflex is enabled (default True)."""
    return bool(load_api_keys().get("enable_edge_reflex", True))


def save_edge_reflex_enabled(enabled: bool) -> None:
    """Persist Edge Reflex toggle state."""
    _patch_config(enable_edge_reflex=bool(enabled))


def get_proxy_version() -> int:
    """Free-proxy implementation selector: 1 = v1 (default, battle-tested),
    2 = v2 (metrics + rate-limit canary). Unknown values collapse to 1."""
    try:
        v = int(load_api_keys().get("proxy_version", 1) or 1)
        return v if v in (1, 2) else 1
    except Exception:
        return 1


def save_proxy_version(version: int) -> None:
    """Persist free-proxy implementation selector (1 or 2)."""
    try:
        v = int(version or 1)
    except Exception:
        v = 1
    _patch_config(proxy_version=2 if v == 2 else 1)


def get_onboarded() -> bool:
    """ADDITIVE: first-run onboarding shown? Default False (purani installs par ek baar dikhega)."""
    return bool(load_api_keys().get("onboarded", False))


def save_onboarded(done: bool = True) -> None:
    """ADDITIVE: onboarding flag persist."""
    _patch_config(onboarded=bool(done))


# ── API-key encryption at rest — now machine-bound vault (DPAPI/file key) ────
# Old MACHINE_KEY-env approach never worked (nobody set it) → delegated to
# core.secret_vault. Same function names/signatures — existing callers untouched.
def encrypt_secret(plain: str) -> str:
    """Encrypt to ENC(...) via machine vault. Never raises."""
    try:
        from core.secret_vault import encrypt_value
        return encrypt_value(plain)
    except Exception:
        return plain


def decrypt_secret(stored: str) -> str:
    """Decrypt ENC(...) via machine vault, else passthrough (never raises)."""
    try:
        from core.secret_vault import decrypt_value
        return decrypt_value(stored)
    except Exception:
        return stored


# ── Additive: session persist + plugin hot-reload + semantic cache ───────────
def save_session_state(handle: str) -> None:
    """Gemini Live resumption handle encrypted persist (RAM-only flow untouched)."""
    try:
        _patch_config(session_state={"handle": encrypt_secret(handle or "")})
    except Exception:
        pass


def load_session_state() -> str:
    """Persisted handle or '' (never raises)."""
    try:
        _raw = (load_api_keys().get("session_state", {}) or {}).get("handle", "")
        return decrypt_secret(str(_raw or ""))
    except Exception:
        return ""


def watch_plugins_once(callback=None) -> bool:
    """Watchdog optional live-reload probe. watchdog na ho to False, kuch nahi todta."""
    try:
        import importlib.util as _u
        if _u.find_spec("watchdog") is None:
            return False
        if callback:
            try:
                callback()
            except Exception:
                pass
        return True
    except Exception:
        return False


def cache_lookup_semantic(query: str, candidates: list[str]) -> str | None:
    """BM25-based semantic cache probe over in-memory candidate strings.

    Uses the real PureBM25 scorer from actions.bm25_search (the old import
    referenced a bm25_scores symbol that never existed, so this ALWAYS fell
    through to the token-overlap fallback). Threshold 2.0 preserved.
    """
    try:
        q = (query or "").strip().lower()
        if not q or not candidates:
            return None
        from actions.bm25_search import PureBM25, _tokenize as _bm_tok
        corpus = [_bm_tok(str(c)) for c in candidates]
        scores = PureBM25(corpus).get_scores(_bm_tok(q))
        if not scores:
            return None
        best_i = max(range(len(scores)), key=lambda i: scores[i])
        # Threshold 1.0 (not 2.0): BM25 scores scale with corpus size, and
        # candidate lists here are tiny — 2.0 would reject genuine matches
        # like 'reserve table restaurant' ~ 'book restaurant table' (1.39).
        return candidates[best_i] if scores[best_i] > 1.0 else None
    except Exception:
        try:
            # Fallback: token-overlap (bm25 module shape alag ho to bhi kaam kare)
            _qt = set(q.split())
            _best, _bs = None, 0
            for c in candidates:
                _s = len(_qt & set(str(c).lower().split()))
                if _s > _bs:
                    _best, _bs = c, _s
            return _best if _bs >= 3 else None
        except Exception:
            return None
