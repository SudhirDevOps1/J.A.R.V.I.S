"""
Text-to-Speech engines for J.A.R.V.I.S.

EdgeTTS     – free Microsoft TTS (internet required, no API key)
Kokoro      – fully offline neural TTS (~330 MB model)
ElevenLabs  – cloud API (API key required, best quality)
"""
from __future__ import annotations

import asyncio
import os
import queue as _queue
import re
import sys
import threading
import time
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

# Regex for stripping artifacts that cause robotic TTS speech
_RE_CODE_BLOCK = re.compile(r"```[\s\S]*?```")
_RE_INLINE_CODE = re.compile(r"`[^`]*`")
_RE_URL = re.compile(r"https?://\S+|www\.\S+")
_RE_MARKDOWN = re.compile(r"[*_~#>`]")
_RE_BRACKETS = re.compile(r"\[.*?\]|\(http\S+\)")
_RE_EMOJIS = re.compile(
    r"[\U00010000-\U0010ffff"
    r"\u2600-\u26ff\u2700-\u27bf"
    r"\ufe00-\ufe0f\u200d"
    r"\U0001f300-\U0001f9ff"
    r"\U0001fa00-\U0001faff]"
)


def clean_speech_text(text: str) -> str:
    """Sanitize raw LLM text for speech synthesis:
    - Strips code blocks, URLs, and markdown formatting.
    - Strips emojis and control characters that cause robotic TTS artifacts.
    - Preserves Devanagari, English, digits, and natural sentence punctuation.
    """
    if not text:
        return ""
    # Strip full code blocks
    text = _RE_CODE_BLOCK.sub(" ", text)
    # Strip inline code
    text = _RE_INLINE_CODE.sub(" ", text)
    # Strip URLs
    text = _RE_URL.sub(" ", text)
    # Strip bracketed system markers like [VISION_ACTIVE]
    text = _RE_BRACKETS.sub(" ", text)
    # Strip markdown syntax symbols
    text = _RE_MARKDOWN.sub(" ", text)
    # Strip emojis
    text = _RE_EMOJIS.sub("", text)
    # Collapse multiple spaces and dashes
    text = re.sub(r"[\t\r\n]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()




# USE_TF=0 stops transformers from importing TensorFlow (saves 4-8 s startup).
# Do NOT set USE_TORCH or USE_JAX explicitly — forcing those values breaks
# transformers' lazy-loader on certain versions, causing AutoModel and other
# classes to vanish from the public namespace.  Auto-detection is reliable.
os.environ.setdefault("USE_TF",                 "0")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# Fix Windows aiodns DNS resolution issues in aiohttp / edge_tts
try:
    import aiohttp
    import aiohttp.connector
    aiohttp.connector.DefaultResolver = aiohttp.ThreadedResolver
    _orig_tcp_init = aiohttp.TCPConnector.__init__
    def _patched_tcp_init(self, *args, **kwargs):
        if "resolver" not in kwargs or kwargs["resolver"] is None:
            kwargs["resolver"] = aiohttp.ThreadedResolver()
        _orig_tcp_init(self, *args, **kwargs)
    aiohttp.TCPConnector.__init__ = _patched_tcp_init
except Exception:
    pass


# ---------------------------------------------------------------------------
# Audio playback helpers
# ---------------------------------------------------------------------------

def _to_numpy(samples) -> np.ndarray:
    """Convert samples to float32 numpy array.

    Handles both numpy arrays and PyTorch tensors (Kokoro >= 0.9).

    PyTorch built against numpy 1.x raises RuntimeError('Numpy is not available')
    when numpy 2.x is installed.  The .tolist() fallback always works regardless
    of PyTorch / numpy version pairing.
    """
    if hasattr(samples, "detach"):                  # PyTorch tensor
        t = samples.detach().cpu().float()
        try:
            return t.numpy()                        # fast path (compatible versions)
        except RuntimeError:
            # PyTorch/numpy version mismatch — convert via Python list (always safe)
            return np.asarray(t.tolist(), dtype=np.float32)
    return np.asarray(samples, dtype=np.float32)


def _compress_silence(
    arr: np.ndarray,
    sample_rate: int    = 24_000,
    max_silence_ms: int = 500,    # cap punctuation pauses — keeps natural rhythm
    threshold: float    = 0.003,  # RMS below this = silence; lower = less clipping
) -> np.ndarray:
    """
    Shorten Kokoro's very long punctuation pauses (1-2 s → ≤500 ms).
    Conservative settings preserve natural prosody; only trims extreme pauses.
    """
    max_samp  = int(max_silence_ms * sample_rate / 1000)
    frame_len = 240                   # ~10 ms at 24 kHz
    out: list[np.ndarray] = []
    silent_acc = 0

    for i in range(0, len(arr), frame_len):
        chunk = arr[i : i + frame_len]
        if np.sqrt(np.mean(chunk ** 2) + 1e-12) < threshold:
            silent_acc += len(chunk)
            if silent_acc <= max_samp:
                out.append(chunk)
        else:
            silent_acc = 0
            out.append(chunk)

    return np.concatenate(out) if out else arr


def _play_np(samples, sample_rate: int) -> None:
    """Play float32 mono (or stereo) audio via sounddevice.
    Accepts numpy arrays or PyTorch tensors.
    """
    sd.play(_to_numpy(samples), sample_rate)
    sd.wait()


def _play_audio_bytes(audio_bytes: bytes) -> None:
    """Decode MP3/WAV/OGG bytes and play via miniaudio, pygame, soundfile, or Windows native MCI."""
    # 1. miniaudio: fast in-memory decoder, no external DLLs needed
    try:
        import miniaudio
        decoded = miniaudio.decode(
            audio_bytes,
            output_format=miniaudio.SampleFormat.FLOAT32,
            nchannels=1,
        )
        samples = np.array(decoded.samples, dtype=np.float32)
        sd.play(samples, decoded.sample_rate)
        sd.wait()
        return
    except Exception:
        pass

    # 2. pygame.mixer: if installed and available
    try:
        import io
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        bio = io.BytesIO(audio_bytes)
        pygame.mixer.music.load(bio)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(25)
        return
    except Exception:
        pass

    # 3. soundfile + sounddevice: works well for WAV/OGG
    try:
        import io
        import soundfile as sf
        bio = io.BytesIO(audio_bytes)
        data, samplerate = sf.read(bio)
        sd.play(data, samplerate)
        sd.wait()
        return
    except Exception:
        pass

    # 4. Windows native MCI (winmm.dll) fallback: zero-dependency native MP3/WAV player
    if sys.platform == "win32":
        try:
            import ctypes
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                tf.write(audio_bytes)
                temp_path = tf.name
            alias = f"jarvis_tts_{int(time.time() * 1000)}"
            mci = ctypes.windll.winmm.mciSendStringW
            mci(f'open "{temp_path}" type mpegvideo alias {alias}', None, 0, 0)
            mci(f'play {alias} wait', None, 0, 0)
            mci(f'close {alias}', None, 0, 0)
            try:
                os.remove(temp_path)
            except Exception:
                pass
            return
        except Exception as mci_err:
            print(f"[TTS] Windows native MCI fallback error: {mci_err}")

    print("[TTS] Audio playback error: No working audio backend found (miniaudio, pygame, soundfile, MCI)")



# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------

def _speak_sapi_fallback(text: str) -> bool:
    """Windows native SAPI5 / pyttsx3 offline fallback when EdgeTTS network is unreachable."""
    try:
        import win32com.client
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        speaker.Speak(text)
        return True
    except Exception:
        pass
    try:
        import pyttsx3
        eng = pyttsx3.init()
        eng.say(text)
        eng.runAndWait()
        return True
    except Exception:
        return False


class EdgeTTSEngine:
    """Microsoft EdgeTTS – free, requires internet with dynamic pitch and rate control."""

    def __init__(self, voice: str = "en-US-GuyNeural", pitch: str | None = None, rate: str | None = None):
        try:
            from memory.config_manager import get_edge_pitch, get_edge_rate
            self.pitch = pitch if pitch is not None else get_edge_pitch()
            self.rate  = rate if rate is not None else get_edge_rate()
        except Exception:
            self.pitch = pitch or "+0Hz"
            self.rate  = rate or "+0%"
        self.voice = voice

    def speak(self, text: str) -> None:
        cleaned = clean_speech_text(text)
        if not cleaned:
            return
        loop = asyncio.new_event_loop()
        audio_bytes = None
        try:
            audio_bytes = loop.run_until_complete(self._synth(cleaned))
        except Exception as e:
            print(f"[EdgeTTS] Synthesis failed ({e}). Attempting offline SAPI fallback...")
            if _speak_sapi_fallback(cleaned):
                return
            return
        finally:
            loop.close()
        if audio_bytes:
            _play_audio_bytes(audio_bytes)

    async def _synth(self, text: str) -> bytes:
        import edge_tts
        pitch_arg = self.pitch if self.pitch else "+0Hz"
        rate_arg  = self.rate if self.rate else "+0%"
        comm = edge_tts.Communicate(text, self.voice, pitch=pitch_arg, rate=rate_arg)
        buf  = bytearray()
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                buf.extend(chunk["data"])
        return bytes(buf)


# ---------------------------------------------------------------------------
# Kokoro import helper — auto-upgrades on version-mismatch errors
# ---------------------------------------------------------------------------

# Errors that indicate the installed kokoro uses old transformers classes
# (AlbertModel, AutoModel) that are no longer exported at the top level.
_KOKORO_COMPAT_ERRORS = ("AlbertModel", "AutoModel", "cannot import name")


def _import_kokoro_pipeline():
    """Import KPipeline, auto-upgrading kokoro if a version mismatch is found.

    Old kokoro (<0.9) imports AlbertModel / AutoModel from transformers.
    Newer transformers versions no longer export these at the top level,
    causing an ImportError.  kokoro>=0.9 removed these dependencies.

    When the error is detected we:
      1. Upgrade kokoro to >=0.9 via pip (silent, background)
      2. Flush stale kokoro entries from sys.modules
      3. Re-import — this time it should succeed
    """
    import sys

    def _try_import():
        from kokoro import KPipeline  # noqa: PLC0415
        return KPipeline

    try:
        return _try_import()
    except Exception as first_err:
        err_msg = str(first_err)
        if not any(marker in err_msg for marker in _KOKORO_COMPAT_ERRORS):
            # Unrelated error (kokoro not installed, etc.)
            raise RuntimeError(
                f"Kokoro import failed: {first_err}\n"
                "Run: pip install kokoro>=0.9 soundfile"
            ) from first_err

        # ── Version mismatch: upgrade kokoro silently and retry ──────────
        print("[TTS] Kokoro/transformers version mismatch detected — upgrading kokoro…")
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "kokoro>=0.9",
             "--upgrade", "--quiet", "--disable-pip-version-check"],
            capture_output=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            raise RuntimeError(
                f"Kokoro auto-upgrade failed: {stderr[:200]}\n"
                "Run manually: pip install kokoro>=0.9 soundfile"
            ) from first_err

        # Flush any stale kokoro submodules from the import cache
        stale = [k for k in sys.modules if k == "kokoro" or k.startswith("kokoro.")]
        for key in stale:
            del sys.modules[key]

        print("[TTS] Kokoro upgraded — retrying import…")
        try:
            return _try_import()
        except Exception as retry_err:
            raise RuntimeError(
                f"Kokoro still broken after upgrade: {retry_err}\n"
                "Run manually: pip install --upgrade kokoro transformers"
            ) from retry_err


# Kokoro voice prefix → KPipeline lang_code mapping
_KOKORO_LANG_CODES = {
    "a": "a",   # American English  (af_*, am_*)
    "b": "b",   # British English   (bf_*, bm_*)
    "j": "j",   # Japanese          (jf_*, jm_*)
    "z": "z",   # Mandarin Chinese  (zf_*, zm_*)
    "s": "s",   # Spanish           (sf_*, sm_*)
    "f": "f",   # French            (ff_*, fm_*)
    "h": "h",   # Hindi             (hf_*, hm_*)
    "i": "i",   # Italian           (if_*, im_*)
    "p": "p",   # Brazilian Portuguese
    "r": "r",   # Russian           (rf_*, rm_*)
    "e": "e",   # German            (ef_*, em_*)
}


class KokoroTTSEngine:
    """Fully offline Kokoro neural TTS.

    Model (~330 MB) is downloaded from HuggingFace on first use,
    then cached locally — subsequent starts load from disk.

    Warmup strategy: _init() runs synchronously in the background
    _do_tts() thread (not the UI thread).  After the pipeline loads,
    a dummy inference compiles the PyTorch JIT graph immediately so
    the first real speak() call has zero compilation overhead.
    """

    def __init__(self, voice: str = "af_heart", speed: float = 1.0):
        self.voice     = voice
        self.speed     = speed
        self._pipeline = None
        self._lock     = threading.Lock()
        self._init()   # blocking, but called from background thread

    @property
    def _lang_code(self) -> str:
        prefix = self.voice[0].lower() if self.voice else "a"
        return _KOKORO_LANG_CODES.get(prefix, "a")

    def _init(self) -> None:
        if self._pipeline is not None:
            return

        lang = self._lang_code

        # Prefer GPU — Kokoro on CUDA is ~10x faster than CPU.
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            if device == "cpu":
                import os as _os
                n_threads = max(1, min(4, (_os.cpu_count() or 4) // 2))
                try:
                    torch.set_num_threads(n_threads)
                    torch.set_num_interop_threads(2)
                except RuntimeError:
                    pass
                print(
                    f"[TTS] Kokoro on CPU — for faster speech install CUDA PyTorch:\n"
                    "      pip install torch --index-url https://download.pytorch.org/whl/cu118"
                )
        except Exception:
            device = "cpu"

        print(f"[TTS] Kokoro — loading (lang='{lang}', device='{device}')…")

        KPipeline = _import_kokoro_pipeline()

        def _create_pipeline():
            try:
                return KPipeline(lang_code=lang, device=device)
            except TypeError:
                return KPipeline(lang_code=lang)   # older build — no device param

        try:
            self._pipeline = _create_pipeline()
        except Exception as _first_err:
            # Offline flag set but model not cached yet → clear flags and download once.
            # Keywords cover multiple huggingface_hub error message variants across versions.
            _e = str(_first_err).lower()
            _offline_keywords = (
                "offline", "not found", "cache", "localentry",
                "does not exist", "outgoing", "local_files_only",
            )
            if any(k in _e for k in _offline_keywords):
                print("[TTS] Kokoro model not in local cache — downloading (one-time, internet required)…")
                os.environ.pop("HF_HUB_OFFLINE",      None)
                os.environ.pop("TRANSFORMERS_OFFLINE", None)
                os.environ.pop("HF_DATASETS_OFFLINE",  None)
                try:
                    self._pipeline = _create_pipeline()
                except Exception as _dl_err:
                    raise RuntimeError(
                        f"Kokoro model download failed.\n"
                        f"Internet access is required the first time to download the voice model (~330 MB).\n"
                        f"After the first download it runs fully offline.\n"
                        f"Tip: Switch to EdgeTTS (free, no download) in the Configure panel if offline.\n"
                        f"Details: {_dl_err}"
                    ) from _dl_err
            else:
                raise

        print("[TTS] Kokoro compiling (first-time only)…")
        # Warmup: compiles PyTorch JIT graph so first real speak() call is instant.
        try:
            for _ in self._pipeline("hello", voice=self.voice, speed=self.speed):
                pass
            print("[TTS] Kokoro ready.")
        except Exception as e:
            print(f"[TTS] Kokoro warmup warning: {e}")

    def speak(self, text: str) -> None:
        with self._lock:
            if self._pipeline is None:
                self._init()

        # ── Concurrent synthesise + playback ────────────────────────────────
        # Kokoro generates audio chunks lazily.  Without threading, we:
        #   synthesise chunk N → play N → synthesise N+1 → play N+1 …
        # With a producer/consumer pair, chunk N+1 synthesises WHILE chunk N
        # plays, cutting perceived latency by the playback duration of all but
        # the last chunk (typically 1-3 s on multi-sentence responses).
        audio_q: "_queue.Queue[np.ndarray | None]" = _queue.Queue(maxsize=4)
        synth_error: list[Exception] = []

        def _synth():
            try:
                for _, _, audio in self._pipeline(text, voice=self.voice, speed=self.speed):
                    if audio is not None:
                        arr = _to_numpy(audio)
                        arr = _compress_silence(arr)
                        if arr.size > 0:
                            audio_q.put(arr)          # blocks if player is slow (backpressure)
            except Exception as exc:
                synth_error.append(exc)
            finally:
                audio_q.put(None)                     # sentinel → player exits

        synth_thread = threading.Thread(target=_synth, daemon=True)
        synth_thread.start()

        # Player runs in this thread so sd.wait() doesn't block the synth thread.
        while True:
            arr = audio_q.get()
            if arr is None:
                break
            _play_np(arr, 24000)

        synth_thread.join()

        if synth_error:
            raise synth_error[0]


class ElevenLabsTTSEngine:
    """ElevenLabs cloud TTS – API key required."""

    def __init__(self, api_key: str, voice_id: str = "pNInz6obpgDQGcFmaJgB"):
        self.api_key  = api_key
        self.voice_id = voice_id

    def speak(self, text: str) -> None:
        import requests
        headers = {
            "xi-api-key":   self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text":     text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        resp = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}",
            json=payload, headers=headers, timeout=30,
        )
        resp.raise_for_status()
        _play_audio_bytes(resp.content)


# ---------------------------------------------------------------------------
# NOTE: PiperHindiTTSEngine REMOVED per user request (Edge TTS + Gemini Live only).
# Any stored 'piper*' engine setting auto-migrates to Edge (see
# memory/config_manager.get_tts_engine). Model files deleted from core/models/piper/.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Thread-safe player wrapper
# ---------------------------------------------------------------------------

class TTSPlayer:
    """
    Wraps any *Engine. Exposes a blocking speak() method
    meant to be called from a dedicated background thread.
    """

    def __init__(self, engine):
        self._engine  = engine
        self._playing = False
        self._lock    = threading.Lock()

    @property
    def is_playing(self) -> bool:
        return self._playing

    def speak(
        self,
        text:     str,
        on_start: Optional[Callable] = None,
        on_done:  Optional[Callable] = None,
    ) -> None:
        """Synthesise and play text. BLOCKING – call from a dedicated thread."""
        try:
            with self._lock:
                self._playing = True
            if on_start:
                on_start()
            self._engine.speak(text)
        except Exception as e:
            print(f"[TTS] Error: {e}")
        finally:
            with self._lock:
                self._playing = False
            if on_done:
                on_done()

    def stop(self) -> None:
        sd.stop()
        with self._lock:
            self._playing = False


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_tts_player(config: dict) -> TTSPlayer:
    engine_name = config.get("tts_engine", "edgetts").lower()
    if engine_name in ("piper", "piper_hindi", "piper_hi"):
        # Piper removed — migrate to Edge default voice
        engine = EdgeTTSEngine(voice=config.get("tts_voice", "en-US-GuyNeural"))
    elif engine_name == "kokoro":
        voice  = config.get("tts_voice", "af_heart")
        speed  = float(config.get("tts_speed", 1.0))
        engine = KokoroTTSEngine(voice=voice, speed=speed)
    elif engine_name == "elevenlabs":
        api_key  = config.get("elevenlabs_api_key", "")
        voice_id = config.get("tts_voice", "pNInz6obpgDQGcFmaJgB")
        engine   = ElevenLabsTTSEngine(api_key=api_key, voice_id=voice_id)
    else:   # edgetts (default)
        voice  = config.get("tts_voice", "en-US-GuyNeural")
        engine = EdgeTTSEngine(voice=voice)
    return TTSPlayer(engine)


def test_tts_voice(engine_name: str, voice_name: str = "", text: Optional[str] = None) -> tuple[bool, str]:
    """Test and preview speech synthesis for the specified engine.
    Returns (success, message). Safe to call from background worker thread.
    Piper removed — piper* requests report removed (no silent fallback).
    """
    engine_id = (engine_name or "edgetts").lower().strip()
    try:
        if engine_id in ("piper", "piper_hindi", "piper_hi"):
            return False, "Piper Hindi removed — use EdgeTTS or Gemini Live voice."

        elif engine_id in ("edgetts", "edge"):
            sample = text or "नमस्ते सुधीर सर, यह माइक्रोसॉफ्ट एज न्यूरल आवाज़ है।"
            v = voice_name or "hi-IN-SwaraNeural"
            try:
                engine = EdgeTTSEngine(voice=v)
                engine.speak(sample)
                return True, f"EdgeTTS ({v}) test passed [OK]"
            except Exception as e_net:
                return False, f"EdgeTTS Network/DNS error ({e_net}). Check internet connection."

        elif engine_id == "kokoro":
            sample = text or "Hello Sudhir Sir, this is Kokoro neural voice."
            try:
                engine = KokoroTTSEngine(voice=voice_name or "af_heart")
                engine.speak(sample)
                return True, "Kokoro offline voice test passed [OK]"
            except Exception as e_kokoro:
                return False, f"Kokoro not installed (pip install kokoro soundfile). Error: {e_kokoro}"

        elif engine_id in ("gemini_live", "gemini"):
            sample = text or "नमस्ते सुधीर सर, गूगल जेमिनी लाइव 2.5 फ्लैश वॉइस मोड तैयार है।"
            try:
                engine = EdgeTTSEngine(voice="hi-IN-MadhurNeural")
                engine.speak(sample)
                return True, "Gemini Live voice preview passed [OK]"
            except Exception as e_live:
                return False, f"Gemini Live preview failed: {e_live}"

        else:
            return False, f"Unknown voice engine: {engine_name}"

    except Exception as e:
        return False, f"Voice test error: {e}"



