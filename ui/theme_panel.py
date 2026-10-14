"""
ui/theme_panel.py — The appearance picker.

WHY THIS EXISTS
---------------
core/theme.py could switch the entire interface between seven palettes and a
light mode, persist the choice, and audit every one of them for readability.
None of it was reachable. "Customise the look" meant calling
apply_theme_from_prefs() from a REPL.

A colour picker was already present - it changes the accent hue - but it offers
one axis and no curated starting points. This adds the rest: light mode, the
full palettes, font scale, density, and the contrast verdict for each preset
shown before it is chosen rather than discovered afterwards.

THE PREVIEW IS THE POINT
------------------------
Clicking a card repaints the whole interface immediately, because every widget
in ui.py reads class C rather than hardcoding colours. You see the theme before
you commit to it. Cancel puts the original one back - it is a preview, not a
point of no return.

THE CONTRAST BADGE
------------------
Each card shows whether the palette passes core.theme.audit(). Showing it up
front is what stops someone choosing a theme that looks fine in the picker and
is unreadable at 2am on a bad monitor.
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ui import C, FONT_UI


class PresetCard(QFrame):
    """One selectable theme, with its swatches and its contrast verdict."""

    def __init__(self, theme, on_pick, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._on_pick = on_pick
        self.setObjectName("presetCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(96)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(6)
        self._name = QLabel(theme.name)
        self._name.setFont(QFont(FONT_UI, 10, QFont.Weight.Bold))
        self._name.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        head.addWidget(self._name)

        self._mode = QLabel(theme.mode.upper())
        self._mode.setFont(QFont(FONT_UI, 7, QFont.Weight.Bold))
        head.addWidget(self._mode)
        head.addStretch()

        from core.theme import audit
        problems = audit(theme)
        badge_text = "READABLE" if not problems else f"{len(problems)} LOW CONTRAST"
        self._badge = QLabel(badge_text)
        self._badge.setFont(QFont(FONT_UI, 7, QFont.Weight.Bold))
        head.addWidget(self._badge)
        lay.addLayout(head)

        # Swatches, in the order they appear most on screen.
        swatches = QHBoxLayout()
        swatches.setSpacing(4)
        for value in (theme.accent, theme.bg, theme.panel, theme.text):
            chip = QFrame()
            chip.setFixedSize(26, 16)
            chip.setStyleSheet(
                f"background: {value}; border: 1px solid {C.BORDER_B}; border-radius: 3px;"
            )
            swatches.addWidget(chip)
        swatches.addStretch()
        lay.addLayout(swatches)

        self._restyle(theme)

    def _restyle(self, theme) -> None:
        self.setStyleSheet(f"""
            QFrame#presetCard {{
                background: {theme.panel};
                border: 1px solid {theme.border};
                border-radius: 6px;
            }}
            QFrame#presetCard:hover {{
                border: 1px solid {theme.accent};
            }}
        """)
        fg, dim = theme.text, theme.text_dim
        self._name.setStyleSheet(f"color: {fg}; background: transparent;")
        self._mode.setStyleSheet(f"color: {dim}; background: transparent;")
        self._badge.setStyleSheet(f"color: {theme.accent}; background: transparent;")

    def mousePressEvent(self, event):
        try:
            self._on_pick(self.theme)
        except Exception:
            pass
        super().mousePressEvent(event)


def _is_dark(theme) -> bool:
    try:
        from core.theme import relative_luminance
        return relative_luminance(theme.bg) < 0.5
    except Exception:
        return theme.mode == "dark"


class ThemePanel(QWidget):
    """Appearance picker: presets, font scale, density, live preview."""

    def __init__(self, parent=None, on_apply=None, on_close=None):
        super().__init__(parent)
        self._on_apply = on_apply
        self._on_close = on_close
        self._original = None

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        title = QLabel("APPEARANCE")
        title.setFont(QFont(FONT_UI, 13, QFont.Weight.Bold))
        root.addWidget(title)

        sub = QLabel(
            "Pick a palette — the whole interface changes instantly. "
            "Cancel puts it back."
        )
        sub.setFont(QFont(FONT_UI, 9))
        root.addWidget(sub)

        # ── presets ──────────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(10)

        from core.theme import PRESETS
        columns = 3
        for i, (name, theme) in enumerate(sorted(PRESETS.items())):
            card = PresetCard(theme, self._preview)
            grid.addWidget(card, i // columns, i % columns)
        grid.setRowStretch(grid.rowCount(), 1)

        inner_layout = QVBoxLayout(inner)
        inner_layout.addLayout(grid)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        # ── font scale ───────────────────────────────────────────────────
        self._scale_label = QLabel("TEXT SIZE")
        self._scale_label.setFont(QFont(FONT_UI, 9, QFont.Weight.Bold))
        root.addWidget(self._scale_label)

        scale_row = QHBoxLayout()
        self._scale = QSlider(Qt.Orientation.Horizontal)
        self._scale.setMinimum(80)
        self._scale.setMaximum(160)
        self._scale.setValue(100)
        self._scale.setSingleStep(5)
        self._scale.valueChanged.connect(self._on_scale)
        scale_row.addWidget(self._scale, 1)

        self._scale_value = QLabel("100%")
        self._scale_value.setFont(QFont(FONT_UI, 9))
        self._scale_value.setMinimumWidth(46)
        scale_row.addWidget(self._scale_value)
        root.addLayout(scale_row)

        # ── density ──────────────────────────────────────────────────────
        from core.theme import DENSITY
        self._density_label = QLabel("DENSITY")
        self._density_label.setFont(QFont(FONT_UI, 9, QFont.Weight.Bold))
        root.addWidget(self._density_label)

        density_row = QHBoxLayout()
        self._density_buttons: dict[str, QPushButton] = {}
        for name in DENSITY:
            btn = QPushButton(name.capitalize())
            btn.setFont(QFont(FONT_UI, 9))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, n=name: self._choose_density(n))
            self._density_buttons[name] = btn
            density_row.addWidget(btn)
        density_row.addStretch()
        root.addLayout(density_row)

        # ── actions ──────────────────────────────────────────────────────
        buttons = QHBoxLayout()
        reset = QPushButton("RESET TO MIDNIGHT")
        reset.setFont(QFont(FONT_UI, 9))
        reset.setCursor(Qt.CursorShape.PointingHandCursor)
        reset.clicked.connect(self._reset)
        buttons.addWidget(reset)
        buttons.addStretch()

        cancel = QPushButton("CANCEL")
        cancel.setFont(QFont(FONT_UI, 9))
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self._cancel)
        buttons.addWidget(cancel)

        save = QPushButton("SAVE")
        save.setFont(QFont(FONT_UI, 9, QFont.Weight.Bold))
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self._save)
        buttons.addWidget(save)
        root.addLayout(buttons)

        self._restyle()

    # ── behaviour ──────────────────────────────────────────────────────

    def show_and_load(self, on_close=None) -> None:
        """Remember the current theme so Cancel can put it back."""
        if on_close is not None:
            self._on_close = on_close
        try:
            from core import theme as theme_mod
            self._original = theme_mod.current()
            prefs = theme_mod.load()
            self._scale.blockSignals(True)
            self._scale.setValue(int(round(float(prefs.get("font_scale", 1.0)) * 100)))
            self._scale.blockSignals(False)
            self._scale_value.setText(f"{self._scale.value()}%")
            self._choose_density(prefs.get("density", "cozy"), preview=False)
        except Exception:
            pass
        self.show()
        self.raise_()

    def _preview(self, theme) -> None:
        """Apply immediately. No save - that is what SAVE is for."""
        try:
            import ui as ui_mod
            ui_mod.apply_theme(theme)
            ui_mod.rescale_all_fonts(theme.font_scale)
        except Exception:
            pass
        self._restyle()

    def _restyle(self) -> None:
        try:
            self.setStyleSheet(f"""
                QWidget {{ background: {C.BG}; color: {C.TEXT}; }}
                QScrollArea {{ background: {C.BG}; border: none; }}
                QPushButton {{
                    background: {C.PANEL}; color: {C.TEXT_MED};
                    border: 1px solid {C.BORDER}; border-radius: 4px;
                    padding: 5px 12px;
                }}
                QPushButton:hover {{ color: {C.TEXT}; border-color: {C.PRI}; }}
                QPushButton:checked {{
                    color: {C.BG}; background: {C.PRI}; border-color: {C.PRI};
                }}
                QSlider::groove:horizontal {{
                    height: 4px; background: {C.BORDER}; border-radius: 2px;
                }}
                QSlider::handle:horizontal {{
                    background: {C.PRI}; width: 14px; margin: -6px 0;
                    border-radius: 7px;
                }}
            """)
        except Exception:
            pass

    def _reset(self) -> None:
        from core.theme import DEFAULT_THEME, PRESETS
        self._preview(PRESETS[DEFAULT_THEME])

    def _on_scale(self, value: int) -> None:
        self._scale_value.setText(f"{value}%")
        try:
            from core.theme import clamp_font_scale
            import ui as ui_mod
            ui_mod.rescale_all_fonts(clamp_font_scale(value / 100.0))
        except Exception:
            pass

    def _choose_density(self, name: str, preview: bool = True) -> None:
        for key, btn in self._density_buttons.items():
            btn.setChecked(key == name)

    def _cancel(self) -> None:
        if self._original is not None:
            self._preview(self._original)
        self._close()

    def _save(self) -> None:
        try:
            from core import theme as theme_mod
            prefs = theme_mod.load()
            current = getattr(C, "PRI", "")
            preset = prefs.get("preset", theme_mod.DEFAULT_THEME)
            # Recover the preset name from the palette now on screen, so saving
            # after a live preview records what is actually shown.
            for name, candidate in theme_mod.PRESETS.items():
                if candidate.accent.lower() == str(current).lower():
                    preset = name
                    break
            prefs.update({
                "preset": preset,
                "accent": "",
                "font_scale": self._scale.value() / 100.0,
                "density": next((k for k, b in self._density_buttons.items()
                                 if b.isChecked()), "cozy"),
            })
            theme_mod.save(prefs)
            if self._on_apply:
                self._on_apply(theme_mod.build(
                    prefs["preset"], "", prefs["font_scale"], prefs["density"]))
        except Exception:
            pass
        self._close()

    def _close(self) -> None:
        self.hide()
        if self._on_close:
            try:
                self._on_close()
            except Exception:
                pass


__all__ = ["ThemePanel", "PresetCard"]