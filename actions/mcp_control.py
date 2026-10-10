"""
actions/mcp_control.py — Voice/chat control surface for MCP servers.

Dropping a server into config/mcp_servers.json is only half the job; the user
also needs a way to see what is connected, start/stop a server, list its tools
and call one directly without waiting for the model to decide to. That is this
action.

Trigger phrases (Hindi/Hinglish/English):
  "mcp status"            / "mcp dikhao"
  "mcp servers"           / "kaunse server chal rahe"
  "mcp start <name>"      / "mcp chalu karo chrome"
  "mcp stop <name>"       / "mcp band karo"
  "mcp list <name>"       / "mcp tools dikhao"
  "mcp call <server> <tool> {...}"
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from core.mcp_manager import get_mcp_manager


def _manager():
    return get_mcp_manager()


def _resolve_server(name: str):
    """Fuzzy server lookup: exact, then case-insensitive, then substring."""
    mgr = _manager()
    mgr.load_config()
    servers = getattr(mgr, "_servers", {}) or {}
    key = (name or "").strip()
    if not key:
        return None, list(servers.keys())
    if key in servers:
        return key, list(servers.keys())
    low = key.lower()
    for k in servers:
        if k.lower() == low:
            return k, list(servers.keys())
    for k in servers:
        if low in k.lower() or k.lower() in low:
            return k, list(servers.keys())
    return None, list(servers.keys())


def mcp_control(parameters: dict | None = None, player=None, speak=None,
                response=None, session_memory=None, **_) -> str:
    params = parameters or {}
    action = str(params.get("action") or "status").strip().lower()
    mgr = _manager()

    if action in ("status", "list_servers", "servers", "dikhao"):
        return mgr.summary()

    if action in ("start", "chalu", "run"):
        target = str(params.get("server") or params.get("name") or "").strip()
        if not target:
            return "Kaunsa MCP server start karna hai? Naam batao."
        key, names = _resolve_server(target)
        if not key:
            return (f"'{target}' nahi mila. Configured servers: "
                    f"{', '.join(names) if names else '(koi nahi)'}")
        ok = mgr.start_server(key)
        if ok:
            st = mgr._servers.get(key)
            return f"MCP server '{key}' start ho gaya — {len(st.tools) if st else 0} tool(s) ready."
        st = mgr._servers.get(key)
        return f"MCP server '{key}' start nahi hua: {st.error if st else 'unknown error'}"

    if action in ("stop", "band", "kill"):
        target = str(params.get("server") or params.get("name") or "").strip()
        if not target:
            return "Kaunsa MCP server band karna hai? Naam batao."
        key, names = _resolve_server(target)
        if not key:
            return f"'{target}' nahi mila. Servers: {', '.join(names) if names else '(koi nahi)'}"
        st = mgr._servers.get(key)
        if st and st.session is not None:
            try:
                st.session.close()
            except Exception:
                pass
            st.session = None
            st.status = "not_started"
            st.tools = []
            return f"MCP server '{key}' band kar diya."
        return f"MCP server '{key}' toh pehle se running nahi tha."

    if action in ("list", "tools", "tools_list"):
        target = str(params.get("server") or params.get("name") or "").strip()
        if not target:
            # No target: list every server with its tool count.
            return mgr.summary()
        key, names = _resolve_server(target)
        if not key:
            return f"'{target}' nahi mila. Servers: {', '.join(names) if names else '(koi nahi)'}"
        st = mgr._servers.get(key)
        if st is None:
            return f"Server '{key}' config me nahi hai."
        if st.session is None or not st.session.is_alive():
            mgr.start_server(key)
            st = mgr._servers.get(key)
        if not st or not st.tools:
            return f"'{key}' ke koi tools nahi mile. Status: {st.status if st else '?'}."
        lines = [f"MCP server '{key}' — {len(st.tools)} tool(s):"]
        for t in st.tools[:60]:
            desc = (t.get("description") or "").strip().splitlines()
            d = f" — {desc[0][:110]}" if desc else ""
            lines.append(f"  • {t.get('name')}{d}")
        return "\n".join(lines)

    if action in ("call", "invoke"):
        tool = str(params.get("tool") or "").strip()
        raw_args = params.get("arguments") or params.get("args") or {}
        if isinstance(raw_args, str):
            try:
                raw_args = json.loads(raw_args)
            except Exception:
                raw_args = {"value": raw_args}
        if not isinstance(raw_args, dict):
            raw_args = {}
        if not tool:
            return "Kaunsa MCP tool call karna hai? Naam batao."
        return _call_mcp_tool(mgr, str(params.get("server") or ""), tool, raw_args)

    return (f"Unknown MCP action '{action}'. "
            "Use: status, start, stop, list, call.")


def _call_mcp_tool(mgr, server_hint: str, tool: str, arguments: Dict[str, Any]) -> str:
    """Route a tool call to the right server.

    Accepts a bare tool name ('list_pages'), a server-qualified name
    ('chrome-devtools.list_pages') or a full namespaced name
    ('mcp__chrome-devtools__list_pages').
    """
    if tool.startswith("mcp__"):
        ok, out = mgr.call_tool(tool, arguments)
        return out if ok else f"MCP call failed: {out}"

    if "." in tool:
        server_hint, tool = tool.split(".", 1)
    if not server_hint:
        return ("Server naam batao, ya 'server.tool' format mein likho "
                "(e.g. chrome-devtools.list_pages).")

    key, _names = _resolve_server(server_hint)
    if not key:
        return f"MCP server '{server_hint}' config me nahi hai."

    from core.mcp_manager import McpManager
    full = McpManager.tool_name(key, tool)
    ok, out = mgr.call_tool(full, arguments)
    return out if ok else f"MCP call failed: {out}"


TOOL = {
    "name": "mcp_control",
    "description": (
        "Manage Model Context Protocol servers: show status, start/stop a server, "
        "list the tools a server exposes, or call a tool directly. "
        "Trigger on 'mcp status', 'mcp servers', 'mcp start chrome', 'mcp stop', "
        "'mcp tools dikhao', 'mcp call'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "status | start | stop | list | call",
                "enum": ["status", "start", "stop", "list", "call"],
            },
            "server": {
                "type": "STRING",
                "description": "Server name from config/mcp_servers.json (e.g. websift, chrome-devtools).",
            },
            "tool": {
                "type": "STRING",
                "description": "Tool name for action=call.",
            },
            "arguments": {
                "type": "OBJECT",
                "description": "Arguments object for action=call.",
            },
        },
        "required": ["action"],
    },
    "handler": mcp_control,
}