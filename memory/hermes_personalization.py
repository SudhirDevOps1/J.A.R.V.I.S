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
    Produces zero-fluff, highly actionable behavioral guidance grounded in user memory.
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

    # Incorporate user facts from long_term.json
    try:
        lt_path = BASE_DIR / "memory" / "long_term.json"
        if lt_path.exists():
            lt_data = json.loads(lt_path.read_text(encoding="utf-8"))
            if isinstance(lt_data, dict):
                loc = lt_data.get("identity", {}).get("location", {}).get("value", "")
                browser = lt_data.get("preferences", {}).get("browser", {}).get("value", "")
                lang = lt_data.get("identity", {}).get("language_preference", {}).get("value", "")
                if loc:
                    lines.append(f"- User Location: {loc}.")
                if browser:
                    lines.append(f"- Preferred Host Browser: {browser}.")
                if lang:
                    lines.append(f"- Native Language Preference: {lang}.")
    except Exception:
        pass

    if quirks:
        lines.append(f"- Living Habits: {'; '.join(quirks[:4])}.")
    if inside_jokes:
        lines.append(f"- Shared Banter & Jokes: {'; '.join(inside_jokes[:3])}.")

    # Past corrections & lessons learned (Strict self-improvement guardrails)
    recent_corrections = load_corrections(limit=5)
    if recent_corrections:
        lines.append("[PAST USER CORRECTIONS & STRICT RULES LEARNED]")
        for c in recent_corrections:
            r = c.get("rule", "")
            if r:
                lines.append(f"- Rule: {r}")
        lines.append("- CRITICAL DIRECTIVE: The user explicitly corrected these behaviors. NEVER repeat these mistakes.")

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


# ─────────────────────────────────────────────────────────────────────────────
# Hermes 2.0: Continuous Intent & Workflow Learning
# ─────────────────────────────────────────────────────────────────────────────
LEARNED_INTENTS_PATH = BASE_DIR / "memory" / "learned_intents.json"
_intents_lock = threading.Lock()

CORRECTIONS_PATH = BASE_DIR / "memory" / "corrections.json"
_corrections_lock = threading.Lock()


def load_corrections(limit: int = 15) -> list[dict]:
    """Retrieve the recent list of user corrections and behavioral lessons."""
    if not CORRECTIONS_PATH.exists():
        return []
    with _corrections_lock:
        try:
            items = json.loads(CORRECTIONS_PATH.read_text(encoding="utf-8"))
            if isinstance(items, list):
                return items[-limit:]
        except Exception:
            pass
    return []


def save_correction(rule_or_mistake: str, user_text: str = "", category: str = "general") -> dict:
    """Record a user-provided correction or behavioral rule into persistent memory."""
    if not rule_or_mistake or not rule_or_mistake.strip():
        return {}
    entry = {
        "rule": rule_or_mistake.strip(),
        "user_statement": (user_text or rule_or_mistake).strip()[:200],
        "category": category,
        "recorded_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    CORRECTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _corrections_lock:
        try:
            items = []
            if CORRECTIONS_PATH.exists():
                try:
                    data = json.loads(CORRECTIONS_PATH.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        items = data
                except Exception:
                    items = []
            items.append(entry)
            items = items[-100:]  # Keep last 100 corrections safely
            CORRECTIONS_PATH.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"[Hermes] ⚠️ Error saving correction: {e}")

    # Register negative feedback in feedback.json so future personalization learns
    try:
        from memory.feedback import log_feedback
        log_feedback("down", f"User Correction: {rule_or_mistake[:120]}")
    except Exception:
        pass

    return entry


def clear_corrections() -> bool:
    """Clear past corrections safely."""
    with _corrections_lock:
        try:
            if CORRECTIONS_PATH.exists():
                CORRECTIONS_PATH.write_text("[]", encoding="utf-8")
            return True
        except Exception:
            return False


def load_learned_intents() -> dict:
    if not LEARNED_INTENTS_PATH.exists():
        return {}
    with _intents_lock:
        try:
            return json.loads(LEARNED_INTENTS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}


def save_learned_intent(phrase: str, tool_name: str, tool_args: dict) -> None:
    """Store dynamically learned user phrase to tool mapping so Needle/TriTier executes it forever."""
    if not phrase or not tool_name:
        return
    phrase_clean = phrase.lower().strip()
    data = load_learned_intents()
    data[phrase_clean] = {
        "tool": tool_name,
        "args": tool_args,
        "learned_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    with _intents_lock:
        try:
            LEARNED_INTENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
            LEARNED_INTENTS_PATH.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception as e:
            print(f"[Hermes] ⚠️ Error saving learned intent: {e}")


def match_learned_intent(text: str) -> Optional[tuple[str, dict]]:
    """Check if input text matches any dynamically learned user intent in <1ms."""
    if not text:
        return None
    data = load_learned_intents()
    if not data:
        return None
    t = text.lower().strip()
    # Exact match
    if t in data:
        item = data[t]
        return (item["tool"], item.get("args", {}))
    # Substring & fuzzy match (learned trigger contained in user sentence or high similarity)
    for k, item in data.items():
        if k in t:  # e.g. "suno na lofi coding vibe chalao please"
            return (item["tool"], item.get("args", {}))
        if len(t) >= 6 and len(k) >= 6:
            import difflib
            if difflib.SequenceMatcher(None, t, k).ratio() >= 0.85:
                return (item["tool"], item.get("args", {}))
    return None


def get_personal_profile_summary() -> str:
    """Return a rich spoken summary of what the assistant knows about the user."""
    profile = load_user_persona()
    corrections = load_corrections(limit=3)
    intents = load_learned_intents()

    parts = []
    intimacy = profile.get("intimacy_stage", "Partner")
    parts.append(f"Aapki profile summary: Humara connection level '{intimacy}' hai.")
    parts.append(f"Schedule: {profile.get('user_schedule', 'Developer')}.")
    topics = ", ".join(profile.get("favorite_topics", []))
    if topics:
        parts.append(f"Interests: {topics}.")
    quirks = profile.get("learned_quirks", [])
    if quirks:
        parts.append(f"Habits: {quirks[0]}.")
    if intents:
        parts.append(f"Maine {len(intents)} custom voice command(s) seekhe hain.")
    if corrections:
        parts.append(f"Aur {len(corrections)} lessons dhyan mein rakhe hain taaki aage koi galti na ho.")
    return " ".join(parts)


def get_learned_knowledge_summary() -> str:
    """Return summary of taught custom intents and past corrections."""
    intents = load_learned_intents()
    corrections = load_corrections(limit=5)
    out = []
    if intents:
        out.append("Taught Voice Triggers:")
        for phrase, info in intents.items():
            out.append(f"  • '{phrase}' → {info.get('tool')} ({info.get('args')})")
    else:
        out.append("Abhi koi custom voice trigger taught nahi hai.")

    if corrections:
        out.append("\nRecent Lessons & Corrections:")
        for c in corrections:
            out.append(f"  • {c.get('rule')} ({c.get('recorded_at')})")
    return "\n".join(out)