"""Additive tests: sense/suggest/hunt/mute routing + monitor behavior (no deletes)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_sense_routing():
    from core.edge_router import NeedleToolRouter
    r = NeedleToolRouter()
    assert r.classify_tool_intent("screen par kya khula hai")[0] == "context_sense"
    assert r.classify_tool_intent("suggest karo")[1]["action"] == "suggest"


def test_sense_runs_safe():
    from actions.context_sense import context_sense, TOOL
    assert TOOL["name"] == "context_sense"
    out = context_sense({"action": "sense"})
    assert isinstance(out, str) and len(out) > 10
    out2 = context_sense({"action": "suggest"})
    assert "Suggestions" in out2


def test_hunt_delete_guards():
    from actions.file_controller import file_controller
    # garbage/short -> refuse, no scan
    out = file_controller({"action": "hunt_delete", "name": "x"})
    assert "Naam bolo" in out
    # nonexistent -> not found, no confirm banner
    out2 = file_controller({"action": "hunt_delete", "name": "pytest_no_such_file_xyz123"})
    assert "nahi mila" in out2


def test_monitor_mute_escalate():
    from actions.system_monitor import (SystemMonitor, set_monitor_muted,
                                        is_monitor_muted)
    assert set_monitor_muted(True) is True
    assert is_monitor_muted() is True
    m = SystemMonitor()
    assert m.check() is None  # muted -> silent
    assert set_monitor_muted(False) is False
    # escalation: 2nd fire within hour -> 30min quiet
    import time as _t
    m._record("ram")
    m._fires["ram"] = [_t.monotonic() - 100, _t.monotonic()]
    m._record("ram")
    assert m._escalated_until.get("ram", 0) > _t.monotonic()
    assert m._can_alert("ram") is False


def test_monitor_ctl_action():
    from actions.monitor_ctl import monitor_ctl, TOOL
    assert TOOL["name"] == "monitor_ctl"
    assert "band" in monitor_ctl({"action": "mute"})
    assert "chalu" in monitor_ctl({"action": "unmute"})
    assert "status" in monitor_ctl({"action": "status"}).lower()
