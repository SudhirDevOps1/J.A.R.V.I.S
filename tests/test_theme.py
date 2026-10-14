"""
tests/test_theme.py - The theme system, and the contrast floor under it.

WHY THE CONTRAST TESTS MATTER MORE THAN THE PRETESTS
-----------------------------------------------------
A theme system that lets someone choose an unreadable palette and says nothing
is worse than no theme system. The presets here are the answer to "make it
premium": they were all run through audit() rather than picked by eye.

The contrast arithmetic is asserted against PUBLISHED WCAG values, not against
this module's own output. Asserting contrast_ratio('#767676', '#ffffff') == 4.54
is a real check; asserting it equals whatever this file happens to produce is a
tautology that passes even if the whole function is wrong.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from core.theme import (  # noqa: E402
    DENSITY,
    DEFAULT_THEME,
    FONT_SCALE_BOUNDS,
    PRESETS,
    audit,
    build,
    clamp_density,
    clamp_font_scale,
    contrast_ratio,
    relative_luminance,
    summarise,
)


# ── the arithmetic, against known answers ───────────────────────────────────

def test_contrast_extremes_match_wcag():
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)
    assert contrast_ratio("#ffffff", "#000000") == pytest.approx(21.0, abs=0.01)


def test_identical_colours_have_no_contrast():
    for c in ("#ffffff", "#000000", "#7c5cff", "#00d4ff"):
        assert contrast_ratio(c, c) == pytest.approx(1.0, abs=0.01)


def test_known_wcag_boundary_value():
    """#767676 on white is the canonical 'just passes AA' grey, 4.54:1."""
    assert contrast_ratio("#767676", "#ffffff") == pytest.approx(4.54, abs=0.05)


def test_contrast_is_symmetric():
    """Order must not matter, or half the audit table is meaningless."""
    assert (contrast_ratio("#123456", "#fedcba")
            == contrast_ratio("#fedcba", "#123456"))


def test_relative_luminance_endpoints():
    assert relative_luminance("#000000") == pytest.approx(0.0, abs=1e-6)
    assert relative_luminance("#ffffff") == pytest.approx(1.0, abs=1e-6)


def test_short_hex_is_expanded_not_rejected():
    assert contrast_ratio("#fff", "#000") == pytest.approx(21.0, abs=0.01)


def test_a_bad_colour_is_an_error_not_a_wrong_number():
    """Silently returning 1.0 for a malformed colour would turn a typo in a
    config file into 'this theme is unreadable', which is worse than crashing."""
    for bad in ("nope", "#12345", "", "#gggggg", None):
        with pytest.raises(ValueError):
            contrast_ratio(bad, "#ffffff")


# ── every preset must be readable ───────────────────────────────────────────

@pytest.mark.parametrize("name", sorted(PRESETS))
def test_every_preset_passes_its_own_contrast_audit(name):
    problems = audit(PRESETS[name])
    assert not problems, (
        f"{name} has unreadable pairs:\n" + summarise(PRESETS[name])
    )


def test_the_original_theme_is_still_one_of_them():
    """Whatever was there before must still be selectable, or this is a
    downgrade dressed as an upgrade."""
    assert DEFAULT_THEME in PRESETS
    assert PRESETS[DEFAULT_THEME].accent == "#00d4ff"


def test_both_modes_exist():
    """There was no light theme at all. Having one that fails contrast would be
    worse than not having one."""
    modes = {t.mode for t in PRESETS.values()}
    assert "dark" in modes
    assert "light" in modes


def test_light_presets_are_not_inverted_dark_ones():
    """A mechanical inversion of a dark theme produces pastels that glare.

    Checked as luminance, which is what 'glaring' means: a light theme's
    background must actually be light, not merely labelled light."""
    for name, theme in PRESETS.items():
        if theme.mode != "light":
            continue
        bg = relative_luminance(theme.bg)
        assert bg > 0.5, (
            f"{name} claims to be light but its background luminance is {bg:.2f}"
        )


def test_dark_presets_are_actually_dark():
    for name, theme in PRESETS.items():
        if theme.mode != "dark":
            continue
        assert relative_luminance(theme.bg) < 0.1, f"{name} background is not dark"


def test_every_preset_has_the_same_fields():
    """ui.py stylesheets read C.BORDER_B and friends. A preset missing one
    would raise deep inside a widget's paintEvent, not at load time."""
    expected = set(PRESETS[DEFAULT_THEME]._asdict())
    for name, theme in PRESETS.items():
        assert set(theme._asdict()) == expected, f"{name} has a different shape"


# ── the audit catches what it exists to catch ───────────────────────────────

def test_audit_finds_a_deliberately_unreadable_theme():
    """A positive control. Without it, an audit that always returned [] would
    pass every preset test above."""
    base = PRESETS[DEFAULT_THEME]
    broken = base._replace(text="#0a1928")   # text almost identical to the panel
    problems = audit(broken)
    assert problems, "an unreadable theme was not detected"
    assert any(p["pair"].startswith("text/") for p in problems)


def test_audit_result_is_data_not_just_a_string():
    problems = audit(PRESETS[DEFAULT_THEME]._replace(text_dim="#07121e"))
    assert problems
    p = problems[0]
    assert {"pair", "minimum", "actual", "purpose", "reason"} <= set(p)


# ── building and overriding ─────────────────────────────────────────────────

def test_build_returns_the_named_preset():
    t = build("Ember")
    assert t.name == "Ember"
    assert t.accent == PRESETS["Ember"].accent


def test_build_falls_back_instead_of_raising():
    """A typo in a config file must not stop the interface from starting."""
    assert build("NotATheme").name == DEFAULT_THEME
    assert build(None).name == DEFAULT_THEME
    assert build("").name == DEFAULT_THEME


def test_a_custom_accent_overrides_the_preset():
    t = build("Midnight", accent="#ff00ff")
    assert t.accent == "#ff00ff"


def test_a_malformed_accent_is_ignored_not_fatal():
    assert build("Midnight", accent="banana").accent == PRESETS["Midnight"].accent
    assert build("Midnight", accent="#ff").accent == PRESETS["Midnight"].accent


def test_presets_are_not_mutated_by_an_override():
    """A build with a custom accent must not write through to the preset."""
    before = PRESETS["Midnight"].accent
    build("Midnight", accent="#ff00ff")
    assert PRESETS["Midnight"].accent == before


# ── clamping ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("given,expected", [
    (0.5, FONT_SCALE_BOUNDS[0]),
    (99, FONT_SCALE_BOUNDS[1]),
    (1.25, 1.25),
    ("not a number", 1.0),
    (None, 1.0),
])
def test_font_scale_is_clamped(given, expected):
    assert clamp_font_scale(given) == pytest.approx(expected)


def test_density_falls_back_instead_of_raising():
    assert clamp_density("compact") == "compact"
    assert clamp_density("COMFORTABLE") == "comfortable"
    assert clamp_density("nonsense") == "cozy"
    assert clamp_density(None) == "cozy"


def test_every_density_option_is_usable():
    for name, values in DENSITY.items():
        assert {"pad", "gap", "line", "radius"} <= set(values), name
        assert values["line"] >= 1.0, f"{name} line height would overlap text"


def test_density_is_ordered_compact_to_comfortable():
    """Otherwise 'compact' could be the roomiest and the names would lie."""
    order = ["compact", "cozy", "comfortable"]
    for a, b in zip(order, order[1:]):
        assert DENSITY[a]["pad"] < DENSITY[b]["pad"]
        assert DENSITY[a]["line"] < DENSITY[b]["line"]


# ── persistence never takes the app down ────────────────────────────────────

def test_save_and_load_round_trip(tmp_path, monkeypatch):
    import core.theme as theme

    target = tmp_path / "ui_theme.json"
    monkeypatch.setattr(theme, "THEME_FILE", target)

    assert theme.save({"preset": "Aurora", "font_scale": 1.2,
                       "density": "compact", "accent": "#123456"})
    loaded = theme.load()
    assert loaded["preset"] == "Aurora"
    assert loaded["font_scale"] == pytest.approx(1.2)
    assert loaded["density"] == "compact"
    assert loaded["accent"] == "#123456"


def test_save_clamps_on_the_way_in(tmp_path, monkeypatch):
    import core.theme as theme

    monkeypatch.setattr(theme, "THEME_FILE", tmp_path / "ui_theme.json")
    theme.save({"font_scale": 500, "density": "wat"})
    loaded = theme.load()
    assert loaded["font_scale"] == FONT_SCALE_BOUNDS[1]
    assert loaded["density"] == "cozy"


def test_a_corrupt_theme_file_does_not_stop_startup(tmp_path, monkeypatch):
    import core.theme as theme

    target = tmp_path / "ui_theme.json"
    target.write_text("{ this is not json", encoding="utf-8")
    monkeypatch.setattr(theme, "THEME_FILE", target)

    prefs = theme.load()
    assert prefs["preset"] == DEFAULT_THEME
    assert theme.current().name == DEFAULT_THEME


def test_current_resolves_a_saved_theme(tmp_path, monkeypatch):
    import core.theme as theme

    monkeypatch.setattr(theme, "THEME_FILE", tmp_path / "ui_theme.json")
    theme.save({"preset": "Daylight"})
    t = theme.current()
    assert t.name == "Daylight"
    assert t.mode == "light"