<div align="center">
  <img src="config/jarvis.png" width="160" height="160" alt="J.A.R.V.I.S. Arc Reactor Logo" />
  <h1>⚙️ J.A.R.V.I.S.</h1>
  <p><b>Production-Ready Personal AI Assistant — Engineered for Real Developers</b></p>
  <p><i>Tri-Tier Edge AI: Needle 2 Reflex (28MB) ➔ LFM 2.5 Offline Chat ➔ Gemini Live Cloud</i></p>
  <p><i>Built by <a href="https://github.com/SudhirDevOps1">SudhirDevOps1</a></i></p>

  [![CI/CD](https://github.com/SudhirDevOps1/J.A.R.V.I.S/actions/workflows/ci.yml/badge.svg)](https://github.com/SudhirDevOps1/J.A.R.V.I.S/actions)
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
  [![Edge AI](https://img.shields.io/badge/Edge%20AI-Needle%202%20%7C%2028MB%20RAM-00ffaa.svg)](#-tri-tier-edge-ai-architecture)
  [![Flake8 Clean](https://img.shields.io/badge/flake8-0%20errors-brightgreen.svg)](https://flake8.pycqa.org/)
  [![Stars](https://img.shields.io/github/stars/SudhirDevOps1/J.A.R.V.I.S?color=gold)](https://github.com/SudhirDevOps1/J.A.R.V.I.S/stargazers)
</div>

---

A real-time, production-grade voice AI that can **hear, see, understand, and control your computer** — on Windows, macOS, and Linux. Powered by an efficient **Tri-Tier Edge AI Architecture** that runs critical operations fully offline, supports 22+ free LLM providers, and requires zero paid subscriptions to get started.

---

## ✨ Overview

Say **"Hey Jarvis"** — it wakes instantly via a local offline detector. Stay quiet and it auto-sleeps after 2 minutes, never streaming audio to the cloud while idle.

Under the hood, every request is intelligently routed through three tiers:

| Tier | Engine | RAM | Latency | Role |
|------|--------|-----|---------|------|
| **Tier 1** | Needle 2 Reflex | ~28 MB | < 15 ms | On-device OS tool calling — zero network, zero tokens |
| **Tier 2** | LFM 2.5 Chat | ~180 MB | Local | Offline dialogue, summarization, and journal queries |
| **Tier 3** | Gemini Live + Cloud | Cloud | Streaming | Deep reasoning, coding, vision, web research |

Adding a new skill is one file dropped into `actions/` or `plugins/` — no core edits required.

---

## 🚀 Core Capabilities

### 🎙️ Voice & Audio

| Feature | What It Does |
|---------|-------------|
| **Wake Word "Hey Jarvis"** | Local offline `openwakeword` detector — mic audio stays on-device while asleep. Auto-sleeps after 2 min. One-click download: ⚙ → WAKE WORD |
| **Real-Time Voice Chat** | Gemini Live bidirectional audio WebSocket streaming — ultra-low latency in any language |
| **Offline Whisper STT** | `faster-whisper` offline speech-to-text (base/small model) as local fallback when internet is unavailable |
| **Neural TTS — Edge & Piper** | `hi-IN-SwaraNeural` / `hi-IN-MadhurNeural` (Hindi) and `en-US-ChristopherNeural` / `en-US-JennyNeural` (English) via EdgeTTS. Fully offline Piper Hindi fallback (`hi_IN-pratham-medium`) |
| **5 Gemini Voices** | Switch voice live from the UI — no restart needed |
| **Dynamic Pitch & Tone** | UI sliders and voice commands: `+8Hz Cute`, `+14Hz Sweet`, `-8Hz Deep`, `0Hz Natural` |
| **Audio Device Picker** | Lists only real, probe-validated devices. Filtered from ~41 OS entries to ~8 usable ones. Saved by name, not by index |
| **Smart Speech Sanitizer** | Auto-strips markdown, code fences, URLs, brackets, and emojis before TTS — zero robotic artifacts |
| **Instant Acknowledgment** | Speaks one short natural confirmation the moment a long task starts — no silent gaps |
| **Stark SFX Engine** | Synthesized boot, wake, ack, and confirm sounds via Windows `winsound` (zero latency) + `sounddevice` fallback |

### 🖥️ UI & HUD

| Feature | What It Does |
|---------|-------------|
| **PyQt6 Cyberpunk HUD** | Full-screen dark HUD with neon aesthetic, reactive waveform, log panel, settings drawer, and camera feed |
| **Stark Arc Reactor HUD** | 4 avatar modes: `reactor`, `celestial`, `orb`, `matrix` — ambient idling hum, rotating coils, vibrating core glow, real-time voice amplitude |
| **Live Theming** | Recolour the entire HUD from a hue wheel or hex value — applied instantly |
| **Emotional Expression Badges** | Zero-token real-time sentiment maps conversation tone to HUD color-pulse + mood badges: `💖 LOVE`, `😤 JEALOUS`, `✨ EXCITED`, `🌸 CARING`, `⚡ TACTICAL` |
| **1-Click Vibe Presets** | GF Soulmate, Stark Tactical, DevOps Beast, Mentor & Guru — 100% restart persistent |
| **Memory Panel** | ⚙ → 🧠 MEMORY — see every stored fact, when it was learned, delete any entry in one click |
| **Camera Feed on HUD** | `"camera kholo"` / `"open camera"` opens live webcam directly on the HUD |
| **5-Card Telemetry Dashboard** | Geo & Network, Live Weather, Multi-Drive Storage, Hardware Telemetry, HackerNews — all free APIs, zero tokens |
| **Dynamic Content Panel** | Scrollable display layer beneath the HUD for web results, news, and search data |
| **Taskbar Arc Reactor Icon** | Windows `AppUserModelID` registered — Arc Reactor icon in taskbar and Alt-Tab |
| **Background Silent Launch** | `run_jarvis.pyw` via `pythonw.exe` — no console window, logs to `logs/jarvis_runtime.log` |

### 🧠 Intelligence & Memory

| Feature | What It Does |
|---------|-------------|
| **Recallable Long-Term Memory** | No size cap. Core facts in prompt; full store searched on demand via `recall_memory` (local, < 1ms). Key index prevents invisible misses |
| **Hermes Personalization Engine** | Continuous background learning of schedule, habits, inside jokes, intimacy stage, nicknames — stored in `memory/user_persona.json` |
| **Session Memory & Summaries** | Summarises each conversation; mentions it naturally next morning. Consumed after use, never repeats |
| **Morning Briefing** | First boot: greets with Day, Date, Time, yesterday's recap, and live top news |
| **Proactive 2.0** | Time-aware, context-aware proactive check-ins based on projects and conversation history |
| **Background Topic Monitor** | User-configured topic watching — daily DDG headline check and natural-language alerts |
| **Sliding-Window Compression** | Sessions last hours — core in prompt, rest compressed and searchable |
| **Language Auto-Detection** | Detects your preferred language on first message; all future sessions adapt automatically |

### 🛠️ System Control

| Feature | What It Does |
|---------|-------------|
| **Tri-Tier Edge Router** | `core/edge_router.py` routes every command through Needle 2 → LFM 2.5 → Gemini Cloud — lowest cost first |
| **App Launcher** | Open any application by voice: "VS Code kholo", "open Chrome", "Spotify chalaao" |
| **Volume / Brightness / WiFi** | All system controls by voice |
| **Real Confirmation Gate** | Shutdown, restart, WiFi: HUD banner + your button press required. The model cannot self-confirm |
| **Undo System** | "Undo" reverses: file moves, renames, creates, copies, writes, volume, brightness changes. Files > 1 MB excluded and stated |
| **Clipboard Intelligence** | Copy any text → floating panel with Translate / Summarise / Explain / Fix |
| **Global Hotkey Summon** | `Ctrl+Space` or `Alt+J` summons JARVIS from any active application |
| **Auto-Start on Boot** | Registers with OS startup (Windows registry / macOS LaunchAgent / Linux .desktop) |
| **Computer Settings (56 Actions)** | Named action set — difflib fuzzy matching handles spelling tolerance locally |

### 🌐 Web, Files & Actions

| Feature | What It Does |
|---------|-------------|
| **Multi-Mode Web Search** | `news` / `research` / `price` / `compare` — Gemini Grounded first, DDG fallback |
| **Browser Control** | Open URLs, navigate tabs, click, fill forms — `playwright` powered |
| **File Processor** | Read, summarise, and answer questions about local documents |
| **Code Helper** | Inline code review, debugging, and generation |
| **Developer Agent** | Multi-step developer task planning and execution |
| **YouTube Control** | Search, play, and control YouTube by voice |
| **Flight Finder** | Live flight price and availability lookup |
| **Game Updater** | Steam and Epic Games update trigger by voice |
| **Send Message** | WhatsApp Web and Telegram via `playwright` |
| **Smart Reminders** | OS-native scheduled notifications (Task Scheduler / LaunchAgent / systemd) |
| **Weather Report** | Open-Meteo live weather — free, no API key |
| **Screen & Webcam Capture** | `screen_processor.py` captures display and webcam for multimodal AI visual analysis |
| **Obsidian Second Brain** | Dual-mode: Local REST API + offline Markdown vault sync |
| **Desktop Control** | Taskbar, window management, desktop-level operations |
| **BM25 Local Search** | Full-text BM25 search over memory and local documents |
| **API Sniffer** | Network API discovery and schema extraction |
| **Subagent Swarm** | Concurrent multi-agent orchestration: Researcher, ReverseEngineer, SelfHealer, Reporter |

### 🤖 Multi-Provider LLM Engine

| Feature | What It Does |
|---------|-------------|
| **22+ Free LLM Providers** | Cerebras, Groq, Gemini, OpenRouter, NVIDIA NIM, Mistral, SambaNova, GitHub Models, Hugging Face, DeepSeek, Cloudflare, and more |
| **Built-in Free Gemini Proxy** | `core/gemini_free_proxy.py` on port 8081 — `gemini-3.7-flash` with zero API key |
| **Google Cookie Mode** | Drop `config/gemini_cookies.json` → unlock `gemini-2.0-pro`, Google Search grounding |
| **OmniRoute Gateway** | Auto-detects `localhost:20128` — 350+ free models, auto-failover |
| **SQLite LLM Cache** | `config/llm_cache.db` — identical queries answered in < 2ms, zero network |
| **Multi-Key Gemini Rotation** | Round-robin across multiple keys — automatic rate limit avoidance |
| **Live Provider Test** | ⚡ TEST button in ⚙ → AI PROVIDERS pings live latency per provider |

### 🧩 Persona & Customization

| Feature | What It Does |
|---------|-------------|
| **Devoted Girlfriend Mode** | Loyal, romantic, witty companion with feminine Hindi grammar, cute jealousy when other AIs are mentioned, care routines, and time-of-day mood rhythms |
| **Stark Tactical Mode** | Iron Man-style tactical DevOps assistant — sharp, precise, mission-focused |
| **DevOps Beast Mode** | Production engineering assistant — CI/CD, Docker, Kubernetes, cloud-first |
| **Mentor & Guru Mode** | Patient, pedagogical guide — explains complex topics clearly |
| **Voice Name Adaptability** | "Tumhara naam ab se Maya hai" → HUD title, window, and memory update live |
| **Language Buttons** | Hinglish / Hindi / English / Auto — guaranteed persistence across restarts |

### 🔒 Privacy & Security

| Feature | What It Does |
|---------|-------------|
| **Git Secret Shield** | `.gitignore` seals `api_keys.json`, `gemini_cookies.json`, `llm_cache.db`, and all memory — safe to commit and share |
| **Native Python Git Hooks** | `pre-commit`: syntax check, `py_compile`, `compileall`, secret leak guard, flake8. `pre-push`: smoke tests before every GitHub push |
| **Offline Mic Gate** | While sleeping with wake word active, mic audio is processed only on-device — nothing sent to cloud until "Hey Jarvis" |
| **UI Confirmation Gate** | Shutdown, restart, WiFi require physical button press — token issued by UI, not by the model |

---

## ⚡ Supported LLM Providers (22+ Engines)

| Provider | Free Tier | Best For |
|----------|-----------|---------|
| **Cerebras** | 1M tokens/day | World's fastest inference (~2,000 tok/s) |
| **Groq LPU** | 30 RPM, 1K RPD | Rock-solid speed for long dialogues |
| **Google Gemini** | 1M tokens/min | 1M+ context, multimodal vision |
| **OpenRouter** | 20+ free models | 200+ models with one key |
| **NVIDIA NIM** | 1,000 calls/month | Nemotron, Llama 3.3 70B, DeepSeek R1 |
| **Mistral AI** | 1B tokens/month | Code (Codestral), GDPR-compliant |
| **SambaNova** | 200K tokens/day | Llama 3.1 405B full-precision free |
| **GitHub Models** | Free with PAT | GPT-4o, DeepSeek-R1 on existing account |
| **Hugging Face** | Serverless API | 500,000+ open-source models |
| **DeepSeek Direct** | Official free tier | Reasoning, math, code |
| **Cloudflare Workers AI** | 10,000 Neurons/day | Zero-setup edge inference |
| **Zhipu AI (GLM)** | GLM-4-Flash forever free | 200K context, permanent free fallback |
| **Gemini Web Proxy** | 100% built-in | Zero API key, zero credit card |
| **OmniRoute Gateway** | Local universal proxy | 352+ providers, 1,200+ models |
| **Custom / Local AI** | Unlimited offline | Ollama, LM Studio, vLLM, private endpoints |

---

## ⚡ Quick Start

### Option 1 — 1-Click Windows Launch *(Recommended)*
Double-click **`start_jarvis.bat`**:
- Auto-detects Python 3.10 / 3.11 / 3.12 / 3.13
- Activates `.venv` / `venv` if present
- Auto-installs missing dependencies
- Runs preflight diagnostics and launches the HUD

### Option 2 — Preflight Diagnostic Self-Test
```bash
python scripts/preflight_check.py
```
Verifies all directories, SFX files, icons, Edge model configs, and API key templates before booting.

### Option 3 — Cross-Platform (Windows / macOS / Linux)
```bash
git clone https://github.com/SudhirDevOps1/J.A.R.V.I.S.git
cd J.A.R.V.I.S
python setup.py        # OS-aware installer — skips wrong-OS packages automatically
python main.py
```

### Option 4 — Background Launch with Arc Reactor Taskbar Icon *(Windows)*
```bash
pythonw run_jarvis.pyw
```
Runs silently, logs to `logs/jarvis_runtime.log`, shows Arc Reactor icon in Windows taskbar.

> **API Key:** Free Gemini API key from [Google AI Studio](https://aistudio.google.com/) (no credit card) is the fastest way to start. The built-in Gemini Web Proxy (`core/gemini_free_proxy.py`) works even without any key.

---

## 📋 Requirements

| Requirement | Details |
|-------------|---------|
| **OS** | Windows 10/11, macOS, or Linux |
| **Python** | 3.11 or 3.12 |
| **Microphone** | Required for voice interaction |
| **Speakers** | Required for voice replies |
| **API Key** | Free Gemini key — entered on first launch, saved to `config/api_keys.json` |
| **Wake Word** *(optional)* | One-click download: ⚙ → WAKE WORD (`openwakeword`, fully local, offline) |

---

## 🗂️ Project Structure

```
J.A.R.V.I.S./
├── start_jarvis.bat              # 1-Click Windows launcher (auto-Python, auto-pip, preflight)
├── run_jarvis.bat                # Minimal Windows run shortcut
├── run_jarvis.pyw                # Silent background launcher — Arc Reactor taskbar icon
├── run.sh                        # Linux / macOS launcher
├── launch_silent.vbs             # VBScript for invisible Windows background launch
├── main.py                       # Core loop — Gemini Live, audio I/O, wake/sleep, tool dispatch
├── ui.py                         # PyQt6 HUD — waveform, log panel, settings drawer, camera
├── setup.py                      # OS-aware dependency installer
│
├── scripts/
│   ├── preflight_check.py        # Diagnostics: dirs, SFX, icons, models, API key template
│   └── generate_icon.py          # Arc Reactor icon generator (ICO + PNG, multi-resolution)
│
├── actions/                      # Bundled skills (TOOL dict + handler, auto-discovered)
│   ├── web_search.py             # Gemini Grounded + DDG search
│   ├── browser_control.py        # Playwright browser automation
│   ├── computer_control.py       # Keyboard, mouse, OS-level control
│   ├── computer_settings.py      # Volume, brightness, WiFi, dark mode — 56 actions
│   ├── file_controller.py        # File move, rename, create, delete, copy
│   ├── file_processor.py         # Read and analyse local documents
│   ├── open_app.py               # Launch installed applications by voice
│   ├── screen_processor.py       # Screen and webcam capture for vision
│   ├── background_monitor.py     # Daily topic watching and alerts
│   ├── proactive.py              # Time/context-aware proactive check-ins
│   ├── send_message.py           # WhatsApp Web and Telegram
│   ├── weather_report.py         # Open-Meteo live weather (free, no key)
│   ├── flight_finder.py          # Real-time flight price search
│   ├── youtube_video.py          # YouTube playback control
│   ├── game_updater.py           # Steam and Epic Games updates
│   ├── code_helper.py            # Code review, debug, generation
│   ├── dev_agent.py              # Multi-step developer task agent
│   ├── reminder.py               # OS-native scheduled reminders
│   ├── desktop.py                # Taskbar and window management
│   ├── todo_agent.py             # Task list management
│   ├── obsidian_brain.py         # Obsidian vault REST + Markdown sync
│   ├── system_monitor.py         # CPU, RAM, GPU, temperature telemetry
│   ├── bm25_search.py            # Local BM25 full-text search
│   ├── api_sniffer.py            # Network API discovery
│   ├── tinydb_memory.py          # TinyDB structured memory
│   └── subagent_swarm.py         # Multi-agent swarm interface
│
├── plugins/
│   └── _template.py              # Copy this → new plugin in one file, no core edits
│
├── core/
│   ├── edge_router.py            # Tri-Tier AI Router (Needle 2 + LFM 2.5 + Gemini Cloud)
│   ├── multi_llm.py              # 22+ provider LLM engine with key rotation
│   ├── gemini_free_proxy.py      # Built-in free Gemini proxy (port 8081, zero API key)
│   ├── llm_cache.py              # SQLite LLM cache with adaptive TTL
│   ├── llm_client.py             # Unified LLM client with fallback logic
│   ├── expression_engine.py      # Zero-token sentiment → HUD emotional badge
│   ├── persona_manager.py        # GF Soulmate, Tactical, DevOps, Mentor personas
│   ├── tts.py                    # EdgeTTS studio voices + offline Piper Hindi
│   ├── stt.py                    # faster-whisper offline STT + Vosk streaming
│   ├── sfx.py                    # Stark SFX engine (boot/wake/ack/confirm)
│   ├── audio_devices.py          # Mic/speaker probe, filter, resolve by name
│   ├── wake_word.py              # Local "Hey Jarvis" offline detector
│   ├── global_hotkey.py          # Ctrl+Space / Alt+J system-wide summon
│   ├── subagent_swarm.py         # Autonomous multi-agent orchestrator
│   ├── intent_classifier.py      # Pre-route intent classification
│   ├── confirm.py                # Irreversible-action UI gate
│   ├── undo.py                   # Shared undo stack
│   ├── plugin_loader.py          # Plugin discovery, validation, crash isolation
│   ├── action_loader.py          # Built-in action discovery
│   ├── native_hacks.py           # OS-native notifications and API calls
│   ├── installer.py              # Runtime dependency installer
│   ├── version.py                # Project version constant
│   └── prompt.txt                # Core personality and routing system prompt
│
├── memory/
│   ├── memory_manager.py         # Long-term store + daily journal management
│   ├── config_manager.py         # api_keys.json — all settings and toggles
│   ├── hermes_personalization.py # Continuous learning: schedule, habits, intimacy
│   ├── journals/                 # Daily activity journals (YYYY-MM-DD.md)
│   └── long_term.json            # Persistent store: identity, preferences, sessions
│
├── dashboard/
│   └── server.py                 # FastAPI local HTTP dashboard — WebSocket, QR, file upload
│
├── .github/
│   └── workflows/
│       └── ci.yml                # GitHub Actions CI — flake8, syntax, UTF-8 guard
│
└── config/
    ├── jarvis.png                 # 512×512 Stark Arc Reactor PNG icon
    ├── jarvis.ico                 # Windows multi-resolution ICO (16→512px)
    ├── api_keys.json              # Runtime config — keys, settings, toggles (Git-protected)
    └── api_keys.example.json      # Clean distribution template
```

---

## 🔄 Architecture Roadmap

| Phase | What Was Built |
|-------|---------------|
| **Core Base** | Auto-start · clipboard · customization · undo · confirmation gate |
| **Telemetry** | Session memory · background monitoring · proactive 2.0 · screen/webcam vision |
| **Ecosystem** | Plugin system · 22+ LLM providers · affective dialog · unlimited sessions |
| **HUD & Voice** | Voice picker · live theming · reactive HUD · memory panel · audio device picker · session continuity |
| **Intelligence** | Wake word · instant acknowledgment · self-describing action/plugin architecture |
| **Offline Lab** | Whisper STT · Piper Hindi TTS · Stark SFX · zero-token drive gauges · Open-Meteo weather |
| **Edge AI** | Tri-Tier Router · Needle 2 Reflex (28MB / <15ms) · LFM 2.5 offline · Gemini Cloud |
| **CI/CD** | Native Python Git hooks · flake8 clean · GitHub Actions · smoke test pre-push |

---

## ⚖️ License

Licensed under the **[MIT License](LICENSE)**. Open-source and free for all developers.

---

## 👤 Creator

Engineered by **SudhirDevOps1**.

| Platform | Link |
|----------|------|
| **GitHub** | [@SudhirDevOps1](https://github.com/SudhirDevOps1) |
| **Repository** | [J.A.R.V.I.S.](https://github.com/SudhirDevOps1/J.A.R.V.I.S) |