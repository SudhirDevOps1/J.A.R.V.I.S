"""
core/theme.py - The visual system, as data.

WHY THIS FILE EXISTS
--------------------
The accent system already worked: apply_ui_accent() re-derives the palette,
current_palette() snapshots it, retheme_all_widgets() repaints every widget
live, and the chosen colour persists in config. What was missing is that all of
that only ever produced the same dark teal, one fixed size, one fixed density.

`class C` in ui.py held ~20 hardcoded dark values and nothing could change them
except the accent hue. So "customise the look" really meant "pick a different
teal".

THE FOUR THINGS THAT WERE MISSING
---------------------------------
    light theme      there was no light mode at all
    presets          a free colour picker with no curated starting points
    font scale       every size was a literal in the source
    density          spacing was a literal in the source

THE PART THAT ACTUALLY MATTERS
------------------------------
audit() computes WCAG contrast for every text/background pair in the palette
and says which ones fail.

That is not decoration. It is the difference between a theme that looks good
in a screenshot and a theme somebody can read at 2am on a bad monitor. A
customisable theme system without a contrast floor will let a user pick a
palace they cannot read, and it will do it silently.

This is why every preset below has been through audit() rather than chosen by
eye. See tests/test_theme.py, which asserts the ratio arithmetic against known
WCAG values rather than against this file's own output.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, NamedTuple, Optional


# ── colour maths ────────────────────────────────────────────────────────────

def _srgb_to_linear(channel: float) -> float:
    """WCAG's sRGB transfer function.

    Not an approximation. The formula differs above and below 0.03928, and
    using the wrong branch changes every ratio computed here.
    """
    c = channel / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_colour: str) -> float:
    """WCAG relative luminance, 0.0 (black) to 1.0 (white)."""
    h = str(hex_colour or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) != 6:
        raise ValueError(f"not a hex colour: {hex_colour!r}")
    r = _srgb_to_linear(int(h[0:2], 16))
    g = _srgb_to_linear(int(h[2:4], 16))
    b = _srgb_to_linear(int(h[4:6], 16))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG contrast ratio, 1.0 to 21.0. Order does not matter."""
    a, b = relative_luminance(fg), relative_luminance(bg)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


# ── theme model ─────────────────────────────────────────────────────────────

class Theme(NamedTuple):
    name: str
    mode: str                 # "dark" | "light"
    accent: str
    bg: str
    panel: str
    panel2: str
    border: str
    border_b: str
    text: str
    text_dim: str
    text_med: str
    white: str
    bar_bg: str
    font_scale: float = 1.0
    density: str = "cozy"     # compact | cozy | comfortable

    def as_dict(self) -> dict:
        return dict(self._asdict())

    @property
    def is_dark(self) -> bool:
        return self.mode == "dark"


# ── density ─────────────────────────────────────────────────────────────────

# Line height and vertical padding, as multipliers applied at render time.
# Compact suits a small screen, comfortable suits long-form reading.
DENSITY = {
    "compact":     {"pad": 6,  "gap": 4,  "line": 1.25, "radius": 4},
    "cozy":        {"pad": 10, "gap": 7,  "line": 1.40, "radius": 6},
    "comfortable": {"pad": 14, "gap": 10, "line": 1.55, "radius": 9},
}

FONT_SCALES = {"small": 0.90, "normal": 1.0, "large": 1.12, "xlarge": 1.25}
FONT_SCALE_BOUNDS = (0.80, 1.60)


# ── presets ─────────────────────────────────────────────────────────────────

_MIDNIGHT = dict(
    name="Midnight", mode="dark", accent="#00d4ff",
    bg="#04080e", panel="#07121e", panel2="#0a1928",
    border="#132d42", border_b="#1a4666",
    text="#b8f4ff", text_dim="#4e8fa8", text_med="#7ec6dc",
    white="#e8f8fc", bar_bg="#0a1c2a",
)

PRESETS: dict[str, Theme] = {}


def _add(name: str, **overrides) -> None:
    base = dict(_MIDNIGHT)
    base["name"] = name        # the display name, not the dict key
    base.update(overrides)
    PRESETS[name] = Theme(**base)


# Dark. Each one keeps the same value structure as the original so that
# apply_ui_accent() and the widget stylesheets keep working unchanged.
_add("Midnight")
_add("Aurora", accent="#7c5cff",
     panel="#0d0a1c", panel2="#140f2b", border="#241a4d", border_b="#3a2a80",
     text="#e2dcff", text_dim="#7d6fb8", text_med="#a99ce0",
     white="#f2efff", bar_bg="#150f30")
_add("Ember", accent="#ff7a18",
     panel="#150c06", panel2="#1e1109", border="#4a2a10", border_b="#7a451a",
     text="#ffeadb", text_dim="#b07a52", text_med="#e0a97c",
     white="#fff5ec", bar_bg="#22150c")
_add("Matrix", accent="#22e07a",
     panel="#03130b", panel2="#061d11", border="#0f4527", border_b="#1a6b3d",
     text="#ccffe4", text_dim="#4aa973", text_med="#8fd6b0",
     white="#e8fff2", bar_bg="#0a2417")
_add("Rose", accent="#ff4d8d",
     panel="#160a11", panel2="#1f0d17", border="#4d1c33", border_b="#7a2c51",
     text="#ffd9e6", text_dim="#b06a85", text_med="#e3a3bd",
     white="#fff0f6", bar_bg="#25101c")

# Light. These are not the dark palette inverted. Inverting a dark theme
# produces pastels that glare; a light theme needs its own values, which is why
# the audit below matters more here than on the dark ones.
_add("Daylight", mode="light", accent="#0a6fd4",
     bg="#f4f7fb", panel="#ffffff", panel2="#eef3f9",
     border="#d3dde8", border_b="#b6c6d8",
     text="#16232f", text_dim="#5b6b7c", text_med="#3d4f61",
     white="#ffffff", bar_bg="#e7edf5")
_add("Paper", mode="light", accent="#8a5a2b",
     bg="#f7f4ef", panel="#fffdfa", panel2="#f0ebe2",
     border="#ded5c8", border_b="#c2b4a0",
     text="#241f18", text_dim="#6b6155", text_med="#4a4136",
     white="#ffffff", bar_bg="#eae3d8")


DEFAULT_THEME = "Midnight"


# ── contrast audit ──────────────────────────────────────────────────────────

# (foreground, background, minimum ratio, what it is for)
# 4.5 is WCAG AA for normal text, 3.0 is AA for large text and for UI borders.
AUDIT_PAIRS = [
    ("text",      "bg",       4.5, "body text on the background"),
    ("text",      "panel",    4.5, "body text in a panel"),
    ("text",      "panel2",   4.5, "body text in a raised panel"),
    ("text_med",  "panel",    4.5, "secondary text in a panel"),
    ("text_dim",  "panel",    3.0, "dimmed labels in a panel"),
    ("accent",    "bg",       3.0, "accent on the background"),
    ("accent",    "panel",    3.0, "accent inside a panel"),
    ("border_b",  "panel",    1.5, "visible panel edge"),
]


def audit(theme: Theme) -> list[dict]:
    """Every contrast failure in a theme, as data. Empty list means it passes."""
    problems = []
    for fg_key, bg_key, minimum, purpose in AUDIT_PAIRS:
        fg = getattr(theme, fg_key)
        bg = getattr(theme, bg_key)
        try:
            ratio = contrast_ratio(fg, bg)
        except ValueError:
            problems.append({
                "pair": f"{fg_key}/{bg_key}",
                "minimum": minimum,
                "actual": 0.0,
                "purpose": purpose,
                "reason": "not a valid hex colour",
            })
            continue
        if ratio < minimum:
            problems.append({
                "pair": f"{fg_key}/{bg_key}",
                "minimum": minimum,
                "actual": round(ratio, 2),
                "purpose": purpose,
                "reason": f"{ratio:.2f}:1 is below the {minimum}:1 minimum",
            })
    return problems


def summarise(theme: Theme) -> str:
    problems = audit(theme)
    if not problems:
        return f"{theme.name}: contrast OK on all {len(AUDIT_PAIRS)} pairs."
    lines = [f"{theme.name}: {len(problems)} contrast problem(s)."]
    for p in problems:
        lines.append(f"  • {p['pair']} ({p['purpose']}) — {p['reason']}")
    return "\n".join(lines)


# ── resolution and persistence ──────────────────────────────────────────────

def _base_dir() -> Path:
    if getattr(__import__("sys"), "frozen", False):
        return Path(__import__("sys").executable).parent
    return Path(__file__).resolve().parent.parent


THEME_FILE = _base_dir() / "config" / "ui_theme.json"


def clamp_font_scale(value) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 1.0
    lo, hi = FONT_SCALE_BOUNDS
    return max(lo, min(hi, v))


def clamp_density(value) -> str:
    v = str(value or "").strip().lower()
    return v if v in DENSITY else "cozy"


def build(preset: str = DEFAULT_THEME, accent: Optional[str] = None,
          font_scale: float = 1.0, density: str = "cozy") -> Theme:
    """A theme from a preset, with optional overrides.

    Falls back to the default preset for an unknown name rather than raising.
    A typo in a config file must not stop the interface from starting.
    """
    theme = PRESETS.get(str(preset or "").strip(), PRESETS[DEFAULT_THEME])
    fields = theme._asdict()
    if accent:
        a = str(accent).strip().lower()
        if len(a) == 7 and a.startswith("#"):
            try:
                int(a[1:], 16)
                fields["accent"] = a
            except ValueError:
                pass
    fields["font_scale"] = clamp_font_scale(font_scale)
    fields["density"] = clamp_density(density)
    return Theme(**fields)


def load() -> dict:
    """Saved theme preferences. Always returns a usable dict."""
    defaults = {
        "preset": DEFAULT_THEME,
        "accent": "",
        "font_scale": 1.0,
        "density": "cozy",
    }
    try:
        if THEME_FILE.exists():
            data = json.loads(THEME_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                defaults.update({k: v for k, v in data.items() if k in defaults})
    except Exception:
        # An unreadable theme file must not stop the app starting.
        pass
    return defaults


def save(prefs: dict) -> bool:
    """Persist theme preferences. Never raises."""
    try:
        current = load()
        for key in ("preset", "accent", "font_scale", "density"):
            if key in (prefs or {}):
                current[key] = prefs[key]
        current["font_scale"] = clamp_font_scale(current.get("font_scale"))
        current["density"] = clamp_density(current.get("density"))
        THEME_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = THEME_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(current, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(THEME_FILE))
        return True
    except Exception:
        return False


def current() -> Theme:
    """The saved theme, resolved. Safe to call before any UI exists."""
    prefs = load()
    return build(prefs.get("preset", DEFAULT_THEME),
                 prefs.get("accent"),
                 prefs.get("font_scale", 1.0),
                 prefs.get("density", "cozy"))


__all__ = [
    "Theme", "PRESETS", "DEFAULT_THEME", "DENSITY", "FONT_SCALES",
    "contrast_ratio", "relative_luminance", "audit", "summarise",
    "build", "load", "save", "current",
    "clamp_font_scale", "clamp_density",
]