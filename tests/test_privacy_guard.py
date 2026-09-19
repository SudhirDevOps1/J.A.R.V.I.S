"""
tests/test_privacy_guard.py — Automated Tests for Zero-Trust Privacy Shield & Screen Stream Security
"""
from __future__ import annotations

import pytest


def test_privacy_settings_defaults():
    """Verify default privacy settings are secure-by-default."""
    from core.privacy_guard import load_privacy_settings
    cfg = load_privacy_settings()
    assert isinstance(cfg, dict)
    assert "privacy_mode" in cfg
    assert "stream_allowed" in cfg
    assert "localhost_only" in cfg
    assert "auto_shield_sensitive" in cfg
    assert "sensitive_keywords" in cfg
    # Crucial security assertion: streaming must be default-off
    assert cfg.get("localhost_only") is True
    assert isinstance(cfg.get("sensitive_keywords"), list)
    assert len(cfg.get("sensitive_keywords")) > 10


def test_sensitive_window_detection():
    """Verify sensitive window detection accurately classifies sensitive vs safe windows."""
    from core.privacy_guard import detect_sensitive_window

    # Sensitive titles
    sensitive_samples = [
        "State Bank of India - Online NetBanking - Google Chrome",
        "HDFC Bank - NetBanking Login",
        "Bitwarden - My Vault",
        "1Password - Passwords & Credentials",
        "Chrome - Incognito Window",
        "WhatsApp Web - Google Chrome",
        "Signal Messenger",
        "KeePass Password Safe",
        "Paytm Payments Gateway",
        "Income Tax Filing - Portal"
    ]
    for sample in sensitive_samples:
        is_sens, reason = detect_sensitive_window(title=sample, proc_name="")
        assert is_sens is True, f"Failed to detect sensitive window for: '{sample}'"
        assert len(reason) > 0

    # Safe titles
    safe_samples = [
        "Visual Studio Code - project.py",
        "Windows Terminal - PowerShell",
        "Notepad - todo_notes.txt",
        "Spotify Free",
        "Calculator"
    ]
    for sample in safe_samples:
        is_sens, _ = detect_sensitive_window(title=sample, proc_name="code.exe")
        assert is_sens is False, f"False positive on safe window: '{sample}'"


def test_generate_shield_frame():
    """Verify privacy shield frame generation creates valid JPEG bytes."""
    from core.privacy_guard import generate_shield_frame
    frame_bytes, mime = generate_shield_frame("STREAM INACTIVE")
    assert isinstance(frame_bytes, bytes)
    assert len(frame_bytes) > 500
    assert mime == "image/jpeg"
    assert frame_bytes[:2] == b"\xff\xd8"  # JPEG header


def test_privacy_mode_lockdown():
    """Verify master privacy mode completely blocks screen capture."""
    from core.privacy_guard import set_privacy_mode, is_screen_capture_allowed
    # Turn ON
    set_privacy_mode(True)
    allowed, reason = is_screen_capture_allowed(is_stream=False)
    assert allowed is False
    assert "Privacy Mode is ON" in reason

    # Turn OFF
    set_privacy_mode(False)


def test_streaming_authorization_and_localhost():
    """Verify stream authorization gate and localhost network enforcement."""
    from core.privacy_guard import set_privacy_mode, set_stream_allowed, is_screen_capture_allowed
    set_privacy_mode(False)

    # 1. Stream denied by default
    set_stream_allowed(False)
    allowed, reason = is_screen_capture_allowed(is_stream=True, client_ip="127.0.0.1")
    assert allowed is False
    assert "inactive" in reason.lower()

    # 2. Remote LAN IP blocked even if stream allowed
    set_stream_allowed(True)
    allowed_lan, reason_lan = is_screen_capture_allowed(is_stream=True, client_ip="192.168.1.105")
    assert allowed_lan is False
    assert "localhost" in reason_lan.lower()

    # Reset
    set_stream_allowed(False)


def test_privacy_ctl_action():
    """Verify actions/privacy_ctl tool handlers and responses."""
    from actions.privacy_ctl import TOOL, privacy_ctl
    assert TOOL["name"] == "privacy_ctl"
    assert callable(TOOL["handler"])

    # Test status
    status_out = privacy_ctl({"action": "status"})
    assert "J.A.R.V.I.S. Privacy" in status_out

    # Test enable/disable
    on_out = privacy_ctl({"action": "enable_privacy_mode"})
    assert "ON" in on_out
    off_out = privacy_ctl({"action": "disable_privacy_mode"})
    assert "OFF" in off_out

    # Test allow/stop stream
    stream_on = privacy_ctl({"action": "allow_stream"})
    assert "ALLOWED" in stream_on
    stream_off = privacy_ctl({"action": "stop_stream"})
    assert "STOP" in stream_off


def test_dashboard_privacy_endpoints():
    """Verify FastAPI dashboard privacy status and stream toggle endpoints."""
    try:
        from fastapi.testclient import TestClient
        from dashboard.server import DashboardServer
        srv = DashboardServer()
        client = TestClient(srv.app)

        # 1. Privacy status
        resp_status = client.get("/api/privacy/status")
        assert resp_status.status_code == 200
        data = resp_status.json()
        assert "privacy_mode" in data
        assert "stream_allowed" in data

        # 2. Stream toggle
        resp_toggle = client.post("/api/screen-stream/toggle", json={"allowed": True})
        assert resp_toggle.status_code == 200
        assert resp_toggle.json().get("stream_allowed") is True

        # Toggle back off
        resp_toggle_off = client.post("/api/screen-stream/toggle", json={"allowed": False})
        assert resp_toggle_off.status_code == 200
        assert resp_toggle_off.json().get("stream_allowed") is False

        # 3. Screen frame while stream disabled returns Privacy Shield frame
        resp_frame = client.get("/api/screen-frame")
        assert resp_frame.status_code == 200
        assert resp_frame.headers.get("content-type") == "image/jpeg"
        assert len(resp_frame.content) > 500
    except ImportError:
        pytest.skip("FastAPI / TestClient dependencies not available")


def test_edge_router_privacy_reflexes():
    """Verify edge router voice/chat reflexes route directly to privacy_ctl."""
    from core.edge_router import NeedleToolRouter
    router = NeedleToolRouter()

    # Privacy Mode ON
    res1 = router.classify_tool_intent("sir privacy mode on karo")
    assert res1 is not None and res1[0] == "privacy_ctl"
    assert res1[1].get("action") == "enable_privacy_mode"

    # Privacy Mode OFF
    res2 = router.classify_tool_intent("privacy mode band karo please")
    assert res2 is not None and res2[0] == "privacy_ctl"
    assert res2[1].get("action") == "disable_privacy_mode"

    # Allow Stream
    res3 = router.classify_tool_intent("screen stream allow karo")
    assert res3 is not None and res3[0] == "privacy_ctl"
    assert res3[1].get("action") == "allow_stream"

    # Stop Stream
    res4 = router.classify_tool_intent("stop screen stream right now")
    assert res4 is not None and res4[0] == "privacy_ctl"
    assert res4[1].get("action") == "stop_stream"

    # Privacy Status
    res5 = router.classify_tool_intent("screen privacy check karo")
    assert res5 is not None and res5[0] == "privacy_ctl"
    assert res5[1].get("action") == "status"
