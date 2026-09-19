"""Additive Phase-1 tests (no destructive exec, no real sends)."""


def test_run_command_blocked():
    from actions.run_command import run_command
    out = run_command({"command": "format C: /q"})
    assert "nahi chalaunga" in out


def test_run_command_allowed_echo():
    from actions.run_command import run_command
    out = run_command({"command": "echo hello-jarvis"})
    assert "hello-jarvis" in out


def test_run_command_unknown_goes_to_gate():
    from actions.run_command import run_command
    out = run_command({"command": "myapp --do-thing"})
    # Headless me refuse, UI par CONFIRMATION_PENDING — dono me execute nahi hota
    assert ("CONFIRMATION_PENDING" in out or "not available" in out
            or "confirmation" in out.lower())


def test_macro_list_safe():
    from actions.macro import macro
    out = macro({"action": "list"})
    assert isinstance(out, str) and ("Macros:" in out or "nahi hai" in out)


def test_contacts_save_resolve_cleanup():
    from actions.contacts import contacts
    from memory import contacts as _cb
    assert "save ho gaya" in contacts({"action": "save", "name": "pytestt", "phone": "9811111111"})
    assert "9811111111" in contacts({"action": "resolve", "name": "pytestt"})
    assert _cb.save_contact is not None
    # cleanup apni entry (sample mummy untouched)
    import json
    from pathlib import Path
    p = Path("memory/contacts.json")
    d = json.loads(p.read_text(encoding="utf-8"))
    d.pop("pytestt", None)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def test_profile_list_and_unknown():
    from actions.profile import profile
    assert "gaming" in profile({"action": "list"}).lower()
    assert "nahi mili" in profile({"action": "apply", "name": "nope_xyz"})


def test_audit_append_and_recent():
    from core.audit import log_event, recent
    log_event("pytest_probe", "test entry")
    assert any(r.get("action") == "pytest_probe" for r in recent(20))


def test_send_message_alias_params():
    from actions.send_message import send_message
    # contact alias + empty message -> message error (receiver resolved, no GUI touched)
    out = send_message({"contact": "mummy", "message": "", "platform": "whatsapp"})
    assert "message content" in out
