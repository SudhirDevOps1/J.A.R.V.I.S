"""Text expander — hotstrings like ;mail ;addr ;sign. New file, auto-discovered.
keyboard lib optional: missing par clean Hindi error, kuch nahi todta.
Expansions config/expansions.json me (default 3 seeded on first enable, user edit kar sakta hai).
"""
from __future__ import annotations

import json
from pathlib import Path

_EXP_FILE = Path(__file__).resolve().parent.parent / "config" / "expansions.json"
_DEFAULTS = {
    ";mail": "sudhir@example.com",
    ";addr": "India",
    ";sign": "Thanks,\nSudhir",
}
_HOOKS: dict = {}
_ENABLED = False


def _log(player, msg: str) -> None:
    try:
        if player:
            player.write_log(msg)
    except Exception:
        pass
    print(msg)


def _load() -> dict:
    try:
        if _EXP_FILE.exists():
            data = json.loads(_EXP_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data:
                return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return dict(_DEFAULTS)


def _save(exp: dict) -> None:
    try:
        _EXP_FILE.parent.mkdir(parents=True, exist_ok=True)
        _tmp = _EXP_FILE.with_suffix(".json.tmp")
        _tmp.write_text(json.dumps(exp, indent=2, ensure_ascii=False), encoding="utf-8")
        import os as _os
        _os.replace(str(_tmp), str(_EXP_FILE))
    except Exception:
        pass


def _enable(player=None) -> str:
    global _ENABLED
    try:
        import keyboard as _kb
    except Exception:
        return "Text expander ke liye keyboard lib install karo: pip install keyboard (admin/root chahiye hook ke liye)."
    exp = _load()
    if not _EXP_FILE.exists():
        _save(exp)
    try:
        for trig, full in exp.items():
            if trig in _HOOKS:
                continue
            _HOOKS[trig] = _kb.add_abbreviation(trig, full)
        _ENABLED = True
        _log(player, f"[expander] {len(_HOOKS)} hotstrings active")
        return f"{len(_HOOKS)} hotstrings on hain (;mail, ;addr, ;sign...). Band ke liye 'expander off' bolo."
    except Exception as e:
        return f"Expander on failed (admin chahiye ho sakta hai): {e}"


def _disable(player=None) -> str:
    global _ENABLED
    try:
        import keyboard as _kb
        for trig, hook in list(_HOOKS.items()):
            try:
                _kb.remove_abbreviation(hook) if hasattr(_kb, "remove_abbreviation") else None
            except Exception:
                try:
                    _kb.unhook(hook)
                except Exception:
                    pass
        _HOOKS.clear()
        _ENABLED = False
        return "Text expander off kar diya."
    except Exception as e:
        return f"Expander off failed: {e}"


def text_expander(parameters: dict | None = None, player=None, session_memory=None, **_) -> str:
    params = parameters or {}
    action = str(params.get("action", "on") or "on").lower().strip()
    if action in ("off", "disable", "stop", "band"):
        return _disable(player)
    if action in ("list", "show"):
        exp = _load()
        lines = [f"{k} -> {v[:40]}" for k, v in list(exp.items())[:15]]
        return "Hotstrings:\n" + ("\n".join(lines) if lines else "khali hai.")
    if action in ("add", "set", "save"):
        trig = str(params.get("trigger", "") or "").strip()
        val = str(params.get("value", "") or "").strip()
        if not trig or not val:
            return "trigger aur value dono do (e.g. trigger=';phone', value='98...')."
        exp = _load()
        exp[trig] = val
        _save(exp)
        return f"Hotstring '{trig}' save ho gaya."
    return _enable(player)


TOOL = {
    "name": "text_expander",
    "description": (
        "Text expander hotstrings (;mail, ;addr, ;sign type karte hi pura text). "
        "Trigger on 'expander on karo', 'hotstring jodo', 'expander list'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "on | off | list | add"},
            "trigger": {"type": "STRING", "description": "Hotstring for add (e.g. ;phone)"},
            "value": {"type": "STRING", "description": "Full text for add"},
        },
        "required": ["action"],
    },
    "handler": text_expander,
}
