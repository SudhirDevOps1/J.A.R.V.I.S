"""
Self-Learning & Continuous Improvement Engine for J.A.R.V.I.S.
Enables voice and text teaching, mistake correction, and personalized profile queries.
Automatically saves custom voice triggers to memory/learned_intents.json and lessons
to memory/corrections.json so the assistant continuously evolves with zero regressions.
"""
from __future__ import annotations

import json
from typing import Any, Dict


def self_learning(
    parameters: dict | None = None,
    player=None,
    session_memory=None,
    **_,
) -> str:
    from memory.hermes_personalization import (
        save_learned_intent,
        save_correction,
        load_corrections,
        clear_corrections,
        load_learned_intents,
        get_personal_profile_summary,
        get_learned_knowledge_summary,
        LEARNED_INTENTS_PATH,
    )

    params = parameters or {}
    action = str(params.get("action", "show_learned") or "show_learned").lower().strip()
    phrase = str(params.get("phrase", "")).strip()
    command = str(params.get("command", params.get("target", ""))).strip()
    feedback = str(params.get("feedback", params.get("rule", ""))).strip()

    # 1. Teach Mode ("jab main X bolu to Y karo")
    if action in ("teach", "learn", "custom_command"):
        if not phrase:
            return "Aap kis voice phrase ko teach karna chahte hain? Phrase specify karein."
        if not command:
            return f"Jab aap '{phrase}' bologe, tab mujhe kya karna chahiye? Target command batao."

        # Parse target command using Needle router
        resolved_tool = "open_app"
        resolved_args: Dict[str, Any] = {"action": "open", "name": command}

        try:
            from core.edge_router import NeedleToolRouter
            router = NeedleToolRouter()
            parsed = router.classify_tool_intent(command)
            if parsed:
                resolved_tool, resolved_args = parsed
        except Exception:
            pass

        save_learned_intent(phrase, resolved_tool, resolved_args)
        if player and hasattr(player, "write_log"):
            player.write_log(f"⚡ [Self-Learning]: Learned '{phrase}' → {resolved_tool} ({resolved_args})")
        return (
            f"Maine seekh liya! Aage se jab bhi aap '{phrase}' bologe, "
            f"main turant '{command}' execute karungi."
        )

    # 2. Mistake Correction Mode ("ye galat hai, aage se X karo")
    if action in ("correct", "correction", "mistake", "galti"):
        rule_text = feedback or phrase or command or "User reported mistake on previous action"
        save_correction(rule_text, user_text=rule_text)
        if player and hasattr(player, "write_log"):
            player.write_log(f"🧠 [Self-Improvement]: Recorded lesson '{rule_text[:80]}'")
        return (
            "I'm sorry, meri galti thi! Maine ise note kar liya hai aur apni memory mein save kar liya hai. "
            "Aage se main dhyan rakhungi aur yeh galti bilkul nahi dohraungi."
        )

    # 3. Show Personalized Profile ("tum mere bare mein kya jante ho")
    if action in ("show_profile", "profile", "user_profile"):
        summary = get_personal_profile_summary()
        if player and hasattr(player, "write_log"):
            player.write_log(f"👤 [Hermes Profile]: {summary}")
        return summary

    # 4. Show Learned Commands & Lessons ("apni learning batao")
    if action in ("show_learned", "learned", "intents"):
        return get_learned_knowledge_summary()

    # 5. Show Past Corrections ("apni galtiyan dikhao")
    if action in ("show_corrections", "corrections", "lessons"):
        corrs = load_corrections(limit=10)
        if not corrs:
            return "Abhi memory mein koi active corrections nahi hain, sab smoothly chal raha hai."
        lines = ["Recent Lessons & Corrections Learned:"]
        for i, c in enumerate(corrs, 1):
            lines.append(f"{i}. {c.get('rule')} (Saved: {c.get('recorded_at', 'recently')})")
        return "\n".join(lines)

    # 6. Forget Custom Intent or Corrections
    if action in ("forget", "delete", "remove"):
        if phrase in ("corrections", "all_corrections", "galtiyan"):
            clear_corrections()
            return "Saari purani corrections clear kar di gayi hain."
        if phrase:
            try:
                data = load_learned_intents()
                p_clean = phrase.lower().strip()
                if p_clean in data:
                    del data[p_clean]
                    LEARNED_INTENTS_PATH.write_text(
                        json.dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    return f"Custom intent '{phrase}' ko memory se bhula diya gaya hai."
                return f"Intent '{phrase}' memory mein nahi mila."
            except Exception as e:
                return f"Error forgetting intent: {e}"
        return "Kaun sa phrase bhulana hai? Phrase ka naam batayein."

    return get_learned_knowledge_summary()


TOOL = {
    "name": "self_learning",
    "description": (
        "Self-improvement, mistake correction, and autonomous learning engine for JARVIS. "
        "Trigger on 'jab main X bolu to Y karo', 'ye galat hai', 'aage se dhyan rakhna', "
        "'tum mere bare mein kya jante ho', 'apni learning batao', 'meri profile batao'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "teach | correct | show_profile | show_learned | show_corrections | forget",
            },
            "phrase": {
                "type": "STRING",
                "description": "Voice trigger phrase to learn or forget (e.g. 'coding night')",
            },
            "command": {
                "type": "STRING",
                "description": "Target action/command to execute when phrase is spoken",
            },
            "feedback": {
                "type": "STRING",
                "description": "Correction details or mistake rule to remember",
            },
        },
        "required": ["action"],
    },
    "handler": self_learning,
}
