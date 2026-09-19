"""Tests for advanced features:
1. Assistant Persona Modes Synchronization (Teacher, DevOps, Companion, JARVIS)
2. Smart Multi-Modal Transit, Travel & Maps Assistant (OSRM, Train, Flight, Bus, Maps)
3. Universal Drive Music Indexer across all drives
4. Video playback vs Headless background audio differentiation
"""
import pytest
from pathlib import Path

from core.persona_manager import (
    build_persona_system_prompt,
    get_persona_greeting,
    get_persona_details,
    AVAILABLE_PERSONAS,
)
from core.edge_router import NeedleToolRouter
from actions.travel_transit import travel_transit, _calculate_osrm_route, _haversine_road_estimate
from actions.youtube_video import _scan_music_library, _find_local_audio, youtube_video


def test_persona_manager_prompts_and_greetings():
    """Verify all persona modes have distinct prompts, titles, and in-character greetings."""
    for mode in ("jarvis", "teacher", "companion", "devops"):
        prompt = build_persona_system_prompt(assistant_name="JARVIS", mode=mode)
        assert len(prompt) > 100
        assert "ABSOLUTE IDENTITY DIRECTIVE" in prompt

        details = get_persona_details(mode)
        assert "title" in details

        greeting = get_persona_greeting(mode, user_name="Sudhir")
        assert "Sudhir" in greeting
        if mode == "teacher":
            assert "Namaste" in greeting or "topic" in greeting
        elif mode == "devops":
            assert "Terminal" in greeting or "pipelines" in greeting
        elif mode == "companion":
            assert "handsome" in greeting or "miss" in greeting
        elif mode == "jarvis":
            assert "operational" in greeting or "Sir" in greeting


def test_edge_router_persona_mode_switching():
    """Verify edge router classifies persona switching commands to profile tool."""
    router = NeedleToolRouter()

    res_teacher = router.classify_tool_intent("teacher mode lagao")
    assert res_teacher is not None
    assert res_teacher[0] == "profile"
    assert res_teacher[1]["name"] == "teacher"

    res_devops = router.classify_tool_intent("devops mode activate karo")
    assert res_devops is not None
    assert res_devops[0] == "profile"
    assert res_devops[1]["name"] == "devops"

    res_gf = router.classify_tool_intent("girlfriend mode lagao")
    assert res_gf is not None
    assert res_gf[0] == "profile"
    assert res_gf[1]["name"] == "companion"


def test_travel_transit_execution_and_routing():
    """Verify multi-modal transit calculation, trains, and edge routing."""
    # Test mathematical road estimation fallback
    road_km, drive_h = _haversine_road_estimate(28.6139, 77.2090, 25.5941, 85.1376)  # Delhi to Patna
    assert road_km > 700.0
    assert drive_h > 10.0

    # Test travel_transit tool execution
    res = travel_transit({"origin": "Delhi", "destination": "Patna", "mode": "all"})
    assert "Delhi" in res
    assert "Patna" in res
    assert "km" in res

    # Test edge router train queries
    router = NeedleToolRouter()
    route_train = router.classify_tool_intent("Delhi se Patna train batao")
    assert route_train is not None
    assert route_train[0] == "travel_transit"
    assert route_train[1]["mode"] == "train"
    assert "Patna" in route_train[1]["destination"]

    # Test edge router map route queries
    route_map = router.classify_tool_intent("Patna kaise jaye map route batao")
    assert route_map is not None
    assert route_map[0] == "travel_transit"


def test_universal_drive_music_library_indexer():
    """Verify music scanner discovers audio files and saves to config/music_library.json."""
    tracks = _scan_music_library(force_refresh=True)
    assert isinstance(tracks, list)

    cache_file = Path(__file__).resolve().parent.parent / "config" / "music_library.json"
    assert cache_file.exists()

    # Verify fuzzy matching
    matched = _find_local_audio("sanam teri kasam gaana chalao")
    if matched:
        assert matched.exists()
        assert "sanam" in matched.stem.lower() or "kasam" in matched.stem.lower()


def test_youtube_video_vs_audio_routing():
    """Verify edge router distinguishes video playback from audio playback."""
    router = NeedleToolRouter()

    # Video request -> mode=video, open_browser=True
    res_video = router.classify_tool_intent("apna college ka video lagao")
    assert res_video is not None
    assert res_video[0] == "youtube_video"
    assert res_video[1].get("mode") == "video"
    assert res_video[1].get("open_browser") is True

    # Audio request -> default audio mode
    res_audio = router.classify_tool_intent("sanam teri kasam gaana chalao")
    assert res_audio is not None
    assert res_audio[0] == "youtube_video"
    assert res_audio[1].get("mode") != "video"

    # Music library rescan request
    res_rescan = router.classify_tool_intent("songs rescan karo")
    assert res_rescan is not None
    assert res_rescan[0] == "youtube_video"
    assert res_rescan[1]["action"] == "rescan"


def test_todo_agent_real_tool_dispatch():
    """Verify todo_agent dispatches real actions without simulated dummy sleep."""
    from actions.todo_agent import _dispatch_step_to_tool
    
    # Test travel transit dispatch
    out_transit = _dispatch_step_to_tool("travel_transit: Delhi to Patna trains", goal="trip to Patna")
    assert "Patna" in out_transit or "distance" in out_transit.lower() or "delhi" in out_transit.lower()

    # Test reminder dispatch
    out_reminder = _dispatch_step_to_tool("reminder: pack clothes", goal="trip checklist")
    assert "reminder" in out_reminder.lower() or "set" in out_reminder.lower() or "checklist" in out_reminder.lower()


def test_agent_mode_and_todo_deduplication():
    """Verify duplicate goals in agent_mode and todo_agent are detected and prevent duplicate threads."""
    from actions.agent_mode import agent_mode
    from actions.todo_agent import create_task, _active_tasks, _tasks_lock

    unique_goal = "Autonomous Test Trip Planning Unique"
    res1 = create_task(unique_goal, ["travel_transit: routes", "reminder: pack"])
    assert "Created" in res1 or "executing" in res1.lower()

    # Immediate second call with identical goal must be deduplicated
    res2 = create_task(unique_goal, ["travel_transit: routes"])
    assert "already actively executing" in res2 or "already" in res2.lower()

    # Clean up test task
    with _tasks_lock:
        for tid in list(_active_tasks.keys()):
            if _active_tasks[tid].get("goal") == unique_goal:
                _active_tasks[tid]["abort"] = True
                _active_tasks[tid]["status"] = "cancelled"


def test_edge_router_telegram_messaging():
    """Verify edge router classifies Telegram message intent directly without phone number detour."""
    router = NeedleToolRouter()

    res1 = router.classify_tool_intent("teligram pr ritik ko hii send kro")
    assert res1 is not None
    assert res1[0] == "send_message"
    assert res1[1]["platform"] == "telegram"
    assert res1[1]["receiver"] == "ritik"
    assert res1[1]["message_text"] == "hii"

    res2 = router.classify_tool_intent("telegram par rahul ko hello bhejo")
    assert res2 is not None
    assert res2[0] == "send_message"
    assert res2[1]["platform"] == "telegram"
    assert res2[1]["receiver"] == "rahul"
    assert res2[1]["message_text"] == "hello"

    res3 = router.classify_tool_intent("ritik ko telegram pr meeting link send karo")
    assert res3 is not None
    assert res3[0] == "send_message"
    assert res3[1]["platform"] == "telegram"
    assert res3[1]["receiver"] == "ritik"
    assert "meeting link" in res3[1]["message_text"]


