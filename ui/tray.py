"""
ui/tray.py — system tray icon, minimize-to-tray, and a real quit path.

THE PROBLEM THIS SOLVES
------------------------
J.A.R.V.I.S is an ambient assistant. Its value is being reachable without
thinking about it — you say "notepad kholo" and it happens. Closing the window
was the only way to get it out of the way, and closing the window killed the
process. There was no closeEvent on MainWindow at all, so the close button was
a hard stop, and a voice assistant that stops existing because you tidied up
the window is broken in the most basic way.

So: close hides to the tray, the tray restores it, and Quit is a separate,
deliberate action. Someone must always be able to actually exit, so the quit
path is explicit and is never the same gesture as close.

WHY THIS IS A MODULE AND NOT 40 LINES IN MainWindow
---------------------------------------------------
The menu contents, the labels, and the close-to-tray decision are the parts
that get changed, and the parts worth testing. All of that is kept out of Qt so
it can be checked without a display; only the icon plumbing needs a GUI.

This module imports PyQt lazily inside TrayController, so the decision logic
here can be imported and tested headless.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

# ── what the tray menu should contain ───────────────────────────────────────
#
# Declared as data so the order, the labels and the accelerator hints are
# testable without instantiating QSystemTrayIcon. The callback names a window
# method, resolved lazily at click time.


@dataclass(frozen=True)
class TrayAction:
    label: str
    callback: str
    # "normal" items toggle state; "quit" is marked so it can be styled as the
    # exit rather than another show/hide toggle.
    kind: str = "normal"
    checkable: bool = False


def build_menu_actions(visible: bool, muted: bool) -> List[List[TrayAction]]:
    """The menu for the current window state, already split into groups.

    Returns groups rather than a flat list with separator markers in it. A
    sentinel string mixed in with real objects means every caller has to
    remember to filter it, and the one that forgets gets an AttributeError
    instead of a menu. Callers iterate groups and insert a separator between
    them.

    Labels change with state ("Show JARVIS" vs "Hide JARVIS") because a tray
    menu is read at a glance and a static label makes the user guess which way
    the toggle currently points.

    The three surfaces that are otherwise reachable only by keyboard are
    mirrored here, so someone who closed the window is not locked out of the
    command palette.
    """
    return [
        [
            TrayAction("Hide JARVIS" if visible else "Show JARVIS",
                       "_tray_toggle_window"),
            TrayAction("Mute microphone" if not muted else "Unmute microphone",
                       "_tray_toggle_mute", checkable=True),
        ],
        [
            TrayAction("Command palette  (Ctrl+K)", "_tray_open_palette"),
            TrayAction("Keyboard shortcuts  (Ctrl+/)", "_tray_open_shortcuts"),
            TrayAction("Conversation history  (Ctrl+H)", "_tray_open_history"),
            # Appearance lives in the tray because it is the one setting people
            # look for after closing the window. A feature that exists and has
            # no way in is the same as a feature that does not exist.
            TrayAction("Appearance  (themes, text size)", "_tray_open_theme"),
        ],
        [
            TrayAction("Quit JARVIS", "_tray_quit", kind="quit"),
        ],
    ]


def flatten(groups: List[List[TrayAction]]) -> List[TrayAction]:
    """Every action in order, for callers that just want the flat list."""
    return [a for g in groups for a in g]


# ── close-to-tray policy ────────────────────────────────────────────────────

def should_hide_on_close(tray_available: bool, enabled: bool) -> bool:
    """Whether closing the window should hide it instead of exiting.

    Tray availability is checked first, and it has to dominate: hiding a
    window whose tray icon does not exist, with no visible way to bring it
    back, looks exactly like the application crashing.
    """
    return bool(tray_available and enabled)


def first_close_message(app_name: str) -> str:
    """Shown once, the first time the window is closed to the tray.

    Without this the window appears to vanish and a new user has no idea it is
    still running, let alone where it went.
    """
    return (f"{app_name} is still running in the system tray.\n\n"
            "Use the tray icon to bring the window back, or right-click it "
            "and choose Quit to exit.")


# ── the Qt part ─────────────────────────────────────────────────────────────

class TrayController:
    """Owns the QSystemTrayIcon and the window it belongs to.

    Every method degrades safely. A missing tray (some Linux desktops, some
    remote sessions) must leave the app fully usable, just without the extra
    affordance.
    """

    def __init__(self, window, icon_path: Optional[str] = None):
        self._win = window
        self._icon_path = icon_path
        self._tray = None            # QSystemTrayIcon
        self._menu = None            # QMenu
        self._available = False
        self._explained_close = False

    # ── lifecycle ────────────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        return self._available

    def setup(self) -> bool:
        """Create the tray icon. Returns False if the platform has none."""
        try:
            from PyQt6.QtGui import QAction, QIcon
            from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QWidget
        except Exception as e:
            print(f"[Tray] Qt tray imports unavailable: {e}")
            return False

        # Constructing a QSystemTrayIcon whose parent is not a QWidget aborts
        # the process outright rather than raising, so this check cannot be
        # left to a try/except further down.
        if not isinstance(self._win, QWidget):
            return False

        try:
            if not QSystemTrayIcon.isSystemTrayAvailable():
                print("[Tray] no system tray on this platform; "
                      "close will exit normally.")
                return False
        except Exception:
            return False

        try:
            self._tray = QSystemTrayIcon(self._win)
            icon = QIcon(self._icon_path) if self._icon_path else QIcon()
            if not icon.isNull():
                self._tray.setIcon(icon)
            else:
                self._tray.setIcon(self._win.windowIcon())

            self._menu = QMenu()
            self._rebuild_menu()

            self._tray.setContextMenu(self._menu)
            self._tray.activated.connect(self._on_activated)
            self._tray.show()

            self._available = True
            return True
        except Exception as e:
            print(f"[Tray] setup failed: {e}")
            self._tray = None
            return False

    def shutdown(self) -> None:
        try:
            if self._tray is not None:
                self._tray.hide()
                self._tray.setContextMenu(None)
                self._tray = None
        except Exception:
            pass
        self._available = False

    # ── menu ─────────────────────────────────────────────────────────────────

    def _rebuild_menu(self) -> None:
        """Rebuild from live state.

        Rebuilt on every show rather than kept in sync through individual
        setters, so a new toggle cannot be forgotten: the menu always reflects
        what the window is actually doing.
        """
        if self._menu is None:
            return
        try:
            from PyQt6.QtGui import QAction

            self._menu.clear()
            visible = bool(self._win.isVisible())
            muted = bool(getattr(self._win, "_muted", False))

            for idx, group in enumerate(build_menu_actions(visible, muted)):
                if idx:
                    self._menu.addSeparator()
                for action in group:
                    act = QAction(action.label, self._menu)
                    act.setCheckable(bool(action.checkable))
                    if action.checkable:
                        act.setChecked(muted)
                    act.triggered.connect(
                        lambda _checked=False, cb=action.callback:
                        self._invoke(cb))
                    self._menu.addAction(act)
        except Exception as e:
            print(f"[Tray] menu rebuild failed: {e}")

    def _invoke(self, method_name: str) -> None:
        """Call a window method by name, tolerating absence."""
        fn = getattr(self._win, method_name, None)
        if not callable(fn):
            print(f"[Tray] no handler {method_name}")
            return
        try:
            fn()
        except Exception as e:
            print(f"[Tray] {method_name} failed: {e}")
        self._rebuild_menu()

    def _on_activated(self, reason) -> None:
        """Left-click or double-click restores the window.

        Right-click is left to the context menu: on Windows a left click that
        also popped the menu made restore feel unreliable.
        """
        try:
            from PyQt6.QtWidgets import QSystemTrayIcon
            if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                          QSystemTrayIcon.ActivationReason.DoubleClick):
                self._invoke("_tray_toggle_window")
        except Exception:
            self._invoke("_tray_toggle_window")

    # ── notifications ────────────────────────────────────────────────────────

    def notify_close_to_tray(self, app_name: str) -> None:
        """Explain once that closing did not quit."""
        if self._explained_close or not self._available:
            return
        self._explained_close = True
        try:
            from PyQt6.QtWidgets import QSystemTrayIcon
            self._tray.showMessage(
                f"{app_name} is still running",
                "Click the tray icon to reopen the window. "
                "Right-click and choose Quit to exit.",
                QSystemTrayIcon.MessageIcon.Information,
                6000,
            )
        except Exception as e:
            print(f"[Tray] notify failed: {e}")

    def notify(self, title: str, message: str, msecs: int = 4000) -> None:
        """Generic notification, for things worth surfacing in the background."""
        if not self._available:
            return
        try:
            from PyQt6.QtWidgets import QSystemTrayIcon
            self._tray.showMessage(
                title, message,
                QSystemTrayIcon.MessageIcon.Information, msecs)
        except Exception:
            pass