"""
Speech-to-Text engines for J.A.R.V.I.S.

Whisper  – offline transcription via faster-whisper (VAD-buffered)
Vosk     – offline streaming transcription (lighter)
"""
import json
import numpy as np


class WhisperSTT:
    """Offline transcription using faster-whisper."""

    def __init__(self, model_name: str = "base", language: str | None = None):
        import os
        from faster_whisper import WhisperModel
        print(f"[STT] Loading Whisper '{model_name}'…")
        try:
            import torch
            device  = "cuda" if torch.cuda.is_available() else "cpu"
            compute = "float16" if device == "cuda" else "int8"
        except Exception:
            device, compute = "cpu", "int8"

        try:
            self._model = WhisperModel(model_name, device=device, compute_type=compute)
        except Exception as _first_err:
            # Offline flag set but model not cached yet → clear flags and download once.
            # Keywords cover multiple huggingface_hub error message variants across versions.
            _e = str(_first_err).lower()
            _offline_keywords = (
                "offline", "not found", "cache", "localentry",
                "does not exist", "outgoing", "local_files_only",
            )
            if any(k in _e for k in _offline_keywords):
                print(f"[STT] Whisper '{model_name}' not in local cache — downloading (one-time, internet required)…")
                os.environ.pop("HF_HUB_OFFLINE",      None)
                os.environ.pop("TRANSFORMERS_OFFLINE", None)
                os.environ.pop("HF_DATASETS_OFFLINE",  None)
                try:
                    self._model = WhisperModel(model_name, device=device, compute_type=compute)
                except Exception as _dl_err:
                    raise RuntimeError(
                        f"Whisper '{model_name}' model download failed.\n"
                        f"Internet access is required the first time to download the speech model (~75–290 MB).\n"
                        f"After the first download it runs fully offline.\n"
                        f"Details: {_dl_err}"
                    ) from _dl_err
            else:
                raise

        self._language = None if (not language or language.strip().lower() == "auto") else language.strip().lower()
        print(f"[STT] Whisper '{model_name}' ready ({device})")

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe a float32 mono 16 kHz numpy array. Returns transcript string."""
        try:
            segments, _ = self._model.transcribe(
                audio,
                language=self._language,
                beam_size=1,                       # greedy — 2-3x faster
                best_of=1,
                condition_on_previous_text=False,  # no hallucinations, faster
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 300},
            )
            return " ".join(s.text for s in segments).strip()
        except Exception as e:
            print(f"[STT] Transcription error: {e}")
            raise


class VoskSTT:
    """Streaming transcription using Vosk."""

    def __init__(self, model_path: str | None = None, language: str = "en-us"):
        from vosk import Model, KaldiRecognizer
        print("[STT] Loading Vosk model…")
        if model_path:
            model = Model(model_path)
        else:
            # Additive fix: vosk.Model takes a filesystem path, not lang=.
            # Purana Model(lang=) call fallback me rakha hai (hataya nahi), pehle
            # common cache paths probe karo taaki offline first-boot crash na ho.
            import os as _os
            lang = language.strip().lower() if language and language.strip().lower() != "auto" else "en-us"
            _candidates = [
                _os.path.join("core", "models", "vosk", lang),
                _os.path.join("models", "vosk", lang),
                _os.path.expanduser(f"~/.cache/vosk/{lang}"),
            ]
            _found = next((p for p in _candidates if _os.path.isdir(p)), None)
            if _found:
                model = Model(_found)
            else:
                try:
                    model = Model(lang=lang)
                except TypeError:
                    raise RuntimeError(
                        f"Vosk model folder not found. Tried: {', '.join(_candidates)}. "
                        f"Download a Vosk model (e.g. vosk-model-small-en-us-0.15) and pass model_path."
                    )
        self._rec = KaldiRecognizer(model, 16000)
        print("[STT] Vosk ready.")

    def process_chunk(self, audio_bytes: bytes) -> tuple[str, bool]:
        """Feed raw int16 LE PCM bytes. Returns (text, is_final)."""
        if self._rec.AcceptWaveform(audio_bytes):
            result = json.loads(self._rec.Result())
            return result.get("text", ""), True
        partial = json.loads(self._rec.PartialResult())
        return partial.get("partial", ""), False


# ── Additive offline fallback (purana untouched) ─────────────────────────────
# main.py Live loop se optional call: Gemini deaf ho to Whisper base/en se suno.
# Lazy import + cached singleton taaki first-boot par 75-290MB download ek baar ho.
_WHISPER_SINGLETON: dict = {}


def is_offline_stt_available() -> bool:
    """True agar faster-whisper import ho jaye (model cache check nahi, sirf pkg)."""
    try:
        import importlib.util as _u
        return _u.find_spec("faster_whisper") is not None
    except Exception:
        return False


def transcribe_fallback(audio: np.ndarray, model_name: str = "base", language: str | None = None) -> str:
    """Offline Whisper fallback. Raises nahi — fail par '' taaki caller Live par rahe."""
    try:
        key = f"{model_name}:{language or 'auto'}"
        if key not in _WHISPER_SINGLETON:
            _WHISPER_SINGLETON[key] = WhisperSTT(model_name=model_name, language=language)
        return _WHISPER_SINGLETON[key].transcribe(audio) or ""
    except Exception as e:
        print(f"[STT] Fallback unavailable: {e}")
        return ""
