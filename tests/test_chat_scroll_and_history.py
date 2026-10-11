"""
tests/test_chat_scroll_and_history.py — auto-scroll policy and input history.

WHY THESE ARE PURE LOGIC
------------------------
Both were implemented inside a QTextEdit and a QLineEdit respectively, where
neither is testable: you cannot deterministically scroll a widget to "near the
bottom but not at it", and you cannot assert on keystrokes without a display
and a running event loop.

So the policy lives in ui/chat_scroll.py as integers in and a boolean out. The
widget calls into it. That is also why the logic is worth its own module: the
"am I following" question has state that has to survive content growing under
the cursor, and burying that in a widget makes it invisible.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from ui.chat_scroll import (  # noqa: E402
    BOTTOM_THRESHOLD_PX,
    FollowState,
    InputHistory,
    is_at_bottom,
)


# ── is_at_bottom ────────────────────────────────────────────────────────────

def test_exact_bottom_is_the_bottom():
    assert is_at_bottom(1000, 1000) is True


def test_mid_content_is_not_the_bottom():
    assert is_at_bottom(400, 1000) is False


def test_a_few_pixels_short_still_counts_as_following():
    """Otherwise a scrollbar that lands a hair short silently disengages
    auto-scroll and the user has no idea why it stopped."""
    assert is_at_bottom(1000 - 10, 1000) is True


def test_far_above_the_threshold_is_not_following():
    assert is_at_bottom(1000 - BOTTOM_THRESHOLD_PX - 50, 1000) is False


def test_empty_content_counts_as_the_bottom():
    """A scrollbar with no range has maximum 0. That must count as at the
    bottom, or the first message ever sent would not scroll into view."""
    assert is_at_bottom(0, 0) is True


def test_threshold_is_configurable():
    assert is_at_bottom(500, 1000, threshold=1000) is True
    assert is_at_bottom(500, 1000, threshold=10) is False


# ── FollowState ─────────────────────────────────────────────────────────────

def test_starts_following():
    """Otherwise the first reply would never scroll into view."""
    assert FollowState().following is True


def test_appended_content_scrolls_while_following():
    s = FollowState()
    assert s.content_appended() is True


def test_scrolling_up_stops_following():
    """The bug this replaces: reading an earlier reply while the answer is
    still streaming and being dragged back to the bottom on every token."""
    s = FollowState()
    s.user_scrolled(viewport_value=200, content_max=1000)
    assert s.following is False
    assert s.content_appended() is False


def test_returning_to_the_bottom_resumes_following():
    """The user scrolls back down because they want to keep watching."""
    s = FollowState()
    s.user_scrolled(200, 1000)
    assert s.following is False
    s.user_scrolled(1000, 1000)
    assert s.following is True
    assert s.content_appended() is True


def test_near_bottom_counts_as_following():
    s = FollowState()
    s.user_scrolled(990, 1000)
    assert s.following is True


def test_auto_scroll_landing_at_the_bottom_does_not_disengage_itself():
    """The scrollbar signal fires for programmatic scrolls too.

    If following flipped off whenever the view moved, the auto-scroll would
    disable itself on the first token and the log would stop advancing.
    """
    s = FollowState()
    s.user_scrolled(1000, 1000)
    assert s.following is True
    assert s.content_appended() is True


def test_force_follow_re_engages():
    s = FollowState()
    s.user_scrolled(0, 1000)
    assert s.following is False
    s.force_follow()
    assert s.following is True


def test_following_state_survives_content_growing():
    """The reason state is remembered rather than recomputed.

    New content makes the old "user was at the bottom" position disappear;
    recomputing from the scrollbar alone would answer a question about a
    layout that no longer exists.
    """
    s = FollowState()
    s.user_scrolled(1000, 1000)      # pinned to the bottom
    assert s.content_appended() is True
    # Now the user scrolls up, and more text arrives on top.
    s.user_scrolled(300, 2000)
    assert s.following is False
    s.content_appended()
    assert s.following is False        # still not dragged back


# ── InputHistory ────────────────────────────────────────────────────────────

def test_starts_empty():
    assert len(InputHistory()) == 0
    assert not InputHistory()


def test_records_a_command():
    h = InputHistory()
    h.record("mausam batao")
    assert h.entries() == ["mausam batao"]


def test_oldest_first_order():
    h = InputHistory()
    h.record("a")
    h.record("b")
    assert h.entries() == ["a", "b"]


def test_blank_input_is_not_recorded():
    """Sending an empty box is a no-op elsewhere; storing it would put a
    useless blank at the top of the recall list."""
    h = InputHistory()
    h.record("")
    h.record("   ")
    h.record(None)
    assert len(h) == 0


def test_whitespace_is_trimmed():
    h = InputHistory()
    h.record("  hello  ")
    assert h.entries() == ["hello"]


def test_consecutive_duplicates_collapse():
    """Holding Up after running the same command twice should not walk
    through ten identical entries."""
    h = InputHistory()
    h.record("same")
    h.record("same")
    h.record("same")
    assert h.entries() == ["same"]


def test_non_consecutive_duplicates_are_kept():
    """A command run, then another, then the first again, is worth recalling
    more than once."""
    h = InputHistory()
    h.record("a")
    h.record("b")
    h.record("a")
    assert h.entries() == ["a", "b", "a"]


def test_up_from_empty_recalls_the_most_recent():
    h = InputHistory()
    h.record("first")
    h.record("second")
    assert h.previous("") == "second"


def test_up_walks_backwards():
    h = InputHistory()
    h.record("first")
    h.record("second")
    assert h.previous("") == "second"
    assert h.previous("second") == "first"


def test_up_stops_at_the_oldest():
    """Holding Up at the top should not wrap or error."""
    h = InputHistory()
    h.record("only")
    h.previous("")
    assert h.previous("only") == "only"


def test_down_walks_forwards():
    """Shell semantics: Up walks back, Down walks forward again."""
    h = InputHistory()
    h.record("first")
    h.record("second")
    assert h.previous("") == "second"
    assert h.previous("second") == "first"
    assert h.next("first") == "second"


def test_down_from_the_newest_returns_to_the_draft():
    """Once at the newest, Down goes back to what was being typed rather than
    wrapping around to the oldest entry."""
    h = InputHistory()
    h.record("first")
    h.record("second")
    assert h.previous("wip") == "second"
    assert h.next("second") == "wip"


def test_down_past_the_newest_restores_the_draft():
    """Walking Up then Down must give back exactly what was being typed,
    otherwise recalling a command loses the one in progress."""
    h = InputHistory()
    h.record("earlier")
    assert h.previous("half typed") == "earlier"
    assert h.next("earlier") == "half typed"


def test_down_with_no_recall_leaves_the_text_alone():
    h = InputHistory()
    h.record("x")
    assert h.next("typing") == "typing"


def test_up_with_empty_history_leaves_the_text_alone():
    h = InputHistory()
    assert h.previous("typing") == "typing"


def test_recording_resets_navigation():
    """After sending, Up should recall the new command, not continue from
    wherever the previous walk left off."""
    h = InputHistory()
    h.record("a")
    h.record("b")
    h.previous("")          # now pointing at "b"
    h.record("c")
    assert h.previous("") == "c"


def test_dedup_also_resets_navigation():
    h = InputHistory()
    h.record("a")
    h.record("b")
    h.previous("")
    h.record("b")           # a duplicate, collapsed
    assert h.previous("") == "b"


def test_history_is_bounded():
    """An hours-long session must not grow the list without limit."""
    h = InputHistory(maxlen=10)
    for i in range(50):
        h.record(f"cmd{i}")
    assert len(h) == 10
    assert h.entries()[-1] == "cmd49"
    assert "cmd0" not in h.entries()


def test_minimum_length_is_sane():
    """A maxlen of 0 or 1 would make the history useless."""
    assert len(InputHistory(maxlen=0)) >= 0
    h = InputHistory(maxlen=1)
    for i in range(5):
        h.record(f"c{i}")
    assert len(h) >= 1


def test_entries_returns_a_copy():
    """Otherwise a caller could mutate the internal list."""
    h = InputHistory()
    h.record("a")
    got = h.entries()
    got.append("injected")
    assert h.entries() == ["a"]


def test_clear_resets_everything():
    h = InputHistory()
    h.record("a")
    h.clear()
    assert len(h) == 0
    assert h.previous("typing") == "typing"


def test_full_round_trip_up_and_down():
    h = InputHistory()
    for c in ("one", "two", "three"):
        h.record(c)
    assert h.previous("") == "three"
    assert h.previous("three") == "two"
    assert h.previous("two") == "one"
    assert h.previous("one") == "one"        # pinned at oldest
    assert h.next("one") == "two"
    assert h.next("two") == "three"
    assert h.next("three") == ""             # back to the empty draft


# ── wiring ──────────────────────────────────────────────────────────────────

def test_log_widget_has_the_follow_aware_scroll():
    """The regression: a bare ensureCursorVisible() on every streamed token."""
    from ui import LogWidget
    assert callable(getattr(LogWidget, "_scroll_to_end_if_following", None))
    assert callable(getattr(LogWidget, "scroll_to_newest", None))


def test_main_window_installs_input_history():
    from ui import MainWindow
    assert callable(getattr(MainWindow, "eventFilter", None))