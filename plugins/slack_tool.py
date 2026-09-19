"""Slack plugin (additive). SLACK_BOT_TOKEN env/config, else guided. No GUI spoof."""

PLUGIN = {
    "name": "slack_tool",
    "description": (
        "Send Slack messages via voice. Trigger on 'slack pe bhejo', 'slack message'. "
        "Do NOT use web_search for Slack — use this instead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "channel": {"type": "STRING", "description": "Channel ID or #name"},
            "text": {"type": "STRING", "description": "Message text"},
        },
        "required": ["channel", "text"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    import os as _os
    channel = str((parameters or {}).get("channel", "") or "").strip()
    text = str((parameters or {}).get("text", "") or "").strip()
    if not channel or not text:
        return "Channel aur text dono do."
    tok = (_os.environ.get("SLACK_BOT_TOKEN", "") or "").strip()
    if not tok:
        try:
            import json as _j, sys as _s
            from pathlib import Path as _P
            base = _P(_s.executable).parent if getattr(_s, "frozen", False) else _P(__file__).resolve().parent.parent
            cfg = _j.loads((base / "config" / "api_keys.json").read_text(encoding="utf-8"))
            tok = str(cfg.get("slack_bot_token", "") or "").strip()
            try:  # ADDITIVE: ENC blob support (plaintext passthrough)
                from core.secret_vault import decrypt_value
                tok = str(decrypt_value(tok) or "").strip()
            except Exception:
                pass
        except Exception:
            tok = ""
    if not tok:
        return "Slack token missing — SLACK_BOT_TOKEN env ya slack_bot_token config me rakho."
    try:
        import urllib.request as _ur, json as _j
        req = _ur.Request("https://slack.com/api/chat.postMessage",
                          data=_j.dumps({"channel": channel, "text": text}).encode(),
                          headers={"Authorization": f"Bearer {tok}",
                                   "Content-Type": "application/json"})
        with _ur.urlopen(req, timeout=15) as r:
            d = _j.loads(r.read().decode("utf-8", "replace"))
        if d.get("ok"):
            return f"Slack {channel} me bhej diya."
        return f"Slack send failed: {d.get('error', 'unknown')}."
    except Exception as e:
        return f"Sir, Slack send failed: {e}"
