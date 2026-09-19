"""Contacts book tool — save/resolve/list. New file, auto-discovered."""
from __future__ import annotations


def contacts(parameters: dict | None = None, player=None, session_memory=None, **_) -> str:
    from memory import contacts as _cb
    params = parameters or {}
    action = str(params.get("action", "list") or "list").lower().strip()
    name = str(params.get("name", "") or "").strip()
    if action in ("save", "add", "yaad"):
        phone = str(params.get("phone", "") or "").strip()
        username = str(params.get("username", params.get("handle", "")) or "").strip()
        if not name:
            return "Naam batao (e.g. name='mummy', phone='98...')."
        ok = _cb.save_contact(name, phone, str(params.get("platform", "whatsapp") or "whatsapp"), username=username)
        if player:
            try:
                player.write_log(f"[contacts] saved {name}")
            except Exception:
                pass
        return f"'{name}' save ho gaya." if ok else f"'{name}' save nahi hua."
    if action in ("resolve", "find", "number"):
        if not name:
            return "Kiska number? Naam bolo."
        hit = _cb.resolve_contact(name)
        if not hit:
            return f"'{name}' contacts me saved nahi hai. WhatsApp/Telegram par direct search karke message bhejne ke liye send_message(platform='whatsapp'/'telegram', receiver='{name}', message_text=...) call karo."
        ph = hit.get("phone", "") or "no phone saved"
        usr = hit.get("username", "")
        parts = []
        if ph and ph != "no phone saved": parts.append(ph)
        if usr: parts.append(f"@{usr.lstrip('@')}")
        parts.append(hit.get('platform', 'whatsapp'))
        return f"{name}: {' | '.join(parts)}."
    names = _cb.list_contacts()
    return ("Contacts: " + ", ".join(names)) if names else "Contacts khali hai."


TOOL = {
    "name": "contacts",
    "description": (
        "Save and look up contact names with phone numbers. Trigger on "
        "'number yaad karo', 'kiska number', 'contacts dikhao'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "save | resolve | list"},
            "name": {"type": "STRING", "description": "Contact name"},
            "phone": {"type": "STRING", "description": "Phone digits for save"},
            "platform": {"type": "STRING", "description": "whatsapp | telegram, default whatsapp"},
        },
        "required": ["action"],
    },
    "handler": contacts,
}
