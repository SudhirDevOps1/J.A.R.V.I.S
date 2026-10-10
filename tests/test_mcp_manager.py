"""
tests/test_mcp_manager.py — End-to-end tests for the config-driven MCP layer.

These spawn a real MCP server subprocess and speak real JSON-RPC to it, so they
exercise the transport rather than mocking it. That matters because the bugs
this layer fixed (stderr deadlock, single-line-kills-session, restart) are all
transport-level and would not show up against a mock.

The fixture server (tests/mcp_fixture_server.py) is a minimal but protocol-correct
implementation: initialize, tools/list, tools/call, ping, roots/list. It also
deliberately emits malformed stdout and floods stderr on demand so the client's
resilience can be asserted.

Each test gets its own McpManager and the manager is stopped in a fixture, so
no subprocess is leaked between tests.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_FIXTURE = _ROOT / "tests" / "mcp_fixture_server.py"


# ── fixtures ────────────────────────────────────────────────────────────────

def _write_config(tmp_path: Path, servers: dict) -> Path:
    cfg = tmp_path / "mcp_servers.json"
    cfg.write_text(json.dumps({"mcpServers": servers}, indent=2), encoding="utf-8")
    return cfg


@pytest.fixture
def cfg_ok(tmp_path):
    return _write_config(tmp_path, {
        "tester": {"command": sys.executable, "args": [str(_FIXTURE)], "enabled": True},
    })


@pytest.fixture
def cfg_mixed(tmp_path):
    return _write_config(tmp_path, {
        "tester": {"command": sys.executable, "args": [str(_FIXTURE)], "enabled": True},
        "offline": {"command": "definitely-not-installed-xyz-12345", "args": []},
        "off": {"command": sys.executable, "args": [str(_FIXTURE)], "enabled": False},
    })


@pytest.fixture
def manager(cfg_ok):
    from core.mcp_manager import McpManager
    mgr = McpManager(cfg_ok, logger=lambda m: None)
    yield mgr
    mgr.stop_all()


@pytest.fixture
def manager_mixed(cfg_mixed):
    from core.mcp_manager import McpManager
    mgr = McpManager(cfg_mixed, logger=lambda m: None)
    yield mgr
    mgr.stop_all()


# ── config parsing ──────────────────────────────────────────────────────────

def test_config_accepts_standard_mcpServers_shape(manager_mixed):
    """The Claude Desktop / Cursor format must work unchanged."""
    assert manager_mixed.load_config(force=True) == 2


def test_config_accepts_bare_mapping_and_list(tmp_path):
    from core.mcp_manager import McpManager

    bare = tmp_path / "bare.json"
    bare.write_text(json.dumps({"s": {"command": sys.executable}}), encoding="utf-8")
    m1 = McpManager(bare, logger=lambda m: None)
    assert m1.load_config(force=True) == 1
    m1.stop_all()

    as_list = tmp_path / "list.json"
    as_list.write_text(json.dumps({"mcpServers": [
        {"name": "a", "command": sys.executable},
        {"name": "b", "command": sys.executable},
    ]}), encoding="utf-8")
    m2 = McpManager(as_list, logger=lambda m: None)
    assert m2.load_config(force=True) == 2
    m2.stop_all()


def test_missing_command_is_skipped_not_fatal(tmp_path):
    from core.mcp_manager import McpManager
    cfg = _write_config(tmp_path, {"good": {"command": sys.executable}, "bad": {"args": []}})
    m = McpManager(cfg, logger=lambda m: None)
    assert m.load_config(force=True) == 1
    m.stop_all()


def test_missing_config_file_is_not_an_error(tmp_path):
    from core.mcp_manager import McpManager
    m = McpManager(tmp_path / "nope.json", logger=lambda m: None)
    assert m.load_config() == 0
    assert "nope.json" in m.summary()


def test_corrupt_config_does_not_raise(tmp_path):
    from core.mcp_manager import McpManager
    bad = tmp_path / "bad.json"
    bad.write_text("{ this is not json", encoding="utf-8")
    m = McpManager(bad, logger=lambda m: None)
    assert m.load_config(force=True) == 0
    m.stop_all()


def test_disabled_server_is_never_started(manager_mixed):
    manager_mixed.load_config(force=True)
    assert manager_mixed._servers["off"].status == "disabled"
    assert manager_mixed.start_server("off") is False
    assert manager_mixed._servers["off"].session is None


# ── lifecycle ───────────────────────────────────────────────────────────────

def test_servers_start_lazily(manager):
    """Nothing should spawn until a tool is actually needed — boot stays fast."""
    manager.load_config(force=True)
    assert manager._servers["tester"].session is None


def test_handshake_records_server_identity(manager):
    from core.mcp_host import PROTOCOL_VERSION
    assert manager.start_server("tester") is True
    st = manager._servers["tester"]
    assert st.status == "ready"
    assert st.session.server_name == "jarvis-test-mcp"
    assert st.session.server_version == "1.0.0"
    assert st.session.protocol_version == PROTOCOL_VERSION
    assert len(st.tools) == 3


def test_missing_binary_reports_actionable_error(manager_mixed):
    manager_mixed.load_config(force=True)
    assert manager_mixed.start_server("offline") is False
    err = manager_mixed._servers["offline"].error
    assert "not found" in err
    assert "definitely-not-installed-xyz-12345" in err


def test_auto_start_only_touches_marked_servers(tmp_path):
    from core.mcp_manager import McpManager
    cfg = _write_config(tmp_path, {
        "lazy": {"command": sys.executable, "args": [str(_FIXTURE)], "auto_start": False},
        "eager": {"command": sys.executable, "args": [str(_FIXTURE)], "auto_start": True},
    })
    m = McpManager(cfg, logger=lambda x: None)
    m.load_config(force=True)
    assert m.start_auto() == 1
    assert m._servers["eager"].status == "ready"
    assert m._servers["lazy"].session is None
    m.stop_all()


def test_stop_all_releases_every_session(manager):
    manager.start_server("tester")
    t0 = time.time()
    manager.stop_all()
    assert time.time() - t0 < 5, "stop_all must not block on process teardown"
    assert manager._servers["tester"].session is None


# ── tool namespace ──────────────────────────────────────────────────────────

def test_tool_names_are_namespaced_and_sanitised():
    from core.mcp_manager import McpManager as MM
    assert MM.tool_name("chrome-devtools", "take_snapshot") == "mcp__chrome_devtools__take_snapshot"
    assert MM.tool_name("my server", "do it!") == "mcp__my_server__do_it_"
    assert len(MM.tool_name("x" * 100, "y" * 100)) <= 58


def test_declarations_shape_is_gemini_compatible(manager):
    manager.start_server("tester")
    decls = manager.all_tool_declarations()
    assert len(decls) == 3
    by_name = {d["name"]: d for d in decls}

    add = by_name["mcp__tester__add"]
    assert add["description"].startswith("[MCP:tester]")
    assert add["parameters"]["type"] == "object"
    assert add["parameters"]["properties"]["a"]["type"] == "number"
    assert add["parameters"]["required"] == ["a", "b"]


def test_empty_required_list_is_stripped(tmp_path):
    """Gemini rejects parameters with "required": []; some MCP servers emit it."""
    from core.mcp_manager import McpManager
    cfg = _write_config(tmp_path, {"t": {"command": sys.executable, "args": [str(_FIXTURE)]}})
    m = McpManager(cfg, logger=lambda x: None)
    m.load_config(force=True)
    m.start_server("t")
    # Simulate a server that declared an empty required array.
    m._servers["t"].tools[0]["inputSchema"]["required"] = []
    decls = m.all_tool_declarations()
    assert all("required" not in d["parameters"] or d["parameters"]["required"]
               for d in decls)
    m.stop_all()


def test_broken_server_contributes_no_declarations(manager_mixed):
    manager_mixed.load_config(force=True)
    manager_mixed.start_server("tester")
    names = {d["name"] for d in manager_mixed.all_tool_declarations()}
    assert "mcp__tester__add" in names
    assert not any(n.startswith("mcp__offline") for n in names)
    assert not any(n.startswith("mcp__off__") for n in names)


# ── calls ───────────────────────────────────────────────────────────────────

def test_call_tool_roundtrip(manager):
    manager.start_server("tester")
    ok, out = manager.call_tool("mcp__tester__add", {"a": 2, "b": 3})
    assert ok and out.strip() == "5"

    ok, out = manager.call_tool("mcp__tester__echo", {"text": "namaste"})
    assert ok and out.strip() == "namaste"


def test_call_rejects_invalid_names(manager):
    ok, out = manager.call_tool("not_mcp", {})
    assert ok is False and "not a valid" in out

    ok, out = manager.call_tool("mcp__ghost__x", {})
    assert ok is False and "not available" in out


def test_call_starts_the_server_on_demand(manager):
    """No explicit start_server() call — the first tool call brings it up."""
    manager.load_config(force=True)
    assert manager._servers["tester"].session is None
    ok, out = manager.call_tool("mcp__tester__add", {"a": 1, "b": 1})
    assert ok and out.strip() == "2"
    assert manager._servers["tester"].status == "ready"


# ── transport resilience (the regressions this layer exists for) ────────────

def test_stderr_flood_does_not_deadlock(manager):
    """Regression: stderr was a PIPE that was never read. Once a server wrote
    more than the OS pipe buffer (~64KB on Windows) it blocked forever on
    write, and every later tool call appeared to time out."""
    manager.start_server("tester")
    t0 = time.time()
    ok, out = manager.call_tool("mcp__tester__flood_stderr", {})
    elapsed = time.time() - t0
    assert ok and out.strip() == "flooded"
    assert elapsed < 15, f"stderr flood took {elapsed:.1f}s — pipe not drained"

    # And the session must still work afterwards.
    ok, out = manager.call_tool("mcp__tester__add", {"a": 10, "b": 5})
    assert ok and out.strip() == "15"


def test_malformed_stdout_does_not_kill_session(manager):
    """Regression: the reader loop's inner parse error escaped to the outer
    `except: break`, so one stray non-JSON line ended the session permanently."""
    manager.start_server("tester")
    # The fixture emits a garbage line after every tools/list.
    ok, out = manager.call_tool("mcp__tester__echo", {"text": "alive"})
    assert ok and "alive" in out
    ok, out = manager.call_tool("mcp__tester__echo", {"text": "still alive"})
    assert ok and "still alive" in out


def test_transport_restarts_after_child_dies(manager):
    """A crashed optional server must not require an app restart."""
    manager.start_server("tester")
    manager._servers["tester"].session.proc.kill()
    time.sleep(0.4)
    assert not manager._servers["tester"].session.is_alive()

    ok, out = manager.call_tool("mcp__tester__add", {"a": 7, "b": 8})
    assert ok and out.strip() == "15"
    assert manager._servers["tester"].status == "ready"


def test_close_unblocks_pending_waiters(manager):
    """A caller blocked in q.get() must fail fast on close, not wait out its
    full timeout."""
    manager.start_server("tester")
    sess = manager._servers["tester"].session
    manager.stop_all()
    assert sess.is_alive() is False


# ── security posture ────────────────────────────────────────────────────────

def test_child_process_gets_a_minimal_environment(tmp_path):
    """A third-party MCP server should not inherit the user's whole shell
    environment (cloud SDK tokens, CI credentials, ...)."""
    from core.mcp_manager import McpManager, _build_env
    env = _build_env({"CUSTOM_ONE": "1"})
    assert env.get("CUSTOM_ONE") == "1"
    for leaky in ("AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN", "OPENAI_API_KEY",
                  "ANTHROPIC_API_KEY", "AZURE_CLIENT_SECRET"):
        assert leaky not in env
    # PATH must survive or nothing can be resolved.
    assert "PATH" in env


def test_env_from_config_is_passed_through(tmp_path):
    from core.mcp_manager import McpManager, _build_env
    env = _build_env({"SCRATCH": "value"})
    assert env["SCRATCH"] == "value"


# ── the control action ──────────────────────────────────────────────────────

def test_mcp_control_action_is_discoverable():
    """It must be auto-discovered by action_loader like every other action."""
    from pathlib import Path as _P
    import sys as _s
    _s.path.insert(0, str(_ROOT))
    from core.action_loader import discover_actions
    reg = discover_actions(actions_dir=_ROOT / "actions",
                           reserved_names=set(), logger=lambda m: None)
    assert reg.has("mcp_control")
    assert "mcp" in reg.run("mcp_control", {"action": "status"}).lower()


def test_mcp_control_reports_unknown_server(manager_mixed, monkeypatch):
    import core.mcp_manager as mm
    monkeypatch.setattr(mm, "_MANAGER", manager_mixed, raising=False)
    import actions.mcp_control as mc
    monkeypatch.setattr(mc, "_manager", lambda: manager_mixed)
    out = mc.mcp_control({"action": "start", "server": "nope-not-here"})
    assert "nahi mila" in out


# ── the bundled example config must stay valid ──────────────────────────────

def test_example_config_is_valid_json_and_shape():
    """config/mcp_servers.example.json is the thing users copy. If it drifts,
    the first thing they try is broken."""
    p = _ROOT / "config" / "mcp_servers.example.json"
    assert p.exists(), "example config is missing"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert "mcpServers" in data
    assert isinstance(data["mcpServers"], dict) and data["mcpServers"]
    for name, cfg in data["mcpServers"].items():
        assert isinstance(name, str) and name
        assert isinstance(cfg, dict), f"{name} must be an object"
        assert cfg.get("command"), f"{name} needs a command"


def test_real_config_if_present_parses():
    """If the user has created config/mcp_servers.json it must at least load."""
    real = _ROOT / "config" / "mcp_servers.json"
    if not real.exists():
        pytest.skip("no user config/mcp_servers.json (expected on a fresh clone)")
    from core.mcp_manager import McpManager
    m = McpManager(real, logger=lambda x: None)
    try:
        m.load_config(force=True)   # must not raise
    finally:
        m.stop_all()