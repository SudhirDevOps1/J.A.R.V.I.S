"""
tests/test_reflex_policy.py — Tests for the confidence gate on the regex tier.

The reflex router used to execute every regex match unconditionally, which is
how "timers aur tasks band karo" became `close "aur tasks"` and "main nahi kiya
hu use band kro" became `close "hu use"` — nonsense names announced to the user
as completed actions.

core.reflex_policy now treats a regex match as a proposal. It executes only when
the usage-learning loop has evidence the phrase worked, and defers to the model
otherwise. These tests pin that contract.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


# tests/conftest.py disables the reflex gate for the whole suite, because most
# router tests assert on regex logic rather than on the gating policy. This
# module is the one place that tests the gate, so it re-enables it explicitly.
@pytest.fixture(autouse=True)
def _gate_on():
    from core import reflex_policy
    reflex_policy.set_enabled(True)
    yield
    reflex_policy.set_enabled(False)


@pytest.fixture
def ll(tmp_path, monkeypatch):
    """A learning_loop bound to a throwaway database.

    Declared before `policy` so it resolves first: the reflex gate imports the
    learning module lazily at call time, so the DB redirect must already be in
    place before any router call happens.
    """
    from core import learning_loop as mod
    monkeypatch.setattr(mod, "DB_PATH", tmp_path / "learning.db")
    mod.reset_connection()
    yield mod
    mod.reset_connection()


@pytest.fixture
def policy(monkeypatch, ll):
    """The reflex gate, isolated from the user's real config.

    `ll` is depended on so the temp database is installed before this fixture
    runs; without it the gate would read memory/learning.db and pick up
    patterns recorded by earlier sessions.
    """
    from core import reflex_policy as mod
    monkeypatch.setattr(mod, "apply_config", lambda: None)
    mod.set_enabled(True)
    mod._state["trust"] = {}
    yield mod
    mod.set_enabled(True)
    mod._state["trust"] = {}


# ── unproven phrases defer ──────────────────────────────────────────────────

def test_unknown_phrase_defers_to_the_model(policy, ll):
    ok, reason = policy.gate("kuch naya command", "open_app")
    assert ok is False
    assert "no evidence" in reason or "unproven" in reason


def test_single_success_is_not_enough(policy, ll):
    """One run is not proof. Without this, a phrase that worked once by luck
    would start bypassing the model forever."""
    ll.record_outcome("risky phrase", "open_app", True)
    ok, _ = policy.gate("risky phrase", "open_app")
    assert ok is False


# ── proven phrases execute ───────────────────────────────────────────────────

def test_repeated_success_trusts_the_phrase(policy, ll):
    for _ in range(4):
        ll.record_outcome("notepad kholo", "open_app", True, 10)
    ok, reason = policy.gate("notepad kholo", "open_app")
    assert ok is True
    assert "proven" in reason


def test_promoted_phrase_is_trusted(policy, ll):
    for _ in range(4):
        ll.record_outcome("promoted phrase", "open_app", True, 10)
    ll.set_promoted("promoted phrase", True)
    ok, _ = policy.gate("promoted phrase", "open_app")
    assert ok is True


def test_pinned_tool_bypasses_evidence(policy, ll):
    """Some routes are unambiguous enough to always trust."""
    policy.trust_tool("clock")
    ok, reason = policy.gate("never seen phrase", "clock")
    assert ok is True
    assert "pinned" in reason


# ── failures and corrections revoke trust ───────────────────────────────────

def test_mixed_history_does_not_trust(policy, ll):
    for _ in range(4):
        ll.record_outcome("flaky", "open_app", True, 10)
    for _ in range(4):
        ll.record_outcome("flaky", "open_app", False, 10)
    ok, _ = policy.gate("flaky", "open_app")
    assert ok is False


def test_correction_revokes_trust(policy, ll):
    for _ in range(6):
        ll.record_outcome("corrected", "open_app", True, 10)
    assert policy.gate("corrected", "open_app")[0] is True
    ll.record_correction("corrected", "open_app", "ye galat hai")
    ok, _ = policy.gate("corrected", "open_app")
    assert ok is False


# ── dangerous tools never auto-run ──────────────────────────────────────────

@pytest.mark.parametrize("tool", [
    "run_command", "devops_sentinel", "computer_settings", "file_controller",
    "process_manager", "macro", "send_message", "agent_mode",
])
def test_dangerous_tools_never_auto_execute(policy, ll, tool):
    """Even a phrase with a perfect history must not auto-run these. The blast
    radius of a wrong reflex here is a real action on the machine, and these are
    the tools where that matters."""
    for _ in range(8):
        ll.record_outcome("proven phrase", tool, True, 5)
    ll.set_promoted("proven phrase", True)
    ok, reason = policy.gate("proven phrase", tool)
    assert ok is False
    assert "always defers" in reason


# ── escape hatch ────────────────────────────────────────────────────────────

def test_disabling_the_gate_restores_legacy_behaviour(policy, ll):
    policy.set_enabled(False)
    ok, _ = policy.gate("never seen", "open_app")
    assert ok is True
    policy.set_enabled(True)
    assert policy.gate("never seen", "open_app")[0] is False


def test_untrust_removes_the_pin(policy, ll):
    policy.trust_tool("clock")
    assert policy.gate("x", "clock")[0] is True
    policy.untrust_tool("clock")
    assert policy.gate("x", "clock")[0] is False


# ── router integration ──────────────────────────────────────────────────────

def test_router_defers_unproven_and_executes_proven(policy, ll):
    """End-to-end through the real router."""
    from core.edge_router import NeedleToolRouter
    r = NeedleToolRouter()

    # Unproven -> None, which main.py reads as "let the model decide".
    assert r.classify_tool_intent("notepad kholo") == (None, None)

    for _ in range(4):
        ll.record_outcome("open notepad", "open_app", True, 10)
    result = r.classify_tool_intent("open notepad")
    assert result is not None
    tool, args = result
    assert tool == "open_app"
    assert args.get("name") == "notepad"


def test_router_still_never_fabricates_app_names(policy, ll):
    """The filler guard is independent of the confidence gate and must hold even
    when the gate is disabled, since that is the legacy escape hatch.

    Note what is NOT asserted here: some of these phrases legitimately resolve
    to a real tool ("aur tasks" -> todo category -> OneNote) because "tasks" is
    a genuine todo keyword. What must never happen is an invented app name
    assembled out of pronouns and conjunctions, which is the bug this pins.
    """
    from core.edge_router import NeedleToolRouter, _is_filler_phrase, strip_action_verbs

    # Direct unit check: none of these token runs may be treated as an app name.
    for junk in ("hu use", "aur tasks", "kaun hai", "kuch nahi", "sab tasks"):
        assert _is_filler_phrase(junk) is True, f"{junk!r} would pass as an app name"

    # And with the gate disabled (legacy mode) the router must still not emit
    # an open_app call whose name is pure filler.
    policy.set_enabled(False)
    try:
        r = NeedleToolRouter()
        for text in ("timers aur tasks band karo",
                     "main nahi kiya hu use band kro"):
            result = r.classify_tool_intent(text)
            if result and result[0] == "open_app":
                name = str(result[1].get("name", ""))
                assert not _is_filler_phrase(strip_action_verbs(name)), (
                    f"{text!r} fabricated an app name from filler: {name!r}"
                )
    finally:
        policy.set_enabled(True)


def test_learning_loop_being_unavailable_does_not_break_commands(policy, monkeypatch):
    """If SQLite is broken the assistant must still work locally, not send
    everything to the cloud. This is the one place failing open is correct."""
    import core.learning_loop as ll

    def boom(*a, **kw):
        raise RuntimeError("db gone")

    monkeypatch.setattr(ll, "get_pattern", boom)
    ok, _ = policy.gate("anything", "open_app")
    assert ok is True


# ── reporting ───────────────────────────────────────────────────────────────

def test_snapshot_exposes_the_policy(policy):
    snap = policy.snapshot()
    assert snap["enabled"] is True
    assert "run_command" in snap["never_trust"]
    assert snap["min_evidence"] >= 1


def test_describe_is_human_readable(policy, ll):
    assert "AUTO-EXECUTE" not in policy.describe("never seen", "open_app")
    assert "ask the model" in policy.describe("never seen", "open_app")
    for _ in range(4):
        ll.record_outcome("shown phrase", "open_app", True, 10)
    assert "AUTO-EXECUTE" in policy.describe("shown phrase", "open_app")