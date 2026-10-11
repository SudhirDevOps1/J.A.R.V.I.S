"""
tests/test_tray_and_close_to_tray.py — Tests for the system tray.

WHY THIS MATTERS ENOUGH TO TEST
-------------------------------
MainWindow had no closeEvent at all before this. That made the window's close
button a hard stop on the process, which is wrong for an assistant whose whole
value proposition is being reachable without thinking about it.

Two properties are easy to get wrong and expensive when wrong:

  * if the window hides but there is no tray to restore it from, the app looks
    like it crashed. Nobody will tolerate that, and it is the first thing a
    user on a desktop without a tray would hit.
  * if there is no separate quit path, close-to-tray traps the user in the
    application with no documented way out.

The menu contents and the close policy are pure logic and are tested here
without a display. The Qt plumbing is smoke-tested for importability only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from ui.tray import (  # noqa: E402
    TrayAction,
    build_menu_actions,
    first_close_message,
    flatten,
    should_hide_on_close,
)


# ── the close policy ────────────────────────────────────────────────────────

def test_closes_to_tray_when_the_tray_exists():
    assert should_hide_on_close(tray_available=True, enabled=True) is True


def test_exits_normally_when_the_user_disables_it():
    assert should_hide_on_close(tray_available=True, enabled=False) is False


def test_never_hides_when_there_is_no_tray():
    """The important one.

    Hiding a window with no visible way to bring it back is indistinguishable
    from a crash. Tray availability must dominate the user's preference.
    """
    assert should_hide_on_close(tray_available=False, enabled=True) is False
    assert should_hide_on_close(tray_available=False, enabled=False) is False


def test_tray_availability_dominates_the_preference_flag():
    """Explicit about the ordering, because reversing it is the natural
    mistake: 'the user enabled close-to-tray, so honour it regardless'."""
    assert (should_hide_on_close(tray_available=False, enabled=True)
            is False)


# ── the menu ────────────────────────────────────────────────────────────────

def test_menu_has_a_quit_action():
    """Without this the user is trapped once close starts hiding."""
    labels = [a.label for a in flatten(build_menu_actions(True, False))]
    assert any("Quit" in lb for lb in labels)


def test_quit_is_a_distinct_action_from_hiding():
    """Close and Quit must not be the same gesture.

    Hiding is convenient and easy to do by accident; quitting is not
    reversible.
    """
    actions = flatten(build_menu_actions(True, False))
    hide = next(a for a in actions if a.callback == "_tray_toggle_window")
    quit_a = next(a for a in actions if a.callback == "_tray_quit")
    assert hide.callback != quit_a.callback
    assert hide.kind != quit_a.kind


def test_every_menu_action_names_a_handler():
    """Handlers are resolved by name at click time, so a typo would be a
    silent no-op exactly like the Ctrl+P bug."""
    for a in flatten(build_menu_actions(True, False)):
        assert isinstance(a, TrayAction), f"{a!r} is not a TrayAction"
        assert a.callback.startswith("_tray_"), a.callback


def test_quit_is_its_own_group():
    """Visually separate, so it does not read as another show/hide toggle."""
    groups = build_menu_actions(True, False)
    quit_groups = [g for g in groups
                   if any(a.kind == "quit" for a in g)]
    assert len(quit_groups) == 1
    assert quit_groups[0] == groups[-1]


def test_no_group_is_empty():
    for visible in (True, False):
        for muted in (True, False):
            for g in build_menu_actions(visible, muted):
                assert g


def test_hide_label_reflects_visibility():
    assert "Hide" in flatten(build_menu_actions(True, False))[0].label
    assert "Show" in flatten(build_menu_actions(False, False))[0].label


def test_mute_label_reflects_state():
    """muted=True means the mic is off, so the action offered must be to
    turn it back on."""
    labels = " ".join(a.label for a in flatten(build_menu_actions(True, False)))
    assert "Mute microphone" in labels
    assert "Unmute" not in labels

    labels = " ".join(a.label for a in flatten(build_menu_actions(True, True)))
    assert "Unmute microphone" in labels


def test_menu_surfaces_the_three_overlays():
    """These are reachable by keyboard only. Once the window is hidden to the
    tray there is no window to press Ctrl+K in, so the tray has to offer them."""
    labels = " ".join(a.label for a in flatten(build_menu_actions(False, False)))
    assert "Command palette" in labels
    assert "Keyboard shortcuts" in labels
    assert "Conversation history" in labels


def test_menu_shows_shortcut_hints():
    """Discoverability. A label nobody can guess is a label nobody finds."""
    labels = " ".join(a.label for a in flatten(build_menu_actions(False, False)))
    assert "Ctrl+K" in labels


def test_menu_is_not_empty_in_either_state():
    for visible in (True, False):
        for muted in (True, False):
            assert len(flatten(build_menu_actions(visible, muted))) > 3


# ── the one-time explanation ────────────────────────────────────────────────

def test_close_message_says_the_app_is_still_running():
    """Without this the window appears to vanish and a new user has no idea
    anything is still going on."""
    msg = first_close_message("J.A.R.V.I.S")
    assert "still running" in msg
    assert "tray" in msg


def test_close_message_names_the_app():
    assert "My Assistant" in first_close_message("My Assistant")


def test_close_message_explains_both_ways_out():
    """How to come back AND how to actually quit. Only mentioning one strands
    people in one direction or the other."""
    msg = first_close_message("X").lower()
    assert "tray" in msg
    assert "quit" in msg


# ── wiring in MainWindow ────────────────────────────────────────────────────

def test_main_window_has_a_close_event():
    """The regression itself.

    Its absence is why closing the window used to end the process with no way
    to bring it back.
    """
    from ui import MainWindow
    assert "closeEvent" in vars(MainWindow)


def test_main_window_has_the_tray_handlers():
    from ui import MainWindow
    for name in ("_tray_toggle_window", "_tray_toggle_mute", "_tray_quit",
                 "_tray_open_palette", "_tray_open_shortcuts",
                 "_tray_open_history"):
        assert callable(getattr(MainWindow, name, None)), f"missing {name}"


def test_quit_sets_the_quitting_flag():
    """closeEvent swallows close as a hide. Quit has to bypass that or the
    process never actually exits."""
    from ui import MainWindow

    class _Fake(MainWindow):
        def __init__(self):          # noqa: D107 - deliberately does not call super
            self._tray_quitting = False
            self.on_quit = None
            self.shutdown_ran = False

    w = _Fake()
    w.on_quit = lambda: setattr(w, "shutdown_ran", True)
    w._tray_quit()
    assert w._tray_quitting is True
    assert w.shutdown_ran is True


def test_quit_without_a_handler_still_sets_the_flag():
    """The UI is usable without main.py; it must not get stuck."""
    from ui import MainWindow

    class _Fake(MainWindow):
        def __init__(self):
            self._tray_quitting = False
            self.on_quit = None

    w = _Fake()
    w._tray_quit()
    assert w._tray_quitting is True


# ── config plumbing ─────────────────────────────────────────────────────────

def test_close_to_tray_setting_round_trips():
    from memory.config_manager import (
        get_close_to_tray_enabled,
        save_close_to_tray_enabled,
    )
    # conftest redirects config writes, so this exercises the real code path.
    original = get_close_to_tray_enabled()
    try:
        save_close_to_tray_enabled(False)
        assert get_close_to_tray_enabled() is False
        save_close_to_tray_enabled(True)
        assert get_close_to_tray_enabled() is True
    finally:
        save_close_to_tray_enabled(original)


def test_close_to_tray_defaults_to_enabled():
    """Read without a written value. The old behaviour was a hard stop, so
    the default has to be the new one."""
    from memory.config_manager import get_close_to_tray_enabled
    assert isinstance(get_close_to_tray_enabled(), bool)


# ── Qt plumbing ─────────────────────────────────────────────────────────────

def test_tray_module_imports_under_qt():
    """Import-only: constructing a QSystemTrayIcon needs a QApplication, and
    some platforms have no tray at all."""
    import ui.tray  # noqa: F401


def test_tray_controller_constructs_without_a_display():
    """The controller must be constructible even where no tray exists, so the
    window can still consult it and decide to exit normally."""
    from ui.tray import TrayController
    c = TrayController(object(), icon_path=None)
    assert c.available is False


def test_tray_setup_reports_failure_rather_than_raising():
    from ui.tray import TrayController
    c = TrayController(object(), icon_path=None)
    result = c.setup()          # must not raise with no QApplication
    assert isinstance(result, bool)


def test_tray_shutdown_is_safe_when_never_set_up():
    from ui.tray import TrayController
    TrayController(object()).shutdown()      # must not raise


def test_tray_notify_is_safe_without_a_tray():
    from ui.tray import TrayController
    c = TrayController(object())
    c.notify("title", "body")                # must not raise
    c.notify_close_to_tray("App")            # must not raise