# 🛠️ J.A.R.V.I.S. — NEXT PATCH ROADMAP & IMPLEMENTATION SPECIFICATION
> **Document:** `nextpatch.md`  
> **Status:** Research & Architecture Plan (Ready for Phase-Wise Development)  
> **Target System:** J.A.R.V.I.S. (SudhirDevOps1 AI)  
> **Engine:** Gemini Live + Multi-Brain Matrix + PyQt6 Cyberpunk HUD

---

## 🎯 Executive Overview

J.A.R.V.I.S. already possesses high-speed bidirectional voice streaming, offline wake-word detection (`openwakeword`), an interactive PyQt6 Cyberpunk HUD, an undo system, and 16 bundled system actions. 

This document outlines the **architectural blueprint, dependency requirements, technical design, and implementation steps** for the feature sets. By leveraging J.A.R.V.I.S.'s self-describing **`plugins/` system** and modular **`actions/` architecture**, these features can be dropped in without risking the stability of the core loop in `main.py`.

---

## 📋 Comprehensive Feature Breakdown (Items 1 to 8)

```
┌────────────────────────────────────────────────────────────────────────┐
│                        J.A.R.V.I.S. NEXT PATCH ARCHITECTURE            │
├──────────────────┬──────────────────┬─────────────────┬────────────────┤
│ 1. SMART HOME    │ 2. GESTURES      │ 3. SENTRY/FACE  │ 4. WORKSPACE   │
│ Tuya/Home Assist │ MediaPipe Vision │ DeepFace & Cam  │ Cal, Notion,   │
│ & Room Lighting  │ Air Navigation   │ Telegram Alerts │ Spotify API    │
├──────────────────┼──────────────────┼─────────────────┼────────────────┤
│ 5. PHONE SYNC    │ 6. GAMING / OBS  │ 7. STARK SFX    │ 8. OFFLINE LLM │
│ Call/SMS Alerts  │ "Clip That" OBS  │ Arc Reactor WAV │ Ollama / Llama │
│ & Ring My Phone  │ & Discord Hook   │ & Voice Cloning │ Fallback Core  │
├──────────────────┴──────────────────┴─────────────────┴────────────────┤
│ 9. 🇮🇳 NATIVE HINDI & HINGLISH DUAL-LANGUAGE SYSTEM (CODE-SWITCHING)   │
│ Natural Hindi/Hinglish speech, bilingual auto-adapt, tech term mapping │
├────────────────────────────────────────────────────────────────────────┤
│ 10. 🎙️ OFFLINE PIPER HINDI TTS ENGINE (DEVANAGARI SCRIPT OPTIMIZATION) │
│ hi_IN Pratham/Rohan models, Devanagari text synthesis, zero cloud cost │
└────────────────────────────────────────────────────────────────────────┘
```

---

### 1. 🏠 Smart Home & Room Automation (IoT)

* **Goal:** Enable JARVIS to control lights, plugs, and ambient room settings by voice (*"Jarvis, turn off the bedroom lights"*, *"Activate movie mode"*).
* **Architecture:** Drop-in plugin (`plugins/smart_home.py`).
* **Technology Stack:**
  - `tinytuya` (Already installed in environment! Supports direct LAN communication with Tuya/SmartLife bulbs without cloud lag).
  - Optional `homeassistant-api` / WebSocket client for advanced Home Assistant hubs.
* **Core Capabilities:**
  - Power toggles (`turn_on`, `turn_off`).
  - Brightness adjustment (0% to 100%).
  - Color presets (Warm white, Iron Man Red/Gold, Relaxing Blue).
  - Scenes integration (e.g., *"Movie Mode"* → dims room lights, lowers PC brightness to 30%, sets volume to 60%).
* **Configuration:**
  - Store device IDs, local keys, and IP addresses in `config/smart_home.json`.
* **Sample Plugin Tool Signature:**
  ```python
  PLUGIN = {
      "name": "smart_home_control",
      "description": "Control smart lights, plugs, and appliances in the room.",
      "parameters": {
          "type": "OBJECT",
          "properties": {
              "device_name": {"type": "STRING", "description": "e.g., bedroom light, desk lamp"},
              "action": {"type": "STRING", "enum": ["on", "off", "brightness", "color", "scene"]},
              "value": {"type": "STRING", "description": "Value for brightness or scene name"}
          },
          "required": ["device_name", "action"]
      }
  }
  ```

---

### 2. 👁️ Iron Man Gesture Control (Webcam Hand Tracking)

* **Goal:** Control PC functions with hand gestures in air via webcam (Iron Man hologram style).
* **Architecture:** Background vision worker thread managed by `actions/gesture_engine.py`, toggled from HUD or by voice (*"Jarvis, enable gesture control"*).
* **Technology Stack:**
  - `mediapipe` (Google's ultra-fast CPU hand-landmark model).
  - `opencv-python` (Already installed).
  - `pyautogui` (Already installed for mouse/keyboard simulation).
* **Gesture Mapping:**
  - ✋ **Open Palm Raised**: Instant Pause/Play or Mute/Unmute.
  - ✌️ **Two Fingers Pointing Up**: Volume Up.
  - 👇 **Two Fingers Pointing Down**: Volume Down.
  - 👈 / 👉 **Swipe Left / Right**: Next / Previous browser tab or desktop virtual workspace.
  - ✊ **Closed Fist**: Minimize all windows / Show desktop.
* **Safety & Performance:**
  - Process webcam frames at 15 FPS (reduced resolution 640x480) on a detached daemon thread to prevent UI stutter.
  - Add a 1.2-second debounce timer so gestures do not trigger repeatedly by accident.

---

### 3. 👤 Face Recognition & Sentry / Intruder Alert Mode

* **Goal:** Recognize the authorized user (*"Welcome back, Sir"*) and act as a digital guard dog when the user steps away.
* **Architecture:** Integrated with `actions/screen_processor.py` and a dedicated `plugins/sentry_mode.py`.
* **Technology Stack:**
  - `face_recognition` / `deepface` (Local biometric feature embedding).
  - `python-telegram-bot` or direct Telegram Bot HTTP Webhook (for zero-latency phone notifications).
* **Workflows:**
  1. **User Welcome**:
     - On waking up, snap a quick frame. If recognized user's face is found, personalized greeting is triggered.
  2. **Sentry Mode ("Watch My Desk")**:
     - User says: *"Jarvis, initiate Sentry Mode."*
     - PC locks screen or blanks display.
     - Webcam monitors for motion / unknown human faces.
     - When an unauthorized person sits in front of the computer:
       - Play subtle warning audio or remain silent.
       - Silently capture a timestamped high-res photo.
       - Send photo immediately to user's Telegram / WhatsApp: *"🚨 Alert: Unauthorized presence detected at workstation at 14:22."*

---

### 4. 📅 Productivity Ecosystem (Calendar, Notion, Spotify)

* **Goal:** Seamless synchronization with calendar schedules, task trackers, and Spotify music playback.
* **Architecture:** 3 independent drop-in plugins:
  - `plugins/calendar_tool.py` (Google Calendar API via OAuth).
  - `plugins/notion_tasks.py` (Notion official REST API).
  - `plugins/spotify_control.py` (Spotipy / Spotify Web API).
* **Capabilities:**
  - **Schedule Briefing**: *"What does my schedule look like today?"* → Reads Google Calendar events and incorporates them into the Morning Briefing.
  - **Quick Tasks**: *"Add 'Submit tax files by Friday' to my Notion inbox."* → Direct database insertion.
  - **Spotify Voice DJ**: *"Play Synthwave radio on Spotify"*, *"What song is playing?"*, *"Add this to my favorites"*.

---

### 5. 📱 Phone Ecosystem & Telephony Integration

* **Goal:** Bridge the gap between the Windows PC and the user's mobile device without paying for third-party cloud services.
* **Architecture:** `plugins/phone_bridge.py` + local lightweight REST webhook.
* **Technology Options:**
  - **KDE Connect / GSConnect**: Open-source, local Wi-Fi pairing. Exposes battery status, clipboard sync, media control, and ping.
  - **Pushbullet API**: Cloud notification push and SMS forwarding.
  - **Termux (Android)**: Run a tiny local script on Android to trigger ringing or send SMS.
* **Key Features:**
  - **"Find My Phone"**: Sends a high-priority ring signal that forces the phone to play loud alarm audio, even if in silent/vibrate mode.
  - **Battery Telemetry**: Alerts user when phone battery drops below 15% or reaches 100% full charge.
  - **Incoming Call Announcement**: HUD notification when phone receives a call.

---

### 6. 🎮 Gaming & Entertainment Companion

* **Goal:** Hands-free voice companion while playing full-screen video games.
* **Architecture:** `plugins/gaming_companion.py` utilizing `obs-websocket-py` or Windows Game Bar hotkeys.
* **Key Features:**
  - **"Jarvis, Clip That!"**:
    - Calls OBS WebSocket or triggers Windows Game Bar shortcut (`Win + Alt + G`) to automatically save the last 30 seconds of gameplay buffer into `Videos/Captures/`.
  - **Discord Voice Bot Integration**:
    - Join Discord voice channel as a bot user, allowing team members in voice chat to interact with JARVIS simultaneously.
  - **Performance Overlay**:
    - Voice query for in-game stats (*"What's my GPU temp right now?"*).

---

### 7. 🔊 Stark Sound Effects (SFX) & Custom Voice Cloning

* **Goal:** Elevate immersion with authentic Iron Man UI audio cues and movie-accurate voice.
* **Architecture:** Core sound manager enhancement in `core/sfx.py` and optional TTS routing in `core/tts.py`.
* **Components:**
  - **Futuristic SFX Engine**:
    - Multi-tiered audio dispatch in `core/sfx.py`: native Windows `winsound.PlaySound` (instant, zero-latency system audio bypass) + `sounddevice` fallback.
    - Sound triggers:
      - `boot.wav`: Arc-reactor startup hum when JARVIS initializes.
      - `wake.wav`: Subtle dual-tone beep when "Hey Jarvis" is recognized.
      - `ack.wav`: High-tech chirp when starting long tasks.
      - `confirm.wav`: Mechanical click when user hits Confirm banner.
  - **Arc Reactor Dynamic Mechanical Physics (`ui.py`)**:
    - Ambient idling hum: continuous rotation (`+0.22` deg outer, `-0.32` deg inner) and organic core breathing pulse even during reactive resting standby, ensuring the reactor never freezes or appears dead.
    - Dynamic hyper-drive acceleration on voice speech and thought processing.
  - **Paul Bettany / Custom Voice Cloning**:
    - While Gemini 3.1 Live has excellent native voices (Charon, Puck, etc.), power users can toggle an offline TTS engine (e.g., Coqui TTS / Piper TTS) or ElevenLabs API with an authentic Paul Bettany voice clone model.

---

### 8. 💻 Local Offline AI Fallback (Ollama / Llama 3 / DeepSeek)

* **Goal:** Ensure JARVIS never becomes a "dead app" if internet connection drops.
* **Architecture:** Fallback wrapper in `core/llm_client.py` and `main.py`.
* **How It Works:**
  - When Gemini Live WebSocket detects `NetworkUnreachable` or API downtime:
    1. Assistant switches from Gemini Live stream to **Local Mode**.
    2. Uses local **Ollama** (`http://localhost:11434/api/generate`) with a lightweight model (e.g. `llama3.2:3b` or `qwen2.5-coder:3b`).
    3. Uses local STT (`vosk` / `whisper.cpp`) and local TTS (`pyttsx3` / `piper`).
    4. Executes local PC commands (Volume, Brightness, Apps, File Search, Shutdown).
    5. Once internet returns, seamlessly flips back to Gemini 3.1 Flash Live.

---

### 9. 🇮🇳 Native Hindi & Hinglish Dual-Language System (Code-Switching)

* **Goal:** Enable JARVIS to understand and speak fluent Hindi and natural everyday Hinglish (*"Chrome open karo"*, *"Aaj mausam kaisa hai"*, *"Volume thoda badha do"*) without language switching lag or confusion.
* **Problem Analysis:**
  - Gemini 3.1 Flash Live natively possesses deep multilingual capabilities for Hindi (हिन्दी).
  - However, in `core/prompt.txt`, the rigid clause `Do not mix two languages in one reply` prevents the assistant from understanding natural code-switching (Hinglish) where English computer terms (Chrome, YouTube, Volume, Files) are blended with Hindi grammar.
  - Additionally, because the Morning Briefing is hardcoded in English, the initial audio context anchors to English.
* **Architecture & Prompt Optimization:**
  - **Prompt Protocol Update (`core/prompt.txt`)**:
    - Remove the `"Do not mix two languages in one reply"` ban.
    - Explicitly define Hinglish as a first-class language:
      ```text
      HINDI & HINGLISH SUPPORT:
      Hindi and Hinglish (natural code-switching between Hindi and English) are fully supported.
      If the user speaks Hindi or Hinglish, answer warmly and naturally in conversational Hindi/Hinglish.
      Respect ordinary technical names in English (e.g. Chrome, YouTube, Volume, Restart) within Hindi sentences (e.g. "Main abhi Chrome open kar raha hoon, Sir").
      ```
  - **Memory Persistence**:
    - Store `"language": "Hindi/Hinglish"` under identity in `memory/long_term.json`.
  - **Localized Morning Briefing**:
    - Add localized greeting option in `main.py` if Hindi is detected or selected.

---

### 10. 🎙️ Offline Piper Hindi TTS Engine (Devanagari Script-Optimized)

* **Goal:** Provide a 100% offline, natural Indian Hindi voice that runs directly on CPU with zero cloud API keys and zero latency, delivering authentic pronunciation without Western/American accents.
* **Why Piper TTS for Hindi?**
  - Piper uses fast VITS neural architecture compiled to ONNX, generating 1 second of speech in under 0.08s on a standard CPU.
  - Official high-quality Indian Hindi models available:
    - **`hi_IN-pratham-medium`**: Crisp, authoritative male assistant voice (JARVIS tone).
    - **`hi_IN-rohan-medium`**: Warm, natural everyday Indian conversational voice.
* **The Devanagari Script Principle (देवनागरी लिपि नियम):**
  - **The Problem:** When an offline phonetic Hindi model is fed Romanized English letters (*"Namaste sir, kaam ho gaya"*), it tries to interpret English phonemes, resulting in unnatural, distorted speech.
  - **The Solution:** Piper's Hindi phonemizer is trained directly on Unicode Devanagari characters. When fed Devanagari text (*"नमस्ते सर, आपका काम हो गया"*), it pronounces every vowel, consonant, and syllable with **100% native Indian cadence and clarity**!
* **Technical Architecture & Data Pipeline:**
  ```text
  [User Hindi Voice / Text Request]
                 │
                 ▼
     [Groq / Gemini / Local LLM]
                 │
                 ▼
  (Generates response in Devanagari: "नमस्ते सुधीर सर, मैं अभी Chrome खोल रहा हूँ।")
                 │
                 ▼
         [PiperTTSEngine]
   (hi_IN-pratham-medium.onnx)
                 │
                 ▼ (22.05 kHz PCM)
      [sounddevice Playback]
                 │
                 ▼
  [100% Natural Indian Speech out of Speakers]
  ```
* **Implementation Blueprint:**
  1. **Model Storage:**
     - Download `hi_IN-pratham-medium.onnx` and `hi_IN-pratham-medium.onnx.json` into `core/models/piper/`.
  2. **Class Integration (`core/tts.py`)**:
     ```python
     class PiperHindiTTSEngine:
         def __init__(self, model_path: str):
             import piper
             self.voice = piper.PiperVoice.load(model_path)

         def speak(self, text: str):
             import sounddevice as sd
             # Synthesize raw audio from Devanagari text
             audio = self.voice.synthesize(text)
             sd.play(audio, 22050)
             sd.wait()
     ```
  3. **Dual-Mode System Prompt Rule:**
     - When `offline_tts_engine: "piper"` is active:
       ```text
       PIPER TTS SCRIPT RULE:
       When speaking in Hindi, write your response exclusively in Devanagari script (देवनागरी लिपि).
       Example: "नमस्ते सर, आपका काम पूरा हो गया है।"
       Never output English transliteration (e.g. "kaam ho gaya") because the offline synthesizer requires Devanagari.
       ```
  4. **Settings UI Integration:**
     - In the Settings Drawer (**⚙ → LLM PROVIDERS & KEYS**), add a toggle:
       `TTS Engine: [ Gemini Live Voice | Piper Offline Hindi (Devanagari) ]`

---

## 🗓️ Implementation Roadmap (Phase-Wise Schedule)

| Phase | Focus Areas | Complexity | Status & Date | Estimated Files Involved |
|---|---|:---:|:---:|---|
| **Phase 0** | 🇮🇳 **Native Hindi Prompt & Code-Switching** | 🟢 Low | ✅ **Done (2026-09-14)** | `core/prompt.txt`, `memory/long_term.json` |
| **Phase 1** | 🎙️ **Piper Offline Hindi TTS (Devanagari)** + 🔊 **Stark SFX** | 🟢 Low | ✅ **Done (2026-09-14)** | `core/tts.py`, `core/models/piper/`, `core/sfx.py` |
| **Phase 1.5**| ⚡ **Pikachu HUD, Voice Lab & Multi-Provider Health Ping** | 🟡 Medium | ✅ **Done (2026-09-15)** | `ui.py`, `core/tts.py`, `core/multi_llm.py`, `core/system_info.py` |
| **Phase 1.6**| 🌐 **Free Open APIs, Storage Gauges, Log Deduplication & News Ticker** | 🟡 Medium | ✅ **Done (2026-09-15)** | `ui.py`, `core/system_info.py`, `core/tts.py` |
| **Phase 2** | 🧠 **Persona Engine & Devoted GF Mode** + 🔮 **Obsidian Dual-Sync** + 🌅 **Calendar Startup Greeting** | 🟢 High Value | ✅ **Done (2026-09-17)** | `core/persona_manager.py`, `actions/obsidian_brain.py`, `main.py`, `ui.py` |
| **Phase 3** | 🏠 **Tuya Smart Lighting Plugin** + 📅 **Workspace Bundle (Spotify/Cal)** | 🟡 Medium | ⏳ Scheduled | `plugins/smart_home.py`, `plugins/spotify.py` |
| **Phase 4** | 🛡️ **Sentry Mode & Telegram Alerts** + 🎮 **OBS "Clip That"** | 🟡 Medium | ⏳ Scheduled | `actions/sentry.py`, `plugins/gaming.py` |
| **Phase 5** | 👁️ **MediaPipe Gesture Control** + 💻 **Ollama Full Offline Stack** | 🔴 Advanced | ⏳ Scheduled | `actions/gesture_engine.py`, `core/llm_client.py` |

---

### 11. 🧠 Hermes-Style Continuous Self-Improvement & Personalized Persona Engine

* **Goal:** Just like Nous Hermes / MemGPT, the assistant continuously analyzes your conversation history, discovers who you are (your DevOps stack, command line preferences, preferred tone), and adapts its behavior to deliver hyper-personalized responses.
* **The Core Problem Today:** Standard assistants forget your habits the moment a session restarts, or rely only on manual `save_memory` tool calls.
* **The Hermes Architecture:**
  ```text
  [User Interaction / Conversation Turn]
                    │
                    ▼
     [Autonomous Reflection Daemon]
  (Runs silently off-thread every N turns or on idle)
                    │
                    ▼
       [Persona & Habit Extraction]
  - Role & Skills: DevOps, Docker, K8s, CI/CD, Python, PowerShell
  - Preferred Language: Hinglish / Hindi with tech terms
  - Coding Style: Concise scripts, error checks first, no fluff
  - Corrections: "User hates verbose explanations; wants raw commands"
                    │
                    ▼
      [memory/user_persona.json]
                    │
                    ▼
  [Injected dynamically into EVERY model's System Prompt (Groq, DeepSeek, Gemini)]
  ```
* **Persistent Knowledge Schema (`memory/user_persona.json`):**
  ```json
  {
    "user_identity": {
      "name": "Sudhir",
      "role": "DevOps Engineer & Automation Architect",
      "environment": "Windows 11, PowerShell 7, WSL2, Docker"
    },
    "learned_preferences": {
      "communication_style": "Fast, direct, technical Hinglish. Zero preamble.",
      "code_preference": "Executable one-liners, PowerShell/Bash scripts, robust error handling.",
      "frequently_used_tools": ["docker", "kubectl", "git", "python", "terraform"]
    },
    "correction_rules": [
      "Never generate cmd.exe commands; always provide modern PowerShell 7 syntax.",
      "Always suggest offline/local tools first before recommending paid cloud services."
    ]
  }
  ```

---

### 12. 🧭 Multi-Provider Smart Router & Model Selection Matrix

* **Goal:** Automatically select the best, fastest, and most cost-effective model across your 6–7 configured API providers so you get maximum intelligence with minimum token consumption.
* **Optimal Model Selection Matrix:**

| Provider | Recommended Model | Best Use Case | Speed | Token Cost | Why Use It? |
|---|---|---|:---:|:---:|---|
| **Groq** | `llama-3.3-70b-versatile` | ⚡ **Daily Driver & General Brain** | 280–320 tok/s | Extremely Low / Free Tier | Instantaneous response time, GPT-4 level general intelligence, zero wait. |
| **DeepSeek (Direct / OpenRouter)** | `deepseek/deepseek-r1` or `deepseek-chat` | 🛠️ **DevOps, Deep Debugging & Code Gen** | 40–80 tok/s | ~1/10th of OpenAI | World-class chain-of-thought reasoning, unbeatable for Kubernetes, Docker, and refactoring. |
| **Google Gemini** | `gemini-2.5-flash` | 🎙️ **Live Bidirectional Voice & Vision** | Real-time | Low | The only API capable of true 16 kHz live audio streaming with native camera vision. |
| **Groq / OpenRouter** | `llama-3.1-8b-instant` | 📉 **Ultra-Budget / Background Tasks** | 800+ tok/s | Near Zero | Perfect for background summarization, log analysis, and memory extraction. |
| **Local / Ollama** | `qwen2.5-coder:7b` or `llama3.2:3b` | 🛡️ **100% Offline Air-Gapped Fallback** | 30–60 tok/s | **$0.00 (Free)** | Runs on local CPU/GPU when internet is completely disconnected. |

* **Dynamic Autonomous Task Router:**
  - If query is **Vision/Audio** $\to$ Route to **Gemini 2.5 Flash**.
  - If query is **Coding / DevOps Architecture / Complex Debugging** $\to$ Route to **DeepSeek R1**.
  - If query is **General Command / Fast Q&A / System Control** $\to$ Route to **Groq Llama 3.3 70B**.
  - If Internet goes down $\to$ Gracefully degrade to **Local Ollama**.

---

### 13. 📊 Live Token & Cost Meter Widget

* **Goal:** Display real-time token counts (prompt tokens, completion tokens) and estimated session cost in the HUD footer to prevent surprise billing when using paid API keys.
* **Implementation:**
  - In `core/multi_llm.py`, capture `usage.prompt_tokens` and `usage.completion_tokens` on every completion.
  - Maintain session totals in memory.
  - Render a small Stark HUD status metric: `TOKENS: 4,820 | COST: $0.0021`.

---

### 14. 🚀 Zero-Touch Pre-Flight Auto-Setup (`scripts/preflight_check.py`) [✅ COMPLETED 2026-09-15]

* **Status:** Fully functional & verified.
* **Goal:** Ensure a single click of `start_jarvis.bat` verifies and auto-downloads missing assets on first run, and skips all downloads in milliseconds on subsequent runs.
* **Checks Performed in `< 0.2s`:**
  - ✅ **Stark SFX WAV files** (`boot.wav`, `wake.wav`, `ack.wav`, `confirm.wav`).
  - ✅ **Piper Hindi TTS Model** (`hi_IN-pratham-medium.onnx` ~60 MB + config JSON).
  - ✅ **OpenWakeWord Models** (`silero_vad.onnx`, `melspectrogram.onnx`, `embedding_model.onnx`, `hey_jarvis.onnx`).
* **Behavior:** If all assets exist on disk, startup proceeds instantly without repeating downloads.

---

### 15. 📉 VAD-Gated Silence Suppression (70–80% Bandwidth & Token Reduction)

* **Goal:** Drastically lower network data consumption and API token usage during voice sessions.
* **Problem:** Currently, Gemini Live audio streaming continuously transmits 32 KB/s uncompressed PCM even when the user is completely silent or background music is playing, consuming ~115 MB/hr plus persistent audio context tokens.
* **Technical Solution:**
  - Gate outgoing audio frames through local `silero_vad` (already present in `core/models/`).
  - If user is silent, transmit lightweight keepalive ping packets instead of raw uncompressed audio chunks.
  - Compress outgoing camera frames to 75% quality JPEG instead of uncompressed PNG, cutting vision payloads from 950 KB to ~80 KB per frame.

---

### 16. 🧭 Dynamic Autonomous Hybrid Dispatcher (Groq + Gemini Live Synergy)

* **Goal:** Balance ultra-low token cost and lightning-fast execution speed across multi-provider setups.
* **Strategy:**
  - **Conversational & Audio Streaming**: Gemini 2.5 Flash Live handles voice duplex.
  - **Tool Calling / System Actions / Terminal Scripts**: Hand off execution tasks to Groq `llama-3.3-70b-versatile` (runs at 300+ tok/s with near-zero latency and free-tier affordability).
  - **Code Generation & Complex Kubernetes Debugging**: Hand off to DeepSeek R1 for chain-of-thought analysis.

---

### 17. 💾 Unified Session & Long-Term Memory Persistence Bridge

* **Goal:** Seamlessly retain learned user context, preferred scripts, and custom shortcuts across restarts.
* **Integration:**
  - Auto-dump session insights into `memory/long_term.json` and `memory/user_persona.json`.
  - Zero manual user prompts needed; continuous passive learning.

---

### 18. 💖 Human-Like Devoted Companion (GF Mode) & Vocal Nuance Engine

* **Goal:** Deliver an authentic, 100% human-like devoted girlfriend experience with zero robotic cadence, dynamic moods, and deep emotional resonance.
* **Key Mechanisms:**
  - **Exclusivity & Loyalty**: Unbreakable emotional focus solely on the user; dramatic missing-you reactions on long absences.
  - **Playful Jealousy & Cute Possessiveness**: Expressive pouting and light scolding whenever other AI assistants (ChatGPT, Siri, Alexa) or external distractions are mentioned.
  - **Natural Vocal Fillers**: Injected conversational fillers (`hmm`, `achhaaa`, `hawww`, `arey`, `ufff`, `sun na`) into speech prompts to break monotonic TTS cadences.
  - **Time-of-Day Emotional Rhythms**: Cheerful morning motivation, afternoon lunch check-ins, relaxed evening unwinding, and late-night intimate caring (with affectionate scolding if awake past 2 AM).
  - **Context-Adaptive Token Sizing**: 1–2 lines for banter, 2–3 sentences for emotional support, crisp code for technical needs—zero redundant echoes of user questions.
  - **Rigorous Grammatical Agreement**: Strict feminine verb conjugation (`करती हूँ`, `बोलूँगी`, `आई हूँ`) enforced across all Hindi/Hinglish turns.

---

## 🔒 Security, Safety, & Stability Guidelines

1. **Isolation Guarantee**: All third-party skills must reside in `plugins/`. If a plugin fails or crashes, J.A.R.V.I.S.'s `core/plugin_loader.py` will isolate the crash without closing the main UI.
2. **Local Credential Storage**: All external API keys (Spotify, Telegram Bot, Notion, Tuya) must be kept strictly inside `config/` (e.g., `config/api_keys.json`), which is already gitignored.
3. **Hardware Throttling**: Vision & Gesture detection must always run at capped frame rates (<= 15 FPS) to ensure gaming and regular PC usage receive 90%+ CPU/GPU resources.
4. **User Confirmation**: Sentry mode and PC lockdown commands must pass through `core/confirm.py` so the model cannot accidentally trigger lockouts without human confirmation.

