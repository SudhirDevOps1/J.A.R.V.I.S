"""
Visual Screen Troubleshooter & Code Error Debugger (Pillow + Gemini 2.5 Flash)
Zero Local Model Overhead (< 5MB RAM, Zero GPU Load).

Workflow:
  1. Pillow / MSS captures the active screen and compresses it into a lightweight thumbnail (<150KB).
  2. Sends the image frame to Gemini 2.5 Flash Cloud with tailored visual debugging instructions.
  3. Gemini identifies compiler errors, syntax bugs, terminal tracebacks, or UI issues and returns
     a concise Hinglish explanation and solution.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from PIL import Image, ImageGrab
    _PIL = True
except ImportError:
    _PIL = False

try:
    import mss
    import mss.tools
    _MSS = True
except ImportError:
    _MSS = False


def _get_gemini_api_key() -> str:
    """Retrieve Gemini API key from config or environment."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    try:
        from memory.config_manager import load_api_keys
        keys = load_api_keys()
        k = (keys.get("gemini_api_key") or keys.get("gemini") or "").strip()
        if k:
            return k
    except Exception:
        pass
    cfg_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            return data.get("gemini_api_key") or data.get("gemini", "")
        except Exception:
            pass
    return ""


def _capture_screen_thumbnail() -> tuple[bytes, str]:
    """Capture screen and compress to <= 1280x720 JPEG thumbnail (<150KB)."""
    try:
        from core.privacy_guard import is_screen_capture_allowed, generate_shield_frame
        allowed, reason = is_screen_capture_allowed(is_stream=False)
        if not allowed:
            return generate_shield_frame(reason)
    except Exception:
        pass

    if _MSS:
        with mss.mss() as sct:
            monitors = sct.monitors
            target = monitors[1] if len(monitors) > 1 else monitors[0]
            shot = sct.grab(target)
            raw_png = mss.tools.to_png(shot.rgb, shot.size)
        if _PIL:
            img = Image.open(io.BytesIO(raw_png)).convert("RGB")
            img.thumbnail((1280, 720), Image.BILINEAR)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            return buf.getvalue(), "image/jpeg"
        return raw_png, "image/png"

    if _PIL:
        img = ImageGrab.grab().convert("RGB")
        img.thumbnail((1280, 720), Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue(), "image/jpeg"

    raise RuntimeError("Neither mss nor PIL (Pillow) is available for screen capture.")


def troubleshoot_screen(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    Inspects user screen and detects code errors, tracebacks, terminal output, or UI bugs.
    """
    params = parameters or {}
    user_query = params.get("query") or params.get("prompt") or "Is screen par kya error dikh raha hai? Check karo aur solution batao."

    # If PiP mode window is floating over the IDE, temporarily hide it so vision sees code/errors clearly
    pip_win = None
    pip_was_visible = False
    if player is not None:
        try:
            pip_win = getattr(player, "_pip", None)
            if pip_win is not None and hasattr(pip_win, "isVisible") and pip_win.isVisible():
                if not any(w in str(user_query).lower() for w in ("pip", "mini window", "companion")):
                    pip_win.hide()
                    pip_was_visible = True
                    import time; time.sleep(0.06)
        except Exception:
            pass

    try:
        img_bytes, mime_type = _capture_screen_thumbnail()
    except Exception as e:
        return f"Screen capture nahi ho paya: {e}"
    finally:
        if pip_was_visible and pip_win is not None:
            try:
                pip_win.show()
            except Exception:
                pass

    api_key = _get_gemini_api_key()
    if not api_key:
        return "Screen capture ho gaya hai par Gemini API key configured nahi hai config/api_keys.json mein."

    b64_img = base64.b64encode(img_bytes).decode("utf-8")

    # Detect active foreground window to give vision model exact context (e.g. VSCodium, Code, Terminal)
    active_win_title = ""
    try:
        import pygetwindow as _gw
        _w = _gw.getActiveWindow()
        if _w and getattr(_w, "title", None):
            active_win_title = _w.title.strip()
    except Exception:
        pass

    # Call Gemini Flash with multimodal payload (working endpoints first)
    models_to_try = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-2.5-flash",
        "gemini-flash-latest",
    ]
    last_err = ""

    asst_name = "Friday"
    try:
        from memory.config_manager import load_api_keys
        asst_name = (load_api_keys().get("assistant_name") or "Friday").strip()
    except Exception:
        pass

    active_win_hint = (
        f"\nUser's Active Window: '{active_win_title}' (e.g. VSCodium / Code Editor / Terminal).\n"
        "Inspect the underlying code editor, syntax highlighting, terminal tracebacks, and compiler errors in priority. "
        "Do NOT focus on or get distracted by any floating assistant widgets or overlays."
        if active_win_title else
        "\nFocus specifically on the code editor (e.g. VSCodium, VS Code), terminal output, compiler errors, and tracebacks. "
        "Ignore any floating assistant widgets or overlays."
    )

    system_instruction = (
        f"You are {asst_name}, a friendly, ultra-sharp AI assistant and visual troubleshooter. "
        "Examine this screenshot carefully and respond directly in fluent, natural Hinglish (conversational Hindi-English mix). "
        f"{active_win_hint}\n"
        "DO NOT use robotic numbered section headers (e.g. do NOT write '**1. Screen Description:**' or '**2. Errors:**'). "
        "Instead, speak directly and naturally: "
        "- In 1-2 quick sentences, mention what is open on the screen (e.g. VS Code, terminal, browser). "
        "- If an error, exception, syntax bug, or crash is visible, explain the exact root cause and give the concise fix or command. "
        "- If no error is visible, confirm everything looks clean and ask what specific part they would like help with. "
        "Keep the tone warm, concise, and helpful."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{system_instruction}\n\nUser question: {user_query}"},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_img
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 600,
        }
    }

    import urllib.request
    req_data = json.dumps(payload).encode("utf-8")

    for model_name in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                reply = "".join(p.get("text", "") for p in parts).strip()
                if reply:
                    return reply
                return "Screen par koi obvious issue nahi dikha sir, sab theek lag raha hai."
        except Exception as e:
            _msg = str(e)
            last_err = _msg
            if "401" in _msg or "403" in _msg or "API key" in _msg:
                return "Gemini API key invalid hai — config/api_keys.json me key check karein."
            continue

    if "timed out" in last_err.lower() or "timeout" in last_err.lower():
        return "Screen analysis timeout — internet slow hai, thodi der baad retry karein."
    if "429" in last_err or "quota" in last_err.lower() or "too many requests" in last_err.lower():
        return "Screen capture ho gaya hai. Abhi API rate limit chal rahi hai, thodi der baad dobara 'screen dekho' bolein."
    if "503" in last_err or "service unavailable" in last_err.lower() or "overloaded" in last_err.lower():
        return "Screen capture ho gaya hai, par vision servers abhi temporarily busy hain (503 Service Unavailable). Thodi der baad dobara 'screen dekho' bolein."
    return f"Screen analysis note: {last_err[:120]}"


TOOL = {
    "name": "troubleshoot_screen",
    "description": "Captures the user screen and uses Gemini 2.5 Flash to identify code errors, syntax issues, terminal tracebacks, compiler failures, or visual bugs without PC load.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "Specific question about what to check on screen (e.g. 'code me kya error hai', 'check terminal crash')"
            }
        },
        "required": []
    },
    "handler": troubleshoot_screen,
}
