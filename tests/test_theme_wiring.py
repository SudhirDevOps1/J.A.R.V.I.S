"""
tests/test_theme_wiring.py - The theme system reaching class C.

core/theme.py being correct is worth nothing if class C never changes. These
tests assert the link between the two, which is the part that can rot quietly:
apply_theme returns True, nobody checks that C actually moved.

Qt runs offscreen. ui.py is a 10,000-line module with heavy import-time work,
so these are deliberately few and behavioural.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def ui_module():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import ui
    ui._TEST_APP = app
    return ui


@pytest.fixture(autouse=True)
def restore_palette(ui_module):
    """Every test that changes C puts it back, or the next one inherits it."""
    from core import theme as T
    before = {k: getattr(ui_module.C, k) for k in
              ("BG", "PANEL", "PANEL2", "BORDER", "BORDER_B", "TEXT",
               "TEXT_DIM", "TEXT_DIM", "TEXT_MED", "WHITE", "BAR_BG",
               "PRI", "PRI_DIM", "PRI_GHO")}
    yield
    for k, v in before.items():
        setattr(ui_module.C, k, v)


def test_apply_theme_moves_the_real_palette(ui_module):
    from core import theme as T

    assert ui_module.C.BG != T.PRESETS["Daylight"].bg
    assert ui_module.apply_theme(T.PRESETS["Daylight"]) is True
    assert ui_module.C.BG == T.PRESETS["Daylight"].bg
    assert ui_module.C.TEXT == T.PRESETS["Daylight"].text


def test_a_light_theme_actually_flips_the_background(ui_module):
    """The point of having a light mode. If BG stays dark while TEXT goes
    dark too, the interface becomes unreadable rather than light."""
    from core import theme as T

    ui_module.apply_theme(T.PRESETS["Daylight"])
    assert ui_module.C.BG.lower() == T.PRESETS["Daylight"].bg.lower()


def test_every_preset_applies_without_error(ui_module):
    from core import theme as T

    for name, preset in T.PRESETS.items():
        assert ui_module.apply_theme(preset) is True, name


def test_applying_a_theme_changes_the_accent(ui_module):
    from core import theme as T

    ui_module.apply_theme(T.PRESETS["Rose"])
    assert ui_module.C.PRI.lower() == T.PRESETS["Rose"].accent.lower()


def test_the_accent_derivations_move_with_it(ui_module):
    """PRI_DIM and PRI_GHO are derived, not copied. Leaving them behind is
    exactly how a themed interface ends up with one stale colour in a corner."""
    from core import theme as T

    ui_module.apply_theme(T.PRESETS["Ember"])
    assert ui_module.C.PRI_DIM != ui_module.C.PRI
    assert ui_module.C.PRI_GHO != ui_module.C.PRI_DIM


def test_a_broken_theme_is_refused_not_fatal(ui_module):
    """A bad theme must not stop the interface starting."""

    class Nonsense:
        def __getattr__(self, item):
            raise AttributeError(item)

    assert ui_module.apply_theme(Nonsense()) is False


# ── font scaling, scoped honestly ───────────────────────────────────────────

def test_font_rescaling_does_not_crash_without_widgets(ui_module):
    assert ui_module.rescale_all_fonts(1.2) is None


def test_font_rescaling_at_one_to_one_is_a_no_op(ui_module):
    """Rescaling by 1.0 must not mark widgets as already-scaled, or a later
    real rescale would be skipped."""
    from PyQt6.QtWidgets import QLabel

    label = QLabel("x")
    assert not hasattr(label, "_jarvis_base_point")
    ui_module.rescale_all_fonts(1.0)
    assert not hasattr(label, "_jarvis_base_point")


def test_font_rescaling_is_idempotent_not_compounding(ui_module):
    """Walking every widget and multiplying its size each time would grow the
    text on every theme change. This is the bug that makes a rescale feature
    unusable within a few clicks."""
    from PyQt6.QtWidgets import QLabel

    label = QLabel("rescale me")
    label.setFont(label.font())
    label.show()

    base = label.font().pointSizeF()
    ui_module.rescale_all_fonts(1.25)
    after_one = label.font().pointSizeF()
    ui_module.rescale_all_fonts(1.25)
    after_two = label.font().pointSizeF()

    assert after_one > base, "the first rescale did nothing"
    assert after_two == pytest.approx(after_one, abs=0.6), (
        f"repeated rescaling compounded: {base} -> {after_one} -> {after_two}"
    )


# ── loading from saved preferences ──────────────────────────────────────────

def test_theme_loads_from_preferences(tmp_path, ui_module, monkeypatch):
    from core import theme as T

    target = tmp_path / "ui_theme.json"
    monkeypatch.setattr(T, "THEME_FILE", target)
    T.save({"preset": "Paper", "font_scale": 1.0, "density": "cozy"})

    applied = ui_module.apply_theme_from_prefs(persist=False)
    assert applied is not None
    assert applied.name == "Paper"
    assert ui_module.C.BG == T.PRESETS["Paper"].bg


def test_missing_preferences_do_not_break_startup(tmp_path, ui_module, monkeypatch):
    """No theme file at all is the first-run case, not an error."""
    from core import theme as T

    monkeypatch.setattr(T, "THEME_FILE", tmp_path / "nothing-here.json")
    applied = ui_module.apply_theme_from_prefs(persist=False)
    assert applied is not None
    assert applied.name == T.DEFAULT_THEME


def test_a_corrupt_theme_file_does_not_break_startup(tmp_path, ui_module, monkeypatch):
    from core import theme as T

    target = tmp_path / "ui_theme.json"
    target.write_text("<<<not json>>>", encoding="utf-8")
    monkeypatch.setattr(T, "THEME_FILE", target)

    assert ui_module.apply_theme_from_prefs(persist=False) is not None