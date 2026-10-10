"""
tests/test_mcp_and_unified_memory.py — Unit Tests for Lightweight MCP & Unified Memory
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest


def test_unified_memory_crud_and_fts(tmp_path, monkeypatch):
    from core import unified_memory

    # Point database to isolated temporary path
    test_db = tmp_path / "test_memory.db"
    monkeypatch.setattr(unified_memory, "_DB_PATH", test_db)
    monkeypatch.setattr(unified_memory, "_DB_CONN", None)

    # 1. Store and Retrieve
    assert unified_memory.store_memory("identity", "preferred_editor", "VS Code")
    val = unified_memory.get_memory("identity", "preferred_editor")
    assert val == "VS Code"

    # Update existing key
    assert unified_memory.store_memory("identity", "preferred_editor", "Cursor")
    assert unified_memory.get_memory("identity", "preferred_editor") == "Cursor"

    # 2. Recall matching memories
    recalled = unified_memory.recall_memories("cursor")
    assert len(recalled) == 1
    assert recalled[0]["key"] == "preferred_editor"
    assert recalled[0]["value"] == "Cursor"

    # 3. Journal Full-Text Search (FTS5)
    assert unified_memory.log_journal_entry("User deployed Docker swarm cluster today", "devops")
    assert unified_memory.log_journal_entry("Meeting scheduled with frontend team about React UI", "work")

    search_res = unified_memory.search_journal("Docker")
    assert len(search_res) >= 1
    assert "swarm" in search_res[0]["content"]

    # 4. Task / Todo management
    task_id = unified_memory.add_task("Review pull request #42", priority="high")
    assert task_id > 0

    pending = unified_memory.list_tasks(status="pending")
    assert any(t["id"] == task_id and t["task"] == "Review pull request #42" for t in pending)

    assert unified_memory.complete_task(task_id)
    completed = unified_memory.list_tasks(status="completed")
    assert any(t["id"] == task_id for t in completed)


def test_unified_memory_auto_migration(tmp_path, monkeypatch):
    from core import unified_memory

    test_db = tmp_path / "migrate_memory.db"
    monkeypatch.setattr(unified_memory, "_DB_PATH", test_db)
    monkeypatch.setattr(unified_memory, "_DB_CONN", None)

    # Seed mock memory files
    fake_base = tmp_path / "fake_app"
    fake_mem = fake_base / "memory"
    fake_cfg = fake_base / "config"
    fake_mem.mkdir(parents=True)
    fake_cfg.mkdir(parents=True)
    monkeypatch.setattr(unified_memory, "_BASE_DIR", fake_base)

    (fake_mem / "long_term.json").write_text(json.dumps({
        "preferences": {"theme": "cyberpunk_neon", "volume": "80"}
    }), encoding="utf-8")

    (fake_cfg / "todos.json").write_text(json.dumps([
        {"task": "Buy new mechanical keyboard", "priority": "high"}
    ]), encoding="utf-8")

    migrated = unified_memory.auto_migrate_existing_json()
    assert migrated >= 3

    assert unified_memory.get_memory("preferences", "theme") == "cyberpunk_neon"
    pending = unified_memory.list_tasks("pending")
    assert any("mechanical keyboard" in t["task"] for t in pending)


def test_mcp_host_session_data_structures():
    from core.mcp_host import McpSession

    session = McpSession("test_cmd", ["--arg1", "val1"])
    assert session.command == "test_cmd"
    assert session.args == ["--arg1", "val1"]
    assert session._next_id() == 1
    assert session._next_id() == 2


def test_mcp_chrome_action_schema_and_discovery():
    from actions.mcp_chrome import TOOL, mcp_chrome
    from core.action_loader import discover_actions

    # 1. Conformance with JARVIS Action Registry
    assert TOOL["name"] == "mcp_chrome"
    assert "parameters" in TOOL
    assert callable(TOOL["handler"])

    # 2. Discovery test
    reg = discover_actions(Path("actions"))
    assert reg.has("mcp_chrome")
    rec = reg._actions.get("mcp_chrome")
    assert rec is not None
    assert rec.valid is True

    # 3. Graceful execution when target is not available
    res = mcp_chrome({"action": "navigate", "url": "example.com"})
    assert "Chrome" in res
