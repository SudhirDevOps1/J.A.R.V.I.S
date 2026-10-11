"""
ui/shortcuts.py — Global keyboard shortcut registry for J.A.R.V.I.S.

WHY THIS EXISTS
---------------
The window had four shortcuts (F4 mute, F11 fullscreen, Escape interrupt) and
nothing else. There was no way to reach settings from the keyboard, no way to
see what commands exist, and no command palette — so every feature was reachable
only by clicking a specific button with the mouse.

This module centralises shortcuts so they are declared once, listed in one
place, and shown to the user in a discoverable overlay. Adding a shortcut means
adding one entry to a table, not wiring another QShortcut by hand.

Convention
----------
  Ctrl+K   command palette        the single fastest way to do anything
  Ctrl+/   keyboard help          answers "what can I press?"
  Ctrl+H   conversation history   browse and re-run past turns
  Ctrl+,   settings               same as clicking the gear
  Ctrl+P   PiP companion          toggle the always-on-top mini window
  Ctrl+L   clear input            empty the text box
  Ctrl+,/  nothing (reserved)
  F1       keyboard help (alias, conventional on Windows)
  F2       command palette (alias)
  F4       mute microphone        pre-existing
  F11      fullscreen             pre-existing
  Esc      interrupt speech       pre-existing
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QWidget

from core.sfx import play_sfx

# Bind at window scope so a shortcut works even when focus is inside the text
# box or an overlay, which is the normal case while typing a command.
QtShortcutContext = Qt.ShortcutContext.WindowShortcut


class ShortcutSpec:
    """One declared shortcut. Kept as data so the help overlay can list them."""

    __slots__ = ("seq", "label", "category", "handler", "description")

    def __init__(self, seq: str, label: str, category: str,
                 handler: Optional[Callable[[], None]], description: str = ""):
        self.seq = seq
        self.label = label
        self.category = category
        self.handler = handler
        self.description = description


class ShortcutManager:
    """Owns every QShortcut for a window and can render itself as a help sheet."""

    def __init__(self, parent: QWidget):
        self._parent = parent
        self._specs: List[ShortcutSpec] = []
        self._objects: List[QShortcut] = []

    # ── registration ────────────────────────────────────────────────────────

    def add(self, seq: str, label: str, handler: Optional[Callable[[], None]],
            category: str = "General", description: str = "") -> None:
        """Declare a shortcut. A handler of None registers nothing but is still
        listed in the help sheet, so the table documents intent even where the
        binding is wired elsewhere."""
        spec = ShortcutSpec(seq, label, category, handler, description)
        self._specs.append(spec)
        if handler is None:
            return
        try:
            sc = QShortcut(QKeySequence(seq), self._parent)
            sc.setContext(QtShortcutContext.WindowShortcut)
            sc.activated.connect(self._wrap(handler, label))
            self._objects.append(sc)
        except Exception as e:
            print(f"[Shortcuts] could not bind {seq} ({label}): {e}")

    @staticmethod
    def _wrap(handler: Callable[[], None], label: str):
        def _run():
            try:
                play_sfx("tick")
            except Exception:
                pass
            try:
                handler()
            except Exception as e:
                print(f"[Shortcuts] '{label}' failed: {e}")
        return _run

    # ── reflection ──────────────────────────────────────────────────────────

    def specs(self) -> List[ShortcutSpec]:
        return list(self._specs)

    def by_category(self) -> Dict[str, List[ShortcutSpec]]:
        out: Dict[str, List[ShortcutSpec]] = {}
        for s in self._specs:
            out.setdefault(s.category, []).append(s)
        return out

    def conflicts(self) -> List[Tuple[str, str]]:
        """Sequences bound more than once. A duplicate silently disables one
        binding in Qt, so this is worth surfacing in tests."""
        seen: Dict[str, str] = {}
        dupes: List[Tuple[str, str]] = []
        for s in self._specs:
            if s.seq in seen:
                dupes.append((s.seq, s.label))
            else:
                seen[s.seq] = s.label
        return dupes

    def help_markdown(self) -> str:
        """Rendered by the help overlay and also useful in docs."""
        lines: List[str] = []
        for cat in sorted(self.by_category()):
            lines.append(f"\n{cat}")
            lines.append("-" * len(cat))
            for s in sorted(self.by_category()[cat], key=lambda x: x.seq):
                lines.append(f"  {s.seq:<12} {s.label}")
        return "\n".join(lines).strip()


def register_defaults(mgr: ShortcutManager, win) -> None:
    """Bind the standard set against a MainWindow.

    Each handler is resolved lazily and defensively: the window gains these
    methods over time, and a missing handler must not stop the remaining
    shortcuts from binding.
    """
    def _h(name: str):
        def _call():
            fn = getattr(win, name, None)
            if callable(fn):
                fn()
        return _call

    # --- General ---
    mgr.add("Ctrl+K", "Command palette", _h("_open_command_palette"), "General",
            "Search and run any action by name")
    mgr.add("Ctrl+/", "Keyboard shortcuts", _h("_open_shortcut_help"), "General",
            "Show this list")
    mgr.add("F1", "Keyboard shortcuts", _h("_open_shortcut_help"), "General", "")
    mgr.add("F2", "Command palette", _h("_open_command_palette"), "General", "")

    # --- Conversation ---
    mgr.add("Ctrl+H", "Conversation history", _h("_open_history"), "Conversation",
            "Browse and re-run past turns")
    mgr.add("Ctrl+L", "Clear input", _h("_clear_input"), "Conversation", "")
    mgr.add("Ctrl+Shift+C", "Copy last reply", _h("_copy_last_reply"), "Conversation",
            "")
    mgr.add("Ctrl+Shift+R", "Regenerate last reply", _h("_regenerate_last"),
            "Conversation", "")

    # --- Window ---
    mgr.add("Ctrl+,", "Settings", _h("_open_settings"), "Window", "")
    mgr.add("Ctrl+P", "Toggle PiP companion", _h("_toggle_pip"), "Window",
            "Always-on-top mini window")
    mgr.add("Ctrl+B", "Toggle quick drawer", _h("_toggle_quick_drawer"), "Window", "")

    # --- Voice (pre-existing) ---
    mgr.add("F4", "Mute / unmute microphone", _h("_toggle_mute"), "Voice", "")
    mgr.add("F11", "Fullscreen", _h("_toggle_fullscreen"), "Window", "")
    mgr.add("Esc", "Interrupt speech", _h("_do_interrupt"), "Voice",
            "Stop what JARVIS is saying right now")