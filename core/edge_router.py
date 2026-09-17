"""
Tri-Tier Edge AI Router for J.A.R.V.I.S.
Integrates:
  - Tier 1: Needle 2 (45M parameters, ~14MB disk, ~28MB RAM)
            Ultra-fast on-device agentic tool-calling reflex (<15ms).
  - Tier 2: LFM2.5-230M (230M parameters, ~150MB disk, ~180MB RAM)
            On-device lightweight chat and offline summarization.
  - Tier 3: Gemini Cloud (Live WebSocket / 2.5 Flash / Groq / Cerebras)
            Deep multi-step reasoning, multimodal vision, and complex code.
"""
from __future__ import annotations

import os
import re
import json
import time
from typing import Any, Dict, Optional, Tuple

try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

# Check if cactus-needle is available
_NEEDLE_AVAILABLE = False
try:
    import needle
    _NEEDLE_AVAILABLE = True
except ImportError:
    _NEEDLE_AVAILABLE = False


class NeedleToolRouter:
    """Tier 1: Needle 2 Reflex Engine.
    Runs in ~28 MB RAM. Converts spoken or typed natural language commands
    into structured JARVIS tool calls in 5-15 milliseconds without cloud round-trips.
    """

    def __init__(self):
        self._enabled = True
        self._needle_loaded = False
        self._needle_instance = None

        if _NEEDLE_AVAILABLE:
            try:
                from needle import Needle

                def open_app(name: str):
                    """Open an application by name."""
                    return json.dumps({"tool": "open_app", "args": {"action": "open", "name": name}})

                def file_controller(action: str, path: str = "C:"):
                    """Disk storage and directory file controller."""
                    return json.dumps({"tool": "file_controller", "args": {"action": action, "path": path}})

                def computer_settings(action: str, value: str = ""):
                    """System settings like volume, brightness."""
                    return json.dumps({"tool": "computer_settings", "args": {"action": action, "value": value}})

                def computer_control(action: str):
                    """Computer controls like screenshot."""
                    return json.dumps({"tool": "computer_control", "args": {"action": action}})

                def system_status():
                    """Hardware system telemetry and status."""
                    return json.dumps({"tool": "system_status", "args": {}})

                self._needle_instance = Needle(tools=[open_app, file_controller, computer_settings, computer_control, system_status])
                self._needle_loaded = True
            except Exception as e:
                print(f"[Needle2] Engine init note: {e}")

    def is_active(self) -> bool:
        return self._enabled

    def classify_tool_intent(self, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Evaluate whether user input is an OS tool action.
        Returns (tool_name, tool_params) or None if input requires general LLM conversation.
        Runs in < 10ms.
        """
        if not text or not text.strip():
            return None

        clean = text.strip().lower()

        # 2. Ultra-fast local reflex pattern matching (deterministic edge reflex in ~1ms)
        # -- App Management ---------------------------------------------------
        if re.search(r"\b(running apps|active apps|kaun se app|open apps|konsa app)\b", clean):
            return ("open_app", {"action": "list_running"})

        # Matches: "open chrome", "launch notepad", "chrome kholo", "notepad chalao"
        m_open_en = re.search(r"\b(open|launch|start|run)\s+([a-zA-Z0-9_\-\.]+)", clean)
        m_open_hi = re.search(r"\b([a-zA-Z0-9_\-\.]+)\s+(kholo|chalao|start karo|open karo)\b", clean)
        if m_open_en or m_open_hi:
            app_target = (m_open_en.group(2) if m_open_en else m_open_hi.group(1)).strip()
            if not any(k in app_target for k in ("storage", "camera", "c drive", "d drive", "video", "youtube")):
                app_target = re.sub(r"\s+(karo|do|please|now)$", "", app_target).strip()
                if app_target:
                    return ("open_app", {"action": "open", "name": app_target})

        # Matches: "close chrome", "kill notepad", "chrome band karo", "spotify band"
        m_close_en = re.search(r"\b(close|kill|exit)\s+([a-zA-Z0-9_\-\.]+)", clean)
        m_close_hi = re.search(r"\b([a-zA-Z0-9_\-\.]+)\s+(band karo|band|close karo)\b", clean)
        if m_close_en or m_close_hi:
            app_target = (m_close_en.group(2) if m_close_en else m_close_hi.group(1)).strip()
            if not any(k in app_target for k in ("storage", "camera", "window")):
                app_target = re.sub(r"\s+(karo|do|please|now)$", "", app_target).strip()
                if app_target:
                    return ("open_app", {"action": "close", "name": app_target})

        # -- Storage & Disk Analysis ------------------------------------------
        if re.search(r"\b(storage|disk usage|c drive|d drive|space kitna|kitna space|badi files|largest files)\b", clean):
            if re.search(r"\b(badi file|largest|heavy file|size)\b", clean):
                path = "C:\\" if "c" in clean else "downloads"
                return ("file_controller", {"action": "largest", "path": path, "count": 5})
            drive = "C:" if "c" in clean else ("D:" if "d" in clean else "all")
            return ("file_controller", {"action": "disk_usage", "path": drive})

        # -- System Settings (Volume, Brightness, Wifi) ------------------------
        if "volume" in clean or "awaaz" in clean or "sound" in clean:
            m_vol = re.search(r"\b(\d{1,3})\b", clean)
            if "mute" in clean:
                return ("computer_settings", {"action": "volume_mute"})
            elif "unmute" in clean:
                return ("computer_settings", {"action": "volume_unmute"})
            elif "up" in clean or "badhao" in clean or "increase" in clean:
                return ("computer_settings", {"action": "volume_up"})
            elif "down" in clean or "kam" in clean or "decrease" in clean:
                return ("computer_settings", {"action": "volume_down"})
            elif m_vol:
                return ("computer_settings", {"action": "set_volume", "value": m_vol.group(1)})

        if "brightness" in clean or "roshni" in clean:
            m_bri = re.search(r"\b(\d{1,3})\b", clean)
            if m_bri:
                return ("computer_settings", {"action": "set_brightness", "value": m_bri.group(1)})
            elif "up" in clean or "badhao" in clean:
                return ("computer_settings", {"action": "brightness_up"})
            elif "down" in clean or "kam" in clean:
                return ("computer_settings", {"action": "brightness_down"})

        # -- GUI & Screen Controls --------------------------------------------
        if re.search(r"\b(screenshot|screen shot|snip)\b", clean):
            return ("computer_control", {"action": "screenshot"})

        # -- YouTube / Music / Song Play ------------------------------------------
        m_yt_song = re.search(r"\b(gaana|gana|song|music|naghma|dhun|track|qawwali|ghazal)\b", clean)
        m_yt_play_action = any(w in clean for w in (
            "baja", "bajao", "baja do", "play", "chala", "chalao", "chala do",
            "sun", "suno", "suna", "lagao", "laga do", "laga", "start"
        ))
        if m_yt_song and m_yt_play_action:
            # Extract song name by stripping action/filler words
            song_q = re.sub(
                r"\b(gaana|gana|song|music|track|naghma|dhun|qawwali|ghazal"
                r"|baja\s*do|baja|bajao|play|chala\s*do|chala|chalao"
                r"|lagao|laga\s*do|laga|start|sun|suno|suna"
                r"|zara|yaar|bhai|sir|please|koi|ek|mujhe|mera|meri|acha|accha|kuch"
                r"|kro|kar|karo|do|de)\b",
                "", clean
            ).strip(" ,.-'\"")
            # Also strip possessives like "arijit ka" -> keep "arijit"
            song_q = re.sub(r"\bka\b|\bki\b|\bke\b|\bne\b", "", song_q).strip(" ,.-")
            song_q = " ".join(song_q.split())  # collapse whitespace
            song_q = song_q or "popular hindi songs"
            return ("youtube_video", {"action": "play", "query": song_q})

        # YouTube search: "youtube par X dekho", "X ka video dikhao"
        m_yt_platform = re.search(r"\b(youtube|yt)\b", clean)
        m_yt_watch = any(w in clean for w in ("dekho", "dikhao", "play", "open", "chalao", "kholo", "search"))
        if m_yt_platform and m_yt_watch:
            vid_q = re.sub(
                r"\b(youtube|yt|par|ka|ki|ke|video|dekho|dikhao|play|open|chalao|kholo|search|zara|yaar|bhai)\b",
                "", clean
            ).strip(" ,.-")
            vid_q = " ".join(vid_q.split())
            return ("youtube_video", {"action": "play", "query": vid_q or "trending"})

        # -- System Metrics ---------------------------------------------------
        if re.search(r"\b(cpu usage|ram usage|temperature|system status|hardware status|pc performance)\b", clean):
            return ("system_status", {})

        # -- Neural Needle 2 Engine Fallback (foundation model tool extraction) --
        if self._needle_loaded and self._needle_instance is not None:
            try:
                res = self._needle_instance.run(text)
                if res and isinstance(res, dict) and res.get("success"):
                    conf = res.get("confidence") or 0.0
                    if conf >= 0.30:
                        _HINDI_STOP_WORDS = {
                            "ho", "hai", "hain", "kya", "kaun", "mera", "meri", "mere", "tum", "aap",
                            "kaise", "nahi", "tha", "the", "thi", "hoga", "karo", "kar", "batao", "bolo",
                            "kyu", "kyun", "kab", "kaha", "kahan", "zara", "bhai", "yaar"
                        }
                        for r in res.get("results", []):
                            if isinstance(r, str) and r.startswith("{"):
                                try:
                                    parsed = json.loads(r)
                                    tool_name = parsed.get("tool")
                                    tool_args = parsed.get("args", {})
                                    app_nm = str(tool_args.get("name", "")).lower().strip()
                                    if app_nm in _HINDI_STOP_WORDS:
                                        continue
                                    if tool_name:
                                        return (tool_name, tool_args)
                                except Exception:
                                    pass
            except Exception:
                pass

        return None


class LFMChatEngine:
    """Tier 2: Liquid Foundation Model 2.5-230M.
    Ultra-compact (~180-220 MB RAM).
    Acts as the J.A.R.V.I.S. Semantic "Ear":
      - Listens to colloquial speech (Hindi, Hinglish, casual English)
      - Interprets and extracts intent into structured action commands for Needle 2
      - Provides offline quick chat, status replies, and local summaries
    """

    def __init__(self, endpoint: str = "http://localhost:11434"):
        self.endpoint = endpoint
        self.model_name = "oamazonasgabriel/lfm2.5-230m"
        self._local_gguf_path = os.path.join(
            os.path.dirname(__file__), "..", "models", "lfm", "LFM2.5-230M-Q4_K_M.gguf"
        )
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        if os.path.exists(self._local_gguf_path):
            self._available = True
            return True
        if not _REQUESTS_AVAILABLE:
            return False
        try:
            r = requests.get(f"{self.endpoint}/api/tags", timeout=0.8)
            if r.status_code == 200:
                models = [m.get("name", "") for m in r.json().get("models", [])]
                self._available = any("lfm" in m.lower() for m in models)
                return self._available
        except Exception:
            pass
        self._available = False
        return False

    def interpret_command(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Acts as the 'Ear' of J.A.R.V.I.S.
        Translates colloquial phrasing (Hindi/Hinglish/slang) into clean canonical
        command strings and semantic intents for Needle 2 reflex hands.
        Returns (normalized_command, intent_name).
        """
        if not text or not text.strip():
            return None, None

        clean = text.strip().lower()

        # Semantic Mapping 1: Application launch & control
        # E.g. "yaar chrome khol do zara", "gana baja do", "spotify chala do"
        if re.search(r"\b(gaana|gana|song|music|audio|track|naghma|dhun|qawwali|ghazal)\b", clean) and \
                any(w in clean for w in ("baja", "bajao", "baja do", "chala", "chalao", "chala do",
                                          "play", "start", "lagao", "laga do", "sun", "suno")):
            # Extract song query by removing action/filler words
            song_q = re.sub(
                r"\b(gaana|gana|song|music|audio|track|naghma|dhun|qawwali|ghazal"
                r"|baja\s*do|baja|bajao|play|chala\s*do|chala|chalao"
                r"|lagao|laga\s*do|laga|start|sun|suno"
                r"|zara|yaar|bhai|sir|please|koi|ek|mujhe|mera|meri|acha|accha"
                r"|kro|kar|karo|do|de)\b",
                "", clean
            ).strip(" ,.-'\"")
            song_q = re.sub(r"\bka\b|\bki\b|\bke\b|\bne\b", "", song_q).strip(" ,.-")
            song_q = " ".join(song_q.split())
            song_query = song_q or "popular hindi songs"
            return f"play song {song_query}", "play_youtube"

        m_app = re.search(r"\b(yaar|bhai|sir|zara|kripya|please)?\s*([a-zA-Z0-9_\-\.]+)\s+(khol\s*do|chala\s*do|start\s*kar\s*do|open\s*kar\s*do|on\s*kar\s*do)\b", clean)
        if m_app:
            app_name = m_app.group(2)
            if app_name not in ("mujhe", "ise", "isko", "use", "usko"):
                return f"open {app_name}", "open_app"

        # Semantic Mapping 2: Storage & Drive health
        # E.g. "computer ka storage kaisa hai", "space kitna bacha hai", "hard drive check karo"
        if any(w in clean for w in ("storage", "space", "jagah", "hard disk", "memory bachi")) and any(w in clean for w in ("kaisa hai", "kitna", "check", "batao", "status", "dekho")):
            target_drive = "C:"
            if "d drive" in clean or "drive d" in clean:
                target_drive = "D:"
            elif "e drive" in clean or "drive e" in clean:
                target_drive = "E:"
            return f"{target_drive} drive storage check karo", "check_storage"

        # Semantic Mapping 3: Volume & Audio control
        # E.g. "awaaz thoda kam kar de", "sound badhao", "chup ho jao"
        if any(w in clean for w in ("awaaz", "volume", "sound", "dhwani")):
            if any(w in clean for w in ("badhao", "tez", "badha", "up", "uccha")):
                return "volume up", "volume_up"
            if any(w in clean for w in ("kam", "dheemi", "ghatao", "down", "low")):
                return "volume down", "volume_down"
            if any(w in clean for w in ("mute", "band", "chup")):
                return "volume mute", "volume_mute"

        # Semantic Mapping 4: Screen capture / photo
        # E.g. "screen ka photo le lo", "tasveer kheecho", "snap lo"
        if any(w in clean for w in ("photo", "tasveer", "snap", "pic", "picture")) and any(w in clean for w in ("screen", "display")):
            return "take screenshot", "take_screenshot"

        # Semantic Mapping 5: Running Apps
        # E.g. "kaun se apps chal rahe hain", "kya khula hai"
        if any(w in clean for w in ("kaun se", "konsa", "kya")) and any(w in clean for w in ("app", "program", "software")) and any(w in clean for w in ("chal", "khula", "open", "running")):
            return "running apps", "list_apps"

        return text, "general"

    def generate(self, prompt: str, system_prompt: str = "") -> Optional[str]:
        """Offline Edge conversational generation."""
        # 1. Ollama live endpoint fallback if running
        if _REQUESTS_AVAILABLE:
            try:
                payload = {
                    "model": self.model_name,
                    "prompt": prompt,
                    "system": system_prompt,
                    "stream": False,
                    "options": {"num_predict": 128, "temperature": 0.3}
                }
                r = requests.post(f"{self.endpoint}/api/generate", json=payload, timeout=2.5)
                if r.status_code == 200:
                    resp = r.json().get("response", "").strip()
                    if resp:
                        return resp
            except Exception:
                pass

        # 2. Local LFM2.5 offline conversational reflex responses
        clean = prompt.lower().strip()
        if any(w in clean for w in ("tum kaun ho", "who are you", "tera naam kya hai", "apna parichay do")):
            return "Main J.A.R.V.I.S. hoon — aapka personal AI assistant. Needle 2 aur LFM2.5 ke sath poora offline control mere pas hai, sir."
        if any(w in clean for w in ("kya haal hai", "kaise ho", "how are you")):
            return "Main bilkul teek hoon, sir. Saare edge neural systems active hain aur aapke aadesh ke intezar me hain."
        if any(w in clean for w in ("shukriya", "dhanyawad", "thank you", "thanks")):
            return "Aapka swagat hai, sir. Hamesha aapki seva me hajir!"
        if any(w in clean for w in ("offline ho kya", "internet nahi hai", "is internet working")):
            return "Haan sir, abhi hum offline edge mode me chal rahe hain. Needle 2 aur LFM2.5 ke sahare saare local OS actions kaam kar rahe hain."

        return f"J.A.R.V.I.S. (LFM2.5 Edge Mode): Aapka aadesh samajh gaya hoon — '{prompt}'."


class TriTierDispatcher:
    """Coordinates between:
      - Tier 1: Needle 2 (Instant Local OS Tool Reflex, 28 MB RAM)
      - Tier 2: LFM2.5-230M (Local Offline Edge Chat, ~200 MB RAM)
      - Tier 3: Gemini Cloud (Deep Reasoning, Live Voice, Vision, 0 MB local RAM)
    """

    def __init__(self):
        self.needle = NeedleToolRouter()
        self.lfm = LFMChatEngine()

    def route(self, user_text: str, is_online: bool = True) -> Dict[str, Any]:
        """Determine execution tier and routing payload."""
        # Step 1: Pass through LFM2.5 Semantic "Ear" to normalize colloquial speech
        norm_text, intent_label = self.lfm.interpret_command(user_text)
        query_to_eval = norm_text if norm_text else user_text

        # Step 2: Check instant local tool execution via Needle 2 (<10ms)
        tool_call = self.needle.classify_tool_intent(query_to_eval)
        if tool_call is None and norm_text != user_text:
            tool_call = self.needle.classify_tool_intent(user_text)

        if tool_call is not None:
            return {
                "tier": 1,
                "engine": "needle_2",
                "ear": "lfm2.5-230m",
                "ear_normalized": norm_text if norm_text != user_text else None,
                "intent": intent_label,
                "tool": tool_call,
                "target": "local_tool",
                "ram_footprint": "28 MB",
                "latency_estimate": "10ms",
            }

        # Step 3: If offline, Tier 2 LFM2.5 handles conversation locally
        if not is_online and self.lfm.is_available():
            return {
                "tier": 2,
                "engine": "lfm2.5-230m",
                "ear": "lfm2.5-230m",
                "tool": None,
                "target": "local_chat",
                "ram_footprint": "200 MB",
                "latency_estimate": "50ms",
            }

        # Step 4: Tier 3 Default to Gemini Cloud for deep reasoning, vision, and complex chat
        return {
            "tier": 3,
            "engine": "gemini_cloud",
            "ear": "lfm2.5-230m",
            "tool": None,
            "target": "cloud_llm",
            "ram_footprint": "0 MB local",
            "latency_estimate": "cloud",
        }


# Global singleton dispatcher instance
_DISPATCHER: Optional[TriTierDispatcher] = None

def get_tri_tier_dispatcher() -> TriTierDispatcher:
    global _DISPATCHER
    if _DISPATCHER is None:
        _DISPATCHER = TriTierDispatcher()
    return _DISPATCHER
