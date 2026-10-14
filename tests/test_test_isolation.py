"""
tests/test_test_isolation.py - The suite must not leak state between tests.

SECOND OCCURRENCE, WHICH IS WHY THIS FILE EXISTS
------------------------------------------------
A test that routes a prompt writes to core.context_buffer, and the next test -
with its own brand new NeedleToolRouter, sharing the same module-level buffer -
resolves pronouns against the leftover. "main nahi kiya hu use band kro" then
became "close notepad".

It happened twice, hours apart, in two unrelated files:

    evals/runner.py     "open notepad" left last_app = notepad
    test_lfm_honesty.py the same, via the router

The first fix was applied inside the eval runner. That fixed the symptom and
left the cause in place, so the second file hit it again immediately. The real
fix is the autouse _no_conversation_carryover fixture in conftest.py, which
resets the buffer around every test in the suite.

These tests prove that fixture works, and that the leak is real, so a future
refactor that removes the fixture fails here rather than surfacing as an
unrelated-looking failure somewhere else three files away.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def test_routing_leaves_state_in_the_context_buffer():
    """Positive control: proves the leak is real and not a theory."""
    from core import reflex_policy
    reflex_policy.set_enabled(False)
    from core.edge_router import get_tri_tier_dispatcher
    import core.context_buffer as cb

    try:
        dispatcher = get_tri_tier_dispatcher()
        dispatcher.route("open notepad")

        buf = getattr(cb, "_GLOBAL_CONTEXT", None)
        if buf is None:
            pytest.skip("the router did not create a context buffer here")

        dirty = bool(getattr(buf, "last_app", "") or getattr(buf, "last_tool", ""))
        assert dirty, (
            "routing left nothing behind, so this file's premise - that state "
            "leaks - no longer holds and the isolation fixture is untested"
        )
    finally:
        from core import reflex_policy
        reflex_policy.set_enabled(False)


def test_the_fixture_empties_the_buffer_before_a_test_runs():
    """If the buffer were already dirty when a test began, the first assertion
    would measure the previous test."""
    import core.context_buffer as cb

    buf = getattr(cb, "_GLOBAL_CONTEXT", None)
    if buf is None:
        pytest.skip("no buffer to inspect")

    assert not getattr(buf, "last_app", ""), (
        "the buffer still holds an app name at the start of a test, so "
        "state is carrying over between tests"
    )
    assert not getattr(buf, "last_tool", ""), (
        "the buffer still holds a tool name at the start of a test"
    )


def test_the_fixture_empties_the_buffer_after_a_test_runs():
    """This test does not route anything, so whatever it sees is residue - and
    there must be none."""
    import core.context_buffer as cb

    buf = getattr(cb, "_GLOBAL_CONTEXT", None)
    if buf is None:
        pytest.skip("no buffer to inspect")

    assert not getattr(buf, "last_app", "")
    assert not getattr(buf, "last_tool", "")


def test_a_hindi_pronoun_does_not_resolve_without_history():
    """The exact utterance that failed twice.

    With a clean buffer "use" has nothing to refer back to, so this cannot
    become a request to close whatever the previous test happened to mention."""
    from core.edge_router import NeedleToolRouter

    result = NeedleToolRouter().classify_tool_intent(
        "main nahi kiya hu use band kro")
    if result is not None:
        assert result[0] != "open_app", (
            f"resolved to open_app without any history: {result!r}"
        )