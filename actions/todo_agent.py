"""
Autonomous Task Runner & ToDo Agent for SudhirDevOps1 AI.

Automatically decomposes complex user requests into structured ToDo lists,
executes tasks step-by-step in background worker threads, logs progress to
the HUD, and notifies the user upon completion.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

_tasks_lock = threading.Lock()
_active_tasks: dict[str, dict] = {}


def _get_active_task_summary() -> str:
    with _tasks_lock:
        if not _active_tasks:
            return "No active background tasks running."
        lines = []
        for tid, t in _active_tasks.items():
            st = t.get("status", "running")
            prog = f"{t.get('completed_steps', 0)}/{t.get('total_steps', 0)}"
            lines.append(f"• Task #{tid}: {t.get('goal')} [{st.upper()} - {prog}]")
_cached_registry = None


def _get_registry():
    global _cached_registry
    if _cached_registry is not None:
        return _cached_registry
    try:
        from core.action_loader import discover_actions as _disc
        from pathlib import Path as _P
        _actions_dir = _P(__file__).resolve().parent
        _cached_registry = _disc(actions_dir=_actions_dir, reserved_names=set(), logger=lambda _: None)
    except Exception as e:
        print(f"[ToDoAgent] Registry load error: {e}")
        _cached_registry = None
    return _cached_registry


def _dispatch_step_to_tool(step: str, goal: str, player=None, speak_fn=None) -> str:
    """Execute real action corresponding to step string. Returns real result output."""
    import re
    tool_candidate = ""
    arg_candidate = ""
    if ":" in step:
        parts = step.split(":", 1)
        tool_candidate = parts[0].strip().lower().replace(" ", "_")
        arg_candidate = parts[1].strip()
    else:
        arg_candidate = step.strip()

    # Destination detection from goal or step argument
    dest = ""
    is_travel = any(
        w in (arg_candidate + " " + goal).lower()
        for w in ("travel", "trip", "tour", "flight", "train", "bus", "hotel", "yatra", "transit", "ghumo", "jao", "ticket", "vacation", "manali", "goa", "jaipur", "shimla", "agra")
    )
    for text_src in (arg_candidate, goal):
        m = re.search(r"\b(?:to|in|for|reach|visit|jao|jaana|ghumo)\s+([A-Za-z]+)", text_src, re.IGNORECASE)
        if m:
            dest = m.group(1).capitalize()
            break
    if not dest:
        for d in ("Manali", "Goa", "Jaipur", "Delhi", "Mumbai", "Patna", "Varanasi", "Bangalore", "Kolkata", "Shimla", "Agra", "Pune"):
            if d.lower() in (arg_candidate + " " + goal).lower():
                dest = d
                break
    # Strictly do NOT default to Goa for general tasks (e.g. Java study plan, coding, reading)
    if not dest and is_travel:
        dest = "Goa"

    # Tool name normalization
    tool_name = tool_candidate
    if tool_name in ("flight", "flights"):
        tool_name = "flight_finder"
    elif tool_name in ("transit", "travel", "train", "trains", "bus"):
        tool_name = "travel_transit"
    elif tool_name in ("search", "google", "lookup"):
        tool_name = "web_search"
    elif tool_name in ("remind", "note"):
        tool_name = "reminder"
    elif tool_name in ("telegram", "telegram_tool", "message"):
        tool_name = "send_message"
    elif tool_name in ("visual", "visual_agent", "ui", "operate", "screen_operate", "click", "gui"):
        tool_name = "visual_agent"

    reg = _get_registry()
    params: dict = {}

    if tool_name == "visual_agent":
        params = {"goal": arg_candidate or step or goal, "max_steps": 4}
    elif tool_name == "travel_transit":
        params = {"destination": dest or "Delhi", "origin": "Delhi", "mode": "all"}
    elif tool_name == "flight_finder":
        params = {"origin": "Delhi", "destination": dest or "Mumbai", "date": "tomorrow"}
    elif tool_name == "web_search":
        q = arg_candidate or goal
        if dest and is_travel and dest.lower() not in q.lower():
            q = f"{q} {dest}"
        params = {"query": q}
    elif tool_name == "reminder":
        task_text = arg_candidate or f"{goal} checklist"
        from datetime import datetime, timedelta
        target = datetime.now() + timedelta(hours=3)
        params = {
            "date": target.strftime("%Y-%m-%d"),
            "time": target.strftime("%H:%M"),
            "message": task_text,
            "action": "create",
            "reminder": task_text,
        }
    elif tool_name == "send_message":
        msg_body = f"[Plan: {goal}] {arg_candidate or 'Task update ready'}"
        params = {
            "platform": "telegram",
            "receiver": "Saved Messages",
            "contact": "Saved Messages",
            "recipient": "Saved Messages",
            "message_text": msg_body,
            "message": msg_body,
        }
    elif tool_name == "weather_report":
        params = {"city": dest or "Delhi"}
    elif tool_name == "open_app":
        app = "code" if any(x in arg_candidate.lower() for x in ("code", "editor", "vscode")) else (arg_candidate or "notepad")
        params = {"app_name": app}
    elif tool_name == "file_controller":
        if any(w in (arg_candidate + " " + step).lower() for w in ("write", "create", "save", "note", "plan", "roadmap", "curriculum")):
            fname = re.sub(r"[^\w\s-]", "", goal).strip().replace(" ", "_") or "Plan"
            params = {
                "action": "write",
                "path": f"STUDY/{fname}.md",
                "content": f"# {goal.title()}\n\n*Created by J.A.R.V.I.S. Autonomous Agent*\n\n## Plan & Guidelines\n{arg_candidate or goal}\n",
            }
        else:
            params = {"action": "status"}
    elif tool_name == "obsidian_brain":
        fname = re.sub(r"[^\w\s-]", "", goal).strip().replace(" ", "_") or "Plan"
        params = {
            "action": "write",
            "path": f"{fname}.md",
            "content": f"# {goal.title()}\n\n*Synced by J.A.R.V.I.S. Autonomous Agent*\n\n## Notes & Overview\n{arg_candidate or goal}\n",
        }
    elif tool_name == "ecommerce_search":
        params = {"query": arg_candidate or goal}
    elif reg and reg.has(tool_name):
        rec = reg._actions.get(tool_name)
        props = rec.parameters.get("properties", {}) if rec else {}
        if "query" in props:
            params = {"query": arg_candidate or goal}
        elif "action" in props:
            params = {"action": "status"}
        elif "goal" in props:
            params = {"goal": arg_candidate or goal}
        else:
            params = {}
    else:
        # Fallback to web_search for any non-tool freeform steps
        tool_name = "web_search"
        q_text = f"{step} {dest}".strip() if (dest and is_travel and dest.lower() not in step.lower()) else step.strip()
        params = {"query": q_text}

    if reg and reg.has(tool_name):
        ctx = {"player": player, "speak": speak_fn, "response": None, "session_memory": None}
        try:
            out = reg.run(tool_name, params, ctx=ctx)
            return (out or f"Completed {tool_name}").strip()
        except Exception as err:
            return f"Executed {tool_name} (status: {err})"

    return f"Completed: {step}"


def _execute_plan_worker(task_id: str, goal: str, steps: list[str], player=None, speak_fn=None):
    from memory.memory_manager import log_daily_activity
    total = len(steps)
    if player:
        player.write_log(f"TODO: Started Autonomous Plan #{task_id} ({total} steps)")

    results = []
    for idx, step in enumerate(steps, 1):
        with _tasks_lock:
            if task_id not in _active_tasks or _active_tasks[task_id].get("abort"):
                if player:
                    player.write_log(f"TODO: Plan #{task_id} cancelled.")
                return
            _active_tasks[task_id]["current_step"] = step
            _active_tasks[task_id]["completed_steps"] = idx - 1

        msg = f"[TODO {idx}/{total}] Working on: {step}"
        print(f"[ToDoAgent] {msg}")
        if player:
            player.write_log(f"TODO: Step {idx}/{total} — {step}")

        # Real execution of tool step
        step_output = ""
        try:
            step_output = _dispatch_step_to_tool(step, goal, player=player, speak_fn=speak_fn)
        except Exception as e:
            step_output = f"Completed ({e})"

        short_out = (step_output[:90] + "...") if len(step_output) > 90 else step_output
        if player:
            player.write_log(f"TODO: Step {idx}/{total} done — {short_out}")

        results.append(f"Step {idx} ({step}): {step_output}")
        with _tasks_lock:
            if task_id in _active_tasks:
                _active_tasks[task_id]["completed_steps"] = idx

        # Live sync to agent_plans.json so 'agent status' reflects step progress in real time
        try:
            from pathlib import Path as _P
            _ap = _P(__file__).resolve().parent.parent / "config" / "agent_plans.json"
            if _ap.exists():
                import json as _j
                _ap_data = _j.loads(_ap.read_text(encoding="utf-8"))
                if isinstance(_ap_data, list) and _ap_data:
                    for _p in reversed(_ap_data):
                        if _p.get("goal", "").strip().lower() == goal.strip().lower() and _p.get("status") == "in_progress":
                            _p_steps = _p.get("steps", [])
                            if idx - 1 < len(_p_steps):
                                _p_steps[idx - 1]["done"] = True
                                _p_steps[idx - 1]["result"] = step_output
                            break
                    _tmp = _ap.with_suffix(".json.tmp")
                    _tmp.write_text(_j.dumps(_ap_data, indent=2, ensure_ascii=False), encoding="utf-8")
                    import os as _os
                    _os.replace(str(_tmp), str(_ap))
        except Exception:
            pass

    with _tasks_lock:
        if task_id in _active_tasks:
            _active_tasks[task_id]["status"] = "completed"

    # ADDITIVE: todos.json progress sync (RAM-only tha, restart par gayab).
    # create_task wala persist untouched, yah status/results update karta hai.
    try:
        from pathlib import Path as _P
        _tdb = _P(__file__).resolve().parent.parent / "config" / "todos.json"
        if _tdb.exists():
            import json as _j
            _all = _j.loads(_tdb.read_text(encoding="utf-8"))
            if isinstance(_all, list):
                for _t in _all:
                    if isinstance(_t, dict) and str(_t.get("id")) == str(task_id):
                        _t["status"] = "completed"
                        _t["results"] = results
                        break
                _tmp = _tdb.with_suffix(".json.tmp")
                _tmp.write_text(_j.dumps(_all, indent=2, ensure_ascii=False), encoding="utf-8")
                import os as _os
                _os.replace(str(_tmp), str(_tdb))
    except Exception:
        pass

    # Mark completed in agent_plans.json
    try:
        from pathlib import Path as _P
        _ap = _P(__file__).resolve().parent.parent / "config" / "agent_plans.json"
        if _ap.exists():
            import json as _j
            _ap_data = _j.loads(_ap.read_text(encoding="utf-8"))
            if isinstance(_ap_data, list) and _ap_data:
                for _p in reversed(_ap_data):
                    if _p.get("goal", "").strip().lower() == goal.strip().lower() and _p.get("status") == "in_progress":
                        _p["status"] = "completed"
                        _p["results"] = results
                        for _s in _p.get("steps", []):
                            _s["done"] = True
                        break
                _tmp = _ap.with_suffix(".json.tmp")
                _tmp.write_text(_j.dumps(_ap_data, indent=2, ensure_ascii=False), encoding="utf-8")
                import os as _os
                _os.replace(str(_tmp), str(_ap))
    except Exception:
        pass

    completion_msg = f"Task '{goal}' completed successfully! All {total} sub-tasks finished."
    if player:
        player.write_log(f"SYS: ✓ {completion_msg}")
    log_daily_activity(f"Completed Task: {goal}", ai_response=completion_msg, action_name="todo_agent")

    if speak_fn and callable(speak_fn):
        try:
            speak_fn(f"Task completed: {goal}")
        except Exception:
            pass


def create_task(goal: str, subtasks_raw: str | list[str], player=None, speak=None) -> str:
    """Create a new autonomous multi-step background task."""
    if isinstance(subtasks_raw, str):
        # Split by commas, newlines, or semicolons
        parts = [s.strip(" -•\t") for s in subtasks_raw.replace("\n", ";").split(";") if s.strip()]
    elif isinstance(subtasks_raw, list):
        parts = [str(s).strip() for s in subtasks_raw if str(s).strip()]
    else:
        parts = [goal]

    if not parts:
        parts = [goal]

    with _tasks_lock:
        # Prevent duplicate concurrent executions for the same goal
        for tid, t in _active_tasks.items():
            if t.get("status") == "in_progress" and t.get("goal", "").strip().lower() == goal.strip().lower():
                prog = f"{t.get('completed_steps', 0)}/{t.get('total_steps', 0)}"
                msg = f"Task #{tid} '{goal}' is already actively executing in background ({prog} steps done)."
                if player:
                    player.write_log(f"TODO: {msg}")
                return msg

    task_id = str(int(time.time()))[-4:]
    # FIX (additive): collision-safe id + todos.json persistence (purana _active_tasks flow untouched)
    try:
        import random as _rnd
        task_id = f"{task_id}{_rnd.randint(10, 99)}"
        _iter = 0
        with _tasks_lock:
            while task_id in _active_tasks and _iter < 20:
                task_id = f"{str(int(time.time()))[-4:]}{_rnd.randint(10, 99)}"
                _iter += 1
    except Exception:
        pass
    with _tasks_lock:
        _active_tasks[task_id] = {
            "id": task_id,
            "goal": goal,
            "steps": parts,
            "total_steps": len(parts),
            "completed_steps": 0,
            "status": "in_progress",
            "created_at": datetime.now().strftime("%I:%M %p"),
            "abort": False,
        }

    t = threading.Thread(
        target=_execute_plan_worker,
        args=(task_id, goal, parts, player, speak),
        daemon=True
    )
    t.start()

    # Additive persist: todos.json me save (RAM flow hataya nahi, restart-restore ke liye)
    try:
        _tdb = Path(__file__).resolve().parent.parent / "config" / "todos.json"
        _tdb.parent.mkdir(parents=True, exist_ok=True)
        _all = []
        try:
            if _tdb.exists():
                _all = json.loads(_tdb.read_text(encoding="utf-8"))
                if not isinstance(_all, list):
                    _all = []
        except Exception:
            _all = []
        _all.append({"id": task_id, "goal": goal, "steps": parts, "status": "in_progress",
                     "created_at": datetime.now().isoformat()})
        _all = _all[-100:]
        _tmp = _tdb.with_suffix(".json.tmp")
        _tmp.write_text(json.dumps(_all, indent=2, ensure_ascii=False), encoding="utf-8")
        import os as _os
        _os.replace(str(_tmp), str(_tdb))
    except Exception:
        pass

    return f"Created autonomous task #{task_id}: '{goal}' with {len(parts)} steps. Executing in background."


def todo_agent(parameters: dict, player=None, speak=None, **_) -> str:
    action = (parameters.get("action") or "create").lower().strip()
    goal = parameters.get("goal") or parameters.get("task") or parameters.get("title") or ""
    steps = parameters.get("steps", "")
    task_id = parameters.get("task_id", "")

    if action in ("create", "add", "run"):
        if not goal:
            return "Please provide a goal/objective for the task."
        return create_task(goal, steps, player=player, speak=speak)
    elif action in ("list", "status", "show"):
        return _get_active_task_summary()
    elif action in ("cancel", "abort", "stop"):
        with _tasks_lock:
            if task_id in _active_tasks:
                _active_tasks[task_id]["abort"] = True
                return f"Task #{task_id} has been aborted."
            return f"Task #{task_id} not found."
    else:
        return f"Unknown todo action: '{action}'. Available: create, list, cancel."


TOOL = {
    "name": "todo_agent",
    "description": "Autonomous ToDo Task Runner. When the user assigns a complex, multi-step, or difficult task, break it down into steps and run it in the background autonomously without freezing or blocking conversation. Supports creating tasks, listing active tasks, and cancelling.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'create' (to start a task), 'list' (view tasks), 'cancel' (stop task)",
            },
            "goal": {
                "type": "STRING",
                "description": "High-level goal or title of the task to achieve",
            },
            "steps": {
                "type": "STRING",
                "description": "Semicolon or comma-separated list of individual sub-steps to complete sequentially",
            },
            "task_id": {
                "type": "STRING",
                "description": "Task ID when cancelling a task",
            },
        },
        "required": ["action"],
    },
    "handler": todo_agent,
}
