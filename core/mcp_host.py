"""
core/mcp_host.py — Lightweight Stdio Model Context Protocol (MCP) Client for J.A.R.V.I.S.

Zero-dependency, pure Python JSON-RPC 2.0 stdio client.
Spawns local MCP servers (such as chrome-devtools-mcp, filesystem, etc.) on demand,
executes tool calls with strict timeout guards, and cleans up subprocesses safely.
"""
from __future__ import annotations

import json
import os
import platform
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_IS_WINDOWS = platform.system() == "Windows"
_WIN_CREATION_FLAGS = subprocess.CREATE_NO_WINDOW if _IS_WINDOWS else 0


class McpSession:
    """Manages an active stdio JSON-RPC 2.0 session with an MCP server."""

    def __init__(self, command: str, args: List[str], cwd: Optional[Path] = None):
        self.command = command
        self.args = args
        self.cwd = str(cwd) if cwd else None
        self.proc: Optional[subprocess.Popen] = None
        self._msg_id = 0
        self._lock = threading.Lock()
        self._responses: Dict[int, queue.Queue] = {}
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False

    def start(self, timeout: float = 12.0) -> bool:
        """Spawn the MCP server process and perform the standard protocol handshake."""
        full_cmd = [self.command] + self.args
        if _IS_WINDOWS and self.command in ("npx", "npm"):
            # On Windows, npx is a batch/cmd script (npx.cmd)
            full_cmd[0] = f"{self.command}.cmd"

        try:
            self.proc = subprocess.Popen(
                full_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                cwd=self.cwd,
                creationflags=_WIN_CREATION_FLAGS,
            )
        except Exception as e:
            print(f"[McpHost] Process spawn error ({full_cmd}): {e}")
            return False

        self._running = True
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()

        # Perform MCP initialize handshake
        init_req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "jarvis-mcp-client",
                    "version": "1.0.0"
                }
            }
        }

        res = self._send_request(init_req, timeout=timeout)
        if not res or "result" not in res:
            self.close()
            return False

        # Send notifications/initialized
        self._send_notification({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        })
        return True

    def _next_id(self) -> int:
        with self._lock:
            self._msg_id += 1
            return self._msg_id

    def _read_loop(self) -> None:
        """Background stdout reader that demuxes JSON-RPC responses."""
        while self._running and self.proc and self.proc.stdout:
            try:
                line = self.proc.stdout.readline()
                if not line:
                    break
                line_str = line.strip()
                if not line_str or not line_str.startswith("{"):
                    continue
                try:
                    payload = json.loads(line_str)
                    req_id = payload.get("id")
                    if req_id is not None and req_id in self._responses:
                        self._responses[req_id].put(payload)
                except Exception:
                    pass
            except Exception:
                break

    def _send_request(self, req: Dict[str, Any], timeout: float = 15.0) -> Optional[Dict[str, Any]]:
        if not self.proc or not self.proc.stdin:
            return None
        req_id = req["id"]
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._responses[req_id] = q

        try:
            line = json.dumps(req) + "\n"
            self.proc.stdin.write(line)
            self.proc.stdin.flush()
            return q.get(timeout=timeout)
        except Exception:
            return None
        finally:
            with self._lock:
                self._responses.pop(req_id, None)

    def _send_notification(self, notif: Dict[str, Any]) -> None:
        if not self.proc or not self.proc.stdin:
            return
        try:
            line = json.dumps(notif) + "\n"
            self.proc.stdin.write(line)
            self.proc.stdin.flush()
        except Exception:
            pass

    def list_tools(self, timeout: float = 10.0) -> List[Dict[str, Any]]:
        """Query available tools exposed by the MCP server."""
        req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
            "params": {}
        }
        res = self._send_request(req, timeout=timeout)
        if res and "result" in res:
            return res["result"].get("tools", [])
        return []

    def call_tool(self, name: str, arguments: Dict[str, Any], timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """Invoke an MCP tool on the server and return the result."""
        req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            }
        }
        return self._send_request(req, timeout=timeout)

    def close(self) -> None:
        """Gracefully close and terminate subprocess."""
        self._running = False
        if self.proc:
            try:
                if self.proc.stdin:
                    self.proc.stdin.close()
            except Exception:
                pass
            try:
                self.proc.terminate()
                self.proc.wait(timeout=2.0)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self.proc = None


def execute_mcp_tool_once(
    command: str,
    args: List[str],
    tool_name: str,
    tool_args: Dict[str, Any],
    timeout: float = 25.0
) -> Tuple[bool, str]:
    """Convenience helper to spawn an MCP server, call a single tool, and shut down cleanly."""
    session = McpSession(command=command, args=args)
    try:
        if not session.start(timeout=10.0):
            return False, f"Could not initialize MCP server '{command}'."
        res = session.call_tool(tool_name, tool_args, timeout=timeout)
        if not res:
            return False, f"MCP tool call '{tool_name}' timed out or returned empty."
        if "error" in res:
            err = res["error"]
            return False, f"MCP error ({err.get('code')}): {err.get('message')}"

        result = res.get("result", {})
        content = result.get("content", [])
        text_outputs = []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                text_outputs.append(c.get("text", ""))
        output = "\n".join(text_outputs) if text_outputs else json.dumps(result, indent=2)
        return True, output
    except Exception as e:
        return False, f"MCP execution exception: {e}"
    finally:
        session.close()
