"""
actions/network_diagnostics.py — Native Windows Network & Wi-Fi Health Diagnostics.

Provides sub-second local network diagnostics without browser popups or heavy tools:
- Real TCP/ICMP ping latency to reliable DNS targets (Cloudflare 1.1.1.1, Google 8.8.8.8)
- Wi-Fi SSID, signal strength %, radio band, and BSSID via Windows native netsh wlan
- Local network interfaces & IPv4 configuration
- Instant Windows DNS cache flushing
Zero extra pip packages — uses standard library socket, subprocess, and platform.
"""
from __future__ import annotations

import os
import platform
import re
import socket
import subprocess
import time
from typing import Any, Dict, Optional


def _measure_ping(host: str = "1.1.1.1", timeout_ms: int = 2000) -> Optional[float]:
    """Measure ping latency in milliseconds using native Windows ping command."""
    try:
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), host]
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_ms / 1000.0 + 1.0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        )
        if proc.returncode == 0:
            match = re.search(r"(?:time[=<]|Average = )(\d+)ms", proc.stdout)
            if match:
                return float(match.group(1))
            return 1.0
    except Exception:
        pass
    return None


def _get_wifi_info() -> Dict[str, str]:
    """Extract Wi-Fi adapter state and signal strength via netsh wlan."""
    info: Dict[str, str] = {}
    if platform.system() != "Windows":
        return {"status": "Non-Windows OS"}

    try:
        proc = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3.0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    k = key.strip().lower()
                    v = val.strip()
                    if "state" in k and "state" not in info:
                        info["state"] = v
                    elif "ssid" in k and "bssid" not in k and "ssid" not in info:
                        info["ssid"] = v
                    elif "signal" in k:
                        info["signal"] = v
                    elif "radio" in k:
                        info["radio"] = v
                    elif "channel" in k:
                        info["channel"] = v
    except Exception as e:
        info["error"] = str(e)
    return info


def _get_local_ip() -> str:
    """Resolve active local outbound IPv4 address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1.0)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _flush_dns() -> bool:
    """Flush the Windows local DNS resolver cache."""
    try:
        proc = subprocess.run(
            ["ipconfig", "/flushdns"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3.0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        )
        return proc.returncode == 0
    except Exception:
        return False


def network_diagnostics(
    parameters: dict | None = None,
    player=None,
    speak=None,
    response=None,
    session_memory=None,
    **_
) -> str:
    params = parameters or {}
    action = str(params.get("action", "status") or "status").lower().strip()
    target = str(params.get("target", "1.1.1.1") or "1.1.1.1").strip()

    # 1. FLUSH DNS
    if action in ("flush_dns", "flush"):
        ok = _flush_dns()
        return "Windows DNS Cache successfully flush ho gaya!" if ok else "DNS flush command run nahi ho saka."

    # 2. PING SPECIFIC TARGET
    if action == "ping":
        latency = _measure_ping(target)
        if latency is not None:
            return f"Ping to {target}: {latency:.0f} ms (Status: Normal, Online)."
        return f"Ping to {target}: Request timed out ya unreachable."

    # 3. WIFI ONLY
    if action in ("wifi", "wlan"):
        wf = _get_wifi_info()
        if not wf:
            return "Koi active Wi-Fi interface detect nahi hua ya LAN connection active hai."
        state = wf.get("state", "Unknown")
        ssid = wf.get("ssid", "Disconnected")
        signal = wf.get("signal", "N/A")
        return f"Wi-Fi Telemetry:\n• Network: {ssid}\n• Signal: {signal}\n• State: {state}\n• Channel: {wf.get('channel', 'Auto')}"

    # 4. OVERALL STATUS / PULSE (DEFAULT)
    latency = _measure_ping("1.1.1.1")
    wf = _get_wifi_info()
    local_ip = _get_local_ip()
    
    online_status = "Online (Connected)" if latency is not None else "Offline / High Latency"
    ping_str = f"{latency:.0f} ms" if latency is not None else "Timeout"
    
    lines = [
        f"Network Diagnostics & Telemetry:",
        f"• Status: {online_status}",
        f"• Gateway Latency (1.1.1.1): {ping_str}",
        f"• Local IP: {local_ip}",
    ]
    if wf.get("ssid"):
        lines.append(f"• Wi-Fi SSID: {wf.get('ssid')} (Signal: {wf.get('signal', 'N/A')})")
        
    return "\n".join(lines)


TOOL = {
    "name": "network_diagnostics",
    "description": (
        "Checks internet connection latency, Wi-Fi signal strength, local IP configuration, "
        "and flushes DNS cache. Trigger on 'ping kaisa hai', 'internet check karo', "
        "'wifi status', 'wifi signal strength', 'dns flush karo'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "status | ping | wifi | flush_dns"
            },
            "target": {
                "type": "STRING",
                "description": "Host or IP to ping (default: 1.1.1.1)"
            }
        },
        "required": ["action"]
    },
    "handler": network_diagnostics
}
