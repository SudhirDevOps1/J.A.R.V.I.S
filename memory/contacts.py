"""Contacts book helpers. New file, additive. memory/contacts.json backed."""
from __future__ import annotations

import json
from pathlib import Path

_CONTACTS_FILE = Path(__file__).resolve().parent / "contacts.json"


def _load() -> dict:
    try:
        if _CONTACTS_FILE.exists():
            data = json.loads(_CONTACTS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save_all(contacts: dict) -> bool:
    try:
        _CONTACTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _tmp = _CONTACTS_FILE.with_suffix(".json.tmp")
        _tmp.write_text(json.dumps(contacts, indent=2, ensure_ascii=False), encoding="utf-8")
        import os as _os
        _os.replace(str(_tmp), str(_CONTACTS_FILE))
        return True
    except Exception:
        return False


def save_contact(name: str, phone: str = "", platform: str = "whatsapp", username: str = "") -> bool:
    """Naam -> phone/username save karo. Never raises."""
    try:
        n = (name or "").strip().lower()
        if not n or n.startswith("_"):
            return False
        contacts = _load()
        cur = contacts.get(n)
        entry = dict(cur) if isinstance(cur, dict) else {}
        if phone:
            import re as _re
            entry["phone"] = _re.sub(r"\D", "", phone)
        if username:
            entry["username"] = username.strip()
        if platform:
            entry["platform"] = platform
        contacts[n] = entry
        return _save_all(contacts)
    except Exception:
        return False


def resolve_contact(name: str) -> dict:
    """Naam -> {phone, platform} ya {} (never raises). Fuzzy: substring match."""
    try:
        n = (name or "").strip().lower()
        if not n:
            return {}
        contacts = _load()
        if n in contacts and isinstance(contacts[n], dict):
            return dict(contacts[n])
        for k, v in contacts.items():
            if k.startswith("_") or not isinstance(v, dict):
                continue
            if n in k or k in n:
                return dict(v)
        return {}
    except Exception:
        return {}


def list_contacts() -> list[str]:
    """Naam list (never raises)."""
    try:
        return sorted(k for k, v in _load().items()
                      if not k.startswith("_") and isinstance(v, dict))
    except Exception:
        return []
