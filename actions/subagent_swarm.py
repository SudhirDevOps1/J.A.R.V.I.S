from __future__ import annotations

from typing import Any, Dict
from core.subagent_swarm import get_subagent_swarm

def subagent_swarm(
    parameters: dict,
    player=None,
    speak=None,
    response=None,
    session_memory=None,
) -> str:
    task = (parameters.get("task") or parameters.get("query") or "").strip()
    if not task:
        return "Please specify a task or research topic for the subagent swarm."

    if player:
        player.write_log(f"[Swarm] Dispatching sub-agents for: {task}")

    swarm = get_subagent_swarm()
    res = swarm.run(task, on_progress=lambda m: player.write_log(f"[Swarm] {m}") if player else None)
    return res.final_report or f"Swarm task completed in {res.duration_seconds}s."

TOOL = {
    "name": "subagent_swarm",
    "description": "Orchestrates autonomous multi-agent swarm (Researcher, Reverse Engineer, Self-Healer, Reporter) to scrape live web data, reverse-engineer APIs, build automation scripts, and self-heal errors in parallel.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "task": {
                "type": "STRING",
                "description": "The complex task, research topic, or reverse-engineering goal."
            }
        },
        "required": ["task"]
    },
    "handler": subagent_swarm,
}
