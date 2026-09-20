"""
Obsidian Second Brain Integration for SudhirDevOps1 AI.

Provides seamless connectivity to the user's Obsidian Vault via:
  1. Obsidian Local REST API (http://127.0.0.1:27123) with Bearer token
  2. Direct Local Vault Markdown Filesystem (dual-mode resilience)
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
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

    # 2. Try Local Vault (explicit fallback — user ko pata chale kahan save hoga)
    vpath = _get_local_vault_dir()
    if vpath.exists():
        cfg_path = (_get_obsidian_settings().get("vault_path") or "").strip()
        notes_count = len(list(vpath.glob('*.md')))
        if cfg_path and Path(cfg_path).resolve() != vpath.resolve():
            return True, (f"Local Vault OK: {vpath.name} ({notes_count} notes). "
                          f"NOTE: configured path '{cfg_path}' nahi mila, isliye fallback vault me save hoga.")
        return True, f"Local Vault OK: {vpath.name} ({notes_count} notes)"

    return False, "REST API offline and vault path not found"


# ── Core Brain Operations ───────────────────────────────────────────────────────

def list_notes(folder: str = "") -> str:
    """List all notes in the Obsidian vault (or a subfolder)."""
    # 1. Try REST API — GET vault/ or GET vault/{folder}/
    endpoint = f"vault/{urllib.parse.quote(folder.strip('/'), safe='/')}/" if folder.strip() else "vault/"
    res = _rest_request("GET", endpoint)
    if res and res.status_code == 200:
        try:
            data = res.json()
            files = data.get("files", [])
            if files:
                out = [f"[Obsidian Vault] {len(files)} items:"]
                for f in sorted(files):
                    icon = "[DIR]" if f.endswith("/") else "[NOTE]"
                    out.append(f"  {icon} {f}")
                return "\n".join(out)
            return "Vault is empty."
        except Exception:
            pass

    # 2. Local Vault Fallback
    vault = _get_local_vault_dir()
    if vault.exists():
        all_files = sorted(vault.rglob("*.md"))
        if all_files:
            out = [f"[Local Vault '{vault.name}'] {len(all_files)} notes:"]
            for f in all_files[:20]:
                out.append(f"  [NOTE] {f.relative_to(vault).as_posix()}")
            return "\n".join(out)
    return "No notes found in vault."


def search_notes(query: str) -> str:
    """Search for notes containing query string in Obsidian vault."""
    q = (query or "").strip().lower()
    if not q:
        return "Please provide a query to search in Obsidian."

    # 1. Try REST API search — GET search/simple/ (Obsidian Local REST API v5.1 standard)
    encoded_q = urllib.parse.quote(q)
    res = _rest_request("GET", f"search/simple/?query={encoded_q}&contentLength=300")
    if not res or res.status_code != 200:
        res = _rest_request("POST", f"search/simple/?query={encoded_q}&contentLength=300")

    if res and res.status_code == 200:
        try:
            results = res.json()
            if results and isinstance(results, list) and len(results) > 0:
                out = [f"🔍 Found {len(results)} notes in Obsidian:"]
                for r in results[:10]:
                    if isinstance(r, str):
                        out.append(f"• [[{r}]]")
                    elif isinstance(r, dict):
                        fname = r.get("filename") or r.get("path") or "note"
                        score = r.get("score")
                        matches = r.get("matches", [])
                        snippet = ""
                        for m in matches[:1]:
                            ctx = m.get("context", "")
                            if ctx:
                                snippet = f" — ...{ctx[:80]}..."
                        out.append(f"• [[{fname}]]" + (f" (score: {score:.2f})" if score else "") + snippet)
                return "\n".join(out)
        except Exception:
            pass

    # 2. Filename-only search via vault listing
    res2 = _rest_request("GET", "vault/")
    if res2 and res2.status_code == 200:
        try:
            files = res2.json().get("files", [])
            matches = [f for f in files if q in f.lower()]
            if matches:
                out = [f"🔍 Found {len(matches)} notes matching '{q}' (by filename):"]
                for f in matches[:10]:
                    out.append(f"• [[{f}]]")
                return "\n".join(out)
        except Exception:
            pass

    # 3. Local Vault Markdown Search Fallback
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
        out = [f"🔍 Found {len(matches)} notes in Local Vault ({vault.name}):"]
        for m in matches[:10]:
            out.append(f"• [[{m}]]")
        return "\n".join(out)

    return f"No notes matching '{query}' found in Obsidian vault."


def read_note(path: str) -> str:
    """Read full content of an Obsidian note."""
    p = (path or "").strip()
    if not p:
        return "Please specify a note path to read."
    # Strip any duplicate .md.md or .md.MD extensions (model sometimes sends double)
    p = re.sub(r'(\.md)+$', '.md', p, flags=re.IGNORECASE)
    if not p.lower().endswith(".md"):
        p += ".md"
    p = p.strip(" _")  # strip stray underscores/spaces at edges

    # 1. Try REST API
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
    # Strip duplicate .md.md extensions and stray edge chars
    p = re.sub(r'(\.md)+$', '.md', p, flags=re.IGNORECASE)
    if not p.lower().endswith(".md"):
        p += ".md"
    p = p.strip(" _")

    # 1. Try REST API — URL-encode path to handle spaces & Unicode
    clean_p = urllib.parse.quote(p, safe="/")
    res = _rest_request("PUT", f"vault/{clean_p}", data=content)
    if res and res.status_code in (200, 204):
        return f"✅ Successfully saved note [[{p}]] to Obsidian via REST API."

    # 2. Local Vault Filesystem
    vault = _get_local_vault_dir()
    fpath = vault / p
    try:
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content, encoding="utf-8")
        return f"✅ Saved note [[{p}]] in local Obsidian vault ({vault.name})."
    except Exception as e:
        return f"❌ Failed to save note [[{p}]]: {e}"


def append_to_note(path: str, content: str) -> str:
    """Append content to an existing note without overwriting."""
    p = (path or "").strip()
    if not p:
        return "Please specify a note path."
    if not p.endswith(".md"):
        p += ".md"

    # 1. Try REST API — POST vault/{path} appends to existing note
    clean_p = urllib.parse.quote(p, safe="/")
    res = _rest_request("POST", f"vault/{clean_p}", data=content)
    if res and res.status_code in (200, 204):
        return f"✅ Appended to [[{p}]] via REST API."

    # 2. Local Vault Fallback — read + write
    vault = _get_local_vault_dir()
    fpath = vault / p
    try:
        existing = fpath.read_text(encoding="utf-8") if fpath.exists() else ""
        fpath.write_text(existing + "\n" + content, encoding="utf-8")
        return f"✅ Appended to [[{p}]] in local vault."
    except Exception as e:
        return f"❌ Failed to append to [[{p}]]: {e}"


def delete_note(path: str) -> str:
    """Delete a note from Obsidian vault."""
    p = (path or "").strip()
    if not p:
        return "Please specify a note path to delete."
    if not p.endswith(".md"):
        p += ".md"

    # 1. Try REST API — DELETE vault/{path}
    clean_p = urllib.parse.quote(p, safe="/")
    res = _rest_request("DELETE", f"vault/{clean_p}")
    if res and res.status_code in (200, 204):
        return f"🗑️ Deleted note [[{p}]] from Obsidian vault."
    if res and res.status_code == 404:
        return f"Note [[{p}]] not found in vault."

    # 2. Local Vault Fallback
    vault = _get_local_vault_dir()
    fpath = vault / p
    if fpath.exists():
        try:
            fpath.unlink()
            return f"🗑️ Deleted [[{p}]] from local vault."
        except Exception as e:
            return f"❌ Failed to delete [[{p}]]: {e}"

    return f"Note [[{p}]] not found."


def rename_note(old_path: str, new_path: str) -> str:
    """Rename or move a note in Obsidian vault (supports both REST API & local vault)."""
    p_old = (old_path or "").strip()
    p_new = (new_path or "").strip()
    if not p_old:
        return "Please specify the current note path to rename."
    if not p_new:
        return "Please specify the new note name or destination path."

    p_old = re.sub(r'(\.md)+$', '.md', p_old, flags=re.IGNORECASE)
    if not p_old.lower().endswith(".md"):
        p_old += ".md"
    p_old = p_old.strip(" _")

    p_new = re.sub(r'(\.md)+$', '.md', p_new, flags=re.IGNORECASE)
    if not p_new.lower().endswith(".md"):
        p_new += ".md"
    p_new = p_new.strip(" _")

    if p_old == p_new:
        return f"Old and new note names are identical: [[{p_old}]]."

    # 1. Try REST API (Read old -> Write new -> Delete old)
    cfg = _get_obsidian_settings()
    if (cfg.get("api_key") or "").strip():
        clean_old = urllib.parse.quote(p_old, safe="/")
        clean_new = urllib.parse.quote(p_new, safe="/")
        
        read_res = _rest_request("GET", f"vault/{clean_old}")
        if read_res and read_res.status_code == 200:
            content = read_res.text or ""
            put_res = _rest_request("PUT", f"vault/{clean_new}", data=content)
            if put_res and put_res.status_code in (200, 204):
                _rest_request("DELETE", f"vault/{clean_old}")
                return f"✅ Renamed note [[{p_old}]] to [[{p_new}]] in Obsidian via REST API."

    # 2. Local Vault Filesystem
    vault = _get_local_vault_dir()
    old_file = vault / p_old
    new_file = vault / p_new

    if old_file.exists():
        try:
            new_file.parent.mkdir(parents=True, exist_ok=True)
            old_file.rename(new_file)
            return f"✅ Renamed note [[{p_old}]] to [[{p_new}]] in local Obsidian vault ({vault.name})."
        except Exception as e:
            return f"❌ Failed to rename note [[{p_old}]]: {e}"

    # Case-insensitive fallback match in local vault
    if vault.exists():
        for f in vault.rglob("*.md"):
            if f.name.lower() == Path(p_old).name.lower():
                try:
                    dest = f.parent / Path(p_new).name
                    f.rename(dest)
                    return f"✅ Renamed note [[{f.name}]] to [[{dest.name}]] in local Obsidian vault."
                except Exception as e:
                    return f"❌ Failed to rename: {e}"

    return f"Note [[{p_old}]] not found in Obsidian vault."


def append_daily_note(content: str) -> str:
    """Append a thought, summary, or action entry to today's Obsidian daily note."""
    text = (content or "").strip()
    if not text:
        return "No content provided to append."

    today_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%I:%M %p")
    entry = f"\n- **[{time_str}]** {text}\n"

    # 1. Try periodic/daily/ endpoint (requires Periodic Notes or Daily Notes plugin)
    res = _rest_request("POST", "periodic/daily/", json_body={"content": entry})
    if res and res.status_code in (200, 204):
        return f"📅 Appended to today's daily note ({today_str}) in Obsidian."

    # 2. Try writing directly to "Daily Notes/YYYY-MM-DD.md" (common vault layout)
    daily_path = f"Daily Notes/{today_str}.md"
    clean_daily = urllib.parse.quote(daily_path, safe="/")

    # Read existing content first to append properly
    existing_res = _rest_request("GET", f"vault/{clean_daily}")
    if existing_res and existing_res.status_code == 200:
        existing_content = existing_res.text or ""
        new_content = existing_content + entry
        write_res = _rest_request("PUT", f"vault/{clean_daily}", data=new_content)
        if write_res and write_res.status_code in (200, 204):
            return f"📅 Appended to [[Daily Notes/{today_str}.md]] in Obsidian."

    # 3. Try root-level YYYY-MM-DD.md
    root_daily = f"{today_str}.md"
    clean_root = urllib.parse.quote(root_daily, safe="/")
    existing_res2 = _rest_request("GET", f"vault/{clean_root}")
    if existing_res2 and existing_res2.status_code == 200:
        existing_content2 = existing_res2.text or ""
        new_content2 = existing_content2 + entry
        write_res2 = _rest_request("PUT", f"vault/{clean_root}", data=new_content2)
        if write_res2 and write_res2.status_code in (200, 204):
            return f"📅 Appended to [[{today_str}.md]] in Obsidian."

    # 4. Create new daily note at root level
    header_content = f"# 📅 Daily Note — {today_str}\n\n{entry}"
    write_new = _rest_request("PUT", f"vault/{clean_root}", data=header_content)
    if write_new and write_new.status_code in (200, 204):
        return f"📅 Created and wrote to [[{today_str}.md]] in Obsidian."

    # 5. Local Vault Daily Note — absolute fallback
    vault = _get_local_vault_dir()
    daily_file = vault / f"{today_str}.md"
    try:
        if not daily_file.exists():
            daily_file.write_text(f"# 📅 Daily Note — {today_str}\n\n", encoding="utf-8")
        with open(daily_file, "a", encoding="utf-8") as f:
            f.write(entry)
        return f"📅 Appended to daily note ({today_str}.md) in local vault."
    except Exception as e:
        return f"❌ Failed to append to daily note: {e}"


# ── Main Tool Handler ──────────────────────────────────────────────────────────

def obsidian_brain(parameters: dict, player=None, **_) -> str:
    action = (parameters.get("action") or "status").lower().strip()
    path = (parameters.get("path") or "").strip()
    content = parameters.get("content", "")
    query = (parameters.get("query") or "").strip()

    # Strip common Hindi prepositions from path (edge router may inject these)
    _path_noise = re.compile(
        r"^\s*(se|ka|ki|ke|mein|me|par|ko|tak|wala)\s+", re.IGNORECASE
    )
    path = _path_noise.sub("", path).strip()

    if player:
        player.write_log(f"BRAIN: Obsidian {action.upper()} ({path or query or 'daily'})")

    if action == "list":
        folder = path or query or ""
        return list_notes(folder)
    elif action == "search":
        return search_notes(query or path)
    elif action == "read":
        return read_note(path or query)
    elif action == "write":
        return write_note(path, content)
    elif action == "append":
        return append_to_note(path, content)
    elif action in ("delete", "remove"):
        return delete_note(path or query)
    elif action in ("rename", "move"):
        new_p = (parameters.get("new_path") or parameters.get("target") or parameters.get("destination") or query or content or "").strip()
        return rename_note(path, new_p)
    elif action in ("delete_all", "clear_all", "sab_delete"):
        # List vault, delete every .md that is NOT a daily note
        res_list = _rest_request("GET", "vault/")
        if not res_list or res_list.status_code != 200:
            return "Obsidian vault se notes list nahi ho paya — REST API check karo."
        try:
            all_files = res_list.json().get("files", [])
        except Exception:
            return "Vault listing parse nahi hua."
        md_files = [f for f in all_files if f.endswith(".md")]
        if not md_files:
            return "Vault mein koi .md notes nahi hain delete karne ke liye."
        deleted, failed = [], []
        for fname in md_files:
            clean_f = urllib.parse.quote(fname, safe="/")
            r = _rest_request("DELETE", f"vault/{clean_f}")
            if r and r.status_code in (200, 204):
                deleted.append(fname)
            else:
                failed.append(fname)
        result_lines = [f"Vault cleanup complete: {len(deleted)} notes deleted."]
        if deleted:
            result_lines.append("Deleted: " + ", ".join(f"[[{f}]]" for f in deleted))
        if failed:
            result_lines.append("Failed (skip manually): " + ", ".join(failed))
        return "\n".join(result_lines)
    elif action in ("append_daily", "daily"):
        return append_daily_note(content or query)
    elif action == "status":
        cfg = _get_obsidian_settings()
        v = _get_local_vault_dir()
        has_key = bool((cfg.get("api_key") or "").strip())
        cfg_path = (cfg.get("vault_path") or "").strip()
        ok, msg = test_connection()
        conn_icon = "🟢" if ok else "🔴"
        if cfg_path and not Path(cfg_path).exists():
            return (f"Obsidian Brain Status: {conn_icon} configured vault '{cfg_path}' NOT FOUND. "
                    f"Saving to fallback '{v}'. REST API configured: {has_key}. "
                    f"Path theek karo ya Obsidian app kholo.")
        return (f"Obsidian Brain Status: {conn_icon} {msg} | "
                f"Local Vault: '{cfg_path or v}' | "
                f"REST API: {'✅' if has_key else '❌ not configured'} "
                f"(Port {cfg.get('port', 27123)})")
    else:
        return (f"Unknown obsidian action: '{action}'. "
                f"Available: list, search, read, write, append, rename, delete, append_daily, status.")


TOOL = {
    "name": "obsidian_brain",
    "description": (
        "Interact with the user's Obsidian Second Brain markdown notes vault. "
        "Search notes, read/write/append/rename/delete notes, list vault contents, "
        "or bulk delete/clear all notes ('all notes delete karo', 'sab delete kar do', 'clear notes'). "
        "Use this whenever user mentions Obsidian, notes, second brain, or wants to store/retrieve/clean knowledge."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "Action to perform: "
                    "'list' (show all notes), "
                    "'search' (find notes by keyword), "
                    "'read' (read note content), "
                    "'write' (create/overwrite note), "
                    "'append' (add to existing note without overwriting), "
                    "'rename' (rename or move a note to a new name/path), "
                    "'delete' (remove single note), "
                    "'delete_all' (delete/clear all created markdown notes from vault), "
                    "'append_daily' (add entry to today's daily note), "
                    "'status' (connection status)"
                ),
            },
            "path": {
                "type": "STRING",
                "description": "Path or name of the note (e.g. 'ProjectPlan.md', 'Ideas/Python', 'Daily Notes/2024-01-15')",
            },
            "new_path": {
                "type": "STRING",
                "description": "New path or name for the note when action is 'rename'",
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
