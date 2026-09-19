"""Additive icon-mix tests: emoji strip + icon set on real app labels (offscreen)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

APP_LABELS = [
    "🔊 VOICE", "📷 CAM", "⚡ PING", "🧹 CLEAR", "🎨 HUD", "🪟 PIP",
    "🎙  MICROPHONE ACTIVE", "✋  INTERRUPT  [ESC]", "◉  REMOTE CONTROL",
    "⛶  FULLSCREEN  [F11]", "⚙  HUD STUDIO & CUSTOMISE",
    "🌐  LLM PROVIDERS & KEYS", "🎧  AUDIO DEVICES", "🧠  MEMORY",
    "🧩  PLUGINS", "↩ Undo", "⏰ Remind me", "📋 Copy", "✕  CLOSE",
    "▸  SAVE", "⚡ TEST", "🔄  REFRESH ALL TELEMETRY",
]

# words that must survive stripping (meaning preserved)
_MUST_KEEP = ["VOICE", "CAM", "PING", "CLEAR", "HUD", "PIP", "MICROPHONE",
              "INTERRUPT", "REMOTE", "FULLSCREEN", "STUDIO", "PROVIDERS",
              "AUDIO", "MEMORY", "PLUGINS", "Undo", "Remind", "Copy",
              "CLOSE", "SAVE", "TEST", "REFRESH"]


def test_strip_keeps_words():
    from ui_icons import strip_emoji
    for label in APP_LABELS:
        out = strip_emoji(label)
        assert isinstance(out, str)
    # spot checks
    assert strip_emoji("🔊 VOICE") == "VOICE"
    assert strip_emoji("🎙  MICROPHONE ACTIVE") == "MICROPHONE ACTIVE"
    assert strip_emoji("✋  INTERRUPT  [ESC]") == "INTERRUPT [ESC]"
    assert "Undo" in strip_emoji("↩ Undo")


def test_icons_set_on_app_labels():
    from PyQt6.QtWidgets import QApplication, QPushButton
    app = QApplication.instance() or QApplication([])
    from ui_icons import set_btn_icon, strip_emoji, BUTTON_ICONS
    for label in APP_LABELS:
        b = QPushButton(label)
        key = next((k for k in BUTTON_ICONS if k in label.upper()), None)
        if key is None:
            continue
        assert set_btn_icon(b, BUTTON_ICONS[key], 16) is True, label
        b.setText(strip_emoji(b.text()))
    # every surviving word still meaningful: spot check a few end states
    b = QPushButton("🔊 VOICE")
    set_btn_icon(b, "speaker", 16)
    b.setText(strip_emoji(b.text()))
    assert b.text() == "VOICE" and not b.icon().isNull()
