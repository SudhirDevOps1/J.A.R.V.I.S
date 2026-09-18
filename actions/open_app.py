import difflib
import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

_SYSTEM = platform.system()

_APP_ALIASES: dict[str, dict[str, str]] = {
    "chrome":             {"Windows": "chrome",                  "Darwin": "Google Chrome",        "Linux": "google-chrome"},
    "google chrome":      {"Windows": "chrome",                  "Darwin": "Google Chrome",        "Linux": "google-chrome"},
    "firefox":            {"Windows": "firefox",                 "Darwin": "Firefox",              "Linux": "firefox"},
    "edge":               {"Windows": "msedge",                  "Darwin": "Microsoft Edge",       "Linux": "microsoft-edge"},
    "brave":              {"Windows": "brave",                   "Darwin": "Brave Browser",        "Linux": "brave-browser"},
    "safari":             {"Windows": "msedge",                  "Darwin": "Safari",               "Linux": "firefox"},
    "opera":              {"Windows": "opera",                   "Darwin": "Opera",                "Linux": "opera"},
    "whatsapp":           {"Windows": "WhatsApp",                "Darwin": "WhatsApp",             "Linux": "whatsapp"},
    "telegram":           {"Windows": "Telegram",                "Darwin": "Telegram",             "Linux": "telegram"},
    "discord":            {"Windows": "Discord",                 "Darwin": "Discord",              "Linux": "discord"},
    "slack":              {"Windows": "Slack",                   "Darwin": "Slack",                "Linux": "slack"},
    "zoom":               {"Windows": "Zoom",                    "Darwin": "zoom.us",              "Linux": "zoom"},
    "teams":              {"Windows": "msteams",                 "Darwin": "Microsoft Teams",      "Linux": "teams"},
    "skype":              {"Windows": "skype",                   "Darwin": "Skype",                "Linux": "skype"},
    "signal":             {"Windows": "signal",                  "Darwin": "Signal",               "Linux": "signal"},
    "spotify":            {"Windows": "Spotify",                 "Darwin": "Spotify",              "Linux": "spotify"},
    "vlc":                {"Windows": "vlc",                     "Darwin": "VLC",                  "Linux": "vlc"},
    "netflix":            {"Windows": "Netflix",                 "Darwin": "Netflix",              "Linux": "firefox"},
    "vscode":             {"Windows": "code",                    "Darwin": "Visual Studio Code",   "Linux": "code"},
    "visual studio code": {"Windows": "code",                    "Darwin": "Visual Studio Code",   "Linux": "code"},
    "code":               {"Windows": "code",                    "Darwin": "Visual Studio Code",   "Linux": "code"},
    "terminal":           {"Windows": "wt",                      "Darwin": "Terminal",             "Linux": "x-terminal-emulator"},
    "cmd":                {"Windows": "cmd.exe",                 "Darwin": "Terminal",             "Linux": "bash"},
    "powershell":         {"Windows": "powershell.exe",          "Darwin": "Terminal",             "Linux": "bash"},
    "postman":            {"Windows": "Postman",                 "Darwin": "Postman",              "Linux": "postman"},
    "git":                {"Windows": "git-bash",                "Darwin": "Terminal",             "Linux": "bash"},
    "figma":              {"Windows": "Figma",                   "Darwin": "Figma",                "Linux": "figma"},
    "blender":            {"Windows": "blender",                 "Darwin": "Blender",              "Linux": "blender"},
    "word":               {"Windows": "winword",                 "Darwin": "Microsoft Word",       "Linux": "libreoffice --writer"},
    "excel":              {"Windows": "excel",                   "Darwin": "Microsoft Excel",      "Linux": "libreoffice --calc"},
    "powerpoint":         {"Windows": "powerpnt",                "Darwin": "Microsoft PowerPoint", "Linux": "libreoffice --impress"},
    "libreoffice":        {"Windows": "soffice",                 "Darwin": "LibreOffice",          "Linux": "libreoffice"},
    "notepad":            {"Windows": "notepad.exe",             "Darwin": "TextEdit",             "Linux": "gedit"},
    "textedit":           {"Windows": "notepad.exe",             "Darwin": "TextEdit",             "Linux": "gedit"},
    "explorer":           {"Windows": "explorer.exe",            "Darwin": "Finder",               "Linux": "nautilus"},
    "file explorer":      {"Windows": "explorer.exe",            "Darwin": "Finder",               "Linux": "nautilus"},
    "finder":             {"Windows": "explorer.exe",            "Darwin": "Finder",               "Linux": "nautilus"},
    "task manager":       {"Windows": "taskmgr.exe",             "Darwin": "Activity Monitor",     "Linux": "gnome-system-monitor"},
    "settings":           {"Windows": "ms-settings:",            "Darwin": "System Preferences",   "Linux": "gnome-control-center"},
    "calculator":         {"Windows": "calc.exe",                "Darwin": "Calculator",           "Linux": "gnome-calculator"},
    "paint":              {"Windows": "mspaint.exe",             "Darwin": "Preview",              "Linux": "gimp"},
    "instagram":          {"Windows": "Instagram",               "Darwin": "Instagram",            "Linux": "firefox"},
    "tiktok":             {"Windows": "TikTok",                  "Darwin": "TikTok",               "Linux": "firefox"},
    "notion":             {"Windows": "Notion",                  "Darwin": "Notion",               "Linux": "notion"},
    "obsidian":           {"Windows": "Obsidian",                "Darwin": "Obsidian",             "Linux": "obsidian"},
    "capcut":             {"Windows": "CapCut",                  "Darwin": "CapCut",               "Linux": "capcut"},
    "steam":              {"Windows": "steam",                   "Darwin": "Steam",                "Linux": "steam"},
    "epic":               {"Windows": "EpicGamesLauncher",       "Darwin": "Epic Games Launcher",  "Linux": "legendary"},
    "epic games":         {"Windows": "EpicGamesLauncher",       "Darwin": "Epic Games Launcher",  "Linux": "legendary"},
}

_CATEGORY_FALLBACKS: dict[str, list[str]] = {
    "browser": ["brave", "chrome", "msedge", "firefox", "opera"],
    "chrome": ["chrome", "brave", "msedge", "firefox", "opera"],
    "google chrome": ["chrome", "brave", "msedge", "firefox", "opera"],
    "brave": ["brave", "chrome", "msedge", "firefox"],
    "firefox": ["firefox", "chrome", "brave", "msedge"],
    "edge": ["msedge", "brave", "chrome", "firefox"],

    "notepad": ["notepad", "notepad3", "notepad++", "code", "sublime_text"],
    "text editor": ["notepad", "notepad3", "notepad++", "code", "sublime_text"],
    "editor": ["notepad", "code", "notepad++", "notepad3", "sublime_text"],
    "code editor": ["code", "cursor", "sublime_text", "notepad++", "notepad"],
    "vscode": ["code", "cursor", "sublime_text", "notepad++"],

    "media player": ["vlc", "wmplayer", "mpv", "potplayer", "groove"],
    "video player": ["vlc", "wmplayer", "mpv", "potplayer"],
    "music player": ["spotify", "vlc", "wmplayer", "groove"],

    "terminal": ["wt", "powershell", "cmd", "git-bash"],
    "cmd": ["cmd", "wt", "powershell"],
    "powershell": ["powershell", "wt", "cmd"],
}

_INSTALLED_APPS_CACHE: dict[str, str] = {}
_CACHE_FILE = Path(__file__).resolve().parent.parent / "config" / "installed_apps.json"


def _scan_installed_apps(force_refresh: bool = False) -> dict[str, str]:
    """
    Dynamically scans and indexes all installed applications on the host computer.
    Runs automatically on first run on any machine, and refreshes on-demand or when needed.
    """
    global _INSTALLED_APPS_CACHE
    if not force_refresh and _INSTALLED_APPS_CACHE:
        return _INSTALLED_APPS_CACHE

    if not force_refresh and _CACHE_FILE.exists():
        try:
            data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            if data and isinstance(data, dict):
                _INSTALLED_APPS_CACHE = data
                return _INSTALLED_APPS_CACHE
        except Exception:
            pass

    apps: dict[str, str] = {}
    if _SYSTEM == "Windows":
        try:
            cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", "Get-StartApps | ConvertTo-Json"]
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if p.returncode == 0 and p.stdout.strip():
                items = json.loads(p.stdout)
                if isinstance(items, dict):
                    items = [items]
                for item in items:
                    name = item.get("Name", "").replace(".lnk", "").strip()
                    appid = item.get("AppID", "").strip()
                    if name and appid:
                        apps[name.lower()] = appid
        except Exception as e:
            print(f"[open_app] Get-StartApps scan note: {e}")

        # Index Start Menu shortcut directories (both System-wide and Current User)
        start_menu_dirs = [
            Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        ]
        for sm_dir in start_menu_dirs:
            if sm_dir.exists():
                try:
                    for lnk in sm_dir.rglob("*.lnk"):
                        clean_n = lnk.stem.strip()
                        if clean_n and clean_n.lower() not in apps:
                            apps[clean_n.lower()] = str(lnk)
                except Exception:
                    pass

    elif _SYSTEM == "Darwin":
        # macOS application scanner (/Applications and ~/Applications)
        mac_dirs = [Path("/Applications"), Path("/System/Applications"), Path.home() / "Applications"]
        for md in mac_dirs:
            if md.exists():
                try:
                    for app_path in md.glob("*.app"):
                        apps[app_path.stem.lower()] = app_path.name
                except Exception:
                    pass

    elif _SYSTEM == "Linux":
        # Linux .desktop application scanner
        linux_dirs = [
            Path("/usr/share/applications"),
            Path.home() / ".local" / "share" / "applications",
        ]
        for ld in linux_dirs:
            if ld.exists():
                try:
                    for dt in ld.glob("*.desktop"):
                        name = dt.stem.lower()
                        apps[name] = dt.stem
                except Exception:
                    pass

    _INSTALLED_APPS_CACHE = apps
    if apps:
        try:
            _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _CACHE_FILE.write_text(json.dumps(apps, indent=2), encoding="utf-8")
            print(f"[open_app] Auto-scanned & indexed {len(apps)} installed applications on this machine.")
        except Exception as e:
            print(f"[open_app] Cache write note: {e}")

    return apps


def _is_app_installed(name_or_bin: str) -> bool:
    """Check whether a binary or app name is directly reachable on the system."""
    if not name_or_bin:
        return False
    if shutil.which(name_or_bin) or shutil.which(name_or_bin.split(".")[0]):
        return True
    installed = _scan_installed_apps()
    k = name_or_bin.lower()
    if k in installed:
        return True
    for app_name in installed:
        if k == app_name or k in app_name:
            return True
    return False


def _resolve_app(requested: str, allow_rescan: bool = True) -> tuple[str, str | None]:
    """
    Intelligently resolves requested app with 4-stage search + dynamic self-healing rescan:
    1. Category fallback first (e.g. Chrome not found -> open Brave or Edge)
    2. Direct match in installed applications
    3. Exact alias or system path check
    4. Substring & fuzzy string matching
    Self-healing: If an app is not found, automatically triggers an on-demand rescan once.
    Returns (launch_target, note_if_fallback)
    """
    key = requested.lower().strip()
    installed = _scan_installed_apps()

    # Stage 1: Category fallback first (handles "browser", "editor", or missing specific app like "chrome" -> "brave")
    if key in _CATEGORY_FALLBACKS:
        for candidate in _CATEGORY_FALLBACKS[key]:
            if candidate == key:
                if candidate in installed:
                    return installed[candidate], None
                cand_bin = _APP_ALIASES.get(candidate, {}).get(_SYSTEM, candidate)
                if _is_app_installed(cand_bin):
                    real_target = installed.get(candidate, installed.get(cand_bin.lower(), cand_bin))
                    return real_target, None
                continue
            cand_target = _APP_ALIASES.get(candidate, {}).get(_SYSTEM, candidate)
            if _is_app_installed(cand_target):
                real_target = installed.get(candidate, installed.get(cand_target.lower(), cand_target))
                note = f"'{requested}' install nahi mila, toh maine aapka alternate ({candidate.capitalize()}) open kar diya"
                return real_target, note
            for app_name, app_id in installed.items():
                if candidate in app_name:
                    note = f"'{requested}' install nahi mila, toh maine aapka alternate ({app_name.title()}) open kar diya"
                    return app_id, note

    # Stage 2: Direct match in installed applications
    if key in installed:
        return installed[key], None

    # Stage 3: Exact alias on system
    if key in _APP_ALIASES:
        target = _APP_ALIASES[key].get(_SYSTEM, requested)
        if _is_app_installed(target):
            real_launch_target = installed.get(key, installed.get(target.lower(), target))
            return real_launch_target, None

    # Check if executable directly exists on PATH
    if shutil.which(key) or shutil.which(key.split(".")[0]):
        return key, None

    # Substring match across installed apps
    for app_name, app_id in installed.items():
        if key in app_name or app_name in key:
            return app_id, None

    # Stage 4: Fuzzy matching against installed apps
    all_names = list(installed.keys())
    close = difflib.get_close_matches(key, all_names, n=1, cutoff=0.6)
    if close:
        matched_name = close[0]
        return installed[matched_name], f"'{requested}' ki jagah '{matched_name}' mila"

    # Self-healing on-demand rescan: If not found, perhaps user recently installed it
    if allow_rescan:
        print(f"[open_app] '{requested}' not found in cache. Running dynamic on-demand system rescan...")
        _scan_installed_apps(force_refresh=True)
        return _resolve_app(requested, allow_rescan=False)

    # Fallback to normalized alias or raw string
    for alias_key, os_map in _APP_ALIASES.items():
        if alias_key in key or key in alias_key:
            return os_map.get(_SYSTEM, requested), None

    return requested, None



def _launch_windows(app_name: str) -> bool:
    """Launch application on Windows via path, AppID, shell protocol, or Start Menu."""
    # 1. Direct path to .lnk or .exe
    if app_name.endswith(".lnk") or app_name.endswith(".exe") and os.path.exists(app_name):
        try:
            subprocess.Popen(f'start "" "{app_name}"', shell=True)
            time.sleep(1.0)
            return True
        except Exception:
            pass

    # 2. Direct binary on PATH
    if shutil.which(app_name) or shutil.which(app_name.split(".")[0]):
        try:
            subprocess.Popen(
                app_name,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1.2)
            return True
        except Exception as e:
            print(f"[open_app] subprocess failed: {e}")

    # 3. Protocol handler (e.g. ms-settings:)
    if ":" in app_name and not ("\\" in app_name or "/" in app_name):
        try:
            subprocess.Popen(f"start {app_name}", shell=True)
            time.sleep(1.0)
            return True
        except Exception:
            pass

    # 4. Windows Store / Get-StartApps AppID via shell:AppsFolder
    if app_name:
        try:
            subprocess.Popen(f'explorer.exe "shell:AppsFolder\\\\{app_name}"', shell=True)
            time.sleep(1.2)
            return True
        except Exception:
            pass

    # 5. Last resort: Start Menu keyboard automation
    try:
        import pyautogui
        pyautogui.PAUSE = 0.1
        pyautogui.press("win")
        time.sleep(0.7)
        pyautogui.write(app_name, interval=0.05)
        time.sleep(0.9)
        pyautogui.press("enter")
        time.sleep(2.0)
        return True
    except Exception as e:
        print(f"[open_app] Start Menu search failed: {e}")

    return False


def _launch_macos(app_name: str) -> bool:
    try:
        result = subprocess.run(["open", "-a", app_name], capture_output=True, timeout=8)
        if result.returncode == 0:
            time.sleep(1.0)
            return True
    except Exception:
        pass

    try:
        result = subprocess.run(["open", "-a", f"{app_name}.app"], capture_output=True, timeout=8)
        if result.returncode == 0:
            time.sleep(1.0)
            return True
    except Exception:
        pass

    binary = shutil.which(app_name) or shutil.which(app_name.lower())
    if binary:
        try:
            subprocess.Popen([binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.0)
            return True
        except Exception:
            pass

    try:
        import pyautogui
        pyautogui.hotkey("command", "space")
        time.sleep(0.6)
        pyautogui.write(app_name, interval=0.05)
        time.sleep(0.8)
        pyautogui.press("enter")
        time.sleep(1.5)
        return True
    except Exception as e:
        print(f"[open_app] Spotlight failed: {e}")

    return False


_LINUX_TERMINAL_FALLBACKS = [
    "x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal",
    "xterm", "lxterminal", "mate-terminal", "tilix", "alacritty", "kitty",
]

def _launch_linux(app_name: str) -> bool:
    if app_name in ("x-terminal-emulator", "gnome-terminal", "terminal"):
        for term in _LINUX_TERMINAL_FALLBACKS:
            if shutil.which(term):
                try:
                    subprocess.Popen([term], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(1.0)
                    return True
                except Exception:
                    continue

    binary = (
        shutil.which(app_name) or
        shutil.which(app_name.lower()) or
        shutil.which(app_name.lower().replace(" ", "-")) or
        shutil.which(app_name.lower().replace(" ", "_"))
    )
    if binary:
        try:
            subprocess.Popen([binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.0)
            return True
        except Exception:
            pass

    try:
        subprocess.run(["xdg-open", app_name], capture_output=True, timeout=5)
        return True
    except Exception:
        pass

    for desktop_name in [
        app_name.lower(),
        app_name.lower().replace(" ", "-"),
        app_name.lower().replace(" ", ""),
    ]:
        try:
            result = subprocess.run(["gtk-launch", desktop_name], capture_output=True, timeout=5)
            if result.returncode == 0:
                return True
        except Exception:
            pass

    return False


_OS_LAUNCHERS = {
    "Windows": _launch_windows,
    "Darwin":  _launch_macos,
    "Linux":   _launch_linux,
}

def list_running_apps() -> list[str]:
    """Return a clean, sorted list of running user applications."""
    if not _PSUTIL:
        return ["psutil not installed"]
    ignore = {
        "system", "registry", "smss.exe", "csrss.exe", "wininit.exe", "services.exe",
        "lsass.exe", "svchost.exe", "fontdrvhost.exe", "dwm.exe", "spoolsv.exe",
        "conhost.exe", "sihost.exe", "taskhostw.exe", "explorer.exe", "ctfmon.exe",
        "searchhost.exe", "startmenuexperiencehost.exe", "shellexperiencehost.exe",
        "securityhealthservice.exe", "mpengine.dll", "aggregatorhost.exe",
    }
    user_apps = set()
    for p in psutil.process_iter(['name']):
        try:
            n = (p.info.get('name') or "").strip()
            if n and n.lower() not in ignore and not n.lower().startswith("dllhost"):
                cleaned = n.replace(".exe", "").capitalize()
                user_apps.add(cleaned)
        except Exception:
            pass
    return sorted(list(user_apps))


def _close_app(app_name: str) -> str:
    """Gracefully terminate or kill a running application process."""
    if not app_name:
        return "No application specified to close."

    clean_target = app_name.lower().strip().replace(".exe", "")
    closed_count = 0

    if _PSUTIL:
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                pname = (proc.info.get('name') or "").lower().replace(".exe", "")
                if clean_target == pname or clean_target in pname:
                    proc.terminate()
                    closed_count += 1
            except Exception:
                pass

    if closed_count > 0:
        return f"{app_name.capitalize()} band kar diya gaya hai ({closed_count} process closed)."

    # Fallback to taskkill on Windows
    if _SYSTEM == "Windows":
        try:
            res = subprocess.run(
                ["taskkill", "/IM", f"{clean_target}.exe", "/F"],
                capture_output=True, text=True, timeout=5
            )
            if res.returncode == 0:
                return f"{app_name.capitalize()} band kar diya gaya hai."
        except Exception:
            pass

    return f"{app_name.capitalize()} abhi chal nahi raha tha."


def open_app(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    app_name = (params.get("app_name") or params.get("name") or "").strip()
    action = params.get("action", "open").strip().lower()

    if action in ("refresh", "rescan", "refresh_apps", "scan_apps", "update_apps") or app_name.lower() in ("refresh", "refresh apps", "scan apps", "rescan", "sync apps", "apps refresh", "scan"):
        discovered = _scan_installed_apps(force_refresh=True)
        return f"System scan complete: {len(discovered)} installed applications indexed successfully on this computer."

    if action in ("list", "list_running", "running_apps") or app_name.lower() in ("list", "running", "all", "all apps", "running apps", "apps"):
        apps = list_running_apps()
        if not apps:
            return "No running applications detected."
        summary = ", ".join(apps[:20])
        return f"Active applications currently running: {summary} ({len(apps)} apps active)."

    if not app_name:
        return "No application name provided."

    if action in ("close", "kill", "quit", "band", "exit"):
        return _close_app(app_name)

    launcher = _OS_LAUNCHERS.get(_SYSTEM)
    if launcher is None:
        return f"Unsupported operating system: {_SYSTEM}"

    resolved_target, fallback_note = _resolve_app(app_name)
    print(f"[open_app] Launching: '{app_name}' → '{resolved_target}' (Note: {fallback_note})")

    if player:
        player.write_log(f"[open_app] {app_name}")

    try:
        if launcher(resolved_target):
            if fallback_note:
                return f"{fallback_note}, aur successfully open kar diya!"
            return f"Opened {app_name}."

        # Secondary attempt with raw app_name
        if resolved_target.lower() != app_name.lower():
            if launcher(app_name):
                return f"Opened {app_name}."

        return (
            f"Could not confirm that {app_name} launched. "
            f"It may still be loading, or it might not be installed."
        )
    except Exception as e:
        print(f"[open_app] Error: {e}")
        return f"Failed to open {app_name}: {e}"


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "open_app",
    "description": "Opens any application on the computer, closes apps, lists active running applications, or refreshes installed apps cache. Supports intelligent dynamic auto-discovery on any PC and smart category fallbacks (e.g. opens Brave if Chrome is not installed).",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "app_name": {
                "type": "STRING",
                "description": "Exact or colloquial name of the application (e.g. 'Chrome', 'Notepad', 'Brave', 'Browser', 'Terminal'), 'list' to see running apps, or 'refresh' to scan system apps."
            },
            "action": {
                "type": "STRING",
                "description": "'open' to launch an app, 'close' to terminate an app, 'list' to list running applications, or 'refresh' to dynamically rescan installed applications."
            }
        },
        "required": [
            "app_name"
        ]
    },
    "handler": open_app,
}
