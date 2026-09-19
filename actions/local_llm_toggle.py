"""
Local LLM Bridge Controller & Status Action.
Allows safe inspection and toggling of local LLMs (DeepSeek-R1 / Qwen2.5 / Ollama).
Defaults to disabled to prevent PC hang/freeze.
"""
from __future__ import annotations

from typing import Any, Dict

from core.local_llm_bridge import (
    check_local_llm_health,
    get_local_llm_config,
    is_local_llm_enabled,
    set_local_llm_enabled,
)


def local_llm_control(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """Action handler to enable, disable, or check status of local LLM."""
    params = parameters or {}
    action = str(params.get("action", "status")).strip().lower()

    if action in ("enable", "on", "start", "activate"):
        set_local_llm_enabled(True)
        health = check_local_llm_health(timeout=1.5)
        if health.get("online"):
            return (
                f"Local LLM Bridge enable kar diya gaya hai. Ollama online hai (Version: {health.get('version')}, "
                f"Model: {health.get('model')}, Ping: {health.get('latency_ms')}ms)."
            )
        else:
            return (
                f"Local LLM Bridge config me enable ho gaya hai, lekin localhost:11434 par Ollama offline hai. "
                f"System safe hai aur Gemini Cloud/Live use karta rahega."
            )

    elif action in ("disable", "off", "stop", "deactivate"):
        set_local_llm_enabled(False)
        return "Local LLM Bridge disable kar diya gaya hai. JARVIS exclusively Gemini Live & Cloud streaming use karega (Zero PC load)."

    # Default: status
    cfg = get_local_llm_config()
    enabled = cfg["enabled"]
    health = check_local_llm_health(timeout=1.5) if enabled else {"online": False}

    status_str = "ENABLED" if enabled else "DISABLED (Safe Mode)"
    health_str = f"ONLINE ({health.get('latency_ms')}ms)" if health.get("online") else "OFFLINE"

    return (
        f"Local LLM Bridge Status:\n"
        f"• Bridge: {status_str}\n"
        f"• Endpoint: {cfg['url']}\n"
        f"• Target Model: {cfg['model']}\n"
        f"• Ollama Service: {health_str}\n"
        f"• Default Engine: Gemini Live WebSocket & Gemini 2.5 Flash Cloud"
    )


TOOL = {
    "name": "local_llm_control",
    "description": "Checks status or toggles the safe, opt-in Local LLM Bridge (DeepSeek-R1 / Qwen2.5 / Ollama).",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'status', 'enable', or 'disable'."
            }
        },
        "required": []
    },
    "handler": local_llm_control,
}
