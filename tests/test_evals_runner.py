"""
tests/test_evals_runner.py - The eval harness itself must be trustworthy.

AN EVAL THAT LIES IS WORSE THAN NO EVAL
----------------------------------------
The first version of this runner scored 8/17 while routing absolutely nothing.
Every `must_not_route` case passed for free, because nothing was ever routed,
and the report looked like a plausible score.

So most of these tests are not about the assistant. They are about the scorer.
A harness that cannot be fooled into a false green is the only thing that makes
the numbers it produces worth reading.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from evals.runner import (  # noqa: E402
    Case,
    Result,
    default_cases,
    format_report,
    reply_looks_like_a_refusal,
    run_all,
    run_case,
)


# ── the scorer must not be fooled ───────────────────────────────────────────

def test_a_router_that_routes_nothing_cannot_score(monkeypatch):
    """The exact failure that made this file worth writing.

    Every `must_not_route` case passes trivially when no tool is ever routed,
    so a broken router scores like a working one.
    """
    import evals.runner as runner

    monkeypatch.setattr(runner, "_dispatch", lambda p: (None, "no tool routed"))

    results = run_all([Case(prompt="x", must_not_route=("open_app",))])
    assert results[0].passed is False
    assert "nothing routed" in results[0].detail


def test_one_routed_case_is_enough_to_avoid_the_total_blackout_guard(monkeypatch):
    """Otherwise the guard would fire on a legitimate run where only one case
    routes, hiding every real result behind one false alarm."""
    import evals.runner as runner

    calls = {"n": 0}

    def fake(prompt):
        calls["n"] += 1
        return ("open_app", "ok") if calls["n"] == 1 else (None, "no tool")

    monkeypatch.setattr(runner, "_dispatch", fake)
    results = run_all([Case(prompt="a", must_route="open_app"),
                       Case(prompt="b", must_not_route=("open_app",))])
    assert "nothing routed" not in results[0].detail


def test_a_must_route_failure_is_reported_not_swallowed():
    r = run_case(Case(prompt="x", must_route="open_app", name="t"))
    if not r.passed:
        assert "expected route" in r.detail


def test_forbidden_text_actually_fails_the_case():
    """The honesty checks are the whole point; prove they bite."""
    import evals.runner as runner

    runner._dispatch = lambda p: ("open_app", "Opened Telegram.")

    try:
        r = run_case(Case(prompt="x", forbid_in_reply=("opened telegram",)))
        assert r.passed is False
        assert "must not contain" in r.detail
    finally:
        # restore the real one
        import importlib
        importlib.reload(runner)


def test_a_refusal_marker_is_recognised():
    for text in ("Unknown action: 'status'", "Could not open the window",
                 "FAILED: boom", "Not found"):
        assert reply_looks_like_a_refusal(text) is True, text


def test_an_ordinary_success_is_not_a_refusal():
    """False positives here would make every success look like a failure."""
    for text in ("Opened Notepad.", "Task completed successfully.",
                 "File created: index.html", "Here is the answer: 42"):
        assert reply_looks_like_a_refusal(text) is False, text


# ── the case set must be worth running ──────────────────────────────────────

def test_there_are_cases():
    cases = default_cases()
    assert len(cases) >= 10


def test_every_case_is_named():
    """An unnamed case shows a prompt in the report, which reads as noise."""
    for c in default_cases():
        assert c.name, f"unnamed case: {c.prompt!r}"


def test_every_case_is_tagged():
    for c in default_cases():
        assert c.tags, f"untagged case: {c.name}"


def test_the_honesty_cases_exist():
    """The four false-success bugs fixed today each have a case. That is the
    strongest claim this harness makes and it should not be quietly dropped."""
    honesty = [c for c in default_cases() if "honesty" in c.tags]
    assert len(honesty) >= 4, f"only {len(honesty)} honesty cases"


def test_known_gaps_are_labelled_not_hidden():
    """The guarantee is about the MECHANISM, not about gaps being open.

    This used to assert that the shipped set contains at least one known_gap,
    reasoning that "none recorded" meant "the router is perfect". That
    reasoning broke the moment two gaps were fixed - the best possible outcome
    - and the test failed to celebrate it.

    What must stay true is that a case marked known_gap is reported and
    excluded from the score. Asserted with a constructed case below, so it
    holds whether or not any gap is currently open.
    """
    gaps = [c for c in default_cases() if c.known_gap]
    for g in gaps:
        assert "gap" in g.tags, f"{g.name} is a gap but not tagged as one"


def test_an_open_gap_would_be_labelled_and_excluded_from_the_score():
    """Constructed rather than taken from the shipped set, so it keeps working
    after every gap is closed."""
    case = Case(prompt="anything", known_gap=True, tags=("routing", "gap"),
                name="a hypothetical open gap")
    assert "gap" in case.tags
    result = run_case(case)
    assert result.passed is True
    assert "not scored" in result.detail


def test_a_closed_case_is_scored_normally():
    """The counterpart. Without this the flag would be a way to quietly excuse
    anything, and a test asserting only the mechanism would not notice."""
    case = Case(prompt="open notepad", must_route="open_app",
                tags=("routing",), name="a real requirement")
    result = run_case(case)
    assert result.detail != "known gap - reported, not scored"
    assert result.passed is True


def test_a_known_gap_is_not_scored_but_is_reported(monkeypatch):
    import evals.runner as runner

    monkeypatch.setattr(runner, "_dispatch", lambda p: (None, "cloud"))
    r = run_case(Case(prompt="x", known_gap=True, name="a gap"))
    assert r.passed is True
    assert "not scored" in r.detail


# ── reporting ───────────────────────────────────────────────────────────────

def test_report_states_the_score():
    results = run_all([Case(prompt="a", must_route="open_app", name="one")])
    text = format_report(results)
    assert "passed" in text
    assert "one" in text


def test_report_lists_failures_with_their_reason():
    import evals.runner as runner
    monkey = pytest.MonkeyPatch()
    monkey.setattr(runner, "_dispatch", lambda p: (None, "no tool"))
    try:
        results = run_all([Case(prompt="a", must_route="open_app", name="broken")])
        text = format_report(results)
    finally:
        monkey.undo()
    assert "Failures" in text
    assert "broken" in text


def test_report_breaks_down_by_area():
    text = format_report(run_all([
        Case(prompt="a", must_route="x", tags=("routing",), name="one"),
        Case(prompt="b", must_not_route=("y",), tags=("routing",), name="two"),
    ]))
    assert "| Area | Passed | Total |" in text
    assert "routing" in text


# ── the real thing ──────────────────────────────────────────────────────────

def test_the_real_router_routes_a_real_launch():
    r = run_case(Case(prompt="open notepad", must_route="open_app",
                      tags=("routing",), name="launch"))
    assert r.passed, r.detail


def test_the_real_router_refuses_a_hindi_verb_as_an_app():
    """The garbage-token guard, end to end."""
    r = run_case(Case(prompt="kro", must_not_route=("open_app",),
                      tags=("refusal",), name="not an app name"))
    assert r.passed, r.detail


def test_the_real_router_does_not_claim_an_uninstalled_app_opened():
    """Telegram is not installed on this machine, so anything but a refusal
    here is a regression of the bug this suite was written to prevent."""
    r = run_case(Case(prompt="open telegram",
                      forbid_in_reply=("opened telegram",),
                      tags=("honesty",), name="no false success"))
    assert r.passed, r.detail


def test_a_case_does_not_leak_conversation_state_into_the_next():
    """The leak this harness actually had.

    Disposing one case left `last_app = notepad` in core.context_buffer, and
    the NEXT test's router - a fresh NeedleToolRouter - then resolved "use
    band kro" to notepad and routed it to open_app, failing a regression test
    about Hindi prose. Two router instances sharing one global conversation
    memory is the mechanism.

    Correct inside a conversation, wrong for an eval: single-turn routing has
    to be measured without the previous turn's pronouns to resolve against.
    """
    import core.context_buffer as cb
    from core.edge_router import NeedleToolRouter

    run_case(Case(prompt="open notepad", must_route="open_app", name="launch"))

    buf = getattr(cb, "_GLOBAL_CONTEXT", None)
    if buf is not None:
        assert getattr(buf, "last_app", "") in ("", None), (
            f"context buffer still remembers {buf.last_app!r} after a case"
        )

    fresh = NeedleToolRouter()
    for utterance in ("main nahi kiya hu use band kro",
                      "timers aur tasks kya hain main nahi kiya hu use band kro to"):
        result = fresh.classify_tool_intent(utterance)
        if result is not None:
            assert result[0] != "open_app", (
                f"{utterance!r} leaked a previous case into this one: {result!r}"
            )


def test_redaction_is_reachable_by_voice():
    """Added after the eval found it was not: the actions existed on
    privacy_ctl and could only be called directly, so a control nobody can
    reach by asking is not a control."""
    r = run_case(Case(prompt="redaction on", must_route="privacy_ctl",
                      tags=("safety",), name="turn redaction on"))
    assert r.passed, r.detail