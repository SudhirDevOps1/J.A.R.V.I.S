"""
tests/test_theme_panel.py - The appearance picker, driven as a real widget.

A theme engine nobody can open is not a feature. These build the actual panel,
click the actual cards, and read the actual saved file, because that is the
only way to catch a stylesheet that throws on one palette or a save button
that records the wrong thing.

Qt runs offscreen.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qt():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def panel(qt, tmp_path, monkeypatch):
    from core import theme as T
    import ui
    from ui.theme_panel import ThemePanel

    monkeypatch.setattr(T, "THEME_FILE", tmp_path / "ui_theme.json")
    before = {k: getattr(ui.C, k) for k in
              ("BG", "PANEL", "PANEL2", "BORDER", "BORDER_B", "TEXT",
               "TEXT_DIM", "TEXT_MED", "WHITE", "BAR_BG",
               "PRI", "PRI_DIM", "PRI_GHO")}
    p = ThemePanel()
    yield p
    for k, v in before.items():
        setattr(ui.C, k, v)


# ── construction ────────────────────────────────────────────────────────────

def test_panel_builds(panel):
    assert panel is not None


def test_one_card_per_preset(panel):
    from ui.theme_panel import PresetCard
    from core.theme import PRESETS

    cards = panel.findChildren(PresetCard)
    assert len(cards) == len(PRESETS)
    assert {c.theme.name for c in cards} == set(PRESETS)


def test_every_card_shows_its_own_name(panel):
    """The bug this exists to catch: every preset was called "Midnight" because
    the display name never reached the Theme. Seven identical cards is exactly
    what that looks like."""
    from core.theme import PRESETS
    from ui.theme_panel import PresetCard

    cards = panel.findChildren(PresetCard)
    assert cards
    for card in cards:
        assert card.theme.name == card._name.text()
        assert card.theme.name in PRESETS


def test_every_card_carries_a_contrast_verdict(panel):
    from ui.theme_panel import PresetCard

    cards = panel.findChildren(PresetCard)
    assert all(c._badge.text() for c in cards)
    # Every shipped preset passes, so every card must say so.
    assert all("READABLE" in c._badge.text() for c in cards)


def test_light_presets_are_labelled_light(panel):
    from ui.theme_panel import PresetCard

    cards = {c.theme.name: c for c in panel.findChildren(PresetCard)}
    light = [c for c in cards.values() if c.theme.mode == "light"]
    assert light, "no light preset to show"
    for c in light:
        assert c._mode.text() == "LIGHT"


def test_density_has_all_three_options(panel):
    assert set(panel._density_buttons) == {"compact", "cozy", "comfortable"}


# ── live preview ────────────────────────────────────────────────────────────

def test_clicking_a_card_repaints_immediately(panel):
    import ui
    from core.theme import PRESETS

    before = ui.C.BG
    panel._preview(PRESETS["Paper"])
    assert ui.C.BG != before
    assert ui.C.BG == PRESETS["Paper"].bg


def test_previewing_a_light_theme_flips_the_text_too(panel):
    """Flipping the background without the text is how a theme becomes
    unreadable rather than light."""
    import ui
    from core.theme import PRESETS

    panel._preview(PRESETS["Daylight"])
    assert ui.C.BG.lower() == PRESETS["Daylight"].bg.lower()
    assert ui.C.TEXT == PRESETS["Daylight"].text


def test_preview_does_not_save(panel, tmp_path):
    """It is a preview. Saving is what the SAVE button is for."""
    from core import theme as T
    from core.theme import PRESETS

    panel._preview(PRESETS["Rose"])
    assert T.THEME_FILE.exists() is False, "previewing wrote to disk"


def test_cancel_puts_the_original_back(panel):
    import ui
    from core.theme import PRESETS

    # Matrix keeps the same background as Midnight - it only re-tints - so this
    # asserts on the accent, which every preset defines differently. Asserting
    # on BG here would have passed for the wrong reason and failed the first
    # time someone adds a preset that shares a background.
    panel._original = PRESETS["Midnight"]
    panel._preview(PRESETS["Matrix"])
    assert ui.C.PRI.lower() != PRESETS["Midnight"].accent.lower()

    panel._cancel()
    assert ui.C.BG == PRESETS["Midnight"].bg
    assert ui.C.PRI.lower() == PRESETS["Midnight"].accent.lower()


def test_a_broken_theme_does_not_break_the_panel(panel):
    class Junk:
        def __getattr__(self, item):
            raise AttributeError(item)

    panel._preview(Junk())     # must not raise


# ── font scale ──────────────────────────────────────────────────────────────

def test_the_slider_actually_changes_font_sizes(panel, qt):
    from PyQt6.QtWidgets import QLabel

    label = QLabel("probe")
    label.setFont(label.font())
    label.show()
    base = label.font().pointSizeF()

    panel._scale.setValue(140)
    assert label.font().pointSizeF() > base


def test_the_slider_reports_its_value(panel):
    panel._scale.setValue(125)
    assert panel._scale_value.text() == "125%"


# ── saving ──────────────────────────────────────────────────────────────────

def test_save_records_what_is_on_screen(panel):
    from core import theme as T
    from core.theme import PRESETS

    panel._preview(PRESETS["Aurora"])
    panel._scale.setValue(115)
    panel._choose_density("compact")
    panel._save()

    saved = T.load()
    assert saved["preset"] == "Aurora"
    assert saved["font_scale"] == pytest.approx(1.15, abs=0.01)
    assert saved["density"] == "compact"


def test_reopening_shows_what_was_saved(panel, qt):
    from ui.theme_panel import ThemePanel

    panel._scale.setValue(130)
    panel._choose_density("comfortable")
    panel._save()

    reopened = ThemePanel()
    reopened.show_and_load()
    assert reopened._scale.value() == 130
    assert reopened._density_buttons["comfortable"].isChecked()


def test_saving_writes_a_file_that_is_actually_json(panel):
    import json
    from core import theme as T

    panel._save()
    data = json.loads(T.THEME_FILE.read_text(encoding="utf-8"))
    assert "preset" in data and "font_scale" in data and "density" in data


def test_reset_returns_to_the_default(panel):
    import ui
    from core.theme import DEFAULT_THEME, PRESETS

    panel._preview(PRESETS["Rose"])
    panel._reset()
    assert ui.C.BG == PRESETS[DEFAULT_THEME].bg