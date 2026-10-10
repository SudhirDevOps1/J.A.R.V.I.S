"""
tests/test_superpower_features.py — Tests for J.A.R.V.I.S Superpowers.
Validates Clipboard Copilot, Network Diagnostics, Process Manager, Quick Notes,
and their respective edge router dispatches.
"""
import json
import pytest
from actions.clipboard_copilot import clipboard_copilot, _detect_content_type
from actions.network_diagnostics import network_diagnostics, _get_local_ip
from actions.process_manager import process_manager, _PROTECTED_PROCESSES
from actions.quick_notes import quick_notes
from core.edge_router import NeedleToolRouter
from core.unified_memory import get_db


def test_clipboard_copilot_content_detection():
    # Test JSON detection
    assert _detect_content_type('{"status": "ok", "count": 10}') == "json"
    
    # Test traceback detection
    trace = """Traceback (most recent call last):
  File "main.py", line 42, in <module>
ZeroDivisionError: division by zero"""
    assert _detect_content_type(trace) == "error_traceback"

    # Test URL detection
    assert _detect_content_type("https://github.com/SudhirDevOps1/J.A.R.V.I.S") == "url"


def test_clipboard_copilot_json_formatting():
    raw_json = '{"b":2,"a":1}'
    res = clipboard_copilot({"action": "write", "text": raw_json})
    assert "updated" in res.lower()

    fmt_res = clipboard_copilot({"action": "format_json"})
    assert "formatted" in fmt_res.lower()


def test_clipboard_copilot_error_diagnosis():
    trace = """Traceback (most recent call last):
  File "calculator.py", line 12, in divide
ZeroDivisionError: division by zero"""
    clipboard_copilot({"action": "write", "text": trace})
    
    diag_res = clipboard_copilot({"action": "explain_error"})
    assert "calculator.py" in diag_res
    assert "Line 12" in diag_res
    assert "ZeroDivisionError" in diag_res or "division by zero" in diag_res


def test_network_diagnostics_local_ip():
    ip = _get_local_ip()
    assert isinstance(ip, str)
    assert len(ip.split(".")) == 4

    res = network_diagnostics({"action": "status"})
    assert "Network Diagnostics" in res
    assert "Local IP" in res


def test_process_manager_top_processes():
    res_ram = process_manager({"action": "top_ram"})
    assert "Top Memory (RAM)-Consuming" in res_ram

    res_cpu = process_manager({"action": "top_cpu"})
    assert "Top CPU-Consuming" in res_cpu


def test_process_manager_protected_security():
    # Attempting to kill core Windows explorer or svchost must be blocked by security guard
    for proc in ["explorer.exe", "svchost", "csrss"]:
        res = process_manager({"action": "kill", "process_name": proc})
        assert "Security Guard" in res
        assert "allowed nahi hai" in res


def test_quick_notes_crud_and_fts():
    test_note = "Meeting with lead architect at 5pm regarding microservices"
    
    # 1. Add
    add_res = quick_notes({"action": "add", "text": test_note})
    assert "successfully save" in add_res.lower()

    # 2. Search
    search_res = quick_notes({"action": "search", "query": "microservices"})
    assert "microservices" in search_res.lower()

    # 3. List
    list_res = quick_notes({"action": "list"})
    assert "Recent Saved Notes" in list_res


def test_edge_router_superpower_dispatches():
    router = NeedleToolRouter()

    # 1. Clipboard
    res1 = router.classify_tool_intent("clipboard ka error explain karo")
    assert res1 is not None
    assert res1[0] == "clipboard_copilot"
    assert res1[1]["action"] == "explain_error"

    # 2. Network ping
    res2 = router.classify_tool_intent("ping kaisa hai")
    assert res2 is not None
    assert res2[0] == "network_diagnostics"

    # 3. Process Manager
    res3 = router.classify_tool_intent("top heavy processes dikhao")
    assert res3 is not None
    assert res3[0] == "process_manager"

    # 4. Process Kill
    res4 = router.classify_tool_intent("kill process chrome")
    assert res4 is not None
    assert res4[0] == "process_manager"
    assert res4[1]["action"] == "kill"
    assert res4[1]["process_name"] == "chrome"

    # 5. Quick Notes
    res5 = router.classify_tool_intent("note likho kal subah gym jana hai")
    assert res5 is not None
    assert res5[0] == "quick_notes"
    assert res5[1]["action"] == "add"
    assert "gym" in res5[1]["text"]
