"""Thumbs feedback store — 👍/👎 per AI reply. New file, additive.
memory/feedback.json (max 500). Hermes future me seekhega. Never raises.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

_FEEDBACK_FILE = Path(__file__).resolve().parent / "feedback.json"
_MAX = 500


def log_feedback(vote: str, context: str = "") -> bool:
    """vote='up'|'down'. Returns True on save. Never raises."""
    try:
        v = "up" if str(vote).lower().startswith("up") else "down"
        _FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        items = []
        try:
            if _FEEDBACK_FILE.exists():
                items = json.loads(_FEEDBACK_FILE.read_text(encoding="utf-8"))
                if not isinstance(items, list):
                    items = []
        except Exception:
            items = []
        items.append({"at": time.strftime("%Y-%m-%d %I:%M"),
                      "vote": v, "context": str(context or "")[:200]})
        items = items[-_MAX:]
        _tmp = _FEEDBACK_FILE.with_suffix(".json.tmp")
        _tmp.write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
        import os as _os
        _os.replace(str(_tmp), str(_FEEDBACK_FILE))
        return True
    except Exception:
        return False


def stats() -> dict:
    """{'up': N, 'down': M}. Never raises."""
    try:
        items = json.loads(_FEEDBACK_FILE.read_text(encoding="utf-8"))
        up = sum(1 for i in items if isinstance(i, dict) and i.get("vote") == "up")
        return {"up": up, "down": max(0, len(items) - up)}
    except Exception:
        return {"up": 0, "down": 0}
