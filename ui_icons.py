"""Vector icon set for J.A.R.V.I.S. HUD — website-style real icons, zero dependencies.

Why not emoji: emoji glyphs render as empty boxes on systems without color-emoji
fonts (many Windows/Linux configs). Why not QStyle standards: native icons clash
with the neon HUD language. So: one consistent stroke-style vector family drawn
with QPainter on transparent pixmaps — crisp at any DPI, tintable to the theme.

Usage:  btn.setIcon(get_icon("mic", 18, "#8ffcff")); btn.setIconSize(QSize(18, 18))
Text labels are NEVER removed by this module — icons sit beside text.
Everything is fail-safe: any error returns an empty QIcon (button keeps text).
"""
from __future__ import annotations

_CACHE: dict = {}


def _pen(p, color: str, w: float = 2.0):
    from PyQt6.QtGui import QPen, QColor
    from PyQt6.QtCore import Qt
    pen = QPen(QColor(color))
    pen.setWidthF(float(w))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)


def _blank(size: int):
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtCore import Qt
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    return px


def _draw(name: str, size: int, color: str):
    """Draw glyph `name` on transparent pixmap. Never raises (caller guards)."""
    from PyQt6.QtGui import QPainter, QPainterPath, QBrush, QColor
    from PyQt6.QtCore import Qt, QRectF, QPointF
    px = _blank(size)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    m = size / 24.0  # 24-unit grid
    cx, cy = size / 2.0, size / 2.0
    _pen(p, color, 2.0 * m)
    p.setBrush(Qt.BrushStyle.NoBrush)

    if name == "mic":
        p.drawRoundedRect(QRectF(cx - 4 * m, 3 * m, 8 * m, 11 * m), 4 * m, 4 * m)
        path = QPainterPath(QPointF(cx - 7 * m, 12 * m))
        path.quadTo(QPointF(cx - 7 * m, 19 * m), QPointF(cx, 19 * m))
        path.quadTo(QPointF(cx + 7 * m, 19 * m), QPointF(cx + 7 * m, 12 * m))
        p.drawPath(path)
        p.drawLine(QPointF(cx, 19 * m), QPointF(cx, 22 * m))
    elif name == "mic_off":
        p.drawRoundedRect(QRectF(cx - 4 * m, 3 * m, 8 * m, 11 * m), 4 * m, 4 * m)
        p.drawLine(QPointF(4 * m, 4 * m), QPointF(20 * m, 20 * m))
    elif name == "cam":
        p.drawRoundedRect(QRectF(2.5 * m, 7 * m, 13 * m, 10 * m), 2 * m, 2 * m)
        p.drawLine(QPointF(15.5 * m, 10 * m), QPointF(21 * m, 7 * m))
        p.drawLine(QPointF(15.5 * m, 14 * m), QPointF(21 * m, 17 * m))
        p.drawLine(QPointF(21 * m, 7 * m), QPointF(21 * m, 17 * m))
        p.drawEllipse(QRectF(6.5 * m, 9.5 * m, 5 * m, 5 * m))
    elif name == "home":
        p.drawLine(QPointF(3 * m, 12 * m), QPointF(12 * m, 4 * m))
        p.drawLine(QPointF(12 * m, 4 * m), QPointF(21 * m, 12 * m))
        p.drawLine(QPointF(5.5 * m, 10.5 * m), QPointF(5.5 * m, 20 * m))
        p.drawLine(QPointF(18.5 * m, 10.5 * m), QPointF(18.5 * m, 20 * m))
        p.drawLine(QPointF(5.5 * m, 20 * m), QPointF(18.5 * m, 20 * m))
        p.drawLine(QPointF(10 * m, 20 * m), QPointF(10 * m, 15.5 * m))
        p.drawLine(QPointF(14 * m, 20 * m), QPointF(14 * m, 15.5 * m))
        p.drawLine(QPointF(10 * m, 15.5 * m), QPointF(14 * m, 15.5 * m))
    elif name == "send":
        p.drawLine(QPointF(3 * m, 12 * m), QPointF(21 * m, 3 * m))
        p.drawLine(QPointF(21 * m, 3 * m), QPointF(14 * m, 21 * m))
        p.drawLine(QPointF(14 * m, 21 * m), QPointF(11 * m, 14 * m))
        p.drawLine(QPointF(11 * m, 14 * m), QPointF(3 * m, 12 * m))
        p.drawLine(QPointF(11 * m, 14 * m), QPointF(21 * m, 3 * m))
    elif name == "speaker":
        p.drawLine(QPointF(4 * m, 10 * m), QPointF(8 * m, 10 * m))
        p.drawLine(QPointF(8 * m, 10 * m), QPointF(12 * m, 5 * m))
        p.drawLine(QPointF(12 * m, 5 * m), QPointF(12 * m, 19 * m))
        p.drawLine(QPointF(12 * m, 19 * m), QPointF(8 * m, 14 * m))
        p.drawLine(QPointF(8 * m, 14 * m), QPointF(4 * m, 14 * m))
        p.drawLine(QPointF(4 * m, 14 * m), QPointF(4 * m, 10 * m))
        p.drawArc(QRectF(13 * m, 8.5 * m, 4 * m, 7 * m), int(-60 * 16), int(120 * 16))
        p.drawArc(QRectF(13 * m, 6 * m, 8 * m, 12 * m), int(-55 * 16), int(110 * 16))
    elif name == "bolt":
        p.drawLine(QPointF(13 * m, 2.5 * m), QPointF(7 * m, 13.5 * m))
        p.drawLine(QPointF(7 * m, 13.5 * m), QPointF(11.5 * m, 13.5 * m))
        p.drawLine(QPointF(11.5 * m, 13.5 * m), QPointF(9.5 * m, 21.5 * m))
        p.drawLine(QPointF(9.5 * m, 21.5 * m), QPointF(17 * m, 10.5 * m))
        p.drawLine(QPointF(17 * m, 10.5 * m), QPointF(12.5 * m, 10.5 * m))
        p.drawLine(QPointF(12.5 * m, 10.5 * m), QPointF(13 * m, 2.5 * m))
    elif name == "trash":
        p.drawLine(QPointF(5 * m, 7 * m), QPointF(19 * m, 7 * m))
        p.drawLine(QPointF(7 * m, 7 * m), QPointF(8 * m, 20 * m))
        p.drawLine(QPointF(17 * m, 7 * m), QPointF(16 * m, 20 * m))
        p.drawLine(QPointF(8 * m, 20 * m), QPointF(16 * m, 20 * m))
        p.drawLine(QPointF(9.5 * m, 4.5 * m), QPointF(14.5 * m, 4.5 * m))
        p.drawLine(QPointF(12 * m, 4.5 * m), QPointF(12 * m, 2.5 * m))
        p.drawLine(QPointF(11 * m, 10.5 * m), QPointF(11 * m, 17 * m))
        p.drawLine(QPointF(13 * m, 10.5 * m), QPointF(13 * m, 17 * m))
    elif name == "palette":
        p.drawEllipse(QRectF(3 * m, 3 * m, 18 * m, 18 * m))
        for dx, dy in ((-4, -3), (1, -4), (4, 0), (-1, 3)):
            p.drawEllipse(QRectF(cx + dx * m - 1.2 * m, cy + dy * m - 1.2 * m, 2.4 * m, 2.4 * m))
    elif name == "hand":
        p.drawRoundedRect(QRectF(7 * m, 10 * m, 10 * m, 9 * m), 3 * m, 3 * m)
        for fx in (8.5, 11, 13.5, 16):
            p.drawLine(QPointF(fx * m, 10 * m), QPointF(fx * m, 4.5 * m))
        p.drawLine(QPointF(7 * m, 13 * m), QPointF(3.5 * m, 11 * m))
    elif name == "gear":
        p.drawEllipse(QRectF(cx - 7 * m, cy - 7 * m, 14 * m, 14 * m))
        for i in range(8):
            import math as _math
            a = _math.pi * i / 4.0
            x1, y1 = cx + 7 * m * _math.cos(a), cy + 7 * m * _math.sin(a)
            x2, y2 = cx + 10 * m * _math.cos(a), cy + 10 * m * _math.sin(a)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        p.drawEllipse(QRectF(cx - 2.5 * m, cy - 2.5 * m, 5 * m, 5 * m))
    elif name == "plug":
        p.drawLine(QPointF(9 * m, 2.5 * m), QPointF(9 * m, 8 * m))
        p.drawLine(QPointF(15 * m, 2.5 * m), QPointF(15 * m, 8 * m))
        p.drawRoundedRect(QRectF(7 * m, 8 * m, 10 * m, 8 * m), 2 * m, 2 * m)
        p.drawLine(QPointF(12 * m, 16 * m), QPointF(12 * m, 21.5 * m))
    elif name == "brain":
        p.drawEllipse(QRectF(cx - 8 * m, cy - 7 * m, 16 * m, 14 * m))
        p.drawLine(QPointF(cx, 5.5 * m), QPointF(cx, 18.5 * m))
        for dx, dy in ((-4, -2), (4, -3), (-4, 3), (4, 2)):
            p.drawEllipse(QRectF(cx + dx * m - 1.4 * m, cy + dy * m - 1.4 * m, 2.8 * m, 2.8 * m))
    elif name == "globe":
        p.drawEllipse(QRectF(cx - 8.5 * m, cy - 8.5 * m, 17 * m, 17 * m))
        p.drawEllipse(QRectF(cx - 4 * m, cy - 8.5 * m, 8 * m, 17 * m))
        p.drawLine(QPointF(cx - 8.5 * m, cy), QPointF(cx + 8.5 * m, cy))
    elif name == "headset":
        path = QPainterPath(QPointF(4.5 * m, 17 * m))
        path.quadTo(QPointF(4.5 * m, 5 * m), QPointF(12 * m, 5 * m))
        path.quadTo(QPointF(19.5 * m, 5 * m), QPointF(19.5 * m, 17 * m))
        p.drawPath(path)
        p.drawRoundedRect(QRectF(3 * m, 15 * m, 4 * m, 6 * m), 1.5 * m, 1.5 * m)
        p.drawRoundedRect(QRectF(17 * m, 15 * m, 4 * m, 6 * m), 1.5 * m, 1.5 * m)
    elif name == "bell":
        p.drawLine(QPointF(7 * m, 18 * m), QPointF(17 * m, 18 * m))
        path = QPainterPath(QPointF(7 * m, 18 * m))
        path.quadTo(QPointF(7.5 * m, 8 * m), QPointF(12 * m, 8 * m))
        path.quadTo(QPointF(16.5 * m, 8 * m), QPointF(17 * m, 18 * m))
        p.drawPath(path)
        p.drawLine(QPointF(10 * m, 8 * m), QPointF(10 * m, 5 * m))
        p.drawLine(QPointF(14 * m, 8 * m), QPointF(14 * m, 5 * m))
        p.drawEllipse(QRectF(11 * m, 19 * m, 2 * m, 2 * m))
    elif name == "check":
        p.drawLine(QPointF(5 * m, 13 * m), QPointF(10.5 * m, 18.5 * m))
        p.drawLine(QPointF(10.5 * m, 18.5 * m), QPointF(19 * m, 6 * m))
    elif name == "cross":
        p.drawLine(QPointF(6 * m, 6 * m), QPointF(18 * m, 18 * m))
        p.drawLine(QPointF(18 * m, 6 * m), QPointF(6 * m, 18 * m))
    elif name == "refresh":
        p.drawArc(QRectF(4 * m, 4 * m, 16 * m, 16 * m), int(40 * 16), int(270 * 16))
        p.drawLine(QPointF(19.5 * m, 4 * m), QPointF(19.5 * m, 10 * m))
        p.drawLine(QPointF(19.5 * m, 4 * m), QPointF(13.5 * m, 4 * m))
    elif name == "pin":
        p.drawEllipse(QRectF(cx - 6 * m, 3.5 * m, 12 * m, 12 * m))
        p.drawLine(QPointF(cx - 4.5 * m, 14 * m), QPointF(cx, 21 * m))
        p.drawLine(QPointF(cx + 4.5 * m, 14 * m), QPointF(cx, 21 * m))
        p.drawEllipse(QRectF(cx - 2 * m, 7.5 * m, 4 * m, 4 * m))
    elif name == "search":
        p.drawEllipse(QRectF(3.5 * m, 3.5 * m, 12 * m, 12 * m))
        p.drawLine(QPointF(13 * m, 13 * m), QPointF(20.5 * m, 20.5 * m))
    elif name == "folder":
        p.drawLine(QPointF(3 * m, 7 * m), QPointF(3 * m, 19 * m))
        p.drawLine(QPointF(3 * m, 19 * m), QPointF(21 * m, 19 * m))
        p.drawLine(QPointF(21 * m, 19 * m), QPointF(21 * m, 9 * m))
        p.drawLine(QPointF(21 * m, 9 * m), QPointF(13 * m, 9 * m))
        p.drawLine(QPointF(13 * m, 9 * m), QPointF(11.5 * m, 6.5 * m))
        p.drawLine(QPointF(11.5 * m, 6.5 * m), QPointF(3 * m, 6.5 * m))
        p.drawLine(QPointF(3 * m, 6.5 * m), QPointF(3 * m, 7 * m))
    elif name == "sparkle":
        p.drawLine(QPointF(12 * m, 2.5 * m), QPointF(12 * m, 21.5 * m))
        p.drawLine(QPointF(2.5 * m, 12 * m), QPointF(21.5 * m, 12 * m))
        p.drawLine(QPointF(5.5 * m, 5.5 * m), QPointF(18.5 * m, 18.5 * m))
        p.drawLine(QPointF(18.5 * m, 5.5 * m), QPointF(5.5 * m, 18.5 * m))
    elif name == "key":
        p.drawEllipse(QRectF(3.5 * m, 3.5 * m, 9 * m, 9 * m))
        p.drawLine(QPointF(10.5 * m, 10.5 * m), QPointF(20.5 * m, 20.5 * m))
        p.drawLine(QPointF(16.5 * m, 16.5 * m), QPointF(16.5 * m, 13.5 * m))
        p.drawLine(QPointF(19 * m, 19 * m), QPointF(19 * m, 16 * m))
    elif name == "phone":
        p.drawRoundedRect(QRectF(7 * m, 2.5 * m, 10 * m, 19 * m), 2.5 * m, 2.5 * m)
        p.drawLine(QPointF(11 * m, 19 * m), QPointF(13 * m, 19 * m))
    elif name == "expand":
        for x1, y1, x2, y2 in ((3, 8, 3, 3), (3, 3, 8, 3), (16, 3, 21, 3),
                               (21, 3, 21, 8), (21, 16, 21, 21), (21, 21, 16, 21),
                               (8, 21, 3, 21), (3, 21, 3, 16)):
            p.drawLine(QPointF(x1 * m, y1 * m), QPointF(x2 * m, y2 * m))
    elif name == "link":
        p.drawRoundedRect(QRectF(3 * m, 9 * m, 10 * m, 7 * m), 3 * m, 3 * m)
        p.drawRoundedRect(QRectF(11 * m, 8 * m, 10 * m, 7 * m), 3 * m, 3 * m)
    elif name == "power":
        p.drawArc(QRectF(5 * m, 6 * m, 14 * m, 14 * m), int(40 * 16), int(260 * 16))
        p.drawLine(QPointF(12 * m, 2.5 * m), QPointF(12 * m, 12 * m))
    elif name == "thumb_up":
        p.drawRoundedRect(QRectF(8 * m, 9 * m, 10 * m, 10 * m), 2 * m, 2 * m)
        p.drawLine(QPointF(8 * m, 9 * m), QPointF(8 * m, 5 * m))
        p.drawLine(QPointF(8 * m, 5 * m), QPointF(11 * m, 5 * m))
        p.drawLine(QPointF(11 * m, 5 * m), QPointF(10 * m, 9 * m))
        p.drawLine(QPointF(5.5 * m, 9 * m), QPointF(5.5 * m, 19 * m))
    elif name == "thumb_down":
        p.drawRoundedRect(QRectF(8 * m, 5 * m, 10 * m, 10 * m), 2 * m, 2 * m)
        p.drawLine(QPointF(8 * m, 15 * m), QPointF(8 * m, 19 * m))
        p.drawLine(QPointF(8 * m, 19 * m), QPointF(11 * m, 19 * m))
        p.drawLine(QPointF(11 * m, 19 * m), QPointF(10 * m, 15 * m))
        p.drawLine(QPointF(5.5 * m, 5 * m), QPointF(5.5 * m, 15 * m))
    else:  # unknown → sparkle dot
        p.drawEllipse(QRectF(cx - 3 * m, cy - 3 * m, 6 * m, 6 * m))
    p.end()
    return px


def get_icon(name: str, size: int = 18, color: str = "#8ffcff"):
    """Return QIcon for `name`. Empty QIcon on any failure (text stays).

    Needs a QApplication instance; headless-import safe (QIcon() fallback).
    Results cached per (name, size, color).
    """
    from PyQt6.QtGui import QIcon
    key = (str(name or "").lower(), int(size), str(color or "").lower())
    if key in _CACHE:
        return _CACHE[key]
    try:
        from PyQt6.QtWidgets import QApplication
        if QApplication.instance() is None:
            raise RuntimeError("no app")
        icon = QIcon(_draw(key[0], key[1], key[2]))
    except Exception:
        try:
            icon = QIcon()
        except Exception:
            icon = None
    _CACHE[key] = icon
    return icon


def set_btn_icon(btn, name: str, size: int = 18, color: str | None = None) -> bool:
    """ADDITIVE one-liner: button par icon lagao, text same rahe. Never raises.
    Returns True agar icon laga (tabhi caller emoji strip kare)."""
    try:
        from PyQt6.QtCore import QSize
        icon = get_icon(name, size, color or "#8ffcff")
        if icon is not None and not icon.isNull():
            btn.setIcon(icon)
            btn.setIconSize(QSize(int(size), int(size)))
            return True
        return False
    except Exception:
        return False


# Emoji / dingbat ranges jo icon lagne par text se hatenge (words same rahenge).
# Geometric ▸/– jaise safe chars nahi hatenge... note: ▸ (U+25B8) range me hai,
# isliye send-button explicit spot par strip hota hai (icon verified hai).
_EMOJI_RE = None


def strip_emoji(text: str) -> str:
    """Button text se emoji/dingbat hatao, words rakho. Never raises."""
    global _EMOJI_RE
    try:
        import re as _re
        if _EMOJI_RE is None:
            _EMOJI_RE = _re.compile(
                "[\U0001F000-\U0001FAFF\u2600-\u27BF\u25A0-\u25FF"
                "\u2B00-\u2BFF\uFE0F\u200D\u20E3\u2190-\u21FF]+"
            )
        out = _EMOJI_RE.sub("", text or "")
        return " ".join(out.split())
    except Exception:
        return text or ""


# Button-name → glyph map (single source; wire code uses this).
# NOTE: order matters — pehle specific, phir general ("STUDIO" before "HUD").
BUTTON_ICONS = {
    "MICROPHONE": "mic", "STUDIO": "palette", "PROVIDERS": "key",
    "AUTO-START": "power", "SHORTCUT": "link", "FULLSCREEN": "expand",
    "REMOTE": "phone", "INTERRUPT": "hand", "VOICE": "speaker",
    "CAM": "cam", "PING": "bolt", "CLEAR": "trash",
    "HUD": "sparkle", "AUDIO": "headset", "MEMORY": "brain", "PLUGINS": "plug",
    "CONFIRM": "check", "CANCEL": "cross", "CLOSE": "cross",
    "SAVE": "check", "APPLY": "check", "TEST": "bolt",
    "REFRESH": "refresh", "SEARCH": "search", "UNDO": "refresh",
    "COPY": "folder", "HOME": "home", "BELL": "bell", "PIN": "pin", "GLOBE": "globe",
}
