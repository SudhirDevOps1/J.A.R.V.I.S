# 📝 SudhirDevOps1 AI Assistant (Mark LIII) — Changelog

All notable changes, bug fixes, enhancements, and roadmap progressions for Mark LIII are documented in this file with dates and timestamps.

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
