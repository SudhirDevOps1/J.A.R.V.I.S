"""
core/privacy_guard.py — Zero-Trust Screen Privacy Shield & Web Stream Guard for J.A.R.V.I.S.

Provides ironclad privacy boundaries:
1. Default-OFF Screen Streaming Authorization Gate.
2. Localhost-only stream connection enforcement (blocks LAN/Wi-Fi snooping).
3. Real-time sensitive window detection (Banking, Passwords, Incognito, UPI, Private chats).
4. Instant Cyberpunk Privacy Shield rendering (masks screen frames with zero CPU overhead).
5. Voice and CLI toggle controls ("privacy mode on/off", "screen stream allow/stop").
"""
from __future__ import annotations

import io
import json
import re
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_BASE_DIR = Path(__file__).resolve().parent.parent
_CONFIG_FILE = _BASE_DIR / "config" / "privacy_settings.json"

_LOCK = threading.Lock()
_CACHED_SETTINGS: Optional[Dict[str, Any]] = None
_CACHED_SHIELD_FRAMES: Dict[str, bytes] = {}

# Default settings in case config file is missing
_DEFAULT_SETTINGS: Dict[str, Any] = {
    "privacy_mode": False,
    "stream_allowed": False,
    "localhost_only": True,
    "auto_shield_sensitive": True,
    "sensitive_keywords": [
        "bank", "netbanking", "sbi", "hdfc", "icici", "axis", "kotak", "pnb", "bob",
        "paytm", "phonepe", "gpay", "paypal", "razorpay", "credit card", "debit card",
        "checkout", "payment", "upi", "bitwarden", "1password", "keepass", "lastpass",
        "dashlane", "authenticator", "two-factor", "2fa", "otp", "password", "credentials",
        "incognito", "inprivate", "private browsing", "tor browser", "whatsapp", "signal",
        "tax", "aadhaar", "pan card"
    ],
    "blacklisted_apps": [
        "bitwarden.exe", "1password.exe", "keepass.exe", "lastpass.exe", "signal.exe", "tor.exe"
    ]
}


def load_privacy_settings() -> Dict[str, Any]:
    """Load privacy settings from disk with memory cache."""
    global _CACHED_SETTINGS
    with _LOCK:
        if _CACHED_SETTINGS is not None:
            return dict(_CACHED_SETTINGS)

        if _CONFIG_FILE.exists():
            try:
                data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
                _CACHED_SETTINGS = {**_DEFAULT_SETTINGS, **data}
                return dict(_CACHED_SETTINGS)
            except Exception as e:
                print(f"[PrivacyGuard] ⚠️ Could not parse {_CONFIG_FILE}: {e}")

        _CACHED_SETTINGS = dict(_DEFAULT_SETTINGS)
        return dict(_CACHED_SETTINGS)


def save_privacy_settings(settings: Dict[str, Any]) -> None:
    """Save privacy settings to disk and update memory cache."""
    global _CACHED_SETTINGS
    with _LOCK:
        _CACHED_SETTINGS = dict(settings)
        try:
            _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            _CONFIG_FILE.write_text(json.dumps(_CACHED_SETTINGS, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[PrivacyGuard] ⚠️ Could not save {_CONFIG_FILE}: {e}")


def is_privacy_mode_active() -> bool:
    """Check if master privacy mode is enabled."""
    return bool(load_privacy_settings().get("privacy_mode", False))


def set_privacy_mode(enabled: bool) -> str:
    """Turn master privacy mode on or off."""
    cfg = load_privacy_settings()
    cfg["privacy_mode"] = bool(enabled)
    save_privacy_settings(cfg)
    if enabled:
        return "Sir, Master Privacy Mode ON kar diya gaya hai. Screen capture, streaming aur vision analysis ab completely locked hain."
    return "Sir, Master Privacy Mode OFF kar diya gaya hai. Normal screen monitoring resume ho chuki hai."


def is_stream_allowed() -> bool:
    """Check if live screen streaming is authorized by the user."""
    return bool(load_privacy_settings().get("stream_allowed", False))


def set_stream_allowed(allowed: bool) -> str:
    """Authorize or revoke screen streaming."""
    cfg = load_privacy_settings()
    cfg["stream_allowed"] = bool(allowed)
    save_privacy_settings(cfg)
    if allowed:
        return "Sir, Screen Streaming ALLOWED kar di gayi hai. Dashboard aur WebSocket clients ab authorized stream dekh sakte hain."
    return "Sir, Screen Streaming STOP aur LOCK kar di gayi hai. Saare streams ab Privacy Shield se masked hain."


def get_active_window_info() -> Tuple[str, str]:
    """
    Get (window_title, process_name) of the current foreground/active window.
    Fast and safe across Windows environments.
    """
    title = ""
    proc_name = ""

    # Strategy 1: pygetwindow
    try:
        import pygetwindow as gw
        win = gw.getActiveWindow()
        if win and win.title:
            title = win.title.strip()
    except Exception:
        pass

    # Strategy 2: win32gui (Windows native)
    if not title and sys.platform == "win32":
        try:
            import win32gui
            import win32process
            import psutil
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                title = win32gui.GetWindowText(hwnd).strip()
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid:
                    p = psutil.Process(pid)
                    proc_name = p.name().lower()
        except Exception:
            pass

    return title, proc_name


def detect_sensitive_window(
    title: Optional[str] = None,
    proc_name: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Check if foreground window matches sensitive banking, password, incognito,
    or confidential keywords. Returns (is_sensitive, reason).
    """
    cfg = load_privacy_settings()
    if not cfg.get("auto_shield_sensitive", True):
        return False, ""

    if title is None or proc_name is None:
        t_active, p_active = get_active_window_info()
        title = title or t_active
        proc_name = proc_name or p_active

    title_lower = (title or "").lower()
    proc_lower = (proc_name or "").lower()

    # Check blacklisted app processes
    blacklisted_apps = [a.lower() for a in cfg.get("blacklisted_apps", [])]
    if proc_lower and proc_lower in blacklisted_apps:
        return True, f"Blacklisted sensitive application active ({proc_name})"

    # Check sensitive keywords in title
    keywords = cfg.get("sensitive_keywords", [])
    for kw in keywords:
        kw_clean = kw.strip().lower()
        if not kw_clean:
            continue
        # Use regex word/boundary matching
        pattern = r"(?:^|[\s\-_\|\.\(\)\[\]])" + re.escape(kw_clean) + r"(?:$|[\s\-_\|\.\(\)\[\]])"
        if re.search(pattern, title_lower) or kw_clean in title_lower:
            return True, f"Sensitive keyword '{kw}' detected in active window"

    return False, ""


def generate_shield_frame(reason: str = "PRIVACY SHIELD ACTIVE") -> Tuple[bytes, str]:
    """
    Generate an aesthetic dark Cyberpunk Privacy Shield JPEG frame (1280x720).
    Caches the binary output so repeated streaming frames use 0 CPU.
    """
    reason_key = reason.strip().upper()
    with _LOCK:
        if reason_key in _CACHED_SHIELD_FRAMES:
            return _CACHED_SHIELD_FRAMES[reason_key], "image/jpeg"

    # Generate shield frame using PIL
    try:
        from PIL import Image, ImageDraw, ImageFont
        w, h = 1280, 720
        img = Image.new("RGB", (w, h), color=(10, 15, 24))  # Dark sleek navy
        draw = ImageDraw.Draw(img)

        # Draw tech grid / borders
        border_color = (0, 210, 255)  # Cyan Stark glow
        accent_red = (255, 60, 80)    # Warning shield accent
        draw.rectangle([(20, 20), (w - 20, h - 20)], outline=border_color, width=2)
        draw.rectangle([(30, 30), (w - 30, h - 30)], outline=(20, 40, 60), width=1)

        # Draw decorative corner brackets
        bracket_len = 40
        # Top-left
        draw.line([(15, 15), (15 + bracket_len, 15)], fill=border_color, width=4)
        draw.line([(15, 15), (15, 15 + bracket_len)], fill=border_color, width=4)
        # Top-right
        draw.line([(w - 15, 15), (w - 15 - bracket_len, 15)], fill=border_color, width=4)
        draw.line([(w - 15, 15), (w - 15, 15 + bracket_len)], fill=border_color, width=4)
        # Bottom-left
        draw.line([(15, h - 15), (15 + bracket_len, h - 15)], fill=border_color, width=4)
        draw.line([(15, h - 15), (15, h - 15 - bracket_len)], fill=border_color, width=4)
        # Bottom-right
        draw.line([(w - 15, h - 15), (w - 15 - bracket_len, h - 15)], fill=border_color, width=4)
        draw.line([(w - 15, h - 15), (w - 15, h - 15 - bracket_len)], fill=border_color, width=4)

        # Draw Shield Emblem in center
        cx, cy = w // 2, h // 2 - 40
        shield_pts = [
            (cx - 70, cy - 80),
            (cx + 70, cy - 80),
            (cx + 80, cy + 10),
            (cx, cy + 90),
            (cx - 80, cy + 10),
        ]
        draw.polygon(shield_pts, fill=(15, 25, 45), outline=accent_red, width=4)

        # Text captions
        title_text = "J.A.R.V.I.S. ZERO-TRUST PRIVACY SHIELD"
        sub_text = reason_key or "SCREEN CAPTURE & STREAMING ARE BLOCKED"
        guidance = "Your sensitive data, passwords, and private activities remain completely confidential."

        # Use default font safely
        draw.text((cx, cy + 130), title_text, fill=(0, 220, 255), anchor="mm")
        draw.text((cx, cy + 175), sub_text, fill=(255, 80, 80), anchor="mm")
        draw.text((cx, cy + 220), guidance, fill=(160, 180, 200), anchor="mm")

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        img_bytes = buf.getvalue()

        with _LOCK:
            _CACHED_SHIELD_FRAMES[reason_key] = img_bytes

        return img_bytes, "image/jpeg"
    except Exception as e:
        print(f"[PrivacyGuard] ⚠️ Frame generation error: {e}")
        # Minimal fallback 1x1 black JPEG
        fallback = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
        return fallback, "image/jpeg"


def is_screen_capture_allowed(
    is_stream: bool = False,
    client_ip: str = "127.0.0.1"
) -> Tuple[bool, str]:
    """
    Master validation for any screen capture or streaming operation.
    Returns (allowed: bool, reason_if_blocked: str).
    """
    cfg = load_privacy_settings()

    # Rule 1: Master Privacy Mode
    if cfg.get("privacy_mode", False):
        return False, "Master Privacy Mode is ON (All screen captures blocked)"

    # Rule 2: Streaming-specific checks
    if is_stream:
        # Check Localhost Only constraint
        if cfg.get("localhost_only", True):
            clean_ip = (client_ip or "").strip()
            if clean_ip not in ("127.0.0.1", "::1", "localhost", "testclient"):
                return False, f"Remote LAN access blocked ({clean_ip} is not localhost)"

        # Check Stream Authorization Gate
        if not cfg.get("stream_allowed", False):
            return False, "Screen stream is inactive (Requires user authorization)"

    # Rule 3: Real-Time Sensitive Window Detection
    if cfg.get("auto_shield_sensitive", True):
        is_sensitive, reason = detect_sensitive_window()
        if is_sensitive:
            return False, reason

    return True, "Allowed"


def get_privacy_status_summary() -> str:
    """Generate human-readable privacy status for voice and chat."""
    cfg = load_privacy_settings()
    mode = "ON (Full Lockdown)" if cfg.get("privacy_mode") else "OFF (Normal)"
    stream = "ALLOWED" if cfg.get("stream_allowed") else "LOCKED (Default-Off)"
    lan = "LOCALHOST ONLY (Wi-Fi Blocked)" if cfg.get("localhost_only") else "LAN Allowed"
    sensitive_guard = "ACTIVE (Banking, Passwords, Incognito Protected)" if cfg.get("auto_shield_sensitive") else "DISABLED"

    # Current window check
    is_sens, sens_desc = detect_sensitive_window()
    current_state = f"⚠️ SENSITIVE ({sens_desc})" if is_sens else "SAFE (No sensitive content detected)"

    return (
        f"🛡️ J.A.R.V.I.S. Privacy & Security Status:\n"
        f"• Master Privacy Mode : {mode}\n"
        f"• Screen Streaming     : {stream}\n"
        f"• Network Isolation    : {lan}\n"
        f"• Auto-Shield Guard    : {sensitive_guard}\n"
        f"• Active Screen State  : {current_state}"
    )
