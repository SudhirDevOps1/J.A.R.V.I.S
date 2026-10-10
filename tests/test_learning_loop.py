"""
tests/test_learning_loop.py — Tests for the closed-loop usage learning engine.

Each test gets an isolated temporary database so the user's real
memory/learning.db is never touched, and so tests cannot influence each other
through accumulated state.

The promotion/demotion thresholds are behaviour, not implementation detail, so
they are asserted directly: a phrase that has not been seen enough is not
trusted, a phrase that keeps failing is suppressed, and an explicit promotion
overrides an automatic cooldown.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def ll(tmp_path, monkeypatch):
    """A learning_loop bound to a throwaway database."""
    sys.path.insert(0, str(_ROOT))
    from core import learning_loop as mod
    monkeypatch.setattr(mod, "DB_PATH", tmp_path / "learning.db")
    mod.reset_connection()
    yield mod
    mod.reset_connection()


# ── normalisation ───────────────────────────────────────────────────────────

def test_normalisation_folds_case_and_punctuation(ll):
    assert ll.normalize_phrase("Kholo Notepad!!") == "kholo notepad"
    assert ll.normalize_phrase("  kholo   notepad  ") == "kholo notepad"


def test_normalisation_keeps_word_order(ll):
    """Folding must not over-merge: "open" and "close" are different intents."""
    assert ll.normalize_phrase("open notepad") != ll.normalize_phrase("close notepad")


def test_normalisation_handles_degenerate_input(ll):
    assert ll.normalize_phrase("") == ""
    assert ll.normalize_phrase(None) == ""
    assert ll.normalize_phrase("   ") == ""


def test_normalisation_is_length_bounded(ll):
    assert len(ll.normalize_phrase("a " * 500)) <= 160


# ── recording ───────────────────────────────────────────────────────────────

def test_empty_database_reports_zero(ll):
    s = ll.stats()
    assert s["patterns"] == 0
    assert s["hits"] == 0
    assert s["success_rate"] == 0.0


def test_outcome_is_recorded(ll):
    ll.record_outcome("kholo notepad", "open_app", True, duration_ms=120)
    row = ll.get_pattern("kholo notepad")
    assert row is not None
    assert row["hits"] == 1
    assert row["successes"] == 1
    assert row["failures"] == 0
    assert row["total_ms"] == 120


def test_variants_merge_into_one_bucket(ll):
    """Evidence must accumulate on one pattern, not three."""
    ll.record_outcome("kholo notepad", "open_app", True)
    ll.record_outcome("KHOLO  NOTEPAD!!!", "open_app", True)
    ll.record_outcome("  Kholo notepad.  ", "open_app", True)
    assert ll.stats()["patterns"] == 1
    assert ll.get_pattern("kholo notepad")["hits"] == 3


def test_recording_never_raises_on_bad_input(ll):
    ll.record_outcome("", "tool", True)
    ll.record_outcome("phrase", "", True)
    ll.record_outcome(None, None, False)
    assert ll.stats()["patterns"] == 0


def test_negative_duration_is_clamped(ll):
    ll.record_outcome("x", "t", True, duration_ms=-5000)
    assert ll.get_pattern("x")["total_ms"] == 0


def test_events_are_logged_individually(ll):
    for _ in range(4):
        ll.record_outcome("cmd", "tool", True)
    assert ll.stats()["events"] == 4
    assert len(ll.recent_events(10)) == 4


# ── confidence and promotion thresholds ─────────────────────────────────────

def test_unknown_phrase_is_never_trusted(ll):
    assert ll.confidence_for("never seen") == 0.0
    assert ll.should_auto_execute("never seen") is False


def test_single_success_is_not_enough(ll):
    """One lucky hit is not evidence. Without this, a phrase that happened to
    work once would start skipping confirmation."""
    ll.record_outcome("band karo wifi", "computer_settings", True)
    assert ll.should_auto_execute("band karo wifi") is False


def test_confidence_is_bounded_prior(ll):
    """Laplace-style smoothing: 1/1 must not read as certainty."""
    ll.record_outcome("c", "t", True)
    one_of_one = ll.confidence_for("c")
    assert one_of_one < 1.0
    for _ in range(20):
        ll.record_outcome("c", "t", True)
    assert ll.confidence_for("c") > one_of_one


def test_reliable_phrase_becomes_trusted(ll):
    for _ in range(5):
        ll.record_outcome("kholo notepad", "open_app", True)
    assert ll.should_auto_execute("kholo notepad") is True


def test_reliable_phrase_is_suggested_for_promotion(ll):
    for _ in range(5):
        ll.record_outcome("kholo notepad", "open_app", True)
    assert any(r["phrase"] == "kholo notepad" for r in ll.suggest_promotions())


# ── demotion ────────────────────────────────────────────────────────────────

def test_failing_phrase_is_not_trusted(ll):
    for _ in range(4):
        ll.record_outcome("flaky cmd", "some_tool", False)
    assert ll.should_auto_execute("flaky cmd") is False


def test_failing_phrase_is_suggested_for_demotion(ll):
    for _ in range(4):
        ll.record_outcome("flaky cmd", "some_tool", False)
    assert any(r["phrase"] == "flaky cmd" for r in ll.suggest_demotions())


def test_mixed_history_blocks_auto_execute(ll):
    """Half the time it works is not good enough to skip asking."""
    for _ in range(6):
        ll.record_outcome("coin flip", "tool", True)
    for _ in range(6):
        ll.record_outcome("coin flip", "tool", False)
    assert ll.should_auto_execute("coin flip") is False


# ── corrections ─────────────────────────────────────────────────────────────

def test_correction_suppresses_auto_execute(ll):
    for _ in range(6):
        ll.record_outcome("corrected cmd", "tool_x", True)
    assert ll.should_auto_execute("corrected cmd") is True

    ll.record_correction("corrected cmd", "tool_x", "ye galat hai")
    assert ll.should_auto_execute("corrected cmd") is False


def test_correction_is_listed(ll):
    ll.record_correction("some phrase", "some_tool", "use the other one")
    corrs = ll.list_corrections()
    assert corrs and corrs[0]["phrase"] == "some phrase"
    assert corrs[0]["rule"] == "use the other one"
    assert corrs[0]["tool"] == "some_tool"


def test_explicit_promotion_overrides_correction_cooldown(ll):
    """Regression in design: a correction installs a 30-minute cooldown, but a
    user who explicitly promotes the phrase must not be locked out of their own
    decision — and must not have to wait out a cooldown they cannot see."""
    for _ in range(6):
        ll.record_outcome("corrected cmd", "tool_x", True)
    ll.record_correction("corrected cmd", "tool_x", "ye galat hai")
    assert ll.should_auto_execute("corrected cmd") is False

    ll.set_promoted("corrected cmd", True)
    assert ll.should_auto_execute("corrected cmd") is True


def test_unpromote_restores_the_cooldown(ll):
    for _ in range(6):
        ll.record_outcome("p", "t", True)
    ll.set_promoted("p", True)
    ll.record_correction("p", "t", "no")
    ll.set_promoted("p", True)          # re-promote clears the block
    assert ll.should_auto_execute("p") is True
    ll.set_promoted("p", False)         # and un-promoting brings it back
    assert ll.should_auto_execute("p") is False


# ── explicit control ────────────────────────────────────────────────────────

def test_set_promoted_roundtrip(ll):
    ll.record_outcome("k", "t", True)
    assert ll.set_promoted("k", True) is True
    assert ll.get_pattern("k")["promoted"] == 1
    ll.set_promoted("k", False)
    assert ll.get_pattern("k")["promoted"] == 0


def test_reset_promotions_clears_everything(ll):
    ll.record_outcome("a", "t", True)
    ll.record_outcome("b", "t", True)
    ll.set_promoted("a", True)
    ll.set_promoted("b", True)
    assert ll.reset_promotions() == 2
    assert ll.get_pattern("a")["promoted"] == 0


def test_forget_removes_one_pattern(ll):
    ll.record_outcome("keep me", "t", True)
    ll.record_outcome("drop me", "t", True)
    assert ll.forget_pattern("drop me") is True
    assert ll.get_pattern("drop me") is None
    assert ll.get_pattern("keep me") is not None


def test_forget_unknown_returns_false(ll):
    assert ll.forget_pattern("never existed") is False


def test_reset_all_clears_the_database(ll):
    for p in ("a", "b", "c"):
        ll.record_outcome(p, "t", True)
    ll.record_correction("a", "t", "r")
    ll.reset_all()
    s = ll.stats()
    assert s["patterns"] == 0 and s["events"] == 0 and s["corrections"] == 0


# ── reporting ───────────────────────────────────────────────────────────────

def test_stats_are_sane(ll):
    for _ in range(7):
        ll.record_outcome("good", "t", True)
    for _ in range(3):
        ll.record_outcome("bad", "t", False)
    s = ll.stats()
    assert s["patterns"] == 2
    assert s["hits"] == 10
    assert s["successes"] == 7
    assert s["failures"] == 3
    assert s["success_rate"] == 70.0


def test_top_patterns_ranked_by_usage(ll):
    for _ in range(5):
        ll.record_outcome("frequent", "t", True)
    ll.record_outcome("rare", "t", True)
    top = ll.top_patterns(10)
    assert top[0]["phrase"] == "frequent"


def test_summary_is_user_facing(ll):
    out = ll.summary_text()
    assert "Learning loop" in out
    for _ in range(5):
        ll.record_outcome("kholo notepad", "open_app", True)
    out2 = ll.summary_text()
    assert "kholo notepad" in out2
    assert "promote" in out2.lower()


# ── action_loader integration ───────────────────────────────────────────────

def test_registry_records_success(ll):
    """The registry is the integration point: every Tier-1 action flows through
    it, so this is what makes the loop observe real usage."""
    from core.action_loader import ActionRegistry, ActionRecord

    def ok_handler(parameters=None, **kw):
        return "Opened Notepad successfully."

    reg = ActionRegistry(
        {"t": ActionRecord(name="t", valid=True, handler=ok_handler)},
        logger=lambda m: None,
    )
    reg.set_current_phrase("notepad kholo")
    reg.run("t", {})
    row = ll.get_pattern("notepad kholo")
    assert row is not None and row["successes"] == 1


def test_registry_detects_failure_from_return_string(ll):
    """Handlers report failure by RETURNING a message, not by raising. If the
    loop only watched for exceptions it would learn that failures were
    successes, and promote exactly the broken commands."""
    from core.action_loader import ActionRegistry, ActionRecord

    reg = ActionRegistry(
        {"t": ActionRecord(name="t", valid=True,
                           handler=lambda parameters=None, **kw: "not available")},
        logger=lambda m: None,
    )
    reg.set_current_phrase("wifi band karo")
    reg.run("t", {})
    row = ll.get_pattern("wifi band karo")
    assert row is not None and row["failures"] == 1 and row["successes"] == 0


def test_registry_records_crashes_as_failures(ll):
    from core.action_loader import ActionRecord, ActionRegistry

    def crash(parameters=None, **kw):
        raise RuntimeError("boom")

    reg = ActionRegistry(
        {"t": ActionRecord(name="t", valid=True, handler=crash)},
        logger=lambda m: None,
    )
    reg.set_current_phrase("crash me")
    out = reg.run("t", {})
    assert "failed" in out.lower()          # caught, not propagated
    row = ll.get_pattern("crash me")
    assert row is not None and row["failures"] == 1


def test_registry_works_without_a_phrase(ll):
    """Not every dispatch has a known utterance (e.g. a UI button). That must
    not raise, and must not create a junk pattern."""
    from core.action_loader import ActionRecord, ActionRegistry

    reg = ActionRegistry(
        {"t": ActionRecord(name="t", valid=True, handler=lambda parameters=None, **kw: "Done.")},
        logger=lambda m: None,
    )
    assert reg.run("t", {}) == "Done."
    assert ll.stats()["patterns"] == 0


def test_learning_failure_does_not_break_the_action(ll, monkeypatch):
    """If the database is unavailable the action must still return its result.
    Losing a learning observation is acceptable; losing the command is not."""
    from core import learning_loop as mod
    from core.action_loader import ActionRecord, ActionRegistry

    def boom(*a, **kw):
        raise sqlite_error()

    class sqlite_error(Exception):
        pass

    monkeypatch.setattr(mod, "record_outcome", boom)
    reg = ActionRegistry(
        {"t": ActionRecord(name="t", valid=True, handler=lambda parameters=None, **kw: "Done.")},
        logger=lambda m: None,
    )
    reg.set_current_phrase("anything")
    assert reg.run("t", {}) == "Done."


# ── the control action ──────────────────────────────────────────────────────

def test_learning_ctl_is_discoverable():
    from core.action_loader import discover_actions
    reg = discover_actions(actions_dir=_ROOT / "actions",
                           reserved_names=set(), logger=lambda m: None)
    assert reg.has("learning_ctl")


def test_learning_ctl_actions_return_text(ll, monkeypatch):
    import actions.learning_ctl as lc
    monkeypatch.setattr(lc, "LL", ll)
    for action in ("summary", "stats", "patterns", "promotions", "corrections"):
        out = lc.learning_ctl({"action": action})
        assert isinstance(out, str) and len(out) > 0


def test_learning_ctl_promote_and_forget(ll, monkeypatch):
    import actions.learning_ctl as lc
    monkeypatch.setattr(lc, "LL", ll)
    for _ in range(5):
        ll.record_outcome("kholo notepad", "open_app", True)

    out = lc.learning_ctl({"action": "promote", "phrase": "kholo notepad"})
    assert ll.get_pattern("kholo notepad")["promoted"] == 1

    out = lc.learning_ctl({"action": "forget", "phrase": "kholo notepad"})
    assert ll.get_pattern("kholo notepad") is None


def test_learning_ctl_reset(ll, monkeypatch):
    import actions.learning_ctl as lc
    monkeypatch.setattr(lc, "LL", ll)
    ll.record_outcome("x", "t", True)
    lc.learning_ctl({"action": "reset"})
    assert ll.stats()["patterns"] == 0


# ── storage ─────────────────────────────────────────────────────────────────

def test_database_lives_in_the_memory_dir_by_default():
    """The loop must stay local: same directory as the rest of the memory.

    Read straight from the source rather than reloading the module: reloading
    would discard the monkeypatched DB_PATH that every other test's `ll`
    fixture depends on.
    """
    import re
    src = (_ROOT / "core" / "learning_loop.py").read_text(encoding="utf-8")
    m = re.search(r'DB_PATH\s*=\s*_BASE_DIR\s*/\s*"(\w+)"\s*/\s*"([\w.]+)"', src)
    assert m, "DB_PATH should be derived from _BASE_DIR"
    assert m.group(1) == "memory"
    assert m.group(2) == "learning.db"


def test_data_survives_reconnection(ll, tmp_path):
    ll.record_outcome("persisted", "t", True)
    ll.reset_connection()          # simulate a restart
    assert ll.get_pattern("persisted") is not None


def test_wal_mode_is_enabled(ll):
    ll.record_outcome("x", "t", True)
    mode = ll._connect().execute("PRAGMA journal_mode").fetchone()[0]
    assert str(mode).lower() == "wal"