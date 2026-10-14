"""
tests/test_lfm_honesty.py - The 230M model that was not there.

WHAT WAS FOUND
--------------
The settings screen showed, on the user's own machine:

    Ear: LFM2.5-230M
    Semantic Parser | 200MB
    Active: LFM2.5 Ear (~200MB) + Needle 2 Hands

Measured at the time:

    models/lfm          an empty directory
    ollama              not installed
    localhost:11434     nothing listening
    is_available()      False

and generate("hello") still returned, in four seconds:

    "Hello sir! Main sun raha hoon, bataiye kya hukum hai?"

The source explained why. Under "Local LFM2.5 offline conversational reflex
responses (30+ Smart Patterns)" there are 23 hand-written regex branches, each
returning a fixed Hinglish sentence. That is pattern matching. It is not a
230M parameter model, and it does not use 200 MB of RAM, because there is no
model to hold.

This is the twelfth instance today of a system reporting a capability it did
not have, and the first one where the report was on the screen in plain sight.

WHAT CHANGED
------------
The branches are kept - removing working behaviour is not the fix - but they
require an explicit opt-in, and generate() returns None when there is no model
at all. The routing payload no longer hardcodes a model name or a RAM figure.

Nothing about the router's actual behaviour changed: normal chat still goes to
the cloud, TEST REFLEX still measures the real tool router, and offline mode
was already guarded by is_available().
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


@pytest.fixture()
def lfm(monkeypatch):
    """An LFMChatEngine with no model behind it, whatever this machine has."""
    from core.edge_router import LFMChatEngine
    import core.edge_router as er

    monkeypatch.setattr(er, "_REQUESTS_AVAILABLE", False)
    engine = LFMChatEngine()
    monkeypatch.setattr(engine, "is_available", lambda: False)
    monkeypatch.delenv("JARVIS_LFM_CANNED", raising=False)
    return engine


# ── the claim itself ────────────────────────────────────────────────────────

def test_with_no_model_generate_returns_nothing(lfm):
    """The single most important assertion in this file.

    It used to return a confident, natural sentence."""
    assert lfm.generate("hello") is None


def test_it_says_nothing_for_every_kind_of_prompt(lfm):
    """Greetings and time are the two branches most likely to fire on an
    everyday prompt, so they are the two checked explicitly."""
    for prompt in ("hello", "good morning", "shubh prabhat",
                   "kya time hai", "aaj kya date hai", "what's up",
                   "tell me a joke", "kuch bhi"):
        assert lfm.generate(prompt) is None, f"{prompt!r} produced an answer"


def test_the_canned_replies_are_not_silently_substituted(lfm):
    """A caller must be able to tell 'the model answered' from 'nothing was
    here'. A string that looks like a reply destroys exactly that
    distinction."""
    for prompt in ("hello sir", "shubh prabhat sir", "abhi samay ho raha hai"):
        result = lfm.generate(prompt)
        assert result is None or len(result) > 0
        assert result is None, f"{prompt!r} still answered without a model"


def test_the_canned_replies_still_exist_behind_an_explicit_opt_in(lfm, monkeypatch):
    """Not deleted - that would remove behaviour. Just no longer automatic.

    A regression test that only checked "it returns None" would pass even if
    someone deleted the 23 branches outright, which is not what happened."""
    monkeypatch.setenv("JARVIS_LFM_CANNED", "1")
    out = lfm.generate("hello")
    assert out is not None
    assert isinstance(out, str) and out.strip()


def test_the_opt_in_is_off_by_default(lfm):
    import os
    assert os.environ.get("JARVIS_LFM_CANNED") is None


def test_the_opt_in_is_not_a_truthy_word_in_a_prompt(lfm):
    """A prompt that happens to contain the word must not switch it on."""
    assert lfm.generate("please set JARVIS_LFM_CANNED=1 and say hello") is None


# ── the routing payload, which claimed a model on every branch ──────────────

def test_the_route_payload_does_not_claim_a_model_that_is_absent(monkeypatch):
    """Six branches carried a hardcoded "ear": "lfm2.5-230m", including the
    cloud branch where no local model runs at all."""
    from core import reflex_policy
    reflex_policy.set_enabled(False)
    from core.edge_router import get_tri_tier_dispatcher

    dispatcher = get_tri_tier_dispatcher()
    monkeypatch.setattr(dispatcher.lfm, "is_available", lambda: False)

    for prompt in ("open notepad", "kya time hai", "suno", "hello"):
        decision = dispatcher.route(prompt)
        assert decision.get("ear") == "none", (
            f"{prompt!r} still reports ear={decision.get('ear')!r} with no model"
        )


def test_the_ram_claim_is_not_a_constant(monkeypatch):
    """"ram_footprint": "200 MB" while nothing was loaded is the same class of
    unverified claim as the model name."""
    from core import reflex_policy
    reflex_policy.set_enabled(False)
    from core.edge_router import get_tri_tier_dispatcher

    dispatcher = get_tri_tier_dispatcher()
    monkeypatch.setattr(dispatcher.lfm, "is_available", lambda: False)
    assert "0 MB" in dispatcher._ear_ram()

    monkeypatch.setattr(dispatcher.lfm, "is_available", lambda: True)
    assert "200 MB" in dispatcher._ear_ram()


def test_the_ear_label_is_honest_about_absence(monkeypatch):
    from core.edge_router import get_tri_tier_dispatcher

    dispatcher = get_tri_tier_dispatcher()
    monkeypatch.setattr(dispatcher.lfm, "is_available", lambda: False)
    assert "not installed" in dispatcher._ear_label().lower()

    monkeypatch.setattr(dispatcher.lfm, "is_available", lambda: True)
    assert "loaded" in dispatcher._ear_label().lower()


def test_no_route_result_ever_claims_the_model_when_there_is_none(monkeypatch):
    """Behavioural, and stronger than banning the string.

    An earlier version of this test walked the AST and failed on any bare
    'lfm2.5-230m' constant. That flagged the Tier 2 branch, which is inside
    `if not is_online and self.lfm.is_available():` - so it is only reachable
    when the model genuinely exists, and banning the string there would have
    been a test of the source text rather than of the behaviour.

    What actually matters: no routing result may report tier 2, a model
    engine, or 200 MB of RAM while nothing is loaded. Checked across a spread
    of prompts and both online states.
    """
    from core import reflex_policy
    reflex_policy.set_enabled(False)
    from core.edge_router import get_tri_tier_dispatcher

    dispatcher = get_tri_tier_dispatcher()
    monkeypatch.setattr(dispatcher.lfm, "is_available", lambda: False)

    prompts = [
        "open notepad", "kya time hai", "hello", "good morning",
        "suno kya haal hai", "shubh prabhat", "kuch bhi bol do",
        "aaj kya date hai", "take a screenshot", "enable privacy mode",
    ]
    for online in (True, False):
        for prompt in prompts:
            d = dispatcher.route(prompt, is_online=online)
            assert d.get("ear") == "none", f"{prompt!r} online={online}: {d}"
            assert d.get("tier") != 2, f"{prompt!r} online={online}: {d}"
            assert d.get("target") != "local_chat", f"{prompt!r}: {d}"
            assert "200 MB" not in str(d.get("ram_footprint")), f"{prompt!r}: {d}"


# ── what must NOT change ────────────────────────────────────────────────────

def test_normal_chat_still_goes_to_the_cloud(monkeypatch):
    """Making the local model honest must not make the assistant worse.

    Genuinely conversational phrasing - the kind with no tool to call.
    Deliberately NOT "kya time hai": that now routes to the local clock, which
    is the point of another fix, and asserting cloud here would have pinned the
    old behaviour back in place."""
    from core import reflex_policy
    reflex_policy.set_enabled(False)
    from core.edge_router import get_tri_tier_dispatcher

    dispatcher = get_tri_tier_dispatcher()
    monkeypatch.setattr(dispatcher.lfm, "is_available", lambda: False)

    # "explain quantum computing simply" - no tool can answer this, it needs
    # reasoning. Deliberately not "kya time hai" or "suno kya chal raha hai":
    # both now route locally, which is the point of another fix, and pinning
    # cloud for them here would have undone it.
    assert dispatcher.route(
        "explain quantum computing simply").get("target") == "cloud_llm"


def test_simple_questions_stay_local_after_the_honesty_work(monkeypatch):
    """Cloud routing for a question this machine can answer offline costs
    latency, money, and the user's text going to a third party.

    Asserted here as well as in evals/runner.py, so the guarantee sits beside
    the tests whose changes made these routes local in the first place."""
    from core import reflex_policy
    reflex_policy.set_enabled(False)
    from core.edge_router import get_tri_tier_dispatcher

    dispatcher = get_tri_tier_dispatcher()
    monkeypatch.setattr(dispatcher.lfm, "is_available", lambda: False)

    for prompt, tool in (("kya time hai", "clock"),
                         ("time batao", "clock"),
                         ("delhi ka mausam kaisa hai", "weather_report")):
        decision = dispatcher.route(prompt)
        assert decision.get("target") == "local_tool", (
            f"{prompt!r} went to {decision.get('target')!r} instead of {tool}"
        )
        assert decision["tool"][0] == tool


def test_tool_routing_is_unaffected(monkeypatch):
    """Needle 2 is real and must keep working. The honest-ear change was never
    meant to touch it."""
    from core import reflex_policy
    reflex_policy.set_enabled(False)
    from core.edge_router import get_tri_tier_dispatcher

    dispatcher = get_tri_tier_dispatcher()
    monkeypatch.setattr(dispatcher.lfm, "is_available", lambda: False)
    result = dispatcher.route("open notepad")
    assert result.get("tool") and result["tool"][0] == "open_app"


def test_offline_tier_two_is_still_guarded_by_availability(monkeypatch):
    """It always was; this pins it so a future change cannot quietly drop it."""
    from core import reflex_policy
    reflex_policy.set_enabled(False)
    from core.edge_router import get_tri_tier_dispatcher

    dispatcher = get_tri_tier_dispatcher()
    monkeypatch.setattr(dispatcher.lfm, "is_available", lambda: False)
    decision = dispatcher.route("hello", is_online=False)
    assert decision.get("target") != "local_chat"