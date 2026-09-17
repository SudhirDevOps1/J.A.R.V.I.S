# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S. Desktop Background Launcher.
Ensures correct working directory, registers Windows AppUserModelID for taskbar icon,
redirects stdout/stderr to logs/jarvis_runtime.log for pythonw.exe stability,
executes preflight asset checks, and launches main.py.
"""
import os
import sys
from pathlib import Path

# 1. Anchor Working Directory to Project Root
PROJECT_ROOT = str(Path(__file__).resolve().parent)
os.chdir(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 2. Register Windows AppUserModelID so Taskbar displays the Custom Arc Reactor Icon
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SudhirDevOps1.JARVIS.AI.MarkLIII")
    except Exception:
        pass

# 3. Redirect stdout / stderr to logs/jarvis_runtime.log
log_dir = Path(PROJECT_ROOT) / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "jarvis_runtime.log"

try:
    # Keep log file manageable (truncate if > 5 MB)
    if log_file.exists() and log_file.stat().st_size > 5 * 1024 * 1024:
        log_file.unlink()
    _log_fp = open(log_file, "a", encoding="utf-8", errors="replace", buffering=1)
    sys.stdout = _log_fp
    sys.stderr = _log_fp
except Exception:
    pass

# 4. Verify/generate required assets silently before starting GUI
try:
    from scripts.preflight_check import run_preflight
    run_preflight(verbose=False)
except Exception as e:
    print(f"[Launcher] Preflight note: {e}")

# 5. Launch Main Application
import runpy
try:
    runpy.run_path(str(Path(PROJECT_ROOT) / "main.py"), run_name="__main__")
except Exception as e:
    import traceback
    print(f"[Launcher Fatal Error]: {e}")
    traceback.print_exc()
