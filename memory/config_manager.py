import json
import os
import sys
from pathlib import Path

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR    = get_base_dir()
CONFIG_DIR  = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "api_keys.json"

def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def config_exists() -> bool:
    return CONFIG_FILE.exists()

def save_api_keys(gemini_api_key: str) -> None:
    ensure_config_dir()

    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    data["gemini_api_key"] = gemini_api_key.strip()

    CONFIG_FILE.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8"
    )

def load_api_keys() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ Failed to load api_keys.json: {e}")
        return {}

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
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["assistant_name"] = assistant_name.strip() or "JARVIS"
    data["user_name"] = user_name.strip()
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")


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
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    v = (voice_name or "").strip()
    data["voice_name"] = v if v in AVAILABLE_VOICES else DEFAULT_VOICE
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")


def get_wake_word_enabled() -> bool:
    """Whether local wake-word gating is on (assistant sleeps until 'Hey Jarvis')."""
    return load_api_keys().get("wake_word_enabled", False)


def save_wake_word_enabled(enabled: bool) -> None:
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["wake_word_enabled"] = bool(enabled)
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")


def get_brief_enabled() -> bool:
    return load_api_keys().get("morning_brief_enabled", True)


def save_brief_enabled(enabled: bool) -> None:
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["morning_brief_enabled"] = enabled
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")


# ── Audio devices ────────────────────────────────────────────────────────────
# Stored as device NAMES, not sounddevice indices. Indices shift every time a
# USB device is plugged in or removed, so a saved index silently starts pointing
# at a different microphone. The empty string means "system default", which is
# both the factory setting and what an unresolvable saved device falls back to —
# so unplugging a headset degrades to the built-in speakers instead of crashing.

def _patch_config(**fields) -> None:
    """Read-modify-write one or more keys in api_keys.json.

    Every setter in this file open-coded this. Collapsing it here means a new
    setting is one line, and there is one place where a corrupt config file is
    handled instead of nine."""
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data.update(fields)
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
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    pc = data.get("plugin_config")
    if not isinstance(pc, dict):
        pc = {}
    cur = pc.get(namespace)
    if not isinstance(cur, dict):
        cur = {}
    cur.update(values)
    pc[namespace] = cur
    data["plugin_config"] = pc
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")


def save_plugin_enabled(plugin_name: str, enabled: bool) -> None:
    ensure_config_dir()
    data: dict = {}
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    plugins_cfg = data.get("plugins_enabled")
    if not isinstance(plugins_cfg, dict):
        plugins_cfg = {}
    plugins_cfg[plugin_name] = enabled
    data["plugins_enabled"] = plugins_cfg
    CONFIG_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")


def get_sfx_enabled() -> bool:
    """Return whether UI Stark sound effects are enabled (default: True)."""
    return bool(load_api_keys().get("sfx_enabled", True))


def save_sfx_enabled(enabled: bool) -> None:
    """Persist UI Stark sound effects setting."""
    _patch_config(sfx_enabled=bool(enabled))


def get_tts_engine() -> str:
    """Return current TTS engine ('gemini_live', 'piper_hindi', 'edgetts', 'kokoro')."""
    return (load_api_keys().get("tts_engine", "gemini_live") or "gemini_live").lower()


def save_tts_engine(engine_name: str) -> None:
    """Persist chosen TTS engine."""
    _patch_config(tts_engine=(engine_name or "gemini_live").strip().lower())


def get_avatar_mode() -> str:
    """Return chosen avatar mode ('celestial', 'reactor', 'orb', 'matrix'). Default: 'celestial'."""
    mode = (load_api_keys().get("avatar_mode", "celestial") or "celestial").lower().strip()
    return mode if mode in ("celestial", "reactor", "orb", "matrix") else "celestial"


def save_avatar_mode(mode: str) -> None:
    """Persist chosen avatar mode."""
    _patch_config(avatar_mode=(mode or "celestial").strip().lower())


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