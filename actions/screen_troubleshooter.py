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

    try:
        img_bytes, mime_type = _capture_screen_thumbnail()
    except Exception as e:
        return f"Screen capture nahi ho paya: {e}"

    api_key = _get_gemini_api_key()
    if not api_key:
        return "Screen capture ho gaya hai par Gemini API key configured nahi hai config/api_keys.json mein."

    b64_img = base64.b64encode(img_bytes).decode("utf-8")

    # Call Gemini 2.5 Flash with multimodal payload
    try:
        import urllib.request
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        
        system_instruction = (
            "You are J.A.R.V.I.S., a top-tier visual code & system troubleshooter. "
            "Examine this screenshot carefully. "
            "Identify: 1) Active IDE / Terminal / Browser errors, tracebacks, red underlines, or compiler logs. "
            "2) The exact file, line number, or syntax bug if visible. "
            "3) Give a clear, concise Hinglish explanation and immediate fix. "
            "Be direct, confident, and developer-friendly."
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

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            reply = "".join(p.get("text", "") for p in parts).strip()
            if reply:
                return reply
            return "Screen par koi obvious error nahi dikha sir, sab clean lag raha hai."

    except Exception as e:
        return f"Gemini screen analysis error: {e}"


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
