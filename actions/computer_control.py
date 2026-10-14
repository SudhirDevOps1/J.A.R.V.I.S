#computer_control.py
import io
import json
import platform
import re
import string
import subprocess
import sys

if platform.system() == "Windows":
    _WIN_HIDE: dict = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    _WIN_HIDE: dict = {}
import time
import random
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.05
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

# Truncation marker for long tool results. Was a literal ellipsis that
# had been corrupted to U+FFFD, which made these lines unmatchable by a
# text edit and rendered as garbage in a cp1252 console.
_TRUNC_MARK = '...'


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE         = _base_dir()
_CONFIG_PATH  = _BASE / "config" / "api_keys.json"
_MEMORY_PATH  = _BASE / "memory" / "long_term.json"

def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _platform_os() -> str:
    return {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}.get(
        platform.system(), "linux"
    )

def _get_os() -> str:
    return _load_config().get("os_system", _platform_os()).lower()


def _get_api_key() -> str:
    """Read the Gemini key the same way the rest of the app does.

    This used to read config/api_keys.json RAW, bypassing memory.config_manager
    .load_api_keys(). Once the secret vault is active the raw value is an
    'ENC(...)' Fernet blob, so genai.Client(api_key=...) received ciphertext and
    every LLM feature in this module failed with an opaque auth error.
    """
    try:
        from memory.config_manager import load_api_keys
        return (load_api_keys().get("gemini_api_key") or "").strip()
    except Exception:
        try:
            return str(_load_config().get("gemini_api_key") or "").strip()
        except Exception:
            return ""

_SAFE_SCREENSHOT_ROOTS = (
    Path.home(),
)

def _safe_screenshot_path(requested: str | None) -> Path:
    fallback = Path.home() / "Desktop" / "jarvis_screenshot.png"
    if not requested:
        return fallback
    try:
        p = Path(requested).expanduser().resolve()
        for root in _SAFE_SCREENSHOT_ROOTS:
            if p.is_relative_to(root.resolve()):
                p.parent.mkdir(parents=True, exist_ok=True)
                return p
    except Exception:
        pass
    return fallback

def _require_pyautogui():
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI not installed. Run: pip install pyautogui")

_FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Drew", "Quinn",
    "Avery", "Blake", "Cameron", "Dakota", "Emerson", "Finley", "Harper",
]
_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson",
]
_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "proton.me", "mail.com"]


def _random_data(data_type: str) -> str:
    dt = data_type.lower().strip()

    if dt == "first_name":
        return random.choice(_FIRST_NAMES)

    if dt == "last_name":
        return random.choice(_LAST_NAMES)

    if dt == "name":
        return f"{random.choice(_FIRST_NAMES)} {random.choice(_LAST_NAMES)}"

    if dt == "email":
        first = random.choice(_FIRST_NAMES).lower()
        last  = random.choice(_LAST_NAMES).lower()
        num   = random.randint(10, 999)
        return f"{first}.{last}{num}@{random.choice(_DOMAINS)}"

    if dt == "username":
        return f"{random.choice(_FIRST_NAMES).lower()}{random.randint(100, 9999)}"

    if dt == "password":
        chars = string.ascii_letters + string.digits + "!@#$%"
        raw   = (
            random.choice(string.ascii_uppercase)
            + random.choice(string.digits)
            + random.choice("!@#$%")
            + "".join(random.choices(chars, k=9))
        )
        return "".join(random.sample(raw, len(raw)))

    if dt == "phone":
        return f"+1{random.randint(200,999)}{random.randint(1_000_000, 9_999_999)}"

    if dt == "birthday":
        y = random.randint(1980, 2000)
        m = random.randint(1, 12)
        d = random.randint(1, 28)
        return f"{m:02d}/{d:02d}/{y}"

    if dt == "address":
        num    = random.randint(100, 9999)
        street = random.choice(["Main St", "Oak Ave", "Park Blvd", "Elm St", "Cedar Ln"])
        return f"{num} {street}"

    if dt == "zip_code":
        return str(random.randint(10000, 99999))

    if dt == "city":
        return random.choice(["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"])

    return f"random_{data_type}_{random.randint(1000, 9999)}"

def _user_profile() -> dict:
    """Read identity fields from long-term memory."""
    try:
        if _MEMORY_PATH.exists():
            data     = json.loads(_MEMORY_PATH.read_text(encoding="utf-8"))
            identity = data.get("identity", {})
            return {k: v.get("value", "") for k, v in identity.items()}
    except Exception:
        pass
    return {}

def _type(text: str, interval: float = 0.03) -> str:
    _require_pyautogui()
    av = _verifier()
    # No screen hash needed: typing is verified by reading the focused
    # control back, which is stronger and cheaper than comparing pixels.
    before = av.snapshot(include_screen=False) if av else None

    time.sleep(0.3)
    pyautogui.typewrite(text, interval=interval)
    msg = f"Typed: {text[:60]}{_TRUNC_MARK}{'...' if len(text) > 60 else ''}"

    # Read the focused control back and check the text actually arrived.
    # This is the check that would have caught the original Notepad bug,
    # where nothing was typed and the task was still reported complete.
    verification = av.verify_typed(before, text) if av and before else None
    return _verified(msg, verification)


def _smart_type(text: str, clear_first: bool = True) -> str:
    _require_pyautogui()
    if clear_first:
        _clear_field()
        time.sleep(0.1)

    if len(text) > 20 and _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.1)
        paste_key = "command" if _get_os() == "mac" else "ctrl"
        pyautogui.hotkey(paste_key, "v")
        return f"Smart-typed (clipboard): {text[:60]}{'…' if len(text) > 60 else ''}"

    pyautogui.typewrite(text, interval=0.04)
    return f"Smart-typed: {text[:60]}{'…' if len(text) > 60 else ''}"


def _verifier():
    """The verification layer, or None where it is unavailable.

    Imported lazily so a machine without pywinauto or Pillow still gets a
    working computer_control, just one that cannot prove anything.
    """
    try:
        from core import action_verifier
        return action_verifier
    except Exception as e:
        print(f"[ComputerControl] verifier unavailable: {e}")
        return None


def _verified(result: str, verification) -> str:
    """Attach the truth to what the user is told.

    An action reported as successful without proof is exactly the bug this
    project shipped four times, so the result string now carries which of the
    three states it ended in. Additive: a caller that only reads the original
    text is unaffected, and nothing is removed.
    """
    if verification is None:
        return result
    try:
        return f"{result}{verification.suffix()}"
    except Exception:
        return result


def _wait_until_action(params: dict) -> str:
    """Block until a condition holds, instead of guessing how long to sleep."""
    av = _verifier()
    if av is None:
        return "Cannot wait for a condition: the verification layer is unavailable."

    timeout = float(params.get("timeout", 10.0))
    timeout = min(max(timeout, 0.1), 120.0)
    kind = (params.get("for") or params.get("condition") or "").strip().lower()
    value = str(params.get("value") or params.get("target") or "").strip()

    if not value:
        return ("Kis cheez ka wait karna hai? Batao, jaise: "
                "'wait until a window Notepad appears' ya "
                "'wait until file C:/temp/a.txt exists'.")

    if kind in ("window", "app", "window_title"):
        v = av.wait_for_window(value, timeout=timeout)
    elif kind in ("process",):
        v = av.wait_for_process(value, timeout=timeout)
    elif kind in ("file", "path"):
        v = av.wait_for_file(value, timeout=timeout)
    elif kind in ("screen", "text", "visible"):
        # LOCAL OCR only.
        #
        # This deliberately does not call _screen_find(). That uploads the
        # entire screen to a cloud model, and the whole reason wait_until exists
        # is that it is cheap enough to actually run in a loop - a cloud round
        # trip per poll would be seconds and money per attempt, and it would
        # ship the user's screen to a third party on every single poll.
        # Cloud vision stays behind the explicit visual_verify action.
        def _visible() -> bool:
            try:
                from actions.ocr_tools import _screen_ocr
                return value.lower() in str(_screen_ocr()).lower()
            except Exception:
                return False
        v = av.wait_until(_visible, timeout=timeout,
                          description=f"{value!r} readable on screen by local OCR")
    else:
        return (f"Samajh nahi aaya '{kind or '(missing)'} kis cheez ka wait karna hai. "
                f"Use for='window' | 'process' | 'file' | 'screen'.")

    mark = {"ok": "✓", "failed": "✗", "unknown": "?"}.get(v.state, "?")
    return f"{mark} wait_until({kind or '?'}={value!r}): {v.evidence}"


# Depth guard for retry-in-retry. The explicit check on `inner` above is the
# real fix; this is the belt to its braces, so a future action that happens to
# route back here cannot build an unbounded loop either.
_RETRY_DEPTH = 0


def _retry_action(params: dict) -> str:
    global _RETRY_DEPTH
    av = _verifier()
    if av is None:
        return "Cannot retry with verification: the verification layer is unavailable."

    # The inner action is read from `do`, NOT from `action`. Reading it from
    # `action` made the feature impossible to use: `action` is by definition
    # the key that selected `retry` in the first place, so it could only ever
    # read back "retry" and refuse. Caught by running it rather than reading it.
    #
    #   {'action': 'retry', 'do': 'click', 'x': 100, 'y': 200, 'attempts': 3}
    inner = str(params.get("do") or params.get("retry_action") or "").strip()
    if not inner:
        return ("Kis action ko retry karoon? 'retry' ke saath 'do' do, jaise: "
                "{'action':'retry', 'do':'click', 'x':100, 'y':200}")

    # A retry must wrap a real action, never itself.
    #
    # Found by running it: retry(action='retry') re-entered this function with
    # the same arguments and recursed until the interpreter gave up with
    # "maximum recursion depth exceeded". The inner action is read straight off
    # params, so nothing stopped it being its own name.
    if inner in ("retry", "wait_until"):
        return ("'retry' aur 'wait_until' dobara retry nahi ho sakte - "
                "retry ke andar ek asli action do jaise 'click', 'press' "
                "ya 'hotkey'.")
    if _RETRY_DEPTH >= 2:
        return "Nested retry ke andar retry nahi karunga. Seedha action do."

    attempts = int(params.get("attempts", 3))
    attempts = min(max(attempts, 1), 5)
    delay = float(params.get("delay", 0.4))

    # Re-enter the public handler for the inner action rather than duplicating
    # the dispatch logic, which would be a second thing to keep in sync.
    def _run(_n: int) -> str:
        return computer_control({
            "action": inner,
            **{k: v for k, v in params.items()
               if k not in ("action", "do", "retry_action", "attempts",
                            "delay", "timeout")},
        })

    before = av.snapshot()
    _RETRY_DEPTH += 1
    try:
        result, verdict = av.with_retry(
            _run,
            lambda r: av.verify_press(before, inner),
            attempts=attempts,
            delay=delay,
        )
    finally:
        _RETRY_DEPTH -= 1
    mark = {"ok": "✓", "failed": "✗", "unknown": "?"}.get(verdict.state, "?")
    return (f"{mark} retried '{inner}' up to {attempts}x: {verdict.evidence}. "
            f"Last result: {result}")


def _click(x=None, y=None, button: str = "left", clicks: int = 1) -> str:
    _require_pyautogui()
    av = _verifier()
    before = av.snapshot() if av else None

    # UIA pre-flight. If the accessibility tree knows which element owns these
    # coordinates, invoke that element rather than replaying mouse events at a
    # fixed point - which lands on something else entirely if the window moved
    # since the screen was last looked at, and still reports success.
    invoked = None
    if av and x is not None and y is not None and button == "left" and clicks == 1:
        try:
            invoked = av.invoke_at(int(x), int(y))
        except Exception:
            invoked = None

    if invoked:
        msg = f"Clicked ({x}, {y}) [{button}]"
    else:
        if x is not None and y is not None:
            pyautogui.click(x, y, button=button, clicks=clicks)
            msg = f"{'Double-c' if clicks == 2 else 'C'}licked ({x}, {y}) [{button}]"
        else:
            pyautogui.click(button=button, clicks=clicks)
            msg = f"Clicked at current position [{button}]"

    verification = av.verify_click(before, x, y) if av and before else None
    return _verified(msg, verification)


def _hotkey(*keys) -> str:
    _require_pyautogui()
    pyautogui.hotkey(*keys)
    return f"Hotkey: {'+'.join(keys)}"


def _press(key: str) -> str:
    _require_pyautogui()
    pyautogui.press(key)
    return f"Pressed: {key}"


def _scroll(direction: str = "down", amount: int = 3) -> str:
    _require_pyautogui()
    vertical   = direction in ("up", "down")
    clicks     = amount if direction in ("up", "right") else -amount
    pyautogui.scroll(clicks) if vertical else pyautogui.hscroll(clicks)
    return f"Scrolled {direction} ×{amount}"


def _move(x: int, y: int, duration: float = 0.3) -> str:
    _require_pyautogui()
    pyautogui.moveTo(x, y, duration=duration)
    return f"Mouse → ({x}, {y})"


def _drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> str:
    _require_pyautogui()
    pyautogui.moveTo(x1, y1, duration=0.2)
    pyautogui.dragTo(x2, y2, duration=duration, button="left")
    return f"Dragged ({x1},{y1}) → ({x2},{y2})"


def _clipboard_get() -> str:
    if _PYPERCLIP:
        return pyperclip.paste()
    _hotkey("ctrl", "c")
    time.sleep(0.2)
    return "(copied — pyperclip unavailable for read)"


def _clipboard_paste(text: str) -> str:
    if _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.1)
        _require_pyautogui()
        paste_key = "command" if _get_os() == "mac" else "ctrl"
        pyautogui.hotkey(paste_key, "v")
        return f"Pasted: {text[:60]}{'…' if len(text) > 60 else ''}"
    return "pyperclip not available"


def _privacy_allows_capture(is_stream: bool = False):
    """(allowed, reason) from the Zero-Trust privacy shield, FAIL CLOSED.

    This module captures the whole screen and — in _screen_find — uploads it to
    a cloud model. It previously had NO privacy check at all, so the shield that
    protects screen_processor / screen_timeline / screen_troubleshooter did not
    apply here. If the guard itself errors we deny, never allow.
    """
    try:
        from core.privacy_guard import is_screen_capture_allowed
        return is_screen_capture_allowed(is_stream=is_stream)
    except Exception as e:
        return False, f"Privacy guard unavailable ({e})"


def _screenshot(save_path: str | None = None) -> str:
    _require_pyautogui()
    allowed, reason = _privacy_allows_capture()
    if not allowed:
        return (f"🛡️ Screenshot blocked by Privacy Shield — {reason}. "
                "Say 'privacy mode off' if you really want this.")
    path = _safe_screenshot_path(save_path)
    img  = pyautogui.screenshot()
    img.save(str(path))
    return f"Screenshot saved: {path}"


def _clear_field() -> str:
    _require_pyautogui()
    select_key = "command" if _get_os() == "mac" else "ctrl"
    pyautogui.hotkey(select_key, "a")
    time.sleep(0.1)
    pyautogui.press("delete")
    return "Field cleared"

def _focus_window(title: str) -> str:
    os_name = _get_os()

    if os_name == "windows":
        try:
            script = f'(New-Object -ComObject WScript.Shell).AppActivate("{title}")'
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, timeout=5, **_WIN_HIDE,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except Exception as e:
            return f"focus_window (Windows) failed: {e}"

    if os_name == "mac":
        script = (
            f'tell application "System Events" to '
            f'set frontmost of (first process whose name contains "{title}") to true'
        )
        try:
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, timeout=5,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except Exception as e:
            return f"focus_window (macOS) failed: {e}"

    if os_name == "linux":
        try:
            result = subprocess.run(
                ["wmctrl", "-a", title],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                time.sleep(0.3)
                return f"Focused window: {title}"
        except FileNotFoundError:
            pass
        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", title, "windowactivate"],
                capture_output=True, timeout=5,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except FileNotFoundError:
            return "focus_window (Linux) requires wmctrl or xdotool"
        except Exception as e:
            return f"focus_window (Linux) failed: {e}"

    return f"focus_window: unknown OS '{os_name}'"

def _screen_find(description: str) -> tuple[int, int] | None:
    # Privacy shield BEFORE anything else: this function captures the entire
    # screen and uploads it to a cloud model. It had no guard at all, so banking
    # / password-manager / private-chat screens were being sent off-device even
    # while Privacy Mode was ON.
    _ok, _why = _privacy_allows_capture()
    if not _ok:
        print(f"[ComputerControl] 🛡️  screen_find blocked: {_why}")
        return None

    api_key = _get_api_key()
    if not api_key:
        print("[ComputerControl] ⚠️ No API key for screen_find")
        return None

    try:
        from google import genai
        from google.genai import types as gtypes

        _require_pyautogui()
        w, h  = pyautogui.size()
        img   = pyautogui.screenshot()
        buf   = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        client = genai.Client(api_key=api_key)
        prompt = (
            f"This is a screenshot of a {w}×{h} pixel screen. "
            f"Locate the UI element described as: '{description}'. "
            f"Reply with ONLY the center coordinates as: x,y "
            f"If the element is not visible, reply: NOT_FOUND"
        )

        models_to_try = [
            "gemini-2.0-flash",
            "gemini-2.5-flash",
            "gemini-flash-lite-latest",
            "gemini-flash-latest",
        ]
        text = ""
        for m in models_to_try:
            try:
                response = client.models.generate_content(
                    model=m,
                    contents=[
                        gtypes.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                        prompt,
                    ],
                )
                if response and response.text:
                    text = response.text.strip()
                    break
            except Exception:
                continue

        if not text or "NOT_FOUND" in text.upper():
            return None

        match = re.search(r"(\d+)\s*,\s*(\d+)", text)
        if match:
            return int(match.group(1)), int(match.group(2))

    except Exception as e:
        print(f"[ComputerControl] ⚠️ screen_find failed: {e}")

    return None

def computer_control(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    Dispatch table for all computer control actions.

    parameters keys (all optional unless noted):
      action        : (required) one of the actions listed below
      text          : text to type or paste
      x, y          : screen coordinates
      button        : 'left' | 'right' (default: left)
      keys          : hotkey string, e.g. 'ctrl+c'
      key           : single key name, e.g. 'enter'
      direction     : 'up' | 'down' | 'left' | 'right'
      amount        : scroll amount (default: 3)
      seconds       : wait duration
      title         : window title fragment for focus_window
      description   : natural-language element description for screen_find/click
      type          : data type for random_data
      field         : memory field name for user_data
      clear_first   : bool, clear field before typing (default: true)
      path          : save path for screenshot (must be inside home dir)

    Actions:
      type          — type text at cursor
      smart_type    — clear field + type (clipboard-backed)
      click         — left click
      double_click  — double left click
      right_click   — right click
      move          — move mouse
      drag          — click-drag between two points
      hotkey        — key combination
      press         — single key
      scroll        — scroll the wheel
      copy          — read clipboard
      paste         — write + paste clipboard
      screenshot    — capture screen (safe path only)
      wait          — sleep N seconds
      clear_field   — select-all + delete
      focus_window  — bring window to foreground
      screen_find   — AI element finder (returns x,y)
      screen_click  — AI element finder + click
      random_data   — generate fake form data
      user_data     — pull real data from memory
    """
    params = parameters or {}
    action = params.get("action", "").lower().strip()

    if not action:
        return "No action specified for computer_control."

    if player:
        player.write_log(f"[Computer] {action}")

    print(f"[ComputerControl] ▶ {action}  {params}")

    try:

        if action == "type":
            return _type(params.get("text", ""))

        if action == "smart_type":
            return _smart_type(
                params.get("text", ""),
                clear_first=params.get("clear_first", True),
            )

        if action in ("click", "left_click"):
            return _click(params.get("x"), params.get("y"), "left", 1)

        if action == "double_click":
            return _click(params.get("x"), params.get("y"), "left", 2)

        if action == "right_click":
            return _click(params.get("x"), params.get("y"), "right", 1)

        if action == "move":
            return _move(int(params.get("x", 0)), int(params.get("y", 0)))

        if action == "drag":
            return _drag(
                int(params.get("x1", 0)), int(params.get("y1", 0)),
                int(params.get("x2", 0)), int(params.get("y2", 0)),
            )

        if action == "hotkey":
            raw  = params.get("keys", "")
            keys = [k.strip() for k in raw.split("+")] if isinstance(raw, str) else raw
            return _hotkey(*keys)

        if action == "press":
            return _press(params.get("key", "enter"))

        if action == "scroll":
            return _scroll(
                direction=params.get("direction", "down"),
                amount=int(params.get("amount", 3)),
            )

        if action == "copy":
            return _clipboard_get()

        if action == "paste":
            return _clipboard_paste(params.get("text", ""))

        if action == "screenshot":
            return _screenshot(params.get("path"))

        if action == "screen_find":
            coords = _screen_find(params.get("description", ""))
            return f"{coords[0]},{coords[1]}" if coords else "NOT_FOUND"

        if action == "screen_click":
            desc   = params.get("description", "")
            coords = _screen_find(desc)
            if coords:
                time.sleep(0.2)
                _click(x=coords[0], y=coords[1])
                return f"Clicked '{desc}' at {coords}"
            return f"Element not found on screen: '{desc}'"

        if action in ("visual_solve_error", "heal_error", "dismiss_popup"):
            from actions.visual_agent import _capture_screen_frame, _detect_and_solve_error
            img_b, _ = _capture_screen_frame()
            res = _detect_and_solve_error(img_b, player=player)
            return res or "No blocking error dialog or modal popup detected on screen."

        if action == "visual_verify":
            # This action existed and nothing ever called it - it was reachable
            # from the tool enum and dead everywhere else. Now it is the
            # explicit, opt-in escalation path: use this ONLY when the cheap
            # local checks cannot tell you anything.
            #
            # It uploads the entire screen to a cloud model, so it is slow,
            # costs money, and is refused on privacy-sensitive windows by the
            # guard inside _screen_find. That is why the verifier never calls
            # it: verification must be cheap enough that it actually happens.
            desc = str(params.get("description") or params.get("target") or "").strip()
            if not desc:
                return ("Kya verify karna hai? 'description' do, jaise "
                        "'Save button dikh raha hai'.")
            coords = _screen_find(desc)
            if coords:
                return (f"✓ Verified: '{desc}' is visible on screen at {coords} "
                        f"(cloud vision check).")
            return (f"✗ Not verified: '{desc}' was not found on screen "
                    f"(cloud vision check). It may still be present but "
                    f"unrecognised, or genuinely absent.")

        if action == "wait":
            secs = float(params.get("seconds", 1.0))
            secs = min(secs, 30.0)
            time.sleep(secs)
            return f"Waited {secs}s"

        # ADDITIVE: wait for a CONDITION instead of sleeping a hopeful fixed
        # amount. The documented failure mode of GUI automation is a window
        # that is detected and then gone a few milliseconds later, and
        # time.sleep() is exactly the wrong tool for that: it returns before
        # the thing happened on a slow machine, and wastes seconds on a fast
        # one.
        if action == "wait_until":
            return _wait_until_action(params)

        # ADDITIVE: retry an action until it is verified. Retries only on a
        # proven failure - never on 'unknown', because firing the same
        # keystrokes again at something that may already have worked is how a
        # half-typed field becomes a double-typed one.
        if action == "retry":
            return _retry_action(params)

        # ADDITIVE: what this machine can actually verify, so the assistant can
        # be honest about its own limits instead of implying it can check
        # everything.
        if action == "capabilities":
            av = _verifier()
            if av is None:
                return "Verification layer unavailable: no local proof of any action."
            caps = av.capabilities()
            enabled = [k for k, v in caps.items() if v is True and k != "cloud_vision_used"]
            return (
                "Verification capabilities: "
                + (", ".join(enabled) if enabled else "none")
                + ". Cloud vision is deliberately never used for verification "
                  "(it uploads the screen and is slow)."
            )

        if action == "clear_field":
            return _clear_field()

        if action == "focus_window":
            return _focus_window(params.get("title", ""))

        if action == "random_data":
            dt     = params.get("type", "name")
            result = _random_data(dt)
            print(f"[ComputerControl] 🎲 random {dt} → {result}")
            return result

        if action == "user_data":
            field   = params.get("field", "name")
            profile = _user_profile()
            value   = profile.get(field, "")
            if not value:
                value = _random_data(field)
                print(f"[ComputerControl] ⚠️ No '{field}' in memory, using random: {value}")
            return value

        if action == "clear_log":
            if player:
                try:
                    if hasattr(player, "_quick_clear_log"):
                        player._quick_clear_log()
                    elif hasattr(player, "_win") and hasattr(player._win, "_quick_clear_log"):
                        player._win._quick_clear_log()
                except Exception:
                    pass
            return "Activity log cleared."

        return f"Unknown action: '{action}'"

    except Exception as e:
        print(f"[ComputerControl] ❌ {action}: {e}")
        return f"computer_control '{action}' failed: {e}"


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "computer_control",
    "description": (
        "Direct MOUSE and KEYBOARD control of the desktop: type text, click at "
        "coordinates, press hotkeys, scroll, move the mouse, take a screenshot, or "
        "find an on-screen element by describing it and click it.\n"
        "USE FOR: 'type karo ...', 'mouse move karo', 'ctrl+s dabao', 'screenshot "
        "lo', 'save button pe click karo', 'screen par X dhoondh kar click karo'.\n"
        "DO NOT USE FOR: launching or closing apps (use open_app — far more "
        "reliable than simulating clicks), window management (use window_tools), "
        "or semantic UI element access on Windows (use uia_controller, which does not "
        "need coordinates).\n"
        "Prefer a purpose-built tool over blind clicking whenever one exists."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | wait_until | retry | capabilities | clear_field | focus_window | screen_find | screen_click | visual_solve_error | visual_verify | random_data | user_data"
            },
            "for": {
                "type": "STRING",
                "description": (
                    "For wait_until: what to wait for - window | process | "
                    "file | screen"
                )
            },
            "value": {
                "type": "STRING",
                "description": (
                    "For wait_until: the title / process name / file path / "
                    "on-screen text to wait for"
                )
            },
            "timeout": {
                "type": "NUMBER",
                "description": "For wait_until: seconds to keep trying (default 10)"
            },
            "attempts": {
                "type": "INTEGER",
                "description": "For retry: how many attempts (default 3, max 5)"
            },
            "do": {
                "type": "STRING",
                "description": (
                    "For retry: the action to actually run and verify, e.g. "
                    "'click'. Never 'retry' itself."
                )
            },
            "delay": {
                "type": "NUMBER",
                "description": "For retry: seconds before the second attempt (default 0.4)"
            },
            "text": {
                "type": "STRING",
                "description": "Text to type or paste"
            },
            "x": {
                "type": "INTEGER",
                "description": "X coordinate"
            },
            "y": {
                "type": "INTEGER",
                "description": "Y coordinate"
            },
            "keys": {
                "type": "STRING",
                "description": "Key combination e.g. 'ctrl+c'"
            },
            "key": {
                "type": "STRING",
                "description": "Single key e.g. 'enter'"
            },
            "direction": {
                "type": "STRING",
                "description": "up | down | left | right"
            },
            "amount": {
                "type": "INTEGER",
                "description": "Scroll amount (default: 3)"
            },
            "seconds": {
                "type": "NUMBER",
                "description": "Seconds to wait"
            },
            "title": {
                "type": "STRING",
                "description": "Window title for focus_window"
            },
            "description": {
                "type": "STRING",
                "description": "Element description for screen_find/screen_click"
            },
            "type": {
                "type": "STRING",
                "description": "Data type for random_data"
            },
            "field": {
                "type": "STRING",
                "description": "Field for user_data: name|email|city"
            },
            "clear_first": {
                "type": "BOOLEAN",
                "description": "Clear field before typing (default: true)"
            },
            "path": {
                "type": "STRING",
                "description": "Save path for screenshot"
            }
        },
        "required": [
            "action"
        ]
    },
    "handler": computer_control,
}
