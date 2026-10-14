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
    """Degradation, not breakage: if we cannot tell, behave exactly as before.

    This one test opts back into the real launcher, because the whole point is
    to observe the Start Menu stage. It stays safe because pyautogui is the
    recorder fixture, so no key is ever pressed - the test asserts on the
    recorded calls, not on anything happening on the machine.
    """
    monkeypatch.setattr(oa, "_scan_installed_apps", lambda *a, **k: {})
    monkeypatch.setattr(oa, "_process_appeared", lambda *a, **k: False)
    monkeypatch.setattr(oa, "_NO_REAL_LAUNCH", False)

    oa._launch_windows("SomeUninstalledThing")
    assert no_pyautogui.pressed, (
        "an unknown index must fall through to the old Start Menu behaviour"
    )


def test_the_test_guard_actually_blocks_launches(fake_index, no_pyautogui):
    """The guard exists because this suite runs on every git push.

    Verified on this machine: before it, tests/test_start_search_gate.py passed
    a real AppUserModelID to _launch_windows and Notepad opened on the
    developer's desktop once per commit.
    """
    assert oa._real_launches_disabled() is True, (
        "conftest must set the guard for the whole suite"
    )
    assert oa._launch_windows("notepad") is False
    assert oa._launch_windows(r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\notepad.exe") is False
    assert no_pyautogui.pressed == []
    assert no_pyautogui.written == []


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

@pytest.fixture()
def launcher_armed(fake_index, monkeypatch):
    """Turn the no-real-launch guard OFF for tests that must exercise the real
    decision path.

    Without this these three tests passed only because conftest blocked every
    launch, which made them a false green: they proved nothing about the code
    they claim to test. That is how a Linux-only bug - _launch_linux returning
    True without checking xdg-open's exit status - reached main and was caught
    only by the ubuntu-latest CI job.

    It is safe to disarm here. The app is absent from the index, so no stage
    can actually start anything: every path either finds no binary or invokes a
    tool that is asked for a name nothing is registered under.
    """
    monkeypatch.setattr(oa, "_NO_REAL_LAUNCH", False)
    return fake_index


def test_absent_app_gets_a_definite_answer(launcher_armed):
    """Not a hedge. The machine can answer this one, so it should."""
    out = oa.open_app(parameters={"app_name": "Telegram"})
    assert "not installed" in out.lower(), out
    assert "may still be loading" not in out.lower(), (
        "hedging when the answer is known wastes the user's time"
    )
    assert "telegram" in out.lower()


def test_the_definite_answer_names_what_was_searched(launcher_armed):
    """So the claim is checkable rather than asserted."""
    out = oa.open_app(parameters={"app_name": "Telegram"})
    low = out.lower()
    assert "start menu" in low or "installed programs" in low
    assert "indexed" in low


def test_absent_app_is_not_announced_as_opened(launcher_armed, no_pyautogui):
    """The false success this whole gate exists to prevent.

    On Linux this is the test that catches _launch_linux returning True
    without looking at xdg-open's exit status."""
    out = oa.open_app(parameters={"app_name": "Telegram"})
    assert "Opened Telegram" not in out, out
    assert "opened" not in out.lower(), out


def test_linux_launcher_does_not_claim_success_on_a_nonzero_exit(monkeypatch):
    """Regression for the ubuntu-latest CI failure.

    `subprocess.run` does not raise when a command fails, so the original

        subprocess.run(["xdg-open", app_name], ...)
        return True

    reported every attempt as launched. xdg-open exits non-zero for an
    application it cannot find, so asking for one that is not installed
    produced "Opened Telegram." on Linux while Windows behaved correctly.
    """
    class _Result:
        returncode = 3          # what xdg-open returns for an unknown app
        stdout = b""
        stderr = b"not found"

    calls = []

    def fake_run(cmd, *a, **kw):
        calls.append(cmd)
        return _Result()

    monkeypatch.setattr(oa, "_NO_REAL_LAUNCH", False)
    monkeypatch.setattr(oa.subprocess, "run", fake_run)
    monkeypatch.setattr(oa.shutil, "which", lambda *a, **kw: None)

    assert oa._launch_linux("DefinitelyNotInstalled") is False, (
        "a non-zero exit is not a successful launch"
    )
    assert ["xdg-open", "DefinitelyNotInstalled"] in calls


def test_linux_launcher_reports_success_only_on_a_zero_exit(monkeypatch):
    """The other half, so the fix cannot be 'never report success'."""
    class _Result:
        returncode = 0
        stdout = b""
        stderr = b""

    monkeypatch.setattr(oa, "_NO_REAL_LAUNCH", False)
    monkeypatch.setattr(oa.shutil, "which", lambda *a, **kw: None)
    monkeypatch.setattr(oa.subprocess, "run", lambda cmd, *a, **kw: _Result())

    assert oa._launch_linux("someapp") is True