"""
0 MB Native System Utilities for J.A.R.V.I.S.
Pure Python Standard Library — Zero external dependencies, 0 MB extra RAM.
Provides:
  1. Native Windows Pop-up Alerts & Notifications via ctypes Win32 API.
  2. Native Process & RAM Monitor fallback via subprocess (tasklist / wmic).
  3. Native Web Scraper fallback via urllib.request + re.
  4. Native Wildcard File Pattern Matcher via fnmatch and glob.
"""
from __future__ import annotations

import ctypes
import json
import os
import platform
import re
import subprocess
import urllib.request
import urllib.parse
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_OS = platform.system()


# ── 1. Native Windows Pop-up Alerts (ctypes) ─────────────────────────────────
def show_native_alert(title: str, message: str, alert_type: str = "info") -> int:
    """
    Displays a native Windows MessageBox without Tkinter, PyQt, or extra GUI frameworks.
    0 MB RAM footprint.
    alert_type: "info" (0x40), "warning" (0x30), "error" (0x10), "question" (0x20)
    """
    if _OS != "Windows":
        print(f"[{title}] {message}")
        return 1

    icon_flags = {
        "info": 0x40 | 0x0,      # MB_ICONINFORMATION | MB_OK
        "warning": 0x30 | 0x0,   # MB_ICONWARNING | MB_OK
        "error": 0x10 | 0x0,     # MB_ICONERROR | MB_OK
        "confirm": 0x20 | 0x1,   # MB_ICONQUESTION | MB_OKCANCEL
    }
    flag = icon_flags.get(alert_type.lower(), 0x40 | 0x0)
    flag |= 0x40000  # MB_TOPMOST

    try:
        res = ctypes.windll.user32.MessageBoxW(0, str(message), str(title), flag)
        return res
    except Exception as e:
        print(f"[native_hacks] MessageBoxW fallback: {e}")
        return 0


# ── 2. Native Process & RAM Telemetry Fallback (subprocess) ───────────────────
def get_native_process_list() -> List[str]:
    """
    Returns running processes using native Windows tasklist.
    Acts as a zero-dependency fallback if psutil is unavailable.
    """
    if _OS != "Windows":
        try:
            out = subprocess.check_output(["ps", "-e", "-o", "comm="], text=True)
            return sorted(list(set(line.strip() for line in out.splitlines() if line.strip())))
        except Exception:
            return []

    try:
        cmd = ["tasklist", "/FO", "CSV", "/NH"]
        out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        processes = set()
        for line in out.splitlines():
            line = line.strip()
            if line.startswith('"'):
                name = line.split('","')[0].replace('"', '').replace('.exe', '')
                if name:
                    processes.add(name)
        return sorted(list(processes))
    except Exception as e:
        print(f"[native_hacks] tasklist error: {e}")
        return []


def is_native_process_running(process_name: str) -> bool:
    """Check if process is active via native Windows tasklist filter."""
    if _OS != "Windows":
        return process_name.lower() in [p.lower() for p in get_native_process_list()]

    clean = process_name.lower().replace(".exe", "").strip()
    try:
        cmd = f'tasklist /FI "IMAGENAME eq {clean}.exe" /NH'
        out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
        return clean in out.lower()
    except Exception:
        return False


def get_native_ram_usage() -> Optional[float]:
    """
    Queries current total RAM utilization percentage using Windows built-in CIM/WMI.
    """
    if _OS != "Windows":
        return None
    try:
        ps_cmd = "(Get-CimInstance Win32_OperatingSystem | ForEach-Object { [math]::Round((($_.TotalVisibleMemorySize - $_.FreePhysicalMemory) / $_.TotalVisibleMemorySize) * 100, 1) })"
        out = subprocess.check_output(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd], text=True, timeout=3)
        val = float(out.strip())
        return val
    except Exception:
        return None


# ── 3. Native 0 MB Web Scraper (urllib + re) ──────────────────────────────────
def native_web_scrape(url: str, timeout: int = 5) -> Dict[str, Any]:
    """
    Fetches web content using Python built-in urllib and parses meta/title via regex.
    0 MB external library footprint (no requests, no beautifulsoup4).
    """
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read(150_000)
            html = raw.decode("utf-8", errors="ignore")

            title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            title = title_m.group(1).strip() if title_m else ""
            title = re.sub(r"\s+", " ", title)

            desc_m = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', html, re.IGNORECASE)
            desc = desc_m.group(1).strip() if desc_m else ""

            body_text = re.sub(r"<script.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
            body_text = re.sub(r"<style.*?</style>", " ", body_text, flags=re.IGNORECASE | re.DOTALL)
            body_text = re.sub(r"<[^>]+>", " ", body_text)
            body_text = re.sub(r"\s+", " ", body_text).strip()

            return {
                "success": True,
                "url": url,
                "title": title,
                "description": desc,
                "preview": body_text[:600],
            }
    except Exception as e:
        return {
            "success": False,
            "url": url,
            "error": str(e)
        }


# ── 4. Native Wildcard File Pattern Matcher (fnmatch) ─────────────────────────
def native_find_files(directory: str | Path, pattern: str = "*", max_results: int = 50) -> List[Dict[str, Any]]:
    """
    Recursively finds files matching a wildcard pattern (e.g. *.py, *invoice*2026.pdf)
    using Python built-in os.walk and fnmatch.
    """
    root_path = Path(directory).resolve()
    if not root_path.exists():
        return []

    matches = []
    skip_dirs = {".git", ".venv", "venv", "node_modules", "__pycache__", ".idea", ".vscode"}

    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in files:
            if fnmatch(f.lower(), pattern.lower()):
                p = Path(root) / f
                try:
                    sz = p.stat().st_size
                    matches.append({
                        "name": f,
                        "path": str(p),
                        "size_bytes": sz,
                    })
                    if len(matches) >= max_results:
                        return matches
                except Exception:
                    pass

    return matches
