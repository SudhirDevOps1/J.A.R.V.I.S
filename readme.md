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

> 📖 **Full Command & Control Guide:** Read the [Complete User Control & Feature Manual (USER_GUIDE.md)](USER_GUIDE.md) for detailed Hindi, Hinglish, and English voice/text commands across all categories.

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
| **Neural TTS — Edge & Gemini Live** | `hi-IN-SwaraNeural` / `hi-IN-MadhurNeural` (Hindi) and `en-US-ChristopherNeural` / `en-US-JennyNeural` (English) via EdgeTTS, plus native Gemini Live realtime voice |
| **5 Gemini Voices** | Switch voice live from the UI — no restart needed |
| **Dynamic Pitch & Tone** | UI sliders and voice commands: `+8Hz Cute`, `+14Hz Sweet`, `-8Hz Deep`, `0Hz Natural` |
| **Audio Device Picker** | Lists only real, probe-validated devices. Filtered from ~41 OS entries to ~8 usable ones. Saved by name, not by index |
| **Smart Speech Sanitizer** | Auto-strips markdown, code fences, URLs, brackets, and emojis before TTS — zero robotic artifacts |
| **Instant Acknowledgment** | Speaks one short natural confirmation the moment a long task starts — no silent gaps |
| **Stark SFX Engine** | 8 synthesized sounds — boot, wake, ack, confirm, error, success, typing, thinking — via Windows `winsound` (zero latency) + `sounddevice` fallback |

### 🔇 Headless Smart Services & Advanced Transit (Zero Browser Overhead)

| Feature | What It Does |
|---------|-------------|
| **Multi-Modal Transit & Maps Navigation** | `actions/travel_transit.py` computes real-world road distance and travel time via OpenStreetMap Nominatim and OSRM routing. Provides comprehensive multi-modal breakdown: **Trains** (Vande Bharat, Rajdhani, Superfast Express schedules, IRCTC link), **Flights**, **Buses** (Volvo AC Sleeper, State Roadways), and **Turn-by-turn Maps** without fake data or browser interruption. |
| **Universal Drive Music Indexer** | `actions/youtube_video.py` indexes all audio tracks across all PC drives (`C:`, `D:`, `E:`) into `config/music_library.json`. Loads in <1ms with fuzzy token matching. Supports `"songs rescan karo"` to update library. |
| **Headless Audio vs Video Playback** | Voice command aware: `"song play karo"` plays local tracks offline or streams minimized in the background. Saying `"youtube par video dikhao"` / `"apna college ka video lagao"` launches YouTube directly in the browser. |
| **Synchronized Assistant Persona Modes** | `core/persona_manager.py` dynamically aligns tone, greetings, and pedagogy across 4 synchronized modes: **Teacher & Guru** (pedagogical mentor), **DevOps & Hacker** (terminal expert), **Companion & GF** (romantic partner), and **J.A.R.V.I.S** (Stark tactical AI). Live session automatically reconnects upon mode switch. |
| **Headless Open-Meteo Weather** | Real-time global atmospheric telemetry (0 tokens, 0 keys) via Open-Meteo Geocoding. Renders rich Cyber-HUD weather card and speaks temperature/humidity/wind — **zero browser popups**. |
| **Headless eCommerce Comparison** | `actions/ecommerce_search.py` researches live prices, ratings, and deals across **Amazon India & Flipkart**. Displays side-by-side comparison tables in the HUD and speaks price differences. |
| **Headless Flight & Travel Schedules** | `actions/flight_finder.py` extracts scheduled flight timings, duration, and prices directly to the HUD without popping open browser tabs. |

### 🖥️ UI & HUD

| Feature | What It Does |
|---------|-------------|
| **Stark Arc Reactor HUD** | 4 avatar modes: `reactor`, `celestial`, `orb`, `matrix` — ambient idling hum, rotating coils, vibrating core glow, real-time voice amplitude |
| **PiP Always-On-Top Mini Companion** | Draggable frameless companion with dedicated header drag handle (`✥`), mini countdown badge (`⏳ MM:SS`), ⚡ EDGE reflex badge, live chat history, screen troubleshoot eye, and expandable panel (`pip_mode.py`) |
| **Live Countdown Watch & Telemetry** | Real-time countdown badge (`⏳ MM:SS`) in HUD header watch + dedicated `◈ TIMERS & TASKS` card with dual-color cyber progress bar and completion voice alert (`timer_manager.py`) |
| **Cyber-HUD Content Display** | Dynamic split panel below the Arc Reactor supporting rich HTML/Markdown telemetry cards, price comparison tables, and weather cards |
| **Live Theming & Vibe Presets** | Instant hue recoloring + 4 presets: GF Soulmate, Stark Tactical, DevOps Beast, Mentor & Guru |
| **Emotional Expression Badges** | Zero-token sentiment maps tone to HUD color pulses: `💖 LOVE`, `😤 JEALOUS`, `✨ EXCITED`, `🌸 CARING`, `⚡ TACTICAL` |
| **Native Windows Camera App** | `"camera kholo"` instantly launches Windows Camera app (`microsoft.windows.camera:`) with 0 latency, while HUD stream captures live vision |
| **Real Vector Icons** | 34 hand-drawn stroke icons on every button (`ui_icons.py`, zero deps) — no more empty emoji boxes on any OS |
| **Toast Banners & CTA Chips** | Self-dismissing toast notifications + Undo, Remind-me, and Copy action chips |

### 🧠 Intelligence, Self-Improvement & Memory

| Feature | What It Does |
|---------|-------------|
| **Autonomous Mistake-Correction** | Detects user corrections ("ye galat hai", "nahi aisa nahi"), logs mistakes into `memory/self_correction_log.json`, and injects learned lessons into future prompts |
| **Recallable Long-Term Memory** | Unlimited persistent memory in `memory/long_term.json`. Core facts in prompt; deep store searched via `recall_memory` (<1ms) |
| **Hermes Personalization Engine** | Continuous background learning of user habits, schedule, nicknames, and project workflows |
| **Sliding-Window Compression** | Hours-long continuous sessions — active context kept crisp while older history compresses automatically |
| **Multi-Language Detection** | Seamlessly understands and responds in English, Hindi, and natural everyday Hinglish |

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
| **App Index 300+** | Start Menu + UWP + winget + Steam scan (~304 apps), 68 category fallbacks, Hindi nicknames ("ganana wala app"), `open_with` file support |
| **App Routines/Workspaces** | `config/routines.json` — "dev routine chalao" opens multi-app setups; voice-create supported |
| **Window Tools** | FancyZones-style layouts, Window Walker bring-to-front, always-on-top pin, peek preview, bulk rename (undoable), batch image resize, keep-awake |
| **Run Any Command** | `run_command` — allowlist instant, unknown asks HUD confirmation, destructive refused, audit-logged |
| **Macro Record/Replay** | `pynput` keyboard/mouse capture, ESC-stop, speed control, confirm-gated replay |
| **Text Expander** | `;mail`/`;addr` hotstrings from `config/expansions.json` |
| **Scheduler 2.0** | Cron/interval/once + file-arrival + battery-low + app-open triggers (APScheduler + watchdog) |
| **Conditional Workflows** | If-this-then-that JSON rules (e.g. battery < 20 → brightness 30) |
| **Profiles** | Work/Gaming/Study bundles — persona + voice + routine in one command |
| **Agent Mode** | Multi-step goal conductor with persisted plans + progress |

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
| **Deep Research** | Multi-query fan-out with merged sources + citations |
| **Page Capture** | Full-page website screenshot/PDF to `~/Downloads/JARVIS Captures` |
| **Screen OCR + Clipboard History** | OCR any screen region; last-20 clipboard search |
| **Windows UIAutomation (UIA) Controller** | Semantic desktop control: click buttons, fill text boxes, and select menus by accessible name without pixel guessing (`actions/uia_controller.py`) |
| **100% Private Local Screen Memory & Timeline Recall** | On-device SQLite FTS5 timeline memory of active windows, apps, and tasks with automatic privacy blacklisting (`actions/screen_timeline.py`) |
| **Safe, Opt-in Local LLM Bridge** | Zero-freeze Ollama bridge (DeepSeek-R1 / Qwen2.5) with 1.5s fast-fail timeout, keeping Gemini Live & Cloud as primary (`core/local_llm_bridge.py` & `actions/local_llm_toggle.py`) |
| **Autonomous DevOps Terminal Sentinel** | Non-blocking background watcher for builds/tests (`pytest`, `npm`, `docker`), auto-diagnosing root causes with HUD and voice alerts (`actions/devops_sentinel.py`) |
| **Plugin Manager** | Lists all 10 plugins by voice — "plugin dikhao" |

### 🧩 Plugins (10 Built-In)

| Plugin | What It Does | Needs |
|---|---|---|
| **spotify_control** | Play/pause/next/queue/like | Spotify (OAuth for full control) |
| **pomodoro_timer** | Focus timer with success chime | Nothing |
| **stock_price** | Live NSE/BSE quotes (2-min cache) | Internet |
| **notion_sync** | Notion search/create | `NOTION_TOKEN` |
| **gmail_tool** | Unread inbox by voice | `~/.credentials/gmail_token.json` |
| **calendar_tool** | Today's events for briefings | `~/.credentials/calendar_token.json` |
| **drive_tool** | Drive file search | `~/.credentials/drive_token.json` |
| **github_tool** | List/create issues | `GITHUB_TOKEN` |
| **slack_tool** | Send channel messages | `SLACK_BOT_TOKEN` |
| **smart_home** | Tuya lights/plugs/scenes | `config/smart_home.json` device id/key |

> Without tokens every plugin answers with Hindi setup guidance — never crashes.

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
| **FIFO Confirm Queue** | Stacked confirmations queue (max 5) instead of overwriting — expired ones logged and skipped |
| **Audit Log** | `memory/audit.jsonl` records every sensitive action: what ran, when, confirmed or cancelled |
| **Atomic Config Writes** | Backup + file-lock + tmp-replace on every settings save — crash can never corrupt `api_keys.json` |
| **Upload Guard** | Dashboard blocks executables (`.exe/.bat/.ps1/...`), 500MB cap, traversal-safe names |

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

## 🗣️ Voice Command Cheat-Sheet

| Category | Example Spoken Command (English & Hinglish) | What Happens (Headless / Reflex) |
|----------|---------------------------------------------|----------------------------------|
| **Weather** | *"Aaj Mumbai ka mausam kaisa hai"*, *"Weather in Delhi today"* | Open-Meteo live atmospheric telemetry card displayed on HUD; speaks temp/humidity/wind without opening browser |
| **Local Music** | *"Sanam Teri Kasam gaana chalao"*, *"Play Believer"* | Scans `~/Music` & `~/Downloads` for audio files; plays offline via Pygame Mixer in the background |
| **Audio Controls** | *"Music pause karo"*, *"Song resume karo"*, *"Gaana band karo"* | Pauses, unpauses, or stops background audio playback cleanly |
| **eCommerce Deals**| *"Flipkart par iPhone 15 ka price check karo"*, *"Amazon rate boAt rockerz"* | Researches prices, ratings, and discounts across Amazon India and Flipkart; outputs side-by-side comparison table to HUD |
| **Flights & Travel**| *"Delhi se Mumbai flight check karo"*, *"Flight to Bangalore tomorrow"* | Formats airline timings, durations, and fares into HUD flight card without browser popup |
| **Apps & Windows** | *"VS Code kholo"*, *"Camera kholo"*, *"Chrome band karo"* | Native fast app launch (<15ms Needle 2 reflex); opens Windows Camera app or requested target |
| **Screen Vision** | *"Screen dekho"*, *"What is on my screen"*, *"Inspect code error"* | Captures display frame and runs multimodal visual inspection |
| **PiP Companion** | *"PiP window kholo"*, *"Mini mode chalao"* | Launches always-on-top draggable cyber companion over active games or IDEs |
| **Self-Correction**| *"Ye galat hai, sahi tareeqa yeh hai..."* | Automatically updates `memory/self_correction_log.json` to prevent making the same mistake again |

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
│   ├── tts.py                    # EdgeTTS studio voices + Gemini Live realtime
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
| **Offline Lab** | Whisper STT · Stark SFX · zero-token drive gauges · Open-Meteo weather |
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