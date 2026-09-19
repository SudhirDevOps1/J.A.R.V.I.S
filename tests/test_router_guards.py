"""Additive tests: web garbage guard, obsidian-save route (no launches)."""


def test_web_garbage_falls_through():
    from core.edge_router import NeedleToolRouter
    r = NeedleToolRouter()
    assert r.classify_tool_intent("fact batao") is None
    assert r.classify_tool_intent("tum batao fact") is None
    # real search untouched
    got = r.classify_tool_intent("laptop price batao")
    assert got is not None and got[0] == "web_search"


def test_obsidian_save_route():
    from core.edge_router import NeedleToolRouter
    r = NeedleToolRouter()
    got = r.classify_tool_intent("ye fact obsidian me save karo")
    assert got is not None and got[0] == "obsidian_brain"
    assert got[1]["action"] == "append_daily"


def test_ai_speech_clock_exists():
    import main as _m
    assert hasattr(_m.JarvisLive, "speak")
    import inspect
    src = inspect.getsource(_m.JarvisLive.speak)
    assert "_last_ai_speech" in src
