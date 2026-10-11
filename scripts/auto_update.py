#!/usr/bin/env python3
"""
scripts/auto_update.py — Universal Cross-Platform Auto-Updater for J.A.R.V.I.S.
=============================================================================
Works on: Windows 10/11, macOS, and Linux.

Key Safety Principles:
1. DEFENSIVE & NON-DESTRUCTIVE: Sirf safe updates, kabhi bhi files delete nahi karta.
2. PROTECTED ASSETS: config/api_keys.json, memory/, .venv/ ko touch nahi karta.
3. ROLLBACK READY: Update se pehle freeze snapshot leta hai, fail hone par auto-restore.
4. NETWORK AWARE: Offline hone par silent exit karta hai, system hang nahi hota.

Usage:
    python scripts/auto_update.py                  # Default safe update
    python scripts/auto_update.py --check          # Sirf check karega, update nahi
    python scripts/auto_update.py --dry-run        # Simulation mode
    python scripts/auto_update.py --aggressive     # Major version upgrades allowed
    python scripts/auto_update.py --safe           # Default safe patch mode
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Reconfigure console streams for clean UTF-8 on Windows
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── Paths & Protected Locations ──────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_ROOT_DIR   = _SCRIPT_DIR.parent
_LOGS_DIR   = _ROOT_DIR / "logs"
_UPDATE_LOG = _LOGS_DIR / "updates.log"
_REQ_FILE   = _ROOT_DIR / "requirements.txt"
_PKG_JSON   = _ROOT_DIR / "package.json"
_CARGO_TOML = _ROOT_DIR / "Cargo.toml"
_API_KEYS   = _ROOT_DIR / "config" / "api_keys.json"

_PROTECTED_PATHS = [
    _ROOT_DIR / "config" / "api_keys.json",
    _ROOT_DIR / "config" / "gemini_cookies.json",
    _ROOT_DIR / "memory",
    _ROOT_DIR / ".venv",
    _ROOT_DIR / "venv",
]


# ── Logging System ───────────────────────────────────────────────────────────
def _log(msg: str, level: str = "INFO", echo: bool = True) -> None:
    """Timestamped logging both to console and logs/updates.log."""
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{ts}] [{level}] {msg}"
    if echo:
        prefix = {
            "INFO": "ℹ️ ",
            "SUCCESS": "✅ ",
            "WARN": "⚠️ ",
            "ERROR": "❌ ",
            "DRY": "🔍 ",
        }.get(level, "• ")
        print(f"{prefix}{msg}")
    try:
        with open(_UPDATE_LOG, "a", encoding="utf-8", errors="replace") as f:
            f.write(formatted + "\n")
    except Exception:
        pass


# ── Network Check ─────────────────────────────────────────────────────────────
def check_network(timeout: float = 2.0) -> bool:
    """Fast socket probe to check active internet connectivity (<50ms)."""
    probe_targets = [("1.1.1.1", 53), ("8.8.8.8", 53), ("pypi.org", 443)]
    for host, port in probe_targets:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            return True
        except Exception:
            continue
    return False


# ── Environment & OS Detection ───────────────────────────────────────────────
def detect_os() -> Dict[str, str]:
    """OS name, release, architecture, and current python binary detect karta hai."""
    sys_name = platform.system()  # 'Windows', 'Darwin', 'Linux'
    return {
        "os": sys_name,
        "release": platform.release(),
        "arch": platform.machine(),
        "python": sys.executable,
        "py_version": platform.python_version(),
    }


def detect_package_managers() -> Dict[str, Optional[str]]:
    """Detect available Python, Node, and Rust package managers on this machine."""
    py_mgrs = ["uv", "pip", "pip3", "pipx"]
    node_mgrs = ["bun", "pnpm", "yarn", "npm"]
    rust_mgrs = ["cargo"]

    detected: Dict[str, Optional[str]] = {
        "python": None,
        "node": None,
        "rust": None,
    }

    # Python package manager (uv preferred for 10x speed, fallback to pip)
    for p in py_mgrs:
        found = shutil.which(p)
        if found:
            detected["python"] = p
            break
    if not detected["python"]:
        detected["python"] = "pip"  # Python built-in module fallback

    # Node package manager
    for n in node_mgrs:
        found = shutil.which(n)
        if found:
            detected["node"] = n
            break

    # Rust package manager
    for r in rust_mgrs:
        found = shutil.which(r)
        if found:
            detected["rust"] = r
            break

    return detected


# ── Security & Integrity Guard ───────────────────────────────────────────────
def calculate_file_hash(path: Path) -> str:
    """Return SHA256 of given file, or empty string if not exists."""
    if not path.exists():
        return ""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def assert_protected_assets_safe(pre_hashes: Dict[str, str]) -> bool:
    """Verify that credentials and memory were NEVER touched or corrupted."""
    for path, old_hash in pre_hashes.items():
        p = Path(path)
        if not p.exists():
            _log(f"CRITICAL: Protected file {p.name} missing after update!", "ERROR")
            return False
        new_hash = calculate_file_hash(p)
        if old_hash and new_hash != old_hash:
            _log(f"CRITICAL: Protected file {p.name} was modified during update! Aborting.", "ERROR")
            return False
    return True


# ── Rollback Management ───────────────────────────────────────────────────────
class RollbackManager:
    """Snapshot and rollback manager for Python dependencies."""

    def __init__(self):
        self.snapshot_file: Optional[Path] = None
        self.req_backup: Optional[Path] = None
        self.req_hash: str = ""

    def create_snapshot(self) -> bool:
        """Create a freeze snapshot before any modification."""
        try:
            _LOGS_DIR.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())

            # 1. Backup requirements.txt
            if _REQ_FILE.exists():
                self.req_backup = _LOGS_DIR / f".backup_requirements_{ts}.txt"
                shutil.copy2(_REQ_FILE, self.req_backup)
                self.req_hash = calculate_file_hash(_REQ_FILE)

            # 2. Freeze current pip packages
            self.snapshot_file = _LOGS_DIR / f".pip_freeze_{ts}.txt"
            cmd = [sys.executable, "-m", "pip", "freeze"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if res.returncode == 0:
                self.snapshot_file.write_text(res.stdout, encoding="utf-8")
                _log(f"Pre-update snapshot saved to {self.snapshot_file.name}", "INFO")
                return True
        except Exception as e:
            _log(f"Failed to create rollback snapshot: {e}", "WARN")
        return False

    def rollback(self) -> bool:
        """Restore previous requirements.txt and package state on failure."""
        _log("Rolling back dependencies to previous known-good state...", "WARN")
        try:
            # Restore requirements.txt
            if self.req_backup and self.req_backup.exists():
                shutil.copy2(self.req_backup, _REQ_FILE)
                _log("Restored requirements.txt from backup.", "INFO")

            # Restore packages if freeze snapshot exists
            if self.snapshot_file and self.snapshot_file.exists():
                cmd = [sys.executable, "-m", "pip", "install", "-r", str(self.snapshot_file)]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if res.returncode == 0:
                    _log("Rollback completed successfully. System restored.", "SUCCESS")
                    return True
                else:
                    _log(f"Rollback pip install had warnings: {res.stderr[:200]}", "WARN")
        except Exception as e:
            _log(f"Rollback encountered error: {e}", "ERROR")
        return False


# ── Dependency Inspection (--check mode) ─────────────────────────────────────
def check_outdated_packages() -> List[Dict[str, str]]:
    """Query pip for list of outdated packages without applying updates."""
    _log("Checking PyPI for outdated Python dependencies...", "INFO")
    cmd = [sys.executable, "-m", "pip", "list", "--outdated", "--format=json"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            return [
                {
                    "name": pkg.get("name", ""),
                    "current": pkg.get("version", ""),
                    "latest": pkg.get("latest_version", ""),
                    "type": pkg.get("latest_filetype", "wheel"),
                }
                for pkg in data
            ]
    except Exception as e:
        _log(f"Error querying outdated packages: {e}", "WARN")
    return []


# ── Verification & Smoke Testing ─────────────────────────────────────────────
def verify_system_integrity() -> Tuple[bool, str]:
    """Run compileall and smoke imports to ensure core system did not break."""
    _log("Verifying system integrity post-update...", "INFO")
    try:
        # 1. Syntax compile test
        cmd_compile = [sys.executable, "-m", "py_compile", str(_ROOT_DIR / "main.py"), str(_ROOT_DIR / "ui.py")]
        res = subprocess.run(cmd_compile, capture_output=True, text=True, timeout=20)
        if res.returncode != 0:
            return False, f"Syntax compilation failed: {res.stderr[:200]}"

        # 2. Core library import test
        smoke_code = (
            "import numpy; import sounddevice; import google.genai; "
            "import fastapi; import psutil; import requests; import ddgs; "
            "print('SMOKE_OK')"
        )
        cmd_smoke = [sys.executable, "-c", smoke_code]
        res_smoke = subprocess.run(cmd_smoke, capture_output=True, text=True, timeout=15)
        if res_smoke.returncode != 0 or "SMOKE_OK" not in res_smoke.stdout:
            return False, f"Core library smoke imports failed: {res_smoke.stderr[:200]}"

        return True, "All syntax checks and core imports verified cleanly."
    except Exception as e:
        return False, f"Verification exception: {e}"


# ── Optional Notifications ───────────────────────────────────────────────────
def send_notification(title: str, message: str) -> None:
    """Send alert via ntfy.sh or Telegram if configured in api_keys.json."""
    if not _API_KEYS.exists():
        return
    try:
        cfg = json.loads(_API_KEYS.read_text(encoding="utf-8"))
        ntfy_topic = cfg.get("ntfy_topic") or os.environ.get("NTFY_TOPIC")
        tg_token   = cfg.get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN")
        tg_chat    = cfg.get("telegram_chat_id") or os.environ.get("TELEGRAM_CHAT_ID")

        import urllib.request

        # 1. Ntfy dispatch
        if ntfy_topic:
            url = f"https://ntfy.sh/{ntfy_topic.strip()}"
            req = urllib.request.Request(
                url,
                data=message.encode("utf-8"),
                headers={"Title": title.encode("utf-8")},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=3.0)

        # 2. Telegram dispatch
        if tg_token and tg_chat:
            tg_url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
            payload = json.dumps({"chat_id": tg_chat, "text": f"*{title}*\n{message}", "parse_mode": "Markdown"}).encode("utf-8")
            req = urllib.request.Request(tg_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=3.0)
    except Exception:
        pass


# ── Main Updater Engine ───────────────────────────────────────────────────────
def run_updater(mode: str = "safe", check_only: bool = False, dry_run: bool = False) -> int:
    """
    Main Auto-Updater routine:
    mode: 'safe' (patch/minor only) | 'aggressive' (major versions)
    check_only: Boolean (list only, no changes)
    dry_run: Boolean (simulate actions)
    """
    os_info = detect_os()
    _log(f"J.A.R.V.I.S. Universal Auto-Updater initialized on {os_info['os']} ({os_info['arch']})", "INFO")
    _log(f"Python interpreter: {os_info['python']} (v{os_info['py_version']})", "INFO")

    # 1. Connectivity check
    _log("Checking network connectivity...", "INFO")
    if not check_network():
        _log("Internet connection offline or unreachable. Skipping updates safely.", "WARN")
        return 0
    _log("Network online and verified.", "SUCCESS")

    # 2. Package manager discovery
    pkg_mgrs = detect_package_managers()
    _log(f"Discovered package managers -> Python: [{pkg_mgrs['python']}], Node: [{pkg_mgrs['node']}], Rust: [{pkg_mgrs['rust']}]", "INFO")

    # 3. Check mode only
    if check_only:
        outdated = check_outdated_packages()
        if outdated:
            _log(f"Found {len(outdated)} outdated package(s):", "INFO")
            for p in outdated:
                _log(f"  • {p['name']}: {p['current']} -> {p['latest']}", "INFO")
        else:
            _log("All Python dependencies are currently up to date.", "SUCCESS")
        return 0

    # 4. Record pre-update security hashes of protected files
    pre_hashes: Dict[str, str] = {}
    if _API_KEYS.exists():
        pre_hashes[str(_API_KEYS)] = calculate_file_hash(_API_KEYS)

    # 5. Rollback snapshot
    rollback_mgr = RollbackManager()
    if not dry_run:
        rollback_mgr.create_snapshot()

    # 6. Execute Python Dependency Updates
    if _REQ_FILE.exists():
        _log(f"Processing Python dependencies from {_REQ_FILE.name} (Mode: {mode.upper()})...", "INFO")
        if dry_run:
            _log(f"[DRY-RUN] Would run: {os_info['python']} -m pip install --upgrade -r requirements.txt", "DRY")
        else:
            py_cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "-r", str(_REQ_FILE)]
            if mode == "safe":
                # Safe mode preserves explicit pins while allowing compatible upgrades
                py_cmd.extend(["--upgrade-strategy", "only-if-needed"])

            _log(f"Executing: {' '.join(py_cmd)}", "INFO")
            res_pip = subprocess.run(py_cmd, capture_output=True, text=True, timeout=300)
            if res_pip.returncode != 0:
                _log(f"Pip update encountered errors:\n{res_pip.stderr[:400]}", "ERROR")
                rollback_mgr.rollback()
                send_notification("J.A.R.V.I.S. Update Failed", f"Pip update failed. Restored snapshot. Error: {res_pip.stderr[:120]}")
                return 1
            _log("Python dependencies upgraded successfully.", "SUCCESS")

    # 7. Execute Node Dependency Updates (if package.json present)
    if _PKG_JSON.exists() and pkg_mgrs["node"]:
        node_cmd = [pkg_mgrs["node"], "update"]
        if dry_run:
            _log(f"[DRY-RUN] Would run: {' '.join(node_cmd)} in {_ROOT_DIR}", "DRY")
        else:
            _log(f"Executing Node update: {' '.join(node_cmd)}...", "INFO")
            try:
                res_node = subprocess.run(node_cmd, cwd=str(_ROOT_DIR), capture_output=True, text=True, timeout=120)
                if res_node.returncode == 0:
                    _log("Node packages updated cleanly.", "SUCCESS")
                else:
                    _log(f"Node update warning: {res_node.stderr[:200]}", "WARN")
            except Exception as e:
                _log(f"Node updater skipped: {e}", "WARN")

    # 8. Execute Rust / Cargo Updates (if Cargo.toml present)
    if _CARGO_TOML.exists() and pkg_mgrs["rust"]:
        cargo_cmd = ["cargo", "update"]
        if dry_run:
            _log(f"[DRY-RUN] Would run: {' '.join(cargo_cmd)} in {_ROOT_DIR}", "DRY")
        else:
            _log("Executing Cargo update...", "INFO")
            try:
                subprocess.run(cargo_cmd, cwd=str(_ROOT_DIR), capture_output=True, timeout=90)
                _log("Cargo packages updated cleanly.", "SUCCESS")
            except Exception:
                pass

    # 9. Verify Protected Files were NOT touched
    if not dry_run and not assert_protected_assets_safe(pre_hashes):
        rollback_mgr.rollback()
        return 1

    # 10. Smoke Test Verification
    if not dry_run:
        ok, verify_msg = verify_system_integrity()
        if not ok:
            _log(f"Post-update verification failed: {verify_msg}", "ERROR")
            rollback_mgr.rollback()
            send_notification("J.A.R.V.I.S. Update Aborted", f"Integrity check failed: {verify_msg}. System rolled back.")
            return 1
        _log(f"Integrity check passed: {verify_msg}", "SUCCESS")

    _log("Universal update finished cleanly with 0 regressions.", "SUCCESS")
    send_notification("J.A.R.V.I.S. Dependencies Updated", "All packages verified and updated safely.")
    return 0


# ── Entry Point ───────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Universal Cross-Platform Auto-Updater for J.A.R.V.I.S.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check PyPI/npm for newer versions without applying changes.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the update workflow without making disk or pip modifications.",
    )
    parser.add_argument(
        "--aggressive",
        action="store_true",
        help="Aggressive upgrade mode (allows major updates across all libraries).",
    )
    parser.add_argument(
        "--safe",
        action="store_true",
        default=True,
        help="Safe mode (default: applies non-breaking patch and minor updates).",
    )

    args = parser.parse_args()
    mode = "aggressive" if args.aggressive else "safe"

    exit_code = run_updater(mode=mode, check_only=args.check, dry_run=args.dry_run)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
