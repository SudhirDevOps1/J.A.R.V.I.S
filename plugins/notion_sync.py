"""Notion page create/search plugin (additive, needs NOTION_TOKEN, else guided)."""

PLUGIN = {
    "name": "notion_sync",
    "description": (
        "Create or search Notion pages. Trigger on 'notion me note', 'notion search'. "
        "Do NOT use obsidian_brain for Notion — use this instead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "create | search"},
            "title": {"type": "STRING", "description": "Page title or query"},
            "text": {"type": "STRING", "description": "Body for create"},
        },
        "required": ["action", "title"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    import os as _os
    action = str((parameters or {}).get("action", "search")).lower().strip()
    title = str((parameters or {}).get("title", "") or "").strip()
    text = str((parameters or {}).get("text", "") or "").strip()
    if not title:
        return "Please specify a Notion title or query."
    token = (_os.environ.get("NOTION_TOKEN", "") or "").strip()
    if not token:
        try:
            import json as _j, sys as _s
            from pathlib import Path as _P
            base = _P(_s.executable).parent if getattr(_s, "frozen", False) else _P(__file__).resolve().parent.parent
            cfg = _j.loads((base / "config" / "api_keys.json").read_text(encoding="utf-8"))
            token = str(cfg.get("notion_token", "") or "").strip()
            try:  # ADDITIVE: ENC blob support (plaintext passthrough)
                from core.secret_vault import decrypt_value
                token = str(decrypt_value(token) or "").strip()
            except Exception:
                pass
        except Exception:
            token = ""
    if not token:
        return "Notion token missing — set NOTION_TOKEN env or notion_token in config, then retry."
    try:
        import urllib.request as _ur, json as _j
        if action == "search":
            req = _ur.Request("https://api.notion.com/v1/search",
                              data=_j.dumps({"query": title, "page_size": 3}).encode(),
                              headers={"Authorization": f"Bearer {token}",
                                       "Notion-Version": "2022-06-28",
                                       "Content-Type": "application/json"})
            with _ur.urlopen(req, timeout=15) as r:
                data = _j.loads(r.read().decode("utf-8", "replace"))
            n = len(data.get("results", []))
            return f"Notion search '{title}': {n} result(s)."
        # create needs a parent page id; keep guided without deleting anything
        return "Notion create needs a parent page — set NOTION_PARENT_ID, then retry."
    except Exception as e:
        return f"Sir, Notion sync failed: {e}"
