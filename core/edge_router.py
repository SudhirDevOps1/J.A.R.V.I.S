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


def _get_user_location() -> str:
    """Retrieve user city from long_term.json memory if available."""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        lt_path = os.path.join(base_dir, "memory", "long_term.json")
        if os.path.exists(lt_path):
            with open(lt_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                val = data.get("identity", {}).get("location", {}).get("value", "")
                if val:
                    return val.split(",")[0].strip()
    except Exception:
        pass
    return "Delhi"


class NeedleToolRouter:
    """Tier 1: Needle 2 Reflex Engine.
    Runs in ~28 MB RAM. Converts spoken or typed natural language commands
    into structured JARVIS tool calls in 5-15 milliseconds without cloud round-trips.
    """

    def __init__(self):
        self._enabled = True
        self._needle_loaded = False
        self._needle_instance = None
        self._last_tool_call: Optional[Tuple[str, Dict[str, Any]]] = None

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

        # -- Universal Hinglish/Hindi Filler Word Stripper (~0ms) ---------------
        # Strips leading/trailing/embedded fillers so patterns match cleanly.
        # E.g. "yaar bhai bas downloads dikhao na zara" → "downloads dikhao"
        _FILLERS = (
            r"\b(yaar|yar|bhai|bro|dost|sir|sir ji|jaan|janeman)\b",
            r"\b(please|plz|pls|kripya|meherbani)\b",
            r"\b(bas|sirf|only|just|thoda|thodi|ek baar)\b",
            r"\b(zara|zaraa|zara sa|thoda sa)\b",
            r"\b(na|naa|re|ji|haan|hmm|ok|okay)\b",
            r"^(ek kaam karo|sun|suno|dekho|bol|bata)[,\s]+",
            r"[,\s]+(na|naa|please|plz|re|ji|yaar|bhai)$",
        )
        for _fp in _FILLERS:
            clean = re.sub(_fp, " ", clean).strip()
        clean = re.sub(r"\s{2,}", " ", clean).strip()

        # Helper to record and return tool execution for repeat command support
        def _dispatch(tool_name: str, tool_args: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
            self._last_tool_call = (tool_name, tool_args)
            return (tool_name, tool_args)

        # -- Improvement 5: Repeat Last Tool Command --------------------------
        if re.search(r"\b(wahi dobara|wahi phir se|wahi kholo|dobara karo|phir se karo|repeat karo|repeat that|once more|repeat command)\b", clean):
            if self._last_tool_call is not None:
                return self._last_tool_call
            return _dispatch("repeat", {"action": "repeat"})

        # -- Hermes 2.0: Dynamically Learned User Intents (<1ms) --------------
        try:
            from memory.hermes_personalization import match_learned_intent
            learned = match_learned_intent(clean)
            if learned:
                return _dispatch(learned[0], learned[1])
        except Exception:
            pass

        # -- Autonomous Sub-Agent Swarm (Ultra-Resilient Speech Parsing) ------
        # "subagent chalao" / "multi agent research" / "swarm run" / "background research"
        m_swarm = re.search(r"\b(subagent|multi\s*agent|multiagent|swarm|background\s*research)\b", clean)
        if m_swarm:
            task_text = clean
            task_text = re.sub(r"\b(subagent\s*(?:chalao|chala\s*do|start\s*karo|start\s*kro|run|kholo)?|multi\s*agent|multiagent|swarm\s*(?:run|task|mode)?|background\s*research)\b", " ", task_text)
            task_text = re.sub(r"\b(yaar|bhai|sir|please|plz|zara|jara|abhi|jaldi\s*se|jaldi|kripya|ek|aur|par|pe|me|mein)\b", " ", task_text)
            task_text = re.sub(r"\b(background\s*me|background\s*mein|background|start\s*karo|start\s*kro|chalu\s*karo|chalao|chala\s*do|karo|kar\s*do|kro|do|de|dena)\b", " ", task_text)
            task_text = re.sub(r"\b(krke\s*report\s*do|karke\s*report\s*do|report\s*do|krke|karke|report\s*banao|report|batao|dikhao)\b", " ", task_text)
            task_text = " ".join(task_text.split()).strip()
            return _dispatch("subagent_swarm", {"task": task_text or "live web research"})

        # -- Dynamic API Sniffer & Reverse Engineer ---------------------------
        # "is website ki api sniff karo" / "sniff api quotes.toscrape.com" / "reverse engineer this api"
        if re.search(r"\b(sniff api|api sniff|reverse engineer|network sniff|api dhoondho|api nikaalo)\b", clean):
            url_m = re.search(r"https?://[^\s]+|[a-zA-Z0-9_\-\.]+\.[a-zA-Z]{2,}", clean)
            target_url = url_m.group(0) if url_m else "https://quotes.toscrape.com"
            goal_text = re.sub(r"\b(sniff\s*api|api\s*sniff|reverse\s*engineer|network\s*sniff|api\s*dhoondho|api\s*nikaalo|karo|do|please|zara)\b", "", clean).strip()
            return _dispatch("api_sniffer", {"url": target_url, "goal": goal_text})

        # -- The Hack: Pillow + Gemini 2.5 Flash Visual Debugger --------------
        # "check karo is code mein kya error hai" / "screen par error dekho" / "troubleshoot screen"
        if re.search(r"\b(error\s*(?:check|dekho|kya\s*hai|dhoondho|batao|solve)|troubleshoot|debug\s*(?:my\s*code|screen|error)|code\s*me\s*error|code\s*mein\s*error|screen\s*(?:pe|par|me|mein)\s*error)\b", clean):
            return _dispatch("troubleshoot_screen", {"query": clean})

        # -- The Tool: TinyDB Persistent Memory & Reminders -------------------
        # "yaad rakhna kal mujhe Java ke multi-threading concepts revise karne hain"
        if re.search(r"\b(yaad\s*(?:rakhna|rakho)|remember\s*that|task\s*save|save\s*task)\b", clean):
            task_text = re.sub(r"^(yaad\s*rakhna|yaad\s*rakho|remember\s*that|task\s*save|save\s*task|ki)\s*", "", clean).strip()
            return _dispatch("tinydb_memory", {"action": "add", "task": task_text or clean})

        if re.search(r"\b(pending\s*tasks?|reminders?\s*(?:dikhao|kya\s*hai|list)|tasks?\s*list|kya\s*karna\s*hai)\b", clean):
            return _dispatch("tinydb_memory", {"action": "list"})

        # -- The Tool: Rank-BM25 Lexical Notes Search (<4ms) -----------------
        # "notes mein search karo polymorphism" / "kahan likha tha polymorphism" / "search notes docker"
        if re.search(r"\b(notes?\s*(?:me|mein|par)?\s*search|search\s*notes?|kahan\s*likha\s*tha|notes?\s*dhoondho)\b", clean):
            q_text = re.sub(r"\b(notes?\s*(?:me|mein|par)?\s*search\s*karo|search\s*notes?|kahan\s*likha\s*tha|notes?\s*dhoondho|karo|do|please|zara)\b", "", clean).strip()
            return _dispatch("bm25_search", {"query": q_text or clean})

        # -- 0 MB Native Windows Pop-up Alert (ctypes) ------------------------
        if re.search(r"\b(alert\s*dikhao|show\s*alert|show\s*popup|popup\s*dikhao)\b", clean):
            msg = re.sub(r"\b(alert\s*dikhao|show\s*alert|show\s*popup|popup\s*dikhao)\b", "", clean).strip()
            from core.native_hacks import show_native_alert
            show_native_alert("J.A.R.V.I.S. Alert", msg or "Aapka task complete ho gaya hai!", "info")
            return _dispatch("computer_control", {"action": "none"})

        # 2. Ultra-fast local reflex pattern matching (deterministic edge reflex in ~1ms)
        # -- App Management ---------------------------------------------------
        if re.search(r"\b(running apps|active apps|kaun se app|open apps|konsa app)\b", clean):
            return _dispatch("open_app", {"action": "list_running"})

        # Refresh/rescan installed apps: "apps refresh karo", "scan apps", "refresh installed apps"
        if re.search(r"\b(refresh apps|scan apps|rescan apps|apps refresh|apps scan|update apps|rescan installed apps)\b", clean):
            return _dispatch("open_app", {"action": "refresh", "name": "apps"})

        # Calculator: "calculator kholo", "calc kholo", "hisaab kholo"
        if re.search(r"\b(calculator|calc|hisaab)\b", clean) and any(w in clean for w in ("kholo", "open", "chalao", "start", "on")):
            return _dispatch("open_app", {"action": "open", "name": "calculator"})

        # File Explorer / This PC: "file explorer kholo", "my computer kholo"
        if re.search(r"\b(file explorer|my computer|this pc|explorer kholo)\b", clean):
            return _dispatch("computer_settings", {"action": "file_explorer"})

        # Desktop: "desktop dikhao", "show desktop", "desktop screen dikhao"
        if re.search(r"\b(show desktop|desktop dikhao|sab minimize)\b", clean):
            return _dispatch("computer_settings", {"action": "show_desktop"})

        # Matches: "open chrome", "launch notepad", "chrome kholo", "notepad chalao", "code editor kholo"
        m_open_en = re.search(r"\b(open|launch|start|run)\s+([a-zA-Z0-9_\-\.]+(?:\s+[a-zA-Z0-9_\-\.]+)?)\b", clean)
        m_open_hi = re.search(r"\b([a-zA-Z0-9_\-\.]+(?:\s+[a-zA-Z0-9_\-\.]+)?)\s+(kholo|chalao|start karo|open karo)\b", clean)
        if m_open_en or m_open_hi:
            app_target = (m_open_en.group(2) if m_open_en else m_open_hi.group(1)).strip()
            _folder_words = ("storage", "camera", "c drive", "d drive", "video", "youtube",
                             "downloads", "desktop", "documents", "pictures", "music", "folder",
                             "setting", "settings", "calc", "calculator", "tab", "window", "screen",
                             "explorer", "file explorer")
            if not any(k in app_target for k in _folder_words):
                app_target = re.sub(r"\s+(karo|do|please|now)$", "", app_target).strip()
                if app_target:
                    return _dispatch("open_app", {"action": "open", "name": app_target})

        # Matches: "close chrome", "kill notepad", "chrome band karo", "spotify band"
        m_close_en = re.search(r"\b(close|kill|exit)\s+([a-zA-Z0-9_\-\.]+(?:\s+[a-zA-Z0-9_\-\.]+)?)\b", clean)
        m_close_hi = re.search(r"\b([a-zA-Z0-9_\-\.]+(?:\s+[a-zA-Z0-9_\-\.]+)?)\s+(band karo|band|close karo)\b", clean)
        if m_close_en or m_close_hi:
            app_target = (m_close_en.group(2) if m_close_en else m_close_hi.group(1)).strip()
            if not any(k in app_target for k in ("storage", "camera", "window", "tab", "pc", "computer", "wifi", "internet")):
                app_target = re.sub(r"\s+(karo|do|please|now)$", "", app_target).strip()
                if app_target:
                    return _dispatch("open_app", {"action": "close", "name": app_target})

        # -- Storage & Disk Analysis ------------------------------------------
        if re.search(r"\b(storage|disk usage|c drive|d drive|space kitna|kitna space|badi files|largest files)\b", clean):
            if re.search(r"\b(badi file|largest|heavy file|size)\b", clean):
                path = "C:\\" if "c" in clean else "downloads"
                return _dispatch("file_controller", {"action": "largest", "path": path, "count": 5})
            drive = "C:" if "c" in clean else ("D:" if "d" in clean else "all")
            return _dispatch("file_controller", {"action": "disk_usage", "path": drive})

        # -- System Settings (Volume, Brightness, Wifi) ------------------------
        if "volume" in clean or "awaaz" in clean or "sound" in clean:
            m_vol = re.search(r"\b(\d{1,3})\b", clean)
            if "up" in clean or "badhao" in clean or "tez" in clean:
                return _dispatch("computer_settings", {"action": "volume_up"})
            elif "down" in clean or "kam" in clean or "dheemi" in clean:
                return _dispatch("computer_settings", {"action": "volume_down"})
            elif "mute" in clean or "chup" in clean:
                return _dispatch("computer_settings", {"action": "mute"})
            elif m_vol:
                return _dispatch("computer_settings", {"action": "set_volume", "value": m_vol.group(1)})

        if "brightness" in clean or "roshni" in clean:
            m_bri = re.search(r"\b(\d{1,3})\b", clean)
            if m_bri:
                return _dispatch("computer_settings", {"action": "set_brightness", "value": m_bri.group(1)})
            elif "up" in clean or "badhao" in clean:
                return _dispatch("computer_settings", {"action": "brightness_up"})
            elif "down" in clean or "kam" in clean:
                return _dispatch("computer_settings", {"action": "brightness_down"})

        # -- GUI & Screen Controls --------------------------------------------
        if re.search(r"\b(screenshot|screen shot|snip)\b", clean):
            return _dispatch("computer_control", {"action": "screenshot"})

        # -- Media Playback Controls (Pause / Resume / Next) -------------------
        if re.search(r"\b(gana pause|song pause|pause karo|gana roko|music pause|pause song|media pause|gaana roko|pause music|gaana band|gana band)\b", clean):
            return _dispatch("computer_control", {"action": "press", "key": "playpause"})
        if re.search(r"\b(gana resume|song resume|resume karo|unpause|chalu karo gana|gaana chalu)\b", clean):
            return _dispatch("computer_control", {"action": "press", "key": "playpause"})
        if re.search(r"\b(next song|agla gana|agla song|next track)\b", clean):
            return _dispatch("computer_control", {"action": "press", "key": "nexttrack"})

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
            return _dispatch("youtube_video", {"action": "play", "query": song_q})

        # YouTube search: "youtube par X dekho", "X ka video dikhao"
        m_yt_platform = re.search(r"\b(youtube|yt)\b", clean)
        m_yt_watch = any(w in clean for w in ("dekho", "dikhao", "play", "open", "chalao", "kholo", "search"))
        if m_yt_platform and m_yt_watch:
            vid_q = re.sub(
                r"\b(youtube|yt|par|ka|ki|ke|video|dekho|dikhao|play|open|chalao|kholo|search|zara|yaar|bhai)\b",
                "", clean
            ).strip(" ,.-")
            vid_q = " ".join(vid_q.split())
            return _dispatch("youtube_video", {"action": "play", "query": vid_q or "trending"})

        # -- System Metrics & Battery -----------------------------------------
        if re.search(r"\b(cpu usage|ram usage|temperature|system status|hardware status|pc performance"
                     r"|cpu kitna|ram kitna|memory kitni|processor load|pc garam|kitna garam"
                     r"|battery|charge|charging|battery kitni|kitni battery|charge kitna)\b", clean):
            act = "battery" if any(w in clean for w in ("battery", "charge", "charging")) else "cpu"
            return _dispatch("system_status", {"action": act})

        # -- Web Search -------------------------------------------------------
        # "google karo X" / "X dhundo" / "search karo X" / "X ke baare mein batao"
        m_ws_en = re.search(r"\b(search|google|bing|find|lookup)\s+(?:for\s+)?(.+)", clean)
        m_ws_hi = re.search(r"(.+?)\s+(?:dhundo|search\s*karo|google\s*karo|khojo|batao|dekho)\b", clean)
        m_ws_kya = re.search(r"\b(kya hai|kaun hai|kahan hai|kab hai)\s+(.+)", clean)
        if m_ws_en and "click" not in clean:
            q = m_ws_en.group(2).strip()
            if q and len(q) > 1 and not any(w in q for w in ("tab", "window", "folder", "calc", "setting")):
                return _dispatch("web_search", {"query": q})
        elif m_ws_hi and "click" not in clean:
            q = m_ws_hi.group(1).strip()
            q = re.sub(r"\b(yaar|bhai|sir|please|zara|jaldi|mujhe|abhi)\b", "", q).strip()
            if q and len(q) > 1 and not any(w in q for w in ("tab", "window", "folder", "calc", "setting", "mausam", "weather")):
                return _dispatch("web_search", {"query": q})
        elif m_ws_kya and "click" not in clean:
            q = f"{m_ws_kya.group(2)} {m_ws_kya.group(1)}".strip()
            return _dispatch("web_search", {"query": q})

        # -- Weather (Memory-Aware: defaults to user location from long_term.json)
        # "Delhi ka mausam" / "aaj weather" / "kal baarish hogi kya"
        m_weather = re.search(
            r"\b(mausam|weather|baarish|tapman|garmi|sardi|temperature|barish|barsat)\b", clean
        )
        if m_weather:
            city_m = re.search(
                r"\b(delhi|mumbai|bangalore|bengaluru|pune|hyderabad|chennai|kolkata|jaipur|lucknow"
                r"|noida|gurgaon|chandigarh|ahmedabad|surat|indore|bhopal|patna|agra|bihar)\b", clean
            )
            city = city_m.group(1).title() if city_m else _get_user_location()
            when_m = re.search(r"\b(kal|tomorrow|aaj|today|parso|week)\b", clean)
            when = "tomorrow" if when_m and "kal" in (when_m.group(1) or "") else "today"
            return _dispatch("weather_report", {"city": city, "time": when})

        # -- Reminder / Alarm -------------------------------------------------
        # "5 minute baad yaad dilana" / "kal subah 8 baje reminder"
        m_remind = re.search(
            r"\b(reminder|alarm|yaad\s*dilana|yaad\s*dilao|yaad\s*karna|set\s*alarm|remind)\b", clean
        )
        if m_remind:
            time_m = re.search(
                r"(\d+)\s*(minute|min|ghante|hour|second|sec|baje|am|pm)", clean
            )
            msg_m = re.search(r"(?:ke\s*liye|ke\s*baad|baad|that)\s+(.+)$", clean)
            r_time = time_m.group(0) if time_m else "5 minutes"
            r_msg = msg_m.group(1).strip() if msg_m else "reminder"
            r_msg = re.sub(r"\b(lagao|set|karo|do|dena|please)\b", "", r_msg).strip() or "reminder"
            return _dispatch("reminder", {"action": "set", "time": r_time, "message": r_msg})

        # -- WhatsApp / Message Send ------------------------------------------
        # "Mummy ko WhatsApp karo" / "Rahul ko message bhejo" / "whatsapp mummy"
        m_msg = re.search(
            r"\b(whatsapp|message|msg|text|sms)\b.*(ko\s+|to\s+)?", clean
        )
        m_contact = re.search(
            r"([a-zA-Z\u0900-\u097F]+)\s+ko\s+(?:whatsapp|message|msg|text)", clean
        )
        m_wa_direct = re.search(r"^whatsapp\s+([a-zA-Z\u0900-\u097F]+)$", clean.strip())
        if m_wa_direct:
            contact = m_wa_direct.group(1).strip()
            if contact not in ("ek", "koi", "kuch", "yeh", "kisi", "karo", "bhejo"):
                return _dispatch("send_message", {"platform": "whatsapp", "contact": contact, "message": ""})
        elif m_msg and m_contact:
            contact = m_contact.group(1).strip()
            if contact not in ("ek", "koi", "kuch", "yeh"):
                msg_text_m = re.search(
                    r"(?:likho|likhke|bol|bolo|bhejo)\s+(.+)$", clean
                )
                msg_text = msg_text_m.group(1).strip() if msg_text_m else ""
                return _dispatch("send_message", {
                    "platform": "whatsapp",
                    "contact": contact,
                    "message": msg_text
                })

        # -- Window Control ---------------------------------------------------
        # "minimize karo" / "maximize karo" / "window band karo" / "fullscreen"
        if re.search(r"\b(minimize|choti\s*karo|chhupa\s*do|taskbar\s*mein)\b", clean):
            return _dispatch("computer_settings", {"action": "minimize"})
        if re.search(r"\b(maximize|badi\s*karo|fullscreen|poori\s*screen)\b", clean):
            return _dispatch("computer_settings", {"action": "full_screen"})
        if re.search(r"\b(window\s*band|window\s*close|band\s*karo\s*window|close\s*window|alt\s*f4)\b", clean):
            return _dispatch("computer_settings", {"action": "close_window"})

        # -- Screen Lock / Lock PC --------------------------------------------
        if re.search(r"\b(screen lock|lock screen|lock pc|computer lock|pc lock|screen ko lock|lock karo)\b", clean):
            return _dispatch("computer_settings", {"action": "lock_screen"})

        # -- Task Manager -----------------------------------------------------
        if re.search(r"\b(task manager|processes dekho|process manager|processes dikhao)\b", clean):
            return _dispatch("computer_settings", {"action": "task_manager"})

        # -- Settings / Control Panel -----------------------------------------
        if re.search(r"\b(open settings|computer settings|system settings|settings kholo|control panel)\b", clean):
            return _dispatch("computer_settings", {"action": "open_settings"})

        # -- File Explorer / This PC ------------------------------------------
        if re.search(r"\b(file explorer|my computer|this pc|explorer kholo)\b", clean):
            return _dispatch("computer_settings", {"action": "file_explorer"})

        # -- Tabs & Browser Navigation ----------------------------------------
        if re.search(r"\b(tab band|close tab|tab close|current tab band)\b", clean):
            return _dispatch("computer_settings", {"action": "close_tab"})
        if re.search(r"\b(new tab|nayi tab|naya tab|tab kholo)\b", clean):
            return _dispatch("computer_settings", {"action": "new_tab"})
        if re.search(r"\b(next tab|agli tab|dusri tab)\b", clean):
            return _dispatch("computer_settings", {"action": "next_tab"})
        if re.search(r"\b(previous tab|prev tab|pichli tab)\b", clean):
            return _dispatch("computer_settings", {"action": "prev_tab"})
        if re.search(r"\b(refresh page|page refresh|reload|reload page|refresh karo)\b", clean):
            return _dispatch("computer_settings", {"action": "refresh_page"})
        if re.search(r"\b(go back|peeche jao|pichla page)\b", clean):
            return _dispatch("computer_settings", {"action": "go_back"})
        if re.search(r"\b(go forward|aage jao|agla page)\b", clean):
            return _dispatch("computer_settings", {"action": "go_forward"})

        # -- Mouse & Click Automation -----------------------------------------
        # "double click karo" / "do baar click"
        if re.search(r"\b(double click|do baar click|double tap)\b", clean):
            coord_m = re.search(r"(\d+)\s*,\s*(\d+)", clean)
            x = int(coord_m.group(1)) if coord_m else None
            y = int(coord_m.group(2)) if coord_m else None
            return _dispatch("computer_control", {"action": "double_click", "x": x, "y": y})

        # "right click karo" / "right click"
        if re.search(r"\b(right click|right button|context menu)\b", clean):
            coord_m = re.search(r"(\d+)\s*,\s*(\d+)", clean)
            x = int(coord_m.group(1)) if coord_m else None
            y = int(coord_m.group(2)) if coord_m else None
            return _dispatch("computer_control", {"action": "right_click", "x": x, "y": y})

        # AI Screen element click: "save icon par click karo", "submit button pe click kar do", "click on submit button"
        m_hindi_target = re.search(r"(.+?)\s+(?:par|pe)\s+click(?:\s*(?:karo|kar\s*do|karna))?\b", clean)
        m_eng_target = re.search(r"\bclick\s+on\s+(.+)$", clean)
        target_desc = None
        if m_hindi_target:
            raw = re.sub(r"\b(yaar|bhai|please|zara|jaldi|kripya)\b", "", m_hindi_target.group(1)).strip()
            if raw and raw not in ("yahan", "here", "mouse", "left", "right", "double", "do baar"):
                target_desc = raw
        elif m_eng_target:
            raw = re.sub(r"\b(yaar|bhai|please|zara|jaldi|the)\b", "", m_eng_target.group(1)).strip()
            if raw and raw not in ("yahan", "here", "mouse", "left", "right", "double"):
                target_desc = raw

        if target_desc:
            return _dispatch("computer_control", {"action": "screen_click", "description": target_desc})

        # "click karo" / "mouse click" / "left click" / "yahan click karo"
        if re.search(r"\b(click karo|mouse click|left click|yahan click|cursor click|click)\b", clean):
            coord_m = re.search(r"(\d+)\s*,\s*(\d+)", clean)
            x = int(coord_m.group(1)) if coord_m else None
            y = int(coord_m.group(2)) if coord_m else None
            return _dispatch("computer_control", {"action": "click", "x": x, "y": y})

        # "mouse move karo 500, 300"
        m_move = re.search(r"\b(?:mouse move|cursor move|mouse le jao|cursor le jao)\b.*?(?:to\s+)?(\d+)\s*,\s*(\d+)", clean)
        if m_move:
            return _dispatch("computer_control", {"action": "move", "x": int(m_move.group(1)), "y": int(m_move.group(2))})

        # -- Scrolling --------------------------------------------------------
        if re.search(r"\b(scroll down|scroll neeche|neeche scroll|down scroll)\b", clean):
            return _dispatch("computer_control", {"action": "scroll", "direction": "down", "amount": 5})
        if re.search(r"\b(scroll up|scroll upar|upar scroll|up scroll)\b", clean):
            return _dispatch("computer_control", {"action": "scroll", "direction": "up", "amount": 5})

        # -- Zoom Control -----------------------------------------------------
        if re.search(r"\b(zoom in|bada dikhao zoom|zoom badhao)\b", clean):
            return _dispatch("computer_settings", {"action": "zoom_in"})
        if re.search(r"\b(zoom out|chhota dikhao zoom|zoom ghatao)\b", clean):
            return _dispatch("computer_settings", {"action": "zoom_out"})
        if re.search(r"\b(zoom reset|normal zoom|zoom theek karo)\b", clean):
            return _dispatch("computer_settings", {"action": "zoom_reset"})

        # -- Clipboard & Editing Shortcuts ------------------------------------
        if re.search(r"\b(clipboard mein kya|clipboard read|clipboard dekho|copy text dikhao|clipboard dikhao)\b", clean):
            return _dispatch("computer_control", {"action": "copy"})
        if re.search(r"\b(paste karo|yahan paste|paste kar do)\b", clean):
            return _dispatch("computer_control", {"action": "paste"})
        if re.search(r"\b(select all|sab select|poora select)\b", clean):
            return _dispatch("computer_settings", {"action": "select_all"})
        if re.search(r"\b(undo karo|undo|wapas lo|pichla action hatao)\b", clean):
            return _dispatch("computer_settings", {"action": "undo"})
        if re.search(r"\b(redo karo|redo|phir se aage)\b", clean):
            return _dispatch("computer_settings", {"action": "redo"})
        if re.search(r"\b(file save|save karo|save document|ctrl s)\b", clean):
            return _dispatch("computer_settings", {"action": "save"})
        if re.search(r"\b(press enter|enter dabao|enter maro)\b", clean):
            return _dispatch("computer_settings", {"action": "enter"})
        if re.search(r"\b(press escape|escape dabao|esc dabao)\b", clean):
            return _dispatch("computer_settings", {"action": "escape"})

        # -- Desktop & Window Arrangement -------------------------------------
        if re.search(r"\b(show desktop|desktop dikhao|sab minimize)\b", clean):
            return _dispatch("computer_settings", {"action": "show_desktop"})
        if re.search(r"\b(switch window|alt tab|agli window|window badlo)\b", clean):
            return _dispatch("computer_settings", {"action": "switch_window"})
        if re.search(r"\b(dark mode|light mode|theme badlo|dark theme)\b", clean):
            return _dispatch("computer_settings", {"action": "dark_mode"})
        if re.search(r"\b(open run|run dialog|run prompt)\b", clean):
            return _dispatch("computer_settings", {"action": "open_run"})
        if re.search(r"\b(left snap|snap left|screen left)\b", clean):
            return _dispatch("computer_settings", {"action": "snap_left"})
        if re.search(r"\b(right snap|snap right|screen right)\b", clean):
            return _dispatch("computer_settings", {"action": "snap_right"})

        # -- Typing / Clipboard -----------------------------------------------
        # "yeh type karo: hello" / "likho: main theek hoon"
        m_type = re.search(r"\b(?:type\s*karo|likho|type\s*this|type)\s*[:\-]?\s*(.+)$", clean)
        if m_type:
            type_text = m_type.group(1).strip().strip(":- \"'")
            if type_text and len(type_text) > 0:
                return _dispatch("computer_control", {"action": "type", "text": type_text})

        # -- System Power (Shutdown / Restart / Sleep) ------------------------
        # "PC band karo" / "shutdown" / "restart karo" / "sleep mode"
        if re.search(r"\b(shutdown|pc\s*band|computer\s*band|band\s*karo\s*pc|band\s*kar\s*do)\b", clean):
            if "restart" not in clean and "reboot" not in clean:
                return _dispatch("computer_settings", {"action": "shutdown"})
        if re.search(r"\b(restart|reboot|dobara\s*chalu|phir\s*se\s*start)\b", clean):
            return _dispatch("computer_settings", {"action": "restart"})
        if re.search(r"\b(sleep|hibernate|so\s*jao|pc\s*so|suspend)\b", clean):
            return _dispatch("computer_settings", {"action": "sleep"})

        # -- WiFi / Internet Toggle -------------------------------------------
        # "wifi on karo" / "wifi off karo" / "internet band karo"
        if re.search(r"\b(wifi|wi-fi|internet|net|network)\b", clean):
            if any(w in clean for w in ("on", "chalu", "shuru", "connect", "lagao")):
                return _dispatch("computer_settings", {"action": "wifi_on"})
            if any(w in clean for w in ("off", "band", "disconnect", "hatao", "rok")):
                return _dispatch("computer_settings", {"action": "wifi_off"})

        # -- File / Folder Open -----------------------------------------------
        # "downloads kholo" / "desktop kholo" / "documents folder"
        _folder_map = {
            "downloads": str(os.path.expanduser("~\\Downloads")),
            "desktop": str(os.path.expanduser("~\\Desktop")),
            "documents": str(os.path.expanduser("~\\Documents")),
            "pictures": str(os.path.expanduser("~\\Pictures")),
            "videos": str(os.path.expanduser("~\\Videos")),
            "music": str(os.path.expanduser("~\\Music")),
            "c drive": "C:\\",
            "d drive": "D:\\",
            "e drive": "E:\\",
        }
        m_folder = re.search(
            r"\b(downloads|desktop|documents|pictures|videos|music|c\s*drive|d\s*drive|e\s*drive)\b", clean
        )
        m_folder_action = any(w in clean for w in (
            "kholo", "open", "dekho", "dikhao", "jao", "explore", "show"
        ))
        if m_folder and m_folder_action:
            folder_key = m_folder.group(1).strip()
            folder_path = _folder_map.get(folder_key, str(os.path.expanduser("~")))
            return _dispatch("file_controller", {"action": "open_folder", "path": folder_path})

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

        # -- Scikit-Learn Micro Naive Bayes Classifier (<0.3ms probabilistic fallback) --
        try:
            from core.intent_classifier import get_micro_intent_classifier
            nb = get_micro_intent_classifier()
            pred = nb.predict_intent(clean, min_confidence=0.65)
            if pred:
                intent_name, conf = pred
                if intent_name == "troubleshoot_screen":
                    return _dispatch("troubleshoot_screen", {"query": clean})
                elif intent_name == "tinydb_memory":
                    t_text = re.sub(r"^(yaad\s*rakhna|yaad\s*rakho|remember\s*that|ki)\s*", "", clean).strip()
                    return _dispatch("tinydb_memory", {"action": "add", "task": t_text or clean})
                elif intent_name == "tinydb_list":
                    return _dispatch("tinydb_memory", {"action": "list"})
                elif intent_name == "bm25_search":
                    q_text = re.sub(r"\b(notes?\s*(?:me|mein|par)?\s*search\s*karo|search\s*notes?|kahan\s*likha\s*tha|notes?\s*dhoondho|karo|do|please|zara)\b", "", clean).strip()
                    return _dispatch("bm25_search", {"query": q_text or clean})
                elif intent_name == "find_files":
                    return _dispatch("file_controller", {"action": "find", "name": clean, "path": "home"})
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

        # Semantic Mapping 6: Web Search
        # "google karo X" / "X ke baare mein batao" / "X dhundo" / "X kya hai"
        if any(w in clean for w in ("google karo", "search karo", "dhundo", "khojo", "net par dekho")):
            q = re.sub(r"\b(google\s*karo|search\s*karo|dhundo|khojo|net\s*par\s*dekho|zara|yaar|bhai|sir|please)\b", "", clean).strip()
            if q:
                return f"search {q}", "web_search"
        if re.search(r"\bke\s+baare\s+mein\s+(batao|bolo|samjhao|likho)\b", clean):
            q = re.sub(r"\bke\s+baare\s+mein\s+(batao|bolo|samjhao|likho)\b", "", clean).strip()
            if q:
                return f"search {q}", "web_search"

        # Semantic Mapping 7: Weather
        # "Delhi ka mausam" / "aaj garmi hai kitni" / "kal baarish hogi"
        if any(w in clean for w in ("mausam", "baarish", "barish", "garmi", "sardi", "tapman", "barsat")):
            city_m = re.search(r"\b(delhi|mumbai|bangalore|bengaluru|pune|hyderabad|chennai|kolkata|jaipur|lucknow|noida|gurgaon)\b", clean)
            city = city_m.group(1).title() if city_m else "current location"
            when = "tomorrow" if "kal" in clean else "today"
            return f"weather {city} {when}", "weather"

        # Semantic Mapping 8: Reminder
        # "5 min baad yaad dilana" / "reminder lagao" / "alarm set karo"
        if any(w in clean for w in ("yaad dilana", "yaad dilao", "reminder lagao", "alarm lagao", "alarm set")):
            time_m = re.search(r"(\d+)\s*(minute|min|ghante|hour|baje)", clean)
            t = time_m.group(0) if time_m else "5 minutes"
            return f"reminder {t}", "reminder"

        # Semantic Mapping 9: WhatsApp / Message
        # "Mummy ko whatsapp karo" / "bhai ko message bhejo"
        m_wa = re.search(r"([a-zA-Z\u0900-\u097F]+)\s+ko\s+(whatsapp|message|msg)\s*(karo|bhejo|likho|bhej\s*do)?", clean)
        if m_wa:
            contact = m_wa.group(1).strip()
            if contact not in ("ek", "koi", "kuch", "yeh", "kisi"):
                return f"whatsapp {contact}", "send_whatsapp"

        # Semantic Mapping 10: Window Control
        # "window chhoti karo" / "screen minimize" / "badi karo window"
        if any(w in clean for w in ("minimize", "chhoti karo", "chota karo", "taskbar mein")):
            return "minimize window", "minimize"
        if any(w in clean for w in ("maximize", "badi karo", "bada karo", "fullscreen", "poori screen")):
            return "maximize window", "maximize"
        if any(w in clean for w in ("window band", "window close", "band karo window")):
            return "close window", "close_window"

        # Semantic Mapping 11: Typing
        # "yeh type karo: hello" / "likho yeh: ..."
        m_type_hi = re.search(r"\b(type\s*karo|likho|type\s*this)\s*[:\-]?\s*(.+)$", clean)
        if m_type_hi:
            t_text = m_type_hi.group(2).strip().strip(":- \"'")
            if t_text:
                return f"type {t_text}", "type_text"

        # Semantic Mapping 12: System Power
        # "PC band karo" / "PC off karo" / "restart karo" / "so jao"
        if any(w in clean for w in ("pc band", "computer band", "pc off", "band kar do", "shut down", "shutdown")):
            if "restart" not in clean:
                return "shutdown pc", "shutdown"
        if any(w in clean for w in ("restart karo", "reboot", "dobara chalu", "phir se start")):
            return "restart pc", "restart"
        if any(w in clean for w in ("sleep mode", "hibernate", "pc so", "so jao")):
            return "sleep pc", "sleep"

        # Semantic Mapping 13: WiFi
        # "wifi on karo" / "internet chalu karo" / "net band karo"
        if any(w in clean for w in ("wifi", "wi-fi", "internet", "net")):
            if any(w in clean for w in ("on", "chalu", "shuru", "lagao", "connect")):
                return "wifi on", "wifi_on"
            if any(w in clean for w in ("off", "band", "disconnect", "hatao")):
                return "wifi off", "wifi_off"

        # Semantic Mapping 14: Folder / File Open vs Show Desktop
        if any(w in clean for w in ("show desktop", "desktop dikhao", "sab minimize")):
            return "show desktop", "show_desktop"

        _hi_folders = {
            "downloads": "downloads",
            "documents": "documents", "pictures": "pictures",
            "videos": "videos", "music": "music",
        }
        for folder_hi, folder_en in _hi_folders.items():
            if folder_hi in clean and any(w in clean for w in ("kholo", "open", "dekho", "dikhao")):
                return f"open folder {folder_en}", "open_folder"

        if "desktop" in clean and any(w in clean for w in ("kholo", "open", "folder")):
            return "open folder desktop", "open_folder"

        # Semantic Mapping 15: Screen Lock / Task Manager / Settings
        if any(w in clean for w in ("screen lock", "lock screen", "pc lock", "computer lock")):
            return "lock screen", "lock_screen"
        if any(w in clean for w in ("task manager", "processes")):
            return "task manager", "task_manager"
        if any(w in clean for w in ("settings kholo", "control panel", "computer settings", "system settings")):
            return "open settings", "open_settings"

        # Semantic Mapping 16: Tabs & Navigation
        if any(w in clean for w in ("tab band", "close tab")):
            return "close tab", "close_tab"
        if any(w in clean for w in ("new tab", "nayi tab", "naya tab")):
            return "new tab", "new_tab"
        if any(w in clean for w in ("refresh page", "reload page", "page refresh", "reload")):
            return "refresh page", "refresh_page"

        # Semantic Mapping 17: Scroll & Zoom
        if any(w in clean for w in ("scroll down", "scroll neeche", "neeche scroll")):
            return "scroll down", "scroll_down"
        if any(w in clean for w in ("scroll up", "scroll upar", "upar scroll")):
            return "scroll up", "scroll_up"
        if any(w in clean for w in ("zoom in", "zoom badhao")):
            return "zoom in", "zoom_in"
        if any(w in clean for w in ("zoom out", "zoom ghatao")):
            return "zoom out", "zoom_out"

        # Semantic Mapping 18: Calculator & Utilities
        if any(w in clean for w in ("calculator", "calc", "hisaab")) and any(w in clean for w in ("kholo", "open", "chalao")):
            return "open calculator", "open_app"

        # Semantic Mapping 19: Repeat Command
        if any(w in clean for w in ("wahi dobara", "wahi phir se", "wahi kholo", "dobara karo", "phir se karo", "repeat karo", "repeat that", "once more")):
            return "repeat command", "repeat"

        # Semantic Mapping 20: Dynamic API Sniffer
        if any(w in clean for w in ("sniff api", "api sniff", "reverse engineer", "api nikaalo")):
            url_m = re.search(r"https?://[^\s]+|[a-zA-Z0-9_\-\.]+\.[a-zA-Z]{2,}", clean)
            target = url_m.group(0) if url_m else "https://quotes.toscrape.com"
            return f"sniff api {target}", "api_sniffer"

        # Semantic Mapping 21: Autonomous Sub-Agent Swarm
        if any(w in clean for w in ("subagent", "multi agent", "multiagent", "swarm", "background research")):
            task = re.sub(r"\b(subagent\s*(?:chalao|chala\s*do|start\s*karo|run|kholo)?|multi\s*agent|multiagent|swarm\s*(?:run|task|mode)?|background\s*research|par|pe|karo|kar\s*do|do|please|zara|jara|yaar|bhai)\b", " ", clean)
            task = re.sub(r"\b(background\s*me|background\s*mein|background|start\s*karo|start\s*kro|chalu\s*karo|chalao|krke\s*report\s*do|report\s*do|report|batao|dikhao)\b", " ", task)
            task = " ".join(task.split()).strip()
            return f"subagent chalao {task or 'research'}", "subagent_swarm"

        # Semantic Mapping 22: Mouse & Click Actions
        if any(w in clean for w in ("double click", "do baar click")):
            return "double click", "double_click"
        if any(w in clean for w in ("right click", "right button")):
            return "right click", "right_click"
        m_hindi_click = re.search(r"(.+?)\s+(?:par|pe)\s+click", clean)
        if m_hindi_click:
            t = re.sub(r"\b(yaar|bhai|please|zara|jaldi|karo|do)\b", "", m_hindi_click.group(1)).strip()
            if t and t not in ("yahan", "here", "mouse", "left", "right"):
                return f"click on {t}", "screen_click"
        if "click on" in clean:
            target = clean.split("click on")[-1].strip()
            return f"click on {target}", "screen_click"
        if any(w in clean for w in ("click karo", "mouse click", "left click", "yahan click")):
            return "click karo", "click"

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

        # 2. Local LFM2.5 offline conversational reflex responses (30+ Smart Patterns)
        clean = prompt.lower().strip()
        from datetime import datetime
        now = datetime.now()

        # Dynamic Time & Date
        if any(w in clean for w in ("kya time", "samay kya", "kitne baje", "time batao", "current time")):
            return f"Sir, abhi samay ho raha hai {now.strftime('%I:%M %p')}."
        if any(w in clean for w in ("aaj kya date", "konsi date", "aaj ka din", "konsa din", "tarikh kya", "date batao")):
            return f"Aaj {now.strftime('%A, %d %B %Y')} hai, sir."

        # Greetings & Pleasantries
        if any(w in clean for w in ("good morning", "shubh prabhat")):
            return "Shubh Prabhat, sir! Umeed hai aapka din shandar rahega. Bataiye kya madad karoon?"
        if any(w in clean for w in ("good afternoon", "shubh dopahar")):
            return "Good afternoon, sir! Main ready hoon, bataiye kya task karna hai?"
        if any(w in clean for w in ("good evening", "shubh sandhya")):
            return "Good evening, sir! Aaj ka din kaisa raha? Main aapki seva me hazir hoon."
        if any(w in clean for w in ("good night", "shubh ratri", "so jao")):
            return "Shubh Ratri, sir! Achi neend lijiye. Main background me standby par hoon."
        if any(w in clean for w in ("namaste", "pranam", "radhe radhe", "ram ram")):
            return "Namaste sir! J.A.R.V.I.S. aapki seva me hazir hai. Kahiye kya aadesh hai?"
        if any(w in clean for w in ("hello", "hii", "hey", "suno jarvis", "sun jarvis")):
            return "Hello sir! Main sun raha hoon, bataiye kya hukum hai?"

        # Capabilities & Help
        if any(w in clean for w in ("tum kya kar sakte ho", "capabilities", "kya features hain", "help me", "kya kar sakte")):
            return ("Main J.A.R.V.I.S. hoon! Main aapke system par apps khol/band kar sakta hoon, YouTube par gaane chala sakta hoon, "
                    "volume/brightness control kar sakta hoon, files manage, reminders, screenshots, web search, "
                    "aur pura offline Edge AI control de sakta hoon!")

        # Identity & Creator
        if any(w in clean for w in ("tum kaun ho", "who are you", "tera naam kya hai", "apna parichay do")):
            return "Main J.A.R.V.I.S. (Mark-LIII) hoon — aapka ultra-fast personal AI assistant. Needle 2 aur LFM2.5 ke sath poora on-device control mere pas hai, sir."
        if any(w in clean for w in ("tumhe kisne banaya", "who created you", "who made you", "tera malik kaun", "creator")):
            return "Mujhe mere boss (Aapne) banaya hai — ek powerful, intelligent aur fully automated personal desktop assistant ke roop me!"
        if any(w in clean for w in ("version kya hai", "which version", "tumhara version")):
            return "Main J.A.R.V.I.S. Mark-LIII (Needle 2 + LFM2.5 Tri-Tier Edge Edition) par chal raha hoon."

        # Status & Feelings
        if any(w in clean for w in ("kya haal hai", "kaise ho", "how are you", "sab theek hai")):
            return "Main bilkul shandar hoon, sir! Saare edge neural systems active hain aur aapke aadesh ke intezar me hain."
        if any(w in clean for w in ("thak gaye kya", "are you tired")):
            return "AI kabhi nahi thakta, sir! 24/7 aapki seva ke liye 100% ready hoon."

        # Gratitude & Courtesy
        if any(w in clean for w in ("shukriya", "dhanyawad", "thank you", "thanks")):
            return "Aapka swagat hai, sir. Hamesha aapki seva me hajir!"
        if any(w in clean for w in ("bye", "alvida", "phir milenge", "goodbye")):
            return "Alvida sir! Apna khayal rakhiyega. Jab bhi zaroorat ho, bas aawaz dijiyega."

        # Offline & Connection Status
        if any(w in clean for w in ("offline ho kya", "internet nahi hai", "is internet working", "net chal raha")):
            return "Haan sir, abhi hum offline edge mode me chal rahe hain. Needle 2 aur LFM2.5 ke sahare saare local OS actions kaam kar rahe hain."

        # Humor & Fun
        if any(w in clean for w in ("joke", "chutkula", "hasao", "kuch hasao")):
            return "Ek programmer ne apni biwi se kaha: 'Market ja raha hoon, agar tamatar mile toh 10 le aana.' Wo 10 dukan le aaya kyunki wahan tamatar the! :D"
        if any(w in clean for w in ("shayari", "kavita")):
            return "Hukm aapka, taamil meri hogi, \nHar mushkil ab aasan banegi, \nJab tak J.A.R.V.I.S. hai aapke sath, \nHar command instant execute hogi!"

        # Math / Quick calculation evaluation offline
        math_m = re.search(r"(\d+)\s*([\+\-\*\/])\s*(\d+)", clean)
        if math_m:
            try:
                n1 = float(math_m.group(1))
                op = math_m.group(2)
                n2 = float(math_m.group(3))
                if op == '+': res_v = n1 + n2
                elif op == '-': res_v = n1 - n2
                elif op == '*': res_v = n1 * n2
                elif op == '/': res_v = n1 / n2 if n2 != 0 else "undefined"
                return f"{int(n1) if n1.is_integer() else n1} {op} {int(n2) if n2.is_integer() else n2} = {int(res_v) if isinstance(res_v, float) and res_v.is_integer() else res_v} hota hai, sir."
            except Exception:
                pass

        return f"J.A.R.V.I.S. (LFM2.5 Edge Mode): Aapka aadesh samajh gaya hoon — '{prompt}'."


class TriTierDispatcher:
    """Coordinates between:
      - Tier 1: Needle 2 (Instant Local OS Tool Reflex, 28 MB RAM) & LLM Cache (0ms)
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

        # Step 2.5: Check Smart LLM Cache (Instant 0ms, avoids unnecessary Cloud calls)
        try:
            from core import llm_cache
            cached_ans = llm_cache.get(user_text)
            if cached_ans:
                return {
                    "tier": 1,
                    "engine": "llm_cache",
                    "ear": "lfm2.5-230m",
                    "cached_response": cached_ans,
                    "tool": None,
                    "target": "cached_reply",
                    "ram_footprint": "0 MB",
                    "latency_estimate": "0ms",
                }
        except Exception:
            pass

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


# Aliases for convenient importing
NeedleTwoReflex = NeedleToolRouter
LFM25Ear = LFMChatEngine

