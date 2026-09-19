"""Gmail reader plugin (additive). Official Google API when OAuth creds exist, else guided."""

PLUGIN = {
    "name": "gmail_tool",
    "description": (
        "Read unread Gmail emails by voice. Trigger on 'emails padho', 'unread mail'. "
        "Do NOT use web_search for Gmail — use this instead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "unread | search"},
            "query": {"type": "STRING", "description": "Search query for action=search"},
            "count": {"type": "STRING", "description": "Max emails, default 5"},
        },
        "required": ["action"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    import os as _os
    action = str((parameters or {}).get("action", "unread")).lower().strip()
    query = str((parameters or {}).get("query", "") or "").strip()
    try:
        count = max(1, min(10, int(str((parameters or {}).get("count", "5") or "5"))))
    except Exception:
        count = 5
    cred_path = _os.path.expanduser("~/.credentials/gmail_token.json")
    if not _os.path.exists(cred_path):
        return ("Gmail connect nahi hai — Google Cloud se OAuth token banao aur "
                "~/.credentials/gmail_token.json me rakho, phir 'emails padho' bolo.")
    try:
        from googleapiclient.discovery import build as _build
        from google.oauth2.credentials import Credentials as _Creds
        import json as _j
        creds = _Creds.from_authorized_user_file(cred_path)
        svc = _build("gmail", "v1", credentials=creds)
        q = query if action == "search" else "is:unread"
        msgs = svc.users().messages().list(userId="me", q=q, maxResults=count).execute().get("messages", [])
        if not msgs:
            return "Koi email nahi mili."
        lines = []
        for m in msgs:
            try:
                meta = svc.users().messages().get(userId="me", id=m["id"], format="metadata",
                                                  metadataHeaders=["Subject", "From"]).execute()
                hdrs = {h["name"]: h["value"] for h in meta.get("payload", {}).get("headers", [])}
                lines.append(f"{hdrs.get('From', '?')} — {hdrs.get('Subject', '(no subject)')}")
            except Exception:
                continue
        out = f"{len(lines)} emails:\n" + "\n".join(f"{i+1}. {l}" for i, l in enumerate(lines))
        if player:
            try:
                player.write_log(f"JARVIS: {out[:300]}")
            except Exception:
                pass
        return out
    except Exception as e:
        return f"Sir, Gmail read failed: {e}"
