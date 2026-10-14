r"""
tests/test_shutdown_safety.py - Closing an app must never shut down the computer.

(Raw docstring: it quotes the old regex, which contains \s.)

THE BUG, AND WHY IT MATTERS MORE THAN THE OTHERS FIXED TODAY
-----------------------------------------------------------
Most of today's bugs were false confirmations: something claimed success it had
not achieved. This one is the inverse and is worse, because there is no undo.

    'chrome band kar do'  ->  computer_settings {'action': 'shutdown'}

"band kar do" means close it. The user was talking about chrome. The computer
would have shut down.

Two independent patterns caused it, and both had the bare phrase "band kar do"
with no subject:

    if re.search(r"\b(shutdown|pc\s*band|computer\s*band|band\s*karo\s*pc|
                   band\s*kar\s*do)\b", clean)

    if any(w in clean for w in ("pc band", "computer band", "pc off",
                                "band kar do", ...)):

Pre-existing - confirmed by stashing the delete-routing change and re-running.
Not caused by anything done today, and not caught by any test until now.

WHY THE TEST IS WORTH WRITING
-----------------------------
A destructive action reached by an ordinary sentence is the worst class of
routing bug there is, and nothing in the suite covered it. The fix requires an
explicit system subject; these tests pin both directions - closing still works,
power still works, and the two can no longer be confused.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


@pytest.fixture()
def dispatcher():
    from core import reflex_policy
    reflex_policy.set_enabled(False)
    from core.edge_router import get_tri_tier_dispatcher
    return get_tri_tier_dispatcher()


def _tool(dispatcher, prompt):
    return dispatcher.route(prompt).get("tool")


def _is_shutdown(tool) -> bool:
    return bool(tool) and tool[0] == "computer_settings" and \
        tool[1].get("action") in ("shutdown", "restart", "sleep")


# ── the regression: closing an app is not a power command ───────────────────

@pytest.mark.parametrize("app", ["chrome", "brave", "notepad", "word",
                                 "telegram", "firefox", "explorer"])
def test_closing_an_app_never_shuts_down_the_machine(dispatcher, app):
    tool = _tool(dispatcher, f"{app} band kar do")
    assert not _is_shutdown(tool), (
        f"'{app} band kar do' (close {app}) was routed to {tool!r}"
    )


@pytest.mark.parametrize("phrase", [
    "band kar do", "band kardo", "band karo", "band kar dijiye",
])
def test_a_bare_close_is_not_a_power_command(dispatcher, phrase):
    tool = _tool(dispatcher, phrase)
    assert not _is_shutdown(tool), f"{phrase!r} became {tool!r}"


def test_the_exact_failing_sentence_now_closes_chrome(dispatcher):
    """Not merely "not a shutdown" - it should do the useful thing."""
    tool = _tool(dispatcher, "chrome band kar do")
    assert tool is not None, "the request was dropped entirely"
    assert tool[0] == "open_app", f"expected an app close, got {tool!r}"
    assert tool[1]["action"] == "close"
    assert "chrome" in str(tool[1].get("name", "")).lower()


# ── power commands must still work ──────────────────────────────────────────

@pytest.mark.parametrize("prompt", [
    "pc band karo",
    "computer band kar do",
    "laptop band kar do",
    "system band karo",
    "shutdown karo",
])
def test_an_explicit_system_subject_still_shuts_down(dispatcher, prompt):
    """Guarding a destructive action by removing it is not the fix."""
    tool = _tool(dispatcher, prompt)
    assert _is_shutdown(tool), f"{prompt!r} no longer reaches a power command: {tool!r}"


@pytest.mark.parametrize("prompt", ["restart karo", "reboot karo", "dobara chalu"])
def test_restart_is_unaffected(dispatcher, prompt):
    tool = _tool(dispatcher, prompt)
    assert tool is not None
    assert tool[0] == "computer_settings", f"{prompt!r} -> {tool!r}"


# ── no other destructive route is reachable by accident ─────────────────────

def test_closing_still_works_for_the_common_wordings(dispatcher):
    for prompt in ("notepad band karo", "chrome band karo",
                   "brave band kardo", "notepad band kar do"):
        tool = _tool(dispatcher, prompt)
        assert tool is not None and tool[0] == "open_app", (
            f"{prompt!r} should close an app, got {tool!r}"
        )