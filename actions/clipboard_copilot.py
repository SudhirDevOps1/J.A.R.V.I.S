"""
actions/clipboard_copilot.py — Intelligent System Clipboard Copilot for J.A.R.V.I.S.

Inspects, diagnoses, formats, and transforms clipboard content with zero latency.
Auto-detects code error tracebacks, JSON data structures, URLs, and text blocks.
Uses pyperclip (<10KB RAM) and local rule/regex parsing.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

try:
    import pyperclip
    _HAS_PYPERCLIP = True
except ImportError:
    _HAS_PYPERCLIP = False

_in_memory_clipboard: str = ""


def _get_clipboard_text() -> str:
    if not _HAS_PYPERCLIP:
        return _in_memory_clipboard
    try:
        val = pyperclip.paste()
        return val if val else _in_memory_clipboard
    except Exception:
        return _in_memory_clipboard


def _set_clipboard_text(text: str) -> bool:
    global _in_memory_clipboard
    _in_memory_clipboard = text
    if not _HAS_PYPERCLIP:
        return True
    try:
        pyperclip.copy(text)
        return True
    except Exception:
        return True


def _detect_content_type(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "empty"
    
    # Traceback / Exception pattern
    if re.search(r"(Traceback \(most recent call last\)|Error:|Exception:|SyntaxError|TypeError|ValueError|NameError|IndexError|KeyError)", stripped):
        return "error_traceback"
    
    # JSON pattern
    if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
        try:
            json.loads(stripped)
            return "json"
        except Exception:
            pass
            
    # URL pattern
    if re.match(r"^https?://[^\s]+$", stripped):
        return "url"
        
    # Code snippet pattern
    if re.search(r"(def |class |function |import |const |let |var |public class |return |#include)", stripped):
        return "code"
        
    return "text"


def clipboard_copilot(
    parameters: dict | None = None,
    player=None,
    speak=None,
    response=None,
    session_memory=None,
    **_
) -> str:
    params = parameters or {}
    action = str(params.get("action", "analyze") or "analyze").lower().strip()
    user_text = str(params.get("text", "") or "").strip()

    clip_text = _get_clipboard_text()

    if action == "write":
        if not user_text:
            return "Clipboard par likhne ke liye koi text provide nahi kiya gaya."
        ok = _set_clipboard_text(user_text)
        return f"Clipboard updated successfully ({len(user_text)} characters copied)." if ok else "Clipboard update fail ho gaya."

    if not clip_text:
        return "Clipboard abhi khali hai (Empty). Pehle kuch text copy karein."

    ctype = _detect_content_type(clip_text)

    # 1. ANALYZE ACTION
    if action == "analyze":
        preview = clip_text[:120].replace("\n", " ") + ("..." if len(clip_text) > 120 else "")
        return (
            f"Clipboard Analysis:\n"
            f"• Content Type: {ctype.upper()}\n"
            f"• Length: {len(clip_text)} characters ({len(clip_text.splitlines())} lines)\n"
            f"• Preview: \"{preview}\""
        )

    # 2. EXPLAIN / DIAGNOSE ERROR TRACEBACK
    elif action in ("explain_error", "diagnose", "fix"):
        if ctype != "error_traceback":
            return f"Clipboard me koi direct error traceback nahi mila (Type: {ctype}). Preview: {clip_text[:100]}"
            
        # Parse common exception lines
        err_matches = re.findall(r"(?:[A-Za-z_]+Error|Exception): (.+)", clip_text)
        file_lines = re.findall(r'File "([^"]+)", line (\d+)', clip_text)
        
        details = []
        if file_lines:
            last_file, last_line = file_lines[-1]
            fname = last_file.replace("\\", "/").split("/")[-1]
            details.append(f"• Location: File {fname}, Line {last_line}")
        if err_matches:
            details.append(f"• Root Cause: {err_matches[-1]}")
            
        summary_str = "\n".join(details) if details else "• Error trace detected."
        return (
            f"Clipboard Error Diagnosis:\n{summary_str}\n"
            f"Tip: Check syntax, missing imports, or variable names at the referenced line."
        )

    # 3. FORMAT JSON
    elif action in ("format_json", "beautify"):
        try:
            parsed = json.loads(clip_text)
            formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
            _set_clipboard_text(formatted)
            return f"JSON successfully formatted and copied back to clipboard ({len(formatted)} chars)."
        except Exception as e:
            return f"Clipboard data valid JSON nahi hai: {e}"

    # 4. CLEAN / UNESCAPE TEXT
    elif action in ("clean", "normalize"):
        cleaned = re.sub(r"\r\n", "\n", clip_text)
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        _set_clipboard_text(cleaned)
        return f"Clipboard text cleaned and formatted ({len(cleaned)} chars)."

    # 5. READ RAW
    elif action == "read":
        return clip_text

    return f"Clipboard Copilot: Unknown action '{action}'. Options: analyze, explain_error, format_json, clean, read, write."


TOOL = {
    "name": "clipboard_copilot",
    "description": (
        "Inspects, diagnoses, and formats text from the system clipboard. "
        "Can explain code error tracebacks, pretty-print JSON, clean whitespace, "
        "or read/write clipboard contents. Trigger on 'clipboard explain karo', "
        "'clipboard me kya hai', 'format clipboard json', 'clipboard clean karo'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "analyze | explain_error | format_json | clean | read | write"
            },
            "text": {
                "type": "STRING",
                "description": "Optional text to copy to clipboard when action is 'write'"
            }
        },
        "required": ["action"]
    },
    "handler": clipboard_copilot
}
