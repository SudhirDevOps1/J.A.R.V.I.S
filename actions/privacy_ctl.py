"""
actions/privacy_ctl.py — Zero-Trust Privacy Shield & Screen Stream Controller for J.A.R.V.I.S.

Allows voice, chat, and automated agents to toggle master privacy mode,
authorize/stop screen streaming, and inspect real-time sensitive window security.
"""
from __future__ import annotations

from typing import Any, Dict


def privacy_ctl(params: Dict[str, Any], player=None, speak_fn=None) -> str:
    """
    Handle privacy mode toggles, stream authorization, and security status queries.
    """
    from core.privacy_guard import (
        set_privacy_mode,
        set_stream_allowed,
        get_privacy_status_summary,
        detect_sensitive_window,
        is_privacy_mode_active,
        is_stream_allowed,
    )

    action = (params.get("action") or "status").lower().strip()

    if action in ("enable_privacy_mode", "privacy_on", "shield_on"):
        res = set_privacy_mode(True)
    elif action in ("disable_privacy_mode", "privacy_off", "shield_off"):
        res = set_privacy_mode(False)
    elif action in ("allow_stream", "stream_on", "start_stream"):
        res = set_stream_allowed(True)
    elif action in ("stop_stream", "stream_off", "deny_stream"):
        res = set_stream_allowed(False)
    elif action in ("toggle_stream",):
        res = set_stream_allowed(not is_stream_allowed())
    elif action in ("toggle_privacy",):
        res = set_privacy_mode(not is_privacy_mode_active())
    elif action in ("check_window", "detect_sensitive"):
        is_sens, desc = detect_sensitive_window()
        if is_sens:
            res = f"⚠️ Sensitive window detected: {desc}. Screen stream and vision captures are currently masked."
        else:
            res = "✅ No sensitive window detected. Screen environment is safe."
    else:  # "status"
        res = get_privacy_status_summary()

    if player:
        player.write_log(f"PRIVACY: {res}")
    if speak_fn and callable(speak_fn):
        speak_fn(res)

    return res


TOOL = {
    "name": "privacy_ctl",
    "description": "Zero-Trust Privacy Shield and Web/WebSocket screen stream controller. Use to toggle master privacy mode, authorize or stop live screen streams, and check sensitive window protection status.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": [
                    "enable_privacy_mode",
                    "disable_privacy_mode",
                    "allow_stream",
                    "stop_stream",
                    "status",
                    "check_window",
                    "toggle_stream",
                    "toggle_privacy"
                ],
                "description": "Privacy command to execute: 'enable_privacy_mode', 'disable_privacy_mode', 'allow_stream', 'stop_stream', 'status', 'check_window'."
            }
        },
        "required": ["action"]
    },
    "handler": privacy_ctl,
}
