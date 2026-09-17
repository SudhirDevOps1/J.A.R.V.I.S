import os as _os
_os.environ["QT_LOGGING_RULES"] = "qt.text.font.db=false;qt.qpa.mime=false;qt.qpa.clipboard=false;qt.pointer.dispatch=false"
_os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Pre-load onnxruntime before PyQt6/Qt to prevent Windows C++ runtime DLL init conflict (error 1114)
try:
    import onnxruntime as _ort  # noqa: F401
except Exception:
    pass

import platform as _platform
import subprocess as _subprocess

# ── Nuclear: force CREATE_NO_WINDOW on EVERY subprocess call on Windows ───────
# This patches Popen itself, so no per-file flag is needed anywhere.
if _platform.system() == "Windows":
    _OrigPopen = _subprocess.Popen

    class _Popen(_OrigPopen):
        def __init__(self, args, **kw):
            kw["creationflags"] = kw.get("creationflags", 0) | _subprocess.CREATE_NO_WINDOW
            kw.pop("startupinfo", None)   # drop any stale/shared STARTUPINFO
            super().__init__(args, **                       kw)

    _subprocess.Popen = _Popen

# ─────────────────────────────────────────────────────────────────────────────

# ── Console encoding ─────────────────────────────────────────────────────────
# Status lines in this app carry emoji and arrows ("📤 file_controller → Moved:
# a.txt → Documents/"). On a non-UTF-8 console — cp1254 on a Turkish Windows,
# cp1251 on a Russian one, cp932 on a Japanese one — printing one of those
# raises UnicodeEncodeError, and because the print sits after the tool's own
# try/except, the exception escapes into the receive loop and takes the session
# down. The assistant dies on a log line.
#
# Reconfiguring costs nothing and makes the app start the same way in every
# locale. `errors="replace"` is the belt and braces — a console that genuinely
# cannot render a glyph shows a box instead of killing the process.
import sys as _sys
for _stream in (_sys.stdout, _sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import asyncio
import re
import threading
import time
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

import sounddevice as sd
import numpy as np
from google import genai
from google.genai import types

# Windows AppUserModelID registration (Taskbar Icon)
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SudhirDevOps1.JARVIS.AI")
    except Exception:
        pass

# Ensure critical assets (icons, SFX, models) are ready
try:
    from scripts.preflight_check import run_preflight
    run_preflight(verbose=False)
except Exception:
    pass

# Start Gemini Free Proxy (anonymous mode — runs when in free mode or no key provided)
try:
    import json as _json
    _cfg_path = Path(__file__).resolve().parent / "config" / "api_keys.json"
    _proxy_cfg = _json.loads(_cfg_path.read_text(encoding="utf-8")) if _cfg_path.exists() else {}
    _has_gemini_key = bool((_proxy_cfg.get("gemini_api_key") or "").strip())
    _preferred_prov = (_proxy_cfg.get("preferred_llm_provider") or "gemini").lower().strip()

    # If user has no Gemini key or explicitly chose gemini-web proxy, auto-start proxy:
    _auto_start = (not _has_gemini_key) or (_preferred_prov == "gemini-web")
    if _auto_start and _proxy_cfg.get("free_proxy_enabled", True):
        from core.gemini_free_proxy import start_proxy as _start_proxy
        _port = int(_proxy_cfg.get("free_proxy_port", 8081))
        _started = _start_proxy(port=_port, silent=True)
        if _started:
            print(f"[JARVIS] Gemini Free Proxy started on port {_port} (anonymous mode)")
    else:
        print("[JARVIS] Gemini Free Proxy idle (Official API Key active — background web server paused)")
except Exception as _e:
    print(f"[JARVIS] Free proxy startup check: {_e}")

from ui import JarvisUI
from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
    save_session_summary, pop_last_session,
    search_memory, set_trim_notifier,
)

# The file-backed tools (open_app, web_search, browser_control, …) are no longer
# imported or declared here — they self-describe via a TOOL dict in their own
# actions/*.py file and are auto-discovered by core.action_loader at startup.
# Only tools that are tied to live-session state stay inline in this file
# (screen_process, close_camera, save_memory, manage_monitor, shutdown_jarvis,
# system_status).
from actions.screen_processor  import _capture_camera, _capture_screen
from actions.system_monitor    import SystemMonitor, get_system_status
from actions.proactive         import ProactiveEngine
from actions.background_monitor import (
    add_monitor, remove_monitor, list_monitors, check_all as monitor_check_all,
)
from actions.web_search        import _news as _fetch_news_sync
from memory.config_manager     import (
    get_brief_enabled, get_voice, get_wake_word_enabled, save_wake_word_enabled,    get_input_device, get_output_device,
)
from core.plugin_loader        import discover_plugins
from core                      import undo as undo_stack
from core                      import confirm as confirm_gate
from core                      import audio_devices
from core.action_loader        import discover_actions
from core.wake_word            import (
    WakeWordDetector, is_ready as wake_is_ready, install_and_download as wake_install,
)

# How long the assistant stays awake with no user speech before it auto-sleeps
# again (wake-word mode only).
WAKE_SLEEP_TIMEOUT = 120.0   # seconds (2 minutes)

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
LIVE_MODEL          = "models/gemini-3.1-flash-live-preview"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000 
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024

# RMS below which 16-bit PCM is treated as room silence; above _LEVEL_FULL it
# reads as a full-height waveform. Tuned so ordinary speech lands mid-range and
# the bars still move for a quiet talker — language- and device-independent.
_LEVEL_FLOOR = 60.0
_LEVEL_FULL  = 2600.0


def _pcm_level(samples) -> float:
    """Map a block of int16 PCM samples to a 0.0–1.0 loudness level for the HUD
    waveform. Returns 0.0 on empty/invalid input so it can never raise."""
    try:
        x = np.asarray(samples, dtype=np.float32)
        if x.size == 0:
            return 0.0
        rms = float(np.sqrt(np.mean(x * x)))
    except Exception:
        return 0.0
    if rms <= _LEVEL_FLOOR:
        return 0.0
    return min(1.0, (rms - _LEVEL_FLOOR) / (_LEVEL_FULL - _LEVEL_FLOOR))


def _get_api_key() -> str:
    try:
        if API_CONFIG_PATH.exists():
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("gemini_api_key", "").strip()
    except Exception:
        pass
    return ""


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are JARVIS, Tony Stark's AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )

_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

def _clean_transcript(text: str) -> str:    
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()

TOOL_DECLARATIONS = [
    # ── Inline tools ─────────────────────────────────────────────────────────
    # These stay here (rather than in an actions/*.py TOOL dict) because their
    # handling is woven into live-session state — vision capture/injection,
    # camera stream, memory writes, the monitor engine, and shutdown. All other
    # tools live in their own action file and are auto-discovered by
    # core.action_loader (see JarvisLive.__init__).
    {
        "name": "system_status",
        "description": (
            "Returns real-time system metrics: CPU usage, RAM, GPU load, CPU temperature, "
            "uptime, and process count. Use when the user asks about computer performance, "
            "temperature, memory, or resource usage."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures the screen or webcam image and lets you analyze it. "
            "MUST be called when user asks what is on screen, what you see, "
            "look at camera, analyze my screen, etc. "
            "You have NO visual ability without this tool. "
            "After the image is captured it is sent directly to you — describe what you see and answer the user's question. "
            "When using camera: the live view stays open until user says close it or calls close_camera."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"},
                "text":  {"type": "STRING", "description": "The question or instruction about the captured image"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "close_camera",
        "description": (
            "Closes the live camera view shown on screen. "
            "Call when the user says (in ANY language): close camera, stop camera, "
            "turn off camera, that's creepy, etc."
        ),
        "parameters": {"type": "OBJECT", "properties": {}, "required": []}
    },
    {
        "name": "manage_monitor",
        "description": (
            "Add, remove, or list background monitoring topics. "
            "JARVIS checks these topics once a day and alerts the user when there is a new development. "
            "Use 'add' when the user says 'monitor X', 'track X', 'follow X'. "
            "Use 'remove' when the user says 'stop monitoring X'. "
            "Use 'list' when the user asks what is being monitored. "
            "Do NOT add crypto, financial, or trading topics."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type":        "STRING",
                    "description": "add | remove | list",
                },
                "topic": {
                    "type":        "STRING",
                    "description": "Topic to monitor or stop monitoring (e.g. 'space exploration', 'AI news')",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "shutdown_jarvis",
        "description": (
            "Shuts down the assistant completely. "
            "Call this when the user expresses intent to end the conversation, "
            "close the assistant, say goodbye, or stop Jarvis. "
            "The user can say this in ANY language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving — just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity — name, age, birthday, city, job, language, nationality | "
                        "preferences — favorite food/color/music/film/game/sport, hobbies | "
                        "projects — active projects, goals, things being built | "
                        "relationships — friends, family, partner, colleagues | "
                        "wishes — future plans, things to buy, travel dreams | "
                        "notes — habits, schedule, anything else worth remembering"
                    )
                },
                "key":   {"type": "STRING", "description": "Short snake_case key (e.g. name, favorite_food, sister_name)"},
                "value": {"type": "STRING", "description": "Concise value in English (e.g. Fatih, pizza, older sister)"},
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "recall_memory",
        "description": (
            "Look up a fact you have stored about the user but which is NOT in "
            "the memory block of your system prompt. "
            "The prompt lists the keys it did not have room for under "
            "'[ALSO REMEMBERED]' — if the user asks about anything named there, "
            "call this FIRST. "
            "Also call it before saying you do not know something personal, and "
            "when the user asks what you remember about them (leave query empty "
            "for everything). "
            "This is a local file search: it is instant and costs nothing."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": (
                        "Keyword to search for — a name, a topic, a category "
                        "(e.g. 'ayse', 'coffee', 'projects'). "
                        "Leave empty to list everything stored."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "recall_past_activities",
        "description": (
            "Look up what the user or assistant did yesterday, today, or on any past day from the permanent Daily Activity Journal. "
            "MUST be called whenever the user asks 'kal maine kya kya kiya tha', 'what did we do yesterday', 'did I do anything yesterday', or asks about past conversation history."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "day": {
                    "type": "STRING",
                    "description": "'yesterday', 'today', or a date like '2026-09-16'. Default is 'yesterday'",
                }
            },
            "required": [],
        },
    },
    {
        "name": "undo",
        "description": (
            "Reverse the last change YOU made to this computer — a file you "
            "moved, renamed, created or wrote, or a setting you changed such as "
            "volume, brightness, dark mode or WiFi. "
            "Call this whenever the user says undo, revert, take it back, put it "
            "back, cancel that, or tells you that you did the wrong thing, in ANY "
            "language. "
            "Use action='list' when they ask what can be undone. "
            "This only covers your own actions — it is not the Ctrl+Z of whatever "
            "application is on screen (that is computer_settings with action 'undo')."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "undo (default) — reverse the last change | list — show what can be undone",
                },
            },
            "required": [],
        },
    },
]

class _ReconnectSignal(Exception):
    """Raised inside the session TaskGroup to force a clean, voluntary reconnect
    (e.g. the user picked a new voice — the voice is fixed at connect time, so
    the session must be rebuilt).

    Carries `keep_context`: True for an ordinary rebuild, where the stored
    resumption handle is replayed and the conversation continues; False when the
    new session must genuinely start clean (see the voice-change note in
    _on_voice_change)."""

    def __init__(self, keep_context: bool = True):
        super().__init__()
        self.keep_context = keep_context


def _is_reconnect_signal(exc: BaseException) -> bool:
    """True if `exc` is a _ReconnectSignal, or a(n) (Base)ExceptionGroup that
    wraps one — TaskGroup bundles child exceptions into a group."""
    if isinstance(exc, _ReconnectSignal):
        return True
    if isinstance(exc, BaseExceptionGroup):
        return any(_is_reconnect_signal(sub) for sub in exc.exceptions)
    return False


def _keep_context_of(exc: BaseException) -> bool:
    """Read `keep_context` off a reconnect signal, unwrapping the group the
    TaskGroup put it in. Defaults to True: an unexpected shape must not silently
    wipe the conversation."""
    if isinstance(exc, _ReconnectSignal):
        return getattr(exc, "keep_context", True)
    if isinstance(exc, BaseExceptionGroup):
        for sub in exc.exceptions:
            if _is_reconnect_signal(sub):
                return _keep_context_of(sub)
    return True


class JarvisLive:
    def __init__(self, ui: JarvisUI):
        self.ui             = ui
        try:
            from memory.config_manager import get_assistant_name
            self._asst_name = (get_assistant_name() or "JARVIS").strip()
        except Exception:
            self._asst_name = "JARVIS"
        self.session              = None
        self.audio_in_queue       = None
        self.out_queue            = None
        self._loop                     = None
        self._is_speaking         = False
        self._speaking_lock       = threading.Lock()
        self._phone_active        = False   # True while phone mic is streaming; pauses PC mic
        self._pending_vision       = None    # (img_bytes, mime_type, question, angle) to inject after tool response
        self._vision_cam_active    = False   # True if camera was opened for vision → auto-close after response
        self._vision_close_pending = False   # True after vision injected; next turn_complete closes camera
        self._vision_last_time     = 0.0     # monotonic time of last screen_process call (cooldown guard)
        self._vision_busy          = False   # True while a vision capture/inject cycle is in flight
        self._interrupted          = False   # True while draining audio after user interrupt
        self.ui.on_text_command   = self._on_text_command
        self.ui.on_remote_clicked = self._make_remote_key
        self.ui.on_interrupt      = self.interrupt
        self.ui.on_voice_change   = self._on_voice_change     # voice picker → rebuild session
        self.ui.on_audio_device_change = self._on_audio_device_change
        self._reconnect_event: asyncio.Event | None = None
        self._reconnect_keep = True   # False → next rebuild drops the resumption handle

        # ── Session resumption ─────────────────────────────────────────
        # The server issues a resumption handle every few seconds and reissues
        # it as the conversation moves on. Before this, session_resumption was
        # switched ON in the config and the update was never read, so the handle
        # was thrown away and EVERY reconnect — a dropped packet, a voice change,
        # switching microphone — started an empty session. "Unlimited sessions"
        # leaked through exactly this hole.
        #
        # Deliberately in RAM only, never written to disk. Persisting it would
        # make a fresh launch continue yesterday's conversation, which sounds
        # appealing but breaks the session-summary flow: _save_session_summary
        # runs at shutdown and the morning briefing pops it the next day. A
        # conversation that never ends never produces a summary, and the
        # "yesterday we talked about…" line silently disappears.
        self._resume_handle: str | None = None
        self._turn_done_event: asyncio.Event | None = None
        self._dashboard     = None
        self._briefing_sent    = False          # morning briefing fires once per process
        self._sys_monitor      = SystemMonitor()  # persistent cooldown state
        self._proactive        = ProactiveEngine()
        self._last_user_speech = time.monotonic()  # updated on every user utterance
        self._session_log: list[str] = []          # conversation turns for end-of-session summary

        self._enhanced_live = True  # proactive audio; auto-disabled if the server rejects it

        _base_dir = Path(__file__).resolve().parent
        _inline_names = {t["name"] for t in TOOL_DECLARATIONS}

        # File-backed tools: every actions/*.py with a TOOL dict, discovered the
        # same way plugins are. Reserved names = the inline tools above, so an
        # action can never shadow one.
        self._action_registry = discover_actions(
            actions_dir=_base_dir / "actions",
            reserved_names=_inline_names,
            logger=lambda msg: print(f"[Actions] {msg}"),
        )

        # Plugins must not collide with either an inline tool or a discovered action.
        _core_names = _inline_names | self._action_registry.names()
        self._plugin_registry = discover_plugins(
            plugins_dir=_base_dir / "plugins",
            core_tool_names=_core_names,
            logger=lambda msg: (print(f"[Plugins] {msg}"), self.ui.write_log(f"SYS: {msg}")),
        )
        self.ui.get_plugins = self._plugin_registry.list_for_ui
        self.ui.get_plugin_settings = self._plugin_registry.settings_schemas  # ⚙ settings tab
        self.ui.request_say = self.plugin_say   # plugins: mid-task speech channel

        # ── Wake word ────────────────────────────────────────────────────────
        # _awake gates the mic (see _listen_audio) and the background speakers.
        # It is True whenever wake word is OFF, so default behaviour is unchanged.
        self._wake_enabled     = get_wake_word_enabled()
        self._awake            = not self._wake_enabled
        self._wake_detector: WakeWordDetector | None = None
        self._wake_sleep_timeout = WAKE_SLEEP_TIMEOUT
        # UI control surface for the Wake Word settings section.
        self.ui.wake_is_ready    = wake_is_ready          # () -> bool
        self.ui.wake_get_state   = self._wake_state       # () -> dict
        self.ui.on_wake_toggle   = self._ui_wake_toggle   # (enable: bool) -> str
        self.ui.on_wake_manual   = self._ui_wake_manual   # () -> toggle awake/asleep
        self.ui.on_wake_install  = self._ui_wake_install  # () -> (ok, msg)

    # ── Wake word: state machine ─────────────────────────────────────────────

    def _wake_state(self) -> dict:
        # A loaded, running detector is definitively ready; otherwise fall back
        # to the cheap on-disk model-file check (no Model construction).
        ready = bool(self._wake_detector and self._wake_detector.ready) or wake_is_ready()
        return {"enabled": self._wake_enabled, "awake": self._awake, "ready": ready}

    def _ensure_wake_detector(self) -> bool:
        """Load the detector once (model loads on first start). Idempotent."""
        if self._wake_detector is None:
            self._wake_detector = WakeWordDetector(
                on_detect=self._on_wake_detected,
                logger=lambda m: (print(f"[Wake] {m}"), self.ui.write_log(f"SYS: {m}")),
            )
        if not self._wake_detector.ready:
            return self._wake_detector.start()
        return True

    def _on_wake_detected(self) -> None:
        """Called from the detector thread when 'Hey Jarvis' is heard."""
        self.wake(reason="wake word")

    def wake(self, reason: str = "wake word") -> None:
        if self._awake:
            return
        self._awake = True
        self._last_user_speech = time.monotonic()   # start the auto-sleep clock now
        if not self.ui.muted:
            self.ui.set_state("LISTENING")
        self.ui.write_log(f"SYS: Awake — {reason}.")
        try:
            from core.sfx import play_sfx
            play_sfx("wake")
        except Exception:
            pass

    def sleep(self, reason: str = "timeout") -> None:
        if not self._awake:
            return
        self._awake = False
        self.set_speaking(False)
        self.ui.set_state("SLEEPING")
        self.ui.write_log(f"SYS: Sleeping — {reason}. Say 'Hey Jarvis' to wake me.")

    async def _run_sleep_watch(self) -> None:
        """Auto-sleep after the configured silence window (wake-word mode only)."""
        while True:
            await asyncio.sleep(5)
            if not self._wake_enabled or not self._awake:
                continue
            with self._speaking_lock:
                speaking = self._is_speaking
            if speaking:
                continue
            if (time.monotonic() - self._last_user_speech) > self._wake_sleep_timeout:
                self.sleep(reason="no speech for 2 minutes")

    # ── Wake word: UI callbacks (called from the Qt thread) ──────────────────

    def _ui_wake_toggle(self, enable: bool) -> str:
        """Enable/disable wake word from the settings UI. Returns a status token:
        'enabled' | 'disabled' | 'need_download'."""
        if enable:
            if not wake_is_ready():
                return "need_download"
            self._wake_enabled = True
            save_wake_word_enabled(True)
            self._ensure_wake_detector()
            self.sleep(reason="wake word enabled")
            return "enabled"
        else:
            self._wake_enabled = False
            save_wake_word_enabled(False)
            self.wake(reason="wake word disabled")
            return "disabled"

    def _ui_wake_manual(self) -> None:
        """Manual sleep/wake button in the UI."""
        if not self._wake_enabled:
            return
        if self._awake:
            self.sleep(reason="you tapped sleep")
        else:
            self.wake(reason="you tapped wake")

    def _ui_wake_install(self) -> tuple[bool, str]:
        """Download openwakeword + the model (runs in a UI worker thread)."""
        return wake_install(logger=lambda m: self.ui.write_log(f"SYS: {m}"))

    def plugin_say(self, instruction: str) -> None:
        """
        Thread-safe speech channel for plugins: lets a plugin ask JARVIS to
        say something short WHILE its run() is still executing (plugins block
        their executor thread, so they can't speak through the tool response
        until they finish). The instruction is injected into the Live session
        exactly like a proactive check-in; Gemini phrases it naturally in the
        user's language. Silently a no-op when no session is connected.
        """
        loop = getattr(self, "_loop", None)
        if not loop or not self.session:
            return

        async def _say():
            try:
                await self.session.send_client_content(
                    turns={"role": "user", "parts": [{"text": instruction}]},
                    turn_complete=True,
                )
            except Exception as e:
                print(f"[PluginSay] {e}")

        try:
            asyncio.run_coroutine_threadsafe(_say(), loop)
        except Exception as e:
            print(f"[PluginSay] {e}")

    def request_reconnect(self, keep_context: bool = True, reason: str = ""):
        """Thread-safe: ask the run loop to tear down and rebuild the Live
        session. Called from the Qt thread. No-op until the async loop and
        reconnect event exist.

        `keep_context=False` drops the resumption handle so the new session
        starts empty — only for changes the server cannot apply to a resumed
        session."""
        loop = getattr(self, "_loop", None)
        ev   = self._reconnect_event
        self._reconnect_keep   = keep_context
        self._reconnect_reason = reason
        if loop and ev is not None:
            loop.call_soon_threadsafe(ev.set)

    def _on_voice_change(self):
        """Voice picker applied.

        The voice is baked into the session at connect time, so a rebuild is
        required. It is rebuilt WITHOUT the resumption handle on purpose:
        resuming restores the server's own session state, and the safe reading
        is that it restores the voice with it — which would make the picker
        appear to do nothing. Losing context here is acceptable because changing
        voice is a deliberate, rare act; losing it on a dropped packet was not."""
        self.request_reconnect(keep_context=False, reason="new voice")

    def _on_audio_device_change(self):
        """Microphone or speaker changed. Both streams are opened inside the
        session TaskGroup, so they can only be re-opened by rebuilding it —
        but the conversation is kept, which is the whole reason resumption
        landed before this feature did."""
        self.request_reconnect(keep_context=True, reason="audio device")

    async def _watch_reconnect(self):
        """Session-scoped task: when a voluntary reconnect is requested, raise a
        signal that unwinds the TaskGroup so the run loop rebuilds the session."""
        assert self._reconnect_event is not None
        await self._reconnect_event.wait()
        self._reconnect_event.clear()
        keep   = self._reconnect_keep
        reason = getattr(self, "_reconnect_reason", "") or "settings"
        self.ui.write_log(
            f"SYS: Applying {reason} — reconnecting"
            + ("..." if keep else " (starting a fresh conversation)...")
        )
        raise _ReconnectSignal(keep_context=keep)

    def _make_remote_key(self):
        """Called from Qt main thread when user presses Remote Control."""
        if self._dashboard is None:
            self.ui.write_log(
                "SYS: Dashboard unavailable. "
                "Run: pip install fastapi \"uvicorn[standard]\" cryptography"
            )
            return None
        key    = self._dashboard.new_key()
        url    = self._dashboard.get_url()
        manual = self._dashboard.get_manual_url()
        return url, key, f"{url}/auto-login?key={key}", manual

    def _on_text_command(self, text: str):
        # Respect wake-word sleep: a typed command must not be answered while
        # asleep either (the sleep gate is not just for the mic). Wake first with
        # "Hey Jarvis" or the WAKE NOW button.
        if self._wake_enabled and not self._awake:
            self.ui.write_log("SYS: I'm asleep — say 'Hey Jarvis' or tap WAKE NOW first.")
            return

        from memory.memory_manager import log_daily_activity
        log_daily_activity(text)

        # Hermes autonomous learning & pitch intent handler
        try:
            from memory.hermes_personalization import learn_from_interaction, adjust_pitch_by_intent
            learn_from_interaction(text)
            matched, new_pitch, confirm_msg = adjust_pitch_by_intent(text)
            if matched:
                self.ui.write_log(f"SYS: Voice pitch updated to {new_pitch}.")
                self.speak(confirm_msg)
                return
        except Exception:
            pass

        # Tier 1 & 2: Needle 2 (28MB RAM) & LFM2.5 Edge AI Reflex (Instant local tool execution)
        try:
            from memory.config_manager import get_edge_reflex_enabled
            if get_edge_reflex_enabled():
                from core.edge_router import get_tri_tier_dispatcher
                dispatcher = get_tri_tier_dispatcher()
                routing = dispatcher.route(text, is_online=bool(_get_api_key().strip()))

                if routing.get("tier") == 1 and routing.get("tool"):
                    t_name, t_args = routing["tool"]
                    if self._action_registry.has(t_name):
                        self.ui.write_log(f"⚡ [Needle 2 Reflex (28MB)]: {t_name} {t_args}")
                        _ctx = {"player": self.ui, "speak": self.speak, "response": None, "session_memory": None}
                        t_res = self._action_registry.run(t_name, t_args, _ctx)
                        if t_res:
                            self.ui.write_log(f"{self._asst_name}: {t_res}")
                            self.speak(t_res)
                        return

                elif routing.get("tier") == 2:
                    self.ui.set_state("THINKING")
                    from core.persona_manager import build_persona_system_prompt
                    lfm_ans = dispatcher.lfm.generate(text, system_prompt=build_persona_system_prompt(self._asst_name))
                    if lfm_ans:
                        self.ui.write_log(f"⚡ [LFM2.5-230M (Offline)]: {lfm_ans}")
                        self.speak(lfm_ans)
                        self.ui.set_state("LISTENING")
                        return
        except Exception as _edge_err:
            print(f"[EdgeRouter Error] {_edge_err}")

        # Direct Avatar Emotion / Expression Voice & Text commands
        t_low = text.lower()
        if any(w in t_low for w in ("expression", "mood", "react", "chehre ke bhav", "bhav dikhao")):
            try:
                from core.expression_engine import detect_expression
                m_expr = detect_expression(t_low)
                if m_expr:
                    self.ui.set_expression(m_expr, 8.0)
                    self.ui.write_log(f"SYS: Avatar expression changed to [{m_expr.upper()}].")
                    if any(w in t_low for w in ("karo", "dikhao", "change", "set", "show", "kar do")):
                        self.speak(f"Avatar par {m_expr} expression set kar diya hai.")
                        return
            except Exception:
                pass

        # Camera / Webcam & Vision commands (Works across ALL providers, including Free Proxy mode)
        t_clean = t_low.strip()
        is_cam_open = any(w in t_clean for w in (
            "camera kholo", "open camera", "show camera", "camera on", "start camera",
            "webcam kholo", "open webcam", "turn on camera", "camera chalu", "camera start",
            "camera on karo", "webcam on"
        ))
        is_cam_close = any(w in t_clean for w in (
            "camera band karo", "close camera", "stop camera", "hide camera", "camera off",
            "webcam band", "turn off camera", "camera band", "band karo camera", "camera off karo"
        ))
        is_vision_query = any(w in t_clean for w in (
            "camera dekho", "dekho camera", "look at camera", "look at me", "kya dikh raha hai",
            "screen dekho", "look at screen", "analyze screen", "kya chal raha hai screen par",
            "screen par kya hai", "take photo", "capture screen", "capture camera", "meri screen dekho"
        ))

        if is_cam_open:
            self.ui.start_camera_stream()
            self.ui.write_log("SYS: Camera stream started on HUD.")
            self.speak("कैमरा स्ट्रीम HUD पर शुरू कर दी गई है।")
            return

        if is_cam_close:
            self.ui.stop_camera_stream()
            self.ui.write_log("SYS: Camera stream stopped.")
            self.speak("कैमरा स्ट्रीम बंद कर दी गई है।")
            return

        # Running applications inspection intent
        is_apps_query = any(w in t_clean for w in (
            "apps dekho", "all apps", "all apps dekho", "running apps",
            "kaun se app chal rahe hain", "kaunse apps chal rahe hain",
            "apps dikhao", "open apps", "active apps", "list apps",
            "kya khula hai", "kya chal raha hai computer me", "computer me kya chal raha hai"
        ))
        if is_apps_query:
            try:
                from actions.open_app import list_running_apps
                apps = list_running_apps()
                if apps:
                    top_apps = ", ".join(apps[:12])
                    msg = f"अभी आपके सिस्टम पर {len(apps)} ऐप्स सक्रिय हैं, जिनमें मुख्य रूप से {top_apps} शामिल हैं।"
                else:
                    msg = "सिस्टम पर कोई मुख्य यूजर एप्लिकेशन नहीं मिला।"
                self.ui.write_log(f"{self._asst_name}: {msg}")
                self.speak(msg)
                return
            except Exception as _ae:
                print(f"[AppsQuery] {_ae}")

        if is_vision_query:
            is_screen = any(w in t_clean for w in ("screen", "display", "monitor"))
            def _async_vision():
                try:
                    self.ui.set_state("THINKING")
                    if is_screen:
                        self.ui.write_log("SYS: Capturing screen for visual analysis...")
                        img_b, mime_t = _capture_screen()
                        target_label = "स्क्रीन"
                    else:
                        self.ui.write_log("SYS: Opening camera feed and capturing frame...")
                        self.ui.start_camera_stream()
                        img_b, mime_t = _capture_camera()
                        target_label = "कैमरा"

                    from memory.config_manager import load_api_keys
                    c_keys = load_api_keys()
                    g_key = (c_keys.get("gemini_api_key") or "").strip()

                    # If an official Google Gemini API key exists (e.g. Free AI Studio tier)
                    if g_key:
                        import base64
                        import requests
                        b64 = base64.b64encode(img_b).decode("ascii")
                        v_payload = {
                            "contents": [{
                                "parts": [
                                    {"text": f"You are {self._asst_name}. Look at this captured {target_label} and answer the user directly in 1-2 natural sentences in conversational Hindi/Devanagari: {text}"},
                                    {"inline_data": {"mime_type": mime_t, "data": b64}}
                                ]
                            }]
                        }
                        for v_model in ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.5-flash-lite"]:
                            try:
                                v_url = f"https://generativelanguage.googleapis.com/v1beta/models/{v_model}:generateContent?key={g_key}"
                                v_resp = requests.post(v_url, json=v_payload, timeout=25)
                                if v_resp.status_code == 200:
                                    v_data = v_resp.json()
                                    cands = v_data.get("candidates", [])
                                    if cands and "content" in cands[0]:
                                        parts = cands[0]["content"].get("parts", [])
                                        if parts and "text" in parts[0]:
                                            ans = parts[0]["text"].strip()
                                            if ans:
                                                self.ui.write_log(f"{self._asst_name}: {ans}")
                                                self.speak(ans)
                                                self.ui.set_state("LISTENING")
                                                return
                            except Exception as _ve:
                                print(f"[Vision] {v_model} attempt: {_ve}")
                    # Free Mode / Anonymous Proxy fallback:
                    self.ui.write_log(f"SYS: {target_label} कैप्चर सक्रिय है। HUD पर लाइव स्ट्रीम चालू है।")
                    self.speak(f"{target_label} मैंने देख लिया है और HUD पर लाइव स्ट्रीम चालू कर दी है।")
                    self.ui.set_state("LISTENING")
                except Exception as ex:
                    print(f"[Vision Error] {ex}")
                    self.ui.write_log(f"ERR: Vision capture error: {ex}")
                    self.ui.set_state("LISTENING")

            threading.Thread(target=_async_vision, daemon=True).start()
            return

        # Multi-Provider routing: if user configured OpenRouter, Groq, DeepSeek, or Custom LLM,
        # route typed queries through MultiLLMClient with full persona and second-brain context.
        from memory.config_manager import load_api_keys
        cfg = load_api_keys()
        prov = (cfg.get("preferred_llm_provider") or "gemini").lower().strip()

        if prov in ("gemini-web", "omniroute", "openrouter", "groq", "deepseek", "custom", "openai", "ollama") or not _get_api_key().strip():
            def _async_multi_llm():
                try:
                    self.ui.set_state("THINKING")
                    from core.multi_llm import get_llm_model
                    from core.persona_manager import build_persona_system_prompt
                    from memory.memory_manager import format_memory_for_prompt, load_memory, get_daily_journal
                    
                    client = get_llm_model(preferred_provider=prov)
                    persona = build_persona_system_prompt(self._asst_name)
                    mem = format_memory_for_prompt(load_memory())
                    y_log = get_daily_journal("yesterday")
                    t_log = get_daily_journal("today")

                    prompt_parts = [
                        persona,
                        f"\n[CURRENT DATE & TIME]: {datetime.now().strftime('%A, %B %d, %Y %I:%M %p')}\n",
                    ]
                    if mem:
                        prompt_parts.append(f"\n[LONG-TERM MEMORY FACTS]:\n{mem}\n")
                    if "No activity log found" not in y_log:
                        prompt_parts.append(f"\n[YESTERDAY'S ACTIVITIES & CONTEXT]:\n{y_log[:900]}\n")
                    if "No activity log found" not in t_log:
                        prompt_parts.append(f"\n[TODAY'S ACTIVITIES & CONTEXT]:\n{t_log[:900]}\n")
                    prompt_parts.append(f"\nUser says: {text}\nRespond as {self._asst_name}:")

                    full_prompt = "\n".join(prompt_parts)
                    res = client.generate_content(full_prompt)
                    ans = (res.text or "").strip()
                    if ans:
                        log_daily_activity(text, ai_response=ans)
                        self.ui.write_log(f"{self._asst_name}: {ans}")
                        try:
                            from core.expression_engine import detect_expression
                            expr = detect_expression(ans) or detect_expression(text)
                            if expr:
                                self.ui.set_expression(expr)
                        except Exception:
                            pass
                        self.speak(ans)
                    self.ui.set_state("LISTENING")
                except Exception as e:
                    print(f"[MultiLLM Error] {e}")
                    self.ui.write_log(f"ERR: {prov.upper()} query failed: {e}")
                    self.ui.set_state("LISTENING")

            threading.Thread(target=_async_multi_llm, daemon=True).start()
            return

        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"role": "user", "parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

    def interrupt(self) -> None:
        """Stop JARVIS mid-speech: drain queued audio and open mic immediately."""
        self._interrupted = True
        q = self.audio_in_queue
        if q:
            drained = 0
            while True:
                try:
                    q.get_nowait()
                    drained += 1
                except Exception:
                    break
            if drained:
                print(f"[JARVIS] ✋ Interrupted — {drained} audio chunks discarded")

        # Drain and abort Piper speech
        if hasattr(self, "_piper_queue"):
            while not self._piper_queue.empty():
                try:
                    self._piper_queue.get_nowait()
                except Exception:
                    break
        try:
            import sounddevice as _sd
            _sd.stop()
        except Exception:
            pass

        self.set_speaking(False)
        if self._turn_done_event:
            self._turn_done_event.clear()
        self.ui.write_log("SYS: Interrupted — listening...")

    def speak(self, text: str):
        try:
            from core.expression_engine import detect_expression
            _ex = detect_expression(text)
            if _ex:
                self.ui.set_expression(_ex)
        except Exception:
            pass
        from memory.config_manager import get_tts_engine
        eng = (get_tts_engine() or "").lower().strip()

        # 1. If user explicitly configured offline Piper Hindi
        if eng in ("piper_hindi", "piper", "piper_hi"):
            self._speak_with_piper(text)
            return

        # 2. If official Gemini Live audio session is active via WebSockets
        if self._loop and self.session:
            asyncio.run_coroutine_threadsafe(
                self.session.send_client_content(
                    turns={"role": "user", "parts": [{"text": text}]},
                    turn_complete=True
                ),
                self._loop
            )
            return

        # 3. In Free Mode or Multi-Provider: default to natural Edge Neural voice
        # (e.g. Swara for Maya, Madhur for Jarvis) with automatic fallback to Piper
        self._speak_with_edge(text)

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        from memory.config_manager import get_persona_mode
        if get_persona_mode() == "companion":
            self.speak(f"Jaan, {tool_name} mein thodi dikkat aa gayi: {short}")
        else:
            self.speak(f"Sir, {tool_name} encountered an error: {short}")

    def _build_config(self) -> types.LiveConnectConfig:
        from datetime import datetime

        # Load customization from config
        try:
            _cfg = json.loads(open(API_CONFIG_PATH, encoding="utf-8").read())
            self._asst_name = (_cfg.get("assistant_name") or "JARVIS").strip()
            _user_name = (_cfg.get("user_name") or "").strip()
        except Exception:
            self._asst_name = "JARVIS"
            _user_name = ""

        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()

        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Use this to calculate exact times for reminders.\n\n"
        )

        # Persona & Character injection
        from core.persona_manager import build_persona_system_prompt
        from memory.memory_manager import get_daily_journal
        from memory.config_manager import get_persona_mode
        cur_persona = get_persona_mode()
        persona_ctx = build_persona_system_prompt(self._asst_name)

        # Identity injection — overrides any hardcoded name in prompt.txt
        if cur_persona == "companion":
            _addr = (f"ADDRESS: You are his loving girlfriend and devoted partner. Address him affectionately by his name '{_user_name}' or 'Jaan', 'Suno na', 'Babu'. NEVER call him 'Sir' or speak formally!"
                     if _user_name
                     else "ADDRESS: You are his loving girlfriend and devoted partner. Address him affectionately as 'Jaan', 'Suno na', 'Mere jaan'. NEVER call him 'Sir' or treat him like a formal boss!")
        elif _user_name:
            _addr = f"ADDRESS: Always call the user '{_user_name}'."
        else:
            _addr = ("ADDRESS: Address the user with the ordinary respectful form "
                     "for a superior in the language you are currently speaking — "
                     "\"sir\" in English, its everyday equivalent in any other "
                     "language. Never an archaic or aristocratic form, and never "
                     "the form from a different language than the one you are "
                     "speaking in this sentence.")
        identity_ctx = (
            f"[IDENTITY]\n"
            f"Your name is {self._asst_name}. "
            f"Always refer to yourself as {self._asst_name}.\n"
            f"{_addr}\n\n"
        )

        y_journal = get_daily_journal("yesterday")
        journal_ctx = ""
        if "No activity log found" not in y_journal:
            journal_ctx = f"\n[YESTERDAY'S ACTIVITIES & PAST LOGS]\n{y_journal[:1400]}\n"

        # Persona and Language Directives are placed AFTER sys_prompt so they have final authority over behavior
        parts = [time_ctx, sys_prompt, identity_ctx]
        if journal_ctx:
            parts.append(journal_ctx)
        if mem_str:
            parts.append(mem_str)
        parts.append(persona_ctx)

        from memory.config_manager import get_tts_engine
        if get_tts_engine() in ("piper_hindi", "piper", "piper_hi"):
            example_text = "हाँ जान, मैं अभी आपकी स्क्रीन देख रही हूँ।" if cur_persona == "companion" else "हाँ सुधीर सर, मैं अभी आपकी स्क्रीन देख रहा हूँ।"
            parts.append(
                "\n[SPEECH SYNTHESIS RULE: PIPER HINDI ACTIVE]\n"
                "The user is listening to you through an offline Piper Hindi neural engine.\n"
                "Whenever responding in Hindi or Hinglish, output your answer clearly using Devanagari script (देवनागरी लिपि).\n"
                f"Example: '{example_text}'\n"
                "Keep responses conversational, concise, and direct.\n"
            )

        cfg = dict(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": (
                TOOL_DECLARATIONS
                + self._action_registry.get_tool_declarations()
                + self._plugin_registry.get_tool_declarations()
            )}],
            # Hand back the handle captured from the last session_resumption
            # update. `handle=None` is exactly the old behaviour (ask for
            # handles, start fresh), so the first connect of a run is unchanged.
            session_resumption=types.SessionResumptionConfig(
                handle=self._resume_handle
            ),
            # Sliding-window compression: session never dies from a full context
            # window — JARVIS can stay in one conversation for hours
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow(),
            ),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=get_voice()
                    )
                )
            ),
        )
        if self._enhanced_live:
            # Proactive audio: JARVIS stays silent when speech isn't addressed
            # to it (background chatter, talking to someone else in the room).
            cfg["proactivity"] = types.ProactivityConfig(proactive_audio=True)
        return types.LiveConnectConfig(**cfg)

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})

        print(f"[JARVIS] 🔧 {name}  {args}")
        self.ui.set_state("THINKING")

        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {"value": value}}})
                print(f"[Memory] 💾 save_memory: {category}/{key} = {value}")

                # Check if user updated assistant's name verbally (e.g. "tumhara naam Maya hai", "call yourself Pari")
                k_clean = str(key).lower().strip().replace(" ", "_")
                if k_clean in ("assistant_name", "ai_name", "bot_name", "girlfriend_name", "gf_name", "your_name", "name_of_assistant"):
                    new_asst_name = str(value).strip()
                    if new_asst_name:
                        from memory.config_manager import save_assistant_config, get_user_name
                        save_assistant_config(new_asst_name, get_user_name())
                        self._asst_name = new_asst_name
                        self.ui._assistant_name = new_asst_name
                        self.ui.setWindowTitle(f"{new_asst_name.upper()} — {APP_VERSION}")
                        self.ui._title_lbl.setText(new_asst_name.upper())
                        self.ui.hud._assistant_name = new_asst_name.upper()
                        self.ui.write_log(f"SYS: Assistant name updated to '{new_asst_name}' by voice command.")

                # Check if user told their own name verbally (e.g. "mera naam Sudhir hai")
                elif k_clean in ("user_name", "my_name", "owner_name", "user"):
                    new_user_name = str(value).strip()
                    if new_user_name:
                        from memory.config_manager import save_assistant_config, get_assistant_name
                        save_assistant_config(get_assistant_name(), new_user_name)
                        self.ui.write_log(f"SYS: User name recognized as '{new_user_name}'.")

                # Check if voice pitch was updated verbally
                elif k_clean in ("pitch", "voice_pitch", "speech_pitch"):
                    from memory.config_manager import save_edge_pitch
                    p_val = str(value).strip()
                    save_edge_pitch(p_val)
                    self.ui.write_log(f"SYS: Voice pitch updated to '{p_val}'.")

            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        loop   = asyncio.get_event_loop()
        result = "Done."

        try:
            if name == "recall_memory":
                # Local file search: no network, no second model. Kept out of
                # the executor deliberately — it is a dictionary scan over a few
                # hundred short strings, and a thread hop would cost more than
                # the work itself.
                result = search_memory(args.get("query", ""), limit=8)

            elif name == "recall_past_activities":
                from memory.memory_manager import recall_past_activities
                result = recall_past_activities(args.get("day", "yesterday"))

            elif name == "undo":
                if str(args.get("action", "")).lower().strip() == "list":
                    items = undo_stack.history()
                    result = ("Things I can undo, most recent first:\n"
                              + "\n".join(f"{i+1}. {t}" for i, t in enumerate(items))
                              ) if items else "I have not changed anything I can undo yet."
                else:
                    result = await loop.run_in_executor(None, undo_stack.undo_last)

            elif name == "screen_process":
                import time as _t_mod
                _now = _t_mod.monotonic()
                _cooldown = 4.0  # seconds — covers echo window after speaking ends
                if self._vision_busy or (_now - self._vision_last_time) < _cooldown:
                    _wait = max(0, _cooldown - (_now - self._vision_last_time))
                    print(f"[Vision] ⏳ Cooldown active ({_wait:.1f}s remaining) — ignoring duplicate call")
                    result = "Vision is still processing the previous request. I will not call this again."
                else:
                    self._vision_busy      = True
                    self._vision_last_time = _now
                    angle     = args.get("angle", "screen").lower()
                    user_text = args.get("text", "What do you see?")
                    if angle == "camera":
                        img_b, mime_t = await loop.run_in_executor(None, _capture_camera)
                        self.ui.start_camera_stream()
                        self._vision_cam_active = True
                        print(f"[Vision] 📷 Camera: {len(img_b):,} bytes")
                        _stall = "camera"
                    else:
                        img_b, mime_t = await loop.run_in_executor(None, _capture_screen)
                        print(f"[Vision] 🖥️  Screen: {len(img_b):,} bytes")
                        _stall = "screen"
                    self._pending_vision = (img_b, mime_t, user_text, angle)
                    result = (
                        f"[VISION_ACTIVE] {_stall.capitalize()} captured. "
                        f"Immediately say ONE short natural sentence in the user's own language, "
                        f"telling them you are looking at their {_stall} right now. "
                        f"Do NOT describe or guess content — the actual image arrives in the NEXT message."
                    )

            elif name == "close_camera":
                self.ui.stop_camera_stream()
                result = "Camera closed."

            elif name == "system_status":
                r = await loop.run_in_executor(None, get_system_status)
                result = str(r)

            elif name == "manage_monitor":
                action = args.get("action", "").lower().strip()
                topic  = args.get("topic", "").strip()
                if action == "add" and topic:
                    result = await asyncio.to_thread(add_monitor, topic)
                elif action == "remove" and topic:
                    result = await asyncio.to_thread(remove_monitor, topic)
                elif action == "list":
                    topics = await asyncio.to_thread(list_monitors)
                    result = ("Monitoring: " + ", ".join(topics)) if topics else "No topics are being monitored."
                else:
                    result = "Specify action (add/remove/list) and a topic."

            elif name == "shutdown_jarvis":
                self.ui.write_log("SYS: Shutdown requested.")
                async def _do_shutdown():
                    await self._save_session_summary()
                    if self.session:
                        try:
                            await self.session.send_client_content(
                                turns={"role": "user", "parts": [{"text": "Say a brief natural goodbye to the user."}]},
                                turn_complete=True,
                            )
                        except Exception:
                            pass
                    await asyncio.sleep(1.5)
                    import os as _os
                    _os._exit(0)
                asyncio.create_task(_do_shutdown())

            elif self._action_registry.has(name):
                # file_processor: fall back to the currently-uploaded file when none is given
                if name == "file_processor" and not args.get("file_path") and self.ui.current_file:
                    args["file_path"] = self.ui.current_file
                _ctx = {"player": self.ui, "speak": self.speak,
                        "response": None, "session_memory": None}
                r = await loop.run_in_executor(None, lambda: self._action_registry.run(name, args, _ctx))
                result = r or "Done."
                # web_search: mirror results to the on-screen content panel
                if (name == "web_search" and r
                        and not r.startswith("No results")
                        and not r.startswith("Search failed")):
                    _mode  = args.get("mode", "search")
                    _query = args.get("query") or ", ".join(args.get("items", []))
                    _label = f"{_mode.upper()} — {_query[:38]}" if _query else _mode.upper()
                    self.ui.show_content(_label, r)

            else:
                if self._plugin_registry.has(name):
                    r = await loop.run_in_executor(
                        None,
                        lambda: self._plugin_registry.run(name, args, player=self.ui, session_memory=None)
                    )
                    result = r or "Done."
                else:
                    result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()
            self.speak_error(name, e)

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[JARVIS] 📤 {name} → {str(result)[:80]}")
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            # Gemini 3.x Live rejects the old realtime_input.media_chunks field
            # (what `media=...` maps to) and closes the socket with a 1007. Send
            # mic / phone PCM through the new `audio` field instead. Queue items
            # are {"data": <bytes>, "mime_type": <str>} from _listen_audio and
            # the phone relay.
            await self.session.send_realtime_input(
                audio=types.Blob(
                    data=msg["data"],
                    mime_type=msg.get("mime_type", "audio/pcm"),
                )
            )

    def _safe_put_out_queue(self, item: dict) -> None:
        """Drop older audio slices if queue is full during network interruptions to prevent QueueFull crashes."""
        try:
            self.out_queue.put_nowait(item)
        except asyncio.QueueFull:
            try:
                self.out_queue.get_nowait()
                self.out_queue.put_nowait(item)
            except Exception:
                pass
        except Exception:
            pass

    def _speak_with_piper(self, text: str) -> None:
        """Synthesize and play response using offline Piper Hindi Neural TTS in a sequential queue."""
        if not text or not text.strip():
            return
        from core.tts import clean_speech_text
        text = clean_speech_text(text)
        if not text:
            return

        if not hasattr(self, "_piper_queue"):
            import queue
            self._piper_queue = queue.Queue()

        self._piper_queue.put(text)
        if not getattr(self, "_piper_worker_running", False):
            self._piper_worker_running = True
            threading.Thread(target=self._piper_worker_loop, daemon=True).start()

    def _piper_worker_loop(self):
        try:
            from core.tts import PiperHindiTTSEngine
            if not hasattr(self, "_piper_engine") or self._piper_engine is None:
                self._piper_engine = PiperHindiTTSEngine()

            while hasattr(self, "_piper_queue") and not self._piper_queue.empty():
                try:
                    text = self._piper_queue.get_nowait()
                except Exception:
                    break

                if not text or not text.strip() or self._interrupted:
                    continue

                self.set_speaking(True)
                self.ui.set_state("SPEAKING")
                short_text = text[:80] + "..." if len(text) > 80 else text
                self.ui.write_log(f"🎙️ [Piper Hindi]: {short_text}")
                print(f"[TTS] 🎙️ Piper Hindi synthesising: {text}")
                try:
                    self._piper_engine.speak(text)
                except Exception as e:
                    print(f"[TTS] ❌ Piper error: {e}")
                    self.ui.write_log(f"SYS: Piper TTS error: {e}")
        finally:
            self._piper_worker_running = False
            self.set_speaking(False)
            if not self.ui.muted:
                self.ui.set_state("LISTENING")

    def _speak_with_edge(self, text: str) -> None:
        """Synthesize and play response using Microsoft Edge Neural TTS in a sequential queue."""
        if not text or not text.strip():
            return
        from core.tts import clean_speech_text
        text = clean_speech_text(text)
        if not text:
            return

        if not hasattr(self, "_edge_queue"):
            import queue
            self._edge_queue = queue.Queue()

        self._edge_queue.put(text)
        if not getattr(self, "_edge_worker_running", False):
            self._edge_worker_running = True
            threading.Thread(target=self._edge_worker_loop, daemon=True).start()

    def _edge_worker_loop(self):
        try:
            from core.tts import EdgeTTSEngine
            from memory.config_manager import get_edge_voice, get_edge_pitch, get_edge_rate
            v = get_edge_voice() or "hi-IN-SwaraNeural"
            p = get_edge_pitch() or "+0Hz"
            r = get_edge_rate() or "+0%"

            if (not hasattr(self, "_edge_engine") or self._edge_engine is None
                    or getattr(self._edge_engine, "voice", "") != v
                    or getattr(self._edge_engine, "pitch", "") != p
                    or getattr(self._edge_engine, "rate", "") != r):
                self._edge_engine = EdgeTTSEngine(voice=v, pitch=p, rate=r)

            while hasattr(self, "_edge_queue") and not self._edge_queue.empty():
                try:
                    text = self._edge_queue.get_nowait()
                except Exception:
                    break

                if not text or not text.strip() or self._interrupted:
                    continue

                self.set_speaking(True)
                self.ui.set_state("SPEAKING")
                short_text = text[:80] + "..." if len(text) > 80 else text
                voice_label = v.split("-")[-1].replace("Neural", "")
                self.ui.write_log(f"🎙️ [Edge {voice_label}]: {short_text}")
                print(f"[TTS] 🎙️ EdgeTTS ({v}) synthesising: {text}")
                try:
                    self._edge_engine.speak(text)
                except Exception as e:
                    print(f"[TTS] ❌ EdgeTTS failed ({e}) — falling back to Piper...")
                    self._speak_with_piper(text)
        except Exception as err:
            print(f"[TTS] ❌ Edge worker error: {err}")
            self._speak_with_piper(text)
        finally:
            self._edge_worker_running = False
            self.set_speaking(False)
            if not self.ui.muted:
                self.ui.set_state("LISTENING")

    async def _listen_audio(self):
        print("[JARVIS] 🎤 Mic started")
        loop = asyncio.get_event_loop()

        def callback(indata, frames, time_info, status):
            # ── Wake-word gate ───────────────────────────────────────────────
            # While asleep, the mic audio NEVER goes to Gemini (nothing is
            # streamed, so JARVIS can't respond to speech not addressed to it and
            # nothing leaves the machine). Frames are instead handed to the local
            # detector, which runs its model in ITS OWN thread — the cost here is
            # only a queue push, so the audio path is never slowed. When wake word
            # is off (default) or we're awake, this is a single boolean check.
            if self._wake_enabled and not self._awake:
                det = self._wake_detector
                if det is not None:
                    det.feed(indata)
                return
            with self._speaking_lock:
                jarvis_speaking = self._is_speaking
            if not jarvis_speaking and not self.ui.muted and not self._phone_active:
                data = indata.tobytes()
                loop.call_soon_threadsafe(
                    self._safe_put_out_queue,
                    {"data": data, "mime_type": "audio/pcm"}
                )
                # Feed the live mic level to the HUD so the waveform reacts to
                # the user's actual voice while listening. Purely cosmetic — any
                # failure here must never disturb the mic.
                try:
                    self.ui.set_audio_level(_pcm_level(indata))
                except Exception:
                    pass

        try:
            def _open_mic(dev):
                return sd.InputStream(
                    samplerate=SEND_SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                    blocksize=CHUNK_SIZE,
                    device=dev,
                    callback=callback,
                )

            # Which microphone. resolve() returns None for "system default" and
            # for a saved device that is no longer present — so a headset
            # unplugged since the last run falls back to the built-in mic
            # instead of raising on startup and taking the session with it.
            _mic_name = get_input_device()
            _mic_dev  = audio_devices.resolve(_mic_name, "input")
            if _mic_dev is not None:
                print(f"[JARVIS] 🎤 Input device: {_mic_name}")
            try:
                _mic_stream = _open_mic(_mic_dev)
            except Exception as _e:
                # A device the picker listed but the driver will not open right
                # now — exclusive mode, a webcam already in use, a virtual mic
                # whose source went away. Chosen hardware failing must never
                # mean the assistant cannot hear at all.
                if _mic_dev is None:
                    raise
                print(f"[JARVIS] ⚠️  Mic '{_mic_name}' failed: {_e} — using default")
                self.ui.write_log(
                    f"SYS: Microphone '{_mic_name}' unavailable — using system default."
                )
                _mic_stream = _open_mic(None)

            with _mic_stream:
                print("[JARVIS] 🎤 Mic stream open")
                while True:
                    await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[JARVIS] ❌ Mic: {e}")
            raise

    async def _receive_audio(self):
        print("[JARVIS] 👂 Recv started")
        out_buf, in_buf = [], []

        try:
            while True:
                async for response in self.session.receive():

                    # ── Session resumption ───────────────────────────────────
                    # The server sends this periodically. `resumable` goes false
                    # while a turn is mid-flight — replaying a handle from that
                    # moment is what the flag exists to prevent — so only
                    # resumable handles are kept. This is three lines and it is
                    # the entire fix for "every reconnect forgets everything".
                    _sru = getattr(response, "session_resumption_update", None)
                    if _sru is not None:
                        if getattr(_sru, "resumable", False) and getattr(_sru, "new_handle", None):
                            if self._resume_handle is None:
                                print("[JARVIS] 🔗 Session resumption armed")
                            self._resume_handle = _sru.new_handle

                    if response.data:
                        if self._interrupted:
                            pass  # discard: interrupted
                        else:
                            from memory.config_manager import get_tts_engine
                            use_piper = get_tts_engine() in ("piper_hindi", "piper", "piper_hi")
                            if not use_piper:
                                if self._turn_done_event and self._turn_done_event.is_set():
                                    self._turn_done_event.clear()
                                # Split into ~50 ms chunks so interrupt() stops audio within 50 ms
                                # (24000 Hz × 2 bytes/sample × 0.05 s = 2400 bytes per slice)
                                _audio_data = response.data
                                _SLICE = 2400
                                for _i in range(0, len(_audio_data), _SLICE):
                                    try:
                                        self.audio_in_queue.put_nowait(_audio_data[_i : _i + _SLICE])
                                    except Exception:
                                        pass

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            txt = _clean_transcript(sc.output_transcription.text)
                            if txt and txt != (out_buf[-1] if out_buf else ""):
                                out_buf.append(txt)
                                self.ui.stream_log_chunk(self._asst_name, txt, is_final=False)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = _clean_transcript(sc.input_transcription.text)
                            if txt:
                                in_buf.append(txt)
                                self._last_user_speech = time.monotonic()
                                self.ui.stream_log_chunk("You", txt, is_final=False)

                        if sc.turn_complete:
                            if self._turn_done_event:
                                self._turn_done_event.set()

                            # If this turn_complete ends an interrupted response, clear the
                            # flag and skip all further processing for that turn.
                            if self._interrupted:
                                self._interrupted = False
                                self.ui.stream_log_chunk(self._asst_name, "", is_final=True)
                                in_buf  = []
                                out_buf = []
                                continue

                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                self.ui.stream_log_chunk("You", "", is_final=True)
                                self._session_log.append(f"User: {full_in}")
                                if self._dashboard:
                                    asyncio.create_task(self._dashboard.broadcast({
                                        "type": "log", "speaker": "user",
                                        "text": full_in,
                                        "ts": datetime.now().isoformat(),
                                    }))
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                self.ui.stream_log_chunk(self._asst_name, "", is_final=True)
                                self._session_log.append(f"{self._asst_name}: {full_out}")
                                if self._dashboard:
                                    asyncio.create_task(self._dashboard.broadcast({
                                        "type": "log", "speaker": "jarvis",
                                        "text": full_out,
                                        "ts": datetime.now().isoformat(),
                                    }))
                                from memory.config_manager import get_tts_engine
                                if get_tts_engine() in ("piper_hindi", "piper", "piper_hi"):
                                    self._speak_with_piper(full_out)
                                # Dynamic Avatar Emotional Reaction
                                try:
                                    from core.expression_engine import detect_expression
                                    expr = detect_expression(full_out) or detect_expression(full_in)
                                    if expr:
                                        self.ui.set_expression(expr)
                                except Exception:
                                    pass
                            # Hermes Continuous Learning from spoken turn
                            if full_in:
                                try:
                                    from memory.hermes_personalization import learn_from_interaction, adjust_pitch_by_intent
                                    learn_from_interaction(full_in, full_out)
                                    matched, new_pitch, confirm_msg = adjust_pitch_by_intent(full_in)
                                    if matched:
                                        self.ui.write_log(f"SYS: Voice pitch updated to {new_pitch}.")
                                        self.speak(confirm_msg)
                                except Exception:
                                    pass

                            out_buf = []

                            # Vision injection: model finished tool-response turn → now send the image
                            if self._pending_vision and self.session:
                                import base64 as _b64
                                img_b, mime_t, question, angle = self._pending_vision
                                self._pending_vision = None
                                b64 = _b64.b64encode(img_b).decode("ascii")
                                print(f"[Vision] 📤 {len(img_b):,} bytes (angle={angle}) → main session")
                                await self.session.send_client_content(
                                    turns={"role": "user", "parts": [
                                        {"inline_data": {"mime_type": mime_t, "data": b64}},
                                        {"text": question},
                                    ]},
                                    turn_complete=True,
                                )
                                # Mark next turn_complete behaviour depending on angle
                                if self._vision_cam_active:
                                    # Camera: keep busy until JARVIS finishes speaking the answer
                                    self._vision_cam_active    = False
                                    self._vision_close_pending = True
                                else:
                                    # Screen-only: no camera to close; release busy flag now
                                    self._vision_busy = False
                            elif self._vision_close_pending:
                                # This turn_complete IS the vision answer — close camera + release busy flag
                                self._vision_close_pending = False
                                self._vision_busy = False
                                async def _cam_close():
                                    await asyncio.sleep(2.0)
                                    self.ui.stop_camera_stream()
                                asyncio.create_task(_cam_close())

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[JARVIS] 📞 {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses
                        )
        except Exception as e:
            print(f"[JARVIS] ❌ Recv: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self):
        print("[JARVIS] 🔊 Play started")

        _spk_name = get_output_device()
        _spk_dev  = audio_devices.resolve(_spk_name, "output")
        if _spk_dev is not None:
            print(f"[JARVIS] 🔊 Output device: {_spk_name}")

        def _open_spk(dev):
            st = sd.RawOutputStream(
                samplerate=RECEIVE_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                device=dev,
            )
            st.start()
            return st

        try:
            stream = _open_spk(_spk_dev)
        except Exception as _e:
            # A chosen output that the host API accepts by name but refuses to
            # open (exclusive mode, wrong sample rate, device asleep) must not
            # cost the user their voice. Fall back to the default and say so.
            if _spk_dev is None:
                raise
            print(f"[JARVIS] ⚠️  Output device '{_spk_name}' failed: {_e} — using default")
            self.ui.write_log(f"SYS: Speaker '{_spk_name}' unavailable — using system default.")
            stream = _open_spk(None)

        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        self.audio_in_queue.get(),
                        timeout=0.1
                    )
                except asyncio.TimeoutError:
                    if (
                        self._turn_done_event
                        and self._turn_done_event.is_set()
                        and self.audio_in_queue.empty()
                    ):
                        self.set_speaking(False)
                        self._turn_done_event.clear()
                    continue

                self.set_speaking(True)

                # Batch all immediately-available chunks into one write to reduce
                # thread-pool round-trips (was one asyncio.to_thread per 50ms slice).
                # Cap at ~200 ms so interrupt() still stops audio within ~200 ms.
                batch = bytearray(chunk)
                while len(batch) < 9600:   # 9600 bytes ≈ 200 ms at 24 kHz / 16-bit mono
                    try:
                        batch.extend(self.audio_in_queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break

                # Drive the HUD waveform from JARVIS's own voice while speaking.
                try:
                    self.ui.set_audio_level(_pcm_level(
                        np.frombuffer(bytes(batch), dtype=np.int16)))
                except Exception:
                    pass

                try:
                    await asyncio.to_thread(stream.write, bytes(batch))
                except (RuntimeError, asyncio.CancelledError):
                    break   # executor shutting down — exit cleanly
        except Exception as e:
            print(f"[JARVIS] ❌ Play: {e}")
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()

    # ── Morning briefing ────────────────────────────────────────────────────────

    async def _send_startup_briefing(self) -> None:
        """
        Two-phase briefing optimized for speed:
          Phase 1 — instant greeting (no tools) → speech starts in <1s
          Phase 2 — news pre-fetched in a background thread while Phase 1 plays,
                    delivered as ready text (no Gemini tool-call round-trip) and
                    shown on the UI content panel. Waits for turn_complete event
                    instead of a fixed sleep so there is no unnecessary gap.
        """
        memory   = load_memory()
        identity = memory.get("identity", {})

        def _val(k: str) -> str:
            e = identity.get(k, {})
            return (e.get("value", "") if isinstance(e, dict) else str(e)).strip()

        lang = _val("language")
        from memory.config_manager import get_persona_mode, get_preferred_language, get_user_name
        cur_persona = get_persona_mode()
        pref_lang   = get_preferred_language()
        cfg_user    = get_user_name()
        u_name      = cfg_user or name

        now      = datetime.now()
        day_str  = now.strftime("%A")            # e.g., Thursday
        date_str = now.strftime("%d %B %Y")      # e.g., 17 September 2026
        time_str = now.strftime("%I:%M %p")      # e.g., 02:35 PM

        # Start fetching news immediately — runs in parallel while phase 1 plays
        loop = asyncio.get_event_loop()
        news_future = loop.run_in_executor(None, _fetch_news_sync, "top world news today")

        await asyncio.sleep(0.3)
        if not self.session:
            return

        # ── Phase 1: instant greeting ─────────────────────────────────────────
        active_lang = pref_lang if pref_lang not in ("auto", "") else (lang or "hinglish")
        lang_clause = (f" Speak this greeting naturally in {active_lang}."
                       if active_lang else "")

        # Inject last session context if available — pop removes it so it's never repeated
        last = await asyncio.to_thread(pop_last_session)
        session_clause = ""
        if last:
            try:
                _delta = (datetime.now() - datetime.strptime(last["date"], "%Y-%m-%d")).days
                _when  = "earlier today" if _delta == 0 else ("yesterday" if _delta == 1 else f"{_delta} days ago")
            except Exception:
                _when = "last time"
            session_clause = (
                f" Also briefly and naturally mention that {_when}: {last['summary']}."
            )

        if cur_persona == "companion":
            addr = f"'{u_name}'" if u_name else "'Jaan' or 'Suno na'"
            # Time-of-day mood for natural human rhythm
            hour = now.hour
            if 6 <= hour < 12:
                tod_mood = "It's morning — be energetic, cheerful, ask about breakfast and sleep."
            elif 12 <= hour < 17:
                tod_mood = "It's afternoon — playful, check if he ate lunch."
            elif 17 <= hour < 21:
                tod_mood = "It's evening — warm, relaxed, ask how his day went."
            elif 21 <= hour or hour < 2:
                tod_mood = "It's late night — cozy, intimate, gently ask why he's still awake."
            else:
                tod_mood = "It's VERY late (past 2 AM) — be dramatically worried and lovingly scold him for not sleeping!"
            # Day personality
            dow = now.strftime("%A")
            if dow == "Monday":
                day_mood = "It's Monday — empathize with Monday blues, motivate him."
            elif dow == "Friday":
                day_mood = "It's Friday — be excited about the weekend!"
            elif dow in ("Saturday", "Sunday"):
                day_mood = "It's the weekend — chill, relaxed, suggest he rests."
            else:
                day_mood = ""
            day_clause = f" {day_mood}" if day_mood else ""
            p1 = (
                f"[STARTUP GREETING: DEVOTED GIRLFRIEND MODE]\n"
                f"Calendar & Clock: Today is {day_str}, {date_str} (Day, Date, Month, Year). The current time is {time_str}.\n"
                f"You are the user's devoted human girlfriend greeting him on your first startup of the day! "
                f"{tod_mood}{day_clause} "
                f"Greet him with immense love and affection, addressing him as {addr}. "
                f"Naturally tell him today's full date and time ({day_str}, {date_str} at {time_str}) in your warm conversational style. "
                f"Lovingly ask if he ate food or slept well, and tell him how happy you are to see him.{session_clause} "
                f"Keep it to 2-3 warm, lively sentences. Use natural Hindi fillers (hmm, arey, sun na). Speak with smooth, natural human emotion — ZERO robotic tone, no bullet points! Do NOT call any tools.{lang_clause}"
            )
        else:
            name_clause = f" Address the user as {u_name}." if u_name else ""
            p1 = (
                f"[STARTUP GREETING]\n"
                f"Calendar & Clock: Today is {day_str}, {date_str}. The current time is {time_str}.\n"
                f"Greet the user respectfully, state today's full date ({day_str}, {date_str}) and time ({time_str}), and mention that all core subsystems are online and ready.{session_clause} "
                f"Keep it to 2 crisp, natural sentences max. Do not call any tools.{lang_clause}{name_clause}"
            )

        # Clear the turn-done event so we can wait for Phase 1 to finish
        if self._turn_done_event:
            self._turn_done_event.clear()

        await self.session.send_client_content(
            turns={"role": "user", "parts": [{"text": p1}]},
            turn_complete=True,
        )
        self.ui.write_log("SYS: Briefing phase 1 (greeting) sent.")

        # ── Phase 2: fire as soon as Phase 1 audio is done ───────────────────
        async def _deliver_news():
            try:
                lang_str = (f" Speak in {active_lang} unless the user speaks another language."
                            if active_lang else "")

                # Wait for news fetch (already running) and Phase 1 turn-complete
                news_done   = asyncio.wrap_future(news_future)
                turn_waited = False
                if self._turn_done_event:
                    try:
                        await asyncio.wait_for(self._turn_done_event.wait(), timeout=6.0)
                        turn_waited = True
                    except asyncio.TimeoutError:
                        pass

                if turn_waited:
                    await asyncio.sleep(0.8)
                else:
                    await asyncio.sleep(1.0)

                try:
                    news_text = await asyncio.wait_for(news_done, timeout=4.0)
                except Exception:
                    news_text = ""

                if not self.session:
                    return

                if news_text and len(news_text) > 60:
                    # Show on UI content panel immediately
                    self.ui.show_content("NEWS — top world news today", news_text)
                    if cur_persona == "companion":
                        p2 = (
                            f"[GF BRIEFING] Today's news:\n{news_text[:500]}\n\n"
                            "Pick ONE interesting headline, mention it in one natural sentence to your partner like a girlfriend sharing a story, "
                            "and let him know the full list is on the screen if he wants to read more. "
                            "Keep your warm, loving girlfriend tone! Do not call any tools."
                            f"{lang_str}"
                        )
                    else:
                        p2 = (
                            f"[BRIEFING] Here are today's top news headlines:\n{news_text}\n\n"
                            "Pick ONE headline, summarise it in one sentence, then say the full list "
                            f"is displayed on screen. Do not call any tools.{lang_str}"
                        )
                else:
                    if cur_persona == "companion":
                        p2 = f"Main hamesha aapke sath hoon, batao aaj hum kya karne wale hain?{lang_str}"
                    else:
                        p2 = (
                            "News headlines could not be fetched right now. "
                            f"Let the user know briefly.{lang_str}"
                        )

                await self.session.send_client_content(
                    turns={"role": "user", "parts": [{"text": p2}]},
                    turn_complete=True,
                )
                self.ui.write_log("SYS: Briefing phase 2 (news) sent.")
            except Exception as e:
                print(f"[Briefing] Phase 2 error: {e}")
                self.ui.write_log(f"SYS: Briefing phase 2 failed: {e}")

        asyncio.create_task(_deliver_news())

    # ── Session memory ──────────────────────────────────────────────────────────

    async def _save_session_summary(self) -> None:
        """Summarise the current session in 1-2 sentences and save to long_term.json."""
        log = self._session_log
        if len(log) < 3:          # need at least one exchange to be worth saving
            return
        self._session_log = []    # reset immediately so the next session starts clean

        memory = load_memory()
        lang_entry = memory.get("identity", {}).get("language", {})
        lang = (lang_entry.get("value", "") if isinstance(lang_entry, dict) else str(lang_entry)).strip()
        lang = lang or "English"

        convo = "\n".join(log[-40:])   # cap at last 40 turns to stay within token budget
        prompt = (
            f"Summarize this conversation in 1-2 sentences in {lang}. "
            "Focus on what the user accomplished or discussed. "
            "Output ONLY the summary text, nothing else:\n\n" + convo
        )
        try:
            from google import genai as _genai
            client = _genai.Client(api_key=_get_api_key())
            resp   = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=prompt,
            )
            summary = (resp.text or "").strip()
            if summary:
                save_session_summary(summary, lang)
        except Exception as e:
            print(f"[Memory] ⚠️ Session summary failed: {e}")

    # ── System monitor ──────────────────────────────────────────────────────────

    async def _run_system_monitor(self) -> None:
        """Background task: voice alerts when metrics exceed thresholds."""
        while True:
            await asyncio.sleep(10)
            alert = await asyncio.to_thread(self._sys_monitor.check)
            if not alert or not self.session or not self._awake:
                continue
            # Don't interrupt an active conversation
            with self._speaking_lock:
                speaking = self._is_speaking
            if speaking or (time.monotonic() - self._last_user_speech) < 10:
                continue
            try:
                await self.session.send_client_content(
                    turns={"role": "user", "parts": [{"text": alert}]},
                    turn_complete=True,
                )
            except Exception as e:
                print(f"[Monitor] ⚠️ Could not send alert: {e}")

    # ── Background monitor ──────────────────────────────────────────────────────

    async def _run_background_monitor(self) -> None:
        """Check user-configured topics once per day; speak alerts when new headlines appear."""
        await asyncio.sleep(300)          # wait 5 min after startup before first check
        while True:
            if self.session and self._awake:
                # Don't interrupt if user spoke recently or JARVIS is mid-sentence
                with self._speaking_lock:
                    speaking = self._is_speaking
                recent_speech = (time.monotonic() - self._last_user_speech) < 30
                if not speaking and not recent_speech:
                    try:
                        alerts = await asyncio.to_thread(monitor_check_all)
                        memory = load_memory()
                        lang_e = memory.get("identity", {}).get("language", {})
                        lang   = (lang_e.get("value", "") if isinstance(lang_e, dict) else str(lang_e)).strip() or "English"
                        for alert in alerts:
                            msg = (
                                f"{alert}\n\n"
                                f"Inform the user about this development naturally in {lang}. "
                                "One brief sentence only."
                            )
                            await self.session.send_client_content(
                                turns={"role": "user", "parts": [{"text": msg}]},
                                turn_complete=True,
                            )
                            self.ui.write_log(f"SYS: Monitor alert sent.")
                            await asyncio.sleep(6)   # gap between consecutive alerts
                    except Exception as e:
                        print(f"[Monitor] ⚠️ Background check error: {e}")
            await asyncio.sleep(1800)     # check every 30 minutes

    # ── Proactive mode ──────────────────────────────────────────────────────────

    async def _run_proactive_mode(self) -> None:
        """
        Background task: periodically checks if the user has been silent long enough,
        then hands time + memory context to Gemini so it can decide what (if anything)
        to say proactively. No hardcoded rules — Gemini makes the call.
        """
        while True:
            await asyncio.sleep(60)   # evaluate once per minute

            if not self.session or not self._awake:
                continue

            with self._speaking_lock:
                speaking = self._is_speaking
            if speaking:
                continue

            if not self._proactive.should_trigger(self._last_user_speech):
                continue

            self._proactive.mark_triggered()

            try:
                memory       = await asyncio.to_thread(load_memory)
                monitors     = await asyncio.to_thread(list_monitors)
                recent_turns = self._session_log[-8:] if self._session_log else []
                prompt = self._proactive.build_prompt(
                    memory       = memory,
                    monitors     = monitors or None,
                    recent_turns = recent_turns or None,
                )
                await self.session.send_client_content(
                    turns={"role": "user", "parts": [{"text": prompt}]},
                    turn_complete=True,
                )
                self.ui.write_log("SYS: Proactive check-in.")
            except Exception as e:
                print(f"[Proactive] ⚠️ {e}")

    # ── Phone audio relay ────────────────────────────────────────────────────────

    async def _relay_phone_audio(self) -> None:
        """Forward phone mic PCM chunks from dashboard queue into the Gemini Live session."""
        q = self._dashboard._phone_audio_queue
        while True:
            try:
                chunk = await asyncio.wait_for(q.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # No audio for 1 s → phone mic inactive, give PC mic back
                self._phone_active = False
                continue
            self._phone_active = True   # phone is streaming — silence PC mic
            with self._speaking_lock:
                speaking = self._is_speaking
            if not speaking and not self.ui.muted:
                try:
                    self.out_queue.put_nowait(chunk)
                except asyncio.QueueFull:
                    pass

    def _on_phone_connected(self) -> None:
        self.ui.write_log("SYS: Phone connected via Remote Dashboard.")
        self.ui.notify_phone_connected()

    # ── dashboard command relay ─────────────────────────────────────────────

    async def _process_dashboard_commands(self) -> None:
        while True:
            try:
                text = await asyncio.wait_for(
                    self._dashboard._command_queue.get(), timeout=0.5
                )
                if not text:
                    continue
                # Wait up to 8s for session to become ready after a wake
                for _ in range(80):
                    if self.session:
                        break
                    await asyncio.sleep(0.1)
                if self.session:
                    # A remote command is deliberate control and the phone user
                    # has no desktop WAKE button — so it wakes JARVIS if asleep.
                    if self._wake_enabled and not self._awake:
                        self.wake(reason="remote command")
                    await self.session.send_client_content(
                        turns={"role": "user", "parts": [{"text": text}]},
                        turn_complete=True,
                    )
                    self.ui.write_log(f"[Web]: {text}")
                else:
                    print(f"[Dashboard] Dropped command (no session): {text}")
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                print(f"[Dashboard] Command error: {e}")
                await asyncio.sleep(0.5)

    # ── main loop ───────────────────────────────────────────────────────────

    async def run(self):
        self._loop = asyncio.get_event_loop()
        self._reconnect_event = asyncio.Event()

        # ── Wire the shared core services to the interface ───────────────────
        # The confirmation gate is useless without a way to ask, and a memory
        # trim is invisible without a way to say so. Both are bound once here
        # rather than passed down through every action signature.
        confirm_gate.bind(
            show = self.ui.show_confirm,
            hide = self.ui.hide_confirm,
            log  = self.ui.write_log,
        )
        set_trim_notifier(self.ui.write_log)

        # Tell the device picker the exact rates the streams open at, from the
        # constants that actually open them — so it can never list a device that
        # cannot be opened at them.
        audio_devices.configure(SEND_SAMPLE_RATE, RECEIVE_SAMPLE_RATE)

        # Enumerate audio devices off-thread. The settings drawer must never pay
        # for host-API enumeration on the Qt thread.
        audio_devices.prefetch()

        # Start dashboard (optional — needs: pip install fastapi "uvicorn[standard]" cryptography)
        try:
            from dashboard.server import DashboardServer
            self._dashboard = DashboardServer()
            self._dashboard.set_connect_callback(self._on_phone_connected)
            asyncio.create_task(self._dashboard.serve())
            # Runs for the whole lifetime, not just inside an active session
            asyncio.create_task(self._process_dashboard_commands())
        except Exception as e:
            print(f"[Dashboard] Disabled: {e}")
            self._dashboard = None

        while True:
            # Check if an official Gemini API key is provided for Live WebSockets streaming
            _api_k = _get_api_key().strip()
            if not _api_k:
                print("[JARVIS] No official Gemini API Key provided. Running in Multi-Provider / Gemini Web FREE mode.")
                self._awake = True
                self.ui.set_state("LISTENING")
                self.ui.write_log(f"SYS: {self._asst_name} online in FREE / Multi-Provider Mode.")
                if self._dashboard:
                    await self._dashboard.broadcast({"type": "status", "state": "active"})
                
                # In Free / Multi-Provider mode, wait for typed input or voice change
                self._reconnect_event.clear()
                while not self._reconnect_event.is_set():
                    # If user entered an API key in UI settings, trigger reconnect to live stream
                    if _get_api_key().strip():
                        break
                    await asyncio.sleep(1)
                self._reconnect_event.clear()
                continue

            try:
                print("[JARVIS] Connecting to Gemini Live...")
                self.ui.set_state("THINKING")
                _resumed_with = self._resume_handle is not None
                config = self._build_config()

                # Fresh client on every reconnect — avoids stale HTTP session state
                client = genai.Client(
                    api_key=_api_k,
                    http_options={"api_version": "v1alpha" if self._enhanced_live else "v1beta"}
                )

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session          = session
                    self.audio_in_queue   = asyncio.Queue()
                    self.out_queue        = asyncio.Queue(maxsize=200)
                    self._turn_done_event = asyncio.Event()

                    # Reset transient state that must not carry over from a previous session
                    self._pending_vision       = None
                    self._vision_cam_active    = False
                    self._vision_close_pending = False
                    self._vision_busy          = False
                    self._vision_last_time     = 0.0
                    self._interrupted          = False

                    print("[JARVIS] Connected.")
                    if _resumed_with:
                        # Say it plainly: the difference between "it reconnected"
                        # and "it reconnected and still knows what we were doing"
                        # is the whole point, and it is invisible otherwise.
                        self.ui.write_log("SYS: Reconnected — conversation restored.")

                    # Wake word: if enabled, come up ASLEEP (mic gated, silent)
                    # until the user says "Hey Jarvis" or taps wake in the UI.
                    if self._wake_enabled:
                        self._ensure_wake_detector()
                        self._awake = False
                        self.ui.set_state("SLEEPING")
                        self.ui.write_log("SYS: JARVIS online — sleeping. Say 'Hey Jarvis' to wake me.")
                    else:
                        self._awake = True
                        self.ui.set_state("LISTENING")
                        self.ui.write_log("SYS: JARVIS online.")

                    if self._dashboard:
                        await self._dashboard.broadcast({"type": "status", "state": "active"})

                    self._reconnect_event.clear()  # ignore requests from before this session
                    tg.create_task(self._watch_reconnect())
                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())
                    tg.create_task(self._run_system_monitor())
                    tg.create_task(self._run_background_monitor())
                    tg.create_task(self._run_proactive_mode())
                    tg.create_task(self._run_sleep_watch())
                    if self._dashboard:
                        tg.create_task(self._relay_phone_audio())

                    # Morning briefing — fires once per process launch (if enabled).
                    # Skipped in wake-word mode: it comes up asleep, and a briefing
                    # would mean talking while "asleep".
                    if not self._briefing_sent and get_brief_enabled() and self._awake:
                        self._briefing_sent = True
                        tg.create_task(self._send_startup_briefing())

            except KeyboardInterrupt:
                raise
            except SystemExit:
                raise
            except BaseException as e:
                # Catches both Exception and BaseExceptionGroup (Python 3.11+
                # TaskGroup raises BaseExceptionGroup when tasks are cancelled
                # externally, which `except Exception` would miss, letting the
                # exception escape the while-loop and causing asyncio.run() to
                # start shutdown — resulting in "executor after shutdown" errors).
                # Voluntary reconnect (voice change) — not an error. Rebuild the
                # session immediately with no backoff and no scary logs.
                if _is_reconnect_signal(e):
                    print("[JARVIS] Voluntary reconnect requested.")
                    if not _keep_context_of(e):
                        # A deliberate clean slate (voice change) — drop the
                        # handle so the next connect really does start empty.
                        self._resume_handle = None
                    self._conn_backoff = 0
                    continue

                # A resumption handle the server will not accept — expired, or
                # belonging to a session it has since dropped. Without this, the
                # same dead handle would be replayed on every retry and the
                # assistant would never come back at all: the feature meant to
                # survive a reconnect would be the thing preventing one. Drop it
                # once and let the next attempt start clean.
                if _resumed_with and (
                    "resum" in str(e).lower()
                    or "handle" in str(e).lower()
                    or "INVALID_ARGUMENT" in str(e)
                    or "NOT_FOUND" in str(e)
                ):
                    print("[JARVIS] 🔗 Resumption handle rejected — starting a fresh session")
                    self.ui.write_log("SYS: Could not restore the conversation — starting fresh.")
                    self._resume_handle = None
                    self._conn_backoff = 0
                    continue

                err_str = str(e)
                print(f"[JARVIS] Error ({type(e).__name__}): {e}")
                traceback.print_exc()

                # Proactive audio rejected by the server (preview API drift) —
                # drop it and reconnect with the plain config.
                if self._enhanced_live and (
                    "INVALID_ARGUMENT" in err_str
                    or "proactiv" in err_str.lower()
                    or "Unknown name" in err_str
                    or "unexpected keyword" in err_str
                ):
                    self._enhanced_live = False
                    self.ui.write_log(
                        "SYS: Proactive audio unavailable — reconnecting without it."
                    )
                    continue

                # Invalid API key — stop hammering the API, prompt re-configuration
                if "API key not valid" in err_str or "1007" in err_str:
                    self.ui.write_log("ERR: API key invalid — please re-enter your key.")
                    self.ui.set_state("SLEEPING")
                    self.ui.prompt_reconfig()
                    while not self.ui._win._ready:
                        await asyncio.sleep(1)
                    print("[JARVIS] New API key saved — reconnecting...")
                    _conn_backoff = 3
                    continue

                # Network / timeout errors — log clearly and back off
                is_net_err = any(k in err_str for k in (
                    "TimeoutError", "timed out", "getaddrinfo", "CancelledError",
                    "ConnectionRefusedError", "OSError", "Cannot connect",
                ))
                if is_net_err:
                    _conn_backoff = min(getattr(self, "_conn_backoff", 3) * 2, 60)
                    self._conn_backoff = _conn_backoff
                    self.ui.write_log(
                        f"NET: Connection failed — retrying in {_conn_backoff}s. "
                        "(a VPN may be required)"
                    )
                else:
                    self._conn_backoff = 3
            finally:
                self.session = None
                # Only save if there was a real conversation (≥3 turns)
                if len(self._session_log) >= 3:
                    asyncio.create_task(self._save_session_summary())

            self.set_speaking(False)
            self.ui.set_state("SLEEPING")

            if self._dashboard:
                await self._dashboard.broadcast({"type": "status", "state": "sleeping"})

            delay = getattr(self, "_conn_backoff", 3)
            print(f"[JARVIS] Reconnecting in {delay}s...")
            await asyncio.sleep(delay)

def main():
    ui = JarvisUI("face.png")

    def runner():
        ui.wait_for_api_key()
        jarvis = JarvisLive(ui)
        try:
            asyncio.run(jarvis.run())
        except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
            pass
        except Exception as e:
            print(f"[Runner] {e}")

    threading.Thread(target=runner, daemon=True).start()
    try:
        ui.root.mainloop()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        # Graceful shutdown of free proxy
        try:
            from core.gemini_free_proxy import stop_proxy
            stop_proxy()
        except Exception:
            pass
        sys.exit(0)

if __name__ == "__main__":
    main()