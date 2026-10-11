"""
tests/test_phase4_router_and_persona.py — Regression tests for bugs found by
running the real assistant.

These came out of an actual session log, not from reading code:

  1. The user said "timers aur tasks kya hain main nahi kiya hu use band kro
     to" and the router fired `open_app close "hu use"` — it tried to close an
     application called "hu use". The open/close reflexes take a 1-2 word token
     run as the app name, which is far too permissive for natural Hinglish:
     conjunctions ("aur"), pronouns ("hu", "use", "main") and subject nouns
     ("tasks") all became application names.

  2. The companion persona answered a routine correction with "gussa kya ho
     raha hai jaan?" and then announced it was creating a file "abhi ek second
     me". The persona prompt had no rule making the task take priority over the
     roleplay, so it derailed a concrete request.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


@pytest.fixture(scope="module")
def router():
    from core.edge_router import NeedleToolRouter
    return NeedleToolRouter()


# ── the exact failure from the session log ──────────────────────────────────

@pytest.mark.parametrize("utterance", [
    "timers aur tasks kya hain main nahi kiya hu use band kro to",
    "main nahi kiya hu use band kro",
    "timers aur tasks band karo",
    "sab tasks band karo",
    "meri files band karo",
])
def test_hinglish_prose_never_becomes_an_app_name(router, utterance):
    """Regression: these all dispatched open_app with a nonsense name.

    "timers aur tasks band karo" produced app_name="aur tasks" and JARVIS
    announced it was closing an app called "aur tasks".
    """
    result = router.classify_tool_intent(utterance)
    if result is not None:
        tool, args = result
        assert tool != "open_app", (
            f"{utterance!r} should not route to open_app, got {result!r}"
        )


# ── real app names must keep working ────────────────────────────────────────

@pytest.mark.parametrize("utterance,expected_action,expected_name", [
    ("close notepad",        "close", "notepad"),
    ("notepad band karo",    "close", "notepad"),
    ("kill word",            "close", "word"),
    ("brave band karo",      "close", "brave"),
    ("close spotify",        "close", "spotify"),
    ("open chrome",          "open",  "chrome"),
    ("chrome kholo",         "open",  "chrome"),
    ("open calculator",      "open",  "calculator"),
])
def test_real_app_names_still_route(router, utterance, expected_action, expected_name):
    """The filler guard must not be so aggressive that it breaks normal use."""
    result = router.classify_tool_intent(utterance)
    assert result is not None, f"{utterance!r} stopped routing (over-aggressive guard)"
    tool, args = result
    assert tool == "open_app", f"{utterance!r} -> {tool!r}"
    assert args.get("action") == expected_action
    assert args.get("name") == expected_name


# ── the guard itself ────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "aur tasks", "hu use", "main", "aur", "kuch", "sab",
    "meri files", "sab tasks", "timers", "aap", "mujhe", "wo",
])
def test_is_filler_phrase_accepts_non_app_words(text):
    from core.edge_router import _is_filler_phrase
    assert _is_filler_phrase(text) is True


@pytest.mark.parametrize("text", [
    "notepad", "chrome", "vs code", "calculator", "spotify", "brave",
    "android studio", "visual studio code",
])
def test_is_filler_phrase_rejects_real_apps(text):
    from core.edge_router import _is_filler_phrase
    assert _is_filler_phrase(text) is False


def test_filler_guard_handles_degenerate_input():
    from core.edge_router import _is_filler_phrase
    assert _is_filler_phrase("") is True
    assert _is_filler_phrase(None) is True
    assert _is_filler_phrase("!!!") is True


# ── persona: task-first, no derailment ──────────────────────────────────────

def test_companion_prompt_requires_task_first():
    """Regression: the persona had no rule making the task take priority, so a
    routine correction drew "gussa kya ho raha hai" instead of action."""
    from core.persona_manager import _PERSONA_PROMPTS
    prompt = _PERSONA_PROMPTS["companion"].lower()
    assert "task first" in prompt or "do the task first" in prompt
    assert "never a blocker" in prompt
    # The instruction that caused the observed behaviour must not survive as
    # ACTUAL guidance. It survives inside a "never ..." prohibition, so assert
    # every occurrence is negated rather than searching for absence of the text.
    lines = [ln.strip() for ln in prompt.splitlines() if "mera haq hai" in ln]
    assert lines, "expected the prohibition to reference the old phrasing"
    for ln in lines:
        assert any(neg in ln for neg in ("never", "no ", "not ")), (
            f"'{ln}' uses the old possessive phrasing as live guidance"
        )


def test_companion_prompt_forbids_stalling():
    """The log showed 'bas ek seCONd me sab ho jayega' followed by a re-ask.
    An already-clear request must not trigger a follow-up question."""
    from core.persona_manager import _PERSONA_PROMPTS
    prompt = _PERSONA_PROMPTS["companion"].lower()
    assert "follow-up" in prompt or "follow up" in prompt
    assert "honestly" in prompt


def test_persona_prompts_all_parse():
    """A syntax error in any persona string would break session start."""
    from core import persona_manager
    for name, prompt in persona_manager._PERSONA_PROMPTS.items():
        assert isinstance(prompt, str) and prompt.strip(), name


def test_companion_prompt_still_warm():
    """The tone-down must not have removed the warmth the user actually wants —
    this is a companion persona, not a bot."""
    from core.persona_manager import _PERSONA_PROMPTS
    prompt = _PERSONA_PROMPTS["companion"].lower()
    assert "jealous" in prompt or "nakhre" in prompt
    assert "feminine" in prompt or "करती" in prompt


# ── other personas unaffected ───────────────────────────────────────────────

@pytest.mark.parametrize("name", ["devops", "guru", "teacher", "jarvis"])
def test_other_personas_unchanged(name):
    from core.persona_manager import AVAILABLE_PERSONAS, _PERSONA_PROMPTS
    if name not in _PERSONA_PROMPTS:
        pytest.skip(f"{name} not defined")
    assert name in AVAILABLE_PERSONAS
    assert _PERSONA_PROMPTS[name].strip()