"""Keyboard/mouse macro record & replay. New file, auto-discovered.
pynput listeners (lazy import), JSON in config/macros/, ESC-stop, speed control.
Replay se pehle confirm gate (research best-practice: countdown + confirmation).
Existing computer_control untouched.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

_MAC_DIR = Path(__file__).resolve().parent.parent / "config" / "macros"
_recording: dict = {"active": False, "events": [], "name": "", "t0": 0.0}
_rec_lock = threading.Lock()


def _log(player, msg: str) -> None:
    try:
        if player:
            player.write_log(msg)
    except Exception:
        pass
    print(msg)


def _audit(action: str, detail: str = "", confirmed: bool = False) -> None:
    try:
        from core.audit import log_event as _ae
        _ae(action, detail, confirmed)
    except Exception:
        pass


def _macro_path(name: str) -> Path:
    safe = "".join(c for c in (name or "macro").strip().lower() if c.isalnum() or c in ("-", "_"))[:30] or "macro"
    return _MAC_DIR / f"{safe}.json"


def _start_record(name: str, player=None) -> str:
    try:
        from pynput import keyboard as _kb, mouse as _ms
    except Exception:
        return "Macro ke liye pynput install karo: pip install pynput."
    with _rec_lock:
        if _recording["active"]:
            return f"'{_recording['name']}' record ho raha hai. Pehle 'macro stop' bolo."
        _recording.update(active=True, events=[], name=name, t0=time.time())
    events = _recording["events"]
    t0 = _recording["t0"]

    def _t():
        return round(time.time() - t0, 3)

    def _on_press(key):
        try:
            k = key.char if hasattr(key, "char") and key.char else str(key).replace("Key.", "")
            events.append({"t": _t(), "dev": "kb", "ev": "press", "key": k[:20]})
        except Exception:
            pass

    def _on_release(key):
        from pynput.keyboard import Key as _K
        if key == _K.esc:
            _stop_record(player)
            return False
        try:
            k = key.char if hasattr(key, "char") and key.char else str(key).replace("Key.", "")
            events.append({"t": _t(), "dev": "kb", "ev": "release", "key": k[:20]})
        except Exception:
            pass

    def _on_click(x, y, button, pressed):
        try:
            events.append({"t": _t(), "dev": "ms", "ev": "click" if pressed else "up",
                           "x": int(x), "y": int(y), "btn": str(button).split(".")[-1]})
        except Exception:
            pass

    def _on_move(x, y):
        try:
            if not events or events[-1].get("dev") != "ms" or events[-1].get("ev") != "move":
                events.append({"t": _t(), "dev": "ms", "ev": "move", "x": int(x), "y": int(y)})
            else:
                events[-1].update(t=_t(), x=int(x), y=int(y))
        except Exception:
            pass

    kl = _kb.Listener(on_press=_on_press, on_release=_on_release, daemon=True)
    ml = _ms.Listener(on_click=_on_click, on_move=_on_move, daemon=True)
    kl.start(); ml.start()
    with _rec_lock:
        _recording["listeners"] = (kl, ml)
    _log(player, f"[macro] recording '{name}' (ESC dabao stop ke liye)")
    return f"Macro '{name}' record ho raha hai. Kaam karo, rokne ke liye ESC dabao ya 'macro stop' bolo."


def _stop_record(player=None) -> str:
    with _rec_lock:
        if not _recording["active"]:
            return "Koi recording chal nahi rahi."
        for li in _recording.get("listeners", ()):
            try:
                li.stop()
            except Exception:
                pass
        name, events = _recording["name"], list(_recording["events"])
        _recording.update(active=False, events=[], name="")
    if not events:
        return f"'{name}' me kuch record nahi hua."
    try:
        _MAC_DIR.mkdir(parents=True, exist_ok=True)
        p = _macro_path(name)
        _tmp = p.with_suffix(".json.tmp")
        _tmp.write_text(json.dumps({"name": name, "events": events[:5000]}, indent=1), encoding="utf-8")
        import os as _os
        _os.replace(str(_tmp), str(p))
        _audit("macro_record", f"{name} ({len(events)} events)")
        _log(player, f"[macro] saved '{name}' ({len(events)} events)")
        return f"Macro '{name}' save ho gaya ({len(events)} steps). Chalane ke liye 'macro chalao {name}' bolo."
    except Exception as e:
        return f"Macro save failed: {e}"


def _play(name: str, speed: float, player=None) -> str:
    p = _macro_path(name)
    if not p.exists():
        return f"Macro '{name}' nahi mila. 'macro list' se dekho."
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        events = data.get("events", [])
    except Exception:
        return f"Macro '{name}' corrupt hai."
    if not events:
        return f"Macro '{name}' khali hai."
    try:
        from pynput.keyboard import Controller as _KC, Key as _K
        from pynput.mouse import Controller as _MC, Button as _B
    except Exception:
        return "Replay ke liye pynput install karo: pip install pynput."
    kb, ms = _KC(), _MC()
    _log(player, f"[macro] playing '{name}' x{speed:g} — 3s me shuru")
    time.sleep(3)  # countdown: galat window ho to cancel karo (research best-practice)
    prev = 0.0
    n = 0
    for ev in events[:5000]:
        try:
            time.sleep(max(0.0, (ev.get("t", 0) - prev)) / max(0.25, speed))
            prev = ev.get("t", 0)
            if ev.get("dev") == "kb":
                k = str(ev.get("key", ""))
                key = getattr(_K, k, None) or k
                (kb.press if ev.get("ev") == "press" else kb.release)(key)
            elif ev.get("dev") == "ms":
                if ev.get("ev") == "move":
                    ms.position = (int(ev.get("x", 0)), int(ev.get("y", 0)))
                else:
                    ms.position = (int(ev.get("x", 0)), int(ev.get("y", 0)))
                    btn = {"left": _B.left, "right": _B.right, "middle": _B.middle}.get(
                        str(ev.get("btn", "left")), _B.left)
                    (ms.press if ev.get("ev") == "click" else ms.release)(btn)
            n += 1
        except Exception:
            continue
    _audit("macro_play", f"{name} ({n} steps)")
    return f"Macro '{name}' chal gaya ({n} steps)."


def macro(parameters: dict | None = None, player=None, session_memory=None, **_) -> str:
    params = parameters or {}
    action = str(params.get("action", "list") or "list").lower().strip()
    name = str(params.get("name", "") or "").strip() or "macro1"
    if action in ("record", "start", "rec"):
        return _start_record(name, player)
    if action in ("stop", "save", "rok"):
        return _stop_record(player)
    if action in ("list", "show"):
        try:
            files = sorted(_MAC_DIR.glob("*.json")) if _MAC_DIR.exists() else []
            if not files:
                return "Koi macro nahi hai. 'macro record karo' se banao."
            return "Macros: " + ", ".join(f.stem for f in files)
        except Exception as e:
            return f"List failed: {e}"
    if action in ("play", "run", "chalao"):
        try:
            speed = max(0.25, min(4.0, float(str(params.get("speed", "1") or "1"))))
        except Exception:
            speed = 1.0
        # Replay confirm-gated (galat window par tez replay se bachao)
        try:
            from core import confirm as _cg
            if _cg.pending_title():
                return "Ek confirmation pending hai. Pehle use nipatao."
            _audit("macro_play_asked", name)

            def _do() -> str:
                return _play(name, speed, player)

            return _cg.request("macro_play", f"Macro chalao: {name}",
                               f"'{name}' replay hoga x{speed:g} speed par (3s countdown ke saath).",
                               _do)
        except Exception:
            return _play(name, speed, player)
    return "Unknown macro action. Use record, stop, list, play."


TOOL = {
    "name": "macro",
    "description": (
        "Record keyboard/mouse macros and replay them. Trigger on 'macro record karo', "
        "'macro rok', 'macro chalao', 'macro list'. Replay asks HUD confirmation first."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "record | stop | list | play"},
            "name": {"type": "STRING", "description": "Macro name"},
            "speed": {"type": "STRING", "description": "Replay speed 0.25-4, default 1"},
        },
        "required": ["action"],
    },
    "handler": macro,
}
