"""OCR tools + clipboard history. New file, auto-discovered. Nothing existing touched.
easyocr optional — missing par clean Hindi error, no crash.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

_HIST_FILE = Path(__file__).resolve().parent.parent / "config" / "clipboard_history.json"
_HIST_MAX = 20


def _log(player, msg: str) -> None:
    try:
        if player:
            player.write_log(msg)
    except Exception:
        pass
    print(msg)


def append_clipboard_history(text: str) -> None:
    """Clipboard listener se call karo. Additive, never raises, max 20 entries."""
    try:
        t = (text or "").strip()
        if len(t) < 10:
            return
        _HIST_FILE.parent.mkdir(parents=True, exist_ok=True)
        hist = []
        try:
            if _HIST_FILE.exists():
                hist = json.loads(_HIST_FILE.read_text(encoding="utf-8"))
                if not isinstance(hist, list):
                    hist = []
        except Exception:
            hist = []
        hist = [h for h in hist if h.get("text") != t[:500]]
        hist.insert(0, {"text": t[:500], "at": time.strftime("%I:%M %p")})
        hist = hist[:_HIST_MAX]
        _tmp = _HIST_FILE.with_suffix(".json.tmp")
        _tmp.write_text(json.dumps(hist, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(str(_tmp), str(_HIST_FILE))
    except Exception:
        pass


def _screen_ocr(player=None) -> str:
    try:
        import mss as _mss
        from PIL import Image as _Im
    except Exception:
        return "Screenshot ke liye mss+pillow install karo: pip install mss pillow."
    shot = None
    try:
        with _mss.mss() as sct:
            mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            shot = sct.grab(mon)
            img = _Im.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    except Exception as e:
        return f"Screenshot failed: {e}"
    try:
        import easyocr as _eo
        reader = _eo.Reader(["en", "hi"], gpu=False)
        import numpy as _np
        res = reader.readtext(_np.array(img), detail=0)
        txt = "\n".join(res).strip()[:2000]
        if txt:
            append_clipboard_history(txt)
            _log(player, "[ocr] screen text copied to history")
            return f"Screen par ye text mila:\n{txt}"
        return "Screen par koi text nahi mila."
    except ImportError:
        return ("OCR ke liye easyocr install karo: pip install easyocr. "
                "Screenshot liya gaya lekin text nahi padha.")
    except Exception as e:
        return f"OCR failed: {e}"


def _history_search(query: str, player=None) -> str:
    try:
        if not _HIST_FILE.exists():
            return "Clipboard history khali hai."
        hist = json.loads(_HIST_FILE.read_text(encoding="utf-8"))
    except Exception:
        return "History read failed."
    q = (query or "").strip().lower()
    if not q:
        lines = [f"{i+1}. {h.get('text', '')[:60]}" for i, h in enumerate(hist[:10])]
        return "Clipboard history:\n" + ("\n".join(lines) if lines else "khali hai.")
    hits = [h for h in hist if q in str(h.get("text", "")).lower()][:5]
    if not hits:
        return f"'{query}' history me nahi mila."
    return "Mile:\n" + "\n".join(f"- {h.get('text', '')[:120]}" for h in hits)


def ocr_tools(parameters: dict | None = None, player=None, session_memory=None, **_) -> str:
    params = parameters or {}
    action = str(params.get("action", "screen_ocr") or "screen_ocr").lower().strip()
    if action in ("screen_ocr", "ocr", "read_screen", "extract_text"):
        return _screen_ocr(player)
    if action in ("history", "clip_history", "search_history"):
        return _history_search(str(params.get("query", "") or ""), player)
    if action in ("save_clip", "remember_clip"):
        append_clipboard_history(str(params.get("text", "") or ""))
        return "Clipboard history me save kar diya."
    return "Unknown ocr_tools action. Use screen_ocr, history, save_clip."


TOOL = {
    "name": "ocr_tools",
    "description": (
        "Read text from screen via OCR (like Text Extractor), search clipboard history. "
        "Trigger on 'screen ka text padho', 'clipboard history dikhao', 'copy history me dhoondo'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "screen_ocr | history | save_clip"},
            "query": {"type": "STRING", "description": "Search text for history"},
            "text": {"type": "STRING", "description": "Text to save for save_clip"},
        },
        "required": ["action"],
    },
    "handler": ocr_tools,
}
