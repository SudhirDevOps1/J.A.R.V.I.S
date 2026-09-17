# 📝 SudhirDevOps1 AI Assistant (J.A.R.V.I.S.) — Changelog

All notable changes, bug fixes, enhancements, and roadmap progressions for J.A.R.V.I.S. are documented in this file with dates and timestamps.

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
