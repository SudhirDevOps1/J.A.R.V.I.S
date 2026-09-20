"""Agent Mode — multi-step conductor. New file, auto-discovered. Nothing existing touched.
Model-in-the-loop design (2026 voice-conductor pattern): plan banata hai, todo_agent
me persist karta hai, HUD par progress dikhata hai, model steps ek-ek karke execute
karta hai. Direct registry dispatch nahi — koi circular import risk nahi.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

_PLAN_FILE = Path(__file__).resolve().parent.parent / "config" / "agent_plans.json"


def _log(player, msg: str) -> None:
    try:
        if player:
            player.write_log(msg)
    except Exception:
        pass
    print(msg)


def _load_plans() -> list:
    try:
        if _PLAN_FILE.exists():
            data = json.loads(_PLAN_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def _save_plans(plans: list) -> None:
    try:
        _PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _tmp = _PLAN_FILE.with_suffix(".json.tmp")
        _tmp.write_text(json.dumps(plans[-50:], indent=2, ensure_ascii=False), encoding="utf-8")
        import os as _os
        _os.replace(str(_tmp), str(_PLAN_FILE))
    except Exception:
        pass


def _plan_goal(goal: str) -> list[str]:
    """Keyword planner (offline, zero-token). Model khud refine kar sakta hai."""
    g = (goal or "").lower()
    steps: list[str] = []
    if any(w in g for w in ("trip", "travel", "flight", "yatra", "tour")):
        steps = [
            "travel_transit: find transit routes, trains and flights",
            "web_search: hotels, attractions and weather research",
            "reminder: pack travel essentials checklist",
            "send_message: share trip itinerary draft",
        ]
    elif any(w in g for w in ("study", "learn", "course", "syllabus", "padhna", "notes", "tutorial", "guide", "roadmap", "plan", "java", "python", "javascript", "dsa", "cpp", "c++", "rust", "go", "sql")):
        steps = [
            f"web_search: core syllabus and topics for {goal}",
            f"file_controller: write comprehensive study plan and notes for {goal} to Desktop",
            f"obsidian_brain: sync {goal} notes to Obsidian vault",
            "open_app: notepad",
        ]
    elif any(w in g for w in ("setup", "dev", "project", "code")):
        steps = ["open_app: open code editor (routine)", "open_app: open browser",
                 "file_controller: create project folder", "todo_agent: track milestones"]
    elif any(w in g for w in ("morning briefing", "morning routine", "subah ka plan", "aaj ka din", "today briefing", "daily digest")) and not any(w in g for w in ("study", "learn", "course", "notes", "syllabus", "java", "python", "code", "coding")):
        steps = ["web_search: news headlines", "weather_report: today weather",
                 "recall_past_activities: yesterday recap", "reminder: today tasks"]
    else:
        steps = [
            f"web_search: key resources and structure for {goal}",
            f"file_controller: write detailed roadmap for {goal} to Desktop",
            f"todo_agent: track completion of {goal}",
        ]
    return steps


def agent_mode(parameters: dict | None = None, player=None, session_memory=None, **_) -> str:
    params = parameters or {}
    action = str(params.get("action", "plan") or "plan").lower().strip()
    goal = str(params.get("goal", "") or "").strip()

    if action in ("status", "list"):
        # 1. First check live memory in todo_agent
        try:
            from actions.todo_agent import _active_tasks, _tasks_lock
            with _tasks_lock:
                for tid, t in reversed(list(_active_tasks.items())):
                    if t.get("status") == "in_progress":
                        done = t.get("completed_steps", 0)
                        total = t.get("total_steps", 0)
                        cur = t.get("current_step", "starting")
                        return f"Plan '{t.get('goal')}' background mein run ho raha hai ({done}/{total} steps complete). Abhi chal raha hai: '{cur}'."
        except Exception:
            pass

        # 2. Check persistent plans
        plans = _load_plans()
        if not plans:
            return "Koi active agent plan nahi hai."
        last = plans[-1]
        done = sum(1 for s in last.get("steps", []) if s.get("done"))
        total = len(last.get("steps", []))
        st = last.get("status", "in_progress")

        if st == "completed" or (total > 0 and done >= total):
            res_lines = []
            for s in last.get("steps", []):
                if s.get("result"):
                    res_lines.append(f"• {s.get('text')}: {s.get('result')[:90]}")
            res_str = ("\n" + "\n".join(res_lines)) if res_lines else ""
            return f"Plan '{last.get('goal', '')}' successfully COMPLETE ho chuka hai ({total}/{total} steps done)!{res_str}"

        return f"Plan '{last.get('goal', '')}': {done}/{total} steps done ({st})."

    if action in ("cancel", "stop"):
        plans = _load_plans()
        if plans:
            plans[-1]["status"] = "cancelled"
            _save_plans(plans)
            # Also abort active memory task
            try:
                from actions.todo_agent import _active_tasks, _tasks_lock
                with _tasks_lock:
                    for tid, t in _active_tasks.items():
                        if t.get("status") == "in_progress":
                            t["abort"] = True
                            t["status"] = "cancelled"
            except Exception:
                pass
            _log(player, "[agent] plan cancelled")
            return "Agent plan cancel kar diya."
        return "Koi plan nahi tha."

    if not goal:
        return "Please specify a goal for agent mode."

    # Deduplication guard: only block if this goal is ACTUALLY running in memory right now!
    try:
        from actions.todo_agent import _active_tasks, _tasks_lock
        with _tasks_lock:
            for tid, t in _active_tasks.items():
                if t.get("status") == "in_progress" and t.get("goal", "").strip().lower() == goal.strip().lower():
                    prog = f"{t.get('completed_steps', 0)}/{t.get('total_steps', 0)}"
                    cur = t.get("current_step", "working")
                    return f"Agent plan for '{goal}' is already actively executing in background ({prog} steps done, on: '{cur}'). Say 'agent status'."
    except Exception:
        pass

    plans = _load_plans()
    steps = _plan_goal(goal)
    plan = {"goal": goal, "steps": [{"text": s, "done": False} for s in steps],
            "status": "in_progress", "at": time.strftime("%I:%M %p")}
    plans.append(plan)
    _save_plans(plans)
    # todo_agent me bhi persist (existing flow untouched, try/except)
    try:
        from actions.todo_agent import create_task as _ct
        _ct(goal, steps, player=player)
    except Exception:
        pass
    _log(player, f"[agent] plan '{goal}' ({len(steps)} steps)")
    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
    return (f"Agent plan ready for '{goal}' ({len(steps)} steps):\n{numbered}\n"
            f"Background mein execute ho raha hai, progress dekhne ke liye 'agent status' bolo.")


TOOL = {
    "name": "agent_mode",
    "description": (
        "Multi-step agent conductor for complex goals (trip plan, dev setup, day plan). "
        "Trigger on 'trip plan karo', 'agent mode', 'multi-step task'. "
        "Breaks goal into steps, persists plan, shows HUD progress. Do NOT use todo_agent directly for big goals."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "plan | status | cancel"},
            "goal": {"type": "STRING", "description": "Complex goal text"},
        },
        "required": ["action"],
    },
    "handler": agent_mode,
}
