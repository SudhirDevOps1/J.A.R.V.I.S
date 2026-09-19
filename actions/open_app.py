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
    "camera":             {"Windows": "microsoft.windows.camera:", "Darwin": "Photo Booth",         "Linux": "cheese"},
    "webcam":             {"Windows": "microsoft.windows.camera:", "Darwin": "Photo Booth",         "Linux": "cheese"},
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

    # ADDITIVE-2 (purana hataya nahi): 50+ category fallbacks for 1000+ app coverage
    "pdf reader": ["acrobat", "sumatra", "foxit", "msedge", "chrome"],
    "pdf": ["acrobat", "sumatra", "foxit", "msedge", "chrome"],
    "photo editor": ["photoshop", "gimp", "paint.net", "mspaint"],
    "image editor": ["photoshop", "gimp", "paint.net", "mspaint"],
    "video editor": ["premiere", "capcut", "davinci", "filmora", "clipchamp"],
    "audio editor": ["audacity", "adobe audition", "fl studio"],
    "music": ["spotify", "vlc", "wmplayer", "groove", "itunes"],
    "video": ["vlc", "mpv", "potplayer", "wmplayer", "films"],
    "calculator": ["calc", "calculator", "speedcrunch"],
    "calendar": ["outlook", "thunderbird", "google calendar"],
    "mail": ["outlook", "thunderbird", "mail"],
    "email": ["outlook", "thunderbird", "mail"],
    "notes": ["notion", "obsidian", "onenote", "notepad", "evernote"],
    "todo": ["todoist", "notion", "onenote", "tasks"],
    "tasks": ["todoist", "notion", "onenote"],
    "chat": ["whatsapp", "telegram", "discord", "slack"],
    "messenger": ["whatsapp", "telegram", "discord", "messenger"],
    "meeting": ["zoom", "teams", "meet", "webex"],
    "video call": ["zoom", "teams", "skype", "meet"],
    "ide": ["code", "cursor", "pycharm", "intellij", "sublime_text"],
    "python ide": ["pycharm", "code", "thonny", "spyder"],
    "database": ["dbeaver", "ssms", "datagrip", "heidisql"],
    "ftp": ["filezilla", "winscp"],
    "vpn": ["openvpn", "wireguard", "protonvpn"],
    "zip": ["7zip", "winrar", "peazip"],
    "archiver": ["7zip", "winrar", "peazip"],
    "antivirus": ["defender", "avast", "avg"],
    "screen recorder": ["obs", "bandicam", "sharex"],
    "screenshot": ["sharex", "snipping", "greenshot"],
    "snipping": ["snippingtool", "sharex", "greenshot"],
    "paint": ["mspaint", "paint.net", "gimp"],
    "maps": ["maps", "google earth", "chrome"],
    "news": ["chrome", "msedge", "firefox"],
    "shopping": ["chrome", "msedge", "firefox"],
    "banking": ["chrome", "msedge", "firefox"],
    "office": ["winword", "excel", "powerpnt", "libreoffice"],
    "spreadsheet": ["excel", "libreoffice", "gsheets"],
    "presentation": ["powerpnt", "libreoffice", "canva"],
    "drawing": ["mspaint", "paint.net", "krita", "blender"],
    "3d": ["blender", "maya", "sketchup"],
    "game": ["steam", "epicgameslauncher", "gog"],
    "games": ["steam", "epicgameslauncher", "xbox"],
    "game launcher": ["steam", "epicgameslauncher", "gog", "origin"],
    "store": ["msstore", "steam", "epicgameslauncher"],
    "app store": ["msstore", "winget"],
    "file manager": ["explorer", "totalcmd", "directoryopus"],
    "task manager": ["taskmgr", "processhacker", "procexp"],
    "system monitor": ["taskmgr", "processhacker", "perfmon"],
    "disk cleaner": ["cleanmgr", "ccleaner", "bleachbit"],
    "driver": ["driverbooster", "snappy", "devmgmt"],
    "backup": ["filehistory", "macrium", "veeam"],
}

_INSTALLED_APPS_CACHE: dict[str, str] = {}
_CACHE_FILE = Path(__file__).resolve().parent.parent / "config" / "installed_apps.json"

# ADDITIVE (purana hataya nahi): Hindi colloquial names -> English app keys.
# thefuzz/difflib stage se pehle consult hota hai taaki "ganana wala app" bhi khule.
_HINDI_APP_NAMES: dict[str, str] = {
    "ganana wala app": "calculator",
    "calculator wala": "calculator",
    "hisab wala": "calculator",
    "likhne wala": "notepad",
    "likhne wala app": "notepad",
    "note likhne wala": "notepad",
    "tasveer wala": "mspaint",
    "photo wala app": "mspaint",
    "drawing wala app": "mspaint",
    "tasveer banane wala": "mspaint",
    "gaana wala app": "spotify",
    "gana wala": "spotify",
    "gaana sunne wala": "spotify",
    "gana sunne wala": "spotify",
    "film wala app": "vlc",
    "video wala": "vlc",
    "film dekhne wala": "vlc",
    "video dekhne wala": "vlc",
    "net wala app": "chrome",
    "browser wala": "chrome",
    "internet wala": "chrome",
    "net chalane wala": "chrome",
    "baat karne wala": "whatsapp",
    "message wala app": "whatsapp",
    "chat karne wala app": "whatsapp",
    "chat wala": "whatsapp",
    "meeting wala app": "zoom",
    "padhne wala app": "winword",
    "hisab kitab wala": "excel",
    "setting wala": "ms-settings:",
    "setting wala app": "ms-settings:",
    "camera wala app": "microsoft.windows.camera:",
    "photo lene wala app": "microsoft.windows.camera:",
    "photo kheenchne wala": "microsoft.windows.camera:",
    "webcam wala": "microsoft.windows.camera:",
    "file dekhne wala": "explorer",
    "folder dekhne wala": "explorer",
    "mail dekhne wala": "chrome",
    "code likhne wala": "code",
    "coding wala app": "code",
}


def _scan_uwp_apps(apps: dict[str, str]) -> int:
    """ADDITIVE: Windows UWP Store apps via Get-AppxPackage. Returns added count."""
    if _SYSTEM != "Windows":
        return 0
    added = 0
    try:
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command",
               "Get-AppxPackage | Select-Object Name, PackageFamilyName | ConvertTo-Json"]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        if p.returncode == 0 and p.stdout.strip():
            items = json.loads(p.stdout)
            if isinstance(items, dict):
                items = [items]
            for item in items:
                name = str(item.get("Name", "") or "").strip()
                fam = str(item.get("PackageFamilyName", "") or "").strip()
                if name and fam and name.lower() not in apps:
                    apps[name.lower()] = fam
                    added += 1
    except Exception as e:
        print(f"[open_app] UWP scan note: {e}")
    return added


def _scan_winget_apps(apps: dict[str, str]) -> int:
    """ADDITIVE: winget list packages. Returns added count."""
    if _SYSTEM != "Windows" or not shutil.which("winget"):
        return 0
    added = 0
    try:
        p = subprocess.run(["winget", "list", "--source", "winget"],
                           capture_output=True, text=True, timeout=20)
        if p.returncode == 0:
            for line in p.stdout.splitlines()[1:]:
                parts = line.strip().rsplit(None, 2)
                if parts and len(parts[0]) > 2 and parts[0].lower() not in apps:
                    apps[parts[0].lower()] = parts[0]
                    added += 1
    except Exception as e:
        print(f"[open_app] winget scan note: {e}")
    return added


def _scan_steam_games(apps: dict[str, str]) -> int:
    """ADDITIVE: Steam library game folders as launchable entries. Returns added count."""
    added = 0
    try:
        steam_dirs = []
        if _SYSTEM == "Windows":
            for d in ("C:/Program Files (x86)/Steam", "C:/Program Files/Steam",
                      "D:/Steam", "E:/Steam"):
                if os.path.isdir(os.path.join(d, "steamapps")):
                    steam_dirs.append(d)
        elif _SYSTEM == "Linux":
            _home = str(Path.home() / ".steam" / "steam")
            if os.path.isdir(os.path.join(_home, "steamapps")):
                steam_dirs.append(_home)
        for sdir in steam_dirs:
            _acf_dir = os.path.join(sdir, "steamapps")
            try:
                for f in os.listdir(_acf_dir):
                    if f.startswith("appmanifest_") and f.endswith(".acf"):
                        try:
                            txt = open(os.path.join(_acf_dir, f), encoding="utf-8", errors="replace").read()
                            import re as _re
                            m = _re.search(r'"name"\s+"([^"]+)"', txt)
                            aid = _re.search(r'"appid"\s+"(\d+)"', txt)
                            if m and m.group(1).lower() not in apps:
                                apps[m.group(1).lower()] = (
                                    f"steam://rungameid/{aid.group(1)}" if aid else sdir)
                                added += 1
                        except Exception:
                            continue
            except Exception:
                continue
    except Exception as e:
        print(f"[open_app] Steam scan note: {e}")
    return added


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
                        k = name.lower()
                        # Prefer working Store AppIDs (with '!') or valid file paths over plain names
                        if k not in apps or ("!" in appid and "!" not in apps[k]):
                            apps[k] = appid
                # Auto-alias desktop variants (e.g. 'Telegram Desktop' -> 'telegram')
                for root_name in ("telegram", "whatsapp", "spotify", "discord", "chrome"):
                    desk_v = f"{root_name} desktop"
                    if desk_v in apps and (root_name not in apps or "!" not in apps.get(root_name, "")):
                        apps[root_name] = apps[desk_v]
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

    # ADDITIVE extended sources (purane 3 scanners untouched, sab try/except me):
    try:
        _n1 = _scan_uwp_apps(apps)
        _n2 = _scan_winget_apps(apps)
        _n3 = _scan_steam_games(apps)
        if (_n1 + _n2 + _n3) > 0:
            print(f"[open_app] Extended scan: +{_n1} UWP, +{_n2} winget, +{_n3} Steam entries.")
    except Exception as e:
        print(f"[open_app] Extended scan note: {e}")

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
    # Windows system URI protocols are always available (e.g. microsoft.windows.camera:, ms-settings:)
    if _SYSTEM == "Windows" and (name_or_bin.endswith(":") or name_or_bin.startswith("ms-") or name_or_bin.startswith("microsoft.")):
        return True
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
    4. Fuzzy matching across all scanned desktop and UWP applications
    5. On-demand dynamic system rescan (self-healing for newly installed apps)
    """
    if not requested:
        return requested, None

    key = requested.strip().lower()

    # Stage 0: Direct protocol / URI schemes
    if _SYSTEM == "Windows" and (key.endswith(":") or key.startswith("ms-") or key.startswith("microsoft.")):
        return requested, None

    installed = _scan_installed_apps()

    # ADDITIVE Stage 0: Hindi colloquial names
    if key in _HINDI_APP_NAMES:
        key = _HINDI_APP_NAMES[key]

    # Stage 1: Category fallback mapping
    for category, candidates in _CATEGORY_FALLBACKS.items():
        if key == category or any(c in key for c in candidates):
            for candidate in candidates:
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
        if _SYSTEM == "Windows" and (target.endswith(":") or target.startswith("ms-") or target.startswith("microsoft.")):
            return target, None
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



# ADDITIVE guards (purana launch flow untouched, sirf verify layer):
# Hindi verbs/particles jo model kabhi-kabhi app naam bana deta hai ("kro", "karo").
_GARBAGE_TOKENS = frozenset({
    "kro", "karo", "kar", "karna", "karke", "khol", "kholo", "kholna", "band", "kroo",
    "dekh", "dekho", "dekhna", "dikh", "dikhao", "dikhana",
    "sun", "suno", "sunna", "sunao", "sunana",
    "bol", "bolo", "bolna", "bata", "batao", "batana", "kaho", "samjhao",
    "chal", "chalo", "chalna", "chala", "chalao", "chalana", "chalu",
    "likh", "likho", "likhna", "bhej", "bhejo", "bhejna", "rok", "roko", "rokna",
    "me", "mein", "ko", "se", "par", "per", "ke", "ki", "ka", "wala", "wale", "wali",
    "hai", "he", "hain", "ho", "ga", "ge", "gi", "do", "de", "doon", "na",
    "naa", "re", "ji", "zara", "abhi", "kuch", "kuchh", "baat", "cheez",
    "the", "a", "an", "it", "this", "that", "please", "pls", "ek", "bhi",
})


def _snapshot_pids() -> set:
    try:
        import psutil as _ps
        return set(_ps.pids())
    except Exception:
        return set()


def _activate_window(hint: str) -> bool:
    """Best-effort window activation: bring existing window matching hint to front."""
    try:
        import pygetwindow as _gw
        q = hint.lower().replace(".exe", "").strip()
        toks = [t for t in q.replace("!", " ").replace("\\", " ").replace(".", " ").split() if len(t) >= 3]
        if not toks:
            return False
        wins = [w for w in _gw.getAllWindows() if w.title.strip()]
        for w in wins:
            w_low = w.title.lower()
            for t in toks:
                if t in w_low:
                    try:
                        w.restore()
                        w.activate()
                        return True
                    except Exception:
                        pass
    except Exception:
        pass
    return False


def _process_appeared(hint: str, before: set, timeout: float = 2.5) -> bool:
    """Best-effort launch verify: koi naya non-Explorer process hint se match,
    ya pehle se running process/window responsive hai?
    psutil na ho to True (fail-open = purana behavior, kuch hataya nahi)."""
    time.sleep(timeout)
    try:
        import psutil as _ps
    except Exception:
        return True
    try:
        toks = [t for t in hint.lower().replace(".exe", "").replace("!", " ").replace(
            "\\", " ").replace(".", " ").replace(":", " ").split() if len(t) >= 3]
        if not toks:
            return True
        # 1. New process appeared
        for pid in _ps.pids():
            if pid in before:
                continue
            try:
                n = (_ps.Process(pid).name() or "").lower()
            except Exception:
                continue
            if n in ("explorer.exe", "shellexperiencehost.exe",
                     "startmenuexperiencehost.exe", "searchhost.exe", "sihost.exe"):
                continue
            base = n.replace(".exe", "")
            for t in toks:
                if t in base or base in t:
                    _activate_window(hint)
                    return True
        # 2. Process was already running: Windows passes activation to existing instance
        for p in _ps.process_iter(['name']):
            try:
                n = (p.info.get('name') or "").lower().replace(".exe", "")
                if n in ("explorer", "shellexperiencehost", "startmenuexperiencehost", "searchhost", "sihost"):
                    continue
                for t in toks:
                    if t == n or (len(t) >= 4 and (t in n or n in t)):
                        _activate_window(hint)
                        return True
            except Exception:
                continue
        return False
    except Exception:
        return True


def _looks_like_appid(name: str) -> bool:
    """shell:AppsFolder sirf plausible AppID par try karo taaki invalid ID par
    Explorer Documents na khole (screenshot wala bug)."""
    n = (name or "").strip()
    if not n or " " in n or "\\" in n or "/" in n or ":" in n:
        return False
    return ("!" in n) or ("." in n and len(n) > 4)


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

    # 4. Windows Store / Get-StartApps AppID via shell:AppsFolder.
    # FIX (additive): plausible AppID par hi try + process verify. Blind return True
    # hataya — invalid ID par Explorer Documents kholta tha + "Opened" jhooth bolta tha.
    # UWP family-only ID par `{family}!App` bhi try karo (shell ko poora AppID chahiye).
    if app_name and _looks_like_appid(app_name):
        try:
            _before = _snapshot_pids()
            subprocess.Popen(f'explorer.exe "shell:AppsFolder\\\\{app_name}"', shell=True)
            if _process_appeared(app_name, _before, timeout=2.5):
                time.sleep(0.5)
                return True
            # Do NOT guess !App if it fails, as invalid shell:AppsFolder paths cause Windows Explorer to open Documents folder
            print(f"[open_app] AppsFolder verify failed for {app_name}, trying Start Menu...")
        except Exception:
            pass

    # 5. Last resort: Start Menu keyboard automation (verify ke saath)
    # Never type dotted names into Start Menu — Windows interprets dots as file extensions and opens Documents folder!
    clean_search = app_name.split(".")[0].strip() if "." in app_name else app_name
    if len(clean_search) >= 2:
        try:
            import pyautogui
            _before = _snapshot_pids()
            pyautogui.PAUSE = 0.1
            pyautogui.press("win")
            time.sleep(0.7)
            pyautogui.write(clean_search, interval=0.05)
            time.sleep(0.9)
            pyautogui.press("enter")
            if _process_appeared(app_name, _before, timeout=2.5):
                time.sleep(0.5)
                return True
            # Dismiss Start Menu cleanly so it doesn't stay open or select files
            pyautogui.press("escape")
            time.sleep(0.1)
            pyautogui.press("escape")
            print(f"[open_app] Start Menu verify failed for {app_name}.")
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

    # ADDITIVE: open_with — file ko specific app me kholo (purana open untouched)
    if action in ("open_with", "openwith", "open_in"):
        file_path = (params.get("file_path") or params.get("file") or "").strip()
        if not app_name or not file_path:
            return "Please specify both app_name and file_path for open_with."
        resolved_target, fallback_note = _resolve_app(app_name)
        try:
            if _SYSTEM == "Windows":
                subprocess.Popen(f'start "" "{resolved_target}" "{file_path}"', shell=True)
            elif _SYSTEM == "Darwin":
                subprocess.run(["open", "-a", resolved_target, file_path], capture_output=True, timeout=8)
            else:
                subprocess.Popen([resolved_target, file_path],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1.2)
            return f"Opened {file_path} in {app_name}."
        except Exception as e:
            return f"Failed to open file in {app_name}: {e}"

    # ADDITIVE: routine save — voice se nayi routine banao (launch block untouched)
    if action in ("save_routine", "create_routine", "routine_banao", "add_routine"):
        routine_name = (params.get("routine") or app_name or "").strip().lower()
        raw_apps = str(params.get("apps", "") or "").strip()
        if not routine_name or not raw_apps:
            return ("Routine banane ke liye naam + apps do "
                    "(e.g. routine='movie', apps='brave, spotify').")
        entries = [a.strip() for a in raw_apps.replace(";", ",").split(",") if a.strip()][:10]
        if not entries:
            return "Apps list khali hai."
        try:
            _rfile = Path(__file__).resolve().parent.parent / "config" / "routines.json"
            routines = json.loads(_rfile.read_text(encoding="utf-8")) if _rfile.exists() else {}
            if not isinstance(routines, dict):
                routines = {}
            routines[routine_name] = entries
            _tmp = _rfile.with_suffix(".json.tmp")
            _tmp.write_text(json.dumps(routines, indent=2, ensure_ascii=False), encoding="utf-8")
            import os as _os
            _os.replace(str(_tmp), str(_rfile))
            return f"Routine '{routine_name}' save ho gayi ({len(entries)} apps). Chalane ke liye '{routine_name} routine chalao' bolo."
        except Exception as e:
            return f"Routine save failed: {e}"

    # ADDITIVE: routine — config/routines.json se multi-app launch (PowerToys Workspaces style)
    if action in ("routine", "workspace", "setup"):
        routine_name = (params.get("routine") or app_name or "").strip().lower()
        try:
            _rfile = Path(__file__).resolve().parent.parent / "config" / "routines.json"
            routines = json.loads(_rfile.read_text(encoding="utf-8")) if _rfile.exists() else {}
        except Exception:
            routines = {}
        if routine_name not in routines:
            known = ", ".join(sorted(k for k in routines.keys() if not k.startswith("_"))) or "dev, movie"
            return (f"Routine '{routine_name}' nahi mili. Saved routines: {known}. "
                    f"Bolo 'routine banao {routine_name}: brave, spotify'.")
        launcher = _OS_LAUNCHERS.get(_SYSTEM)
        opened, failed = [], []
        for entry in routines[routine_name]:
            try:
                tgt, _ = _resolve_app(str(entry))
                if launcher and launcher(tgt):
                    opened.append(str(entry))
                else:
                    failed.append(str(entry))
            except Exception:
                failed.append(str(entry))
        msg = f"Routine '{routine_name}': {len(opened)} opened ({', '.join(opened)})"
        if failed:
            msg += f"; failed: {', '.join(failed)}"
        return msg + "."

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

    # ADDITIVE guard: model kabhi Hindi verb ko app naam bana deta hai ("kro").
    # Aise garbage par launcher chalane se Explorer Documents khul jata tha.
    if app_name.lower().strip() in _GARBAGE_TOKENS or len(app_name.strip()) < 2:
        return ("Mujhe samajh nahi aaya kaun sa app kholna hai. "
                "App ka naam dobara bolo (e.g. 'Chrome kholo').")

    if action in ("close", "kill", "quit", "band", "exit"):
        return _close_app(app_name)

    launcher = _OS_LAUNCHERS.get(_SYSTEM)
    if launcher is None:
        return f"Unsupported operating system: {_SYSTEM}"

    resolved_target, fallback_note = _resolve_app(app_name)
    print(f"[open_app] Launching: '{app_name}' -> '{resolved_target}' (Note: {fallback_note})")

    # ADDITIVE: If app window is already open and visible, bring to front directly
    if _activate_window(app_name) or _activate_window(resolved_target):
        if player:
            player.write_log(f"[open_app] {app_name} (already active)")
        return f"{app_name.capitalize()} is already open and brought to front."

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
    "description": "Opens any application on the computer, closes apps, lists active running applications, refreshes installed apps cache, opens files in apps (open_with), or launches saved multi-app routines/workspaces. Supports intelligent dynamic auto-discovery on any PC and smart category fallbacks (e.g. opens Brave if Chrome is not installed).",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "app_name": {
                "type": "STRING",
                "description": "Exact or colloquial name of the application (e.g. 'Chrome', 'Notepad', 'Brave', 'Browser', 'Terminal'), 'list' to see running apps, or 'refresh' to scan system apps."
            },
            "action": {
                "type": "STRING",
                "description": "'open' to launch an app, 'close' to terminate an app, 'list' to list running applications, 'refresh' to dynamically rescan installed applications, 'open_with' to open a file in an app, 'routine' to launch a saved multi-app workspace, 'save_routine' to create one by voice."
            },
            "file_path": {
                "type": "STRING",
                "description": "File to open when action is open_with (e.g. 'C:\\notes\\a.docx')"
            },
            "routine": {
                "type": "STRING",
                "description": "Routine name from config/routines.json when action is routine (e.g. 'dev setup')"
            },
            "apps": {
                "type": "STRING",
                "description": "Comma-separated app list when action is save_routine (e.g. 'brave, spotify')"
            }
        },
        "required": [
            "app_name"
        ]
    },
    "handler": open_app,
}
