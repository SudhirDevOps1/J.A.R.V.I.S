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
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_IS_WINDOWS = platform.system() == "Windows"
_WIN_CREATION_FLAGS = subprocess.CREATE_NO_WINDOW if _IS_WINDOWS else 0

# MCP protocol revision this client speaks. The server's answer is recorded in
# McpSession.protocol_version so a mismatch is visible in the log rather than
# manifesting as a confusing failure at tools/call time.
PROTOCOL_VERSION = "2024-11-05"


class McpSession:
    """Manages an active stdio JSON-RPC 2.0 session with an MCP server.

    Sessions are LONG-LIVED on purpose. The original design spawned a fresh
    process per tool call (`execute_mcp_tool_once`), which meant paying the
    npx/python startup cost plus the MCP handshake on every single call. For
    chrome-devtools-mcp that is seconds of latency each time.
    """

    def __init__(self, command: str, args: List[str], cwd: Optional[Path] = None,
                 env: Optional[Dict[str, str]] = None):
        self.command = command
        self.args = args
        self.cwd = str(cwd) if cwd else None
        self.env = env
        self.proc: Optional[subprocess.Popen] = None
        self._msg_id = 0
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._responses: Dict[int, queue.Queue] = {}
        self._reader_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._stderr_tail: List[str] = []
        self._running = False
        self.server_name: str = ""
        self.server_version: str = ""
        self.protocol_version: str = PROTOCOL_VERSION
        self._tools_cache: Optional[List[Dict[str, Any]]] = None

    def start(self, timeout: float = 20.0) -> bool:
        """Spawn the MCP server process and perform the standard protocol handshake."""
        full_cmd = [self.command] + list(self.args)
        if _IS_WINDOWS and self.command in ("npx", "npm", "pnpm", "yarn"):
            # On Windows these are .cmd batch shims; CreateProcess needs the
            # extension or the spawn fails with a confusing WinError 2.
            resolved = shutil.which(full_cmd[0])
            if resolved:
                full_cmd[0] = resolved
            else:
                full_cmd[0] = f"{self.command}.cmd"

        if self.env:
            merged = os.environ.copy()
            merged.update(self.env)
            env = merged
        else:
            env = None

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
                env=env,
                creationflags=_WIN_CREATION_FLAGS,
            )
        except Exception as e:
            print(f"[McpHost] Process spawn error ({full_cmd}): {e}")
            return False

        self._running = True
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()
        # SECURITY/CORRECTNESS: stderr MUST be drained. The original code opened
        # a stderr pipe and never read it, so any MCP server that wrote more
        # than the OS pipe buffer (~64KB on Windows) blocked forever on write.
        # chrome-devtools-mcp is chatty, so this manifested as tools randomly
        # "timing out" for reasons unrelated to the tool.
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_thread.start()

        init_req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "jarvis-mcp-client",
                    "version": "1.1.0"
                }
            }
        }

        res = self._send_request(init_req, timeout=timeout)
        if not res or "result" not in res:
            self.close()
            return False

        # Record what the server actually negotiated so mismatches are visible
        # instead of surfacing later as a confusing tools/call failure.
        result = res.get("result") or {}
        info = result.get("serverInfo") or {}
        self.server_name = str(info.get("name") or "")
        self.server_version = str(info.get("version") or "")
        self.protocol_version = str(result.get("protocolVersion") or PROTOCOL_VERSION)
        if self.protocol_version != PROTOCOL_VERSION:
            print(f"[McpHost] protocol mismatch: server={self.protocol_version} "
                  f"client={PROTOCOL_VERSION}")

        self._send_notification({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        })
        return True

    def _drain_stderr(self) -> None:
        """Consume stderr continuously, keeping a short tail for diagnostics."""
        if not (self.proc and self.proc.stderr):
            return
        try:
            for line in iter(self.proc.stderr.readline, ''):
                if not line:
                    break
                self._stderr_tail.append(line.rstrip())
                # Bound the tail; a crashed server can emit a lot.
                if len(self._stderr_tail) > 50:
                    del self._stderr_tail[:-50]
        except Exception:
            pass

    def stderr_tail(self, n: int = 20) -> str:
        return "\n".join(self._stderr_tail[-n:])

    def _next_id(self) -> int:
        with self._lock:
            self._msg_id += 1
            return self._msg_id

    def _read_loop(self) -> None:
        """Background stdout reader that demuxes JSON-RPC traffic.

        Two things the original loop did wrong:
        1. A single unparseable line raised out of the inner try and hit the
           outer `except: break`, killing the session for good. A server that
           prints a banner or a stray line to stdout would break the channel.
        2. Server-initiated requests (roots/list_request, sampling/createMessage)
           were dropped silently. We answer the ones we can and ignore the rest,
           so the server is never left waiting.
        """
        while self._running and self.proc and self.proc.stdout:
            try:
                line = self.proc.stdout.readline()
            except Exception:
                break
            if not line:
                break
            line_str = line.strip()
            if not line_str.startswith("{"):
                # Non-JSON noise on stdout (banners, warnings) — ignore it.
                continue
            try:
                payload = json.loads(line_str)
            except Exception:
                # A malformed line must NOT end the session.
                continue

            try:
                req_id = payload.get("id")
                if req_id is not None:
                    with self._lock:
                        q = self._responses.get(req_id)
                    if q is not None:
                        q.put(payload)
                        continue
                # No pending response with this id: it is server -> client.
                self._handle_server_request(payload)
            except Exception:
                continue

    def _handle_server_request(self, payload: Dict[str, Any]) -> None:
        """Answer the server-initiated requests MCP servers legitimately send.

        We declare no roots and do no sampling, so we reply with empty results
        rather than staying silent (which can leave the server blocked).
        """
        if "method" not in payload or payload.get("id") is None:
            # A notification from the server. tools/list_changed invalidates
            # our cache so the next call re-reads the tool list.
            if payload.get("method") == "notifications/tools/list_changed":
                self._tools_cache = None
            return

        method = payload.get("method")
        result: Dict[str, Any] = {}
        if method == "roots/list":
            result = {"roots": []}
        elif method in ("sampling/createMessage",):
            result = {}
        elif method == "ping":
            result = {}
        else:
            return  # Unknown method: stay quiet rather than guess.

        try:
            self._send_raw({
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": result,
            })
        except Exception:
            pass

    def _send_raw(self, msg: Dict[str, Any]) -> None:
        """Serialised, newline-delimited write. All writes funnel through here."""
        if not self.proc or not self.proc.stdin:
            return
        line = json.dumps(msg) + "\n"
        with self._write_lock:
            self.proc.stdin.write(line)
            self.proc.stdin.flush()

    def _send_request(self, req: Dict[str, Any], timeout: float = 15.0) -> Optional[Dict[str, Any]]:
        if not self.proc or not self.proc.stdin:
            return None
        req_id = req["id"]
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._responses[req_id] = q

        try:
            # Writes go through _send_raw so concurrent callers cannot interleave
            # partial lines and corrupt the JSON-RPC stream.
            self._send_raw(req)
            return q.get(timeout=timeout)
        except Exception:
            return None
        finally:
            with self._lock:
                self._responses.pop(req_id, None)

    def _send_notification(self, notif: Dict[str, Any]) -> None:
        try:
            self._send_raw(notif)
        except Exception:
            pass

    def list_tools(self, timeout: float = 10.0, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Query available tools exposed by the MCP server.

        The result is cached: the manager calls this once at startup to build
        Gemini's tool declarations, and the list only changes on a
        tools/list_changed notification (which clears the cache).
        """
        if use_cache and self._tools_cache is not None:
            return self._tools_cache
        req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
            "params": {}
        }
        res = self._send_request(req, timeout=timeout)
        if res and "result" in res:
            tools = res["result"].get("tools", []) or []
            self._tools_cache = tools
            return tools
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

    def is_alive(self) -> bool:
        return bool(self.proc and self.proc.poll() is None)

    def restart(self, timeout: float = 20.0) -> bool:
        """Close and re-open the transport.

        A crashed MCP server should not require restarting the whole assistant;
        the manager calls this after a failed call and retries once.
        """
        self.close()
        self._tools_cache = None
        self._stderr_tail = []
        self._msg_id = 0
        return self.start(timeout=timeout)

    def close(self) -> None:
        """Gracefully close and terminate the subprocess.

        Also clears the pending-response queues: without this, any in-flight
        caller blocked in q.get(timeout=...) waits out its full timeout even
        though the session is gone. Failing them fast lets the caller fall
        through to a restart.
        """
        self._running = False
        proc, self.proc = self.proc, None
        # Unblock everyone waiting on a response that can no longer arrive.
        with self._lock:
            pending = list(self._responses.values())
            self._responses.clear()
        for q in pending:
            try:
                q.put({"error": {"code": -32000, "message": "session closed"}})
            except Exception:
                pass
        if proc:
            try:
                if proc.stdin:
                    proc.stdin.close()
            except Exception:
                pass
            try:
                proc.terminate()
                proc.wait(timeout=2.0)
            except Exception:
                try:
                    proc.kill()
                    proc.wait(timeout=1.0)
                except Exception:
                    pass
        self._tools_cache = None


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
