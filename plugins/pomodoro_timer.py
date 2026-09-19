"""Pomodoro focus timer plugin (additive). Threaded, SFX alerts, no core change."""

PLUGIN = {
    "name": "pomodoro_timer",
    "description": (
        "Start a focus Pomodoro timer with SFX alerts. Trigger on 'pomodoro start', "
        "'focus 25 minutes', 'break lo'. Do NOT use reminder for short focus sprints."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "minutes": {"type": "STRING", "description": "Focus minutes, default 25"},
            "label": {"type": "STRING", "description": "Session label"},
        },
        "required": [],
    },
}

_TIMERS: dict = {}


def run(parameters: dict, player=None, session_memory=None) -> str:
    import threading as _th, time as _t
    try:
        minutes = float(str((parameters or {}).get("minutes", "25") or "25").strip() or "25")
    except Exception:
        minutes = 25.0
    minutes = max(1.0, min(120.0, minutes))
    label = str((parameters or {}).get("label", "Focus") or "Focus").strip()[:40]

    def _worker():
        try:
            _t.sleep(minutes * 60)
            try:
                from core.sfx import play_sfx as _sfx
                _sfx("success")
            except Exception:
                pass
            if player:
                try:
                    player.write_log(f"SYS: Pomodoro '{label}' complete ({minutes:g} min).")
                except Exception:
                    pass
        except Exception:
            pass

    _th.Thread(target=_worker, daemon=True, name=f"pomodoro-{label}").start()
    if player:
        try:
            player.write_log(f"JARVIS: Pomodoro '{label}' started ({minutes:g} min).")
        except Exception:
            pass
    return f"Pomodoro '{label}' started for {minutes:g} minutes. I will alert you."
