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
    # ADDITIVE: control over what gets written into the permanent journal.
    # Screen shielding above protects the display; this protects the disk.
    elif action in ("enable_redaction", "redaction_on", "redact_on"):
        res = _set_redaction(True)
    elif action in ("disable_redaction", "redaction_off", "redact_off"):
        res = _set_redaction(False)
    elif action in ("toggle_redaction", "redact"):
        res = _set_redaction(not _redaction_enabled())
    elif action in ("scan_text", "check_pii", "pii_scan"):
        res = _scan_text(params.get("text") or "")
    else:  # "status"
        res = get_privacy_status_summary()

    if player:
        player.write_log(f"PRIVACY: {res}")
    if speak_fn and callable(speak_fn):
        speak_fn(res)

    return res


# ── redaction helpers ───────────────────────────────────────────────────────

def _redaction_enabled() -> bool:
    from core.pii_redactor import is_enabled
    return bool(is_enabled())


def _set_redaction(enabled: bool) -> str:
    """Toggle journal redaction and persist it to config/privacy_settings.json."""
    from core.privacy_guard import load_privacy_settings, save_privacy_settings
    settings = load_privacy_settings()
    settings["redact_pii_in_memory"] = bool(enabled)
    save_privacy_settings(settings)
    if enabled:
        return ("✅ Journal redaction ON. API keys, tokens, emails, card numbers, "
                "Aadhaar and PAN are stripped before anything is written to "
                "memory/journals/.")
    return ("⚠️ Journal redaction OFF. Anything you say is written to "
            "memory/journals/ exactly as spoken, including credentials. "
            "Turn it back on with 'redaction on'.")


def _scan_text(text: str) -> str:
    """Show the user what redaction would do, without storing anything.

    Exists because 'trust me' is not a security property. The user can point
    the tool at their own sentence and see the result before trusting it with
    their memory.
    """
    text = str(text or "").strip()
    if not text:
        return "Text empty hai — kuch check karne ke liye text do."
    from core.pii_redactor import redact, scan
    findings = scan(text)
    if not findings:
        return f"✅ Kuch sensitive nahi mila. Text as-is rehne dega:\n  {text}"
    out = redact(text)
    lines = [f"🔎 {len(findings)} sensitive cheezein mili:", ""]
    seen = []
    for f in findings:
        if f.kind in seen:
            continue
        seen.append(f.kind)
        lines.append(f"  • {f.kind}: {f.sample}")
    lines.append("")
    lines.append("Redacted version:")
    lines.append(f"  {out}")
    lines.append("")
    lines.append(f"Journal me yehi likha jayega. (redaction "
                 f"{'ON' if _redaction_enabled() else 'OFF'})")
    return "\n".join(lines)


TOOL = {
    "name": "privacy_ctl",
    "description": "Zero-Trust Privacy Shield and Web/WebSocket screen stream controller. Use to toggle master privacy mode, authorize or stop live screen streams, check sensitive window protection status, and control what is stripped before a conversation is written to permanent memory.",
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
                    "toggle_privacy",
                    "enable_redaction",
                    "disable_redaction",
                    "toggle_redaction",
                    "scan_text"
                ],
                "description": (
                    "Privacy command to execute: 'enable_privacy_mode', "
                    "'disable_privacy_mode', 'allow_stream', 'stop_stream', "
                    "'status', 'check_window', 'toggle_stream', 'toggle_privacy'. "
                    "Journal redaction (strips API keys, tokens, emails, card "
                    "numbers, Aadhaar and PAN before writing to memory): "
                    "'enable_redaction', 'disable_redaction', "
                    "'toggle_redaction'. 'scan_text' shows what redaction would "
                    "do to the given text without storing anything."
                )
            },
            "text": {
                "type": "STRING",
                "description": "Only for action='scan_text'. The sentence to inspect."
            }
        },
        "required": ["action"]
    },
    "handler": privacy_ctl,
}
