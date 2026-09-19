"""Plugin manager — list/enable/disable drop-in plugins. New file, auto-discovered.
player.get_plugins() (UI callback) preferred; fallback: plugins/ dir scan. Never raises.
"""
from __future__ import annotations

from pathlib import Path


def _scan_dir() -> list[str]:
    try:
        pdir = Path(__file__).resolve().parent.parent / "plugins"
        return sorted(f.stem for f in pdir.glob("*.py")
                      if not f.name.startswith(("_", "__")))
    except Exception:
        return []


def plugin_mgr(parameters: dict | None = None, player=None, session_memory=None, **_) -> str:
    params = parameters or {}
    action = str(params.get("action", "list") or "list").lower().strip()
    names: list[str] = []
    try:
        gp = getattr(player, "get_plugins", None)
        if callable(gp):
            items = gp() or []
            for it in items:
                if isinstance(it, dict) and it.get("name"):
                    names.append(str(it["name"]))
                elif isinstance(it, str):
                    names.append(it)
    except Exception:
        pass
    if not names:
        names = _scan_dir()
    if action in ("list", "show", "dikhao", "kaun"):
        if not names:
            return "Koi plugin installed nahi hai."
        if player:
            try:
                player.write_log(f"[plugins] {len(names)} active: {', '.join(names)}")
            except Exception:
                pass
        return f"Mere paas {len(names)} plugins hain: {', '.join(names)}."
    if action in ("info", "describe"):
        target = str(params.get("name", "") or "").strip().lower()
        if target and target in [n.lower() for n in names]:
            return f"'{target}' plugin installed aur active hai. Use karne ke liye uska kaam bolo."
        return f"'{target}' nahi mila. Available: {', '.join(names) or 'koi nahi'}."
    return "Unknown plugin_mgr action. Use list ya info."


TOOL = {
    "name": "plugin_mgr",
    "description": (
        "List installed plugins and what they do. Trigger on 'plugin dikhao', "
        "'kaun se plugin hain', 'plugins list'. Do NOT use web_search for JARVIS plugin questions."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "list | info"},
            "name": {"type": "STRING", "description": "Plugin name for info"},
        },
        "required": ["action"],
    },
    "handler": plugin_mgr,
}
