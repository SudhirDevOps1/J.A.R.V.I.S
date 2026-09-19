"""GitHub plugin (additive). GITHUB_TOKEN env/config, else guided. No GUI spoof."""

PLUGIN = {
    "name": "github_tool",
    "description": (
        "GitHub issues/PRs via voice: list issues, create issue. Trigger on "
        "'github issues dikhao', 'naya issue banao'. Do NOT use web_search for GitHub."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "list_issues | create_issue"},
            "repo": {"type": "STRING", "description": "owner/repo, e.g. SudhirDevOps1/J.A.R.V.I.S"},
            "title": {"type": "STRING", "description": "Issue title for create_issue"},
            "body": {"type": "STRING", "description": "Issue body for create_issue"},
        },
        "required": ["action", "repo"],
    },
}


def _token() -> str:
    import os as _os
    tok = (_os.environ.get("GITHUB_TOKEN", "") or "").strip()
    if not tok:
        try:
            import json as _j, sys as _s
            from pathlib import Path as _P
            base = _P(_s.executable).parent if getattr(_s, "frozen", False) else _P(__file__).resolve().parent.parent
            cfg = _j.loads((base / "config" / "api_keys.json").read_text(encoding="utf-8"))
            tok = str(cfg.get("github_token", "") or "").strip()
            try:  # ADDITIVE: ENC blob support (plaintext passthrough)
                from core.secret_vault import decrypt_value
                tok = str(decrypt_value(tok) or "").strip()
            except Exception:
                pass
        except Exception:
            tok = ""
    return tok


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str((parameters or {}).get("action", "list_issues")).lower().strip()
    repo = str((parameters or {}).get("repo", "") or "").strip()
    if not repo or "/" not in repo:
        return "Repo owner/repo format me do (e.g. SudhirDevOps1/J.A.R.V.I.S)."
    tok = _token()
    if not tok:
        return "GitHub token missing — GITHUB_TOKEN env ya github_token config me rakho."
    try:
        import urllib.request as _ur, json as _j
        if action == "create_issue":
            title = str((parameters or {}).get("title", "") or "").strip() or "JARVIS issue"
            body = str((parameters or {}).get("body", "") or "").strip()
            req = _ur.Request(f"https://api.github.com/repos/{repo}/issues",
                              data=_j.dumps({"title": title, "body": body}).encode(),
                              headers={"Authorization": f"Bearer {tok}",
                                       "Accept": "application/vnd.github+json"})
            with _ur.urlopen(req, timeout=15) as r:
                d = _j.loads(r.read().decode("utf-8", "replace"))
            return f"Issue #{d.get('number', '?')} ban gaya: {title}."
        req = _ur.Request(f"https://api.github.com/repos/{repo}/issues?state=open&per_page=5",
                          headers={"Authorization": f"Bearer {tok}",
                                   "Accept": "application/vnd.github+json"})
        with _ur.urlopen(req, timeout=15) as r:
            items = _j.loads(r.read().decode("utf-8", "replace"))
        if not items:
            return f"{repo} me koi open issue nahi hai."
        lines = [f"#{i.get('number', '?')} — {i.get('title', '?')}" for i in items[:5]]
        return f"{repo} open issues:\n" + "\n".join(lines)
    except Exception as e:
        return f"Sir, GitHub action failed: {e}"
