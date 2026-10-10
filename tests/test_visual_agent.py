"""
tests/test_visual_agent.py — Tests for Real-Time Screen Streaming & Visual Self-Healing Agent
"""
from __future__ import annotations

import pytest


def test_visual_agent_tool_schema():
    """Verify visual_agent tool declaration conforms to action loader specification."""
    from actions.visual_agent import TOOL
    assert TOOL["name"] == "visual_agent"
    assert "parameters" in TOOL
    assert "properties" in TOOL["parameters"]
    assert "goal" in TOOL["parameters"]["properties"]
    assert callable(TOOL["handler"])


def test_screen_capture_and_compress():
    """Verify screen capture generates valid compressed image bytes."""
    from actions.visual_agent import _capture_screen_frame
    img_bytes, mime_type = _capture_screen_frame()
    assert isinstance(img_bytes, bytes)
    assert len(img_bytes) > 100
    assert mime_type in ("image/jpeg", "image/png")


def test_visual_agent_inspect_clean():
    """Verify visual_agent inspect action runs without crash and reports screen status."""
    from actions.visual_agent import visual_agent
    result = visual_agent({"action": "error_check"})
    assert isinstance(result, str) and len(result) > 0


def test_computer_control_visual_actions():
    """Verify computer_control actions for visual self-healing and verification."""
    from actions.computer_control import computer_control
    # Test visual_solve_error
    res_heal = computer_control({"action": "visual_solve_error"})
    assert isinstance(res_heal, str) and len(res_heal) > 0

    # Test visual_verify (with no API key or dummy text, returns verification result without crashing)
    res_ver = computer_control({"action": "visual_verify", "description": "desktop"})
    assert isinstance(res_ver, str) and len(res_ver) > 0


def test_dashboard_screen_endpoints():
    """Verify the screen endpoints exist AND require authentication.

    These routes return a live image of the user's entire screen, and the server
    binds 0.0.0.0 (plus opens the Windows firewall). They previously had no
    _auth() call, so any host on the LAN could pull them. Both halves of the
    contract are asserted here.
    """
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        # Fall back to route presence if testclient isn't configured.
        from dashboard.server import DashboardServer
        srv = DashboardServer()
        routes = [r.path for r in srv.app.routes]
        assert "/api/screen-frame" in routes
        assert "/api/screen-stream.mjpg" in routes
        assert "/ws/screen-stream" in routes
        return

    import time as _t
    from dashboard.server import DashboardServer

    # --- Unauthenticated must be refused ---
    anon = TestClient(DashboardServer().app)
    assert anon.get("/api/screen-frame").status_code == 401
    assert anon.get("/api/screen-stream.mjpg").status_code == 401

    # --- Authenticated still serves a frame ---
    srv = DashboardServer()
    srv._tokens.add("test-token-xyz")
    srv._token_keys["test-token-xyz"] = srv.new_key(expiry_secs=600)
    srv._token_created["test-token-xyz"] = _t.time()
    client = TestClient(srv.app)
    client.headers.update({"Authorization": "Bearer test-token-xyz"})

    resp = client.get("/api/screen-frame")
    assert resp.status_code == 200
    assert "image/" in resp.headers.get("content-type", "")
    assert len(resp.content) > 100


def test_edge_router_visual_reflex():
    """Verify edge router triggers visual self-healing for error dismissal phrases."""
    from core.edge_router import NeedleToolRouter
    r = NeedleToolRouter()

    # Test Hindi visual error solve
    r1 = r.classify_tool_intent("screen par error solve karo")
    assert r1 is not None
    assert r1[0] == "visual_agent"
    assert r1[1].get("action") == "heal_errors"

    # Test English popup dismiss
    r2 = r.classify_tool_intent("popup band karo")
    assert r2 is not None
    assert r2[0] == "visual_agent"
    assert r2[1].get("action") == "heal_errors"
