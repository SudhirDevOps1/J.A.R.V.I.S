"""Additive tests: clock routing, browser dedupe (no real browser needed for 2nd call)."""


def test_clock_routing():
    from core.edge_router import NeedleToolRouter
    r = NeedleToolRouter()
    assert r.classify_tool_intent("time batao")[0] == "clock"
    assert r.classify_tool_intent("aaj kya date hai")[0] == "clock"
    assert r.classify_tool_intent("aaj kaun sa din hai")[0] == "clock"


def test_clock_answers():
    from actions.clock import clock, TOOL
    assert TOOL["name"] == "clock"
    assert "PM" in clock({"action": "time"}) or "AM" in clock({"action": "time"})
    assert "2026" in clock({"action": "date"})


def test_browser_dedupe():
    from actions import browser_control as _bc
    # Real browser kabhi na khule: _open_native mock karo (pehle test asli tab kholta tha!)
    _real = _bc._open_native
    _bc._open_native = lambda url, browser=None: f"MOCK opened: {url}"
    try:
        _bc._NAV_DEDUPE.clear()
        r1 = _bc.browser_control({"action": "go_to", "url": "https://example.com/dedupe-probe-xyz"})
        r2 = _bc.browser_control({"action": "go_to", "url": "https://example.com/dedupe-probe-xyz"})
        assert "duplicate skipped" in r2
        assert r1 != r2
    finally:
        _bc._open_native = _real
        _bc._NAV_DEDUPE.clear()
