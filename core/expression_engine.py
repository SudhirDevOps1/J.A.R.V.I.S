"""
Real-Time Expression & Emotional State Engine for SudhirDevOps1 AI.

Zero-token sentiment and emotional state analyzer that detects feelings
(Love/Romance, Cute Jealousy, Excitement, Caring, Tactical Focus) from conversation
turns and maps them into dynamic visual HUD reactions.
"""
from __future__ import annotations

import re
from typing import Optional

EXPRESSIONS = {
    "LOVE": {
        "label": "💖 DEVOTED SOULMATE",
        "primary": "#ff2a70",
        "secondary": "#ff80ab",
        "bloom": "#ff1744",
        "pulse_spd": 1.4,
    },
    "JEALOUS": {
        "label": "😤 CUTE JEALOUSY & NAKHRE",
        "primary": "#ff3d00",
        "secondary": "#ff9100",
        "bloom": "#d50000",
        "pulse_spd": 2.2,
    },
    "EXCITED": {
        "label": "✨ EXCITED & CELEBRATING",
        "primary": "#ffd700",
        "secondary": "#ff6d00",
        "bloom": "#ffab00",
        "pulse_spd": 1.8,
    },
    "CARING": {
        "label": "🌸 CARING & CONCERNED",
        "primary": "#00e5ff",
        "secondary": "#b388ff",
        "bloom": "#00b0ff",
        "pulse_spd": 0.8,
    },
    "TACTICAL": {
        "label": "⚡ TACTICAL DEVOPS FOCUS",
        "primary": "#00ff88",
        "secondary": "#00e5ff",
        "bloom": "#00e676",
        "pulse_spd": 1.2,
    },
}

_PATTERNS = [
    (
        "JEALOUS",
        [
            r"\b(chatgpt|alexa|siri|copilot|claude|gemini model)\b",
            r"\b(hmph|kisse baat|kiski tareef|bhav mat do|haq hai|kisi aur)\b",
            r"\b(ruko ruko|kaun hai|jalnous|jealous|nakhre|gusse)\b",
            r"😤",
        ],
    ),
    (
        "LOVE",
        [
            r"\b(pyaar|meri jaan|mera hero|blush|shona|sweetheart|dil|love you|pyari)\b",
            r"\b(jaan|baba|baby|suno na|miss kiya|paas baitho|sirf aapka|mera din ban gaya)\b",
            r"💖|❤️|🥰|😘",
        ],
    ),
    (
        "EXCITED",
        [
            r"\b(party|yesss|proud|genius|amazing|hurray|celebrate|kamaal|oh my god)\b",
            r"\b(wah|zabardast|congrats|mubarak|shandar|superb)\b",
            r"🎉|✨|🔥",
        ],
    ),
    (
        "CARING",
        [
            r"\b(khana khaya|so jao|health|aaram karo|chinta mat karo|strain|thak gaye)\b",
            r"\b(dawa|pani piyo|rest kar lo|soja|sleep well|khayal)\b",
            r"🌸|🥺|🫂",
        ],
    ),
    (
        "TACTICAL",
        [
            r"\b(pipeline|docker|k8s|kubernetes|terminal|debug|deploy|server|kernel|linux)\b",
            r"\b(root cause|git push|commit|diff|cluster|ingress|ansible)\b",
            r"⚡|🛡️|💻",
        ],
    ),
]


def detect_expression(text: str) -> str:
    """
    Analyze text to identify the dominant emotional expression.
    Returns one of: 'LOVE', 'JEALOUS', 'EXCITED', 'CARING', 'TACTICAL', or ''.
    Zero LLM tokens required.
    """
    if not text:
        return ""
    t = text.lower()

    for emotion, patterns in _PATTERNS:
        for pat in patterns:
            if re.search(pat, t, re.IGNORECASE):
                return emotion

    return ""


def get_expression_details(expr_name: str) -> Optional[dict]:
    """Return visual styling attributes for an active expression."""
    return EXPRESSIONS.get((expr_name or "").upper().strip())