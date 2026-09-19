# Stark SFX Engine
import os, threading, wave, numpy as np, sounddevice as sd

SFX_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'sfx')
os.makedirs(SFX_DIR, exist_ok=True)
_CACHE = {}
_LOCK = threading.Lock()

def _save_wav(path, data, sr=44100):
    m = np.max(np.abs(data))
    norm = (data / m * 0.95) if m > 0 else data
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((norm * 32767).astype(np.int16).tobytes())

def _ensure():
    sr = 44100
    bp = os.path.join(SFX_DIR, 'boot.wav')
    if not os.path.exists(bp):
        t = np.linspace(0, 1.1, int(sr*1.1), endpoint=False)
        freq = np.linspace(90, 380, len(t))
        phase = 2 * np.pi * np.cumsum(freq) / sr
        sweep = 0.5 * np.sin(phase) + 0.3 * np.sin(2 * np.pi * 75 * t)
        chime = np.zeros_like(t)
        idx = int(0.7 * sr)
        tc = t[idx:] - 0.7
        chime[idx:] = 0.25 * np.sin(2 * np.pi * 1440 * tc) * np.exp(-12 * tc)
        _save_wav(bp, (sweep + chime) * (np.sin(np.pi * t / 1.1) ** 0.8), sr)

    wp = os.path.join(SFX_DIR, 'wake.wav')
    if not os.path.exists(wp):
        t = np.linspace(0, 0.22, int(sr * 0.22), endpoint=False)
        p1 = (t < 0.10)
        p2 = (t >= 0.10)
        w = np.zeros_like(t)
        t1, t2 = t[p1], t[p2] - 0.10
        w[p1] = 0.45 * np.sin(2 * np.pi * 880 * t1) * np.exp(-25 * t1)
        w[p2] = 0.5 * np.sin(2 * np.pi * 1760 * t2) * np.exp(-30 * t2)
        _save_wav(wp, w, sr)

    ap = os.path.join(SFX_DIR, 'ack.wav')
    if not os.path.exists(ap):
        t = np.linspace(0, 0.15, int(sr * 0.15), endpoint=False)
        _save_wav(ap, 0.4 * np.sin(2 * np.pi * 1050 * t) * np.exp(-22 * t), sr)

    cp = os.path.join(SFX_DIR, 'confirm.wav')
    if not os.path.exists(cp):
        t = np.linspace(0, 0.08, int(sr * 0.08), endpoint=False)
        _save_wav(cp, 0.5 * np.sin(2 * np.pi * 2100 * t) * np.exp(-60 * t), sr)

    # Additive (purana 4 untouched): error/success/thinking/typing synth
    ep = os.path.join(SFX_DIR, 'error.wav')
    if not os.path.exists(ep):
        t = np.linspace(0, 0.35, int(sr * 0.35), endpoint=False)
        w = 0.45 * np.sin(2 * np.pi * 220 * t) * np.exp(-8 * t)
        w += 0.3 * np.sin(2 * np.pi * 165 * t + 1.0) * np.exp(-8 * t)
        _save_wav(ep, w, sr)

    sp = os.path.join(SFX_DIR, 'success.wav')
    if not os.path.exists(sp):
        t = np.linspace(0, 0.4, int(sr * 0.4), endpoint=False)
        w = np.zeros_like(t)
        for i, f in enumerate((660.0, 880.0, 1320.0)):
            s = int(i * 0.09 * sr)
            e = min(len(t), s + int(0.18 * sr))
            tt = t[s:e] - t[s]
            w[s:e] += 0.35 * np.sin(2 * np.pi * f * tt) * np.exp(-14 * tt)
        _save_wav(sp, w, sr)

    tp = os.path.join(SFX_DIR, 'typing.wav')
    if not os.path.exists(tp):
        t = np.linspace(0, 0.06, int(sr * 0.06), endpoint=False)
        click = 0.5 * np.sin(2 * np.pi * 3200 * t) * np.exp(-90 * t)
        _save_wav(tp, click, sr)

    hp = os.path.join(SFX_DIR, 'thinking.wav')
    if not os.path.exists(hp):
        t = np.linspace(0, 1.6, int(sr * 1.6), endpoint=False)
        hum = 0.22 * np.sin(2 * np.pi * 110 * t) + 0.12 * np.sin(2 * np.pi * 220 * t)
        _save_wav(hp, hum * (0.6 + 0.4 * np.sin(2 * np.pi * 2.5 * t)), sr)

def play_sfx(name: str) -> None:
    def _run():
        try:
            from memory.config_manager import get_sfx_enabled
            if not get_sfx_enabled():
                return
        except Exception:
            pass
        p = os.path.join(SFX_DIR, f'{name}.wav')
        if not os.path.exists(p):
            _ensure()
        if not os.path.exists(p):
            return

        # On Windows, winsound provides instantaneous, zero-latency system audio
        # that bypasses PortAudio/sounddevice stream conflicts while the microphone is open.
        played = False
        if os.name == 'nt':
            try:
                import winsound
                winsound.PlaySound(p, winsound.SND_ASYNC | winsound.SND_FILENAME)
                played = True
            except Exception:
                played = False

        if not played:
            with _LOCK:
                if name in _CACHE:
                    d, sr = _CACHE[name]
                else:
                    try:
                        with wave.open(p, 'rb') as wf:
                            sr = wf.getframerate()
                            raw = wf.readframes(wf.getnframes())
                            d = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                            _CACHE[name] = (d, sr)
                    except Exception:
                        return
            try:
                sd.play(d, sr)
            except Exception:
                pass
    threading.Thread(target=_run, daemon=True).start()

_ensure()
