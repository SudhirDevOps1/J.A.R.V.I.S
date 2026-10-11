"""
ui/history_panel.py — Ctrl+H conversation history browser.

Re-runnable history. The assistant keeps a session log in main.py but it was
never visible in the UI, so a user who forgot what they asked could not look it
up or run it again. This reads that log and makes every turn clickable.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


class HistoryPanel(QFrame):
    """Searchable list of past turns. Selecting one re-runs it."""

    rerun_requested = pyqtSignal(str)
    dismissed = pyqtSignal()

    def __init__(self, parent: QWidget, turns: Optional[List[dict]] = None):
        super().__init__(parent)
        self._turns: List[dict] = list(turns or [])
        self._filtered: List[dict] = self._turns

        self.setObjectName("historyPanel")
        self.setStyleSheet("""
            #historyPanel {
                background: #0a0f1a;
                border: 1px solid #00d4ff;
                border-radius: 10px;
            }
            QLineEdit {
                background: #05080f;
                border: 1px solid #123047;
                border-radius: 6px;
                padding: 9px 12px;
                color: #d8f3ff;
                font-size: 13px;
            }
            QListWidget {
                background: transparent;
                border: none;
                color: #cfe8f5;
                font-size: 13px;
                outline: none;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 5px;
            }
            QListWidget::item:selected { background: #10314a; color: #fff; }
            QListWidget::item:hover    { background: #0d2438; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("CONVERSATION HISTORY")
        title.setStyleSheet("color:#00d4ff; font-size:12px; font-weight:bold;")
        head.addWidget(title)
        head.addStretch(1)
        self._hint = QLabel("Enter = run again")
        self._hint.setStyleSheet("color:#6d8ba3; font-size:11px;")
        head.addWidget(self._hint)
        root.addLayout(head)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Search past messages…")
        self._search.textChanged.connect(self._refresh)
        self._search.returnPressed.connect(self._activate)
        root.addWidget(self._search)

        self._list = QListWidget(self)
        self._list.itemActivated.connect(lambda _i: self._activate())
        root.addWidget(self._list, 1)

        self.setFixedWidth(640)
        self.setFixedHeight(520)
        self.hide()

    # ── public ──────────────────────────────────────────────────────────────

    def set_turns(self, turns: List[dict]) -> None:
        """Reload from the live session log."""
        self._turns = list(turns or [])
        self._refresh(self._search.text())

    def open(self) -> None:
        self._refresh("")
        self.show()
        self.raise_()
        self._search.setFocus()

    def close_panel(self) -> None:
        self.hide()
        self.dismissed.emit()

    # ── internals ────────────────────────────────────────────────────────────

    def _refresh(self, text: str = "") -> None:
        q = (text or "").strip().lower()
        if q:
            self._filtered = [
                t for t in self._turns
                if q in str(t.get("user", "")).lower()
                or q in str(t.get("assistant", "")).lower()
            ]
        else:
            self._filtered = list(self._turns)

        self._list.clear()
        for t in self._filtered:
            u = str(t.get("user", "")).strip().replace("\n", " ")
            a = str(t.get("assistant", "")).strip().replace("\n", " ")
            label = f"You:  {u[:80]}"
            if a:
                label += f"\nJARVIS: {a[:80]}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, t)
            self._list.addItem(item)

        self._hint.setText(f"{len(self._filtered)} turn(s) · Enter = run again")

        # Select the first result so Enter works straight after typing. Without
        # this, currentItem() is None after any search and Enter silently does
        # nothing — only a double-click would re-run a turn.
        if self._filtered:
            self._list.setCurrentRow(0)

    def _activate(self) -> None:
        item = self._list.currentItem()
        if item is None and self._list.count():
            item = self._list.item(0)
        if item is None:
            return
        turn = item.data(Qt.ItemDataRole.UserRole)
        if not turn:
            return
        text = str(turn.get("user", "")).strip()
        if text:
            self.close_panel()
            self.rerun_requested.emit(text)

    def keyPressEvent(self, event) -> None:
        """Escape must close this panel, not fall through to the window's
        interrupt-speech binding. Without an override the key was consumed by
        the window shortcut and the panel could not be dismissed."""
        if event.key() == Qt.Key.Key_Escape:
            self.close_panel()
            return
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            # Let the list handle navigation, but stop the parent input box from
            # also reacting (which would move its caret and fire on_return).
            event.accept()
            self._list.keyPressEvent(event)
            return
        super().keyPressEvent(event)