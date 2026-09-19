"""Clock — time/date/day, zero-token local answer. New file, auto-discovered.
"time batao" web_search me jaata tha (galat). Ab seedha jawab, koi network nahi.
"""
from __future__ import annotations

from datetime import datetime


def clock(parameters: dict | None = None, player=None, session_memory=None, **_) -> str:
    params = parameters or {}
    action = str(params.get("action", "time") or "time").lower().strip()
    now = datetime.now()
    if player:
        try:
            player.write_log(f"[clock] {now.strftime('%I:%M %p, %d %b %Y')}")
        except Exception:
            pass
    if action in ("date", "tarikh", "today"):
        return f"Aaj {now.strftime('%A, %d %B %Y')} hai."
    if action in ("day", "din", "weekday"):
        return f"Aaj {now.strftime('%A')} hai."
    return f"Abhi time {now.strftime('%I:%M %p')} hai ({now.strftime('%d %B %Y')})."


TOOL = {
    "name": "clock",
    "description": (
        "Tell current time, date, or day locally with zero tokens. Trigger on "
        "'time batao', 'kitne baje', 'aaj kya date', 'kaun sa din'. "
        "Do NOT use web_search for time/date — use this instead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "time | date | day"},
        },
        "required": ["action"],
    },
    "handler": clock,
}
