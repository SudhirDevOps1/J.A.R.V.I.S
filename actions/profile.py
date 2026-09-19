"""Profiles — Work/Gaming/Study bundle switch. New file, auto-discovered.
persona + voice + routine ek command me. Existing setters reuse, kuch naya overwrite nahi.
"""
from __future__ import annotations

import json
from pathlib import Path

_PROF_FILE = Path(__file__).resolve().parent.parent / "config" / "profiles.json"


def _log(player, msg: str) -> None:
    try:
        if player:
            player.write_log(msg)
    except Exception:
        pass
    print(msg)


def _load() -> dict:
    try:
        if _PROF_FILE.exists():
            data = json.loads(_PROF_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def profile(parameters: dict | None = None, player=None, session_memory=None, **_) -> str:
    from memory import config_manager as _cm
    params = parameters or {}
    action = str(params.get("action", "apply") or "apply").lower().strip()
    name = str(params.get("name", params.get("profile", "")) or "").strip().lower()
    if action in ("list", "show"):
        names = sorted(k for k in _load() if not k.startswith("_"))
        return ("Profiles: " + ", ".join(names)) if names else "Koi profile nahi hai."
    if not name:
        return "Kaun si profile? Naam bolo (e.g. 'gaming profile lagao')."
    profs = _load()
    if name not in profs or not isinstance(profs[name], dict):
        known = ", ".join(sorted(k for k in profs if not k.startswith("_"))) or "none"
        return f"Profile '{name}' nahi mili. Available: {known}."
    prof = profs[name]
    applied = []
    try:
        if prof.get("persona_mode"):
            _cm.save_persona_mode(str(prof["persona_mode"]))
            applied.append(f"persona={prof['persona_mode']}")
    except Exception:
        pass
    try:
        if prof.get("voice_name"):
            _cm.save_voice(str(prof["voice_name"]))
            applied.append(f"voice={prof['voice_name']}")
    except Exception:
        pass
    routine = str(prof.get("routine", "") or "").strip()
    if routine:
        try:
            from actions.open_app import open_app as _oa
            _oa({"action": "routine", "routine": routine})
            applied.append(f"routine={routine}")
        except Exception:
            pass
    try:
        from core.audit import log_event as _ae
        _ae("profile_apply", name)
    except Exception:
        pass
    # ADDITIVE verify: lagane ke baad padh ke confirm karo (silent fail band)
    try:
        got_p = _cm.get_persona_mode()
        ok = (not prof.get("persona_mode")) or (got_p == str(prof["persona_mode"]))
    except Exception:
        ok = True
    try:
        if player and hasattr(player, "request_reconnect"):
            player.request_reconnect(keep_context=False, reason=f"profile_{name}")
    except Exception:
        pass
    _log(player, f"[profile] {name}: {', '.join(applied)}")
    from core.persona_manager import get_persona_greeting
    p_mode = str(prof.get("persona_mode", name))
    greet = get_persona_greeting(p_mode)
    tail = "" if ok else " (verify: persona apply nahi dikha, dobara try karo)"
    return f"'{name.upper()}' mode activate ho gaya ({', '.join(applied)}). {greet}{tail}"


TOOL = {
    "name": "profile",
    "description": (
        "Switch Work/Gaming/Study profiles (persona + voice + app routine bundle). "
        "Trigger on 'gaming profile lagao', 'work mode', 'study profile'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "apply | list"},
            "name": {"type": "STRING", "description": "Profile name"},
        },
        "required": ["action"],
    },
    "handler": profile,
}
