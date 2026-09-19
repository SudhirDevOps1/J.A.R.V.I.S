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

        def read_pipe(pipe, chunk_list):
            for line in iter(pipe.readline, ''):
                chunk_list.append(line)
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


def watch_command(command: str, cwd: Optional[str] = None, player=None, speak=None) -> str:
    """Launch a non-blocking background command watch."""
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
        args=(job_id, command, cwd, player, speak),
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
