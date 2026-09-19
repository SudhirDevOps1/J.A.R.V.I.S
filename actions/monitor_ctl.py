"""Monitor control — warning mute/unmute/status. New file, auto-discovered.
"warning band karo" -> khamoshi. Purana SystemMonitor untouched.
"""
from __future__ import annotations


def monitor_ctl(parameters: dict | None = None, player=None, session_memory=None, **_) -> str:
    from actions.system_monitor import set_monitor_muted, is_monitor_muted
    params = parameters or {}
    action = str(params.get("action", "status") or "status").lower().strip()
    if action in ("mute", "band", "off", "stop", "quiet"):
        set_monitor_muted(True)
        if player:
            try:
                player.write_log("[monitor] warnings muted")
            except Exception:
                pass
        return "System warnings band kar diye. Wapas ke liye 'warning chalu karo' bolo."
    if action in ("unmute", "chalu", "on", "start"):
        set_monitor_muted(False)
        return "System warnings chalu ho gayi."
    st = "MUTED (band)" if is_monitor_muted() else "ACTIVE (chalu)"
    return f"Monitor status: {st}."


TOOL = {
    "name": "monitor_ctl",
    "description": (
        "Mute/unmute system CPU/RAM warning alerts. Trigger on 'warning band karo', "
        "'alert band karo', 'warning chalu karo', 'monitor status'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "mute | unmute | status"},
        },
        "required": ["action"],
    },
    "handler": monitor_ctl,
}
