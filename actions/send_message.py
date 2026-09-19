import json
import os
import subprocess
import sys
import time
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.06
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def _get_os() -> str:
    try:
        cfg = json.loads(
            (_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8")
        )
        return cfg.get("os_system", "windows").lower()
    except Exception:
        return "windows"


def _require_pyautogui():
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI not installed. Run: pip install pyautogui")


def _paste_text(text: str) -> None:
    _require_pyautogui()

    os_name = _get_os()
    paste_hotkey = ("command", "v") if os_name == "mac" else ("ctrl", "v")

    if _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.15)
        pyautogui.hotkey(*paste_hotkey)
        time.sleep(0.1)
    else:
        pyautogui.write(text, interval=0.03)


def _clear_and_paste(text: str) -> None:
    _require_pyautogui()
    os_name = _get_os()
    select_all = ("command", "a") if os_name == "mac" else ("ctrl", "a")
    pyautogui.hotkey(*select_all)
    time.sleep(0.1)
    pyautogui.press("delete")
    time.sleep(0.1)
    _paste_text(text)

def _open_app(app_name: str) -> bool:
    _require_pyautogui()
    os_name = _get_os()

    try:
        if os_name == "windows":
            # 1. First try actions.open_app if available for seamless AppID / shortcut launch
            try:
                from actions.open_app import open_app as _core_open_app
                res = _core_open_app({"app_name": app_name})
                if res and any(k in res.lower() for k in ("opened", "running", "already", "open", "launch")):
                    time.sleep(2.0)
                    return True
            except Exception:
                pass

            # 2. Check if window is already open
            try:
                import pygetwindow as gw
                wins = [w for w in gw.getAllWindows() if app_name.lower() in (w.title or "").lower() and w.visible]
                if wins:
                    try:
                        wins[0].activate()
                        time.sleep(0.5)
                        return True
                    except Exception:
                        pass
            except Exception:
                pass

            # 3. Try Windows Start search, but strictly verify that the target window appeared
            pyautogui.press("win")
            time.sleep(0.5)
            _paste_text(app_name)
            time.sleep(0.6)
            pyautogui.press("enter")
            time.sleep(2.5)

            try:
                import pygetwindow as gw
                wins = [w for w in gw.getAllWindows() if app_name.lower() in (w.title or "").lower() and w.visible]
                if wins:
                    return True
            except Exception:
                pass

            # If no window opened, dismiss Start Menu safely so it doesn't stay open
            pyautogui.press("escape")
            return False

        elif os_name == "mac":
            result = subprocess.run(
                ["open", "-a", app_name],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                result = subprocess.run(
                    ["open", "-a", f"{app_name}.app"],
                    capture_output=True, text=True, timeout=10,
                )
            time.sleep(2.5)
            return result.returncode == 0

        else: 
            launched = False
            for launcher in [
                ["gtk-launch", app_name.lower()],
                [app_name.lower()],
            ]:
                try:
                    subprocess.Popen(
                        launcher,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    launched = True
                    break
                except FileNotFoundError:
                    continue
            time.sleep(2.5)
            return launched

    except Exception as e:
        print(f"[SendMessage] ⚠️ Could not open {app_name}: {e}")
        return False


def _open_browser_url(url: str) -> bool:
    import webbrowser
    try:
        webbrowser.open(url)
        time.sleep(4.0) 
        return True
    except Exception as e:
        print(f"[SendMessage] ⚠️ Could not open browser: {e}")
        return False

def _search_in_app(query: str) -> None:
    _require_pyautogui()
    os_name = _get_os()
    search_hotkey = ("command", "f") if os_name == "mac" else ("ctrl", "f")

    pyautogui.hotkey(*search_hotkey)
    time.sleep(0.5)
    _clear_and_paste(query)
    time.sleep(1.0)

def _desktop_send(app_name: str, receiver: str, message: str) -> str:
    # Additive guard: lock-screen / headless par jhootha "sent" mat bolo (purana flow rakha hai)
    try:
        import ctypes as _ct
        try:
            _fg = _ct.windll.user32.GetForegroundWindow() if hasattr(_ct, "windll") else 1
            if _fg == 0:
                return f"Desktop locked or no foreground window — could not verify send to {receiver} via {app_name}. GUI fallback skipped."
        except Exception:
            pass
    except Exception:
        pass
    if not _open_app(app_name):
        return f"Could not open {app_name}."
    return _desktop_send_verified(app_name, receiver, message)


def _desktop_send_verified(app_name: str, receiver: str, message: str) -> str:
    # Purana GUI flow alag function me rakha hai (hataya nahi), upar verify wrapper joda hai
    time.sleep(1.0)
    _search_in_app(receiver)
    time.sleep(1.0)
    # Highlight first chat/contact in search list (essential for Telegram & desktop apps)
    pyautogui.press("down")
    time.sleep(0.4)
    pyautogui.press("enter")
    time.sleep(1.0)

    if message:
        _paste_text(message)
        time.sleep(0.3)
        pyautogui.press("enter")
        time.sleep(0.3)
    return f"Message sent to {receiver} via {app_name}."

def _try_whatsapp_api(receiver: str, message: str) -> str | None:
    """Additive: phone-number receiver par click-to-chat URL kholo (GUI hataya nahi).
    Returns None jab API path lagu na ho taaki desktop fallback chale."""
    try:
        import re as _re
        from urllib.parse import quote as _q
        _digits = _re.sub(r"\D", "", receiver or "")
        if len(_digits) >= 10 and len(_digits) <= 15:
            _url = f"https://web.whatsapp.com/send?phone={_digits}&text={_q(message)}"
            if _open_browser_url(_url):
                time.sleep(7.0)
                try:
                    pyautogui.press("enter")
                    time.sleep(0.5)
                except Exception:
                    pass
                return f"Message sent to {receiver} via WhatsApp Web link."
    except Exception:
        pass
    return None


def _try_telegram_api(receiver: str, message: str) -> str | None:
    """Additive: TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID env/config ho to Bot API se bhejo.
    Na ho to None taaki desktop fallback chale (purana hataya nahi)."""
    try:
        import os as _os
        _tok = (_os.environ.get("TELEGRAM_BOT_TOKEN", "") or "").strip()
        _chat = (_os.environ.get("TELEGRAM_CHAT_ID", "") or "").strip()
        if not _tok:
            try:
                _cfg = json.loads((_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8"))
                _tok = str(_cfg.get("telegram_bot_token", "") or "").strip()
                _chat = str(_cfg.get("telegram_chat_id", "") or _chat).strip()
                try:  # ADDITIVE: ENC blob support (plaintext passthrough)
                    from core.secret_vault import decrypt_value
                    _tok = str(decrypt_value(_tok) or "").strip()
                except Exception:
                    pass
            except Exception:
                pass
        if _tok and _chat:
            import urllib.request as _ur, urllib.parse as _up
            _data = _up.urlencode({"chat_id": _chat, "text": f"To {receiver}: {message}"}).encode()
            _req = _ur.Request(f"https://api.telegram.org/bot{_tok}/sendMessage", data=_data)
            with _ur.urlopen(_req, timeout=15) as _r:
                if _r.status == 200:
                    return f"Message sent to {receiver} via Telegram Bot API."
    except Exception as _e:
        return f"Telegram Bot API failed ({_e}) — desktop fallback available."
    return None


def _send_whatsapp_web(receiver: str, message: str) -> str:
    """ADDITIVE WhatsApp Web flow — jab PC par WhatsApp app/PWA installed nahi hai.
    web.whatsapp.com kholo -> search me contact -> chat kholo -> message bhejo."""
    _require_pyautogui()
    try:
        # 1. Agar receiver phone number hai, toh direct click-to-chat URL use karo
        import re as _re
        from urllib.parse import quote as _q
        digits = _re.sub(r"\D", "", receiver or "")
        if len(digits) >= 10 and len(digits) <= 15:
            wa_url = f"https://web.whatsapp.com/send?phone={digits}&text={_q(message)}"
            _open_browser_url(wa_url)
            time.sleep(8.0)
            try:
                pyautogui.press("enter")
                time.sleep(0.5)
            except Exception:
                pass
            return f"Message sent to {receiver} via WhatsApp Web."

        # 2. Agar receiver naam hai ('sudhir', 'mummy', etc.)
        if not _open_browser_url("https://web.whatsapp.com"):
            return "Could not open WhatsApp Web in browser."
        time.sleep(6.0)

        # Address bar se focus hatao
        pyautogui.press("escape")
        time.sleep(0.2)
        pyautogui.press("escape")
        time.sleep(0.3)

        # WhatsApp Web search box focus:
        # A. Screen click on typical search location
        try:
            sw, sh = pyautogui.size()
            pyautogui.click(int(sw * 0.18), int(sh * 0.18))
            time.sleep(0.4)
        except Exception:
            pass

        # B. Official WhatsApp Web shortcut: Ctrl+Alt+/ (Cmd+Option+/ on Mac)
        os_name = _get_os()
        if os_name == "mac":
            pyautogui.hotkey("command", "option", "/")
        else:
            pyautogui.hotkey("ctrl", "alt", "/")
        time.sleep(0.5)

        _clear_and_paste(receiver)
        time.sleep(2.0)  # Wait for contact search results to populate
        pyautogui.press("down")
        time.sleep(0.4)
        pyautogui.press("enter")  # Open chat
        time.sleep(1.2)  # Wait for chat input to focus

        if message:
            _paste_text(message)
            time.sleep(0.4)
            pyautogui.press("enter")  # Send
            time.sleep(0.5)

        return (f"WhatsApp Web par '{receiver}' ko message bhejne ki koshish ki. "
                f"Browser me verify kar lo (chat khula dikhe to sent).")
    except Exception as e:
        return f"WhatsApp Web send failed: {e}. Browser me haath se bhej do."


def _is_whatsapp_installed() -> bool:
    """ADDITIVE: WhatsApp desktop/PWA installed hai? Nahi to GUI typing galat
    window me jayegi — isliye pehle check, phir Web fallback."""
    try:
        import shutil as _sh
        if _sh.which("WhatsApp") or _sh.which("whatsapp"):
            return True
    except Exception:
        pass
    try:
        from actions.open_app import _scan_installed_apps
        apps = _scan_installed_apps()
        if any("whatsapp" in k for k in apps):
            return True
    except Exception:
        pass
    try:
        import os as _os
        _paths = [
            os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe"),
            os.path.expandvars(r"%ProgramFiles%\WhatsApp\WhatsApp.exe"),
            r"C:\Program Files\WindowsApps\Meta.WhatsAppBeta_8wekyb3d8bbwe",
        ]
        if any(os.path.exists(p) for p in _paths):
            return True
    except Exception:
        pass
    try:
        import psutil as _ps
        for p in _ps.process_iter(["name"]):
            try:
                if "whatsapp" in (p.info.get("name") or "").lower():
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _send_whatsapp(receiver: str, message: str) -> str:
    _api = _try_whatsapp_api(receiver, message)
    if _api:
        return _api
    # ADDITIVE: app installed nahi (PWA/Web user) -> seedha Web flow, taaki
    # message galat window me type na ho. Purana desktop path installed par same.
    if not _is_whatsapp_installed():
        try:
            return _send_whatsapp_web(receiver, message)
        except Exception as e:
            return f"WhatsApp app nahi mila, Web fallback fail: {e}."
    _desk = _desktop_send("WhatsApp", receiver, message)
    if "Could not open" in _desk or "could not verify" in _desk:
        try:
            return _send_whatsapp_web(receiver, message)
        except Exception as e:
            return f"{_desk} (Web fallback bhi fail: {e})"
    return _desk

def _send_telegram(receiver: str, message: str) -> str:
    _api = _try_telegram_api(receiver, message)
    if _api:
        return _api

    clean_r = (receiver or "").lstrip("@").strip()
    # 1. First try direct Telegram protocol URL — opens exact contact chat without global search mistakes
    if clean_r:
        try:
            import os
            # If receiver is digits, use phone URL; otherwise use domain/username URL
            if clean_r.isdigit():
                _tg_link = f"tg://resolve?phone={clean_r}"
            else:
                _tg_link = f"tg://resolve?domain={clean_r}"
            os.system(f'start "" "{_tg_link}"')
            time.sleep(1.8)
            if message:
                _paste_text(message)
                time.sleep(0.3)
                pyautogui.press("enter")
                time.sleep(0.3)
            return f"Message sent to {receiver} via Telegram."
        except Exception as _e:
            print(f"[send_message] tg:// protocol note: {_e}")

    _desk = _desktop_send("Telegram", receiver, message)
    if "Could not open" in _desk or "not installed" in _desk:
        # Fallback to Telegram Web in default browser
        import urllib.parse
        tg_url = f"https://web.telegram.org/k/#?q={clean_r}"
        if _open_browser_url(tg_url):
            return f"Telegram Desktop app is PC par nahi mila — Telegram Web browser me khol diya gaya hai taaki aap {receiver} ko message bhej sakein."
        return f"Telegram app is computer par install ya open nahi ho paya."
    return _desk

def _send_signal(receiver: str, message: str) -> str:
    return _desktop_send("Signal", receiver, message)


def _send_discord(receiver: str, message: str) -> str:
    return _desktop_send("Discord", receiver, message)


def _send_instagram(receiver: str, message: str) -> str:
    _require_pyautogui()

    if not _open_browser_url("https://www.instagram.com/direct/new/"):
        return "Could not open Instagram in browser."

    _paste_text(receiver)
    time.sleep(1.5)

    pyautogui.press("down")
    time.sleep(0.3)
    pyautogui.press("enter")   
    time.sleep(0.4)

    for _ in range(4):
        pyautogui.press("tab")
        time.sleep(0.15)
    pyautogui.press("enter")
    time.sleep(2.0)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)

    return f"Message sent to {receiver} via Instagram."


def _send_messenger(receiver: str, message: str) -> str:
    _require_pyautogui()

    if not _open_browser_url("https://www.messenger.com/"):
        return "Could not open Messenger in browser."


    _search_in_app(receiver)
    time.sleep(0.5)
    pyautogui.press("down")
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(1.0)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)

    return f"Message sent to {receiver} via Messenger."

_PLATFORM_MAP = [
    ({"whatsapp", "wp", "wapp"},              _send_whatsapp),
    ({"telegram", "tg"},                      _send_telegram),
    ({"instagram", "ig", "insta"},            _send_instagram),
    ({"signal"},                               _send_signal),
    ({"discord"},                              _send_discord),
    ({"messenger", "facebook", "fb"},         _send_messenger),
]


def _resolve_platform(platform_str: str):
    key = platform_str.lower().strip()
    for keywords, handler in _PLATFORM_MAP:
        if any(k in key for k in keywords):
            return handler
    return lambda r, m: _desktop_send(platform_str.strip().title(), r, m)


def send_message(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params       = parameters or {}
    # ADDITIVE alias fix: edge_router 'contact'+'message' bhejta hai, LLM 'receiver'+'message_text'.
    # Dono accept karo (purana flow untouched) + contacts book resolve.
    receiver     = (params.get("receiver") or params.get("contact") or "").strip()
    message_text = (params.get("message_text") or params.get("message") or "").strip()
    platform     = (params.get("platform", "whatsapp") or "whatsapp").strip()
    try:
        from memory import contacts as _cb
        _hit = _cb.resolve_contact(receiver)
        if _hit.get("phone"):
            receiver = _hit["phone"]
    except Exception:
        pass

    if not receiver:
        return "Please specify a recipient."
    if not message_text:
        return "Please specify the message content."
    if not _PYAUTOGUI:
        return "PyAutoGUI is not installed — cannot control the desktop."

    preview = message_text[:50] + ("…" if len(message_text) > 50 else "")
    print(f"[SendMessage] 📨 {platform} → {receiver}: {preview}")
    if player:
        player.write_log(f"[msg] {platform} → {receiver}")

    try:
        handler = _resolve_platform(platform)
        result  = handler(receiver, message_text)
    except Exception as e:
        result = f"Could not send message: {e}"

    print(f"[SendMessage] {'✅' if 'sent' in result.lower() else '❌'} {result}")
    if player:
        player.write_log(f"[msg] {result}")

    return result


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "send_message",
    "description": "Sends a text message via WhatsApp, Telegram, or other messaging platform.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "receiver": {
                "type": "STRING",
                "description": "Recipient contact name"
            },
            "message_text": {
                "type": "STRING",
                "description": "The message to send"
            },
            "platform": {
                "type": "STRING",
                "description": "Platform: WhatsApp, Telegram, etc."
            }
        },
        "required": [
            "receiver",
            "message_text",
            "platform"
        ]
    },
    "handler": send_message,
}
