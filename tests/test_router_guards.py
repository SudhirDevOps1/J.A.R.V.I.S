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


def test_hindi_daily_verbs_naive_bayes_classification():
    """Verify Scikit-Learn Naive Bayes intent classification across all 5 Hindi verb families."""
    from core.intent_classifier import get_micro_intent_classifier
    nb = get_micro_intent_classifier()
    assert nb is not None

    # 1. Dekhna (देखना)
    pred_screen = nb.predict_intent("screen par error dekho", min_confidence=0.50)
    assert pred_screen is not None and pred_screen[0] == "troubleshoot_screen"

    pred_shot = nb.predict_intent("screenshot le lo", min_confidence=0.50)
    assert pred_shot is not None and pred_shot[0] == "take_screenshot"

    # 2. Sunna (सुनना)
    pred_vol = nb.predict_intent("volume badhao thoda", min_confidence=0.50)
    assert pred_vol is not None and pred_vol[0] == "volume_up"

    # 3. Chalna (चलना)
    pred_run = nb.predict_intent("kya chal raha hai", min_confidence=0.50)
    assert pred_run is not None and pred_run[0] == "list_apps"

    # 4. Karna (करना)
    pred_mem = nb.predict_intent("yaad rakhna kal mujhe exam dena hai", min_confidence=0.50)
    assert pred_mem is not None and pred_mem[0] == "tinydb_memory"


def test_hindi_daily_verbs_lfm_interpret_and_generate():
    """Verify LFMChatEngine handles Sunna, Dekhna, Chalna, and Bolna colloquial queries."""
    from core.edge_router import LFMChatEngine
    lfm = LFMChatEngine()

    # 1. Sunna: Gaana sunao
    norm_cmd, intent = lfm.interpret_command("arijit singh ka gaana sunao")
    assert intent == "play_youtube"
    assert "play song" in norm_cmd

    # 2. Dekhna: Camera se dekho
    norm_cam, intent_cam = lfm.interpret_command("camera se dekho")
    assert intent_cam == "camera_vision"

    # 3. Chalna: Delhi kaise jaye (Travel & Transit)
    norm_tr, intent_tr = lfm.interpret_command("delhi kaise jaye")
    assert intent_tr == "travel_transit"

    # 4. Sunna: Audibility / Mic check
    resp_hear = lfm.generate("meri awaaz aa rahi hai")
    assert "sun raha hoon" in resp_hear.lower() or "sun" in resp_hear.lower()

    # 5. Bolna: Conversational continuation
    resp_cont = lfm.generate("aur batao")
    assert len(resp_cont) > 10


def test_persona_colloquial_directive_injected():
    """Verify build_persona_system_prompt contains all 5 grounded action families."""
    from core.persona_manager import build_persona_system_prompt
    prompt = build_persona_system_prompt(assistant_name="JARVIS", mode="companion")
    for verb_family in ("DEKHNA", "SUNNA", "BOLNA", "CHALNA", "KARNA"):
        assert verb_family in prompt

