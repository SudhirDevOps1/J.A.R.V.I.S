"""
ui/shortcut_help.py — Ctrl+/ keyboard shortcut reference.

Exists because the answer to "what can I press?" was previously "nothing shows
you". Built directly from the ShortcutManager's declared specs, so it can never
drift from what is actually bound.
"""
from __future__ import annotations

from typing import Dict, List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class ShortcutHelp(QFrame):
    """A readable two-column sheet of every registered shortcut."""

    def __init__(self, parent: QWidget, manager):
        super().__init__(parent)
        self.setObjectName("shortcutHelp")
        self.setStyleSheet("""
            #shortcutHelp {
                background: #0a0f1a;
                border: 1px solid #00d4ff;
                border-radius: 10px;
            }
            QLabel { color: #cfe8f5; font-size: 13px; }
            QLabel#title {
                color: #00d4ff; font-size: 13px; font-weight: bold;
                letter-spacing: 1px;
            }
            QLabel#cat {
                color: #7cffb2; font-size: 11px; font-weight: bold;
                padding-top: 8px;
            }
            QLabel#keys {
                color: #ffd479; font-size: 12px;
                font-family: 'Consolas', 'Courier New', monospace;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(6)

        title = QLabel("KEYBOARD SHORTCUTS")
        title.setObjectName("title")
        root.addWidget(title)

        by_cat: Dict[str, List] = manager.by_category()
        for cat in sorted(by_cat):
            cat_label = QLabel(cat.upper())
            cat_label.setObjectName("cat")
            root.addWidget(cat_label)

            grid = QGridLayout()
            grid.setHorizontalSpacing(20)
            grid.setVerticalSpacing(5)
            row = 0
            for spec in sorted(by_cat[cat], key=lambda s: s.seq):
                keys = QLabel(spec.seq)
                keys.setObjectName("keys")
                keys.setMinimumWidth(130)
                label = QLabel(spec.label)
                if spec.description:
                    label.setToolTip(spec.description)
                grid.addWidget(keys, row, 0)
                grid.addWidget(label, row, 1)
                row += 1
            root.addLayout(grid)

        tip = QLabel("Press Esc to close")
        tip.setStyleSheet("color:#6d8ba3; font-size:11px; padding-top:10px;")
        root.addWidget(tip)

        self.setFixedWidth(460)
        self.hide()

    def open(self) -> None:
        self.show()
        self.raise_()
        # Focus is required, not cosmetic: an unfocused frame never receives
        # keyPressEvent, so its own footer instruction ("Press Esc to close")
        # was untrue — Escape reached the window and interrupted speech instead.
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def close_help(self) -> None:
        self.hide()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_F1):
            self.close_help()
            return
        super().keyPressEvent(event)