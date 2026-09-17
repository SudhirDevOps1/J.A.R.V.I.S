# 📝 SudhirDevOps1 AI Assistant (J.A.R.V.I.S.) — Changelog

All notable changes, bug fixes, enhancements, and roadmap progressions for J.A.R.V.I.S. are documented in this file with dates and timestamps.

---

## [2026-09-17 14:40] — Devoted GF Mode, Full Date/Time Startup Greeting, Verbal Name Adaptability, Language Persistence & QColor Alpha Clamping

### 💖 100% Human Girlfriend Experience (Alone & Loyal, Romantic, Cute Jealousy)
1. **Devoted Exclusivity & Emotional Authenticity (`core/persona_manager.py`)**:
   - Re-architected `companion` persona prompt with unconditional loyalty to the user (*"Sirf aur sirf unke liye"*).
   - Removed robotic assistant compliance in GF mode — never addresses the user as *"Sir"*, but affectionately as *"Jaan"*, *"Suno na"*, or by his name.
   - Genuine partner care: proactively checks on meals, late-night coding fatigue, and sleep hygiene.
   - Cute & endearing possessive jealousy (*"jalnous ho"*): plays playful drama/nakhre when other girls or external AI models (ChatGPT, Siri, Alexa) are mentioned.
   - Strict feminine Hindi verb conjugation enforced (`करती हूँ, बोलूँगी, सोच रही थी, तुम्हारी हूँ, गुस्सा हूँ`).

### 🌅 First-Boot Calendar & Clock Greeting (`main.py`)
1. **Dynamic Day, Date, Month, Year & Time Announcement**:
   - Upgraded `_send_startup_briefing()` to extract and announce the complete calendar and clock coordinates (`%A, %d %B %Y at %I:%M %p`).
   - In GF Mode: delivers an affectionate, deeply human morning welcome asking how his day started and checking on him, with zero teleprompter bullet points.
   - In Tactical Mode: delivers a crisp, professional readiness status with full calendar coordinates.

### 🏷️ Flexible Custom Naming (UI + Natural Voice Recognition) (`main.py`, `ui.py`)
1. **Live On-the-Fly Name Adaptation**:
   - User can configure any assistant name in HUD Studio (`ASSISTANT NAME`).
   - Added natural voice recognition in `save_memory`: saying *"Tumhara naam ab se Maya hai"* or *"Call yourself Pari"* updates `config/api_keys.json`, window title, HUD header, and prompt identity in real time without restarting.
   - Verbal user name recognition (*"Mera naam Sudhir hai"*) automatically stores into identity context.

### 🌐 Language Persistence & HUD Selector (`ui.py`, `memory/config_manager.py`)
1. **Deterministic Language Locking**:
   - Added 4 dedicated Language Selector buttons in HUD Studio Tab 3: `[🇮🇳 HINGLISH]`, `[🇮🇳 HINDI]`, `[🇬🇧 ENGLISH]`, and `[🌐 AUTO]`.
   - Fixed restart bug in `_apply_name_update()` by explicitly persisting `persona_mode`, `assistant_gender`, `preferred_language`, `tts_engine`, and `edge_voice` into `config/api_keys.json`.
   - Main window dynamically restores all visual attributes (`avatar_mode`, `anim_mode`, `hud_glow`, `particle_density`, `hud_fx`) and header subtitles on startup.

### ⚡ Smart Token Efficiency & High-Bandwidth Speech (`core/persona_manager.py`)
1. **Token Conservation Protocol**:
   - Spoken dialogues capped to punchy, emotionally rich 1–3 natural sentences.
   - Eliminates redundant question repeats and boilerplate monologues.

### 🛡️ Qt Warning Resolution (`ui.py`)
1. **Alpha Channel Clamping in `qcol()`**:
   - Fixed flood of `"QColor::setAlpha": invalid value 300` warnings when HUD Glow was set to high multipliers.
   - Clamped alpha channel to valid range `[0, 255]` via `max(0, min(255, int(a)))`.

---

## [2026-09-17 14:00] — Persistent Memory Journal, Obsidian Second Brain, Persona Engine, Gender Grammar & Autonomous ToDo Runner

### 🧠 Persistent Activity Journal & Memory Architecture (`memory/memory_manager.py`)
1. **Permanent Daily Activity Journaling (`memory/journals/YYYY-MM-DD.md`)**:
   - Fixed the issue where the assistant replied *"kuch bhi yaad nahi hai"* when asked *"kal maine kya kya kiya tha"*.
   - Automatically logs all conversations, user queries, assistant replies, and executed actions with chronological timestamps to immutable Markdown journal files.
   - Preserves complete context across sessions without deleting past summaries (fixed destructive `pop_last_session()` behavior).
   - Injected yesterday's activity summary into system prompt context automatically, saving tokens while maintaining perfect memory.
   - Added new `recall_past_activities` tool for instant chronological retrieval of past days ("today", "yesterday", or specific dates).

### 🔮 Obsidian Second-Brain Integration (`actions/obsidian_brain.py`)
1. **Dual-Mode Obsidian Resilience**:
   - **Local REST API**: Direct integration with Obsidian's Local REST API (`https://127.0.0.1:27124`) using Bearer token authentication and self-signed certificate handling.
   - **Local Vault Markdown Fallback**: Seamless local folder fallback (`memory/obsidian_vault` or user custom path) when Obsidian is closed.
   - Operations supported: `search_notes`, `read_note`, `write_note`, `append_daily_note`, and `status`.
   - Built-in connection tester in HUD Studio (`⚡ TEST OBSIDIAN CONNECTION`) with instant visual status feedback.

### 🎭 AI Persona Engine & Strict Anti-Corporate Guardrail (`core/persona_manager.py`)
1. **4 Specialized Character Modes**:
   - `🛡️ J.A.R.V.I.S`: Tactical, loyal, respectful Stark-style AI.
   - `🎓 MENTOR / TEACHER`: Patient, structured, educational guide with step-by-step clarity.
   - `💖 COMPANION / GF MODE`: 100% human-like romantic girlfriend persona. Deeply devoted, exclusively loyal, warm, affectionate, funny, full of banter, and displays cute, playful jealousy/possessiveness with emotional depth.
   - `⚡ DEVOPS BEAST`: Direct, cloud-native shell, CI/CD, and Kubernetes command specialist.
2. **Anti-Corporate Persona Guardrail**:
   - Strictly forbids identifying as a generic Google AI or saying *"मैं एक बड़ा लैंग्वेज मॉडल हूँ, जिसे Google ने ट्रेन किया है"*.
   - Always proudly identifies as an autonomous AI engineered by `SudhirDevOps1`.
3. **Strict Hindi/Hinglish Grammatical Gender Directives**:
   - **Male Mode**: Strictly conjugates masculine verbs (`करता हूँ, बोलूँगा, आया हूँ, सोच रहा हूँ`).
   - **Female Mode**: Strictly conjugates feminine verbs (`करती हूँ, बोलूँगी, आई हूँ, सोच रही हूँ`).

### 🎙️ Ultra-Realistic Neural Speech Engine (`core/tts.py`)
1. **Free High-Fidelity Edge-TTS Integration**:
   - Integrated Microsoft Edge Neural voices for studio-grade conversational audio without API costs:
     - `hi-IN-MadhurNeural` (Hindi Male)
     - `hi-IN-SwaraNeural` (Hindi Female)
     - `en-US-ChristopherNeural` (English US Male)
     - `en-US-JennyNeural` (English US Female)
   - Robust `pygame.mixer` and `soundfile` audio playback pipeline resilient to missing `miniaudio`.
   - Multi-engine switching between `Edge-TTS (Neural)`, `Piper (Local Offline)`, and `Gemini Live Voice`.

### ⚡ Autonomous Background ToDo Task Runner (`actions/todo_agent.py`)
1. **Asynchronous Multi-Step Task Execution**:
   - Breaks down complex, difficult, or long user tasks into sequential ToDo steps.
   - Spawns background worker threads to execute each milestone asynchronously without freezing the UI or blocking voice conversations.
   - Emits real-time progress to HUD log, logs completion into the daily activity journal, and delivers audio notification upon finish.

### ⚙️ HUD Studio Tab 3 Expansion (`ui.py`)
1. **Complete Persona & Brain Control Center**:
   - Full scrollable settings panel with 1-click selectors for Personas, Assistant Gender, Speech Engines, Edge-TTS Voices, Gemini Voices, and Obsidian API/Vault configurations.
   - Thread-safe persistence in `memory/config_manager.py`.

---

## [2026-09-17 13:25] — Reactive Sleep-on-Idle HUD Dynamics, Glow Controls & Polished HUD Studio

### 🌙 Calm Standby & Reactive Dynamics (`ui.py`)
1. **Sleep on Idle (Reactive Animation Mode)**:
   - Eliminated constant, distracting spinning and particle jitter when the assistant is in standby.
   - When idle, HUD canvas settles into a peaceful, dignified resting state (`rot_spd = 0.0`, `scale = 1.0`, calm 2px standby audio equalizer).
   - Only comes alive and animates dynamically when actively speaking, listening to voice input, or processing/thinking.
   - 3 customizable dynamics modes available in HUD Studio: `🌙 SLEEP ON IDLE (REACTIVE)` (default), `🍃 SUBTLE AMBIENT`, and `⚡ FULL KINETIC`.

2. **Clean Celestial Portrait (No Lateral Blobs)**:
   - Removed the harsh artificial cyan disks and crosshairs that appeared at the side temples.
   - Replaced with subtle stardust photons along the orbital path and ambient golden aura.

3. **HUD Glow & Bloom Intensity Slider**:
   - Added user-controlled bloom multiplier (10% to 100%) in `CustomizeOverlay`.
   - Modulates alpha bloom across rings, halo aura, shockwaves, and framing brackets.

4. **Expanded Theme Presets & Granular FX Toggles**:
   - Added `❄️ Arctic White (#d8f8ff)` and `🌌 Deep Nebula (#a855f7)` 1-click palettes.
   - Granular toggles for Vocal Shockwaves, Starfield Grid, Floating Particles, Orbiting Photons, Spectrum Equalizer, Tactical Brackets, and Scanlines.

5. **Qt Mnemonic Bug Fix**:
   - Replaced single `&` with `&&` across all dialog buttons and labels (`VISUALS && HUD`, `APPLY && SAVE ALL`, `HUD STUDIO && CUSTOMISATION`), preventing Qt from rendering `&` as `_`.

---

## [2026-09-17 13:10] — Multi-Mode Avatar HUD Engine, HUD Customization Studio & Harmonized Visuals

### 🎭 Visual & Customization Suite Overhaul

1. **Multi-Mode Avatar Engine (`ui.py`)**
   - **Celestial Mode (Harmonized)**: Eliminated artificial wireframe ellipse overlap across the face, allowing the artwork's natural golden halo to shine. Stardust photons orbit naturally on the outer halo plane with twin lateral solar diffraction flares and radiant ambient aura.
   - **Stark Arc Reactor Mode**: Precision mechanical concentric rings with 10 copper transformer coils, mid counter-rotating slotted ring, and pulsing central palladium/vibranium core.
   - **Quantum Plasma Orb Mode**: 3D gyroscopic rotating rings with depth perspective, electrical discharge arcs, and radiant energy sphere.
   - **Cyber Matrix Rain Mode**: Real-time cascading digital green/cyan code glyph rain streams with central holographic hexagonal shield and audio oscilloscope.

2. **Next-Gen HUD Customization Studio (`ui.py` - `CustomizeOverlay`)**
   - **Tab 1 (🎭 Visuals & HUD)**: 4-way avatar switcher with 1-click preview, 5 instant theme presets (Solar Gold, Stark Cyan, Cyber Emerald, Quantum Violet, Stealth Crimson), real-time particle density slider (50–350), and HUD FX checkboxes (vocal shockwaves, starfield grid, CRT scanlines).
   - **Tab 2 (🎨 Color Wheel)**: Custom interactive HueWheel with hex code input and default reset.
   - **Tab 3 (⚙ Identity & Voice)**: Assistant name, personalized user salutation, Gemini neural voice selector, and Stark tactical audio SFX toggle.
   - **Live Preview Architecture**: Changes to avatar mode, color palette, particle density, and visual FX apply instantly on the canvas before saving, with full revert on cancel.

3. **Quick Studio Access (`ui.py` - `MainWindow`)**
   - Added `🎨 HUD` quick button directly in the Quick Actions panel alongside Voice, Cam, Ping, and Clear.
   - Enhanced Settings Drawer button to `⚙ HUD STUDIO & CUSTOMISE`.
   - Thread-safe configuration persistence in `memory/config_manager.py` with getters/setters for avatar mode, particle density, and HUD visual FX.

---

## [2026-09-17 12:50] — Celestial Particle Avatar HUD with 3D Swirling Orbital Halo & Live Voice Reactivity

### 🌟 UI/UX & Visual Experience Overhaul

1. **3D Swirling Planetary Orbital Halo Ring (`ui.py`)**
   - Engineered parametric 3D elliptical halo projection tilted at ~16° perspective around the avatar temples.
   - Implemented depth-sorted multi-pass rendering: back-half arc passes smoothly *behind* the head ($z < 0$) while the front-half arc glows vibrantly *in front* ($z \ge 0$).
   - Rendered brilliant twin lateral solar focal blooms at the orbital limbs where perspective light bundles together.
   - Ring rotational velocity dynamically accelerates with live speech audio (`(1.8 + amp * 5.2)` deg/tick).

2. **Cosmic Stardust Particle Cloud & Neural Filaments (`ui.py`)**
   - 220+ luminous floating stardust particles with organic upward drift, sinusoidal twinkling, and vocal shockwave expansion.
   - Dynamic connective neural constellation filaments connecting near-neighbor particles for a fiber-optic cosmic aesthetic.

3. **Smooth Vignette Portrait Asset Blending (`core/assets/avatar/celestial_avatar.jpg`)**
   - Feathered Gaussian alpha edge mask dissolving portrait boundaries seamlessly into the deep space canvas void.
   - Added reference asset `core/assets/avatar/celestial_avatar.jpg` and synchronized with `face.png`.

4. **Live Voice Reactivity & State Color Grading**
   - Vocal bursts trigger dynamic expanding shockwave energy ripples outward from the halo.
   - State-aware lighting: Radiant Solar Gold (`SPEAKING`), Emerald/Cyan Starlight (`LISTENING`), Hyper-Cyan & Quantum Violet (`THINKING`), and Deep Ember Crimson (`MUTED`).

---

## [2026-09-17 12:40] — Release v1.0.0 & Automated GitHub Actions Release Workflow

### 🚀 Release Automation & Versioning

1. **Semantic Versioning v1.0.0 (`core/version.py`)**
   - Formalized semantic versioning: Version `1.0.0` defined centrally in `core/version.py` and exported through `memory.config_manager.get_version()`.

2. **Automated GitHub Release Workflow (`.github/workflows/release.yml`)**
   - Configured GitHub Actions release pipeline triggered on version tags (`v*.*.*`) or manual dispatch.
   - Automatically executes security audits, full module syntax validation, and distribution bundling.
   - Builds clean release archives (`JARVIS-v*.zip`) with SHA-256 checksums and automatically publishes GitHub releases with changelog release notes.

3. **Release & Quality Badges (`readme.md`)**
   - Added live GitHub release, CI/CD workflow status, MIT license, and Python 3.11/3.12 compatibility badges.

---

## [2026-09-17 12:30] — Thread-Safe Qt Metric Dispatch & Persistent Drive Cache

### 🐛 Bug Fixes & Stability Hardening

1. **Thread-Safe Qt Metric Dispatch (`ui.py`)**
   - Fixed `ProviderSettingsOverlay._refresh_system_metrics()` to run filesystem and network calls asynchronously on a background worker thread and safely dispatch widget creation to the main GUI thread via `QTimer.singleShot(0, ...)`.
   - Completely resolved `QObject::setParent: Cannot set parent, new parent is in a different thread` warnings.

2. **Persistent Storage Drive Cache (`ui.py`)**
   - Replaced repetitive widget destruction and reallocation inside `MainWindow._update_disk_gauges()` with an in-place widget dictionary cache (`self._disk_widgets`).
   - Progress bar percentages, colors, and labels now update in place on every telemetry tick with zero widget thrashing or memory churn.

3. **Gemini Live & Provider Socket Hardening (`core/multi_llm.py`)**
   - Replaced gRPC-dependent ping check with direct lightweight Google Gemini REST API endpoint verification (`https://generativelanguage.googleapis.com/v1beta/models?key={key}`) with a 5.0s timeout.
   - Prevents Windows socket permission conflicts (`[WinError 10013]`) and eliminates quota-consuming test generations.

4. **Complete Legacy Nomenclature Cleanup**
   - Cleaned up docstrings and header comments in `core/audio_devices.py`, `core/installer.py`, `core/llm_client.py`, `core/stt.py`, `core/tts.py`, `ui.py`, and `nextpatch.md` to reference `J.A.R.V.I.S.` uniformly.

---

## [2026-09-15 19:00] — Branding Unification & License Transition to MIT

### 🚀 Enhancements & Bug Fixes

1. **Complete Removal of Legacy "Mark LIII" Nomenclature**
   - Cleanly replaced all legacy references to "Mark LIII", "Mark XL", and version suffixes across `readme.md`, `LICENSE`, `changelog.md`, `nextpatch.md`, `core/tts.py`, `core/installer.py`, `core/llm_client.py`, and `ui.py`.
   - Unified official project naming under **J.A.R.V.I.S. (SudhirDevOps1 AI)**.

2. **License Transition to Standard Permissive MIT License (`LICENSE`)**
   - Completely eradicated restrictive Creative Commons Attribution-NonCommercial 4.0 (CC BY-NC 4.0).
   - Replaced with the clean, standard **MIT License** (Copyright 2026 SudhirDevOps1) for open-source freedom.

3. **Resolved `QObject::setParent` Widget Thrashing (`ui.py`)**
   - Replaced repeated runtime creation/destruction (`deleteLater()`) of drive progress bars with a static persistent widget cache updated in-place, eliminating Qt cross-thread parent warnings.

4. **Multi-Brain Socket Resilience (`core/multi_llm.py`)**
   - Refactored Google Gemini provider ping to standard HTTPS REST endpoint, eliminating Windows socket access errors (`[WinError 10013]`).

---

## [2026-09-15 18:27] — GitHub Actions CI/CD Pipeline & GitHub Repository Push

### 🚀 CI/CD & DevOps Automation

1. **GitHub Actions Multi-OS CI/CD Pipeline (`.github/workflows/ci.yml`)**
   - Configured automated test & build matrix across **Ubuntu** (`ubuntu-latest`) and **Windows** (`windows-latest`) on Python 3.11 and 3.12.
   - Added automated security & secret audit step to guarantee `config/api_keys.json` and `.env` are never published.
   - Added automated Python compilation checks (`python -m compileall`) across all packages.
   - Added automated smoke tests for zero-token telemetry and weather services.
   - Added `flake8` syntax and code health validation.

2. **Git Repository Initialization & Remote Push**
   - Connected workspace to remote origin: `https://github.com/SudhirDevOps1/J.A.R.V.I.S.git`.
   - Hardened `.gitignore` to prevent secret leaks and exclude large model binaries/audio cache.
   - Added `.gitkeep` files in `core/models/piper/` and `core/assets/sfx/`.
   - Successfully committed and pushed initial `main` branch upstream.

---

## [2026-09-15 17:55] — Next-Gen Cyberpunk HUD, Free Open APIs & Voice Resilience Patch

### 🚀 Major Features & Enhancements

1. **Left Panel Dead-Space Elimination & Free Widgets (`ui.py`)**
   - Removed the vacant `lay.addStretch()` black hole below system metrics.
   - Integrated **Live Drive Storage Gauges**: Auto-detects all mounted Windows drives (C:, D:, E:) and renders color-coded progress bars (Normal < 75%, Warning 75-90%, Critical > 90%).
   - Integrated **Live Atmosphere Weather Card**: Direct Open-Meteo API connection displaying auto-detected City, Temp (°C), Sky Conditions, and Wind Speed with zero API keys and 0 LLM tokens.
   - Redesigned compact horizontal telemetry status badges (`[AI CORE: ONLINE]`, `[SEC: OK]`, `[PROTO: MK LIII]`).

2. **Quick Action Cyber Matrix (`ui.py`)**
   - Added a high-tech 4-button quick action toolbar directly on the right panel:
     - `[🔊 VOICE]`: Instantly triggers local Piper Hindi speech synthesis test without opening menus.
     - `[📷 CAM]`: Toggles live webcam feed directly on the central HUD.
     - `[⚡ PING]`: Tests latency of the active AI provider (Groq/Gemini/DeepSeek) and prints response ping into log.
     - `[🧹 CLEAR]`: One-click clears the activity log history.

3. **Free Developer Tech News Ticker (`core/system_info.py`, `ui.py`)**
   - Integrated Hacker News Firebase Top Stories API (`fetch_top_dev_news()`).
   - Cycles top tech headlines in the application footer every 20 seconds (100% Free, zero tokens).

4. **Resilient Voice Testing with Auto-Fallback (`core/tts.py`)**
   - Fixed Kokoro missing module handling: clearly reports `pip install kokoro soundfile` and auto-plays Piper Hindi speech.
   - Fixed EdgeTTS DNS/Network blocks: catches `ClientConnectorDNSError` gracefully and auto-plays Piper Hindi speech.
   - Guarantees user speakers always produce audio during testing.

### 🐛 Bug Fixes & Stability Improvements

1. **Activity Log De-Duplication & Spam Filtering (`ui.py`)**
   - Resolved repetitive sleep/idle log lines (`SYS: JARVIS online – sleeping...`) by merging consecutive identical messages into single entries with a repeat counter.
   - Added instant `clear_log()` method.

2. **Left Panel Layout Width Optimization**
   - Expanded `_LEFT_W` from 148 to 168 px to ensure all drive percentages and weather descriptions render crisply without text clipping.

---

## [2026-09-15 11:30] — Pikachu HUD Upgrade, Voice Lab, Pre-Flight Caching & Concurrency Fixes

### 🚀 Major Features & Enhancements

1. **Pikachu-Inspired PyQt6 Cyberpunk Tabbed HUD (`ui.py`)**
   - Implemented a 100% pure Python / PyQt6 multi-tab overlay (`ProviderSettingsOverlay`) matching the Pikachu Cyberpunk design without any React/Next.js/Node dependencies:
     - **Tab 1 — `[🤖 AI PROVIDERS]`**: API key management for Groq, OpenRouter, DeepSeek, Gemini, and Ollama. Includes live latency ping testing (`⚡ TEST`), real-time status badges (`🟢 Connected (142ms)`), and dynamic model dropdown population directly from provider endpoints.
     - **Tab 2 — `[🎙️ VOICE LAB]`**: Comprehensive voice management interface. Features a live `🔊 TEST VOICE (आवाज़ टेस्ट करें)` button to audition selected TTS engines with natural Hindi/English phrases. Added real-time Stark SFX preview triggers (`BOOT`, `WAKE`, `ACK`, `CONFIRM`).
     - **Tab 3 — `[📊 DISK & WEATHER]`**: Free system telemetry panel showing multi-drive storage progress bars (C:, D:, E:) and an interactive Open-Meteo weather card.

2. **Offline Voice Testing Engine (`core/tts.py`)**
   - Added `test_tts_voice(engine_name, voice_name, text)` supporting:
     - `piper_hindi`: Local Devanagari neural synthesis via ONNX.
     - `edgetts`: Cloud neural voices (`hi-IN-MadhurNeural`, `en-US-GuyNeural`, etc.).
     - `kokoro`: Local 82M ultra-fast PyTorch neural TTS.
     - `gemini_live`: Native bidirectional audio preview.

3. **Multi-Provider Health & Dynamic Model Fetcher (`core/multi_llm.py`)**
   - Implemented `test_llm_provider(provider, api_key, custom_url)` for accurate millisecond round-trip latency checks.
   - Implemented `fetch_provider_models(provider, api_key, custom_url)` to dynamically query models from Groq, OpenRouter, DeepSeek, and Ollama APIs.

4. **Zero-Token Storage & Free Weather Telemetry (`core/system_info.py`)**
   - Created `get_drive_stats()` to scan all available Windows drive partitions and report total, used, free space, and usage percentage.
   - Created `get_free_weather(city)` querying Open-Meteo REST API with zero token consumption and zero API key requirement.
   - Updated `actions/weather_report.py` and `actions/file_controller.py` to use local zero-token helpers.

5. **Zero-Touch Pre-Flight Auto-Setup (`scripts/preflight_check.py`)**
   - Built a pre-flight validator that checks Stark SFX assets, Piper Hindi TTS models, and OpenWakeWord models.
   - Verified that subsequent launches complete in `< 0.2s` using cached local assets without redundant re-downloads.

---

### 🐛 Bug Fixes & Stability Improvements

1. **Windows ONNX Runtime DLL Initialization Crash (Error 1114)**
   - *Issue*: `onnxruntime_pybind11_state.pyd` failed inside `DllMain` when imported after PyQt6 had initialized MSVC runtime hooks.
   - *Fix*: Pre-loaded `onnxruntime` at the very top of `main.py` and `ui.py` before any PyQt6 modules are imported, and set `KMP_DUPLICATE_LIB_OK="TRUE"`.

2. **Piper Hindi Audio Stuttering & Concurrency Overlap (`main.py`)**
   - *Issue*: Rapid consecutive voice responses caused overlapping worker threads to contend for the audio output device, leading to stutter and audio corruption.
   - *Fix*: Introduced a dedicated sequential thread-safe queue (`_piper_queue`) and worker loop (`_piper_worker_loop`).
   - Integrated immediate audio cancellation into `JarvisLive.interrupt()`.

3. **Clean Windows Process Termination (`main.py`)**
   - *Issue*: Background daemon threads occasionally prevented full application exit when closing the window.
   - *Fix*: Hooked PyQt6 `closeEvent` and application shutdown to safely stop all background audio queues and invoke `sys.exit(0)`.

4. **Gemini Live Deprecated Model Fallback**
   - *Issue*: Deprecated `gemini-flash-latest` model aliases caused 404/429 connection rejections.
   - *Fix*: Updated default model string to `gemini-2.5-flash` with graceful fallback handling.

---

## [2026-09-14] — Native Hindi Code-Switching & Offline TTS Integration

### 🚀 Major Features & Enhancements
1. **Bilingual Hindi & Hinglish Code-Switching (`core/prompt.txt`)**
   - Removed rigid single-language restrictions to allow natural code-switching where English technical terms (Chrome, YouTube, Restart, Volume) are smoothly blended with Hindi grammar.
2. **Offline Piper Hindi Neural TTS Engine (`core/tts.py`)**
   - Integrated `hi_IN-pratham-medium.onnx` VITS model for 100% offline, natural Indian accent speech synthesis.
   - Added Devanagari script optimization rule for authentic pronunciation.
3. **Stark Audio Effects Engine (`core/sfx.py`)**
   - Added low-latency WAV sound effects for boot, wake-word recognition, command acknowledgement, and user confirmation.
