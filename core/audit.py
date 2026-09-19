"""Audit log — kaunsi sensitive action, kab, kisne confirm ki. New file, additive.
memory/audit.jsonl me append-only lines. Never raises, never blocks.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

_AUDIT_FILE = Path(__file__).resolve().parent.parent / "memory" / "audit.jsonl"
_MAX_LINES = 2000


def log_event(action: str, detail: str = "", confirmed: bool = False) -> None:
    """Ek audit line append karo. Kabhi raise nahi karta."""
    try:
        _AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        entry = {"at": time.strftime("%Y-%m-%d %I:%M %p"),
                 "action": str(action)[:120],
                 "detail": str(detail)[:300],
                 "confirmed": bool(confirmed)}
        with open(_AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        try:
            lines = _AUDIT_FILE.read_text(encoding="utf-8").splitlines()
            if len(lines) > _MAX_LINES:
                _AUDIT_FILE.write_text("\n".join(lines[-_MAX_LINES:]) + "\n", encoding="utf-8")
        except Exception:
            pass
    except Exception:
        pass


def recent(count: int = 10) -> list[dict]:
    """Aakhri N audit entries (never raises)."""
    try:
        lines = _AUDIT_FILE.read_text(encoding="utf-8").splitlines()
        out = []
        for ln in lines[-max(1, min(50, count)):]:
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out
    except Exception:
        return []
