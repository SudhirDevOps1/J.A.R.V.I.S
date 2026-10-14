"""
tests/test_start_search_gate.py — Windows Search must not become a Store tripwire.

THE BUG
-------
Asking for Telegram produced:

    [open_app] 'Telegram' not found in cache. Running dynamic on-demand system
               rescan...
    [open_app] Launching: 'Telegram' -> 'Telegram'

and Windows Search opened showing "Telegram (software)". Telegram is not
installed on that machine: no Get-StartApps entry, no uninstall registry key,
nothing on disk. The user had to dismiss a search box and a Microsoft Store
results page for an application that does not exist.

WHY THAT MATTERS
----------------
Windows Search does not report failure when a query matches nothing locally.
It falls through to the Store and shows products to buy. So "type it and see"
turns a one-line "not installed" into a shopping page, and steals focus from
whatever the user was doing.

The stages above the gate already handle everything genuinely installed — a
real path, a binary on PATH, a protocol handler, an AppID. A name absent from
the index and unreachable by all of those is not installed, and searching for
it cannot succeed.

GUARANTEE
---------
Unknown must never mean "not installed". An index that is empty or that raises
returns None, and the caller keeps its previous behaviour, so a scan failure on
someone else's machine degrades instead of breaking every launch.

Tests use an injected index rather than the real one, so they assert the
decision logic on any machine and cannot pass by accident because Telegram
happened to be installed during a run.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

import actions.open_app as oa  # noqa: E402


@pytest.fixture()
def fake_index(monkeypatch):
    """A small, fixed app index. Deliberately not the machine's real one."""
    index = {
        "notepad": r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\notepad.exe",
        "brave": "Brave",
        "visual studio code": r"C:\...\Code.exe",
        "task manager": "Taskmgr.exe",
    }
    monkeypatch.setattr(oa, "_scan_installed_apps", lambda *a, **k: index)
    return index


@pytest.fixture()
def no_pyautogui(monkeypatch):
    """Record key presses instead of making them. Nothing here may type."""

    class _FakePyautogui:
        def __init__(self):
            self.pressed: list = []
            self.written: list = []
            self.PAUSE = 0

        def press(self, key):
            self.pressed.append(("press", key))

        def write(self, text, interval=0):
            self.written.append(text)

        def hotkey(self, *keys):
            self.pressed.append(("hotkey", keys))

    fake = _FakePyautogui()
    monkeypatch.setitem(sys.modules, "pyautogui", fake)
    return fake


# ── the three-way answer ────────────────────────────────────────────────────

def test_absent_name_is_not_installed(fake_index):
    assert oa._known_installed("telegram") is False
    assert oa._known_installed("spotify") is False
    assert oa._known_installed("telegram desktop") is False


def test_present_name_is_installed(fake_index):
    assert oa._known_installed("notepad") is True
    assert oa._known_installed("Brave") is True          # case-insensitive
    assert oa._known_installed("brave") is True


def test_partial_name_matches_on_a_shared_word(fake_index):
    """`visual studio code` is in the index; users say "code"."""
    assert oa._known_installed("code") is True
    assert oa._known_installed("vs code") is True
    assert oa._known_installed("task manager") is True


def test_short_fragments_never_count_as_a_match(fake_index):
    """A bare 2-3 character prefix must not look like an installed app, or
    "hu" would match half the index."""
    assert oa._known_installed("no") is False
    assert oa._known_installed("xyz") is False


def test_empty_input_is_not_installed(fake_index):
    assert oa._known_installed("") is False
    assert oa._known_installed("   ") is False
    assert oa._known_installed(None) is False


# ── the critical guarantee: unknown is never "not installed" ─────────────────

def test_empty_index_means_unknown_not_absent(monkeypatch):
    """An empty index is indistinguishable from a broken one. Treating it as
    proof that nothing is installed would break every launch wherever the scan
    misbehaves."""
    monkeypatch.setattr(oa, "_scan_installed_apps", lambda *a, **k: {})
    assert oa._known_installed("anything at all") is None


def test_raising_index_means_unknown_not_absent(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("scan exploded")

    monkeypatch.setattr(oa, "_scan_installed_apps", boom)
    assert oa._known_installed("anything at all") is None


# ── the gate itself: no keystrokes for an app that is not there ─────────────

def test_no_search_for_an_app_absent_from_the_index(fake_index, no_pyautogui):
    """The whole point: an unmatched name must never reach Windows Search."""
    assert oa._launch_windows("Telegram") is False
    assert no_pyautogui.pressed == []
    assert no_pyautogui.written == [], (
        f"typed {no_pyautogui.written!r} into Windows Search, which opens the "
        f"Microsoft Store for an app that is not installed"
    )


def test_identifiers_are_never_typed_into_search(fake_index, no_pyautogui):
    """The pre-existing guard must survive the new one in front of it.

    Note what is *not* asserted: that both calls return False. A genuine
    AppUserModelID is a real, launchable target - stage 4 opens Notepad with
    `{1AC14E77-...}\\notepad.exe`, which is the fix working, not failing. What
    must never happen is either value being typed into Windows Search, which is
    what produced a search box reading "5198B7}\\notepad".
    """
    # An opaque hex identifier: nothing to launch, and nothing to search for.
    assert oa._launch_windows("308046B0AF4A39CB") is False

    # A real AppID may legitimately launch. Either result is acceptable; the
    # keystroke assertion is the invariant.
    oa._launch_windows(r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\notepad.exe")

    assert no_pyautogui.written == [], (
        f"typed {no_pyautogui.written!r} into Windows Search; an AppID is "
        f"developer output, not a name anyone can search for"
    )
    assert ("press", "win") not in no_pyautogui.pressed, (
        "the Start Menu was opened for an identifier"
    )


def test_unknown_index_still_reaches_search(fake_index, no_pyautogui, monkeypatch):
    """Degradation, not breakage: if we cannot tell, behave exactly as before."""
    monkeypatch.setattr(oa, "_scan_installed_apps", lambda *a, **k: {})
    monkeypatch.setattr(oa, "_process_appeared", lambda *a, **k: False)

    oa._launch_windows("SomeUninstalledThing")
    assert no_pyautogui.pressed, (
        "an unknown index must fall through to the old Start Menu behaviour"
    )


def test_gate_runs_before_the_keystrokes(fake_index, no_pyautogui):
    """Ordering, asserted structurally: a guard placed after the typing is not
    a guard."""
    src = (_ROOT / "actions" / "open_app.py").read_text(encoding="utf-8-sig")
    body = src.split("def _launch_windows")[1].split("\ndef ")[0]
    gate_at = body.index("_known_installed(clean_search)")
    type_at = body.index("pyautogui.write(")
    assert gate_at < type_at


def test_gate_is_only_a_gate_not_a_removal(fake_index):
    """The fallback stays; it is gated, not deleted."""
    src = (_ROOT / "actions" / "open_app.py").read_text(encoding="utf-8-sig")
    body = src.split("def _launch_windows")[1].split("\ndef ")[0]
    assert "pyautogui.press(\"win\")" in body
    assert "pyautogui.write(" in body


# ── the message the user actually reads ─────────────────────────────────────

def test_absent_app_gets_a_definite_answer(fake_index):
    """Not a hedge. The machine can answer this one, so it should."""
    out = oa.open_app(parameters={"app_name": "Telegram"})
    assert "not installed" in out.lower(), out
    assert "may still be loading" not in out.lower(), (
        "hedging when the answer is known wastes the user's time"
    )
    assert "telegram" in out.lower()


def test_the_definite_answer_names_what_was_searched(fake_index):
    """So the claim is checkable rather than asserted."""
    out = oa.open_app(parameters={"app_name": "Telegram"})
    low = out.lower()
    assert "start menu" in low or "installed programs" in low
    assert "indexed" in low


def test_absent_app_is_not_announced_as_opened(fake_index, no_pyautogui):
    out = oa.open_app(parameters={"app_name": "Telegram"})
    assert "Opened Telegram" not in out, out