"""
ui/palette_widget.py — The Qt widget for the Ctrl+K command palette.

Presentation only. All the matching logic lives in ui/command_palette.py and is
tested there without a QApplication, because fuzzy search is exactly the kind of
thing that is easy to get subtly wrong and painful to test through a GUI.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QKeyEvent
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

from ui.command_palette import (
    PaletteEntry,
    build_entries,
    filter_entries,
    selection_to_text,
)


class CommandPalette(QFrame):
    """Modal-ish search overlay. Enter runs the highlighted entry."""

    submitted = pyqtSignal(str)      # text to send to the assistant
    ran_command = pyqtSignal()        # a UI command was executed instead
    dismissed = pyqtSignal()

    def __init__(self, parent: QWidget, entries: List[PaletteEntry]):
        super().__init__(parent)
        self._entries = entries
        self._filtered: List[PaletteEntry] = entries[:]

        self.setObjectName("commandPalette")
        self.setStyleSheet("""
            #commandPalette {
                background: #0a0f1a;
                border: 1px solid #00d4ff;
                border-radius: 10px;
            }
            QLineEdit {
                background: #05080f;
                border: 1px solid #123047;
                border-radius: 6px;
                padding: 10px 12px;
                color: #d8f3ff;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
                selection-background-color: #00d4ff;
                selection-color: #00121d;
            }
            QListWidget {
                background: transparent;
                border: none;
                color: #cfe8f5;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                outline: none;
            }
            QListWidget::item {
                padding: 7px 8px;
                border-radius: 5px;
            }
            QListWidget::item:selected {
                background: #10314a;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background: #0d2438;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(10)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Type a command, tool or plugin…  (Ctrl+K)")
        self._search.textChanged.connect(self._refresh)
        self._search.returnPressed.connect(self._activate)
        root.addWidget(self._search)

        self._list = QListWidget(self)
        self._list.itemActivated.connect(lambda _i: self._activate())
        root.addWidget(self._list, 1)

        footer = QHBoxLayout()
        footer.setSpacing(14)
        for keys, desc in (
            ("↑↓", "navigate"),
            ("Enter", "run"),
            ("Esc", "close"),
        ):
            lbl = QLabel(f"<b style='color:#00d4ff'>{keys}</b> "
                         f"<span style='color:#6d8ba3'>{desc}</span>")
            footer.addWidget(lbl)
        footer.addStretch(1)
        self._count = QLabel("")
        self._count.setStyleSheet("color:#6d8ba3; font-size:11px;")
        footer.addWidget(self._count)
        root.addLayout(footer)

        self.setFixedWidth(660)
        self.setFixedHeight(460)
        self.hide()

    # ── public ──────────────────────────────────────────────────────────────

    def set_entries(self, entries: List[PaletteEntry]) -> None:
        """Replace the searchable list.

        Called on every open so tools added at runtime, or plugins toggled
        on/off, are reflected. Building the list once and caching it meant the
        palette went stale the moment anything changed.
        """
        self._entries = list(entries or [])
        self._filtered = self._entries[:]
        self._refresh(self._search.text())

    def open(self) -> None:
        self._search.clear()
        self._refresh("")
        self.show()
        self.raise_()
        self._search.setFocus()

    def close_palette(self) -> None:
        self.hide()
        self.dismissed.emit()

    @staticmethod
    def build(parent: QWidget, action_registry=None, plugin_registry=None,
              ui_commands: Optional[Dict[str, Callable[[], None]]] = None,
              ) -> "CommandPalette":
        return CommandPalette(parent, build_entries(action_registry,
                                                    plugin_registry,
                                                    ui_commands))

    # ── internals ────────────────────────────────────────────────────────────

    def _refresh(self, text: str = "") -> None:
        self._filtered = filter_entries(self._entries, text)
        self._list.clear()
        for e in self._filtered:
            item = QListWidgetItem(e.display())
            item.setData(Qt.ItemDataRole.UserRole, e)
            if e.category == "UI":
                item.setForeground(QColor("#7cffb2"))
            elif e.category == "Plugin":
                item.setForeground(QColor("#c79bff"))
            elif e.category == "Tool":
                item.setForeground(QColor("#8fd8ff"))
            self._list.addItem(item)
        self._count.setText(f"{len(self._filtered)} of {len(self._entries)}")
        if self._filtered:
            self._list.setCurrentRow(0)

    def _activate(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        entry: PaletteEntry = item.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return
        self.close_palette()
        if entry.run is not None:
            try:
                entry.run()
            except Exception as e:
                print(f"[CommandPalette] '{entry.label}' failed: {e}")
            self.ran_command.emit()
            return
        text = selection_to_text(entry)
        if text:
            self.submitted.emit(text)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close_palette()
            return
        super().keyPressEvent(event)