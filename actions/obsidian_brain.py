"""
Obsidian Second Brain Integration for SudhirDevOps1 AI.

Provides seamless connectivity to the user's Obsidian Vault via:
  1. Obsidian Local REST API (https://127.0.0.1:27124) with Bearer token
  2. Direct Local Vault Markdown Filesystem (dual-mode resilience)
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib3
from datetime import datetime
from pathlib import Path

import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()
DEFAULT_VAULT_DIR = BASE_DIR / "memory" / "obsidian_vault"


def _get_obsidian_settings() -> dict:
    from memory.config_manager import get_obsidian_config
    return get_obsidian_config()


def _get_local_vault_dir() -> Path:
    cfg = _get_obsidian_settings()
    configured = (cfg.get("vault_path") or "").strip()
    if configured and Path(configured).exists():
        return Path(configured)
    DEFAULT_VAULT_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_VAULT_DIR


def _rest_request(method: str, endpoint: str, data: str | None = None, json_body: dict | None = None) -> requests.Response | None:
    cfg = _get_obsidian_settings()
    api_key = (cfg.get("api_key") or "").strip()
    if not api_key:
        return None

    pref_port = cfg.get("port", 27123)
    pref_https = cfg.get("use_https", False)

    # Build candidate URLs: preferred first, then alternate HTTP/HTTPS port
    candidates = []
    candidates.append(("https" if pref_https else "http", pref_port))
    alt_proto = "http" if pref_https else "https"
    alt_port = 27123 if alt_proto == "http" else 27124
    if alt_port != pref_port:
        candidates.append((alt_proto, alt_port))

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/vnd.olra+json, application/json, text/markdown",
    }
    if data is not None:
        headers["Content-Type"] = "text/markdown"
    elif json_body is not None:
        headers["Content-Type"] = "application/json"

    clean_endpoint = endpoint.lstrip("/")
    for proto, port in candidates:
        url = f"{proto}://127.0.0.1:{port}/{clean_endpoint}"
        try:
            res = requests.request(
                method=method,
                url=url,
                headers=headers,
                data=data.encode("utf-8") if isinstance(data, str) else None,
                json=json_body,
                verify=False,
                timeout=4,
            )
            return res
        except Exception:
            continue

    return None


def test_connection() -> tuple[bool, str]:
    """Test connection to Obsidian Local REST API and/or verify local vault path."""
    cfg = _get_obsidian_settings()
    api_key = (cfg.get("api_key") or "").strip()

    # 1. Try REST API
    if api_key:
        res = _rest_request("GET", "/")
        if res and res.status_code == 200:
            try:
                info = res.json()
                svc = info.get("service", "Obsidian REST API")
                ver = info.get("manifest", {}).get("version", "5.1")
                return True, f"Connected to {svc} v{ver} (Local Port Active)"
            except Exception:
                return True, "Connected to Obsidian Local REST API"
        elif res:
            return False, f"Obsidian API returned HTTP {res.status_code}"

    # 2. Try Local Vault
    vpath = _get_local_vault_dir()
    if vpath.exists():
        notes_count = len(list(vpath.glob('*.md')))
        return True, f"Local Vault OK: {vpath.name} ({notes_count} notes)"

    return False, "REST API offline and vault path not found"


# ── Core Brain Operations ───────────────────────────────────────────────────────

def search_notes(query: str) -> str:
    """Search for notes containing query string in Obsidian vault."""
    q = (query or "").strip().lower()
    if not q:
        return "Please provide a query to search in Obsidian."

    # 1. Try REST API search (search/simple/ or search/)
    import urllib.parse
    encoded_q = urllib.parse.quote(q)
    res = _rest_request("POST", f"search/simple/?query={encoded_q}")
    if not res or res.status_code != 200:
        res = _rest_request("POST", "search/", json_body={"query": q})

    if res and res.status_code == 200:
        try:
            results = res.json()
            if results and isinstance(results, list) and len(results) > 0:
                out = [f"Found {len(results)} notes via Obsidian REST API:"]
                for r in results[:10]:
                    if isinstance(r, str):
                        out.append(f"• [[{r}]]")
                    elif isinstance(r, dict):
                        fname = r.get("filename") or r.get("path") or "note"
                        score = r.get("score")
                        out.append(f"• [[{fname}]]" + (f" (score: {score})" if score else ""))
                return "\n".join(out)
        except Exception:
            pass

    # 2. Local Vault Markdown Search Fallback
    vault = _get_local_vault_dir()
    matches = []
    if vault.exists():
        for md_file in vault.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
                rel_path = md_file.relative_to(vault).as_posix()
                if q in rel_path.lower() or q in content.lower():
                    matches.append(rel_path)
            except Exception:
                pass

    if matches:
        out = [f"Found {len(matches)} notes in Local Vault ({vault.name}):"]
        for m in matches[:10]:
            out.append(f"• [[{m}]]")
        return "\n".join(out)

    return f"No notes matching '{query}' found in Obsidian vault."


def read_note(path: str) -> str:
    """Read full content of an Obsidian note."""
    p = (path or "").strip()
    if not p:
        return "Please specify a note path to read."
    if not p.endswith(".md"):
        p += ".md"

    # 1. Try REST API
    import urllib.parse
    clean_p = urllib.parse.quote(p, safe="/")
    res = _rest_request("GET", f"vault/{clean_p}")
    if res and res.status_code == 200:
        res.encoding = "utf-8"
        return f"--- [[{p}]] ---\n{res.text}"

    # 2. Local Vault Filesystem
    vault = _get_local_vault_dir()
    fpath = vault / p
    if fpath.exists():
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            return f"--- [[{p}]] ---\n{content}"
        except Exception as e:
            return f"Error reading [[{p}]]: {e}"

    return f"Note [[{p}]] does not exist in the Obsidian vault."


def write_note(path: str, content: str) -> str:
    """Write or overwrite a note in Obsidian."""
    p = (path or "").strip()
    if not p:
        return "Please specify a note path."
    if not p.endswith(".md"):
        p += ".md"

    # 1. Try REST API
    res = _rest_request("PUT", f"vault/{p}", data=content)
    if res and res.status_code in (200, 204):
        return f"Successfully saved note [[{p}]] to Obsidian via REST API."

    # 2. Local Vault Filesystem
    vault = _get_local_vault_dir()
    fpath = vault / p
    try:
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content, encoding="utf-8")
        return f"Successfully saved note [[{p}]] in local Obsidian vault ({vault.name})."
    except Exception as e:
        return f"Failed to save note [[{p}]]: {e}"


def append_daily_note(content: str) -> str:
    """Append a thought, summary, or action entry to today's Obsidian daily note."""
    text = (content or "").strip()
    if not text:
        return "No content provided to append."

    today_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%I:%M %p")
    entry = f"\n- **[{time_str}]** {text}\n"

    # 1. Try REST API periodic daily note
    res = _rest_request("POST", "periodic/daily/", data=entry)
    if res and res.status_code in (200, 204):
        return f"Appended entry to today's daily note ({today_str}) in Obsidian."

    # 2. Local Vault Daily Note
    vault = _get_local_vault_dir()
    daily_file = vault / f"{today_str}.md"
    try:
        if not daily_file.exists():
            daily_file.write_text(f"# 📅 Daily Note — {today_str}\n\n", encoding="utf-8")
        with open(daily_file, "a", encoding="utf-8") as f:
            f.write(entry)
        return f"Appended entry to daily note ({today_str}.md) in vault."
    except Exception as e:
        return f"Failed to append to daily note: {e}"


# ── Main Tool Handler ──────────────────────────────────────────────────────────

def obsidian_brain(parameters: dict, player=None, **_) -> str:
    action = (parameters.get("action") or "status").lower().strip()
    path = parameters.get("path", "")
    content = parameters.get("content", "")
    query = parameters.get("query", "")

    if player:
        player.write_log(f"BRAIN: Obsidian {action.upper()} ({path or query or 'daily'})")

    if action == "search":
        return search_notes(query or path)
    elif action == "read":
        return read_note(path or query)
    elif action == "write":
        return write_note(path, content)
    elif action in ("append_daily", "daily"):
        return append_daily_note(content)
    elif action == "status":
        cfg = _get_obsidian_settings()
        v = _get_local_vault_dir()
        has_key = bool((cfg.get("api_key") or "").strip())
        return f"Obsidian Brain Status: Local Vault at '{v}'. REST API configured: {has_key} (Port {cfg.get('port', 27124)})."
    else:
        return f"Unknown obsidian action: '{action}'. Available: search, read, write, append_daily, status."


TOOL = {
    "name": "obsidian_brain",
    "description": "Interact with the user's Obsidian Second Brain vault. Search existing notes, read documentation/thoughts, create new markdown notes, and log thoughts to daily notes. Always use this when the user mentions Obsidian, notes, thoughts, second brain, or past knowledge.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action to perform: 'search', 'read', 'write', 'append_daily', or 'status'",
            },
            "path": {
                "type": "STRING",
                "description": "Path or name of the note (e.g. 'ProjectPlan.md', 'Ideas/Python')",
            },
            "content": {
                "type": "STRING",
                "description": "Text content to write or append to the note",
            },
            "query": {
                "type": "STRING",
                "description": "Search keyword when searching notes",
            },
        },
        "required": ["action"],
    },
    "handler": obsidian_brain,
}
