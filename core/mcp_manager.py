"""
core/mcp_manager.py — Config-driven MCP server pool for J.A.R.V.I.S.

WHAT THIS CHANGES
-----------------
Before this module, core/mcp_host.py existed but was used exactly once, by
actions/mcp_chrome.py, with the chrome-devtools-mcp command hardcoded. The
`list_tools()` method was dead code — never called anywhere. That meant:

  * there was no way to add an MCP server without editing Python source,
  * there was no `mcpServers` config file (a grep for "mcpServers" across the
    repo returned zero hits),
  * every tool call spawned a fresh process and paid the handshake again.

This module makes MCP servers declarative. Drop a JSON block into
config/mcp_servers.json and its tools join the assistant's tool list:

    {
      "mcpServers": {
        "websift": {
          "command": "websift",
          "args": ["serve", "--transport", "stdio"]
        },
        "chrome-devtools": {
          "command": "npx",
          "args": ["-y", "chrome-devtools-mcp@latest"]
        }
      }
    }

That is the same shape used by Claude Desktop / Cursor / VS Code, so an existing
config can be pasted in unchanged.

DESIGN NOTES
------------
* Sessions are long-lived and created lazily on first tool call. Starting every
  server at boot would add seconds of latency and RAM for servers the user may
  never invoke that day.
* Servers are spawned with an explicit, minimal environment. A config file is
  still executable code, but it should not silently inherit a huge ambient
  environment.
* A server that cannot start is disabled with a reason rather than crashing the
  assistant — MCP is additive, so a missing optional server must never be fatal.
* Tool names are namespaced ("mcp__<server>__<tool>") so two servers exposing
  "search" cannot collide, and so Gemini sees a stable, unambiguous name.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from core.mcp_host import McpSession, PROTOCOL_VERSION
except Exception:  # pragma: no cover - defensive
    McpSession = None  # type: ignore
    PROTOCOL_VERSION = "2024-11-05"


_BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = _BASE_DIR / "config" / "mcp_servers.json"

# Only these variables are inherited by spawned MCP servers. Anything else in
# the user's environment (tokens for cloud SDKs, CI credentials, ...) is not
# passed to a third-party process that we merely want to talk JSON-RPC with.
_ENV_PASSTHROUGH = (
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP",
    "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMFILES",
    "PROGRAMFILES(X86)", "PROGRAMDATA", "HOMEDRIVE", "HOMEPATH",
    "LANG", "LC_ALL", "TZ", "SHELL",
    # Node/npx resolution
    "APPDATA\\npm", "NVM_HOME", "NVM_SYMLINK", "NODE_PATH",
    # Python resolution for `python -m ...` style servers
    "VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH",
)

_DEFAULT_START_TIMEOUT = 25.0
_DEFAULT_CALL_TIMEOUT = 60.0


def _build_env(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    env: Dict[str, str] = {}
    for key in _ENV_PASSTHROUGH:
        val = os.environ.get(key)
        if val is not None:
            env[key] = val
    if extra:
        env.update({str(k): str(v) for k, v in extra.items()})
    return env


@dataclass
class McpServerSpec:
    """One entry from the mcpServers config block."""
    name: str
    command: str
    args: List[str] = field(default_factory=list)
    cwd: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    auto_start: bool = False
    startup_timeout: float = _DEFAULT_START_TIMEOUT
    call_timeout: float = _DEFAULT_CALL_TIMEOUT
    description: str = ""


@dataclass
class McpServerState:
    """Runtime state for a configured server."""
    spec: McpServerSpec
    session: Any = None
    tools: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "not_started"   # not_started | starting | ready | error | disabled
    error: str = ""
    started_at: float = 0.0
    last_used: float = 0.0
    call_count: int = 0
    error_count: int = 0

    def describe(self) -> str:
        if self.status == "disabled":
            return f"{self.spec.name}: disabled ({self.error or 'disabled in config'})"
        if self.status == "ready":
            uptime = int(time.time() - self.started_at) if self.started_at else 0
            return (f"{self.spec.name}: ready — {len(self.tools)} tool(s), "
                    f"up {uptime}s, {self.call_count} call(s)"
                    + (f", {self.error_count} error(s)" if self.error_count else ""))
        return f"{self.spec.name}: {self.status}" + (f" — {self.error}" if self.error else "")


class McpManager:
    """Owns every configured MCP server and exposes a flat tool namespace."""

    def __init__(self, config_path: Path = CONFIG_PATH,
                 logger: Optional[Callable[[str], None]] = None):
        self._config_path = Path(config_path)
        self._log = logger or (lambda m: print(f"[MCP] {m}"))
        self._servers: Dict[str, McpServerState] = {}
        self._lock = threading.RLock()
        self._loaded = False

    # ── config ──────────────────────────────────────────────────────────────

    def load_config(self, force: bool = False) -> int:
        """Read config/mcp_servers.json. Returns the number of enabled servers.

        Never raises. A missing file simply means "no MCP servers configured",
        which is the normal state for a fresh clone.
        """
        with self._lock:
            if self._loaded and not force:
                return sum(1 for s in self._servers.values() if s.spec.enabled)
            self._loaded = True
            self._servers.clear()

            if not self._config_path.exists():
                return 0

            try:
                raw = json.loads(self._config_path.read_text(encoding="utf-8"))
            except Exception as e:
                self._log(f"config parse failed ({self._config_path}): {e}")
                return 0

            # Accept both {"mcpServers": {...}} and a bare {...} mapping, and
            # also the list form [{"name":..., "command":...}, ...].
            block = raw.get("mcpServers") if isinstance(raw, dict) else None
            entries: Dict[str, Any] = {}
            if isinstance(block, dict):
                entries = block
            elif isinstance(block, list):
                entries = {e.get("name", f"server{i}"): e for i, e in enumerate(block)
                           if isinstance(e, dict)}
            elif isinstance(raw, dict):
                entries = raw  # bare mapping form

            for name, cfg in entries.items():
                if not isinstance(cfg, dict):
                    continue
                spec = self._parse_spec(str(name), cfg)
                if spec is None:
                    continue
                state = McpServerState(spec=spec)
                if not spec.enabled:
                    state.status = "disabled"
                    state.error = "disabled in config"
                self._servers[spec.name] = state

            enabled = sum(1 for s in self._servers.values() if s.spec.enabled)
            self._log(f"config loaded — {enabled} enabled / {len(self._servers)} total")
            return enabled

    def _parse_spec(self, name: str, cfg: Dict[str, Any]) -> Optional[McpServerSpec]:
        command = str(cfg.get("command") or "").strip()
        if not command:
            self._log(f"{name}: skipped — no 'command'")
            return None
        args = cfg.get("args") or []
        if isinstance(args, str):
            args = [args]
        if not isinstance(args, list):
            args = []
        try:
            return McpServerSpec(
                name=name,
                command=command,
                args=[str(a) for a in args],
                cwd=str(cfg["cwd"]) if cfg.get("cwd") else None,
                env={str(k): str(v) for k, v in (cfg.get("env") or {}).items()},
                enabled=bool(cfg.get("enabled", True)),
                auto_start=bool(cfg.get("auto_start", False)),
                startup_timeout=float(cfg.get("startup_timeout", _DEFAULT_START_TIMEOUT)),
                call_timeout=float(cfg.get("call_timeout", _DEFAULT_CALL_TIMEOUT)),
                description=str(cfg.get("description") or ""),
            )
        except Exception as e:
            self._log(f"{name}: invalid spec — {e}")
            return None

    # ── lifecycle ───────────────────────────────────────────────────────────

    def _resolve_command(self, command: str) -> Optional[str]:
        """Locate the executable so a missing binary is reported as a clear
        'not installed' rather than a WinError 2 from Popen."""
        found = shutil.which(command)
        if found:
            return found
        if os.path.isfile(command) and os.access(command, os.X_OK):
            return command
        # Windows batch shims often resolve only with the extension.
        if os.name == "nt":
            for ext in (".cmd", ".bat", ".exe"):
                cand = command + ext
                if os.path.isfile(cand):
                    return cand
        return None

    def start_server(self, name: str) -> bool:
        """Start one server (idempotent). Returns True when the session is live.

        Loads the config first if it has not been read yet, so callers never
        have to remember to call load_config() first.
        """
        with self._lock:
            if not self._loaded:
                self.load_config()
            state = self._servers.get(name)
            if state is None:
                return False
            if state.session is not None and state.session.is_alive():
                return True
            if not state.spec.enabled:
                state.status = "disabled"
                return False
            if McpSession is None:
                state.status = "error"
                state.error = "core.mcp_host unavailable"
                return False

            resolved = self._resolve_command(state.spec.command)
            if resolved is None:
                state.status = "error"
                state.error = (f"command not found: '{state.spec.command}' — "
                               "install it, or set \"enabled\": false")
                self._log(f"{name}: {state.error}")
                return False

            state.status = "starting"
            state.error = ""
            session = McpSession(
                command=resolved,
                args=state.spec.args,
                cwd=Path(state.spec.cwd) if state.spec.cwd else None,
                env=_build_env(state.spec.env),
            )
            ok = False
            try:
                ok = session.start(timeout=state.spec.startup_timeout)
            except Exception as e:
                state.error = f"start failed: {e}"

            if not ok:
                tail = session.stderr_tail(8)
                state.status = "error"
                state.error = (state.error or "handshake failed") + (
                    f"\n{tail}" if tail else "")
                try:
                    session.close()
                except Exception:
                    pass
                self._log(f"{name}: startup failed — {state.error.splitlines()[0]}")
                return False

            state.session = session
            state.status = "ready"
            state.started_at = time.time()
            try:
                state.tools = session.list_tools(timeout=15.0)
            except Exception as e:
                state.tools = []
                self._log(f"{name}: tools/list failed — {e}")
            self._log(f"{name}: ready — {len(state.tools)} tool(s) "
                      f"(server={state.session.server_name or '?'} "
                      f"{state.session.server_version or ''}, "
                      f"proto={state.session.protocol_version})")
            return True

    def start_auto(self) -> int:
        """Start only the servers marked auto_start. Cheap by default."""
        started = 0
        for name, state in list(self._servers.items()):
            if state.spec.enabled and state.spec.auto_start:
                if self.start_server(name):
                    started += 1
        return started

    def stop_all(self) -> None:
        with self._lock:
            for state in self._servers.values():
                if state.session is not None:
                    try:
                        state.session.close()
                    except Exception:
                        pass
                state.session = None
                state.status = "not_started"

    # ── tool namespace ──────────────────────────────────────────────────────

    @staticmethod
    def tool_name(server: str, tool: str) -> str:
        """Namespaced, Gemini-safe tool name."""
        safe_server = "".join(c if (c.isalnum() or c == "_") else "_" for c in server)
        safe_tool = "".join(c if (c.isalnum() or c == "_") else "_" for c in tool)
        return f"mcp__{safe_server}__{safe_tool}"[:58]

    @staticmethod
    def _split_tool_name(full: str) -> Optional[Tuple[str, str]]:
        if not full.startswith("mcp__"):
            return None
        parts = full.split("__", 2)
        if len(parts) != 3 or not parts[1] or not parts[2]:
            return None
        return parts[1], parts[2]

    def all_tool_declarations(self, include_offline: bool = False) -> List[Dict[str, Any]]:
        """Gemini function-calling declarations for every discovered MCP tool.

        include_offline=True will start servers that have not been started yet,
        which is what the assistant does once at boot.
        """
        with self._lock:
            self.load_config()

        declarations: List[Dict[str, Any]] = []
        for name, state in list(self._servers.items()):
            if not state.spec.enabled:
                continue
            if state.session is None or not state.session.is_alive():
                if not include_offline:
                    continue
                if not self.start_server(name):
                    continue
            for tool in state.tools or []:
                tname = tool.get("name")
                if not tname:
                    continue
                desc = str(tool.get("description") or "") or f"{tname} via MCP server '{name}'"
                schema = tool.get("inputSchema") or tool.get("input_schema")
                if not isinstance(schema, dict):
                    schema = {"type": "OBJECT", "properties": {}}
                # Gemini rejects an empty "required" list and some MCP servers
                # emit one; normalise defensively.
                req = schema.get("required")
                if isinstance(req, list) and not req:
                    schema = {k: v for k, v in schema.items() if k != "required"}
                declarations.append({
                    "name": self.tool_name(name, tname),
                    "description": f"[MCP:{name}] {desc}"[:900],
                    "parameters": schema,
                })
        return declarations

    def call_tool(self, full_name: str, arguments: Dict[str, Any]) -> Tuple[bool, str]:
        """Invoke a namespaced tool, starting its server on demand.

        Returns (ok, output_text). A dead server is restarted once and the call
        retried, so a crashed optional server does not permanently break the
        assistant.
        """
        parsed = self._split_tool_name(full_name)
        if not parsed:
            return False, f"'{full_name}' is not a valid MCP tool name."
        server_hint, tool = parsed

        with self._lock:
            self.load_config()
            state = self._find_state(server_hint, tool)
            if state is None:
                # A never-started server has an empty tool list, so _find_state
                # cannot match on tool name. Fall back to matching the server
                # key alone: the declaration was produced from a previous
                # discovery pass, so the server exists and is ours to start.
                if server_hint in self._servers:
                    state = self._servers[server_hint]
                else:
                    state = self._find_state_by_prefix(server_hint)
            if state is None:
                return False, f"MCP tool '{full_name}' is not available."
            spec = state.spec

        if state.session is None or not state.session.is_alive():
            if not self.start_server(spec.name):
                return False, (f"MCP server '{spec.name}' unavailable: "
                               f"{state.error or 'unknown error'}")
            state = self._servers[spec.name]

        state.call_count += 1
        state.last_used = time.time()

        def _invoke() -> Tuple[bool, str]:
            res = state.session.call_tool(tool, arguments or {},
                                          timeout=spec.call_timeout)
            if not res:
                return False, (f"MCP call timed out or returned nothing "
                               f"(server stderr: {state.session.stderr_tail(5)})")
            if "error" in res:
                err = res["error"] or {}
                if isinstance(err, dict):
                    return False, f"MCP error {err.get('code')}: {err.get('message')}"
                return False, f"MCP error: {err}"
            result = res.get("result") or {}
            blocks = result.get("content") or []
            texts = [b.get("text", "") for b in blocks
                     if isinstance(b, dict) and b.get("type") == "text"]
            if texts:
                return True, "\n".join(t for t in texts if t)
            if result.get("isError"):
                return False, json.dumps(result)[:1500]
            return True, json.dumps(result, indent=2)[:4000]

        ok, out = _invoke()
        if not ok and state.session is not None and not state.session.is_alive():
            # Server died mid-call. Restart once and retry.
            self._log(f"{spec.name}: server died, restarting and retrying once")
            if self.start_server(spec.name):
                state = self._servers[spec.name]
                ok, out = _invoke()

        if ok:
            state.status = "ready"
            state.error = ""
        else:
            state.error_count += 1
        return ok, out

    def _find_state(self, server_hint: str, tool: str) -> Optional[McpServerState]:
        """Resolve a state by namespaced name; the sanitised form may differ
        from the config key (e.g. dashes become underscores)."""
        if server_hint in self._servers:
            state = self._servers[server_hint]
            if any(t.get("name") == tool for t in state.tools):
                return state
        for state in self._servers.values():
            if not state.spec.enabled:
                continue
            sanitised = self.tool_name(state.spec.name, state.spec.name)
            # sanitised is mcp__<name>__<name>; compare only the server segment.
            parts = sanitised.split("__")
            if len(parts) >= 2 and parts[1] == server_hint:
                return state
        for state in self._servers.values():
            if not state.spec.enabled:
                continue
            for t in state.tools or []:
                if t.get("name") == tool and self.tool_name(
                        state.spec.name, str(t.get("name"))) == f"mcp__{server_hint}__{tool}":
                    return state
        return None

    def _find_state_by_prefix(self, server_hint: str) -> Optional[McpServerState]:
        """Match a server by its sanitised namespace, for the case where the
        tool list is not yet populated (server never started)."""
        for state in self._servers.values():
            if not state.spec.enabled:
                continue
            parts = self.tool_name(state.spec.name, state.spec.name).split("__")
            if len(parts) >= 2 and parts[1] == server_hint:
                return state
        return None

    # ── diagnostics ─────────────────────────────────────────────────────────

    def status_lines(self) -> List[str]:
        with self._lock:
            self.load_config()
            if not self._servers:
                return ["No MCP servers configured "
                        f"(add them to {self._config_path.name})."]
            return [s.describe() for s in self._servers.values()]

    def summary(self) -> str:
        with self._lock:
            self.load_config()
            if not self._servers:
                return (f" MCP: koi server configured nahi ({self._config_path.name} "
                        "me add karo).")
            ready = sum(1 for s in self._servers.values() if s.status == "ready")
            total_tools = sum(len(s.tools) for s in self._servers.values())
            lines = [f"🔌 MCP: {ready}/{len(self._servers)} server(s) ready, "
                     f"{total_tools} tool(s) available."]
            for s in self._servers.values():
                lines.append(f"   • {s.describe()}")
            return "\n".join(lines)


# ── module singleton ────────────────────────────────────────────────────────

_MANAGER: Optional[McpManager] = None
_MANAGER_LOCK = threading.Lock()


def get_mcp_manager(config_path: Path = CONFIG_PATH) -> McpManager:
    """Process-wide manager. Cheap to call repeatedly."""
    global _MANAGER
    with _MANAGER_LOCK:
        if _MANAGER is None:
            _MANAGER = McpManager(config_path)
        return _MANAGER