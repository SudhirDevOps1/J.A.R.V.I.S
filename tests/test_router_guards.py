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


def test_conversational_continuation_falls_through():
    from core.edge_router import NeedleToolRouter, get_tri_tier_dispatcher
    r = NeedleToolRouter()
    assert r.classify_tool_intent("aur batao") is None
    assert r.classify_tool_intent("aur") is None
    assert r.classify_tool_intent("aur kya") is None
    assert r.classify_tool_intent("aage batao") is None
    assert r.classify_tool_intent("main kya kr raha hu") is None
    assert r.classify_tool_intent("main kya kar raha hoon") is None

    dispatcher = get_tri_tier_dispatcher()
    assert dispatcher.route("aur batao")["tool"] is None
    assert dispatcher.route("aur")["tool"] is None
    assert dispatcher.route("main kya kr raha hu")["tool"] is None


def test_camera_queries_do_not_route_to_troubleshoot_screen():
    from core.edge_router import NeedleToolRouter, get_tri_tier_dispatcher
    r = NeedleToolRouter()
    out = r.classify_tool_intent("camera se dekho main kya liya hu hand mein")
    assert out is None or out[0] != "troubleshoot_screen"

    dispatcher = get_tri_tier_dispatcher()
    route_out = dispatcher.route("camera se dekho main kya liya hu hand mein")
    assert route_out["tool"] is None or route_out["tool"][0] != "troubleshoot_screen"


def test_needle_hindi_verb_hallucination_guarded():
    from core.edge_router import get_tri_tier_dispatcher
    dispatcher = get_tri_tier_dispatcher()
    out = dispatcher.route("dekhna abhi chal nahi raha tha")
    assert out["tool"] is None or out["tool"][0] != "open_app"


def test_camera_app_resolves_instantly():
    from actions.open_app import _resolve_app
    target, note = _resolve_app("camera")
    assert "camera" in target.lower()


def test_weather_salutation_is_persona_clean():
    from actions.weather_report import weather_action
    msg = weather_action({"city": "Patna"})
    assert isinstance(msg, str) and len(msg) > 0
    assert not msg.startswith("Sir,")
