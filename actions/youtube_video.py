#youtube_video.py
import json
import re
import sys
import time
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from urllib.parse import quote_plus

try:
    import pyautogui
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import numpy as np
    _NUMPY = True
except ImportError:
    _NUMPY = False

try:
    import requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    _TRANSCRIPT_OK = True
except ImportError:
    _TRANSCRIPT_OK = False

try:
    import pygame
    _PYGAME_OK = True
except ImportError:
    _PYGAME_OK = False

from config import get_os, is_windows, is_mac, is_linux


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_YT_VIDEO_FILTER = "EgIQAQ%3D%3D"


def _get_api_key() -> str:
    try:
        from memory.config_manager import load_api_keys
        k = (load_api_keys().get("gemini_api_key") or "").strip()
        if k:
            return k
    except Exception:
        pass
    try:
        if API_CONFIG_PATH.exists():
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("gemini_api_key", "").strip()
    except Exception:
        pass
    return ""


def _open_url(url: str) -> None:
    try:
        if is_mac():
            subprocess.Popen(["open", url])
        elif is_linux():
            subprocess.Popen(["xdg-open", url])
        else:
            subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)
    except Exception as e:
        print(f"[YouTube] [WARN] open_url failed: {e}")


def _open_url_minimized(url: str) -> None:
    """Launch playback minimized in the background to avoid interrupting user workflow."""
    try:
        if is_mac():
            subprocess.Popen(["open", "-g", url])
        elif is_linux():
            subprocess.Popen(["xdg-open", url])
        else:
            # On Windows start /min runs the browser minimized in the background
            subprocess.Popen(["cmd", "/c", "start", "/min", "", url], shell=False)
    except Exception as e:
        print(f"[YouTube] [WARN] open_url_minimized fallback: {e}")
        _open_url(url)


def _init_mixer() -> bool:
    """Safely initialize pygame mixer for headless background audio."""
    if not _PYGAME_OK:
        return False
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        return True
    except Exception as e:
        print(f"[Audio] Mixer init note: {e}")
        return False


_MUSIC_CACHE_FILE = BASE_DIR / "config" / "music_library.json"


def _scan_music_library(force_refresh: bool = False) -> list[dict]:
    """
    Auto-discovers and indexes audio files across all PC drives (C:, D:, E:, etc. on Windows)
    and caches metadata in config/music_library.json for instant <1ms lookup.
    """
    if not force_refresh and _MUSIC_CACHE_FILE.exists():
        try:
            with open(_MUSIC_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    return data
        except Exception:
            pass

    import os
    import string
    audio_exts = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"}
    scanned_tracks: list[dict] = []
    seen_paths: set[str] = set()

    # 1. Base user directories
    scan_dirs: list[Path] = [
        Path.home() / "Music",
        Path.home() / "Downloads",
        Path.home() / "Desktop",
        Path.home() / "Documents",
        BASE_DIR / "music",
        BASE_DIR / "assets",
    ]

    # 2. Add all available Windows drive media folders or /media on Linux
    if is_windows():
        for letter in string.ascii_uppercase:
            drive = Path(f"{letter}:/")
            if drive.exists():
                for sub in ("Music", "Songs", "Media", "Downloads", "Audio"):
                    candidate = drive / sub
                    if candidate.exists() and candidate not in scan_dirs:
                        scan_dirs.append(candidate)
    elif is_linux() or is_mac():
        for extra in (Path("/media"), Path("/mnt"), Path("/Volumes")):
            if extra.exists():
                scan_dirs.append(extra)

    # 3. Traverse paths safely with depth limit & max track cap (3000 tracks)
    for s_dir in scan_dirs:
        if not s_dir.exists():
            continue
        try:
            for root, dirs, files in os.walk(str(s_dir)):
                # Skip hidden/system folders
                dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() not in ("node_modules", "appdata", "windows", "program files", "$recycle.bin")]
                for fn in files:
                    ext = os.path.splitext(fn)[1].lower()
                    if ext in audio_exts:
                        full_path = os.path.join(root, fn)
                        if full_path in seen_paths:
                            continue
                        seen_paths.add(full_path)
                        stem = os.path.splitext(fn)[0]
                        tokens = list(set(re.sub(r"[^a-zA-Z0-9\s]", " ", stem.lower()).split()))
                        scanned_tracks.append({
                            "name": fn,
                            "stem": stem,
                            "path": full_path,
                            "tokens": tokens,
                            "ext": ext,
                        })
                        if len(scanned_tracks) >= 3000:
                            break
                if len(scanned_tracks) >= 3000:
                    break
        except Exception as e:
            print(f"[Music Scanner] Note on {s_dir}: {e}")

    try:
        _MUSIC_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_MUSIC_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(scanned_tracks, f, indent=2)
        print(f"[Music Scanner] Indexed {len(scanned_tracks)} audio tracks across drives.")
    except Exception as e:
        print(f"[Music Scanner] Cache save note: {e}")

    return scanned_tracks


def _find_local_audio(query: str) -> Path | None:
    """
    Search local music library across all indexed drives for audio matching the query.
    Supports .mp3, .wav, .m4a, .flac, .ogg without opening any browser or network overhead.
    """
    clean_q = re.sub(r"[^a-zA-Z0-9\s]", " ", query.lower()).strip()
    stop_words = {"play", "chalao", "gaana", "gana", "song", "music", "audio", "track", "karo", "do", "batao", "sunao", "chalu"}
    q_words = [w for w in clean_q.split() if len(w) > 1 and w not in stop_words]
    if not q_words:
        return None

    tracks = _scan_music_library(force_refresh=False)
    best_match_path: str | None = None
    best_score = 0.0

    for track in tracks:
        stem_lower = track.get("stem", "").lower()
        track_tokens = set(track.get("tokens", []))
        # Exact token match or high-confidence word match (avoids false positives like 'lofi beats' matching 'shoorveer')
        matched = 0
        for w in q_words:
            if w in track_tokens or f" {w} " in f" {stem_lower} ":
                matched += 1
            elif len(w) >= 4 and any(w in tok and len(w) / len(tok) >= 0.7 for tok in track_tokens if len(tok) >= 4):
                matched += 1

        score = matched / len(q_words)
        if score > best_score and score >= 0.75:
            best_score = score
            best_match_path = track["path"]
            if score == 1.0:
                break

    if best_match_path and Path(best_match_path).exists():
        return Path(best_match_path)

    # Fallback to direct check on Music folder if index was empty
    music_dirs = [Path.home() / "Music", Path.home() / "Downloads"]
    for m_dir in music_dirs:
        if m_dir.exists():
            for p in m_dir.glob("*"):
                if p.is_file() and p.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg", ".flac"}:
                    p_tokens = set(re.sub(r"[^a-zA-Z0-9\s]", " ", p.stem.lower()).split())
                    if any(w in p_tokens or any(w in pt for pt in p_tokens) for w in q_words):
                        return p

    return None

def _scrape_first_video_url(query: str) -> str | None:

    if not _REQUESTS_OK:
        return None

    search_url = (
        f"https://www.youtube.com/results"
        f"?search_query={quote_plus(query)}"
        f"&sp={_YT_VIDEO_FILTER}"
    )

    try:
        r    = requests.get(search_url, headers=HEADERS, timeout=10)
        html = r.text

        video_ids = re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', html)

        seen = set()
        for vid in video_ids:
            if vid in seen:
                continue
            seen.add(vid)

            if f'/shorts/{vid}' in html:
                continue
            return f"https://www.youtube.com/watch?v={vid}"

    except Exception as e:
        print(f"[YouTube] [WARN] scrape_first_video_url failed: {e}")

    return None

def _extract_video_id(url: str) -> str | None:
    match = re.search(
        r"(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/)([A-Za-z0-9_-]{11})", url
    )
    return match.group(1) if match else None


def _is_valid_youtube_url(url: str) -> bool:
    return bool(re.search(r"(youtube\.com|youtu\.be)", url or ""))


def _ask_for_url(prompt_text: str = "YouTube video URL:") -> str | None:
    # ADDITIVE headless fast-path: Linux bina DISPLAY par tkinter hang karta hai.
    # Pehle check, dialog sirf GUI me. Purana try/except fallback untouched.
    try:
        import os as _os
        import platform as _pf
        if _pf.system() == "Linux" and not _os.environ.get("DISPLAY"):
            print("[YouTube] headless -- skipping URL dialog, URL voice/text me do.")
            return None
    except Exception:
        pass
    try:
        import tkinter as tk
        from tkinter import simpledialog

        root = tk._default_root
        if root is None:
            root = tk.Tk()
            root.withdraw()

        url = simpledialog.askstring("J.A.R.V.I.S", prompt_text, parent=root)
        return url.strip() if url else None
    except Exception as e:
        print(f"[YouTube] [WARN] URL dialog failed: {e}")
        return None


def _get_transcript(video_id: str) -> str | None:
    if not _TRANSCRIPT_OK:
        return None
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript      = None

        lang_priority = ["en", "tr", "de", "fr", "es", "it", "pt", "ru", "ja", "ko", "ar", "zh"]

        try:
            transcript = transcript_list.find_manually_created_transcript(lang_priority)
        except Exception:
            pass

        if transcript is None:
            try:
                transcript = transcript_list.find_generated_transcript(lang_priority)
            except Exception:
                for t in transcript_list:
                    transcript = t
                    break

        if transcript is None:
            return None

        fetched = transcript.fetch()
        return " ".join(entry["text"] for entry in fetched)

    except Exception as e:
        print(f"[YouTube] [WARN] Transcript fetch failed: {e}")
        return None


def _summarize_with_gemini(transcript: str, video_url: str) -> str:
    from google import genai as _genai
    from google.genai import types

    _client = _genai.Client(api_key=_get_api_key())
    max_chars = 80000
    truncated = transcript[:max_chars] + ("..." if len(transcript) > max_chars else "")
    response  = _client.models.generate_content(
        model="gemini-flash-latest",
        contents=f"Please summarize this YouTube video transcript:\n\n{truncated}",
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are JARVIS, an AI assistant. "
                "Summarize YouTube video transcripts clearly and concisely. "
                "Structure: 1-sentence overview, then 3-5 key points. "
                "Be direct. Address the user as 'sir'. "
                "Match the language of the transcript."
            )
        )
    )
    return response.text.strip()


def _save_summary(content: str, video_url: str) -> str:
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"youtube_summary_{ts}.txt"
    desktop  = Path.home() / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    filepath = desktop / filename

    header = (
        f"JARVIS — YouTube Summary\n"
        f"{'─' * 50}\n"
        f"URL    : {video_url}\n"
        f"Date   : {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"{'─' * 50}\n\n"
    )
    filepath.write_text(header + content, encoding="utf-8")

    try:
        if is_windows():
            subprocess.Popen(["notepad.exe", str(filepath)])
        elif is_mac():
            subprocess.Popen(["open", "-t", str(filepath)])
        else:
            subprocess.Popen(["xdg-open", str(filepath)])
    except Exception as e:
        print(f"[YouTube] [WARN] Could not open text editor: {e}")

    return str(filepath)


def _scrape_video_info(video_id: str) -> dict:
    if not _REQUESTS_OK:
        return {}
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        r    = requests.get(url, headers=HEADERS, timeout=12)
        html = r.text
        info = {}

        for key, pattern in [
            ("title",    r'"title":\{"runs":\[\{"text":"([^"]+)"'),
            ("channel",  r'"ownerChannelName":"([^"]+)"'),
            ("views",    r'"viewCount":"(\d+)"'),
            ("duration", r'"lengthSeconds":"(\d+)"'),
            ("likes",    r'"label":"([0-9,]+ likes)"'),
        ]:
            match = re.search(pattern, html)
            if match:
                raw = match.group(1)
                if key == "views":
                    info[key] = f"{int(raw):,}"
                elif key == "duration":
                    secs = int(raw)
                    info[key] = f"{secs // 60}:{secs % 60:02d}"
                else:
                    info[key] = raw

        return info
    except Exception as e:
        print(f"[YouTube] [WARN] Info scrape failed: {e}")
        return {}


def _scrape_trending(region: str = "TR", max_results: int = 8) -> list[dict]:
    if not _REQUESTS_OK:
        return []
    url = f"https://www.youtube.com/feed/trending?gl={region.upper()}"
    try:
        r    = requests.get(url, headers=HEADERS, timeout=12)
        html = r.text

        titles   = re.findall(r'"title":\{"runs":\[\{"text":"([^"]+)"\}\]', html)
        channels = re.findall(r'"ownerText":\{"runs":\[\{"text":"([^"]+)"', html)

        results, seen = [], set()
        for i, title in enumerate(titles):
            if title in seen or len(title) < 5:
                continue
            seen.add(title)
            channel = channels[i] if i < len(channels) else "Unknown"
            results.append({"rank": len(results) + 1, "title": title, "channel": channel})
            if len(results) >= max_results:
                break

        return results
    except Exception as e:
        print(f"[YouTube] [WARN] Trending scrape failed: {e}")
        return []

def _handle_play(parameters: dict, player) -> str:
    query = parameters.get("query", "").strip()
    if not query:
        return "Please tell me what you'd like to watch or listen to, sir."

    if player:
        player.write_log(f"[Audio/YouTube] Searching: {query}")

    explicit_video = bool(
        parameters.get("open_browser")
        or parameters.get("mode") == "video"
        or any(w in query.lower() for w in ("video", "browser", "dekho", "dikhao", "watch", "bada karo", "fullscreen", "college", "lecture", "tutorial"))
    )
    mode = str(parameters.get("mode", "") or "").lower().strip()

    if mode == "local":
        local_song = _find_local_audio(query)
        if local_song and _init_mixer():
            try:
                pygame.mixer.music.load(str(local_song))
                pygame.mixer.music.play()
                title_clean = local_song.stem
                card_lines = [
                    "╔══════════════════════════════════════════════════════════════╗",
                    "  JARVIS AUDIO CORE: LOCAL MUSIC PLAYBACK",
                    "╚══════════════════════════════════════════════════════════════╝",
                    "",
                    f"  TRACK        : {local_song.name}",
                    f"  DIRECTORY    : {local_song.parent}",
                    f"  AUDIO ENGINE : Pygame Hi-Fi Mixer (Offline)",
                    f"  PLAYBACK     : Background Active (0 Browser Overhead)",
                    "",
                    "  [Say 'pause music', 'resume music', or 'stop music' to control]",
                ]
                if player and hasattr(player, "show_content"):
                    player.show_content("LOCAL AUDIO PLAYER", "\n".join(card_lines))
                return f"Playing {title_clean} from your local music library, sir."
            except Exception as e:
                print(f"[Audio] Local playback note: {e}")
        return f"Local file for '{query}' was not found in your indexed music library, sir. You can say 'online chalao' to stream."

    # 1. Local Music Scan (Headless, 0 network overhead, 0 browser) unless video requested
    if not explicit_video and mode != "online":
        local_song = _find_local_audio(query)
        if local_song and _init_mixer():
            try:
                pygame.mixer.music.load(str(local_song))
                pygame.mixer.music.play()
                title_clean = local_song.stem
                card_lines = [
                    "╔══════════════════════════════════════════════════════════════╗",
                    "  JARVIS AUDIO CORE: LOCAL MUSIC PLAYBACK",
                    "╚══════════════════════════════════════════════════════════════╝",
                    "",
                    f"  TRACK        : {local_song.name}",
                    f"  DIRECTORY    : {local_song.parent}",
                    f"  AUDIO ENGINE : Pygame Hi-Fi Mixer (Offline)",
                    f"  PLAYBACK     : Background Active (0 Browser Overhead)",
                    "",
                    "  [Say 'pause music', 'resume music', or 'stop music' to control]",
                ]
                if player and hasattr(player, "show_content"):
                    player.show_content("LOCAL AUDIO PLAYER", "\n".join(card_lines))
                return f"Playing {title_clean} from your local music library, sir."
            except Exception as e:
                print(f"[Audio] Local playback note: {e}")

    # 2. Online Streaming (YouTube)
    print(f"[YouTube] [SEARCH] Scraping first non-Shorts video for: {query}")
    video_url = _scrape_first_video_url(query)

    if video_url:
        if explicit_video:
            print(f"[YouTube] [PLAY] Opening browser: {video_url}")
            _open_url(video_url)
            card_lines = [
                "╔══════════════════════════════════════════════════════════════╗",
                "  JARVIS VISUAL STREAM: YOUTUBE BROWSER",
                "╚══════════════════════════════════════════════════════════════╝",
                "",
                f"  QUERY        : {query}",
                f"  TARGET URL   : {video_url}",
                f"  STATUS       : Browser Tab Active",
            ]
            if player and hasattr(player, "show_content"):
                player.show_content("YOUTUBE VIDEO", "\n".join(card_lines))
            return f"Playing {query} video in browser, sir."
        else:
            print(f"[YouTube] [PLAY] Headless background launch: {video_url}")
            _open_url_minimized(video_url)
            card_lines = [
                "╔══════════════════════════════════════════════════════════════╗",
                "  JARVIS AUDIO CORE: HEADLESS AUDIO STREAM",
                "╚══════════════════════════════════════════════════════════════╝",
                "",
                f"  STREAM TITLE : {query}",
                f"  STREAM URL   : {video_url}",
                f"  PLAYBACK     : Minimized Background (Zero Distraction)",
                f"  STATUS       : Audio Active (0 Screen Interruption)",
                "",
                "  [Say 'pause music' or 'stop music' to control]",
            ]
            if player and hasattr(player, "show_content"):
                player.show_content("HEADLESS AUDIO STREAM", "\n".join(card_lines))
            return f"Playing {query} in the background, sir."

    print(f"[YouTube] [WARN] Scrape failed, opening filtered search page")
    fallback_url = (
        f"https://www.youtube.com/results"
        f"?search_query={quote_plus(query)}"
        f"&sp={_YT_VIDEO_FILTER}"
    )
    if explicit_video:
        _open_url(fallback_url)
    else:
        _open_url_minimized(fallback_url)
    return f"Opened YouTube search for: {query}"


def _handle_pause(parameters: dict, player=None, speak=None) -> str:
    if _PYGAME_OK and pygame.mixer.get_init() and pygame.mixer.music.get_busy():
        try:
            pygame.mixer.music.pause()
        except Exception:
            pass
    if _PYAUTOGUI:
        try:
            pyautogui.press("playpause")
        except Exception:
            pass
    return "Music playback paused, sir."


def _handle_resume(parameters: dict, player=None, speak=None) -> str:
    if _PYGAME_OK and pygame.mixer.get_init():
        try:
            pygame.mixer.music.unpause()
        except Exception:
            pass
    if _PYAUTOGUI:
        try:
            pyautogui.press("playpause")
        except Exception:
            pass
    return "Music playback resumed, sir."


def _handle_stop(parameters: dict, player=None, speak=None) -> str:
    if _PYGAME_OK and pygame.mixer.get_init():
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
    if _PYAUTOGUI:
        try:
            pyautogui.press("stop")
        except Exception:
            pass
    return "Music playback stopped, sir."


def _handle_summarize(parameters: dict, player, speak) -> str:
    if not _TRANSCRIPT_OK:
        return "youtube-transcript-api is not installed. Run: pip install youtube-transcript-api"

    # FIX (additive): parameters["url"] first, dialog sirf fallback (purana flow hataya nahi)
    url = str((parameters or {}).get("url", "") or "").strip()
    if not url:
        url = _ask_for_url("Please paste the YouTube video URL:")
    if not url:
        return "No URL provided, sir. Summary cancelled."
    if not _is_valid_youtube_url(url):
        return "That doesn't appear to be a valid YouTube URL, sir."

    video_id = _extract_video_id(url)
    if not video_id:
        return "Could not extract video ID from that URL, sir."

    if player:
        player.write_log(f"[YouTube] Summarizing: {url}")
    if speak:
        speak("Fetching the transcript now, sir. One moment.")

    transcript = _get_transcript(video_id)
    if not transcript:
        return "I couldn't retrieve a transcript for that video, sir."

    if speak:
        speak("Transcript retrieved. Generating summary now.")

    try:
        summary = _summarize_with_gemini(transcript, url)
    except Exception as e:
        return f"Summary generation failed, sir: {e}"

    if speak:
        speak(summary)

    if parameters.get("save", False):
        saved_path = _save_summary(summary, url)
        return f"Summary complete and saved to Desktop: {saved_path}"

    return summary


def _handle_get_info(parameters: dict, player, speak) -> str:
    url = parameters.get("url", "").strip()
    if not url:
        url = _ask_for_url("Please paste the YouTube video URL:")
    if not url or not _is_valid_youtube_url(url):
        return "Please provide a valid YouTube URL, sir."

    video_id = _extract_video_id(url)
    if not video_id:
        return "Could not extract video ID, sir."

    if player:
        player.write_log(f"[YouTube] Getting info: {url}")

    info = _scrape_video_info(video_id)
    if not info:
        return "Could not retrieve video information, sir."

    lines = [
        f"{key.capitalize()}: {info[key]}"
        for key in ("title", "channel", "views", "duration", "likes")
        if key in info
    ]
    result = "\n".join(lines)

    if speak:
        speak(f"Here's the video info, sir. {result.replace(chr(10), '. ')}")

    return result


def _handle_trending(parameters: dict, player, speak) -> str:
    region = parameters.get("region", "TR").upper()

    if player:
        player.write_log(f"[YouTube] Trending: {region}")

    trending = _scrape_trending(region=region, max_results=8)
    if not trending:
        return f"Could not fetch trending videos for region {region}, sir."

    lines  = [f"Top trending videos in {region}:"]
    lines += [f"{v['rank']}. {v['title']} — {v['channel']}" for v in trending]
    result = "\n".join(lines)

    if speak:
        top3   = trending[:3]
        spoken = "Here are the top trending videos, sir. " + ". ".join(
            f"Number {v['rank']}: {v['title']} by {v['channel']}" for v in top3
        )
        speak(spoken)

    return result

def _handle_rescan(parameters: dict, player=None, speak=None) -> str:
    tracks = _scan_music_library(force_refresh=True)
    msg = f"Music library refreshed across all drives: {len(tracks)} audio files indexed."
    if player and hasattr(player, "write_log"):
        player.write_log(f"[Music] {msg}")
    return msg


_ACTION_MAP = {
    "play":      _handle_play,
    "summarize": _handle_summarize,
    "get_info":  _handle_get_info,
    "trending":  _handle_trending,
    "pause":     _handle_pause,
    "resume":    _handle_resume,
    "unpause":   _handle_resume,
    "stop":      _handle_stop,
    "rescan":    _handle_rescan,
    "refresh":   _handle_rescan,
}


def youtube_video(
    parameters:     dict,
    response=None,
    player=None,
    session_memory=None,
    speak=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "play").lower().strip()

    if player:
        player.write_log(f"[YouTube] Action: {action}")
    print(f"[YouTube] Action: {action} Params: {params}")

    handler = _ACTION_MAP.get(action)
    if handler is None:
        return (
            f"Unknown YouTube action: '{action}'. "
            "Available: play, pause, resume, stop, summarize, get_info, trending."
        )

    try:
        if action == "play":
            return handler(params, player) or "Done."
        return handler(params, player, speak) or "Done."
    except Exception as e:
        print(f"[YouTube] [ERROR] Error in {action}: {e}")
        return f"YouTube {action} failed, sir: {e}"


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "youtube_video",
    "description": "Controls audio and YouTube media. Use for: playing local audio or streaming music/videos, pause, resume, stop playback, summarizing video content, getting video info, or showing trending videos.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "play | pause | resume | stop | summarize | get_info | trending (default: play)"
            },
            "query": {
                "type": "STRING",
                "description": "Search query for play action"
            },
            "save": {
                "type": "BOOLEAN",
                "description": "Save summary to Notepad (summarize only)"
            },
            "region": {
                "type": "STRING",
                "description": "Country code for trending e.g. TR, US"
            },
            "url": {
                "type": "STRING",
                "description": "Video URL for get_info action"
            }
        },
        "required": []
    },
    "handler": youtube_video,
}
