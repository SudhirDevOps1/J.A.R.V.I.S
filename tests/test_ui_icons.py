"""Additive icon-set tests (offscreen-safe, no window shown)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_icon_glyphs_render():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from ui_icons import get_icon, BUTTON_ICONS, set_btn_icon
    from PyQt6.QtWidgets import QPushButton
    seen = set(BUTTON_ICONS.values()) | {"mic", "home", "send", "thumb_up", "thumb_down"}
    for glyph in seen:
        assert not get_icon(glyph, 18).isNull(), glyph
    b = QPushButton("TEST")
    set_btn_icon(b, "bolt", 16)
    assert not b.icon().isNull()
    # unknown glyph -> safe fallback path (no crash)
    set_btn_icon(b, "nope_xyz", 16)


def test_button_map_covers_quick_actions():
    from ui_icons import BUTTON_ICONS
    for key in ("VOICE", "CAM", "PING", "CLEAR", "HUD", "CONFIRM", "CANCEL", "SAVE"):
        assert key in BUTTON_ICONS, key
