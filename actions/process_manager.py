"""
actions/process_manager.py — Smart Process & Resource Manager for J.A.R.V.I.S.

Inspects top CPU and Memory consuming applications, lists running instances,
and safely terminates heavy or frozen user processes.
Includes a strict safety blocklist to protect core Windows system processes.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

_PROTECTED_PROCESSES = {
    "system", "system idle process", "registry", "smss.exe", "csrss.exe",
    "wininit.exe", "services.exe", "lsass.exe", "svchost.exe", "winlogon.exe",
    "explorer.exe", "spoolsv.exe", "dwm.exe", "taskhostw.exe", "sihost.exe",
    "smss", "csrss", "wininit", "services", "lsass", "svchost", "winlogon",
    "explorer", "spoolsv", "dwm", "taskhostw", "sihost", "systemd", "init"
}


def _get_top_processes(sort_by: str = "cpu", limit: int = 5) -> List[Dict[str, Any]]:
    if not _HAS_PSUTIL:
        return []

    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = p.info
            name = (info.get("name") or "").lower()
            if not name or name in ("system", "system idle process", "idle"):
                continue
            procs.append({
                "pid": info["pid"],
                "name": info["name"],
                "cpu": float(info.get("cpu_percent") or 0.0),
                "ram": float(info.get("memory_percent") or 0.0)
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if sort_by == "ram":
        procs.sort(key=lambda x: x["ram"], reverse=True)
    else:
        procs.sort(key=lambda x: x["cpu"], reverse=True)

    return procs[:limit]


def _kill_user_process(process_name: str) -> Dict[str, Any]:
    if not _HAS_PSUTIL:
        return {"ok": False, "msg": "psutil library available nahi hai."}

    clean_name = process_name.lower().strip()
    base_name = clean_name[:-4] if clean_name.endswith(".exe") else clean_name
    clean_target = base_name + ".exe"

    # Check protected list
    if base_name in _PROTECTED_PROCESSES or clean_target in _PROTECTED_PROCESSES or clean_name in _PROTECTED_PROCESSES:
        return {
            "ok": False,
            "msg": f"Security Guard: '{process_name}' Windows ka core system process hai aur ise band karna allowed nahi hai."
        }

    terminated = 0
    errors = 0
    for p in psutil.process_iter(["pid", "name"]):
        try:
            p_name = (p.info.get("name") or "").lower()
            if p_name in (clean_name, clean_target):
                p.terminate()
                terminated += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            errors += 1

    if terminated > 0:
        return {"ok": True, "msg": f"Successfully closed {terminated} instance(s) of '{process_name}'."}
    if errors > 0:
        return {"ok": False, "msg": f"'{process_name}' ko band karne ke liye Administrator permissions ki zaroorat hai."}
    return {"ok": False, "msg": f"'{process_name}' naam ka koi active process nahi mila."}


def process_manager(
    parameters: dict | None = None,
    player=None,
    speak=None,
    response=None,
    session_memory=None,
    **_
) -> str:
    params = parameters or {}
    action = str(params.get("action", "top_ram") or "top_ram").lower().strip()
    target = str(params.get("process_name", "") or "").strip()

    if not _HAS_PSUTIL:
        return "Process manager unavailable: psutil package missing."

    # 1. KILL PROCESS
    if action in ("kill", "terminate", "close"):
        if not target:
            return "Kis application ya process ko band karna hai? process_name batayein (e.g. 'chrome', 'node')."
        res = _kill_user_process(target)
        if player and res["ok"]:
            player.write_log(f"[ProcessManager] Terminated: {target}")
        return res["msg"]

    # 2. TOP CPU CONSUMERS
    if action in ("top_cpu", "cpu"):
        top_list = _get_top_processes(sort_by="cpu", limit=5)
        if not top_list:
            return "No user processes found."
        lines = ["Top CPU-Consuming Applications:"]
        for i, p in enumerate(top_list, 1):
            lines.append(f"{i}. {p['name']} (PID: {p['pid']}) — CPU: {p['cpu']:.1f}% | RAM: {p['ram']:.1f}%")
        return "\n".join(lines)

    # 3. TOP RAM CONSUMERS (DEFAULT)
    top_list = _get_top_processes(sort_by="ram", limit=5)
    if not top_list:
        return "No user processes found."
    lines = ["Top Memory (RAM)-Consuming Applications:"]
    for i, p in enumerate(top_list, 1):
        lines.append(f"{i}. {p['name']} (PID: {p['pid']}) — RAM: {p['ram']:.1f}% | CPU: {p['cpu']:.1f}%")
    return "\n".join(lines)


TOOL = {
    "name": "process_manager",
    "description": (
        "Monitors and manages running processes on the computer. Lists top CPU and RAM consuming "
        "applications, and safely closes hung or heavy user applications (e.g. Chrome, Node, Python). "
        "Trigger on 'top processes dikhao', 'kaunsa app sabse zyada ram le raha hai', "
        "'kill process chrome', 'chrome band karo'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "top_ram | top_cpu | kill"
            },
            "process_name": {
                "type": "STRING",
                "description": "Name of the process to kill when action is 'kill' (e.g. 'chrome', 'node', 'spotify')"
            }
        },
        "required": ["action"]
    },
    "handler": process_manager
}
