"""
core/confirm.py — a confirmation the model cannot forge.

THE PROBLEM WITH THE OLD GATE
    computer_settings guarded shutdown and restart like this:

        confirmed = str(params.get("confirmed", "")).lower()
        if confirmed not in ("yes", "true", "1", "confirm"):
            return "Please confirm by calling again with confirmed=yes."

    `confirmed` is a tool parameter, which means the *model* writes it. Nothing
    stops it from sending confirmed=yes on the first call, and nothing checks
    that a human was ever involved. It is a convention, not a gate — and its
    coverage was two actions, so deleting files and switching off the WiFi the
    assistant is talking over went through with no gate at all.

THE DESIGN HERE
    The confirmation token is issued by the *interface*, never by the model:

      1. An action calls `request(...)` with a callable that does the real work.
      2. This module hands the UI a banner with CONFIRM / CANCEL and returns
         IMMEDIATELY with a sentence for the model to say out loud.
      3. If — and only if — the user presses CONFIRM, the UI calls `resolve()`,
         which runs the stored callable off the Qt thread.

    Nothing blocks. The model keeps talking while the banner is up, so this
    costs no latency at all; in fact it is cheaper than the old gate, which
    burned two tool round trips (reject, then re-call) on every shutdown.

WHAT BELONGS HERE AND WHAT DOES NOT
    Only genuinely irreversible things. Anything that can be reversed should be
    done at once and pushed onto core/undo.py instead — undo is faster than a
    question, and an assistant that asks before every action is one nobody uses.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

# A pending confirmation is abandoned after this long. Chosen to outlast a
# normal "hang on, let me look at the screen" pause without leaving a live
# shutdown button sitting on the HUD for the rest of the day.
TIMEOUT_SECONDS = 90.0


@dataclass
class _Pending:
    key:     str
    title:   str
    detail:  str
    run:     Callable[[], str]
    at:      float


_pending: Optional[_Pending] = None
_lock = threading.Lock()

# ADDITIVE FIFO queue (single slot tha — dusra confirm pehle ko overwrite karta tha).
# _pending = screen par abhi dikh raha; _queue = waiting (max 5, purana drop nahi hota silently — log me aata hai).
_queue: list[_Pending] = []
_QUEUE_MAX = 5


def _valid(p: Optional[_Pending]) -> bool:
    return p is not None and (time.monotonic() - p.at) <= TIMEOUT_SECONDS

# Set once at startup by main.py. Signature: (title, detail) -> None for show,
# and () -> None for hide. Both are marshalled onto the Qt thread by the UI.
_show_cb: Optional[Callable[[str, str], None]] = None
_hide_cb: Optional[Callable[[], None]] = None
_log_cb:  Optional[Callable[[str], None]] = None


def bind(show, hide, log=None) -> None:
    """Wire this module to the HUD. Called once from main.py at startup."""
    global _show_cb, _hide_cb, _log_cb
    _show_cb, _hide_cb, _log_cb = show, hide, log


def _log(msg: str) -> None:
    if _log_cb:
        try:
            _log_cb(msg)
        except Exception:
            pass


def _audit(action: str, detail: str = "", confirmed: bool = False) -> None:
    """ADDITIVE: audit log hook (core/audit.py). Never raises, never blocks."""
    try:
        from core.audit import log_event as _ae
        _ae(action, detail, confirmed)
    except Exception:
        pass


def request(key: str, title: str, detail: str, run: Callable[[], str]) -> str:
    """Park an irreversible action behind the on-screen gate.

    Returns the sentence the tool should hand back to the model — phrased as an
    instruction so the assistant asks the user out loud in their own language,
    rather than reading an English string verbatim."""
    global _pending

    if _show_cb is None:
        # No interface bound (headless, or a very early call). Refuse rather
        # than silently performing something irreversible.
        return (f"I cannot confirm '{title}' right now because the interface is "
                f"not available, so I have not done it.")

    with _lock:
        if _valid(_pending):
            # Screen busy hai — queue me lagao (overwrite nahi, kuch hataya nahi)
            _queue.append(_Pending(key=key, title=title, detail=detail, run=run, at=time.monotonic()))
            while len(_queue) > _QUEUE_MAX:
                dropped = _queue.pop(0)
                _log(f"SYS: Confirm queue full — dropped oldest: {dropped.title}")
            pos = len(_queue)
            cur = _pending.title if _pending else ""
            return (
                f"[CONFIRMATION_PENDING] '{cur}' is already awaiting confirmation. "
                f"I have queued '{title}' at position {pos}. "
                f"Say ONE short sentence in the user's own language telling them there are "
                f"{pos + 1} confirmations waiting. Do not claim anything is done."
            )
        _pending = _Pending(key=key, title=title, detail=detail,
                            run=run, at=time.monotonic())

    try:
        _show_cb(title, detail)
    except Exception as e:
        with _lock:
            _pending = None
        return f"Could not ask for confirmation: {e}. Nothing was done."

    _log(f"SYS: Awaiting confirmation — {title}")
    return (
        f"[CONFIRMATION_PENDING] I have put a confirmation on screen for: {title}. "
        f"Say ONE short sentence in the user's own language telling them you need "
        f"them to confirm it on the HUD before you do it. Do not claim it is done."
    )


def resolve(accepted: bool) -> None:
    """Called by the UI when the user presses CONFIRM or CANCEL.

    Runs the stored callable on a worker thread — this is invoked from the Qt
    thread, and shutting the machine down from inside a button handler would
    freeze the interface on its way out."""
    global _pending

    with _lock:
        p, _pending = _pending, None

    if _hide_cb:
        try:
            _hide_cb()
        except Exception:
            pass

    if p is None:
        _promote_next()
        return

    if time.monotonic() - p.at > TIMEOUT_SECONDS:
        _log(f"SYS: Confirmation expired — {p.title}")
        _promote_next()
        return

    if not accepted:
        _log(f"SYS: Cancelled — {p.title}")
        _audit(f"confirm:{p.key}_cancelled", p.title)
        _promote_next()
        return

    def _worker():
        try:
            result = p.run() or "Done."
            _log(f"SYS: Confirmed — {p.title}. {result}")
            _audit(f"confirm:{p.key}", p.title, confirmed=True)
        except Exception as e:
            _log(f"ERR: {p.title} failed — {e}")
            _audit(f"confirm:{p.key}_failed", p.title)
        finally:
            _promote_next()

    threading.Thread(target=_worker, daemon=True,
                     name=f"confirm-{p.key}").start()


def _promote_next() -> None:
    """ADDITIVE FIFO: queue se next valid uthao + banner dikhao. Never raises."""
    global _pending
    nxt: Optional[_Pending] = None
    with _lock:
        while _queue:
            cand = _queue.pop(0)
            if _valid(cand):
                nxt = cand
                break
            _log(f"SYS: Queued confirmation expired — {cand.title}")
        if nxt is not None:
            _pending = nxt
    if nxt is not None:
        if _show_cb:
            try:
                _show_cb(nxt.title, nxt.detail)
            except Exception as e:
                with _lock:
                    if _pending is nxt:
                        _pending = None
                _log(f"SYS: Could not show queued confirmation: {e}")
                return
        _log(f"SYS: Next confirmation — {nxt.title}")


def _queued_count() -> int:
    """ADDITIVE: waiting confirmations ki ginti (UI badge ke liye)."""
    with _lock:
        return sum(1 for c in _queue if _valid(c))


def pending_title() -> str:
    """'' when nothing is waiting. Lets an action avoid stacking two banners."""
    with _lock:
        if _pending is None:
            return ""
        if time.monotonic() - _pending.at > TIMEOUT_SECONDS:
            return ""
        return _pending.title


# ── Additive expandable gate (purana request/resolve untouched) ──────────────
# Model khud decide kare kab confirm mangna hai: mass-delete, mass-mail,
# main-branch push, form-submit. Heuristics only, false-negative par purana
# shutdown/restart/WiFi gate waise hi kaam karta hai.
IRREVERSIBLE_PATTERNS: tuple[str, ...] = (
    "mass_delete_50_plus",
    "mass_email_send",
    "github_push_main",
    "browser_form_submit",
)


def needs_confirmation(key: str, params: dict | None = None) -> bool:
    """True agar key/params irreversible expanded gate me aaye. Never raises."""
    try:
        k = (key or "").lower().strip()
        if k in IRREVERSIBLE_PATTERNS:
            return True
        p = params or {}
        try:
            n = int(p.get("count", p.get("files_count", 0)) or 0)
            if n >= 50:
                return True
        except Exception:
            pass
        if k in ("github_push", "git_push") and str(p.get("branch", "")).lower() in ("main", "master"):
            return True
        return False
    except Exception:
        return False
