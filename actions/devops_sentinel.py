"""
Autonomous DevOps Terminal Sentinel.
Monitors long-running terminal builds, test suites, and background processes.
Detects crashes, compiler failures, and exceptions in real-time and alerts via HUD and voice.
"""
from __future__ import annotations

import os
import re
import shlex
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Active sentinel watch jobs: job_id -> dict
_WATCH_JOBS: Dict[str, Dict[str, Any]] = {}
_LAST_ERROR_DIAGNOSIS: Optional[str] = None

def _audit(action: str, detail: str = "", confirmed: bool = False) -> None:
    """Audit hook. Mirrors actions/run_command._audit so sentinel decisions are
    recorded in the same audit log. Never raises — an audit failure must not
    break the action, but it is reported rather than silently discarded."""
    try:
        from core.audit import log_event as _ae
        _ae(action, detail, confirmed)
    except Exception as e:
        print(f"[DevOpsSentinel] audit write failed ({action}): {e}")


_COMMON_ERROR_PATTERNS = [
    (r"ModuleNotFoundError:\s*No module named '([^']+)'", r"Python dependency missing: 'pip install \1' karein."),
    (r"ImportError:\s*cannot import name '([^']+)'", r"Circular import ya library version mismatch: '\1' nahi mila."),
    (r"address already in use[:\s]+(\d+)|port\s+(\d+)\s+is already in use", r"Port busy hai. Dusra port use karein ya process kill karein."),
    (r"PermissionDenied|Access is denied|EACCES", r"Permission denied: Administrator privileges ya file permissions check karein."),
    (r"SyntaxError:\s*(.+)", r"Code me syntax error hai: \1"),
    (r"npm ERR!\s*code\s*(\w+)", r"NPM error (\1): 'npm install' ya node_modules clean karke retry karein."),
    (r"fatal: not a git repository", r"Ye directory git repository nahi hai."),
    (r"fatal: refusing to merge unrelated histories", r"Git histories mismatch: '--allow-unrelated-histories' flag use karein."),
]


def analyze_terminal_error(error_log: str) -> str:
    """Analyze a terminal crash or traceback and return an immediate diagnosis."""
    global _LAST_ERROR_DIAGNOSIS
    if not error_log or not error_log.strip():
        return "Koi error log provide nahi kiya gaya."

    lines = error_log.strip().splitlines()
    error_summary = "\n".join(lines[-10:])

    diagnosis = []
    for pat, fix in _COMMON_ERROR_PATTERNS:
        m = re.search(pat, error_log, re.IGNORECASE)
        if m:
            sugg = re.sub(pat, fix, m.group(0), flags=re.IGNORECASE)
            diagnosis.append(f"• Root Cause: {m.group(0)}\n• Suggestion: {sugg}")

    if not diagnosis:
        # Generic traceback extraction
        tb_lines = [l for l in lines if any(k in l.lower() for k in ("error", "exception", "failed", "fatal"))]
        highlight = "\n".join(tb_lines[:3]) if tb_lines else error_summary[:200]
        diagnosis.append(f"• Error Highlight: {highlight}\n• Suggestion: Traceback check karein ya 'screen dekho' bolkar visually debug karein.")

    result = "DevOps Sentinel Error Analysis:\n" + "\n".join(diagnosis)
    _LAST_ERROR_DIAGNOSIS = result
    return result


def _run_sentinel_worker(job_id: str, command: str, cwd: Optional[str], player=None, speak=None) -> None:
    """Background worker executing command and streaming outputs for error sentinel."""
    t0 = time.time()
    job = _WATCH_JOBS[job_id]
    job["status"] = "RUNNING"
    job["start_time"] = t0

    try:
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        job["pid"] = proc.pid

        stdout_chunks: List[str] = []
        stderr_chunks: List[str] = []
        # Cap retained output. These lists grew without bound until the process
        # exited, so a chatty command (`npm install`, a long build) could hold
        # hundreds of MB in RAM for the full 300s window. Keep a rolling tail:
        # the diagnostics only ever use the last ~2000 chars anyway.
        _MAX_CHUNK_CHARS = 200_000

        def read_pipe(pipe, chunk_list):
            for line in iter(pipe.readline, ''):
                chunk_list.append(line)
                if sum(len(c) for c in chunk_list) > _MAX_CHUNK_CHARS:
                    # Collapse to a tail rather than growing without bound.
                    chunk_list[:] = ["".join(chunk_list)[-_MAX_CHUNK_CHARS:]]
            pipe.close()

        t_out = threading.Thread(target=read_pipe, args=(proc.stdout, stdout_chunks), daemon=True)
        t_err = threading.Thread(target=read_pipe, args=(proc.stderr, stderr_chunks), daemon=True)
        t_out.start()
        t_err.start()

        ret = proc.wait(timeout=300)
        t_out.join(timeout=2)
        t_err.join(timeout=2)

        elapsed = round(time.time() - t0, 1)
        out_text = "".join(stdout_chunks)
        err_text = "".join(stderr_chunks)
        combined = f"{out_text}\n{err_text}"

        job["return_code"] = ret
        job["elapsed"] = elapsed
        job["output"] = combined[-2000:]

        if ret == 0:
            job["status"] = "SUCCESS"
            msg = f"DevOps Sentinel: '{command}' successfully finish ho gaya ({elapsed}s)."
            if player and hasattr(player, "write_log"):
                player.write_log(f"✅ [Sentinel] {msg}")
            if speak:
                speak(f"Command successfully complete ho gaya sir.")
        else:
            job["status"] = "FAILED"
            diag = analyze_terminal_error(combined)
            alert = f"🚨 [Sentinel] Command '{command}' FAILED (Exit {ret}). {diag}"
            if player and hasattr(player, "write_log"):
                player.write_log(alert)
            if speak:
                speak(f"Sir, monitored command me error aaya hai (Exit code {ret}). HUD par details check karein.")

    except subprocess.TimeoutExpired:
        job["status"] = "TIMEOUT"
        if player and hasattr(player, "write_log"):
            player.write_log(f"⚠️ [Sentinel] Command '{command}' timed out (5 min limit).")
    except Exception as e:
        job["status"] = "ERROR"
        job["error"] = str(e)
        if player and hasattr(player, "write_log"):
            player.write_log(f"🚨 [Sentinel] Execution error on '{command}': {e}")


def _sentinel_gate(command: str, cwd: Optional[str], player=None) -> Optional[str]:
    """Apply run_command's safety model to a sentinel command.

    SECURITY: this module used to hand the command straight to
    subprocess.Popen(..., shell=True) with NO allowlist, NO blocklist and NO
    confirmation gate — while run_command.py implemented all three carefully.
    Worse, core/edge_router.py routes plain spoken text ("watch command ...")
    straight into this action, so the shell was reachable by voice with no
    model in the loop at all. The only limit was a 300s timeout.

    Now the command is classified with run_command's own predicates:
      * blocked pattern            -> refused outright, audited
      * allowlisted (no shell ops)  -> runs in background, audited
      * anything else              -> requires HUD confirmation, audited
      * gate unavailable           -> REFUSED (fail closed, never open)

    Returns None to proceed, or a user-facing refusal string to stop.
    """
    cmd = (command or "").strip()
    if not cmd:
        return "Koi command di nahi gayi."
    if len(cmd) > 500:
        return "Command bahut lamba hai (max 500 chars)."

    try:
        from actions.run_command import _is_blocked, _is_allowed
    except Exception as e:
        return (f"Safety gate unavailable ({e}). Sentinel refuse karta hai — "
                "sirf allowlist commands chala sakta hu.")

    blocked = _is_blocked(cmd)
    if blocked:
        _audit("sentinel_blocked", cmd)
        return f"Ye command dangerous hai ('{blocked}') — main ise nahi chalaunga."

    if _is_allowed(cmd):
        _audit("sentinel_allowed", cmd)
        return None

    # Unknown / risky -> HUD confirmation gate, exactly like run_command.
    try:
        from core import confirm as _cg
        if _cg.pending_title():
            return ("Ek confirmation pehle se pending hai. Pehle CONFIRM/CANCEL karo, "
                    "phir ye command dobara bolo.")
        _audit("sentinel_asked", cmd)

        def _do() -> str:
            _audit("sentinel_confirmed", cmd)
            _launch(cmd, cwd, player)
            return f"Sirf background me chal raha hai: {cmd}"

        return _cg.request(
            "devops_sentinel",
            f"Sentinel: {cmd[:60]}",
            f"Command chalega: {cmd}\nCWD: {cwd or 'current'}\n"
            f"Timeout: 5 min. CONFIRM dabane par chalega.",
            _do,
        )
    except Exception as e:
        # FAIL CLOSED — same rule as run_command.py. macro.py has the opposite
        # bug (fails open on a gate error); do not repeat it here.
        return f"Confirm gate unavailable: {e}. Sentinel refuse karta hai."


def watch_command(command: str, cwd: Optional[str] = None, player=None, speak=None) -> str:
    """Launch a non-blocking background command watch (after the safety gate)."""
    verdict = _sentinel_gate(command, cwd, player)
    if verdict is not None:
        return verdict
    return _launch(command, cwd, player)


def _launch(command: str, cwd: Optional[str], player=None) -> str:
    job_id = f"job_{int(time.time())}_{len(_WATCH_JOBS) + 1}"
    _WATCH_JOBS[job_id] = {
        "id": job_id,
        "command": command,
        "cwd": cwd,
        "status": "QUEUED",
        "return_code": None,
        "elapsed": 0,
    }

    t = threading.Thread(
        target=_run_sentinel_worker,
        args=(job_id, command, cwd, player, None),
        daemon=True
    )
    t.start()

    return f"DevOps Sentinel: Command '{command}' background watch me shuru kar diya gaya hai (Job ID: {job_id})."


def get_sentinel_status() -> str:
    """Return status of all monitored commands."""
    if not _WATCH_JOBS:
        return "Filhal koi active DevOps Sentinel watch running nahi hai."

    lines = []
    for j_id, j in list(_WATCH_JOBS.items())[-5:]:
        cmd_short = j['command'][:40]
        lines.append(f"• [{j['status']}] {j_id}: '{cmd_short}' (Elapsed: {j['elapsed']}s, Exit: {j['return_code']})")

    return "DevOps Sentinel Jobs:\n" + "\n".join(lines)


def devops_sentinel(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """JARVIS action dispatcher for DevOps Sentinel."""
    params = parameters or {}
    action = str(params.get("action", "watch")).strip().lower()
    command = str(params.get("command", params.get("cmd", ""))).strip()
    error_log = str(params.get("error_log", params.get("log", ""))).strip()

    # Extract speak function if provided in context
    speak_fn = None
    if isinstance(response, dict) and "speak" in response:
        speak_fn = response["speak"]

    if action in ("analyze", "diagnose", "error"):
        return analyze_terminal_error(error_log or command or (_LAST_ERROR_DIAGNOSIS or ""))

    elif action in ("status", "list"):
        return get_sentinel_status()

    elif action in ("watch", "monitor", "run"):
        if not command:
            return "Kripya monitor karne ke liye command batayein (e.g. 'npm test' ya 'pytest')."
        return watch_command(command, player=player, speak=speak_fn)

    else:
        if command:
            return watch_command(command, player=player, speak=speak_fn)
        return get_sentinel_status()


TOOL = {
    "name": "devops_sentinel",
    "description": "Autonomous DevOps Terminal Sentinel. Watches long-running builds, test suites, or background processes, detects failures/tracebacks, and analyzes root causes.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'watch' (monitor a command), 'analyze' (diagnose error log), or 'status'."
            },
            "command": {
                "type": "STRING",
                "description": "Terminal command to monitor (e.g. 'pytest', 'npm run build', 'docker-compose up')."
            },
            "error_log": {
                "type": "STRING",
                "description": "Error traceback or terminal output to diagnose."
            }
        },
        "required": []
    },
    "handler": devops_sentinel,
}
