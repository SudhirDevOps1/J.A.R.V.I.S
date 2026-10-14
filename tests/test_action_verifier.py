"""
tests/test_action_verifier.py - An action is not "done" until something proves it.

WHY
---
Four bugs on this project, all found on the user's own machine, all the same
shape:

    _process_appeared   "Opened Notepad."         nothing opened
    todo_agent          "completed successfully"  every step refused
    _launch_linux       "Opened Telegram."        exit status discarded
    open_app verifier   "Opened Notepad."         empty process name matched

Four coincidences is not a coincidence. This module is the missing layer, and
these tests are what stops it quietly rotting back into a bool.

THE THREE-STATE ANSWER IS THE WHOLE POINT
-----------------------------------------
OK, FAILED, UNKNOWN. Not a bool. UNKNOWN means "this machine could not tell",
and it must never be laundered into either answer:

    * collapsing UNKNOWN into FAILED makes the assistant refuse to act
    * collapsing UNKNOWN into OK is the exact bug this was written to end

So most of these tests are about which state came back, not about what a
caller does with it.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from core.action_verifier import (  # noqa: E402
    FAILED,
    OK,
    UNKNOWN,
    Verification,
    with_retry,
    wait_until,
)


# ── the three states ────────────────────────────────────────────────────────

def test_verification_has_three_states_not_two():
    assert {OK, FAILED, UNKNOWN} == {"ok", "failed", "unknown"}


def test_unknown_is_not_success():
    """The single most important line in the module.

    An unverified action reported as verified is how this project shipped four
    false confirmations."""
    assert Verification(UNKNOWN, "could not tell").ok is False
    assert Verification(UNKNOWN, "could not tell").verified is False


def test_unknown_is_not_failure_either():
    """Otherwise the assistant becomes unable to act on any machine where
    verification is unavailable - a regression in capability, not honesty."""
    assert Verification(UNKNOWN, "could not tell").state != FAILED


def test_ok_is_the_only_state_that_counts_as_verified():
    assert Verification(OK, "proven").verified is True


def test_suffix_says_which_it_was():
    assert "verified:" in Verification(OK, "screen changed").suffix()
    assert "NOT VERIFIED" in Verification(FAILED, "nothing moved").suffix()
    # UNKNOWN must not read as a quiet success.
    assert "unverified" in Verification(UNKNOWN, "no baseline").suffix()


def test_an_unknown_result_is_visibly_not_a_claim():
    """A caller that only ever prints the action message would hide UNKNOWN
    entirely, so it has to be part of the message."""
    v = Verification(UNKNOWN, "no UIA here")
    assert "unverified" in v.suffix().lower()
    assert "verified:" not in v.suffix().lower().replace("unverified:", "")


# ── verification must never raise ───────────────────────────────────────────

def test_module_never_raises_on_junk():
    """Verification failing must not be the reason an action fails. That would
    make the assistant less capable than before this module existed."""
    from core import action_verifier as av

    junk = [None, "", 0, -1, [], {}, object()]
    for name in ("verify_click", "verify_press", "verify_typed",
                 "wait_for_window", "wait_for_process", "wait_for_file"):
        fn = getattr(av, name)
        for value in junk:
            try:
                if name == "verify_click":
                    fn(av.Snapshot(0, "", 0, "", ""), value, value)
                elif name == "verify_typed":
                    fn(av.Snapshot(0, "", 0, "", ""), str(value))
                elif name == "verify_press":
                    fn(av.Snapshot(0, "", 0, "", ""), str(value))
                else:
                    fn(str(value), timeout=0.2)
            except Exception as e:          # pragma: no cover - the assertion
                pytest.fail(f"{name}({value!r}) raised {e!r}")


def test_capabilities_never_claims_cloud_vision():
    """The cloud path exists elsewhere in this codebase and uploads the whole
    screen. It must never appear as verification."""
    from core.action_verifier import capabilities
    caps = capabilities()
    assert caps["cloud_vision_used"] is False
    assert set(caps) >= {"uia_structured", "local_pixels", "window_state"}


def test_capabilities_are_booleans():
    from core.action_verifier import capabilities
    for key, value in capabilities().items():
        if key == "platform":
            assert isinstance(value, str)
        else:
            assert isinstance(value, bool), f"{key} is {value!r}"


# ── wait_until replaces sleeping and hoping ─────────────────────────────────

def test_wait_until_returns_immediately_when_already_true():
    start = time.time()
    v = wait_until(lambda: True, timeout=5.0)
    assert v.state == OK
    assert time.time() - start < 1.0, "must not sleep when the condition holds"


def test_wait_until_fails_on_timeout_with_the_budget_honoured():
    v = wait_until(lambda: False, timeout=0.4, interval=0.05)
    assert v.state == FAILED
    assert "0.4" in v.evidence


def test_wait_until_becomes_true_partway_through():
    """The case time.sleep() cannot handle: the thing appears, but late."""
    box = {"t": time.time()}

    def appears():
        return time.time() - box["t"] > 0.3

    v = wait_until(appears, timeout=3.0, interval=0.05,
                   description="window finally appeared")
    assert v.state == OK
    assert v.detail["polls"] > 1, "should have taken more than one poll"


def test_wait_until_reports_a_raising_predicate_as_failure_not_crash():
    def boom():
        raise RuntimeError("window handle died")

    v = wait_until(boom, timeout=0.2, interval=0.05)
    assert v.state == FAILED
    assert "window handle died" in v.evidence


def test_wait_until_zero_timeout_is_not_a_hang():
    start = time.time()
    v = wait_until(lambda: False, timeout=0.0)
    assert v.state == FAILED
    assert time.time() - start < 1.0


# ── retry: the rule that matters most ───────────────────────────────────────

def test_retry_stops_immediately_when_verification_is_ok():
    calls = []

    def action(n):
        calls.append(n)
        return "done"

    value, v = with_retry(action, lambda r: Verification(OK, "proven"))
    assert calls == [1], "must not retry something that already worked"
    assert v.state == OK


def test_retry_does_not_fire_again_on_unknown():
    """Firing the same keystrokes twice at something that may have already
    succeeded is how a half-typed field becomes a double-typed one.

    UNKNOWN means the machine could not tell. Retrying anyway risks a second,
    unwanted effect. So it does not."""
    calls = []

    def action(n):
        calls.append(n)
        return "typed"

    value, v = with_retry(action, lambda r: Verification(UNKNOWN, "could not read"))
    assert calls == [1], (
        "an unknown result must not be retried - the action may already have "
        "happened"
    )
    assert v.state == UNKNOWN


def test_retry_does_fire_again_on_a_genuine_failure():
    calls = []

    def action(n):
        calls.append(n)
        return "clicked"

    value, v = with_retry(action, lambda r: Verification(FAILED, "nothing moved"),
                          attempts=3, delay=0.01)
    assert calls == [1, 2, 3], "a proven failure is worth another attempt"
    assert v.state == FAILED


def test_retry_stops_as_soon_as_it_succeeds():
    calls = []
    outcomes = [FAILED, FAILED, OK]

    def action(n):
        calls.append(n)
        return n

    value, v = with_retry(action, lambda r: (Verification(OK, "fine")
                                              if r == 3 else Verification(FAILED, "no")),
                          attempts=5, delay=0.01)
    assert calls == [1, 2, 3], "must not keep going after it worked"
    assert v.state == OK


def test_retry_survives_an_action_that_raises():
    calls = []

    def action(n):
        calls.append(n)
        raise RuntimeError("device locked")

    value, v = with_retry(action, lambda r: Verification(OK, "fine"),
                          attempts=2, delay=0.01)
    assert calls == [1, 2]
    assert v.state == FAILED
    assert "device locked" in v.evidence


def test_retry_survives_a_verifier_that_raises():
    """A broken verifier must not turn a working action into a failure loop."""
    calls = []

    def action(n):
        calls.append(n)
        return "ok"

    def bad_verify(_):
        raise RuntimeError("verifier exploded")

    value, v = with_retry(action, bad_verify, attempts=3, delay=0.01)
    assert calls == [1], "an unknown verification must not be retried"
    assert v.state == UNKNOWN


def test_retry_backs_off_rather_than_hammering():
    delays = []
    real_sleep = time.sleep

    def fake_sleep(d):
        delays.append(d)
        return real_sleep(0)

    import core.action_verifier as av
    original = av.time.sleep
    av.time.sleep = fake_sleep
    try:
        with_retry(lambda n: n, lambda r: Verification(FAILED, "no"),
                   attempts=4, delay=0.1, backoff=2.0)
    finally:
        av.time.sleep = original

    assert delays == [0.1, 0.2, 0.4], f"expected geometric backoff, got {delays}"


# ── verification of a real action path ──────────────────────────────────────

def test_typed_verification_reads_the_control_back(monkeypatch):
    """The strong check: read what the application actually received instead
    of assuming the keystrokes arrived."""
    from core import action_verifier as av

    monkeypatch.setattr(av, "read_focused_text", lambda: "hello from the field")
    snap = av.Snapshot(0, "", 0, "", "")
    v = av.verify_typed(snap, "hello")
    assert v.state == OK
    assert v.detail["read_back"] is True


def test_typed_verification_fails_when_the_text_did_not_arrive(monkeypatch):
    from core import action_verifier as av

    monkeypatch.setattr(av, "read_focused_text", lambda: "something else")
    v = av.verify_typed(av.Snapshot(0, "", 0, "", ""), "hello")
    assert v.state == FAILED, (
        "this is the check that would have caught the Notepad typing bug"
    )


def test_typed_verification_matches_on_the_tail(monkeypatch):
    """A field holds earlier text plus what was just typed. Matching the whole
    string would fail every time you type into a field that already had
    something in it."""
    from core import action_verifier as av

    monkeypatch.setattr(av, "read_focused_text", lambda: "existing text and then hello")
    v = av.verify_typed(av.Snapshot(0, "", 0, "", ""), "hello")
    assert v.state == OK


def test_typed_verification_is_unknown_not_failed_when_it_cannot_read(monkeypatch):
    from core import action_verifier as av

    monkeypatch.setattr(av, "read_focused_text", lambda: None)
    v = av.verify_typed(av.Snapshot(0, "", 0, "", ""), "hello")
    assert v.state == UNKNOWN, (
        "an unreadable control means we do not know, not that it failed"
    )


def test_typing_nothing_cannot_be_verified_and_says_so():
    from core import action_verifier as av

    v = av.verify_typed(av.Snapshot(0, "", 0, "", ""), "")
    assert v.state == UNKNOWN


def test_click_verification_needs_a_baseline_to_compare_against():
    """Without a 'before' there is nothing to compare, and that is unknown,
    not a pass."""
    from core import action_verifier as av

    v = av.verify_click(av.Snapshot(0, "", 0, "", ""), 5, 5)
    assert v.state in (UNKNOWN, FAILED)
    assert v.state != OK


def test_snapshot_is_safe_to_take_with_nothing_running():
    from core.action_verifier import snapshot
    s = snapshot()
    assert isinstance(s.pid_count, int)
    assert isinstance(s.fg_title, str)