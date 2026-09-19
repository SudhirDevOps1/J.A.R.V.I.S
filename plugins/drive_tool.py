"""Google Drive plugin (additive). OAuth token guided, else clean message."""

PLUGIN = {
    "name": "drive_tool",
    "description": (
        "Search Google Drive files by voice. Trigger on 'drive me dhoondo', "
        "'drive file'. Do NOT use web_search for Drive."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "search | list"},
            "query": {"type": "STRING", "description": "File name query"},
        },
        "required": ["action"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    import os as _os
    action = str((parameters or {}).get("action", "search")).lower().strip()
    query = str((parameters or {}).get("query", "") or "").strip()
    cred_path = _os.path.expanduser("~/.credentials/drive_token.json")
    if not _os.path.exists(cred_path):
        return ("Drive connect nahi hai — Google Cloud OAuth token "
                "~/.credentials/drive_token.json me rakho.")
    try:
        from googleapiclient.discovery import build as _build
        from google.oauth2.credentials import Credentials as _Creds
        svc = _build("drive", "v3", credentials=_Creds.from_authorized_user_file(cred_path))
        if action == "list":
            res = svc.files().list(pageSize=10, fields="files(name, modifiedTime)").execute()
        else:
            if not query:
                return "Kya dhoondu? Naam bolo."
            res = svc.files().list(q=f"name contains '{query}'", pageSize=10,
                                   fields="files(name, modifiedTime)").execute()
        items = res.get("files", [])
        if not items:
            return "Drive me kuch nahi mila."
        lines = [f"{i.get('name', '?')}" for i in items[:10]]
        out = "Drive results:\n" + "\n".join(f"{i+1}. {l}" for i, l in enumerate(lines))
        if player:
            try:
                player.write_log(f"JARVIS: {out[:300]}")
            except Exception:
                pass
        return out
    except Exception as e:
        return f"Sir, Drive search failed: {e}"
