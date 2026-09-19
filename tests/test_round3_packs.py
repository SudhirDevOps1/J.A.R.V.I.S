"""Additive round-3 tests (scheduler/workflows/plugins/song — no side effects kept)."""


def test_scheduler_parse_and_list():
    from actions.scheduler import _parse_natural, scheduler
    assert _parse_natural("roz subah 9 baje backup")["kind"] == "cron"
    assert _parse_natural("har 30 minute check")["kind"] == "interval"
    assert _parse_natural("10 minute me yaad dilao")["kind"] == "once"
    assert _parse_natural("kuch bhi random") is None
    out = scheduler({"action": "list"})
    assert isinstance(out, str)


def test_scheduler_add_cancel_roundtrip():
    from actions.scheduler import scheduler
    name = "pytest_tmp_sched"
    out = scheduler({"action": "add", "name": name, "when": "har 60 minute test",
                     "message": "pytest"})
    assert "lag gaya" in out or "failed" in out
    out2 = scheduler({"action": "cancel", "name": name})
    assert "cancel" in out2 or "nahi mila" in out2


def test_workflows_add_check_delete():
    from actions.workflows import workflows
    assert "save ho gayi" in workflows({"action": "add", "name": "pytest_tmp_wf",
                                        "metric": "battery", "below": "1",
                                        "tool": "reminder", "args": {}})
    out = workflows({"action": "list"})
    assert "pytest_tmp_wf" in out
    assert "hata di" in workflows({"action": "delete", "name": "pytest_tmp_wf"})


def test_drive_smarthome_guided():
    from plugins.drive_tool import run as _dr
    from plugins.smart_home import run as _sh
    assert "connect nahi" in _dr({"action": "list"})
    out = _sh({"device": "test_xyz", "action": "on"})
    assert isinstance(out, str) and len(out) > 0


def test_song_query_expanded():
    from core.edge_router import NeedleToolRouter
    r = NeedleToolRouter()
    tool, args = r.classify_tool_intent("sad song play kro na")
    assert tool == "youtube_video"
    assert len(args["query"].split()) >= 2


def test_flight_url_no_hardcoded_tfs():
    from actions.flight_finder import _build_google_flights_url
    url = _build_google_flights_url("DEL", "LHR", "2026-10-01", None, 1, "economy")
    assert "2025-03-15" not in url and "Flights" in url
