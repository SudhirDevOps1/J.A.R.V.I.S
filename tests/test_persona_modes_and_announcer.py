"""
tests/test_persona_modes_and_announcer.py — persona behaviour and announcements.

WHY THESE EXIST
---------------
Both come from a real session on the user's own machine, not from a spec.

The persona problem: the assistant was asked "tum kaun ho" and answered with
affection and a disclaimer instead of the question. It was asked to check an
HTML file it had just written and insisted the file was fine while the user
said it was empty. The companion prompt already contained a "do the task
first" rule and it still lost, which is the finding that shaped the design
below: the rule that matters most has to be the rule that appears last.

The announcement problem: "task ya timer start ho to bole" produced no speech
at all, only a log line invisible when the window is closed. The completion
announcement existed but was the hardcoded string "Alert sir! X ka time ho
gaya hai", which ignored the configured name, gender and language.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from core import announcer  # noqa: E402
from core.persona_manager import (  # noqa: E402
    AVAILABLE_PERSONAS,
    _PERSONA_PROMPTS,
    build_persona_system_prompt,
    get_task_first_directive,
)


# ── the professional mode ───────────────────────────────────────────────────

def test_professional_mode_exists():
    assert "professional" in AVAILABLE_PERSONAS
    assert "professional" in _PERSONA_PROMPTS


def test_professional_is_described_as_the_default():
    assert "default" in AVAILABLE_PERSONAS["professional"]["desc"].lower()


def test_professional_prompt_forbids_romantic_padding():
    """The reason it exists. Shipping this project with a flirty default makes
    it read as a toy."""
    body = _PERSONA_PROMPTS["professional"].lower()
    assert "no emojis" in body
    assert "flirtation" in body


def test_professional_prompt_states_task_first():
    assert "task first" in _PERSONA_PROMPTS["professional"].lower()


def test_every_mode_still_compiles():
    for mode in AVAILABLE_PERSONAS:
        prompt = build_persona_system_prompt("X", mode=mode)
        assert prompt.strip(), mode


# ── task first, in every mode ───────────────────────────────────────────────

def test_task_first_directive_exists():
    assert get_task_first_directive().strip()


@pytest.mark.parametrize("mode", sorted(AVAILABLE_PERSONAS))
def test_task_first_is_present_in_every_mode(mode):
    """The companion mode already had a task-first line and still lost to the
    persona. Proximity decides what a model obeys."""
    assert "ABSOLUTE PRIORITY" in build_persona_system_prompt("X", mode=mode)


@pytest.mark.parametrize("mode", sorted(AVAILABLE_PERSONAS))
def test_task_first_comes_last(mode):
    """Placed last on purpose. A rule buried in the middle of a long persona
    is outweighed by whatever is nearest the end of the prompt."""
    prompt = build_persona_system_prompt("X", mode=mode)
    assert prompt.rstrip().endswith("confirmed it.")


def test_task_first_says_the_question_gets_answered():
    text = get_task_first_directive().lower()
    assert "answer the question" in text


def test_task_first_tells_it_to_believe_the_user_when_you_are_wrong():
    """'Usmein kuch nahi hai' means go and look again, not argue."""
    assert "re-check" in get_task_first_directive().lower()


def test_task_first_forbids_claiming_unverified_success():
    assert "confirmed it" in get_task_first_directive().lower()


# ── mode switching ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("utterance,expected", [
    ("professional mode", "professional"),
    ("pro mode lagao", "professional"),
    ("serious mode", "professional"),
    ("gf mode", "companion"),
    ("girlfriend mode", "companion"),
    ("companion mode", "companion"),
    ("teacher mode", "teacher"),
    ("devops mode", "devops"),
    ("jarvis mode", "jarvis"),
])
def test_mode_switching_phrases_resolve(utterance, expected):
    """These are the phrasings the user actually types."""
    from core.edge_router import PERSONA_KEYWORD_RE, map_profile_word
    m = PERSONA_KEYWORD_RE.search(utterance)
    assert m is not None, f"{utterance!r} is not recognised as a mode switch"
    assert map_profile_word(m.group(1)) == expected, utterance


def test_every_mapped_target_is_a_registered_persona():
    """The bug this table exists to fix.

    'work mode' mapped to a persona named 'work' and 'gaming mode' to one named
    'gaming'. Neither exists in AVAILABLE_PERSONAS, so the phrase switched
    nothing and the user was told nothing was wrong.
    """
    from core.edge_router import PERSONA_MODE_MAP
    for word, target in PERSONA_MODE_MAP.items():
        assert target in AVAILABLE_PERSONAS, (
            f"{word!r} maps to persona {target!r}, which is not registered"
        )


def test_work_mode_resolves_to_professional():
    from core.edge_router import map_profile_word
    assert map_profile_word("work") == "professional"


def test_unknown_word_falls_back_to_a_real_persona():
    from core.edge_router import map_profile_word
    assert map_profile_word("something-else") in AVAILABLE_PERSONAS


def test_mapping_is_case_and_space_insensitive():
    from core.edge_router import map_profile_word
    assert map_profile_word("  GF  ") == "companion"
    assert map_profile_word("Teacher") == "teacher"


# ── announcements ───────────────────────────────────────────────────────────

def test_timer_set_says_something():
    out = announcer.timer_set_text("Paani", "5 minutes", user_text="pani pin hai")
    assert out
    assert "Panai" in out or "Paani" in out


def test_timer_set_is_short():
    """It plays at the moment of setting. A paragraph would be unusable."""
    assert len(announcer.timer_set_text("x", "5 minutes")) < 160


def test_timer_done_mentions_the_message():
    out = announcer.timer_done_text("Paani", user_text="x")
    assert "Paani" in out


def test_timer_done_does_not_hardcode_sir(monkeypatch):
    """It used to be literally 'Alert sir! X ka time ho gaa hai'.

    A user running the assistant in English, or with a different configured
    name, was still addressed as 'sir'.
    """
    import memory.config_manager as cm
    monkeypatch.setattr(cm, "get_user_name", lambda: "Anita")
    monkeypatch.setattr(cm, "get_preferred_language", lambda: "english")
    out = announcer.timer_done_text("Tea")
    assert "sir" not in out.lower()
    assert "Anita" in out


def test_timer_done_uses_the_configured_name(monkeypatch):
    import memory.config_manager as cm
    monkeypatch.setattr(cm, "get_user_name", lambda: "Anita")
    monkeypatch.setattr(cm, "get_preferred_language", lambda: "english")
    assert "Anita" in announcer.timer_done_text("Tea")


def test_language_follows_devanagari(monkeypatch):
    """Actual Devanagari input. Roman-script Hinglish is ambiguous with
    English, so the script is the reliable signal."""
    import memory.config_manager as cm
    monkeypatch.setattr(cm, "get_user_name", lambda: "")
    out = announcer.timer_done_text("Paani", user_text="paani pii hai पानी")
    assert "time ho gaya" in out


def test_plain_english_user_text_gives_english(monkeypatch):
    """Roman-script Hinglish is ambiguous, but actual user text beats a
    guess: someone typing English words gets English."""
    import memory.config_manager as cm
    monkeypatch.setattr(cm, "get_user_name", lambda: "")
    monkeypatch.setattr(cm, "get_preferred_language", lambda: "hinglish")
    out = announcer.timer_done_text("Tea", user_text="remind me to drink tea")
    assert "time ho gaya" not in out
    assert "finished" in out


def test_no_user_text_falls_back_to_the_setting(monkeypatch):
    import memory.config_manager as cm
    monkeypatch.setattr(cm, "get_user_name", lambda: "")
    monkeypatch.setattr(cm, "get_preferred_language", lambda: "hinglish")
    assert "time ho gaya" in announcer.timer_done_text("Paani")


def test_announce_with_no_speak_hook_is_a_noop():
    """The scheduler has already succeeded by this point. A missing audio
    device must not raise into the reminder path."""
    assert announcer.announce("hello", speak=None) is False


def test_announce_actually_speaks():
    said = []
    announcer.announce("hello", speak=said.append)
    import time
    for _ in range(50):
        if said:
            break
        time.sleep(0.02)
    assert said == ["hello"]


def test_announce_survives_a_broken_speak_hook():
    """A speech failure must not lose the reminder that was already set."""
    def _boom(_text):
        raise RuntimeError("no audio device")

    assert announcer.announce("hello", speak=_boom) is True


def test_announce_ignores_empty_text():
    assert announcer.announce("", speak=lambda t: None) is False
    assert announcer.announce("   ", speak=lambda t: None) is False


def test_announce_logs_when_a_log_hook_is_given():
    logged = []
    announcer.announce("hi", speak=None, log=logged.append)
    assert logged == ["hi"]


# ── wiring ──────────────────────────────────────────────────────────────────

def test_reminder_module_announces_on_set():
    """The explicit request: 'task ya timer start ho to bole'."""
    src = (_ROOT / "actions" / "reminder.py").read_text(encoding="utf-8-sig")
    assert "timer_set_text" in src
    assert "announce" in src


def test_timer_alarm_no_longer_hardcodes_sir():
    """The completion line used to be built inline as
    'Alert sir! {msg} ka time ho gaya hai', ignoring the configured name,
    gender and language.

    Asserted behaviourally rather than by grepping for the string: the string
    survives in the comments that explain why it was replaced, so a grep
    matches the documentation of the fix and passes for the wrong reason.
    """
    src = (_ROOT / "ui.py").read_text(encoding="utf-8-sig")
    assert "timer_done_text" in src, "the timer alarm must go through announcer"

    # The inline construction would be an f-string literal containing 'sir'.
    inline = [
        ln for ln in src.splitlines()
        if "Alert sir" in ln and not ln.strip().startswith("#")
    ]
    assert not inline, f"hardcoded alarm sentence still in code: {inline}"


def test_timer_alarm_respects_the_configured_name(monkeypatch):
    """End to end through the real helper, for a user who is not 'sir'."""
    import memory.config_manager as cm
    monkeypatch.setattr(cm, "get_user_name", lambda: "Anita")
    monkeypatch.setattr(cm, "get_preferred_language", lambda: "english")
    out = announcer.timer_done_text("Tea")
    assert "sir" not in out.lower()
    assert "Anita" in out