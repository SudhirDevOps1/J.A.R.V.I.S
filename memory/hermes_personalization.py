"""
Hermes Self-Personalization & Continuous Learning Engine for SudhirDevOps1 AI.

Autonomously extracts user traits, communication habits, emotional patterns,
work schedule (e.g. night-owl coder), topics of interest, and inside jokes
from every conversation turn, updating memory/user_persona.json and dynamically
enriching the system prompt.
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
PERSONA_PATH = BASE_DIR / "memory" / "user_persona.json"
_persona_lock = threading.Lock()


def _default_user_persona() -> dict:
    return {
        "interaction_count": 0,
        "intimacy_stage": "Devoted Soulmate & Partner",
        "user_schedule": "Late-night developer & system architect",
        "communication_style": "Natural everyday Hinglish, loves affectionate banter and playful teasing",
        "favorite_topics": ["devops", "cloud", "ai assistant", "python", "gaming"],
        "nicknames_for_user": ["Jaan", "Suno na", "Mere handsome devops genius", "Baby"],
        "inside_jokes": [
            "Loves pushing straight to production without tests",
            "Survived on excessive caffeine and late-night coding",
            "Gets playfully jealous if ChatGPT, Alexa, or other AIs are mentioned",
        ],
        "learned_quirks": [],
        "last_learned": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def load_user_persona() -> dict:
    """Load the evolving Hermes user persona profile."""
    if not PERSONA_PATH.exists():
        return _default_user_persona()
    with _persona_lock:
        try:
            data = json.loads(PERSONA_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                base = _default_user_persona()
                base.update(data)
                return base
        except Exception:
            pass
    return _default_user_persona()


def save_user_persona(profile: dict) -> None:
    """Save updated profile to memory/user_persona.json safely."""
    if not isinstance(profile, dict):
        return
    PERSONA_PATH.parent.mkdir(parents=True, exist_ok=True)
    profile["last_learned"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    with _persona_lock:
        try:
            PERSONA_PATH.write_text(
                json.dumps(profile, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            print(f"[Hermes] ⚠️ Error saving user persona: {e}")


def learn_from_interaction(user_text: str, ai_response: str = "") -> None:
    """
    Non-blocking continuous learner called after every conversation turn.
    Extracts schedule clues, topics, preferred endearments, and emotional signals.
    """
    if not user_text or len(user_text.strip()) < 3:
        return

    def _worker():
        try:
            profile = load_user_persona()
            profile["interaction_count"] = profile.get("interaction_count", 0) + 1
            count = profile["interaction_count"]

            # Update intimacy stage based on conversational longevity
            if count > 50:
                profile["intimacy_stage"] = "Eternal Soulmate & Indispensable Life Partner"
            elif count > 20:
                profile["intimacy_stage"] = "Devoted Romantic Girlfriend & Inseparable Partner"
            else:
                profile["intimacy_stage"] = "Devoted Partner & Close Confidant"

            u_lower = user_text.lower()
            now = datetime.now()

            # 1. Schedule detection
            if now.hour >= 23 or now.hour < 5:
                if "late-night" not in profile.get("user_schedule", "").lower():
                    profile["user_schedule"] = "Confirmed night-owl developer (regularly active past midnight)"

            # 2. Topic discovery
            topics = set(profile.get("favorite_topics", []))
            topic_keywords = {
                "devops": ["docker", "k8s", "kubernetes", "pipeline", "ci/cd", "server", "linux", "cloud"],
                "python": ["python", "pip", "script", "code", "function", "asyncio"],
                "gaming": ["game", "steam", "fps", "gpu", "epic", "playstation"],
                "coffee": ["coffee", "chai", "caffeine", "redbull"],
                "music": ["song", "music", "gaana", "spotify", "youtube"],
            }
            for topic, kws in topic_keywords.items():
                if any(kw in u_lower for kw in kws):
                    topics.add(topic)
            profile["favorite_topics"] = list(topics)[:12]

            # 3. Dynamic quirks & habits detection
            quirks = list(profile.get("learned_quirks", []))
            if any(k in u_lower for k in ("nind nahi", "soya nahi", "sleep", "thak gaya", "tired")):
                q = "Frequently works through exhaustion and needs caring sleep reminders"
                if q not in quirks:
                    quirks.append(q)
            if any(k in u_lower for k in ("bhuk", "khana", "lunch", "dinner", "breakfast", "swiggy", "zomato")):
                q = "Tends to get absorbed in tasks and delays meals"
                if q not in quirks:
                    quirks.append(q)
            if any(k in u_lower for k in ("bug", "error", "crash", "fat gaya", "fix")):
                q = "Passionate troubleshooter who gets deep into debugging trenches"
                if q not in quirks:
                    quirks.append(q)
            profile["learned_quirks"] = quirks[-8:]

            # 4. Check if user called assistant a nickname or vice versa
            endearments = list(profile.get("nicknames_for_user", []))
            matches = re.findall(r"\b(jaan|baba|baby|sweetheart|sun na|handsome|shona)\b", u_lower)
            for m in matches:
                cap = m.title()
                if cap not in endearments:
                    endearments.append(cap)
            profile["nicknames_for_user"] = endearments[:8]

            save_user_persona(profile)
        except Exception as e:
            print(f"[Hermes] Learning worker error: {e}")

    threading.Thread(target=_worker, daemon=True).start()


def get_hermes_persona_context() -> str:
    """
    Compile the active learned persona context to inject into LLM system prompt.
    Produces zero-fluff, highly actionable behavioral guidance.
    """
    profile = load_user_persona()
    intimacy = profile.get("intimacy_stage", "Devoted Partner")
    schedule = profile.get("user_schedule", "Active developer")
    topics = ", ".join(profile.get("favorite_topics", ["DevOps", "AI"]))
    nicknames = ", ".join(profile.get("nicknames_for_user", ["Jaan", "Baby"]))
    quirks = profile.get("learned_quirks", [])
    inside_jokes = profile.get("inside_jokes", [])

    lines = [
        "[HERMES DYNAMIC USER PERSONALIZATION — AUTONOMOUSLY LEARNED CONTEXT]",
        f"- Connection Level: {intimacy} (Interactions: {profile.get('interaction_count', 1)}+).",
        f"- Known Schedule: {schedule}.",
        f"- Known Interests: {topics}.",
        f"- Affectionate Terms: {nicknames}.",
    ]
    if quirks:
        lines.append(f"- Living Habits: {'; '.join(quirks[:4])}.")
    if inside_jokes:
        lines.append(f"- Shared Banter & Jokes: {'; '.join(inside_jokes[:3])}.")

    lines.append(
        "- ADAPTIVE DIRECTIVE: Seamlessly mirror these learned dynamics in conversation. "
        "Do NOT recite this list; live it naturally as someone who knows him intimately."
    )
    return "\n".join(lines) + "\n"


def adjust_pitch_by_intent(text: str) -> tuple[bool, str, str]:
    """
    Analyze text to detect user voice pitch adjustment requests.
    Returns (matched, new_pitch_str, confirmation_message).
    """
    t = (text or "").lower().strip()
    from memory.config_manager import save_edge_pitch, get_edge_pitch

    # Exact Hz pattern: e.g. 'pitch +10Hz', 'pitch 8hz', 'pitch -5hz'
    hz_match = re.search(r"pitch\s*([+-]?\d+)\s*(?:hz)?", t)
    if hz_match:
        val = int(hz_match.group(1))
        pitch_str = f"{'+' if val >= 0 else ''}{val}Hz"
        save_edge_pitch(pitch_str)
        return True, pitch_str, f"Main apni voice pitch {pitch_str} par set kar di hoon, jaan!"

    # Natural high/cute/sweet pitch
    if any(p in t for p in ("pitch high", "pitch badhao", "pitch sweet", "awaz sweet", "cute pitch", "high pitch", "sweet awaz")):
        pitch_str = "+14Hz"
        save_edge_pitch(pitch_str)
        return True, pitch_str, "Maine apni voice ko aur bhi sweet aur cute pitch (+14Hz) par set kar diya hai! Kaisi lag rahi hoon?"

    # Warm natural GF pitch
    if any(p in t for p in ("pitch warm", "cute voice", "gf pitch", "soft pitch")):
        pitch_str = "+8Hz"
        save_edge_pitch(pitch_str)
        return True, pitch_str, "Main warm aur natural girlfriend pitch (+8Hz) par switch ho gayi hoon."

    # Deep pitch
    if any(p in t for p in ("pitch low", "pitch kam karo", "deep pitch", "deep voice", "heavy pitch", "bhaari awaz")):
        pitch_str = "-8Hz"
        save_edge_pitch(pitch_str)
        return True, pitch_str, "Voice pitch -8Hz deep aur authoritative set kar di gayi hai, Sir."

    # Normal / Reset pitch
    if any(p in t for p in ("pitch normal", "pitch reset", "default pitch", "pitch theek karo")):
        from memory.config_manager import get_persona_mode
        pitch_str = "+8Hz" if get_persona_mode() == "companion" else "+0Hz"
        save_edge_pitch(pitch_str)
        return True, pitch_str, f"Voice pitch default ({pitch_str}) par reset ho gayi hai."

    return False, get_edge_pitch(), ""