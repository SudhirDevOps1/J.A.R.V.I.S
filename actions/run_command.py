"""Run shell commands safely — allowlist instant, baaki confirm-gated + audit-logged.
New file, auto-discovered. Existing scattered subprocess calls untouched.
"""
from __future__ import annotations

import platform
import shutil
import subprocess

_SYSTEM = platform.system()

# Instant chalega (read-only / harmless)
_ALLOW_PREFIX = (
    "dir", "echo", "whoami", "hostname", "ver", "systeminfo",
    "ipconfig", "ping", "tracert", "nslookup",
    "tasklist", "ps", "ls", "pwd", "df", "free",
    "winget list", "winget search", "git status", "git log", "git diff",
    "python --version", "pip list", "node --version", "npm list",
)
# Kabhi nahi chalega (model bhi bole to refuse)
_BLOCK_PATTERNS = (
    "format ", "del /f", "rm -rf /", "rm -rf ~", "mkfs",
    "reg delete", "regedit /s", ":(){:|:&};:",
    "cipher /w", "shutdown /p", "> /dev/sda",
)


def _log(player, msg: str) -> None:
    try:
        if player:
            player.write_log(msg)
    except Exception:
        pass
    print(msg)


def _audit(action: str, detail: str = "", confirmed: bool = False) -> None:
    try:
        from core.audit import log_event as _ae
        _ae(action, detail, confirmed)
    except Exception:
        pass


def _is_blocked(cmd: str) -> str | None:
    low = f" {cmd.lower().strip()} "
    for pat in _BLOCK_PATTERNS:
        if pat in low:
            return pat.strip()
    return None


def _is_allowed(cmd: str) -> bool:
    low = cmd.lower().strip()
    return any(low == a or low.startswith(a + " ") or low.startswith(a + ";") for a in _ALLOW_PREFIX)


def _exec(cmd: str, timeout: int = 25) -> str:
    try:
        if _SYSTEM == "Windows":
            r = subprocess.run(["cmd", "/c", cmd], capture_output=True, text=True, timeout=timeout)
        else:
            r = subprocess.run(["bash", "-lc", cmd], capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "").strip()[:3000]
        err = (r.stderr or "").strip()[:500]
        if r.returncode != 0:
            return f"Exit {r.returncode}. {out}\n{err}".strip()
        return out or "(koi output nahi)"
    except subprocess.TimeoutExpired:
        return f"Timeout ({timeout}s) — command bahut lambi chali."
    except Exception as e:
        return f"Run failed: {e}"


def run_command(parameters: dict | None = None, player=None, session_memory=None, **_) -> str:
    params = parameters or {}
    cmd = str(params.get("command", "") or "").strip()
    if not cmd:
        return "Please specify a command to run."
    if len(cmd) > 500:
        return "Command bahut lamba hai (max 500 chars)."
    blocked = _is_blocked(cmd)
    if blocked:
        _audit("run_command_blocked", cmd)
        _log(player, f"[run] BLOCKED: {cmd[:60]}")
        return f"Ye command dangerous hai ('{blocked}') — main ise nahi chalaunga."
    if _is_allowed(cmd):
        out = _exec(cmd)
        _audit("run_command", cmd)
        _log(player, f"[run] {cmd[:60]}")
        return f"Output:\n{out}"
    # Unknown/risky → confirm gate (model khud confirm nahi kar sakta)
    try:
        from core import confirm as _cg
        if _cg.pending_title():
            return ("Ek confirmation pehle se pending hai. Pehle use CONFIRM/CANCEL karo, "
                    "phir ye command dobara bolo.")
        _audit("run_command_asked", cmd)

        def _do() -> str:
            out = _exec(cmd)
            _audit("run_command", cmd, confirmed=True)
            return out

        return _cg.request("run_command", f"Run: {cmd[:60]}",
                           f"Command: {cmd}\nTimeout: 25s. CONFIRM dabane par chalega.", _do)
    except Exception as e:
        return f"Confirm gate unavailable: {e}. Sirf allowlist commands chala sakta hu."


TOOL = {
    "name": "run_command",
    "description": (
        "Run a shell/PowerShell/Terminal command safely. Read-only commands run instantly; "
        "unknown ones ask HUD confirmation; destructive ones are refused. "
        "Trigger on 'cmd se check karo', 'command chalao', 'terminal me dikhao'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "command": {"type": "STRING", "description": "Command text, max 500 chars"},
        },
        "required": ["command"],
    },
    "handler": run_command,
}
