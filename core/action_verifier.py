"""
core/action_verifier.py - Prove that an action actually happened.

WHY THIS EXISTS
---------------
Four separate bugs on this project, found on the user's own machine, all had
the same shape:

    _process_appeared   -> "Opened Notepad."        nothing opened
    todo_agent          -> "completed successfully"  every step refused
    _launch_linux       -> "Opened Telegram."        returncode discarded
    open_app verifier   -> "Opened Notepad."        empty process name matched

Every one reported success without checking. That is not four coincidences,
it is a missing layer, and this is that layer.

THE COST CONSTRAINT
------------------
Verification has to be cheap or it will not get used. computer_control's
_screen_find() already exists and is a terrible thing to put in this path: it
captures the entire screen and uploads it to a cloud model, which costs a
second of latency, costs money, and hands the contents of the user's screen to
a third party. It also has a privacy guard that blocks banking and password
manager windows, so on exactly the screens where verification would matter most
it refuses to run.

So the ladder here is local and cheap, cheapest first:

    1. window state      GetForegroundWindow + title      free
    2. structured state  UI Automation via pywinauto     milliseconds
    3. pixel state       downsampled local screenshot    milliseconds, stays local
    4. (never) a cloud vision round trip

THE THREE-STATE ANSWER
----------------------
Verification returns OK, FAILED, or UNKNOWN - never a bare bool.

UNKNOWN is the important one. It means "this machine could not tell". A system
that collapses unknown into failed refuses to act; a system that collapses it
into ok is the bug factory this module was written to end. The caller gets to
decide, with the truth in hand.

Nothing here raises. Verification failing must never be the reason an action
fails, or the assistant becomes less capable than it was before.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
import platform
import time
from typing import Any, Callable, NamedTuple, Optional

_IS_WINDOWS = platform.system() == "Windows"

try:
    import psutil as _ps
    _HAS_PSUTIL = True
except Exception:
    _HAS_PSUTIL = False

try:
    from PIL import Image as _Image
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False

try:
    import pyautogui as _pg
    _HAS_PYAUTOGUI = True
except Exception:
    _HAS_PYAUTOGUI = False

try:
    from pywinauto import Desktop as _UiaDesktop
    from pywinauto.timings import Timings as _Timings
    _HAS_UIA = True
except Exception:
    _HAS_UIA = False


# ── results ─────────────────────────────────────────────────────────────────

OK = "ok"
FAILED = "failed"
UNKNOWN = "unknown"


class Verification(NamedTuple):
    state: str                      # OK | FAILED | UNKNOWN
    evidence: str = ""              # what was observed, in plain words
    detail: Optional[dict] = None   # structured extras

    @property
    def ok(self) -> bool:
        return self.state == OK

    @property
    def verified(self) -> bool:
        """True only when something actually confirmed it.

        False for UNKNOWN as well as FAILED. A caller that wants certainty
        must not be handed an unverified claim dressed as a verified one."""
        return self.state == OK

    def suffix(self) -> str:
        """Text for a tool result, so the user is told what really happened."""
        if self.state == OK:
            return f" [verified: {self.evidence}]" if self.evidence else ""
        if self.state == FAILED:
            return f" [NOT VERIFIED: {self.evidence}]"
        return f" [unverified: {self.evidence}]" if self.evidence else " [unverified]"


def _unknown(why: str, detail: dict | None = None) -> Verification:
    return Verification(UNKNOWN, why, detail)


# ── 1. window state (free) ──────────────────────────────────────────────────

def _fg_hwnd() -> int:
    if not _IS_WINDOWS:
        return 0
    try:
        return int(ctypes.windll.user32.GetForegroundWindow())
    except Exception:
        return 0


def _window_title(hwnd: int) -> str:
    if not hwnd:
        return ""
    try:
        if _IS_WINDOWS:
            n = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, n + 1)
            return buf.value.strip()
        if _HAS_PSUTIL:
            return ""
    except Exception:
        pass
    return ""


class Snapshot(NamedTuple):
    """State before an action, so 'after' can be compared against it."""
    fg_hwnd: int
    fg_title: str
    pid_count: int
    focus_signature: str
    screen_hash: str


def snapshot(include_screen: bool = True) -> Snapshot:
    """Cheap picture of the machine right now. Never raises."""
    try:
        fg = _fg_hwnd()
        return Snapshot(
            fg_hwnd=fg,
            fg_title=_window_title(fg),
            pid_count=len(_ps.pids()) if _HAS_PSUTIL else 0,
            focus_signature=_focus_signature(),
            screen_hash=_screen_hash() if include_screen else "",
        )
    except Exception:
        # An unusable snapshot must not stop the action. Unknown state is still
        # better than no action at all.
        return Snapshot(0, "", 0, "", "")


def _focus_signature() -> str:
    """Identifies the element that has keyboard focus, without reading its text.

    The signature is deliberately the element's identity, not its contents, so
    a snapshot taken before typing and one taken after can show that focus
    stayed put without the snapshot itself holding whatever is being typed.
    """
    if not _IS_WINDOWS or not _HAS_UIA:
        return ""
    try:
        _Timings.window_find_timeout = 0.4
        el = _UiaDesktop(backend="uia").get_focus()
        if el is None:
            return ""
        try:
            return f"{el.element_info.control_type}|{el.window_text()[:60]}"
        except Exception:
            return f"{getattr(el.element_info, 'control_type', '?')}|"
    except Exception:
        return ""


def _screen_hash(region: tuple | None = None) -> str:
    """Hash of a downsampled local screenshot.

    Downsampled hard, on purpose. The question is only 'did anything on screen
    change', and a 64x36 thumbnail answers that for a fraction of the
    bandwidth - and without ever leaving the machine.
    """
    if not (_HAS_PYAUTOGUI and _HAS_PIL):
        return ""
    try:
        img = _pg.screenshot(region=region) if region else _pg.screenshot()
        small = img.resize((64, 36), _Image.Resampling.BILINEAR)
        return hashlib.sha1(small.tobytes()).hexdigest()[:16]
    except Exception:
        return ""


# ── 2. structured state (UI Automation) ─────────────────────────────────────

def _uia_desktop():
    if not (_IS_WINDOWS and _HAS_UIA):
        return None
    try:
        _Timings.window_find_timeout = 0.5
        return _UiaDesktop(backend="uia")
    except Exception:
        return None


def invoke_at(x: int, y: int) -> Optional[str]:
    """Press the element at these coordinates through UI Automation.

    Returns a short description of what was invoked, or None to tell the
    caller to fall back to a plain coordinate click.

    WHY THIS IS WORTH THE CODE
    ---------------------------
    A coordinate click replays mouse events at a fixed point. If the window
    moved, was resized, or another window took that space since the screen was
    last looked at, the click lands on something else entirely - and reports
    success. Asking the accessibility tree which element owns those
    coordinates, and invoking that element directly, removes the guess entirely
    for anything that supports Invoke.

    Only for click-like controls. Buttons, menu items, checkboxes and tabs have
    an Invoke pattern that means "activate me"; clicking a text field through
    Invoke would be meaningless, so those deliberately fall back.
    """
    if not (_IS_WINDOWS and _HAS_UIA):
        return None
    desk = _uia_desktop()
    if desk is None:
        return None
    try:
        spec = desk.from_point(int(x), int(y))
    except Exception:
        return None
    if spec is None:
        return None

    try:
        ctype = str(spec.element_info.control_type or "")
    except Exception:
        return None

    if ctype not in ("Button", "MenuItem", "CheckBox", "RadioButton",
                     "TabItem", "TreeItem", "ListItem", "Hyperlink"):
        return None

    try:
        spec.invoke()
        label = ""
        try:
            label = (spec.window_text() or "")[:60]
        except Exception:
            pass
        return f"UIA invoked {ctype} {label!r}".strip()
    except Exception:
        # No Invoke pattern, or it was refused. Fall back rather than fail.
        return None


def read_focused_text() -> Optional[str]:
    """The text currently in the focused control, or None if unknowable.

    This is the strong verification for typing: read back what the application
    actually received instead of assuming the keystrokes arrived.
    """
    if not (_IS_WINDOWS and _HAS_UIA):
        return None
    desk = _uia_desktop()
    if desk is None:
        return None
    try:
        el = desk.get_focus()
        if el is None:
            return None
        for getter in ("get_value", "window_text"):
            try:
                val = getattr(el, getter)()
                if isinstance(val, str) and val.strip():
                    return val
            except Exception:
                continue
        try:
            return el.iface_text.GetDocumentRange(-1).GetText(-1)
        except Exception:
            return None
    except Exception:
        return None


def element_from_point(x: int, y: int) -> Optional[dict]:
    """What is at these coordinates, per UI Automation.

    Lets a blind coordinate click be upgraded to a targeted one: if the element
    under the point supports Invoke, that is far more reliable than replaying
    mouse events at coordinates that may belong to a window that has since
    moved.
    """
    if not (_IS_WINDOWS and _HAS_UIA):
        return None
    try:
        from pywinauto import mouse
        el = mouse.element_from_point(x, y) if hasattr(mouse, "element_from_point") else None
    except Exception:
        el = None
    desk = _uia_desktop()
    if el is None and desk is not None:
        try:
            from pywinauto import mouse as _mouse
            el = _mouse.click(coords=(x, y))
        except Exception:
            el = None
    if el is None:
        return None
    try:
        info = el.element_info
        return {
            "control_type": str(getattr(info, "control_type", "") or ""),
            "name": str(getattr(info, "name", "") or "")[:120],
            "automation_id": str(getattr(info, "automation_id", "") or "")[:120],
            "rect": str(getattr(info, "rectangle", "") or ""),
            "can_invoke": hasattr(el, "invoke"),
        }
    except Exception:
        return None


# ── 3. action verification ──────────────────────────────────────────────────

def verify_click(before: Snapshot, x: Optional[int] = None,
                 y: Optional[int] = None) -> Verification:
    """Did the click change anything at all?

    A click that lands on a button, a menu, or nothing produces identical
    results from the keyboard's point of view, so this cannot promise the
    button was pressed. It CAN prove the screen moved, which is the difference
    between 'something happened' and 'nothing happened'.
    """
    if not (_HAS_PYAUTOGUI and _HAS_PIL):
        return _unknown("no screen capture available")
    after = _screen_hash()
    if not before.screen_hash or not after:
        return _unknown("no baseline screen hash")
    if after != before.screen_hash:
        return Verification(OK, "screen changed after the click",
                            {"changed": True})

    # Identical screen: either the click missed, or it hit something inert.
    # Windows that moved count - a new foreground window is real progress.
    fg = _fg_hwnd()
    if fg and fg != before.fg_hwnd:
        return Verification(OK, f"foreground window changed to {_window_title(fg)!r}",
                            {"changed": True, "fg": _window_title(fg)})
    if _HAS_PSUTIL and before.pid_count and len(_ps.pids()) > before.pid_count:
        return Verification(OK, "a new process appeared", {"changed": True})

    return Verification(FAILED, "nothing on screen changed after the click",
                        {"changed": False})


def verify_typed(before: Snapshot, text: str) -> Verification:
    """Read the focused control back and check the text actually arrived.

    The strongest check available here, and entirely local. If the application
    received the keystrokes, the text is in its control; if not, it is not.
    """
    expected = (text or "").strip()
    if not expected:
        return _unknown("nothing was typed")

    got = read_focused_text()
    if got is None:
        # No UIA, or the focused control does not expose its text. Fall back to
        # whether anything moved at all, and be honest that it is weaker.
        after = _screen_hash()
        if before.screen_hash and after and after != before.screen_hash:
            return Verification(UNKNOWN,
                                "screen changed but the control's text could not be read back",
                                {"changed": True})
        return _unknown("could not read the focused control's text")

    tail = expected[-40:]
    if tail and tail in got:
        return Verification(OK, f"the focused control now contains the typed text",
                            {"read_back": True})
    return Verification(FAILED,
                        f"typed text is not in the focused control (read {got[-60:]!r})",
                        {"read_back": True, "seen": got[-60:]})


def verify_press(before: Snapshot, keys: str = "") -> Verification:
    """Verify a keypress or hotkey.

    Keys like Ctrl+C have no observable end state of their own, so this only
    proves the screen or the window changed. Weakest of the three, and says so.
    """
    if not (_HAS_PYAUTOGUI and _HAS_PIL):
        return _unknown("no screen capture available")
    after = _screen_hash()
    if before.screen_hash and after and after != before.screen_hash:
        return Verification(OK, "screen changed after the key press")
    fg = _fg_hwnd()
    if fg and fg != before.fg_hwnd:
        return Verification(OK, f"foreground window changed to {_window_title(fg)!r}")
    return Verification(UNKNOWN,
                        f"no observable change after {keys!r}; it may still have worked",
                        {"changed": False})


# ── 4. conditions ───────────────────────────────────────────────────────────

def wait_until(predicate: Callable[[], Any], timeout: float = 10.0,
               interval: float = 0.25, description: str = "") -> Verification:
    """Wait for a condition, instead of sleeping a hopeful fixed amount.

    computer_control's existing `wait` action is time.sleep(). That is a guess
    dressed as a wait: on a slow machine it returns before the thing happened,
    and on a fast one it wastes seconds. The documented failure mode for GUI
    automation is exactly this - a window that is detected and then gone a few
    milliseconds later.

    Returns OK the moment the predicate is truthy, FAILED on timeout.
    """
    deadline = time.time() + max(0.0, float(timeout))
    polls = 0
    last_err = ""
    while True:
        polls += 1
        try:
            if predicate():
                return Verification(OK, description or "condition met",
                                    {"polls": polls})
        except Exception as e:
            last_err = str(e)
        if time.time() >= deadline:
            break
        time.sleep(max(0.01, float(interval)))

    return Verification(FAILED,
                        f"condition not met within {timeout:g}s"
                        + (f" (last error: {last_err})" if last_err else ""),
                        {"polls": polls})


def wait_for_window(title_contains: str, timeout: float = 10.0) -> Verification:
    return wait_until(
        lambda: title_contains.lower() in _window_title(_fg_hwnd()).lower(),
        timeout=timeout,
        description=f"foreground window matching {title_contains!r}",
    )


def wait_for_process(name: str, timeout: float = 10.0) -> Verification:
    if not _HAS_PSUTIL:
        return _unknown("psutil not available")

    def _present() -> bool:
        needle = name.lower().replace(".exe", "")
        for p in _ps.process_iter(["name"]):
            try:
                if (p.info.get("name") or "").lower().replace(".exe", "") == needle:
                    return True
            except Exception:
                continue
        return False

    return wait_until(_present, timeout, description=f"process {name!r} running")


def wait_for_file(path: str, timeout: float = 10.0) -> Verification:
    p = os.path.expanduser(str(path))
    return wait_until(lambda: os.path.exists(p), timeout,
                      description=f"file {p!r} exists")


# ── 5. retry ────────────────────────────────────────────────────────────────

def with_retry(attempt: Callable[[int], Any],
               verify: Callable[[Any], Verification],
               attempts: int = 3,
               delay: float = 0.4,
               backoff: float = 2.0) -> tuple[Any, Verification]:
    """Run an action, verify it, and retry only when verification says no.

    Retrying on UNKNOWN would be wrong - it would fire the same keystrokes
    again at something that may have already succeeded, which is how a
    half-typed field becomes a double-typed one. Only a genuine FAILED
    earns another attempt.
    """
    last_value = None
    last_ver: Optional[Verification] = None
    wait = max(0.0, float(delay))

    for i in range(1, max(1, int(attempts)) + 1):
        try:
            last_value = attempt(i)
        except Exception as e:
            last_ver = Verification(FAILED, f"attempt {i} raised {e}")
            time.sleep(wait)
            wait *= backoff
            continue

        try:
            last_ver = verify(last_value)
        except Exception as e:
            last_ver = _unknown(f"verification itself failed: {e}")

        if last_ver.state in (OK, UNKNOWN):
            return last_value, last_ver

        # No point sleeping before an attempt that will not be made.
        # Caught by the backoff test: sleeping after the final failure added
        # 0.8s of dead time to every exhausted retry, delaying the answer the
        # user is waiting for by exactly as long as it slept for nothing.
        if i >= max(1, int(attempts)):
            break

        time.sleep(wait)
        wait *= backoff

    return last_value, last_ver or _unknown("no attempt was made")


# ── capability report ───────────────────────────────────────────────────────

def capabilities() -> dict:
    """What this machine can actually verify.

    Exposed so the assistant can tell the user the truth about its own
    limits instead of implying it can check everything.
    """
    return {
        "platform": platform.system(),
        "window_state": _IS_WINDOWS,
        "uia_structured": bool(_IS_WINDOWS and _HAS_UIA),
        "local_pixels": bool(_HAS_PYAUTOGUI and _HAS_PIL),
        "processes": _HAS_PSUTIL,
        # Deliberately absent: cloud vision. It is slow, costs money, and
        # ships the user's screen to a third party. Not used for verification.
        "cloud_vision_used": False,
    }


__all__ = [
    "OK", "FAILED", "UNKNOWN", "Verification", "Snapshot",
    "snapshot", "verify_click", "verify_typed", "verify_press",
    "read_focused_text", "element_from_point", "invoke_at",
    "wait_until", "wait_for_window", "wait_for_process", "wait_for_file",
    "with_retry", "capabilities",
]