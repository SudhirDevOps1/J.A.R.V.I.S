"""Google Calendar plugin (additive). Morning Briefing me events integrate karega."""

PLUGIN = {
    "name": "calendar_tool",
    "description": (
        "Read today's Google Calendar events for Morning Briefing. Trigger on "
        "'aaj ke events', 'schedule batao', 'meeting kab hai'. Do NOT use web_search for calendar."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "day": {"type": "STRING", "description": "today | tomorrow, default today"},
        },
        "required": [],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    import os as _os
    day = str((parameters or {}).get("day", "today")).lower().strip()
    cred_path = _os.path.expanduser("~/.credentials/calendar_token.json")
    if not _os.path.exists(cred_path):
        return ("Calendar connect nahi hai — Google Cloud OAuth token "
                "~/.credentials/calendar_token.json me rakho.")
    try:
        from googleapiclient.discovery import build as _build
        from google.oauth2.credentials import Credentials as _Creds
        from datetime import datetime as _dt, timedelta as _td
        creds = _Creds.from_authorized_user_file(cred_path)
        svc = _build("calendar", "v3", credentials=creds)
        base = _dt.now() + (_td(days=1) if day == "tomorrow" else _td(0))
        start = base.replace(hour=0, minute=0, second=0).isoformat() + "Z"
        end = base.replace(hour=23, minute=59, second=59).isoformat() + "Z"
        evs = svc.events().list(calendarId="primary", timeMin=start, timeMax=end,
                                maxResults=10, singleEvents=True,
                                orderBy="startTime").execute().get("items", [])
        if not evs:
            return f"{day} ke liye koi event nahi hai."
        lines = []
        for e in evs:
            st = (e.get("start") or {}).get("dateTime", (e.get("start") or {}).get("date", "?"))
            lines.append(f"{st[11:16] if len(st) > 16 else st} — {e.get('summary', '(no title)')}")
        out = f"{day} ke events:\n" + "\n".join(f"{i+1}. {l}" for i, l in enumerate(lines))
        if player:
            try:
                player.write_log(f"JARVIS: {out[:300]}")
            except Exception:
                pass
        return out
    except Exception as e:
        return f"Sir, Calendar read failed: {e}"
