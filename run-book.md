# 📖 J.A.R.V.I.S. RUN-BOOK — Chalao, Setup Karo, Use Karo (Codebase Analysis Se)

> Ye file actual codebase padhke banayi gayi hai — `setup.py`, `requirements.txt`,
> `run.bat` / `run.sh` / `start_jarvis.bat`, `scripts/preflight_check.py` (14 checks),
> `config/api_keys.example.json`, `main.py`, `ui.py`, `dashboard/server.py:PORT=8000`.
> Koi andaza nahi — sab verify kiya hua.

---

## 1. System Requirements

| Cheez | Chahiye |
|---|---|
| OS | Windows 10/11 (best), macOS, Linux |
| Python | **3.10+** (3.11/3.12 tested — yahan 3.12.10 chal raha hai) |
| Mic + Speaker | Voice ke liye zaroori (text-only bhi chalta hai) |
| Internet | Pehli baar setup + Gemini key ke liye; baad me partial offline |
| Disk (first run) | ~500MB–1GB (Playwright chromium+firefox, Whisper optional; Piper removed ≈60MB saved) |

Linux me native tools alag se: `pulseaudio-utils` (volume), `brightnessctl`,
`systemd`/`at` (reminder), `xdg-utils` (URL). macOS me kuch extra nahi chahiye.

---

## 2. Setup (Pehli Baar)

### Option A — 1-click (recommended)
- **Windows:** `run.bat` double-click (andar `start_jarvis.bat` chalta hai)
- **Linux/macOS:** `bash run.sh`

Ye automatically: Python dhoondta hai → `.venv` activate karta hai (ho to) →
missing packages install karta hai → preflight chalata hai → `main.py` start karta hai.

### Option B — Manual
```powershell
python setup.py                 # deps (OS-filtered) + playwright chromium+firefox
python scripts/preflight_check.py   # 14 checks, missing assets download
python main.py                  # start
```

### API Key
Pehle launch par setup screen aayegi → **free Gemini API key** dalo.
Bina key ke **Gemini Web FREE (anonymous proxy)** mode me chalta hai —
`preferred_llm_provider: gemini-web`, halki capability ke saath.
Config file: `config/api_keys.json` (example: `config/api_keys.example.json`).
⚠️ Ye file **git me kabhi mat dalo** (gitignored + CI check hai).

### Tests
```powershell
python -m pytest -q              # abhi 83 tests, sab pass hone chahiye
python -m flake8 --select E9,F63,F7,F82 actions core memory dashboard plugins tests main.py ui.py ui_icons.py
```

---

## 3. Chalane Ke Tarike

| Tarika | Command |
|---|---|
| Normal | `python main.py` |
| Windows 1-click | `run.bat` |
| Linux/macOS 1-click | `bash run.sh` |
| Silent background (Win) | `run_jarvis.pyw` (pythonw, log: `logs/jarvis_runtime.log`) |
| Global summon | **Ctrl+Space** ya Alt+J (kahin se bhi) |
| Phone se | Dashboard `http://<PC-IP>:8000` → QR scan → PIN |
| Compact Companion | `pip mode kholo` (Always-on-top Glass HUD) |

---

## 4. Kaise Use Karo (Cheat-Sheet)

### Jagna/Sona
- `Hey Jarvis` bolo (wake-word ON ho to — ⚙ → WAKE WORD se one-click download)
- Kam sunai de to `config/api_keys.json` me `"wake_threshold": 0.35` rakho (default 0.5)
- 2 min chup → auto-sleep. Sote waqt mic bahar nahi jata (local gate)

### Roz ke commands (Hindi/Hinglish/English)
```
notepad kholo / brave browser kholo / gemini kholo brave me
volume 50% / brightness badhao / wifi status
C drive me sabse bade files / desktop organize karo / undo karo
AI news batao / laptop price research karo / deep research karo AI agents
aaj mausam kaisa hai / kal maine kya kiya tha
mera naam X hai / mummy ka number yaad karo 98...
mummy ko whatsapp karo hello (Web khulega agar app nahi hai)
screenshot le / screen ka text padho / screen dekho
reminder: 10 minute me chai / roz subah 9 baje backup
macro record karo → macro stop → macro chalao demo
expander list / routine banao movie: brave, spotify / dev routine chalao
gaming profile lagao / plugin dikhao / agent mode trip plan karo
shutdown karo (HUD CONFIRM dabana padega, queue lagti hai) / undo karo
mummy ko kya pasand hai (knowledge graph) / graph stats dikhao
agar battery 20 se kam to brightness 30 (workflow) / rules dikhao
cmd se check karo disk space (run_command) / github issues dikhao owner/repo
drive me photo dhoondo / bedroom light jalao (smart home + token)
```

### ⚡ Headless Smart Services (Bina Browser Popups Ke)
Bar-bar browser khulne ki pareshani khatam! Yeh saare services background me execute hote hain aur Cyber-HUD card me live data render karte hain:

1. **Live Weather (`weather_report`)**:
   - Commands: `aaj mausam kaisa hai`, `Delhi ka weather batao`, `weather in Mumbai`
   - Flow: Open-Meteo REST API + dynamic geocoding (<1ms, 0 API key required). Live temperature, wind, humidity, weather code Cyber-HUD Atmospheric Telemetry card me render hota hai. Browser sirf tab khulta hai jab user explicitly `browser me mausam kholo` bole.

2. **Universal Drive Music Indexer & Background Audio (`youtube_video`)**:
   - Commands: `sanam teri kasam gaana chalao`, `song play karo`, `Arijit Singh track play karo`, `songs rescan karo`
   - Flow: Sabhi drives (`C:`, `D:`, `E:`) me audio files scan karke `config/music_library.json` me cache karta hai. Match milne par native `pygame.mixer` se **offline** background me play karta hai (0 network, 0 browser popups). Agar local file na mile toh minimized stream fallback chalta hai.
   - Voice Controls: `gaana pause karo`, `gaana resume karo`, `gaana stop karo`, `songs rescan karo`.
   - Video Playback: Agar user `video play karo` ya `apna college ka video lagao` bole toh visual YouTube browser window khul jayegi.

3. **Multi-Modal Transit, Train, Bus & Maps Navigation (`travel_transit`)**:
   - Commands: `Delhi se Patna train batao`, `Mumbai to Pune bus`, `Patna kaise jaye map route`, `Agra route dikhao`
   - Flow: OpenStreetMap Nominatim geocoding + OSRM routing API se real road distance (km) aur driving time calculate karta hai. **Trains** (Vande Bharat Express, Rajdhani Express, Superfast train numbers, timings, IRCTC portal), **Flights**, **Buses** (Volvo AC Sleeper, Roadways), aur **Turn-by-turn Maps** Cyber-HUD Transit Telemetry Card me render karta hai.

4. **Synchronized Assistant Persona Modes (`profile`, `persona_manager`)**:
   - Commands: `teacher mode lagao`, `study profile`, `devops mode`, `girlfriend mode`, `jarvis mode`
   - Flow: Persona badalte hi AI ka behavior, greeting, vocabulary, aur pedagogy us role ke anuroop badal jati hai. Live session automatically reconnect karta hai bina PC restart ke.

5. **eCommerce Price & Deal Comparison (`ecommerce_search`)**:
   - Commands: `laptop price flipkart amazon`, `iPhone 15 rate batao`, `amazon par boat earphones ka price`
   - Flow: Background headless extraction se Amazon India aur Flipkart dono ke price, rating, aur discount compare karke rich HUD table card me display karta hai aur cheapest deal voice se announce karta hai.

6. **Headless Flight Search (`flight_finder`)**:
   - Commands: `delhi se mumbai flight batao`, `flights to bangalore tomorrow`
   - Flow: Headless search grounding se airline schedules, departure times, aur pricing Cyber-HUD Flight Telemetry card me deta hai bina background browser open kiye.

7. **PiP Companion Mode (`pip_mode`)**:
   - Commands: `pip mode on karo`, `mini window kholo`, `pip window band karo`
   - Flow: Sleek, draggable, always-on-top transparent glass cyber companion widget with animated arc reactor, live status indicator, aur quick-access shortcuts.

### Dashboard (phone)
Same WiFi → QR → PIN → command bhejo, file upload/download karo.
Login 10/min/IP limit hai. HTTPS sirf `config/certs/` me key+crt ho to.

### Tokens (Gmail/Calendar/Drive/Notion/Slack/GitHub/Spotify)
Bina token **guided message** aayega (crash nahi). Token lagao:
- Google (Gmail/Calendar/Drive): `~/.credentials/<name>_token.json` (OAuth)
- Telegram: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`
- Slack/GitHub/Notion: env ya `api_keys.json` me `slack_bot_token` / `github_token` / `notion_token`
- Spotify: Spotipy OAuth (warna guided)

---

## 5. Architecture (1-minute me samjho)

```
Mic/Text → edge_router (Needle2 regex, ~1ms) → action_registry (39 tools)
                                                → plugin_registry (10 plugins)
                                                → Gemini Live (cloud brain)
Memory: long_term.json + journals/ + TinyDB + contacts.json + knowledge_graph.json + llm_cache.db + music_library.json
Safety: confirm.py (HUD gate, FIFO queue) + undo.py + audit.jsonl
UI: PyQt6 HUD (ui.py) + PiP Window + vector icons (ui_icons.py) + toasts/CTA/onboarding/thumbs | Phone: dashboard/server.py (:8000)
```

Naya skill = `actions/` ya `plugins/` me **1 file** (TOOL/PLUGIN dict + run()) — core edit nahi chahiye.

---

## 6. Limitations (Sach — Kya Nahi Karega)

1. **Bina token wale integrations** guided message denge (Gmail/Drive/Slack/GitHub/Notion/Spotify/Telegram-bot).
2. **Headless Flight search** search-grounding / best-effort heuristic par chalta hai — exact real-time ticketing API nahi hai.
3. **LFM offline chat** weights file hai par inference template hai — asli offline LLM ke liye Ollama chahiye.
4. **ToDo worker** steps simulate karta hai (persist real hai, execution nahi).
5. **Meeting assistant, tray icon, command-palette UI, cross-device sync, VAD bandwidth-saver, token-cost meter, sentry/face-ID, gesture control** — abhi nahi hain (roadmap).
6. **WhatsApp Web send** best-effort GUI hai — browser me verify karo.
7. **Macro replay galat window me chal sakta hai** — 3s countdown me cancel karo; replay confirm-gated hai.
8. **Voice overlap**: JARVIS bolte waqt beech me toko mat (echo-guard); pehle interrupt karo.
9. **Preflight 6–8s** leta hai (docs me `<0.2s` purana claim hai).
10. **Secrets plaintext** hain disk par (keyring layer optional) — PC shared hai to dhyan rakho.

---

## 7. Dikkat Aaye To (Troubleshooting)

| Problem | Fix |
|---|---|
| `'system' is not recognized` (purana bat) | Fixed hai — latest `start_jarvis.bat` lo |
| Mic nahi sun raha | Settings me mic **naam** se chuno; wake threshold 0.35 try karo |
| Kuch kholne par Documents khulta tha | Fixed (garbage-guard + launch-verify); `launch kro` ab poochta hai |
| `Opened X` bola par khula nahi | Ab imaandaar message aata hai; screenshot bhejo |
| Config corrupt | `config/api_keys.json.bak-TIMESTAMP` se restore karo (auto-backup banta hai) |
| Port 8000 busy | Dusra app band karo ya `dashboard/server.py` me PORT badlo |
| Playwright fail | `python -m playwright install chromium` dobara |
| Slow first run | Pehli baar ~500MB download normal hai; dobara 6–8s |

---

## 8. Safe Re-Setup (Sab Uda Ke Nayi Shuruaat)

```powershell
# Backup pehle (auto .bak banta hai, plus manual):
Copy-Item config\api_keys.json config\api_keys.manual-bak.json
Remove-Item config\installed_apps.json   # agle run par rescan (175→304 apps)
python scripts/preflight_check.py
python main.py
```

`memory/` mat udana (yaadein jayengi) — sirf rescan chahiye to HUD me `apps refresh karo` bolo.
