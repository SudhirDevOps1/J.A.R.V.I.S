"""Conditional workflows — if-this-then-that rules. New file, auto-discovered.
config/workflows.json me rules: {name, when:{metric, below/above}, then:{tool, args}}.
evaluate() ko scheduler-poll ya manual check se chalao. Existing tools reuse, kuch naya overwrite nahi.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

_RULES_FILE = Path(__file__).resolve().parent.parent / "config" / "workflows.json"
_last_fire: dict = {}


def _log(player, msg: str) -> None:
    try:
        if player:
            player.write_log(msg)
    except Exception:
        pass
    print(msg)


def _audit(action: str, detail: str = "") -> None:
    try:
        from core.audit import log_event as _ae
        _ae(action, detail)
    except Exception:
        pass


def _load() -> list:
    try:
        if _RULES_FILE.exists():
            data = json.loads(_RULES_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def _save(rules: list) -> None:
    try:
        _RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
        _tmp = _RULES_FILE.with_suffix(".json.tmp")
        _tmp.write_text(json.dumps(rules[-50:], indent=2, ensure_ascii=False), encoding="utf-8")
        import os as _os
        _os.replace(str(_tmp), str(_RULES_FILE))
    except Exception:
        pass


def _metrics() -> dict:
    m: dict = {}
    try:
        import psutil as _ps
        m["battery"] = (_ps.sensors_battery().percent if _ps.sensors_battery() else None)
        m["ram"] = _ps.virtual_memory().percent
        m["cpu"] = _ps.cpu_percent(interval=None)
    except Exception:
        pass
    try:
        m["hour"] = int(time.strftime("%H"))
    except Exception:
        pass
    return m


def _cond_ok(when: dict, m: dict) -> bool:
    try:
        metric = str(when.get("metric", "") or "").lower()
        if metric not in m or m[metric] is None:
            return False
        v = float(m[metric])
        if "below" in when and v >= float(when["below"]):
            return False
        if "above" in when and v <= float(when["above"]):
            return False
        if "equals" in when and v != float(when["equals"]):
            return False
        return True
    except Exception:
        return False


def evaluate(player=None, cooldown: int = 900) -> str:
    """Sab rules check karo, fire hui to action chalao. Never raises."""
    rules = _load()
    if not rules:
        return "Koi workflow rule nahi hai."
    m = _metrics()
    fired = []
    for r in rules:
        try:
            nm = str(r.get("name", "rule"))
            if time.time() - _last_fire.get(nm, 0) < cooldown:
                continue
            if not _cond_ok(r.get("when", {}), m):
                continue
            then = r.get("then", {}) or {}
            tool = str(then.get("tool", "") or "")
            args = then.get("args", {}) or {}
            out = _run_tool(tool, args, player)
            _last_fire[nm] = time.time()
            fired.append(f"{nm}: {out[:80]}")
            _audit("workflow_fire", nm)
        except Exception:
            continue
    if player and fired:
        try:
            player.write_log(f"[workflow] {len(fired)} fired")
        except Exception:
            pass
    return ("Fired:\n" + "\n".join(fired)) if fired else "Koi rule match nahi hui."


def _run_tool(tool: str, args: dict, player=None) -> str:
    """Safe dispatch: sirf read-mostly + settings tools (destructive confirm-gated tools skip nahi — unka gate lagta hai)."""
    try:
        if tool == "computer_settings":
            from actions.computer_settings import computer_settings as _cs
            return str(_cs(args, player=player))
        if tool == "open_app":
            from actions.open_app import open_app as _oa
            return str(_oa(args, player=player))
        if tool == "reminder":
            from actions.reminder import reminder as _rm
            return str(_rm(args, player=player))
        return f"Unsupported workflow tool '{tool}' (computer_settings/open_app/reminder allowed)."
    except Exception as e:
        return f"Workflow action failed: {e}"


def workflows(parameters: dict | None = None, player=None, session_memory=None, **_) -> str:
    params = parameters or {}
    action = str(params.get("action", "list") or "list").lower().strip()
    if action in ("list", "show"):
        rules = _load()
        if not rules:
            return "Koi rule nahi. Bolo: 'agar battery 20 se kam to brightness 30'."
        return "Rules:\n" + "\n".join(
            f"{i+1}. {r.get('name')}: {r.get('when')} -> {r.get('then', {}).get('tool')}"
            for i, r in enumerate(rules))
    if action in ("check", "run", "evaluate"):
        return evaluate(player)
    if action in ("add", "create"):
        name = str(params.get("name", "") or "").strip()[:40] or f"rule{int(time.time()) % 10000}"
        metric = str(params.get("metric", "battery") or "battery").lower().strip()
        try:
            below = float(params.get("below", "nan"))
        except Exception:
            below = float("nan")
        try:
            above = float(params.get("above", "nan"))
        except Exception:
            above = float("nan")
        import math as _math
        when = {"metric": metric}
        if not _math.isnan(below):
            when["below"] = below
        if not _math.isnan(above):
            when["above"] = above
        then = {"tool": str(params.get("tool", "computer_settings") or "computer_settings"),
                "args": params.get("args") or {}}
        rules = _load()
        rules = [r for r in rules if r.get("name") != name]
        rules.append({"name": name, "when": when, "then": then})
        _save(rules)
        _audit("workflow_add", name)
        return f"Rule '{name}' save ho gayi."
    if action in ("delete", "remove", "cancel"):
        name = str(params.get("name", "") or "").strip()
        rules = [r for r in _load() if r.get("name") != name]
        _save(rules)
        return f"Rule '{name}' hata di."
    return "Unknown workflows action. Use list, add, check, delete."


TOOL = {
    "name": "workflows",
    "description": (
        "Conditional if-this-then-that automation rules (e.g. battery low -> brightness low). "
        "Trigger on 'agar battery kam to', 'workflow banao', 'rules dikhao'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "list | add | check | delete"},
            "name": {"type": "STRING", "description": "Rule name"},
            "metric": {"type": "STRING", "description": "battery | ram | cpu | hour"},
            "below": {"type": "STRING", "description": "Fire when metric below this"},
            "above": {"type": "STRING", "description": "Fire when metric above this"},
            "tool": {"type": "STRING", "description": "computer_settings | open_app | reminder"},
            "args": {"type": "OBJECT", "description": "Tool args dict"},
        },
        "required": ["action"],
    },
    "handler": workflows,
}
