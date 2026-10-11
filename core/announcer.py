"""
core/announcer.py â€” spoken confirmations for background events.

WHY THIS EXISTS
---------------
The user asked for two things that were only half true of this codebase:

  "task ya timer start ho to bole"   â€” when a timer is SET, say so out loud
  "jab timer khtam ho to bole"        â€” when a timer COMPLETES, say so

Completion already spoke, but the sentence was a hardcoded Hinglish string
built with "sir" in it: "Alert sir! X ka time ho gaya hai." It ignored the
configured assistant name, the configured gender, and the user's chosen
language, so a user running the assistant in English still got Hinglish, and a
user whose persona is not addressed as "sir" was addressed as "sir" anyway.

Setting a timer produced no speech at all - only a log line, which is invisible
if the window is closed, which is precisely when a timer matters most.

This module builds those sentences. It has no TTS dependency: it returns the
text and lets the caller speak it, which keeps it testable and keeps audio
concerns out of the scheduling code.

THE ANNOUNCEMENT MUST NOT BLOCK
-------------------------------
Speech runs on a worker thread via the caller's speak hook, and every call
here is wrapped. A reminder that has already been scheduled must not be lost
because the audio engine threw.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

# How long to describe "in 5 minutes" without inventing precision the
# scheduler may not honour.
_DAYWORDS = {
    "day": "day", "days": "days",
    "hour": "hour", "hours": "hours",
    "minute": "minute", "minutes": "minutes",
    "second": "second", "seconds": "seconds",
}


def _address() -> str:
    """How the assistant should address this user.

    Empty string when unknown, because a wrong form of address is worse than
    none. 'Sir' is used only as the last resort and only for the male default.
    """
    try:
        from memory.config_manager import get_user_name, get_assistant_gender
        name = (get_user_name() or "").strip()
        if name:
            return name
        gender = (get_assistant_gender() or "male").lower().strip()
    except Exception:
        return ""
    return "Sir" if gender == "male" else "Ma'am"


def _prefers_hinglish(user_text: str = "") -> bool:
    """Whether to speak Hinglish rather than English.

    Devanagari in the user's own text is the reliable signal. Roman-script
    Hinglish is genuinely ambiguous - English and Hinglish share an alphabet -
    so when there is no user text to inspect, the configured language setting
    is the honest fallback. Guessing from a Latin transcript alone would flip
    the language on every English word.
    """
    text = user_text or ""
    if any("\u0900" <= ch <= "\u097F" for ch in text):
        return True
    if text.strip():
        # Real user text, but no Devanagari: they typed plain English.
        return False
    try:
        from memory.config_manager import get_preferred_language
        lang = (get_preferred_language() or "").lower().strip()
        return lang in ("hinglish", "hi", "hindi", "hinglish-roman")
    except Exception:
        return False


def timer_set_text(message: str, when_text: str,
                   user_text: str = "") -> str:
    """Spoken confirmation that a timer or reminder is now armed.

    Short by design. This plays at the moment of setting, and a long sentence
    would be worse than useless while the user is mid-sentence.
    """
    who = _address()
    label = (message or "").strip()
    when = (when_text or "").strip()

    if _prefers_hinglish(user_text):
        if who:
            return f"Timer set hai {who}. {when}. {label}."
        return f"Timer set hai. {when}. {label}."

    if who:
        return f"Timer set for {when}. {label}."
    return f"Timer set for {when}. {label}."


def timer_done_text(message: str, user_text: str = "") -> str:
    """Spoken confirmation that a timer has just finished.

    Used to be a hardcoded Hinglish string containing the literal word "sir".
    It now follows the configured name and the user's language.
    """
    label = (message or "").strip() or "Alarm"
    who = _address()

    if _prefers_hinglish(user_text):
        if who:
            return f"{who}, {label} ka time ho gaya hai."
        return f"{label} ka time ho gaya hai."

    if who:
        return f"{who}, your {label} timer has finished."
    return f"Your {label} timer has finished."


def task_added_text(task: str, count: Optional[int] = None,
                    user_text: str = "") -> str:
    """Spoken confirmation that a todo/task was added."""
    label = (task or "").strip()
    n = f" ({count} total)" if count else ""
    if _prefers_hinglish(user_text):
        return f"Task add kar diya{n}: {label}"
    return f"Task added{n}: {label}"


def announce(text: str, speak: Optional[Callable[[str], None]] = None,
             log: Optional[Callable[[str], None]] = None) -> bool:
    """Say `text`, if a speak hook was supplied.

    Returns True when speech was handed off. Never raises and never blocks the
    caller: scheduling has already succeeded by the time this runs, and a
    speech failure must not lose the reminder.
    """
    if not (text or "").strip():
        return False
    try:
        if log is not None:
            log(text)
    except Exception:
        pass
    if speak is None or not callable(speak):
        return False
    try:
        threading.Thread(target=_speak_guarded, args=(speak, text),
                         daemon=True, name="jarvis-announce").start()
        return True
    except Exception:
        # Thread creation can fail under resource pressure. Speak inline as a
        # last resort rather than staying silent.
        try:
            _speak_guarded(speak, text)
            return True
        except Exception:
            return False


def _speak_guarded(speak: Callable[[str], None], text: str) -> None:
    try:
        speak(text)
    except Exception as e:
        print(f"[Announce] speech failed: {e}")