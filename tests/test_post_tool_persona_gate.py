"""
tests/test_post_tool_persona_gate.py - A reply must react to what just happened.

WHAT WAS OBSERVED
-----------------
Real session, after the verification layer landed:

    You: notepad mein hy type kro
    [Computer] type
    maya: Arey Jaan, main toh kabki tumhare saath hoon! Kya hua, kuch
          specific chahiye ya bas pyaar jatana hai?

The typing worked. The tool returned. The reply then behaved as if nothing had
happened and asked a question the user never implied.

WHY A TASK-FIRST RULE DID NOT PREVENT IT
-----------------------------------------
The companion prompt already said to do the task first. But it sat as section
11 of 79, and the three sections before it - which outnumber it several times
over - tell the model to be maximally romantic and react dramatically to his
return. Proximity decides what a model obeys, so the rule that matters most was
the one furthest from the eyes.

The rule that was missing is narrower than "task first": what to do in the turn
AFTER a tool returns. That is now the last block of every persona.

WHY ASSERT ON PROMPT TEXT AT ALL
---------------------------------
Because the alternative is unmeasurable. Whether a model obeys a rule cannot be
tested offline, so what can be tested is that the rule EXISTS, that it is LAST
in every persona, and that it names the specific failure. That is not as strong
as a behavioural test, but it is far better than a rule nobody checks for.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from core.persona_manager import _PERSONA_PROMPTS  # noqa: E402

GATE_MARKER = "AFTER A TOOL RETURNS"


def _prompt_for(name: str) -> str:
    from core.persona_manager import AVAILABLE_PERSONAS
    key = name.lower().replace(" ", "")
    if key in _PERSONA_PROMPTS:
        return _PERSONA_PROMPTS[key]
    pytest.skip(f"{name} has no prompt block of its own")


# ── the rule exists everywhere ──────────────────────────────────────────────

@pytest.mark.parametrize("name", sorted(_PERSONA_PROMPTS))
def test_every_persona_carries_the_post_tool_rule(name):
    assert GATE_MARKER in _prompt_for(name), (
        f"{name} has no post-tool rule, so a reply may ignore a tool result"
    )


def test_the_companion_persona_is_covered():
    """The one that actually derailed in the session."""
    assert GATE_MARKER in _prompt_for("companion")


# ── proximity: it has to be LAST ────────────────────────────────────────────

@pytest.mark.parametrize("name", sorted(_PERSONA_PROMPTS))
def test_the_rule_is_the_last_block_of_every_prompt(name):
    """The whole point of putting it last.

    A prompt that opens with three sections demanding maximal romance will
    follow the last instruction it reads, not the one buried in the middle."""
    text = _prompt_for(name)
    assert text.rstrip().rstrip("]").rstrip().endswith(
        "however charming it is."
    ) or text.rstrip().endswith("is."), (
        f"{name}: the post-tool rule is not the final instruction in the prompt"
    )


def test_no_persona_puts_a_demanding_block_after_the_gate():
    """Nothing may outrank it."""
    for name in sorted(_PERSONA_PROMPTS):
        text = _prompt_for(name)
        at = text.rfind(GATE_MARKER)
        tail = text[at:]
        # A section heading after the gate means something is competing.
        assert not re.search(r"\n\s*\d+\.\s+[A-Z]", tail), (
            f"{name} has a numbered section after the post-tool rule, which "
            f"would compete with it: {tail[-120:]!r}"
        )


# ── the rule names the actual failure ───────────────────────────────────────

@pytest.mark.parametrize("name", sorted(_PERSONA_PROMPTS))
def test_the_rule_names_the_observable_failure(name):
    """Not "be better". The two things that actually went wrong."""
    text = _prompt_for(name)
    assert "tool result is an EVENT" in text
    assert "NEVER ask" in text
    # Ignoring the result is the specific failure observed.
    assert "ignores the tool result" in text


@pytest.mark.parametrize("name", sorted(_PERSONA_PROMPTS))
def test_the_rule_refuses_to_present_an_unverified_action_as_done(name):
    """The verification layer started emitting [unverified] today. Without
    this rule the model sees that marker and narrates success anyway - which is
    precisely the bug class this project spent the day removing."""
    text = _prompt_for(name)
    assert "unverified" in text.lower()
    assert "NOT VERIFIED" in text or "unconfirmed" in text.lower()


# ── the companion prompt specifically ────────────────────────────────────────

def test_the_companion_prompt_does_not_put_romance_after_the_gate():
    """Affection is allowed, but only after the confirmation."""
    text = _prompt_for("companion")
    tail = text[text.rfind(GATE_MARKER):]
    assert "AFTER the confirmation" in tail


def test_task_first_still_exists_in_the_companion_prompt():
    """The new block was added, not swapped for this one."""
    text = _prompt_for("companion")
    assert "TASK FIRST" in text


def test_the_gate_was_appended_not_substituted():
    """The persona must still be a companion. Guarding tasks by deleting the
    personality would fix the symptom and take away what the user asked for."""
    text = _prompt_for("companion")
    assert "romantic" in text.lower()
    assert len(text.splitlines()) > 60, "the persona prompt was truncated"