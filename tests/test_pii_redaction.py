"""
tests/test_pii_redaction.py - Nothing sensitive reaches the journal on disk.

WHY
---
log_daily_activity writes to memory/journals/YYYY-MM-DD.md and the code calls
it an "immutable second-brain activity record". Nothing filtered it.

That is not a hypothetical. A scan of this repository's history found
config/knowledge_graph.json in commits 573a30a5 and 49f38404 holding a real
person's relationships - which relative contacts them through which messenger,
which friend is named what - in a repository that is public. The data left the
machine because a conversation was written to disk verbatim and later committed.

The tests here assert on what lands ON DISK, not on what a function returns.
A redactor that works but is called one line too late still leaks.

THE DIRECTION THAT MATTERS
-------------------------
Most of these tests assert that ordinary text is NOT touched. A redactor that
catches every secret by eating half the user's diary is not safe, it is just
quietly destructive, and the user has no way to notice until their memory is
gone.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from core.pii_redactor import (  # noqa: E402
    luhn_ok,
    redact,
    scan,
    verhoeff_ok,
)


# ── checksums, which are what make the patterns trustworthy ─────────────────

@pytest.mark.parametrize("number", [
    "4111111111111111",   # Visa
    "5500005555555559",   # Mastercard
    "378282246310005",    # Amex
    "6011111111111117",   # Discover
])
def test_real_card_numbers_pass_luhn(number):
    assert luhn_ok(number) is True


@pytest.mark.parametrize("number", [
    "4111111111111112",   # one digit off a real Visa
    "1234567890123",
    "20260114123000",     # a timestamp, not a card
    "999999999999",
    "not-a-number",
    "",
])
def test_non_cards_fail_luhn(number):
    assert luhn_ok(number) is False


def test_verhoeff_is_a_pure_checksum():
    """It must NOT contain heuristics. A 12-digit timestamp can satisfy
    Verhoeff - one arbitrary number in ten does - and that is a collision to
    be handled by the caller, not by lying about the checksum."""
    assert verhoeff_ok("234567890124") is True
    assert verhoeff_ok("999999990019") is True
    assert verhoeff_ok("202601141230") is True   # collides, but IS valid
    assert verhoeff_ok("123456789012") is False
    assert verhoeff_ok("abcdefghijkl") is False
    assert verhoeff_ok("12345") is False


# ── secrets must be caught ──────────────────────────────────────────────────

# Every value below is a synthetic fixture with the correct SHAPE so the
# patterns are exercised properly. The pre-commit credential scanner flags them,
# which is the scanner working correctly, and the escape it documents is a
# marker in the comment - deliberately not in the value, because a marker
# inside a quoted string is exactly how a real key gets smuggled through.
#
# None of these is or ever was a live credential.
@pytest.mark.parametrize("text,kind", [
    ("my openai key is sk-proj-AbCdEf0123456789XyZ", "openai-key"),  # FAKE
    ("token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", "github-token"),  # FAKE
    ("github_pat_11ABCDEFG0abcdefghijklmnop", "github-fine-grained-token"),  # FAKE
    ("google key AIzaSyD-1234567890abcdefghijklmnopqrstu", "google-api-key"),  # FAKE
    ("aws AKIAIOSFODNN7EXAMPLE", "aws-access-key"),  # FAKE (AWS's own docs value)
    ("slack xoxb-123456789012-abcdefghijkl", "slack-token"),  # FAKE
    ("gitlab glpat-AbCdEfGhIjKlMnOpQr", "gitlab-token"),  # FAKE
    ("jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVP",  # FAKE
     "jwt"),
    ("password = hunter2secret99", "assigned-secret"),  # FAKE
    ("api_key: 'my-secret-value-here'", "assigned-secret"),  # FAKE
    ("-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA\n"  # FAKE
     "-----END RSA PRIVATE KEY-----", "private-key"),
    ("clone https://user:s3cr3tpass@github.com/me/repo.git", "url-credentials"),  # FAKE
    ("email me at sudhir.devops1@gmail.com", "email"),  # FAKE
    ("my pan is ABCDE1234F", "pan-card"),  # FAKE
    ("card 4111 1111 1111 1111", "card"),  # FAKE
    ("aadhaar 2345 6789 0124", "aadhaar"),  # FAKE
    ("call me on +91 98765 43210", "phone"),  # FAKE
])
def test_secret_is_redacted(text, kind):
    kinds = {f.kind for f in scan(text)}
    assert kind in kinds, f"{kind} not found in {text!r}; got {kinds}"
    out = redact(text)
    assert "[REDACTED:" in out, out


@pytest.mark.parametrize("text,leaked", [
    ("my openai key is sk-proj-AbCdEf0123456789XyZ", "AbCdEf0123456789XyZ"),  # FAKE
    ("token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", "ABCDEFGHIJKLMNOPQRST"),  # FAKE
    ("aws AKIAIOSFODNN7EXAMPLE", "IOSFODNN7EXAMPLE"),  # FAKE
    ("email me at sudhir.devops1@gmail.com", "sudhir.devops1@gmail.com"),  # FAKE
    ("card 4111 1111 1111 1111", "4111 1111 1111 1111"),  # FAKE
])
def test_the_secret_value_does_not_survive(text, leaked):
    """Not just 'was it detected' - is the value actually gone."""
    assert leaked not in redact(text)


def test_keys_are_never_partially_kept():
    """There is no useful partial API key. Cards keep 4 digits so the owner can
    still recognise their own card; a key keeps nothing."""
    out = redact("my openai key is sk-proj-AbCdEf0123456789XyZ")  # FAKE
    assert "AbCdEf" not in out
    assert "3456789" not in out


def test_cards_keep_only_the_last_four():
    """A journal entry saying [REDACTED] cannot be recognised by the person
    who wrote it, and the point of a second-brain record is that they can."""
    out = redact("card 4111 1111 1111 1111")
    assert "1111" in out
    assert "4111 1111" not in out


def test_placeholder_is_ascii():
    """An earlier version used a bullet character and it rendered as mojibake
    through a cp1252 console - which is where the user reads it."""
    out = redact("card 4111 1111 1111 1111")
    out.encode("ascii")      # must not raise


# ── ordinary text must survive. This is the half that is easy to skip. ──────

@pytest.mark.parametrize("text", [
    "open notepad",
    "notepad khol ke usmein 10 bar hii likhein",
    "brave browser kholo aur usmein youtube chalao",
    "meeting is at 3 pm on 2026-10-14",
    "I have 12345 files in my downloads folder",
    "version 1.2.3 released in 2024",
    "my phone number is on the board",
    "tell me about the PAN of the company",
    "credit card payment failed",
    "the Aadhaar card is at home",
    "sum 1500 + 2500 = 4000",
    "today is Wednesday",
    "the server is at 192.168.1.33:8000",
    "task #910222 created",
])
def test_ordinary_text_is_untouched(text):
    assert scan(text) == [], f"false positive on {text!r}: {scan(text)}"
    assert redact(text) == text


def test_a_bare_twelve_digit_number_is_left_alone():
    """It is far more often a timestamp, a serial or a job number."""
    assert "aadhaar" not in {f.kind for f in scan("build 202601141230 done")}
    assert "aadhaar" not in {f.kind for f in scan("202601141230")}


def test_an_explicit_label_beats_the_shape_heuristic():
    """Found by the checker while writing it: the first version checked the
    date-shape rule before the label, so a user who typed the word "aadhaar"
    had their number left in the clear.

    The user named the thing. Believe them."""
    assert "aadhaar" in {f.kind for f in scan("aadhaar 202601141230")}
    assert "aadhaar" in {f.kind for f in scan("my aadhaar number is 202601141230")}


def test_relationship_words_are_not_guessed_at():
    """Documented as a deliberate non-goal.

    Redacting "mummy" or a friend's name from a Hinglish diary means guessing
    which words are names. Get it wrong and the user's own memory is mangled
    with no way to notice. Secrets are verifiable; relationships are not, so
    relationships are left to the user, not guessed."""
    text = "mummy ko whatsapp karna hai rikshit ko"
    assert redact(text) == text


def test_empty_and_none_input():
    for value in ("", "   ", None):
        assert scan(value) == []
        assert redact(value) in ("", "   ", None) or redact(value) == (value or "")


# ── the whole point: what lands on disk ────────────────────────────────────

def test_journal_file_on_disk_contains_no_secret(tmp_path, monkeypatch):
    """Asserted on the file, not the return value.

    Reading the return value would prove nothing. The redaction has to happen
    before the write, and only the file proves it did.
    """
    import memory.memory_manager as mm

    journals = tmp_path / "journals"
    monkeypatch.setattr(mm, "JOURNALS_DIR", journals)

    # Synthetic fixtures, shaped like real credentials on purpose.
    mm.log_daily_activity(
        "mera openai key sk-proj-AbCdEf0123456789XyZ hai, "  # FAKE
        "email sudhir.devops1@gmail.com par bhejo",  # FAKE
        ai_response="Set: sk-proj-AbCdEf0123456789XyZ",  # FAKE
    )
    mm.log_daily_activity(
        "card 4111 1111 1111 1111 se payment kiya",  # FAKE
        ai_response="Done.",
    )

    written = "".join(p.read_text(encoding="utf-8") for p in journals.glob("*.md"))
    assert written, "nothing was journalled - the test would be vacuous"

    for secret in ("sk-proj-AbCdEf0123456789XyZ",  # FAKE
                   "sudhir.devops1@gmail.com",  # FAKE
                   "4111 1111 1111 1111"):  # FAKE
        assert secret not in written, f"{secret!r} reached disk"
    assert "[REDACTED:" in written


def test_journal_still_records_the_ordinary_part(tmp_path, monkeypatch):
    """Redaction must not cost the user their record."""
    import memory.memory_manager as mm

    journals = tmp_path / "journals"
    monkeypatch.setattr(mm, "JOURNALS_DIR", journals)

    mm.log_daily_activity(
        "notepad khol ke usmein 10 bar hii likhein",
        ai_response="Task completed successfully.",
    )
    written = "".join(p.read_text(encoding="utf-8") for p in journals.glob("*.md"))
    assert "notepad khol ke usmein 10 bar hii likhein" in written
    assert "Task completed successfully." in written


def test_the_redactor_cannot_cost_the_user_their_journal(tmp_path, monkeypatch):
    """A broken redactor degrades to verbatim, it does not raise.

    Losing the entry would be a worse failure than storing it unredacted, and
    the log says so."""
    import memory.memory_manager as mm
    import core.pii_redactor as pr

    journals = tmp_path / "journals"
    monkeypatch.setattr(mm, "JOURNALS_DIR", journals)

    def boom(*a, **k):
        raise RuntimeError("redactor exploded")

    monkeypatch.setattr(pr, "redact_if_enabled", boom)
    monkeypatch.setitem(sys.modules, "core.pii_redactor", pr)

    mm.log_daily_activity("something worth keeping")
    written = "".join(p.read_text(encoding="utf-8") for p in journals.glob("*.md"))
    assert "something worth keeping" in written


def test_the_toggle_defaults_to_on(monkeypatch):
    """A privacy control that ships disabled is a control nobody turns on, and
    the failure it prevents has already happened once."""
    import core.privacy_guard as pg
    import core.pii_redactor as pr

    monkeypatch.setattr(pg, "load_privacy_settings",
                        lambda: {"redact_pii_in_memory": True})
    assert pr.is_enabled() is True

    monkeypatch.setattr(pg, "load_privacy_settings",
                        lambda: {"redact_pii_in_memory": False})
    assert pr.is_enabled() is False

    monkeypatch.setattr(pg, "load_privacy_settings", lambda: {})
    assert pr.is_enabled() is True, "absent key must mean ON, not OFF"


def test_disabling_the_toggle_stores_verbatim(tmp_path, monkeypatch):
    """The user must be able to turn it off. A control that cannot be turned
    off is not a control."""
    import memory.memory_manager as mm
    import core.pii_redactor as pr

    journals = tmp_path / "journals"
    monkeypatch.setattr(mm, "JOURNALS_DIR", journals)
    monkeypatch.setattr(pr, "is_enabled", lambda: False)

    mm.log_daily_activity("contact sudhir.devops1@gmail.com")  # FAKE
    written = "".join(p.read_text(encoding="utf-8") for p in journals.glob("*.md"))
    assert "sudhir.devops1@gmail.com" in written


def test_redact_if_enabled_never_raises(monkeypatch):
    import core.pii_redactor as pr
    monkeypatch.setattr(pr, "is_enabled",
                        lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert isinstance(pr.redact_if_enabled("hello"), str)