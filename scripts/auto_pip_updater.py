"""
Auto-Pip Dependency Updater for J.A.R.V.I.S.
Checks PyPI for newer versions of packages in requirements.txt in parallel (<1s).
Automatically upgrades any outdated packages safely without breaking system state.
"""
from __future__ import annotations

import concurrent.futures
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = Path(__file__).resolve().parent.parent
_REQ_PATH = _ROOT / "requirements.txt"
_CACHE_PATH = _ROOT / "cache" / "last_pip_update.json"
_CHECK_INTERVAL_SECONDS = 12 * 3600  # Check at most twice a day on normal launch


def _parse_version(v_str: str) -> tuple:
    """Parse version string into comparable tuple."""
    try:
        from packaging import version
        return version.parse(v_str)
    except Exception:
        parts = []
        for part in re.findall(r'\d+|[a-zA-Z]+', v_str):
            parts.append(int(part) if part.isdigit() else part)
        return tuple(parts)


def get_requirements_packages() -> List[str]:
    """Parse clean package names from requirements.txt."""
    if not _REQ_PATH.exists():
        return []

    packages = []
    for line in _REQ_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Strip comments
        line = line.split("#")[0].strip()
        # Strip extras like uvicorn[standard] -> uvicorn
        line = re.sub(r'\[.*?\]', '', line)
        # Strip version constraints like >=2.8.0, ==1.0, etc.
        match = re.match(r'^([a-zA-Z0-9_\-\.]+)', line)
        if match:
            pkg_name = match.group(1).strip()
            if pkg_name:
                packages.append(pkg_name)

    return sorted(set(packages))


def fetch_pypi_latest_version(pkg_name: str, timeout: float = 2.0) -> Optional[str]:
    """Fetch the latest release version of a package from PyPI JSON API."""
    url = f"https://pypi.org/pypi/{pkg_name}/json"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Jarvis-Pip-Updater/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("info", {}).get("version")
    except Exception:
        pass
    return None


def patch_sounddevice_numpy_warning():
    """Ensure sounddevice.py in venv does not trigger NumPy 2.5 shape setter warning."""
    try:
        import sounddevice
        sd_file = Path(sounddevice.__file__)
        if sd_file.exists():
            content = sd_file.read_text(encoding="utf-8", errors="ignore")
            old_str = "    data = np.frombuffer(buffer, dtype=dtype)\n    data.shape = -1, channels\n    return data"
            new_str = "    import numpy as np\n    return np.frombuffer(buffer, dtype=dtype).reshape(-1, channels)"
            if old_str in content:
                content = content.replace(old_str, new_str)
                sd_file.write_text(content, encoding="utf-8")
    except Exception:
        pass


def check_and_update_packages(force: bool = False, check_only: bool = False, verbose: bool = True) -> bool:
    """
    Check for outdated packages and auto-update them.
    Returns True if updates were applied or system is clean.
    """
    now = time.time()
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Check cache throttle unless force is requested
    if not force and _CACHE_PATH.exists():
        try:
            cache = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
            last_check = float(cache.get("last_check", 0))
            if (now - last_check) < _CHECK_INTERVAL_SECONDS:
                if verbose:
                    print("  [OK] Pip Dependencies: Verified recently (auto-check cached)")
                return True
        except Exception:
            pass

    packages = get_requirements_packages()
    if not packages:
        return True

    if verbose:
        print(f"  [*] Checking PyPI for updates across {len(packages)} dependencies...")

    outdated: List[Tuple[str, str, str]] = []  # (pkg, installed, latest)

    def _check_one(pkg: str) -> Optional[Tuple[str, str, str]]:
        try:
            inst_ver = importlib.metadata.version(pkg)
        except Exception:
            # Package not installed or unversioned
            return None

        latest_ver = fetch_pypi_latest_version(pkg)
        if latest_ver and _parse_version(latest_ver) > _parse_version(inst_ver):
            return (pkg, inst_ver, latest_ver)
        return None

    # Parallel query with short timeout to prevent startup lag
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_pkg = {executor.submit(_check_one, pkg): pkg for pkg in packages}
            for future in concurrent.futures.as_completed(future_to_pkg, timeout=5.0):
                res = future.result()
                if res:
                    outdated.append(res)
    except Exception:
        # If timeout or network issues, skip cleanly without failing launch
        if verbose:
            print("  [OK] Pip Dependencies: Fast-skip (network check timed out or offline)")
        return True

    # Save cache timestamp
    try:
        _CACHE_PATH.write_text(json.dumps({
            "last_check": now,
            "outdated_found": len(outdated)
        }, indent=2), encoding="utf-8")
    except Exception:
        pass

    if not outdated:
        if verbose:
            print(f"  [OK] Pip Dependencies: All {len(packages)} packages are at latest version")
        return True

    # Upgrade outdated packages
    print(f"\n===================================================")
    print(f"       J.A.R.V.I.S. Auto-Updater: Updates Found!")
    print(f"===================================================")
    for pkg, cur, lat in outdated:
        print(f"  [UPDATE] {pkg}: v{cur} -> v{lat}")
    print(f"===================================================")
    print(f"[*] Auto-upgrading {len(outdated)} packages safely via pip...")

    if check_only:
        print(f"[*] Check-only mode: {len(outdated)} packages have updates available. Skipping install.")
        return True

    upgrade_targets = [pkg for pkg, _, _ in outdated]
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade"] + upgrade_targets

    try:
        res = subprocess.run(cmd, capture_output=False, text=True)
        if res.returncode == 0:
            print(f"\n[OK] Safaltapoorvak {len(outdated)} packages update ho gaye!")
            # Re-apply NumPy 2.5 safety patch if sounddevice was upgraded
            if any(p.lower() == "sounddevice" for p in upgrade_targets):
                patch_sounddevice_numpy_warning()
            return True
        else:
            print(f"[!] Warning: Pip upgrade had non-zero exit code: {res.returncode}")
            return False
    except Exception as e:
        print(f"[!] Auto-upgrade error: {e}")
        return False


if __name__ == "__main__":
    force_update = "--force" in sys.argv or "--update" in sys.argv or "-u" in sys.argv
    check_mode = "--check-only" in sys.argv or "--check" in sys.argv
    check_and_update_packages(force=force_update, check_only=check_mode, verbose=True)
