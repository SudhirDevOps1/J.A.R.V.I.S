"""
Unit tests for Next-Gen Desktop Autonomous Features:
  1. Windows UIAutomation (UIA) Controller (actions/uia_controller.py)
  2. 100% Private Local Screen Memory & Timeline Recall (actions/screen_timeline.py)
  3. Safe, Opt-in Local LLM Bridge (core/local_llm_bridge.py & actions/local_llm_toggle.py)
  4. Autonomous DevOps Terminal Sentinel (actions/devops_sentinel.py)
  5. EdgeRouter Reflex Intent Dispatches
"""
import os
import sqlite3
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_uia_controller_schema_and_graceful_handling():
    from actions.uia_controller import TOOL, uia_controller

    assert TOOL["name"] == "uia_controller"
    assert "handler" in TOOL
    assert callable(TOOL["handler"])

    # Test handling when window does not exist
    res = uia_controller({"action": "click", "window_title": "NonExistentWindow12345", "element_name": "Save"})
    assert "nahi mili" in res or "error" in res.lower()

    # Test inspect on non-existent window
    res_list = uia_controller({"action": "list_elements", "window_title": "NonExistentWindow12345"})
    assert "nahi mili" in res_list or "error" in res_list.lower()


def test_screen_timeline_db_and_fts5_recall(tmp_path, monkeypatch):
    from actions import screen_timeline

    # Redirect database to temp path for isolated testing
    test_db = tmp_path / "test_timeline.db"
    monkeypatch.setattr(screen_timeline, "_DB_PATH", test_db)

    # 1. Record normal snapshots
    ok1 = screen_timeline.record_snapshot(
        window_title="VSCodium - test_router_guards.py",
        app_name="vscodium.exe",
        summary="Editing router tests and edge reflexes",
        tags="code,python,testing"
    )
    assert ok1 is True

    # 2. Privacy blacklist test — sensitive data must NEVER be recorded
    ok_priv = screen_timeline.record_snapshot(
        window_title="Google Chrome - Bank NetBanking Login - Enter Password",
        app_name="chrome.exe",
        summary="User entering secret password",
        tags="bank,login"
    )
    assert ok_priv is False

    # 3. Recall test with keyword match via FTS5
    recall_res = screen_timeline.recall_screen_history("VSCodium", minutes=60)
    assert "VSCodium" in recall_res
    assert "test_router_guards.py" in recall_res

    # 4. Action dispatcher test
    disp_res = screen_timeline.screen_timeline({"action": "recall", "query": "router"})
    assert "VSCodium" in disp_res


def test_safe_opt_in_local_llm_bridge(monkeypatch):
    from core import local_llm_bridge
    from actions.local_llm_toggle import local_llm_control

    # Ensure disabled by default in test environment
    monkeypatch.setenv("ENABLE_LOCAL_LLM", "0")
    monkeypatch.setattr(local_llm_bridge, "is_local_llm_enabled", lambda: False)

    # 1. Disabled safety check — must return None instantly without hanging or network calls
    res = local_llm_bridge.generate_local_llm("Explain Docker")
    assert res is None

    # 2. Toggle status check
    status_msg = local_llm_control({"action": "status"})
    assert "DISABLED (Safe Mode)" in status_msg
    assert "Gemini Live" in status_msg

    # 3. Enable test
    monkeypatch.setattr(local_llm_bridge, "set_local_llm_enabled", lambda x: True)
    monkeypatch.setattr(local_llm_bridge, "check_local_llm_health", lambda timeout=1.5: {"online": False})
    en_msg = local_llm_control({"action": "enable"})
    assert "enable ho gaya hai" in en_msg or "enable kar diya gaya" in en_msg


def test_devops_sentinel_error_analysis():
    from actions.devops_sentinel import analyze_terminal_error, TOOL, devops_sentinel

    assert TOOL["name"] == "devops_sentinel"

    # Test Python ModuleNotFoundError pattern
    sample_py_err = """
    Traceback (most recent call last):
      File "main.py", line 12, in <module>
        import non_existent_pkg
    ModuleNotFoundError: No module named 'non_existent_pkg'
    """
    diag_py = analyze_terminal_error(sample_py_err)
    assert "pip install non_existent_pkg" in diag_py

    # Test Port in use error pattern
    port_err = "Error: listen EADDRINUSE: address already in use :::8080"
    diag_port = analyze_terminal_error(port_err)
    assert "Port busy hai" in diag_port

    # Test action handler
    res_h = devops_sentinel({"action": "analyze", "error_log": port_err})
    assert "DevOps Sentinel Error Analysis" in res_h


def test_edge_router_nextgen_dispatches():
    from core.edge_router import get_tri_tier_dispatcher

    dispatcher = get_tri_tier_dispatcher()

    # 1. Screen Timeline routing
    r_timeline = dispatcher.needle.classify_tool_intent("screen timeline dekho")
    assert r_timeline is not None
    assert r_timeline[0] == "screen_timeline"

    r_timeline2 = dispatcher.needle.classify_tool_intent("pehle main kya kar raha tha")
    assert r_timeline2 is not None
    assert r_timeline2[0] == "screen_timeline"

    # 2. Local LLM Control routing
    r_llm_stat = dispatcher.needle.classify_tool_intent("local llm status")
    assert r_llm_stat is not None
    assert r_llm_stat[0] == "local_llm_control"
    assert r_llm_stat[1]["action"] == "status"

    r_llm_on = dispatcher.needle.classify_tool_intent("local llm chalu karo")
    assert r_llm_on is not None
    assert r_llm_on[0] == "local_llm_control"
    assert r_llm_on[1]["action"] == "enable"

    r_llm_off = dispatcher.needle.classify_tool_intent("local llm band karo")
    assert r_llm_off is not None
    assert r_llm_off[0] == "local_llm_control"
    assert r_llm_off[1]["action"] == "disable"

    # 3. DevOps Sentinel routing
    r_sentinel_watch = dispatcher.needle.classify_tool_intent("watch command pytest tests/")
    assert r_sentinel_watch is not None
    assert r_sentinel_watch[0] == "devops_sentinel"
    assert r_sentinel_watch[1]["action"] == "watch"

    r_sentinel_err = dispatcher.needle.classify_tool_intent("terminal error analyze karo")
    assert r_sentinel_err is not None
    assert r_sentinel_err[0] == "devops_sentinel"
    assert r_sentinel_err[1]["action"] == "analyze"

    # 4. UIA Controller routing
    r_uia = dispatcher.needle.classify_tool_intent("window elements dikhao")
    assert r_uia is not None
    assert r_uia[0] == "uia_controller"


if __name__ == "__main__":
    import tempfile
    import shutil
    print("[Testing] test_uia_controller_schema_and_graceful_handling...")
    test_uia_controller_schema_and_graceful_handling()
    print("[PASS] test_uia_controller_schema_and_graceful_handling")

    print("[Testing] test_screen_timeline_db_and_fts5_recall...")
    td = Path(tempfile.mkdtemp())
    class DummyMonkeyPatch:
        def setattr(self, target, name, val):
            setattr(target, name, val)
        def setenv(self, k, v):
            os.environ[k] = v
    try:
        test_screen_timeline_db_and_fts5_recall(td, DummyMonkeyPatch())
        print("[PASS] test_screen_timeline_db_and_fts5_recall")
    finally:
        shutil.rmtree(td, ignore_errors=True)

    print("[Testing] test_safe_opt_in_local_llm_bridge...")
    test_safe_opt_in_local_llm_bridge(DummyMonkeyPatch())
    print("[PASS] test_safe_opt_in_local_llm_bridge")

    print("[Testing] test_devops_sentinel_error_analysis...")
    test_devops_sentinel_error_analysis()
    print("[PASS] test_devops_sentinel_error_analysis")

    print("[Testing] test_edge_router_nextgen_dispatches...")
    test_edge_router_nextgen_dispatches()
    print("[PASS] test_edge_router_nextgen_dispatches")

    print("\nALL NEXT-GEN TESTS PASSED SUCCESSFULLY! (5/5)")

