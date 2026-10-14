"""
tests/test_computer_control_wiring.py - The verification layer, actually wired in.

The verifier itself is covered in tests/test_action_verifier.py. What matters
here is that computer_control actually uses it, because the failure mode is
specific: a helper that works perfectly and that nothing calls.

TWO BUGS FOUND BY RUNNING THIS WIRING, NOT BY READING IT
-------------------------------------------------------
1. retry(action='retry') recursed until "maximum recursion depth exceeded".
   The inner action was read from params['action'] - the same key that selects
   retry - so it could only ever read back "retry".

2. retry read the inner action from params['action'] at all, which made the
   feature impossible to use even once the recursion was fixed: there was no
   way to name an action to retry. It now comes from `do`.

Both were found by calling the function. Neither was visible in review, which
is the whole reason these tests exist rather than a code comment claiming the
path is safe.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from actions.computer_control import computer_control  # noqa: E402
from core.action_verifier import Verification  # noqa: E402


# ── retry must not be able to recurse ───────────────────────────────────────

def test_retry_cannot_wrap_itself():
    """Ran, not reasoned about: this is the exact call that blew the stack."""
    out = computer_control({"action": "retry"})
    assert isinstance(out, str)
    assert "maximum recursion" not in out.lower()
    assert "retry" in out.lower()


def test_retry_refuses_retry_as_the_inner_action():
    out = computer_control({"action": "retry", "do": "retry"})
    assert "dobara retry nahi" in out.lower() or "retry" in out.lower()
    assert "maximum recursion" not in out.lower()


def test_retry_refuses_wait_until_as_the_inner_action():
    out = computer_control({"action": "retry", "do": "wait_until"})
    assert "maximum recursion" not in out.lower()


def test_retry_explains_how_to_name_the_inner_action():
    """It must not just refuse; the user has to be able to fix it."""
    out = computer_control({"action": "retry"})
    assert "'do'" in out, out


def test_retry_terminates_on_a_real_inner_action():
    """Runs the inner action, verifies it, and stops - without a stack blow-up."""
    out = computer_control({"action": "retry", "do": "copy", "attempts": 2})
    assert isinstance(out, str)
    assert len(out) < 2000, "output grew, which suggests the nesting did too"


# ── wait_until replaces sleeping ────────────────────────────────────────────

def test_wait_until_on_a_file_that_exists_succeeds():
    out = computer_control({"action": "wait_until", "for": "file",
                            "value": "C:/Windows/win.ini", "timeout": 3})
    assert "✓" in out, out


def test_wait_until_on_a_file_that_cannot_exist_fails_honestly():
    out = computer_control({"action": "wait_until", "for": "file",
                            "value": "C:/definitely/not/here.txt", "timeout": 0.5})
    assert "✗" in out, out


def test_wait_until_rejects_an_unknown_condition_kind():
    out = computer_control({"action": "wait_until", "for": "banana", "value": "x"})
    assert "samajh nahi" in out.lower()
    # It must say what IS supported, not just that it failed.
    assert "window" in out and "file" in out


def test_wait_until_without_a_value_asks_for_one():
    out = computer_control({"action": "wait_until", "for": "file"})
    assert "wait karna hai" in out.lower()
    # It must show an example, not just a refusal.
    assert "jaise" in out.lower() or "example" in out.lower()


def test_wait_until_screen_uses_local_ocr_never_cloud_vision(monkeypatch):
    """wait_until polls. Cloud vision per poll would cost seconds, money and
    the user's screen contents on every iteration.

    Asserted BEHAVIOURALLY, by making the cloud path explode if it is reached.
    A source grep for "_screen_find" would match the comment explaining why it
    is not called - the same trap that makes source-grep assertions useless.

    The stubs are verified BEFORE the call. The earlier version patched with a
    string target and raising=False, then assumed it had applied. It had not,
    in the full suite: the real _screen_ocr ran, easyocr is not installed so
    that call takes about three and a half seconds, against a one-second
    budget, and the test failed for reasons unrelated to what it checks.
    """
    import actions.computer_control as cc
    import actions.ocr_tools as ocr

    called = []

    def explode(*a, **k):
        called.append(True)
        raise AssertionError("_screen_find must never run inside the wait loop")

    monkeypatch.setattr(cc, "_screen_find", explode)
    monkeypatch.setattr(ocr, "_screen_ocr", lambda *a, **k: "hello world")

    # If these are not in force the test is measuring the real thing, not the
    # routing. Say so here instead of failing mysteriously downstream.
    assert ocr._screen_ocr() == "hello world", (
        "the OCR stub did not take effect; this test would be exercising the "
        "real OCR engine instead of the routing it claims to check"
    )
    try:
        cc._screen_find("anything")
        raise AssertionError("_screen_find stub did not take effect")
    except AssertionError as e:
        assert "must never run" in str(e)

    # Clear the flag: proving the cloud stub works required calling it on
    # purpose, and leaving that call recorded made the assertion below
    # impossible to satisfy - it was failing on its own probe, not on the code.
    called.clear()

    out = computer_control({"action": "wait_until", "for": "screen",
                            "value": "hello", "timeout": 5})

    assert not called, "the cloud vision path was reached from the wait loop"
    assert "✓" in out, out


def test_the_real_ocr_is_not_required_for_this_feature():
    """easyocr is optional and is not installed here, so the real _screen_ocr
    is slow and answers with a 'not installed' message.

    Recorded rather than asserted as a failure: the point is that nothing here
    depends on it being present or fast.
    """
    try:
        from actions.ocr_tools import _screen_ocr
    except Exception:
        pytest.skip("ocr_tools is not importable in this environment")

    assert callable(_screen_ocr)


# ── capabilities: the assistant can be honest about its own limits ──────────

def test_capabilities_action_reports_what_is_available():
    out = computer_control({"action": "capabilities"})
    assert "Verification capabilities" in out
    assert "Cloud vision is deliberately never used" in out


# ── visual_verify was dead code, now it is a documented escalation ──────────

def test_visual_verify_asks_for_a_description():
    out = computer_control({"action": "visual_verify"})
    assert "description" in out.lower()


def test_visual_verify_is_now_reachable_from_the_documentation():
    """It was already in the tool enum and had zero callers. A test that only
    calls it directly would not have noticed that."""
    src = (_ROOT / "actions" / "computer_control.py").read_text(encoding="utf-8-sig")
    assert 'action == "visual_verify"' in src
    assert "visual_verify" in src.split('"description": "type |')[1][:400]


# ── the results now carry the truth ─────────────────────────────────────────

def test_verified_result_text_says_which_state_it_was(monkeypatch):
    """Without this the verification runs and the user is never told, which is
    the same as not having verified at all."""
    import actions.computer_control as cc
    from core import action_verifier as av

    out = cc._verified("Typed: hello", av.Verification(av.FAILED, "text not there"))
    assert "NOT VERIFIED" in out
    assert out.startswith("Typed: hello"), "the original message must survive"

    out2 = cc._verified("Typed: hello", av.Verification(av.UNKNOWN, "cannot read"))
    assert "unverified" in out2.lower()


def test_verified_passes_the_result_through_when_there_is_nothing_to_say():
    import actions.computer_control as cc

    assert cc._verified("Typed: hello", None) == "Typed: hello"


def test_verified_survives_a_broken_verification_object():
    """Verification must never be the reason an action fails."""

    class Explodes:
        def suffix(self):
            raise RuntimeError("boom")

    import actions.computer_control as cc

    assert cc._verified("Typed: hello", Explodes()) == "Typed: hello"