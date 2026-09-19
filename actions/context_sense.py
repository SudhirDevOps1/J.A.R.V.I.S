"""Screen-aware context: kya khula hai + smart suggestions. New file, auto-discovered.
Zero-token heuristics (psutil/pygetwindow). Model isko padhke user se puchega
ya khud act karega. Existing tools untouched.
"""
from __future__ import annotations

import os
import time


def _log(player, msg: str) -> None:
    try:
        if player:
            player.write_log(msg)
    except Exception:
        pass
    print(msg)


def _open_windows(limit: int = 12) -> list[str]:
    """Visible window titles (best-effort). Never raises."""
    try:
        import pygetwindow as _gw
        out = []
        for w in _gw.getAllWindows():
            try:
                t = (w.title or "").strip()
                if t and w.visible and t not in out:
                    out.append(t)
            except Exception:
                continue
            if len(out) >= limit:
                break
        return out
    except Exception:
        return []


def _active_window() -> str:
    try:
        import pygetwindow as _gw
        w = _gw.getActiveWindow()
        return (w.title or "").strip() if w else ""
    except Exception:
        return ""


def _top_proc() -> str:
    """Sabse zyada CPU khane wala user process (best-effort). Never raises."""
    try:
        import psutil as _ps
        best, best_v = "", 0.0
        for p in _ps.process_iter(["name", "cpu_percent"]):
            try:
                n = (p.info.get("name") or "").lower()
                if not n or n in ("system", "registry", "svchost.exe", "idle"):
                    continue
                v = float(p.info.get("cpu_percent") or 0.0)
                if v > best_v:
                    best, best_v = n, v
            except Exception:
                continue
        return f"{best} ({best_v:.0f}%)" if best else ""
    except Exception:
        return ""


def _metrics() -> dict:
    m: dict = {}
    try:
        import psutil as _ps
        m["ram"] = _ps.virtual_memory().percent
        m["cpu"] = _ps.cpu_percent(interval=None)
    except Exception:
        pass
    try:
        m["hour"] = int(time.strftime("%H"))
    except Exception:
        pass
    return m


def context_sense(parameters: dict | None = None, player=None, session_memory=None, **_) -> str:
    params = parameters or {}
    action = str(params.get("action", "sense") or "sense").lower().strip()
    wins = _open_windows()
    active = _active_window()
    m = _metrics()

    if action in ("suggest", "sujhav", "kya_karun", "advise"):
        tips: list[str] = []
        ram = m.get("ram")
        if isinstance(ram, (int, float)) and ram >= 85:
            top = _top_proc()
            tips.append(f"RAM {ram:.0f}% hai" + (f" — '{top}' sabse bhari hai, band kar dun?" if top else " — kuch apps band kar dun?"))
        if len(wins) >= 8:
            tips.append(f"{len(wins)} windows khuli hain — purani band kar dun?")
        try:
            import os as _os
            dl = str(_os.path.join(os.path.expanduser("~"), "Downloads"))
            import pathlib as _pl
            n = sum(1 for _ in _pl.Path(dl).iterdir()) if _pl.Path(dl).is_dir() else 0
            if n > 30:
                tips.append(f"Downloads me {n} items — organize kar dun?")
        except Exception:
            pass
        h = m.get("hour")
        if isinstance(h, int) and h >= 23:
            tips.append("Raat ke 11+ baj gaye — so jao, kal continue karenge?")
        if not tips:
            tips.append("Sab smooth hai — koi kaam ho to bolo.")
        if active:
            tips.insert(0, f"Abhi saamne: {active[:60]}")
        out = "Suggestions:\n" + "\n".join(f"{i+1}. {t}" for i, t in enumerate(tips))
        _log(player, f"[sense] {len(tips)} suggestions")
        return out

    # sense: kya khula hai
    lines = [f"Saamne: {active}" if active else "Saamne: (pata nahi)"]
    if wins:
        lines.append(f"Khuli windows ({len(wins)}): " + ", ".join(w[:40] for w in wins[:8]))
    else:
        lines.append("Khuli windows: list nahi mili (pygetwindow chahiye).")
    if "ram" in m:
        lines.append(f"RAM {m['ram']:.0f}% | CPU {m.get('cpu', 0):.0f}%")
    top = _top_proc()
    if top:
        lines.append(f"Sabse bhari process: {top}")
    out = "\n".join(lines)
    _log(player, "[sense] snapshot")
    return out


TOOL = {
    "name": "context_sense",
    "description": (
        "See what's open on screen right now + smart suggestions. Trigger on "
        "'screen par kya hai', 'kya khula hai', 'suggest karo', 'kya karun'. "
        "Use before advising about open apps."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "sense | suggest"},
        },
        "required": ["action"],
    },
    "handler": context_sense,
}
