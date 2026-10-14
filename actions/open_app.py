import difflib
import json
import os
import platform
import re
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
    # Spaced form of the same product. Without this, "vs code" fell through to
    # fuzzy matching and resolved to Notepad, because "code" is not itself an
    # installed app name on Windows.
    "vs code":            {"Windows": "code",                    "Darwin": "Visual Studio Code",   "Linux": "code"},
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


def _known_installed(name: str) -> bool | None:
    """Is there any record that `name` is an application on this machine?

    Returns
    -------
    True   - the installed-app index has a plausible entry for it.
    False  - the index is populated and holds nothing plausible.
    None   - the index could not be built, so nothing can honestly be claimed.

    WHY THE THREE-WAY ANSWER
    ------------------------
    A two-way answer would turn a failed or still-building scan into "not
    installed" for every request, breaking launches on any machine where the
    scan misbehaves. None means "unknown", and the caller keeps its previous
    behaviour rather than guessing.

    Matched the same way _resolve_app matches, on purpose: two different
    definitions of "installed" would eventually disagree, and the caller would
    act on the wrong one.
    """
    try:
        installed = _scan_installed_apps()
    except Exception:
        return None
    if not installed:
        # An empty index is indistinguishable from a broken one. Do not treat
        # it as proof that nothing is installed.
        return None

    key = str(name or "").strip().lower()
    if not key:
        return False

    if key in installed:
        return True

    # Colloquial names the resolver itself would translate.
    if key in _HINDI_APP_NAMES and _HINDI_APP_NAMES[key] in installed:
        return True

    # An alias whose target is genuinely reachable is a hit, even when the
    # alias name is not itself an index key.
    if key in _APP_ALIASES:
        try:
            if _is_app_installed(_APP_ALIASES[key].get(_SYSTEM, key)):
                return True
        except Exception:
            pass

    # Word-overlap, using the same minimum-fragment guard as the resolver so
    # a bare 2-3 character prefix can never count as a match.
    words = {w for w in re.split(r"[\s_\-.]+", key) if len(w) >= 4}
    if words:
        for indexed in installed:
            if words & set(re.split(r"[\s_\-.]+", indexed)):
                return True
    return False


def _looks_like_opaque_identifier(text: str) -> bool:
    """Whether `text` is a machine identifier rather than a human app name.

    Three shapes, all of which reach this function in practice because the
    value column of the app index contains Windows AppUserModelIDs:

      308046B0AF4A39CB                       a publisher/AppID hex token
      1AC14E77-02E7-4E5D-B744-2EB1AE5198B7   a GUID / UUID
      Microsoft.WindowsCalculator_8wekyb3d8bbwe  an AppID package family name

    The test is deliberately narrow. A real app name is never all hex, and a
    name containing a digit like "7zip" or "Notepad 3" must still resolve, so
    the checks require the WHOLE string to be opaque - no words mixed in.

    Ordinary prose is never flagged: "ab", "hello", "notepad" all fail every
    test below and fall through to normal resolution.
    """
    s = str(text or "").strip()
    if not s:
        return False

    # GUID / UUID, with or without braces.
    if re.fullmatch(
            r"\{?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
            r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}?", s):
        return True

    # All-hex token with no separators. Needs >= 8 chars so that short tokens
    # and ordinary words made of hex letters (deadbeef aside) are not swept up.
    if len(s) >= 8 and re.fullmatch(r"[0-9a-fA-F]+", s):
        return True

    # AppID package family: words, but joined by dots and digits in the shape
    # Windows uses. Requires a digit and at least one dot to stay clear of
    # ordinary dotted names.
    if "." in s and re.fullmatch(r"[A-Za-z0-9_]+(\.[A-Za-z0-9_]+)+", s):
        if any(c.isdigit() for c in s) and len(s) >= 12:
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
    # Shortest meaningful app-name fragment. Guards the substring/fuzzy stages
    # below against matching on bare 2-3 character prefixes such as "hu".
    _MIN_SUBSTR = 4

    # Opaque identifiers are not app names.
    #
    # Found in a real session: the user spoke a Firefox profile UUID,
    # "308046B0AF4A39CB". The app index stores Windows AppUserModelIDs in the
    # VALUE column - firefox maps to "308046B0AF4A39CB" - so the substring
    # stage happily matched the user's text against that value and returned it
    # as the executable. Windows then resolved the AppID and something
    # unrelated opened, and the user was told their own machine did not have
    # the app they were looking at.
    #
    # An AppID is not a path. Matching a spoken string against the value column
    # can only ever produce garbage, because no user names an application by
    # its AppID.
    if _looks_like_opaque_identifier(requested):
        return requested, (
            "That is an identifier, not an application name "
            "(it looks like a hex code, GUID or AppUserModelID). "
            "Name the app instead."
        )

    # Stage 0: Direct protocol / URI schemes
    if _SYSTEM == "Windows" and (key.endswith(":") or key.startswith("ms-") or key.startswith("microsoft.")):
        return requested, None

    installed = _scan_installed_apps()

    # ADDITIVE Stage 0: Hindi colloquial names
    if key in _HINDI_APP_NAMES:
        key = _HINDI_APP_NAMES[key]

    # Stage 0b: Exact alias lookup, BEFORE any category fallback.
    #
    # An explicit alias is the most specific answer available and must not be
    # pre-empted by a category. "vs code" is an alias for VS Code, but the word
    # "code" is also a member of the "dev" category, whose fallback list ends in
    # notepad++ — so the category stage resolved "vs code" to Notepad before the
    # alias was ever consulted.
    if key in _APP_ALIASES:
        _alias_target = _APP_ALIASES[key].get(_SYSTEM, requested)
        if _SYSTEM == "Windows" and (_alias_target.endswith(":")
                                     or _alias_target.startswith("ms-")
                                     or _alias_target.startswith("microsoft.")):
            return _alias_target, None
        if _is_app_installed(_alias_target):
            return installed.get(key, installed.get(_alias_target.lower(),
                                                    _alias_target)), None

    # Stage 1: Category fallback mapping
    #
    # REGRESSION: `any(c in key for c in candidates)` is a bare substring test.
    # "aur tasks" contains "tasks", so the todo category matched and the
    # resolver answered "aur tasks" with OneNote. Category words must be
    # matched as whole words, not as fragments of unrelated prose.
    _key_words = set(re.split(r"[\s_\-.]+", key))
    for category, candidates in _CATEGORY_FALLBACKS.items():
        if key == category or any(c in _key_words for c in candidates):
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

    # Substring match across installed apps.
    #
    # REGRESSION: this used to be a bare two-way substring test
    # (`key in app_name or app_name in key`). With a two-word target that
    # matches almost anything — "hu use" contains "hu", and any app whose name
    # starts with "hu" (Hubs, Hub) satisfied `app_name in key`, so the resolver
    # confidently reported Notepad as the answer to "main nahi kiya hu use band
    # kro" and the assistant announced it had closed an app that does not exist.
    #
    # A substring is only meaningful when it is a substantial part of the query
    # and not a bare prefix fragment, so require the overlap to be at least
    # 4 characters (the shortest real app name) and to anchor on a word boundary.
    if len(key) >= _MIN_SUBSTR:
        for app_name, app_id in installed.items():
            if len(app_name) >= _MIN_SUBSTR:
                if key in app_name or app_name in key:
                    return app_id, None

    # Stage 4: Fuzzy matching against installed apps
    all_names = list(installed.keys())
    # Fuzzy matching, but only against names that plausibly overlap.
    #
    # `difflib.get_close_matches(key, all_names, cutoff=0.6)` compares whole
    # strings, so a two-word query like "vs code" can land on an unrelated
    # single-word app. Restricting the candidate pool to names that share at
    # least one meaningful word with the query keeps the fuzzy step useful
    # without letting it invent a target.
    _query_words = {w for w in re.split(r"[\s_\-.]+", key) if len(w) >= _MIN_SUBSTR}
    if _query_words:
        all_names = [n for n in installed.keys()
                     if _query_words & set(re.split(r"[\s_\-.]+", n.lower()))]
    else:
        all_names = list(installed.keys())
    close = difflib.get_close_matches(key, all_names, n=1, cutoff=0.6) if all_names else []
    if close:
        matched_name = close[0]
        return installed[matched_name], f"'{requested}' ki jagah '{matched_name}' mila"

    # Self-healing on-demand rescan: If not found, perhaps user recently installed it
    if allow_rescan:
        print(f"[open_app] '{requested}' not found in cache. Running dynamic on-demand system rescan...")
        _scan_installed_apps(force_refresh=True)
        return _resolve_app(requested, allow_rescan=False)

    # Fallback to normalized alias or raw string.
    # Same word-boundary guard as the substring stage above: a bare two-way
    # containment test here would let a short alias fragment match an unrelated
    # multi-word query.
    _MIN_SUBSTR = 4
    for alias_key, os_map in _APP_ALIASES.items():
        if len(alias_key) < _MIN_SUBSTR or len(key) < _MIN_SUBSTR:
            continue
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


def _force_window_to_front(w) -> bool:
    """Force window to foreground bypassing Windows SetForegroundWindow lock."""
    try:
        w.restore()
    except Exception:
        pass
    if _SYSTEM == "Windows":
        try:
            import ctypes
            u32 = ctypes.windll.user32
            hwnd = getattr(w, "_hWnd", None)
            if hwnd:
                u32.ShowWindow(hwnd, 9)  # SW_RESTORE
                # Windows SetForegroundWindow lock bypass via simulated ALT keystroke
                u32.keybd_event(0x12, 0, 0, 0)  # ALT down
                u32.SetForegroundWindow(hwnd)
                u32.keybd_event(0x12, 0, 2, 0)  # ALT up
                return True
        except Exception:
            pass
    try:
        w.activate()
        return True
    except Exception:
        pass
    return False


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
                    if _force_window_to_front(w):
                        return True
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
            if not n:
                # An unreadable or just-exited process reports an empty name.
                # Python's `"" in "anything"` is True, so an unguarded empty
                # name matches EVERY hint and this function reports success for
                # a launch that never happened. Observed: asking for an app
                # that is not installed returned "Opened <app>."
                continue
            if n in ("explorer.exe", "shellexperiencehost.exe",
                     "startmenuexperiencehost.exe", "searchhost.exe", "sihost.exe"):
                continue
            base = n.replace(".exe", "")
            if not base:
                continue
            for t in toks:
                if t and base and (t == base or t in base or base in t):
                    _activate_window(hint)
                    return True
        # 2. Process was already running: Windows passes activation to existing instance
        for p in _ps.process_iter(['name']):
            try:
                n = (p.info.get('name') or "").lower().replace(".exe", "")
                if not n:
                    continue        # same empty-name trap as the loop above
                if n in ("explorer", "shellexperiencehost", "startmenuexperiencehost", "searchhost", "sihost"):
                    continue
                for t in toks:
                    if t and (t == n or (len(t) >= 4 and (t in n or n in t))):
                        _activate_window(hint)
                        return True
            except Exception:
                continue
        return False
    except Exception:
        return True


def _looks_like_appid(name: str) -> bool:
    """Is this a Windows AppUserModelID, launchable via shell:AppsFolder?

    THE BUG THIS FIXES
    ------------------
    The old version rejected anything containing a backslash:

        if not n or " " in n or "\\" in n or "/" in n or ":" in n:
            return False

    That was well intentioned - a real path like `C:\\Program Files\\...` must
    not be handed to the shell namespace. But `{1AC14E77-...}\\notepad.exe`
    IS the genuine Notepad AppID, straight from Get-StartApps:

        Firefox    308046B0AF4A39CB
        Notepad    {1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\notepad.exe
        Calculator Microsoft.WindowsCalculator_8wekyb3d8bbwe!App

    So the AppID stage was skipped for Notepad, control fell through to the
    Start Menu keyboard automation, and pyautogui typed the literal tail of
    the id into the Windows search box - `5198B7}\\notepad` in the All apps
    list - while the assistant reported "Opened Notepad."

    The distinction that actually matters is not "contains a backslash". It is
    "is this a filesystem path or an opaque Windows identifier":
      * a GUID in braces followed by one backslash and a name is an AppID
      * a drive letter, or more than one separator, is a real path
    """
    n = (name or "").strip()
    if not n or " " in n:
        return False

    # "Family.Name!App" - the packaged-app form.
    if "!" in n:
        return "/" not in n and ":" not in n

    # "{GUID}\\name.exe" - the form Get-StartApps reports for Notepad.
    # Exactly one backslash, braces around the first segment, and no drive.
    if "\\" in n:
        if n.count("\\") != 1 or ":" in n or "/" in n:
            return False                    # a real path, not an identifier
        head, _, tail = n.partition("\\")
        return bool(re.fullmatch(r"\{[0-9A-Fa-f-]{36}\}", head)) and bool(tail)

    # A bare AppID with no separator at all, e.g. Firefox's publisher token.
    # Get-StartApps also reports suffixed variants such as
    # "308046B0AF4A39CB;PrivateBrowsingAUMID", so a semicolon is allowed here.
    # Requires a digit so ordinary words never qualify.
    if "/" in n or ":" in n:
        return False
    if (len(n) >= 8 and re.fullmatch(r"[0-9A-Za-z;]+", n)
            and any(c.isdigit() for c in n)):
        return True

    return "." in n and len(n) > 4


def _win_start(target: str, *extra: str) -> None:
    """Launch a Windows target via `start` WITHOUT shell interpolation.

    Every previous call site used subprocess.Popen(f'start "" "{x}"', shell=True).
    `app_name` arrives from the model's tool-call arguments, so a value like
    `x" & calc &"` closed the quoted argument and ran a second command. Windows
    has no argv form of `start`, so cmd.exe is invoked explicitly as a LIST —
    cmd /c receives the whole thing as one argument and never re-parses our
    quoting into a new command. This is the standard Windows equivalent of a
    shell=True launch and removes the injection vector.
    """
    cmd = ["cmd", "/c", "start", "", target, *extra]
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(cmd, **kw)


# ── test guard ──────────────────────────────────────────────────────────────
# J.A.R.V.I.S can put windows on the user's screen and press keys for them.
# That is unacceptable while the test suite runs, because scripts/git_hooks/
# checks.py executes the full suite on EVERY push. A test that really launched
# Notepad would open Notepad on the developer's desktop once per commit.
#
# That is not hypothetical. tests/test_start_search_gate.py passed a real
# AppUserModelID to _launch_windows to prove identifiers are never typed into
# Start Menu. _launch_windows did exactly what it is built to do and opened
# Notepad. Confirmed from the process table on this machine: notepad.exe whose
# parent explorer.exe had already exited, created during the test run.
#
# The switch lives here, in the module someone is about to call, rather than as
# a monkeypatch in conftest.py. A conftest patch makes the problem invisible to
# the next person who writes a test; a named guard here does not.
_NO_REAL_LAUNCH: bool | None = None


def _real_launches_disabled() -> bool:
    """True when nothing may actually be launched.

    Callable side sets it directly; the environment variable exists so a test
    that imported the module before conftest ran is still covered.
    """
    if _NO_REAL_LAUNCH is not None:
        return bool(_NO_REAL_LAUNCH)
    return str(os.environ.get("JARVIS_NO_REAL_LAUNCH", "")).strip().lower() \
        not in ("", "0", "false", "no")


def _launch_windows(app_name: str) -> bool:
    """Launch application on Windows via path, AppID, shell protocol, or Start Menu."""
    if _real_launches_disabled():
        print(f"[open_app] real launches disabled; not launching {app_name!r}")
        return False

    # 1. Direct path to .lnk or .exe
    if app_name.endswith(".lnk") or app_name.endswith(".exe") and os.path.exists(app_name):
        try:
            _win_start(app_name)
            time.sleep(1.0)
            return True
        except Exception:
            pass

    # 2. Direct binary on PATH
    if shutil.which(app_name) or shutil.which(app_name.split(".")[0]):
        try:
            kw = {}
            if os.name == "nt":
                kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            # No shell: the resolved executable is executed directly.
            subprocess.Popen(
                app_name,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **kw,
            )
            time.sleep(1.2)
            return True
        except Exception as e:
            print(f"[open_app] subprocess failed: {e}")

    # 3. Protocol handler (e.g. ms-settings:)
    if ":" in app_name and not ("\\" in app_name or "/" in app_name):
        try:
            _win_start(app_name)
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
            # No shell: explorer.exe is exec'd directly with the shell: namespace
            # URI as an argv element, so no quoting/escaping is involved.
            kw = {}
            if os.name == "nt":
                kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(
                ["explorer.exe", f"shell:AppsFolder\\{app_name}"],
                **kw,
            )
            if _process_appeared(app_name, _before, timeout=2.5):
                time.sleep(0.5)
                return True
            # Do NOT guess !App if it fails, as invalid shell:AppsFolder paths cause Windows Explorer to open Documents folder
            print(f"[open_app] AppsFolder verify failed for {app_name}, trying Start Menu...")
        except Exception:
            pass

    # 5. Last resort: Start Menu keyboard automation (verify ke saath)
    # Never type dotted names into Start Menu — Windows interprets dots as file
    # extensions and opens the Documents folder instead.
    #
    # And never type an identifier at all. Typing the tail of
    # "{1AC14E77-...}\notepad.exe" produced a Windows search box reading
    # "5198B7}\notepad", which is not a search anyone can act on - it is
    # developer output leaking into the user's screen.
    clean_search = app_name.split(".")[0].strip() if "." in app_name else app_name
    if _looks_like_opaque_identifier(clean_search) or _looks_like_appid(app_name):
        print(f"[open_app] refusing Start Menu search for non-name target "
              f"{app_name!r}")
        return False

    # ADDITIVE gate: only hand a name to Windows Search when the machine
    # actually has a record of that application.
    #
    # THE BUG
    # -------
    # Asking for Telegram produced:
    #
    #     [open_app] 'Telegram' not found in cache. Running dynamic on-demand
    #                system rescan...
    #     [open_app] Launching: 'Telegram' -> 'Telegram'
    #
    # and Windows Search opened showing "Telegram (software)". Telegram is not
    # installed on this machine - no Get-StartApps entry, no uninstall
    # registry key, nothing on disk. The user had to dismiss a search box and a
    # Microsoft Store results page for an application that does not exist.
    #
    # This is worse than doing nothing. When Windows Search is given a name it
    # cannot match locally, it does not report failure - it falls through to
    # the Store and shows results to buy. So "type it and see" converts a
    # one-line "not installed" into a shopping page, while stealing focus from
    # whatever the user was actually doing.
    #
    # The stages above already handle everything genuinely installed: a real
    # path, a binary on PATH, a protocol handler, an AppID. An application that
    # is absent from the index AND unreachable by all of those is not installed,
    # and searching for it cannot succeed - it can only reach the Store.
    #
    # Unknown (an index that could not be built) keeps the old behaviour, so a
    # scan failure on someone else's machine degrades rather than breaks.
    _on_record = _known_installed(clean_search)
    if _on_record is False:
        print(f"[open_app] '{clean_search}' is not in the installed-app index "
              f"({len(_scan_installed_apps())} apps scanned). Refusing Windows "
              f"Search: an unmatched query opens the Microsoft Store.")
        return False

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
    # Same guard as _launch_windows: `open -a` really does launch the app.
    if _real_launches_disabled():
        return False
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
    if _real_launches_disabled():
        return False
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
        result = subprocess.run(["xdg-open", app_name], capture_output=True, timeout=5)
        # FIX: returncode was ignored and this returned True unconditionally.
        #
        # subprocess.run does not raise when the command fails - it returns a
        # finished process with a non-zero exit status. xdg-open on Ubuntu
        # exits non-zero for an application it cannot find, so asking for one
        # that is not installed produced "Opened Telegram."
        #
        # Caught by the ubuntu-latest CI job, not by the Windows one. Same
        # family as the empty-string bug fixed in _process_appeared: a launch
        # reported as successful without ever checking whether it worked.
        if result.returncode == 0:
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
    """Gracefully terminate or kill a running application process with truthful post-termination verification."""
    if not app_name:
        return "No application specified to close."

    raw_clean = re.sub(r"\b(hu|kya|ye|yeh|wo|woh|mera|meri|ko|bhi|app|application)\b", "", app_name.lower()).strip()
    if not raw_clean:
        raw_clean = app_name.lower().strip()

    # Map well-known aliases (e.g. "command prompt" -> "cmd")
    alias_map = {
        "command prompt": "cmd",
        "command line": "cmd",
        "terminal": "cmd",
        "windows terminal": "windowsterminal",
        "file explorer": "explorer",
    }
    clean_target = alias_map.get(raw_clean, raw_clean).replace(".exe", "").strip()

    verified_closed = 0
    failed_pids = []

    if _PSUTIL:
        matching_procs = []
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                pname = (proc.info.get('name') or "").lower().replace(".exe", "")
                if clean_target == pname or (len(clean_target) > 3 and clean_target in pname):
                    matching_procs.append(proc)
            except Exception:
                pass

        for proc in matching_procs:
            pid = proc.pid
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=0.6)
                except (psutil.TimeoutExpired, psutil.NoSuchProcess):
                    pass
                if proc.is_running():
                    proc.kill()
                    try:
                        proc.wait(timeout=0.4)
                    except Exception:
                        pass
                # Post-kill verification
                if not proc.is_running():
                    verified_closed += 1
                else:
                    failed_pids.append(pid)
            except psutil.NoSuchProcess:
                verified_closed += 1
            except Exception:
                failed_pids.append(pid)

    if verified_closed > 0:
        return f"✅ Verified: {raw_clean.capitalize()} band kar diya gaya hai ({verified_closed} process closed)."

    # Fallback to taskkill on Windows with post-verification
    if _SYSTEM == "Windows":
        try:
            exe_name = f"{clean_target}.exe"
            res = subprocess.run(
                ["taskkill", "/IM", exe_name, "/F"],
                capture_output=True, text=True, timeout=5
            )
            if res.returncode == 0:
                time.sleep(0.3)
                chk = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {exe_name}"],
                    capture_output=True, text=True, timeout=3
                )
                if exe_name.lower() not in chk.stdout.lower():
                    return f"✅ Verified: {raw_clean.capitalize()} band kar diya gaya hai."
                else:
                    return f"⚠️ {raw_clean.capitalize()} band nahi ho saka (Process still running)."
        except Exception:
            pass

    if failed_pids:
        return f"⚠️ {raw_clean.capitalize()} band nahi ho saka (Access Denied / System Process)."

    return f"{raw_clean.capitalize()} abhi chal nahi raha tha."


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
        try:
            from actions.file_controller import _resolve_path
            resolved_fp = str(_resolve_path(file_path))
        except Exception:
            resolved_fp = file_path
        resolved_target, fallback_note = _resolve_app(app_name)
        try:
            if _SYSTEM == "Windows":
                _win_start(resolved_target, resolved_fp)
            elif _SYSTEM == "Darwin":
                subprocess.run(["open", "-a", resolved_target, resolved_fp], capture_output=True, timeout=8)
            else:
                subprocess.Popen([resolved_target, resolved_fp],
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
    if "explorer" in resolved_target.lower() and params.get("file_path"):
        try:
            from actions.file_controller import _resolve_path
            fp = str(_resolve_path(params["file_path"]))
            resolved_target = f'explorer.exe "{fp}"'
        except Exception:
            pass
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
            # Best-effort post-launch foreground boost
            time.sleep(0.3)
            _activate_window(app_name)
            if fallback_note:
                return f"{fallback_note}, aur successfully open kar diya!"
            return f"Opened {app_name}."

        # Secondary attempt with raw app_name
        if resolved_target.lower() != app_name.lower():
            if launcher(app_name):
                time.sleep(0.3)
                _activate_window(app_name)
                return f"Opened {app_name}."

        # ADDITIVE: say the useful thing when the machine can actually answer.
        #
        # "It may still be loading, or it might not be installed" is true for
        # every app that ever fails, which makes it no use to anyone. When the
        # index positively holds nothing for this name, the app is not
        # installed and saying so is more useful than hedging - and it is
        # checkable rather than a guess.
        try:
            _absent = _known_installed(app_name) is False
        except Exception:
            _absent = False
        if _absent:
            return (
                f"{app_name} is not installed on this PC - it was not found in "
                f"Start Menu apps, installed programs, UWP apps or the app list "
                f"({len(_scan_installed_apps())} apps indexed). "
                f"Kya main aapke liye web se iske baare mein search karoon?"
            )

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
    "description": (
        "Launch or CLOSE a desktop application. Also lists running apps and launches "
        "saved multi-app routines.\n"
        "USE FOR: 'notepad kholo', 'open chrome', 'brave chalao', 'close notepad', "
        "'spotify band karo', 'kill word', 'open vs code', 'list running apps', "
        "'dev routine chalao'.\n"
        "DO NOT USE FOR (these are different tools):\n"
        "  - opening a FILE or FOLDER   -> file_controller (action=open/explorer)\n"
        "  - timers, tasks, todos       -> todo_agent or tinydb_memory\n"
        "  - volume, brightness, wifi   -> computer_settings\n"
        "  - changing wallpaper, icons  -> desktop_control\n"
        "  - a QUESTION about apps ('mere paas kaunse apps hain') -> just answer in "
        "text, no tool call needed.\n"
        "IMPORTANT: app_name must be a real application name. Never pass sentence "
        "fragments, pronouns or conjunctions such as 'aur tasks' or 'hu use'."
    ),
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
