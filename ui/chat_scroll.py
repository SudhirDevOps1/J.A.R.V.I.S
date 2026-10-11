"""
ui/chat_scroll.py — auto-scroll policy and input history.

THE SCROLL PROBLEM
------------------
LogWidget calls ensureCursorVisible() on every streamed token - seven call
sites. There is no check for whether the user is actually at the bottom, so
anyone trying to re-read an earlier reply while the answer is still arriving
gets yanked back to the end on the very next character. For a streaming chat
surface that is unusable: the text you were reading keeps moving.

PipWindow already had the correct guard (`sb.setValue(sb.maximum())` only when
pinned). The main log did not, which is why the behaviour is inconsistent
between the two surfaces.

The rule implemented here: follow the stream only while the viewport is at, or
near, the bottom. Once the user scrolls up, stop. When they come back to the
bottom, resume. That is the behaviour every chat interface has, and it needs
explicit state because "am I at the bottom" is not answerable after the content
under the cursor has already grown.

Pure integers in, boolean out, so the policy can be tested without a widget.
"""
from __future__ import annotations

from typing import List, Optional

# How close to the bottom still counts as "following". A few pixels of slack
# so that a scrollbar that lands a hair short of the end does not silently
# disengage auto-scroll.
BOTTOM_THRESHOLD_PX = 48


def is_at_bottom(viewport_value: int, content_max: int,
                 threshold: int = BOTTOM_THRESHOLD_PX) -> bool:
    """Whether the viewport is at (or within `threshold` of) the bottom.

    Guards the degenerate cases: a scrollbar that does not exist yet has a
    maximum of 0, and that counts as being at the bottom because there is
    nothing to scroll.
    """
    if content_max <= 0:
        return True
    return (content_max - viewport_value) <= threshold


class FollowState:
    """Tracks whether auto-scroll is currently following the stream.

    Deliberately not derived from the scrollbar alone. Once new content has
    been appended, the old "user was at the bottom" position no longer exists,
    so the answer has to be remembered rather than recomputed.
    """

    def __init__(self, threshold: int = BOTTOM_THRESHOLD_PX):
        self._threshold = threshold
        self.following = True

    def user_scrolled(self, viewport_value: int, content_max: int) -> bool:
        """Report the user's current position. Returns the new follow state.

        Called on every scroll event, including programmatic ones caused by the
        auto-scroll itself. That is fine: auto-scroll always lands at the
        bottom, so it reports `following` back.
        """
        self.following = is_at_bottom(viewport_value, content_max,
                                      self._threshold)
        return self.following

    def content_appended(self) -> bool:
        """New text arrived. True if it should be scrolled into view."""
        return self.following

    def force_follow(self) -> None:
        """Re-engage, for an explicit "jump to newest" action."""
        self.following = True


class InputHistory:
    """Up/Down recall for the command box.

    The text box is a plain QLineEdit with no history, so re-running
    "mausam batao" to check the forecast meant retyping it. That is a
    surprising omission in something you talk to all day.

    Behaviour matches a shell, which is what people already have the muscle
    memory for:

      * Up from an empty box recalls the most recent entry
      * Up again walks backwards
      * Down walks forwards, and past the newest entry restores what was typed
      * consecutive duplicates are collapsed, so holding Up does not fill the
        history with twenty copies of the same command
      * blank input is never recorded

    Drafts are preserved per history entry. Walking Up then Down has to give
    back exactly what was being typed, otherwise recalling a command loses the
    one you were in the middle of writing.
    """

    def __init__(self, maxlen: int = 100):
        self._entries: List[str] = []
        # Guard only against a nonsensical value. Clamping upward would make a
        # caller asking for a smaller history silently get a bigger one.
        self._maxlen = maxlen if (maxlen and maxlen > 0) else 100
        self._cursor: Optional[int] = None      # None = on the live draft
        self._draft: str = ""

    # ── recording ────────────────────────────────────────────────────────────

    def record(self, text: str) -> None:
        """Store a sent command. Blank text is ignored."""
        value = (text or "").strip()
        if not value:
            return
        if self._entries and self._entries[-1] == value:
            # Collapse consecutive duplicates: holding Up after a repeat
            # should not walk through ten identical entries.
            self._reset()
            return
        self._entries.append(value)
        if len(self._entries) > self._maxlen:
            del self._entries[0]
        self._reset()

    def _reset(self) -> None:
        self._cursor = None
        self._draft = ""

    # ── navigation ───────────────────────────────────────────────────────────

    def previous(self, current_text: str = "") -> str:
        """Up. Returns the text the box should now contain."""
        if not self._entries:
            return current_text

        if self._cursor is None:
            # First Up: remember whatever is being typed as the draft.
            self._draft = current_text or ""
            self._cursor = len(self._entries) - 1
        elif self._cursor > 0:
            self._cursor -= 1
        else:
            return self._entries[0]        # already at the oldest, stay put
        return self._entries[self._cursor]

    def next(self, current_text: str = "") -> str:
        """Down. Returns the text the box should now contain."""
        if self._cursor is None:
            return current_text        # not recalling; leave the draft alone

        if self._cursor < len(self._entries) - 1:
            self._cursor += 1
            return self._entries[self._cursor]

        # Past the newest: restore the draft that was in the box. Capture it
        # before resetting, because _reset() clears it - reading it afterwards
        # always returned an empty string, so walking Up then Down wiped
        # whatever the user was in the middle of typing.
        draft = self._draft
        self._reset()
        return draft

    def clear(self) -> None:
        self._entries.clear()
        self._reset()

    # ── introspection ────────────────────────────────────────────────────────

    def entries(self) -> List[str]:
        """Oldest first. A copy, so a caller cannot mutate internal state."""
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __bool__(self) -> bool:
        return bool(self._entries)