# ⚙️ J.A.R.V.I.S. (SudhirDevOps1 AI)
### The Ultimate Cross-Platform Personal AI Assistant — By SudhirDevOps1

[![GitHub Release](https://img.shields.io/github/v/release/SudhirDevOps1/J.A.R.V.I.S?color=00ffff&label=release)](https://github.com/SudhirDevOps1/J.A.R.V.I.S/releases)
[![CI/CD](https://github.com/SudhirDevOps1/J.A.R.V.I.S/actions/workflows/ci.yml/badge.svg)](https://github.com/SudhirDevOps1/J.A.R.V.I.S/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)

A real-time voice AI that can hear, see, understand, and control your computer — on any OS. Supports Windows, macOS, and Linux. Built on the Gemini Live API for native audio streaming, delivering zero subscriptions and total digital autonomy.

---

## ✨ Overview

**J.A.R.V.I.S. is the ultimate hands-free & scalable personal AI assistant.** Say **"Hey Jarvis"** and it wakes; stay quiet and it slips back to sleep on its own — while asleep, your microphone never leaves the machine, so an off-hand *"I'll be right there"* to someone in the room no longer sets it off. Under the hood it now runs on the faster **Gemini 2.5/3.1 Flash Live** engine with multi-brain fallback (Groq, DeepSeek, Ollama), and the moment you ask for something that takes a beat — analysing a file, searching the web — it answers instantly *("On it — going through that now…")* so you never wonder whether it heard you.

It's also built to grow: every skill — bundled or drop-in — now **describes itself in its own file**, so adding a tool is a one-file operation and the core stays lean.

It's not just an assistant — it's an extension of your digital life.

---

## 🚀 Capabilities

### Core Features
| Feature | Description |
|---|---|
| 🎙️ Wake Word | Local **"Hey Jarvis"** detection — sleeps until called, auto-sleeps after 2 min of silence, and never streams audio while asleep. Opt-in, one-click download, toggle & manual sleep/wake from the UI |
| ⚡ Instant Acknowledgment | Speaks a short, context-aware reply in **your language** the instant a longer task starts — no more silent waiting |
| 🚀 Faster Live Engine | Runs on **Gemini 3.1 Flash Live** — roughly 2× faster time-to-first-word than the previous model |
| 🧩 Self-Describing Skills | Actions and plugins share one shape (`TOOL` / `PLUGIN` dict + `run()`), auto-discovered at launch — adding or moving a skill is a single file, no core edits |
| 🧠 Recallable Memory | No size limit and nothing silently forgotten — the prompt carries what fits, the rest is looked up on demand from a local search |
| 👁️ Memory Panel | See every fact JARVIS has stored about you, when it learned it, and delete any of it in one click |
| ↩️ Undo | Take back what the assistant did — files it moved, renamed, created or wrote, and settings it changed |
| ⚠️ Real Confirmation | Shutdown, restart and WiFi wait for a button **you** press — the model cannot confirm its own irreversible actions |
| 🎧 Audio Device Picker | Choose the microphone and speakers by name, filtered to the short list your OS shows — and measured, so every entry actually works |
| 🔗 Session Continuity | A dropped connection, a voice change or a device change no longer wipes the conversation |
| 🧩 Plugin System | Drop a single `.py` file into `plugins/` — JARVIS learns a new skill on next launch |
| 🎙️ Real-time Voice | Ultra-low latency conversation in any language via Gemini Live API |
| 🎨 Live Theming | Recolour the entire HUD from a hue wheel or hex — applied instantly across every panel |
| 🎭 Emotional Expressions | Real-time visual mood badge and HUD color-pulse reactions (`LOVE`, `JEALOUS`, `EXCITED`, `CARING`, `TACTICAL`) with zero tokens |
| ✨ 1-Click Vibe Presets | 1-click all-in-one setup (GF Soulmate, Stark Tactical, DevOps Beast, Mentor & Guru) with 100% restart persistence |
| 🚀 1-Click Auto-Setup | Self-healing `.bat` launcher — first-time automatic Python check, pip dependency install, preflight asset verification, and crash protection |
| 🖥️ Desktop App & Taskbar | Background `run_jarvis.pyw` launcher with registered Windows `AppUserModelID`, custom Arc Reactor taskbar icon, and runtime logging |
| 〰️ Reactive HUD & Arc Reactor | 4 distinct avatar modes (`reactor`, `celestial`, `orb`, `matrix`) featuring authentic continuous ambient idling hum, rotating copper coils, vibrating core glow, and real-time voice reactivity |
| 🔊 Stark SFX Engine | Zero-latency boot and UI sound effects (`boot`, `wake`, `confirm`, `ack`) backed by Windows native `winsound` and `sounddevice` |
| 🎙️ Voice Picker | Choose from 5 native Gemini voices and switch live from the UI — no restart |
| ♾️ Unlimited Sessions | Sliding-window context compression — one conversation can last for hours |
| 🖥️ System Control | Launch apps, adjust volume/brightness, WiFi, shortcuts, power — all by voice |
| 🧩 Autonomous Tasks | High-level planning for complex multi-step goals via agent mode |
| 👁️ Visual Awareness | Real-time screen capture and webcam vision piped into your main Gemini session |
| 🧠 Persistent Memory | Deeply remembers projects, preferences, and personal context across sessions |
| ⌨️ Hybrid Input | Seamlessly switch between keyboard typing and voice commands |
| 🌅 Morning Briefing | On first boot: greets you, reads the time, recaps yesterday, and fetches live news |
| 🔔 Proactive 2.0 | Time-aware, context-aware check-ins — knows the time of day, your projects, and what you've been discussing |
| 🗓️ Session Memory | Summarises each conversation and mentions it naturally next morning — consumed after use, never repeats |
| 👁️‍🗨️ Background Monitoring | User-configured topic watching — checks for new headlines once a day and alerts naturally |
| 📊 Hardware Monitoring | Continuous CPU, RAM, GPU and temperature telemetry with localized voice alerts |
| 🌐 Telemetry & APIs Dashboard | 5-card cyberpunk dashboard: Geo-Location & Network, Live Weather (Open-Meteo), Multi-Drive Storage, Hardware Telemetry, HackerNews Feed — all free APIs, zero tokens, scrollable UI |
| 🌤️ Weather Report | Live weather data for your city, personalized from memory |
| 🗺️ Dynamic Content Panel | Scrollable display layer beneath the HUD that renders web results, news, and search data |
| 🔍 Multi-Mode Web Search | `news` / `research` / `price` / `compare` / `search` — Gemini Grounded first, DDG fallback |
| ⏰ Smart Reminders | OS-native scheduled notifications (Windows Task Scheduler / macOS LaunchAgent / Linux systemd) |
| ✈️ Flight Finder | Live flight price and availability lookup |
| 🎮 Game Updater | Checks and triggers game updates on Steam and Epic Games on demand |
| 📂 File Processor | Read, summarize, and answer questions about local files |
| 💻 Code Helper | Inline code review, debugging, and generation |
| 🌐 Browser Control | Open URLs, navigate tabs, and interact with the browser by voice |
| 📨 Send Message | Compose and send messages through WhatsApp, Telegram, and more |
| 🎬 YouTube Control | Search, play, and control YouTube playback by voice |
| 🖱️ Desktop Control | Taskbar, window management, and desktop-level operations |
| 🧑‍💻 Silent Language Memory | Detects spoken language on first use — all future sessions adapt automatically |
| 📱 Remote Dashboard | Control the assistant from your phone via QR code pairing |
| ⚡ Auto-Start on Boot | Registers with the OS startup system (registry / LaunchAgent / .desktop) |
| 📋 Clipboard Intelligence | Copy any text → floating panel with Translate / Summarise / Explain / Fix |
| 🪪 Assistant Customization | Change the assistant name, your name, voice, and colour from the UI — takes effect immediately |
| 💖 Devoted Girlfriend Mode | 100% human girlfriend persona: exclusively loyal, romantic, playful banter, cute jealousy & possessiveness ("jalnous ho", anti-ChatGPT/Alexa), celebration mode, natural vocal fillers ("hmm", "achhaaa", "hawww", "sun na"), time-of-day mood rhythms, care routines, and strict feminine Hindi verb grammar |
| 🌅 Calendar & Clock Greeting | Announces full Day, Date, Month, Year, and Time on first boot with natural human cadence, time-of-day warmth, day-of-week context, and zero robotic monotone |
| 🏷️ Voice Name Adaptability | Renaming via voice (*"Tumhara naam ab se Maya hai"*) instantly updates HUD, window title, and memory live without restarting |
| 🔮 Obsidian Second Brain | Dual-mode note sync with Obsidian Local REST API + offline Markdown vault integration |
| ⚡ Smart Token Efficiency | Crisp, high-bandwidth responses (1–3 natural sentences for dialogue) that preserve context without wasting tokens |
| 🎙️ Neural Edge-TTS | Studio-grade, natural voices for Hindi (Madhur, Swara) and English (Chris, Jenny) with offline Piper fallback |
| 🎚️ Dynamic Pitch & Tone | Customizable pitch presets (`+8Hz Cute GF`, `+14Hz Sweet`, `-8Hz Deep`, `0Hz Default`) or custom Hz/rate via UI or voice command |
| 🧠 Hermes Personalization | Continuous background learning of schedule, habits, inside jokes, and intimacy stages stored in `user_persona.json` and mirrored dynamically |
| 🌐 Language Locking | Dedicated UI buttons for Hinglish, Hindi, English, and Auto with guaranteed persistence across restarts |
| ⚡ 100% Free Gemini Proxy | Built-in reverse-engineered web proxy: run `gemini-3.7-flash` with zero API key, no credit card, and 100% free anonymous access |
| 🍪 Google Account Cookies | Drop `config/gemini_cookies.json` to unleash `gemini-2.0-pro` with Google Search grounding and persistent context |
| 🔄 OmniRoute Gateway | Auto-detects local OmniRoute server (`localhost:20128`) for 350+ free models (Llama, DeepSeek, Qwen) with zero config |
| ⚡ SQLite Smart Cache | Fast LRU query caching (`config/llm_cache.db`) for weather, facts, news, and search queries, saving tokens and network latency |
| 🔒 Privacy & Git Shield | Built-in `.gitignore` automatically seals all keys, cookies, caches, and memory files away from git repositories |
| 👁️ HUD Camera & Vision | Instant webcam view on HUD ("camera kholo" / "camera band karo") and visual inspection ("camera dekho" / "screen dekho") with free Gemini AI Studio integration |
| 🎙️ Crystal-Clear Hindi Speech | Studio-quality neural voice (`hi-IN-SwaraNeural` / `hi-IN-MadhurNeural`) tuned at `+0Hz` natural pitch with Devanagari text formatting and offline Piper fallback |


---

## 🆕 Features & Innovations

J.A.R.V.I.S. is engineered to be **hands-free, faster, emotionally intelligent, and easy to extend** — all universal: no hardcoded language, no bundled asset files, works the same on Windows, macOS and Linux.

### 💖 Devoted Girlfriend Persona (GF Mode)
A deeply loyal, romantic, witty, and human-like companion. She treats you as her exclusive partner and soulmate, checks on your food and sleep schedules during late-night coding, cracks jokes about your bugs, and cutely pouts with possessive jealousy (*"Achha ji? Ab unse hi baat kar lo na fir! Mere paas kyu aaye ho? Hmph!"*) when other people or AI models are mentioned. In Hindi/Hinglish, she strictly speaks with feminine grammar (`करती हूँ, बोलूँगी, सोच रही थी, तुम्हारी हूँ`).

### 🌅 First-Boot Calendar & Clock Greeting
Every morning or on first launch of the day, the assistant greets you naturally with the complete calendar and clock coordinates: **Day, Date, Month, Year, and Time** (e.g. *"Arey Jaan! Aaj Thursday, 17 September 2026 hai aur abhi time 02:35 PM ho raha hai..."*). Delivered in a warm human voice with zero teleprompter bullet points.

### 🏷️ Natural Custom Naming (UI + Voice)
Personalize your assistant with any name you choose (*Maya, Pari, Shreya, Friday, etc.*). Set it through the HUD Studio UI, or simply say it aloud: *"Tumhara naam ab se Maya hai"* — the system updates its internal memory, window header, HUD title, and prompt identity live in real time.

### ⚡ Smart Token Efficiency & High-Bandwidth Speech
Responses are optimized for conversational punch: vivid, warm, and concise (typically 1 to 3 natural sentences) to conserve tokens and reduce latency. Elaborations and deep analysis are reserved for when you explicitly ask for technical explanations or multi-step execution.

### 🔮 Obsidian Second-Brain Dual-Sync
Connects directly to your local Obsidian vault via the **Local REST API** or file-system Markdown fallback. Search your notes, log thoughts, append to your daily journal, and query past activity seamlessly.

### 🎙️ Wake Word — "Hey Jarvis"
JARVIS can now sit quietly until you call it. Turn on **⚙ → WAKE WORD** (a one-click, opt-in download of a tiny local model) and it goes to sleep: the microphone is processed **only on your machine** by a local detector, and nothing is sent to the cloud until it hears **"Hey Jarvis."** Once awake it listens normally, then **auto-sleeps after 2 minutes** of silence. You can also **sleep/wake it by clicking** in the settings. Because it's a *local* gate, background chatter — *"I'm coming!"* to someone at home — never wakes it. It costs **zero** when off (the model isn't even loaded), and the detection runs in its own thread, so nothing else in the app slows down.

### ⚡ Instant Acknowledgment
No more silent gaps. When you ask for something that takes a moment — reading an uploaded file, a web/research search, building code — JARVIS **immediately** says one short, natural sentence *in your language* (*"Right away — going through that file now."*) and *then* runs the tool. Instant actions (opening an app, volume) stay snappy with no chatter.

### 🚀 Faster Live Engine — Gemini Live + Multi-Brain Matrix
The live session is powered by **Gemini Live**, with multi-provider backup across Cerebras, Groq, NVIDIA NIM, OpenRouter, Mistral, GitHub Models, SambaNova, DeepSeek, and local Ollama, cutting latency while keeping tools, voices, transcription, and sliding-window compression intact.

### ⚡ Supported High-Speed Free LLM Providers & Gateways (22+ Engines)

J.A.R.V.I.S. now supports 22+ high-speed, free-tier LLM providers, aggregators, and local gateways. Every provider can be configured directly from the Cyberpunk HUD Settings (`⚙ → AI PROVIDERS`), complete with a **dynamic model selector** and instant **`⚡ TEST` latency ping**.

| Provider | Free Tier (Approx) | Highlights | Why Use It in J.A.R.V.I.S.? |
|---|---|---|---|
| **Cerebras Cloud** | 1M tokens/day, 30 RPM | World's fastest AI inference (~2,000 tok/s, 20x faster than OpenAI) | Real-time conversational responses with zero delay. |
| **Groq LPU** | 30 RPM, 1K RPD | Ultra-fast LPU inference (350–1000 tok/s) | Rock-solid reliability and speed for long dialogues and coding. |
| **OpenRouter** | 20+ free models, 50 req/day | Unified API for 200+ models with `:free` tag | Testing and comparing different open models with one key. |
| **Google Gemini** | 1M tokens/min (free tier) | 1M+ token context window, native multimodal input | Extended memory, full documents, and live screen/webcam vision. |
| **NVIDIA NIM** | 1,000 free calls/month | 70+ models hosted on enterprise NVIDIA DGX Cloud | Access to Nemotron, Llama 3.3 70B, and DeepSeek R1. |
| **Mistral AI** | 1B tokens/month, 500K TPM | European open-weights leader, Codestral programming model | Outstanding code generation and GDPR-compliant reasoning. |
| **Cloudflare Workers AI** | 10,000 Neurons/day free | Globally distributed serverless inference at the edge | Lightweight, fast queries with zero credit card setup. |
| **Cohere** | 1,000 calls/month free | Specialized Command-R+ model with native search grounding | RAG citations, structured outputs, and factual retrieval. |
| **Zhipu AI (GLM)** | GLM-4-Flash permanently free | High-speed model with 200K context, zero expiration | Permanent free fallback brain with zero token anxiety. |
| **GitHub Models** | Free access with GitHub PAT | Direct access to GPT-4o, DeepSeek-R1, and Llama 3.3 | Use your existing developer GitHub account with no new signup. |
| **Hugging Face** | Serverless free inference API | 500,000+ open-source models with community endpoints | Testing novel architectures and niche fine-tunes. |
| **SambaNova Cloud** | 20 RPM, 200K tokens/day | Full-precision Llama 3.1 405B and 70B available free | Mammoth 405B parameter reasoning at blistering speeds. |
| **Kluster AI** | $5 free credits + permanent tier | Low-latency inference for DeepSeek R1 and Qwen 2.5 | Fast batch tasks and complex multi-step reasoning. |
| **LLM7.io** | 30–120 RPM free | Instant access, zero-friction, no signup required | Instant out-of-the-box operation with zero registration. |
| **FreeLLMAPI** | 1.7B tokens/month shared | Aggregator with automatic failover across 14+ providers | Eliminates 429 rate limit errors automatically. |
| **OrcaRouter** | $0 / token free tier | Auto-routing across top free community models | Zero markup smart router for free models. |
| **Vercel AI Gateway** | Unified free gateway tier | Failover routing with custom BYOK support | Edge failover orchestration for reliable uptime. |
| **FreeTheAi** | 60+ models free forever | Community-backed initiative for unrestricted free AI | 100% free models with zero subscription gates. |
| **OmniRoute Gateway** | Universal local proxy | Connects to 352+ providers and 1,200+ models on `localhost:20128` | All-in-one local aggregator with automatic fallback. |
| **Gemini Web Proxy** | 100% Free Built-in | Reverse-engineered web endpoints (`gemini-3.7-flash` on `:8081`) | Autonomous local proxy, works out-of-the-box without keys. |
| **DeepSeek Direct** | Official Free Tier | Official DeepSeek V3 and DeepSeek Reasoner R1 | Ultra-smart reasoning and mathematical problem solving. |
| **Custom / Local AI** | Unlimited offline | Local Ollama, LM Studio, vLLM, or private OpenAI endpoint | Complete offline privacy with zero external internet dependencies. |

#### 🎛️ Individual Provider & Model Selection in Settings:
1. Open the HUD settings by clicking the **⚙ (Gear)** icon on the Cyberpunk HUD.
2. Select the **🤖 AI PROVIDERS** tab.
3. Choose your desired provider from the **ACTIVE BRAIN / LLM PROVIDER** dropdown.
4. The **ACTIVE MODEL FOR SELECTED PROVIDER** combobox will automatically populate with that provider's models (e.g. `llama-3.3-70b` for Cerebras, `meta/llama-3.3-70b-instruct` for NVIDIA NIM, `Meta-Llama-3.1-405B-Instruct` for SambaNova).
5. You can pick any model from the dropdown or type in any custom model name.
6. Click **⚡ TEST** next to your API key to verify latency and connectivity in real time (e.g. `🟢 Cerebras Live • 142ms`).
7. Click **SAVE & CLOSE** — your active provider, chosen models, and API keys are safely recorded in `config/api_keys.json` with zero git leakage.


### 🧩 Self-Describing Skills — a Scalable Core
Every bundled **action** now carries its own `TOOL` declaration in its own file (exactly like a drop-in **plugin's** `PLUGIN` dict), and the core auto-discovers them at launch. `main.py` no longer holds a giant list of tool definitions and dispatch branches — it shrank by hundreds of lines. Adding a new built-in skill, or promoting an `actions/*.py` file into a shareable plugin, is now just… moving a file.

### 🌐 100% Free AI Architecture (Zero Subscriptions, No API Key Required)

J.A.R.V.I.S. features an autonomous free AI pipeline that requires zero paid subscriptions and zero credit cards.

#### 1. Built-in Gemini Free Web Proxy (Anonymous Mode)
- **Architecture**: J.A.R.V.I.S. includes an embedded proxy server (`core/gemini_free_proxy.py`) running on port `8081`. It routes requests directly through Google's public web endpoints using reverse-engineered Batchexecute RPCs.
- **Model**: Delivers `gemini-3.7-flash` and `gemini-2.0-flash` completely free.
- **API Key**: None required (`"Authorization": "Bearer none"`).
- **Daily Rate Limits**: Google applies IP-based rate limits (~10-15 requests per minute, rolling hourly quota). To maximize uptime, J.A.R.V.I.S. automatically pairs the proxy with the SQLite Smart Cache to prevent duplicate queries from consuming quota.

#### 2. Enhanced Mode: With Free Google Account Cookies (`gemini_cookies.json`)
For power users who want `gemini-2.0-pro` with Google Search grounding and practically unlimited requests without paying:
1. Open your browser (Chrome, Edge, or Firefox) and log into [gemini.google.com](https://gemini.google.com).
2. Press `F12` to open Developer Tools, then go to **Application** (or **Storage**) → **Cookies** → `https://gemini.google.com`.
3. Locate and copy the values for:
   - `__Secure-1PSID`
   - `__Secure-1PSIDTS`
4. Create or edit `config/gemini_cookies.json`:
```json
{
  "__Secure-1PSID": "your_secure_1psid_here",
  "__Secure-1PSIDTS": "your_secure_1psidts_here"
}
```
5. When J.A.R.V.I.S. starts, the free proxy automatically attaches these cookies. You instantly unlock `gemini-2.0-pro`, Google Search grounding, image generation capabilities, and significantly higher request ceilings!

#### 3. OmniRoute Gateway Integration (`localhost:20128`)
- If you have [OmniRoute](https://github.com/dani-garcia/vaultwarden) installed (`npm install -g omniroute`), J.A.R.V.I.S. automatically detects the gateway on `http://localhost:20128/v1`.
- Provides instant, zero-cost access to over 350+ free models (DeepSeek R1/V3, Llama 3.3 70B, Qwen 2.5, Mistral) with auto-failover.

#### 4. Smart SQLite LLM Cache (`config/llm_cache.db`)
- To protect your quotas and eliminate network latency, all deterministic queries (weather reports, news recaps, fact retrieval, system status checks) are cached in a local SQLite database (`config/llm_cache.db`) with adaptive TTL (Time-To-Live).
- Identical questions are answered in **< 2 milliseconds** with zero network round trips.

#### 5. Absolute Privacy & Git Protection
- Your privacy is guaranteed. All configuration files containing personal credentials, browser cookies, local caches, and memory stores (`config/api_keys.json`, `config/gemini_cookies.json`, `config/llm_cache.db`, and `memory/long_term.json`) are strictly excluded in `.gitignore`.
- You can safely commit and share your code without ever leaking keys or conversations.

---

### 👁️ Real-Time Camera & Vision Guide

J.A.R.V.I.S. features native visual awareness that works across both keyboard chat and voice commands:

- **HUD Camera Commands**:
  - Say or type `"camera kholo"`, `"open camera"`, `"webcam on"`, or `"show camera"` — the real-time webcam feed launches directly on the Cyberpunk HUD.
  - Say or type `"camera band karo"`, `"close camera"`, or `"stop camera"` — the webcam feed closes immediately.
- **Visual Inspection & Analysis**:
  - Say or type `"camera dekho"` or `"look at camera"` — J.A.R.V.I.S. opens the camera stream and captures the active frame.
  - Say or type `"screen dekho"`, `"look at screen"`, or `"what is on my screen"` — captures the primary display and analyzes open windows, code, or errors.
- **Multimodal Vision Modes**:
  - **Free Mode / Anonymous Proxy**: Displays live real-time video stream on the HUD.
  - **Gemini AI Studio Mode (100% Free)**: For automated live AI visual analysis of objects, code, and screen context, simply generate a free API key from [Google AI Studio](https://aistudio.google.com/) (costs ₹0, requires no credit card) and save it in `config/api_keys.json`. J.A.R.V.I.S. will automatically analyze your webcam and screen with multimodal precision!

---

### 🎙️ Natural Voice Synthesis (Zero Robotic Accent)

To ensure the assistant sounds like an authentic human being and never mechanical:
1. **Natural Pitch Calibration**: The pitch is calibrated to `+0Hz` (natural native pitch). Higher artificial pitch boosts (`+14Hz`) have been eliminated to avoid metallic phase-distortion.
2. **Devanagari Script Delivery**: For Hindi and Hinglish dialogues, text is synthesized using clean Devanagari Hindi. Azure Neural TTS (`hi-IN-SwaraNeural` and `hi-IN-MadhurNeural`) and Piper Hindi (`hi_IN-pratham-medium`) are phonologically tuned for Devanagari, producing warm, emotional Indian human cadence with zero English spelling artifacts.
3. **Smart Speech Sanitization**: All markdown formatting (`**bold**`, `*italic*`), code fences (`` ```python ... ``` ``), bracketed metadata, URLs, and emojis are automatically scrubbed before reaching the speech engine, ensuring clean, uninterrupted vocal flow.
4. **Offline Piper Fallback**: If EdgeTTS experiences any network disruption, speech automatically and seamlessly switches to the local Piper Hindi engine without crashing.

---

## 🔄 Core Architectural Foundation

Designed with high stability and modularity so new capabilities never compromise core functionality. No new dependencies. No bundled asset files. No hardcoded language, and nothing that assumes one operating system.

### 🧠 A memory that actually remembers

The store was capped at **2,200 characters — the whole memory, not per entry** — because all of it was pasted into the system prompt on every connect, so growing the memory grew every request. When it filled, the oldest entries were deleted and one line was printed to a console nobody reads. An assistant advertised as remembering "projects, preferences and personal context" was in practice a two-page notepad that quietly forgot your sister's name after a few weeks.

Storage and prompt budget are now separate problems:

* **Nothing is deleted.** The cap is a runaway guard normal use never approaches, and if it is ever hit it says so in the activity log instead of on stdout.
* **The prompt carries a core, not a dump.** Identity in full, then the most recently updated facts, budgeted — measured at **971 characters on a memory holding 62 stored facts.** That is *smaller* than the old whole-store cap, so sessions now connect with fewer tokens than before.
* **The rest is fetched on demand.** A `recall_memory` tool searches the full store locally — no network, no second model, well under a millisecond.

The part that is easy to get wrong: **a model cannot look something up if it doesn't know the thing exists.** So the prompt also carries an **index of the keys** it had no room for. Without it, "who is Ayşe?" gets "I don't know" while `ayse_sister` sits on disk unread. That index interleaves categories rather than sorting by recency — sorted like the core, a memory with forty preferences pushed the one entry the index existed for off the end.

⚙ → **🧠 MEMORY** shows every stored fact, when it was learned, and a ✕ to forget it. Everything stays in `memory/long_term.json` on your machine.

### ↩️ Undo — it can take back what it did

JARVIS moves files, renames them, writes to them and changes your settings. None of that had a way back; if it misheard you, the only remedy was to fix it by hand.

Say **"undo"** — in any language — and it reverses its own last action:

| | |
|---|---|
| **Files** | move · rename · create · copy · write · delete · organize desktop |
| **Settings** | volume · brightness · dark mode |

Three things it deliberately does *not* do:

* **It does not guess.** Settings undo reads the current value *before* changing it. Where a platform won't report that value, nothing is registered — an undo that restores a guess is worse than no undo.
* **It does not hoard.** Undoing a write means keeping the old contents in memory, so files over 1 MB are excluded and it says so rather than holding a 200 MB log for the session.
* **It does not delete your files to undo a copy.** The reverse of a copy is removing the copy; the reverse of "create a folder" is removing it *only while it's still empty*.

`organize_desktop` gets special treatment — one command that moves dozens of files, which made it the least reversible thing the assistant could do. It journals every move and puts all of them back in one go, cleaning up the folders it created if they're still empty.

**Undo costs nothing at runtime.** It appends a closure to a list; nothing in it runs unless you ask.

### ⚠️ A confirmation the model can't forge

The old gate read like this:

```python
if action in _DANGEROUS_ACTIONS:            # {"restart", "shutdown"}
    confirmed = str(params.get("confirmed", "")).lower()
```

`confirmed` is a **tool parameter, which means the model fills it in.** Nothing stopped it sending `confirmed=yes` on the first call and nothing checked that a human was ever involved. It was a convention, not a gate. And its coverage was two actions — so `toggle_wifi`, which cuts the assistant's own connection to the Live API and therefore *cannot be asked to undo itself*, went through with no gate at all.

The token is now issued by the interface. Shutdown, restart and WiFi put a banner on the HUD and **return immediately**; the action runs only if you press CONFIRM. Nothing blocks — JARVIS keeps talking while the banner is up — so this is **cheaper than the old gate**, which burned two tool round trips on every power command.

> The split between the two mechanisms is about reversibility, not about how alarming a word sounds. Anything undoable is done at once; only the genuinely irreversible asks. An assistant that checks with you before turning the volume down is one you stop talking to.

### 🎧 It finally asks which microphone

Both audio streams opened with no device argument at all, so they always took whatever the OS called "default" — and on Windows that *moves on its own* the moment you plug a headset in. "JARVIS can't hear me" almost always meant "JARVIS is listening to the webcam".

⚙ → **🎧 AUDIO DEVICES** lets you pick the microphone and the speakers by name. Two things matter more than the dropdown:

**The list is short.** `query_devices()` returns one entry per *device × host API*, not per device — measured on an ordinary Windows machine, **41 entries for what the sound settings show as 4 microphones and 4 speakers.** The same microphone appears four times, under MME, DirectSound, WASAPI and WDM-KS, with nothing to say which is which. That is not a choice, it's a quiz. The picker takes one host API per direction, drops the "Sound Mapper" and "Primary Sound Driver" pseudo-devices that just mean "default", and deduplicates. **41 → 8.**

**Every entry has been measured, not assumed.** The obvious approach is to pick the host API with the nicest names — WASAPI on Windows, which in shared mode **doesn't resample**, so with 16 kHz in and 24 kHz out against 48 kHz hardware every open failed. Adding a rate check and moving to DirectSound passes that test on both sides, and PortAudio's DirectSound **output is a silent sink**: the stream opens, every write returns success in ~0 ms, and not one sample reaches the speakers.

| | write(2.0 s) took | |
|---|---|---|
| MME | **2.02 s** | consumed in real time |
| DirectSound | **0.00 s** | swallowed instantly |

No capability flag reports that. So the app measures it — once per host API per direction, on a background thread at startup, using silence. Two consequences worth stating plainly:

* **Each direction picks its own host API.** On Windows this lands on DirectSound for the microphone and MME for the speakers — a split no amount of reasoning would have produced.
* **The probe runs in the mode the app actually ships.** DirectSound input passes a callback stream and fails a blocking read; probing the wrong mode rejected a microphone that works perfectly.

Your choice is stored **by name, not by index** — indices shift whenever something is plugged in. If the saved device is gone, it falls back to the system default and says so in the log rather than failing to start.

### 🔗 It stops forgetting the conversation when the connection drops

`session_resumption` was switched on in the config and the handle the server sent back was **never read** — so every reconnect started an empty session. A dropped packet, or simply changing the voice, wiped the conversation. "Unlimited sessions" leaked through exactly this hole.

The handle is captured and replayed now. A network blip, or switching your microphone, keeps the conversation intact.

It is held in memory only, deliberately: writing it to disk would make a fresh launch continue yesterday's chat, which sounds appealing but breaks the session-summary flow — a conversation that never ends never produces a summary, and the "yesterday we talked about…" line in the morning briefing silently disappears. Changing the **voice** also starts clean on purpose, since resuming restores the server's session state and would likely bring the old voice back with it.

### 🩹 Fixes that came with it

* **The assistant could die on a log line.** Status lines carry emoji and arrows (`📤 file_controller → Moved: a.txt → Documents/`). On a non-UTF-8 console — cp1254 on a Turkish Windows, cp1251 on a Russian one, cp932 on a Japanese one — printing one raises `UnicodeEncodeError`, and because that print sits *after* the tool's own `try/except`, it escaped into the receive loop and took the session down.
* **Every computer command paid for two model round trips.** `computer_settings` made an *entire second Gemini call, inside the tool*, purely to translate the request into one of its own action names — because the declaration only said "The action to perform", so the model rarely filled it in. When that second call failed, the fallback was `description.lower().replace(" ", "_")`, which turns the Turkish for "turn it down" into `sesi_kis` and straight into "Unknown action". The declaration now names all 56 actions and the rest is spelling tolerance handled locally by `difflib` in microseconds. When nothing matches it suggests real action names instead of dead-ending.
* An unresolvable saved audio device, or one the driver refuses to open, falls back to the system default and says so — on both the microphone and the speakers.
* A rejected session-resumption handle is dropped after one attempt, so an expired handle can never be replayed on every retry and prevent the reconnect it exists to protect.



---

### 🗺️ Evolution & Architecture Roadmap

| Phase | Capabilities |
|---|---|
| **Core Base** | Auto-start · clipboard intelligence · assistant customization |
| **Telemetry** | Session memory · background monitoring · proactive 2.0 · instant vision |
| **Ecosystem** | Plugin system · affective dialog · proactive audio · unlimited sessions |
| **HUD & Voice** | Voice picker · live theming · reactive HUD · recallable memory · undo · real confirmation · audio device picker · session continuity |
| **Intelligence**| Wake word · Gemini Live + Groq Llama-3.3 70B + DeepSeek · instant acknowledgment · self-describing action/plugin architecture |
| **Offline Lab** | Offline Piper Hindi TTS (Devanagari) · Stark SFX · Zero-token drive gauges & Open-Meteo weather |

---

## ⚡ Quick Start

```bash
git clone https://github.com/SudhirDevOps1/J.A.R.V.I.S.git
cd J.A.R.V.I.S
python setup.py        # installs deps for YOUR OS + the browser automation engine
python main.py
```

`setup.py` only ever installs what your operating system needs — the Windows-only libraries are skipped automatically on macOS and Linux (and vice-versa). Prefer to do it by hand? `pip install -r requirements.txt` works too.

> ⚠️ **Installation Note:** If you hit a `ModuleNotFoundError` for an OS-specific package, install it with `pip install <module_name>`. The optional **wake word** engine is *not* installed here — grab it in one click from **⚙ → WAKE WORD** inside the app.

---

## 📋 Requirements

| Requirement | Details |
| --- | --- |
| **OS** | Windows 10/11, macOS, or Linux |
| **Python** | 3.11 or 3.12 |
| **Microphone** | Required for voice interaction (and for the "Hey Jarvis" wake word) |
| **Speakers** | Required for voice replies |
| **API Key** | Free Gemini / Groq API key (entered on first launch → `config/api_keys.json`) |
| **Wake word** *(optional)* | One-click download from ⚙ → WAKE WORD (`openwakeword`, fully local) |

---

## 🗂️ Project Structure

```
J.A.R.V.I.S./
├── main.py                   # Core loop — Gemini Live session, audio I/O, wake/sleep state, tool dispatch
├── ui.py                     # PyQt6 HUD — reactive waveform, log panel, settings drawer, plugin manager, camera feed
├── setup.py                  # OS-aware installer (skips wrong-OS dependencies)
├── plugins/
│   ├── _template.py          # Copy this to write a new plugin — one file, drop in, done
│   └── ...                   # Drop-in skills (each self-describes via a PLUGIN dict + run())
├── actions/                  # Bundled skills — each self-describes via a TOOL dict + handler
│   ├── web_search.py         # Gemini + DDG parallel search (news, research, price, compare)
│   ├── screen_processor.py   # Screen & webcam capture for vision
│   ├── background_monitor.py # User-configured topic watching — daily DDG check, no crypto
│   ├── proactive.py          # Proactive 2.0 — time/context/rotation-aware check-ins
│   ├── send_message.py       # Messaging integration
│   ├── weather_report.py     # Live weather data
│   ├── flight_finder.py      # Flight search
│   ├── youtube_video.py      # YouTube playback control
│   ├── game_updater.py       # Game update management (Steam / Epic)
│   ├── code_helper.py        # Code review and generation
│   ├── dev_agent.py          # Developer task agent
│   └── desktop.py            # Desktop and taskbar control
├── memory/
│   ├── memory_manager.py     # Load/save long_term.json — sessions, monitors, identity
│   ├── config_manager.py     # api_keys.json access — key, OS, name, voice, colour, toggles
│   └── long_term.json        # Persistent store: identity, preferences, projects, sessions, monitors
├── core/
│   ├── prompt.txt            # Assistant personality and tool-routing rules
│   ├── undo.py               # One shared undo stack — actions register how to reverse themselves
│   ├── confirm.py            # Irreversible-action gate — the token is issued by the UI, not the model
│   ├── audio_devices.py      # Microphone / speaker list — filtered, measured, resolved by name
│   ├── plugin_loader.py      # Plugin engine — discovery, validation, crash isolation
│   ├── action_loader.py      # Bundled-action engine — the built-in twin of plugin_loader
│   └── wake_word.py          # Local "Hey Jarvis" detector — own thread, offline, opt-in
└── config/
    └── api_keys.json         # API key, OS setting, assistant name, user name, voice, UI colour, toggles
```

---

## ⚖️ License

Licensed under the **[MIT License](LICENSE)**. Open-source and free for all developers.

---

## 👤 Connect with the Creator

Engineered by SudhirDevOps1.

| Platform | Link |
| --- | --- |
| GitHub | [@SudhirDevOps1](https://github.com/SudhirDevOps1) |
