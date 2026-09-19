"""Plugin credential registry — auto-detect + guided save. New file, additive.
Har plugin: kya chahiye, kahan jata hai, kaise check karein, kahan se layein.
UI (PluginSettingsOverlay) isko padhke CREDENTIALS section banata hai.
Env > api_keys.json > default — read order wahi jo plugins use karte hain.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path


def _api_cfg() -> dict:
    try:
        from memory.config_manager import load_api_keys
        d = load_api_keys()
        if isinstance(d, dict) and d:
            return d
    except Exception:
        pass
    try:
        base = Path(__file__).resolve().parent.parent
        f = base / "config" / "api_keys.json"
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _cred_file(name: str) -> Path:
    return Path(os.path.expanduser(f"~/.credentials/{name}_token.json"))


def _has_file_cred(name: str) -> bool:
    try:
        p = _cred_file(name)
        return p.exists() and p.stat().st_size > 10
    except Exception:
        return False


def _has_keys(*keys: str) -> bool:
    try:
        cfg = _api_cfg()
        for k in keys:
            v = cfg.get(k, "") or os.environ.get(k.upper(), "")
            if isinstance(v, str) and v.strip():
                return True
        return False
    except Exception:
        return False


def save_keys(values: dict) -> bool:
    """api_keys.json keys save karo (atomic helper reuse). Never raises."""
    try:
        from memory.config_manager import _patch_config
        clean = {str(k): str(v).strip() for k, v in (values or {}).items()
                 if str(v).strip()}
        if not clean:
            return False
        _patch_config(**clean)
        return True
    except Exception:
        return False


def import_cred_file(kind: str, src_path: str) -> tuple[bool, str]:
    """Download ki hui OAuth JSON ko sahi jagah copy karo. Never raises."""
    try:
        src = Path(src_path)
        if not src.exists():
            return False, "File nahi mili."
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return False, "Valid JSON nahi hai."
        except Exception:
            return False, "Valid JSON file chahiye."
        dst = _cred_file(kind)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dst))
        return True, f"Saved: {dst}"
    except Exception as e:
        return False, f"Import failed: {e}"


def save_smart_device(name: str, dev_id: str, key: str, ip: str = "") -> tuple[bool, str]:
    """smart_home.json me device jodo. Never raises."""
    try:
        base = Path(__file__).resolve().parent.parent
        f = base / "config" / "smart_home.json"
        devs = {}
        if f.exists():
            try:
                devs = json.loads(f.read_text(encoding="utf-8"))
                if not isinstance(devs, dict):
                    devs = {}
            except Exception:
                devs = {}
        n = (name or "").strip().lower()
        if not n or not dev_id.strip() or not key.strip():
            return False, "Naam + id + key teeno do."
        devs[n] = {"id": dev_id.strip(), "key": key.strip(), "ip": ip.strip()}
        _tmp = f.with_suffix(".json.tmp")
        _tmp.write_text(json.dumps(devs, indent=2), encoding="utf-8")
        os.replace(str(_tmp), str(f))
        return True, f"Device '{n}' save ho gaya."
    except Exception as e:
        return False, f"Save failed: {e}"


def smart_device_count() -> int:
    try:
        base = Path(__file__).resolve().parent.parent
        f = base / "config" / "smart_home.json"
        devs = json.loads(f.read_text(encoding="utf-8"))
        return sum(1 for k, v in devs.items()
                   if not k.startswith("_") and isinstance(v, dict) and v.get("id"))
    except Exception:
        return 0


SPECS: list[dict] = [
    {"plugin": "gmail_tool", "label": "Gmail",
     "kind": "file", "file_kind": "gmail",
     "detect": lambda: _has_file_cred("gmail"),
     "help_url": "https://console.cloud.google.com/apis/credentials",
     "help_text": "Google Cloud → OAuth Desktop → JSON download karo → IMPORT dabao."},
    {"plugin": "calendar_tool", "label": "Google Calendar",
     "kind": "file", "file_kind": "calendar",
     "detect": lambda: _has_file_cred("calendar"),
     "help_url": "https://console.cloud.google.com/apis/credentials",
     "help_text": "Wahi Google OAuth JSON (Calendar scope) → IMPORT dabao."},
    {"plugin": "drive_tool", "label": "Google Drive",
     "kind": "file", "file_kind": "drive",
     "detect": lambda: _has_file_cred("drive"),
     "help_url": "https://console.cloud.google.com/apis/credentials",
     "help_text": "Wahi Google OAuth JSON (Drive scope) → IMPORT dabao."},
    {"plugin": "spotify_control", "label": "Spotify",
     "kind": "keys", "keys": ["spotipy_client_id"],
     "fields": [{"key": "spotipy_client_id", "label": "Client ID", "secret": False}],
     "detect": lambda: _has_keys("spotipy_client_id", "SPOTIPY_CLIENT_ID"),
     "help_url": "https://developer.spotify.com/dashboard",
     "help_text": "Spotify Dashboard → app → Client ID paste karo → SAVE."},
    {"plugin": "notion_sync", "label": "Notion",
     "kind": "keys", "keys": ["notion_token"],
     "fields": [{"key": "notion_token", "label": "Integration Token", "secret": True}],
     "detect": lambda: _has_keys("notion_token", "NOTION_TOKEN"),
     "help_url": "https://www.notion.so/my-integrations",
     "help_text": "New integration → token copy → paste → SAVE."},
    {"plugin": "github_tool", "label": "GitHub",
     "kind": "keys", "keys": ["github_token"],
     "fields": [{"key": "github_token", "label": "Personal Access Token", "secret": True}],
     "detect": lambda: _has_keys("github_token", "GITHUB_TOKEN"),
     "help_url": "https://github.com/settings/tokens",
     "help_text": "Fine-grained PAT (issues:read/write) → paste → SAVE."},
    {"plugin": "slack_tool", "label": "Slack",
     "kind": "keys", "keys": ["slack_bot_token"],
     "fields": [{"key": "slack_bot_token", "label": "Bot Token (xoxb-...)", "secret": True}],
     "detect": lambda: _has_keys("slack_bot_token", "SLACK_BOT_TOKEN"),
     "help_url": "https://api.slack.com/apps",
     "help_text": "App → OAuth → Bot token → paste → SAVE."},
    {"plugin": "send_message", "label": "Telegram (via send_message)",
     "kind": "keys", "keys": ["telegram_bot_token", "telegram_chat_id"],
     "fields": [{"key": "telegram_bot_token", "label": "Bot Token", "secret": True},
                {"key": "telegram_chat_id", "label": "Chat ID", "secret": False}],
     "detect": lambda: _has_keys("telegram_bot_token", "TELEGRAM_BOT_TOKEN"),
     "help_url": "https://t.me/BotFather",
     "help_text": "@BotFather → /newbot → token + chat id paste → SAVE."},
    {"plugin": "smart_home", "label": "Tuya Smart Home",
     "kind": "smart",
     "detect": lambda: smart_device_count() > 0,
     "help_url": "https://platform.tuya.com/",
     "help_text": "Neeche device jodo (Tuya app se id/key)."},
    {"plugin": "pomodoro_timer", "label": "Pomodoro",
     "kind": "none",
     "detect": lambda: True,
     "help_url": "",
     "help_text": "Setup nahi chahiye — turant chalta hai ✓"},
    {"plugin": "stock_price", "label": "Stocks",
     "kind": "none",
     "detect": lambda: True,
     "help_url": "",
     "help_text": "Setup nahi chahiye — free Stooq ✓"},
]


def status_all() -> list[tuple[str, bool]]:
    """[(label, connected)]. Never raises."""
    out = []
    for spec in SPECS:
        try:
            out.append((spec.get("label", spec.get("plugin", "?")), bool(spec["detect"]())))
        except Exception:
            out.append((spec.get("label", "?"), False))
    return out
