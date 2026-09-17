from __future__ import annotations

import json
import math
import os
os.environ["QT_LOGGING_RULES"] = "qt.text.font.db=false;qt.qpa.mime=false;qt.qpa.clipboard=false;qt.pointer.dispatch=false"
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Pre-load onnxruntime before Qt loads its C++ runtime
try:
    import onnxruntime as _ort  # noqa: F401
except Exception:
    pass

import platform
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

if platform.system() == "Windows":
    _WIN_HIDE: dict = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    _WIN_HIDE: dict = {}

from PyQt6.QtCore import (
    QEasingCurve, QMimeData, QObject, QParallelAnimationGroup, QPointF,
    QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer, QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QConicalGradient, QDragEnterEvent, QDropEvent, QFont,
    QFontDatabase, QKeySequence, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QRadialGradient, QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy, QSlider, QSplitter,
    QStackedWidget, QTabWidget, QTextEdit, QVBoxLayout, QWidget, QProgressBar,
)

# ── Application Identity & Protocol ──────────────────────────────────────────
# Dynamic application identity and protocol derivation managed centrally
# via config_manager.
from memory.config_manager import (
    get_app_name, get_protocol_name,
    get_avatar_mode, save_avatar_mode,
    get_particle_density, save_particle_density,
    get_hud_fx, save_hud_fx,
    get_sfx_enabled, save_sfx_enabled,
    get_tts_engine, save_tts_engine,
    get_anim_mode, save_anim_mode,
    get_hud_glow, save_hud_glow,
    get_persona_mode, save_persona_mode,
    get_assistant_gender, save_assistant_gender,
    get_edge_voice, save_edge_voice,
    get_edge_pitch, save_edge_pitch,
    get_obsidian_config, save_obsidian_config,
    get_preferred_language, save_preferred_language,
)
APP_VERSION  = get_app_name()
APP_PROTOCOL = get_protocol_name()

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"


def _read_full_config() -> dict:
    """Read api_keys.json config dict. Returns {} on any error."""
    try:
        return json.loads(API_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


_DEFAULT_W, _DEFAULT_H = 980, 700
_MIN_W,     _MIN_H     = 820, 580
_LEFT_W  = 168
_RIGHT_W = 340

_OS = platform.system()  # "Windows" | "Darwin" | "Linux"


class C:
    BG        = "#00060a"
    PANEL     = "#010d14"
    PANEL2    = "#010f18"
    BORDER    = "#0d3347"
    BORDER_B  = "#1a5c7a"
    BORDER_A  = "#0f4060"
    PRI       = "#00d4ff"
    PRI_DIM   = "#007a99"
    PRI_GHO   = "#001f2e"
    ACC       = "#ff6b00"
    ACC2      = "#ffcc00"
    GREEN     = "#00ff88"
    GREEN_D   = "#00aa55"
    RED       = "#ff3355"
    MUTED_C   = "#ff3366"
    TEXT      = "#8ffcff"
    TEXT_DIM  = "#3a8a9a"
    TEXT_MED  = "#5ab8cc"
    WHITE     = "#d8f8ff"
    DARK      = "#000d14"
    BAR_BG    = "#011520"


# Keys tied to the accent colour — status colours (ACC, GREEN, RED…) stay fixed
_HUE_LINKED = (
    "BG", "PANEL", "PANEL2", "BORDER", "BORDER_B", "BORDER_A",
    "PRI", "PRI_DIM", "PRI_GHO", "TEXT", "TEXT_DIM", "TEXT_MED",
    "WHITE", "DARK", "BAR_BG",
)
_PALETTE_DEFAULTS: dict[str, str] = {k: getattr(C, k) for k in _HUE_LINKED}

DEFAULT_UI_COLOR = _PALETTE_DEFAULTS["PRI"]


def apply_ui_accent(accent_hex: str) -> bool:
    """
    Re-derives the whole teal-family palette from the chosen accent colour
    (hue shift — brightness/saturation ratios are preserved, design stays intact).
    Painted elements (HUD, waveform, metrics) pick up the new colour on the next
    frame; stylesheet-based panels pick it up when they are rebuilt.
    """
    import colorsys

    accent_hex = (accent_hex or "").strip().lower()
    if not (accent_hex.startswith("#") and len(accent_hex) == 7):
        return False
    try:
        int(accent_hex[1:], 16)
    except ValueError:
        return False

    def _hsv(h: str) -> tuple[float, float, float]:
        r = int(h[1:3], 16) / 255
        g = int(h[3:5], 16) / 255
        b = int(h[5:7], 16) / 255
        return colorsys.rgb_to_hsv(r, g, b)

    base_h            = _hsv(_PALETTE_DEFAULTS["PRI"])[0]
    acc_h, acc_s, _av = _hsv(accent_hex)
    dh   = acc_h - base_h
    grey = acc_s < 0.08   # near-grey accent → the whole theme is desaturated

    for key, hex0 in _PALETTE_DEFAULTS.items():
        h, s, v = _hsv(hex0)
        if grey:
            s *= 0.15
        r, g, b = colorsys.hsv_to_rgb((h + dh) % 1.0, s, v)
        setattr(C, key, "#{:02x}{:02x}{:02x}".format(
            int(r * 255 + 0.5), int(g * 255 + 0.5), int(b * 255 + 0.5)))
    return True


def current_palette() -> dict[str, str]:
    """A snapshot of the accent-linked colours currently on class C."""
    return {k: getattr(C, k) for k in _HUE_LINKED}


def retheme_all_widgets(old: dict[str, str], new: dict[str, str]) -> None:
    """
    LIVE full theme change. Replaces the old palette colours with the new ones
    in EVERY widget's stylesheet across the app and repaints them. This way the
    colour change applies INSTANTLY across the whole interface — panels, buttons,
    borders included — not just the painted elements. No restart needed.
    """
    mapping = {old[k].lower(): new[k].lower()
               for k in old if old[k].lower() != new.get(k, old[k]).lower()}
    if not mapping:
        return
    app = QApplication.instance()
    if app is None:
        return
    for w in app.allWidgets():
        try:
            ss = w.styleSheet()
            if ss:
                s2 = ss
                for o, n in mapping.items():
                    if o in s2:
                        s2 = s2.replace(o, n)
                if s2 != ss:
                    w.setStyleSheet(s2)
            w.update()
        except Exception:
            pass


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h)
    c.setAlpha(max(0, min(255, int(a))))
    return c


# ── Windows GPU via NVML DLL (no subprocess, no console window) ──────────────
_nvml_lib: object = None   # cached ctypes DLL
_nvml_ok:  object = None   # None=untested, True=works, False=unavailable


def _nvml_gpu_windows() -> float:
    """Return NVIDIA GPU utilisation % using nvml.dll directly — zero subprocess."""
    global _nvml_lib, _nvml_ok
    if _nvml_ok is False:
        return -1.0
    try:
        import ctypes

        class _Util(ctypes.Structure):
            _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

        if _nvml_lib is None:
            for dll_name in ("nvml", r"C:\Windows\System32\nvml.dll"):
                try:
                    lib = ctypes.WinDLL(dll_name)
                    lib.nvmlInit_v2()
                    _nvml_lib = lib
                    break
                except Exception:
                    continue

        if _nvml_lib is None:
            import pynvml  # type: ignore
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            _nvml_ok = True
            return float(pynvml.nvmlDeviceGetUtilizationRates(h).gpu)

        dev = ctypes.c_void_p()
        _nvml_lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev))
        util = _Util()
        _nvml_lib.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(util))
        _nvml_ok = True
        return float(util.gpu)
    except Exception:
        _nvml_ok = False
        return -1.0


class _SysMetrics:
    def __init__(self):
        self.cpu  = 0.0
        self.mem  = 0.0
        self.net  = 0.0   
        self.gpu  = -1.0  
        self.tmp  = -1.0  
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        # Probe caches — GPU (NVML) and temperature (WMI) are the expensive
        # queries; initialise their handles once and reuse them instead of
        # rebuilding a connection on every poll.
        self._slow_tick = 0            # gpu/temp refreshed every 3rd cycle
        self._pynvml    = None         # cached pynvml module + device handle
        self._pynvml_h  = None
        self._pynvml_ok = None         # None=untested, False=unavailable here
        self._nv_unix   = None         # cached (lib, dev) for Linux/macOS NVML
        self._wmi_conn  = None         # cached WMI connection (creating one is slow)
        self._wmi_ok    = None         # None=untested, False=unavailable here
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(2.0)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent

        nc  = psutil.net_io_counters()
        now = time.time()
        dt  = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net  = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net   = nc
        self._last_net_t = now

        # GPU and temperature change slowly and are the most expensive probes
        # (NVML / WMI) — refresh them every 3rd cycle (~6 s) instead of every
        # cycle, reusing the previous reading in between.
        self._slow_tick = (self._slow_tick + 1) % 3
        if self._slow_tick == 1:
            gpu = self._get_gpu()
            tmp = self._get_temp()
        else:
            gpu = self.gpu
            tmp = self.tmp

        with self._lock:
            self.cpu = cpu
            self.mem = mem
            self.net = net
            self.gpu = gpu
            self.tmp = tmp

    def _get_gpu(self) -> float:
        # pynvml — subprocess-free; initialise once and reuse the handle.
        # Re-initialising NVML on every poll is slow, so cache it and stop
        # retrying pynvml entirely once it proves unavailable here.
        if self._pynvml_ok is not False:
            try:
                if self._pynvml_h is None:
                    import pynvml  # type: ignore
                    pynvml.nvmlInit()
                    self._pynvml    = pynvml
                    self._pynvml_h  = pynvml.nvmlDeviceGetHandleByIndex(0)
                    self._pynvml_ok = True
                return float(self._pynvml.nvmlDeviceGetUtilizationRates(self._pynvml_h).gpu)
            except Exception:
                self._pynvml_ok = False

        # Windows: nvml.dll via ctypes (already cached in _nvml_gpu_windows)
        if _OS == "Windows":
            return _nvml_gpu_windows()

        # Linux / macOS: libnvidia-ml shared lib via ctypes — init once, reuse
        try:
            import ctypes

            class _Util(ctypes.Structure):
                _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

            if self._nv_unix is None:
                _lib = "libnvidia-ml.so.1" if _OS == "Linux" else "libnvidia-ml.dylib"
                nv = ctypes.CDLL(_lib)
                nv.nvmlInit_v2()
                dev = ctypes.c_void_p()
                nv.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev))
                self._nv_unix = (nv, dev)

            nv, dev = self._nv_unix
            u = _Util()
            nv.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(u))
            return float(u.gpu)
        except Exception:
            pass

        return -1.0   # N/A — zero subprocess on all platforms

    def _get_temp(self) -> float:
        # psutil — works on Linux; occasionally Windows with driver support
        try:
            temps = psutil.sensors_temperatures()
            for name in ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                         "cpu-thermal", "zenpower", "it8688"]:
                if name in temps and temps[name]:
                    return temps[name][0].current
            for entries in temps.values():
                if entries:
                    return entries[0].current
        except Exception:
            pass

        # Windows: wmi module (pure Python COM, zero subprocess). Reuse a single
        # connection — building a fresh wmi.WMI() on every poll spins up a COM
        # connection each time and is very slow. Give up after one failure.
        if _OS == "Windows" and self._wmi_ok is not False:
            try:
                if self._wmi_conn is None:
                    import wmi  # type: ignore
                    self._wmi_conn = wmi.WMI(namespace="root/wmi")
                tz = self._wmi_conn.MSAcpi_ThermalZoneTemperature()
                if tz:
                    return (tz[0].CurrentTemperature / 10.0) - 273.15
            except Exception:
                self._wmi_ok   = False
                self._wmi_conn = None

        return -1.0   # N/A — zero subprocess on all platforms

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "cpu": self.cpu,
                "mem": self.mem,
                "net": self.net,
                "gpu": self.gpu,
                "tmp": self.tmp,
            }


_metrics = _SysMetrics()

class HudCanvas(QWidget):
    """
    Celestial AI Avatar HUD with 3D Swirling Planetary Orbital Halo Ring,
    Cosmic Stardust Particle Cloud, Fiber-Optic Neural Filaments, and Live Voice Reactivity.
    """

    def __init__(self, face_path: str, assistant_name: str = "J.A.R.V.I.S", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted = False
        self.speaking = False
        self.state = "INITIALISING"
        self._assistant_name = assistant_name
        self._face_path = face_path

        self._tick = 0
        self._paint_tick = 0
        self._last_t = time.time()

        # ── Visual Customization & Multi-Mode HUD ─────────────────────────────
        self._avatar_mode = get_avatar_mode()
        self._particle_density = get_particle_density()
        self._hud_fx = get_hud_fx()
        self._anim_mode = get_anim_mode()
        self._hud_glow = get_hud_glow()

        # Real-Time Emotional State & Expression Engine
        self._expression = ""
        self._expr_timer = QTimer(self)
        self._expr_timer.setSingleShot(True)
        self._expr_timer.timeout.connect(self._clear_expression)

        # Multi-mode state trackers
        self._reactor_outer_ang = 0.0
        self._reactor_inner_ang = 0.0
        self._orb_ang_x = 0.0
        self._orb_ang_y = 0.0
        self._orb_ang_z = 0.0

        # Quantum Arc Reactor Particle Embers & Holographic Scanline
        self._reactor_embers: list[dict] = []
        for _ in range(54):
            self._reactor_embers.append({
                "r": random.uniform(10, 160),
                "ang": random.uniform(0, math.pi * 2),
                "spd": random.uniform(0.6, 2.2),
                "sz": random.uniform(1.2, 3.4),
                "life": random.uniform(0.1, 1.0),
                "fade": random.uniform(0.010, 0.022),
            })
        self._scanline_y = 0.0
        self._halo_angle = 0.0                      # Main orbital rotation angle in degrees
        self._halo_tilt = math.radians(16.0)        # Perspective tilt angle (~16°)
        self._halo = 60.0                           # Base glow intensity
        self._scale = 1.0                           # Organic breathing scale
        self._base_scale = 1.0
        self._tgt_scale = 1.0

        # Orbiting photons travelling along the tilted 3D elliptical halo
        self._photons: list[dict] = []
        for i in range(42):
            base_ang = (i / 42.0) * math.pi * 2 + random.uniform(-0.05, 0.05)
            self._photons.append({
                "angle": base_ang,
                "rad_jit": random.uniform(-5.0, 5.0),
                "spd": random.uniform(0.85, 1.25),
                "sz": random.uniform(1.2, 3.4),
                "alpha": random.uniform(180, 255),
                "strand": random.choice([0, 1, 2]),
            })

        # Cosmic Stardust Swarm
        self._stardust: list[dict] = []
        self._init_stardust()

        # Matrix Rain Streams
        self._matrix_cols: list[dict] = []
        self._init_matrix()

        # ── Vocal Shockwaves ──────────────────────────────────────────────────
        self._shockwaves: list[dict] = []

        # ── Image Caching & Soft Vignetting ───────────────────────────────────
        self._face_px: QPixmap | None = None
        self._face_cache: QPixmap | None = None
        self._face_cache_sz = (-1, -1)
        self._face_aspect = 0.62
        self._load_face(face_path)

        # ── Audio Reactivity ──────────────────────────────────────────────────
        self._live_amp = 0.0
        self._amp_disp = 0.0

        # ── Blinking / Status Animation ───────────────────────────────────────
        self._blink = True
        self._blink_tick = 0

        # Background Grid Layer Cache
        self._grid_cache: QPixmap | None = None
        self._grid_key = None

        # 60 FPS Animation Timer
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def _init_stardust(self):
        """Initialize stardust particles based on configured density."""
        self._stardust = []
        count = getattr(self, "_particle_density", 200)
        for _ in range(count):
            ny = random.uniform(-0.85, 0.85)
            max_w = 0.38 if ny < -0.2 else (0.50 if ny < 0.2 else 0.82)
            nx = random.gauss(0, max_w * 0.42)
            nx = max(-max_w, min(max_w, nx))
            self._stardust.append({
                "x": nx,
                "y": ny,
                "sz": random.uniform(1.1, 2.6),
                "phase": random.uniform(0, math.pi * 2),
                "spd": random.uniform(0.65, 1.45),
                "col": random.choice(["gold", "amber", "white", "cyan"]),
                "base_a": random.uniform(110, 220),
                "dx": 0.0,
                "dy": 0.0,
            })

    def _init_matrix(self):
        """Initialize digital rain columns for Cyber Matrix mode."""
        self._matrix_cols = []
        chars = "0123456789ABCDEFJARVISSTARK"
        for i in range(40):
            self._matrix_cols.append({
                "col_x": i / 40.0,
                "y": random.uniform(-0.6, 1.0),
                "spd": random.uniform(0.006, 0.020),
                "length": random.randint(8, 18),
                "chars": [random.choice(chars) for _ in range(20)],
            })

    def set_avatar_mode(self, mode: str) -> None:
        """Switch active avatar mode ('celestial', 'reactor', 'orb', 'matrix')."""
        m = (mode or "celestial").lower().strip()
        if m in ("celestial", "reactor", "orb", "matrix"):
            self._avatar_mode = m
            self.update()

    def set_particle_density(self, count: int) -> None:
        """Update particle density in real time."""
        self._particle_density = max(50, min(350, int(count)))
        self._init_stardust()
        self.update()

    def set_hud_fx(self, fx: dict) -> None:
        """Update HUD visual effects in real time."""
        if isinstance(fx, dict):
            self._hud_fx.update(fx)
            self.update()

    def set_anim_mode(self, mode: str) -> None:
        """Update animation dynamics mode ('reactive', 'subtle', 'kinetic')."""
        m = (mode or "reactive").lower().strip()
        if m in ("reactive", "subtle", "kinetic"):
            self._anim_mode = m
            self.update()

    def set_hud_glow(self, glow: int) -> None:
        """Update HUD glow bloom intensity (10..100)."""
        self._hud_glow = max(10, min(100, int(glow)))
        self.update()

    def set_expression(self, expr_name: str, duration_sec: float = 6.0) -> None:
        """Trigger an emotional visual reaction on the avatar HUD."""
        self._expression = (expr_name or "").upper().strip()
        if self._expression:
            self._expr_timer.stop()
            self._expr_timer.start(int(duration_sec * 1000))
        self.update()

    def _clear_expression(self) -> None:
        self._expression = ""
        self.update()

    def set_audio_level(self, level: float) -> None:
        """Thread-safe entry point for audio amplitude from mic/TTS."""
        try:
            lv = float(level)
        except (TypeError, ValueError):
            return
        lv = max(0.0, min(1.0, lv))
        if lv > self._live_amp:
            self._live_amp = lv

    def _load_face(self, path: str):
        """Load avatar portrait with smooth feathered vignette dissolving into void."""
        try:
            from PIL import Image, ImageDraw, ImageFilter
            import io

            p = Path(path)
            if not p.exists():
                alt = BASE_DIR / "core" / "assets" / "avatar" / "celestial_avatar.jpg"
                if alt.exists():
                    p = alt
                elif (BASE_DIR / "face.png").exists():
                    p = BASE_DIR / "face.png"

            if not p.exists():
                self._face_px = None
                return

            img = Image.open(p).convert("RGBA")
            w, h = img.size

            # Create soft vignette mask
            mk = Image.new("L", (w, h), 255)
            d = ImageDraw.Draw(mk)

            fade_x = int(w * 0.10)
            fade_y_bot = int(h * 0.18)
            fade_y_top = int(h * 0.06)

            for i in range(fade_x):
                alpha = int(255 * (i / max(1, fade_x)))
                d.line([(i, 0), (i, h)], fill=alpha)
                d.line([(w - 1 - i, 0), (w - 1 - i, h)], fill=alpha)

            for j in range(fade_y_bot):
                alpha = int(255 * (j / max(1, fade_y_bot)))
                for x_idx in range(w):
                    cur = mk.getpixel((x_idx, h - 1 - j))
                    mk.putpixel((x_idx, h - 1 - j), min(cur, alpha))

            for k in range(fade_y_top):
                alpha = int(255 * (k / max(1, fade_y_top)))
                for x_idx in range(w):
                    cur = mk.getpixel((x_idx, k))
                    mk.putpixel((x_idx, k), min(cur, alpha))

            mk = mk.filter(ImageFilter.GaussianBlur(radius=6))
            img.putalpha(mk)

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap()
            px.loadFromData(buf.getvalue())
            self._face_px = px
            self._face_aspect = w / max(1, h)
        except Exception as e:
            print(f"[HUD] Avatar load error: {e}")
            self._face_px = None

        self._face_cache = None
        self._face_cache_sz = (-1, -1)

    def _make_grid(self, W: int, H: int) -> QPixmap:
        """Pre-render static celestial stardust grid points for background depth."""
        pm = QPixmap(max(1, W), max(1, H))
        pm.fill(Qt.GlobalColor.transparent)
        gp = QPainter(pm)
        gp.setPen(QPen(qcol(C.PRI_GHO), 1))
        for x in range(0, W, 48):
            for y in range(0, H, 48):
                gp.drawPoint(x, y)
        gp.end()
        return pm

    def _step(self):
        self._tick += 1

        # Audio smoothing
        self._live_amp *= 0.86
        self._amp_disp += (self._live_amp - self._amp_disp) * 0.45
        amp = self._amp_disp

        # Check if the assistant is actively interacting (speaking, listening to user audio, or thinking)
        is_active = (
            self.speaking or
            (self.state == "LISTENING" and amp > 0.025) or
            (self.state in ("THINKING", "PROCESSING"))
        )

        anim_mode = getattr(self, "_anim_mode", "reactive")

        # Organic breathing scale and rotation dynamics based on mode and activity
        if anim_mode == "reactive":
            if is_active:
                self._scale = 1.0 + math.sin(self._tick * 0.04) * 0.015 + amp * 0.04
                if self.speaking:
                    rot_spd = 1.8 + amp * 5.2
                elif self.state == "LISTENING":
                    rot_spd = 1.2 + amp * 3.6
                else:
                    rot_spd = 3.2
            else:
                # Calm resting standby — zero jitter or unwanted spinning
                self._scale = 1.0
                rot_spd = 0.0
        elif anim_mode == "subtle":
            # Peaceful, very slow ambient breathing
            self._scale = 1.0 + math.sin(self._tick * 0.02) * 0.008 + (amp * 0.03 if is_active else 0.0)
            rot_spd = (1.5 + amp * 4.0) if is_active else 0.22
        else:  # kinetic
            self._scale = 1.0 + math.sin(self._tick * 0.035) * 0.012 + amp * 0.03
            rot_spd = (1.8 + amp * 5.2) if is_active else 0.75

        # ── Advance Celestial Halo ────────────────────────────────────────────
        if rot_spd > 0.001:
            self._halo_angle = (self._halo_angle + rot_spd) % 360.0
            for ph in self._photons:
                ph["angle"] = (ph["angle"] + math.radians(rot_spd * ph["spd"])) % (math.pi * 2)

        # ── Advance Stark Arc Reactor & Embers ───────────────────────────────
        reactor_spd = max(0.28 if anim_mode != "kinetic" else 0.65, rot_spd)
        self._reactor_outer_ang = (self._reactor_outer_ang + reactor_spd * 0.75) % 360.0
        self._reactor_inner_ang = (self._reactor_inner_ang - reactor_spd * 1.35) % 360.0

        # Animate outward drifting quantum fusion embers
        ember_boost = (1.0 + amp * 3.5) if is_active else 0.85
        for em in getattr(self, "_reactor_embers", []):
            em["r"] += em["spd"] * ember_boost
            em["ang"] += 0.008
            em["life"] -= em.get("fade", 0.015)
            if em["life"] <= 0.0 or em["r"] > 240:
                em["r"] = random.uniform(8, 30)
                em["ang"] = random.uniform(0, math.pi * 2)
                em["life"] = random.uniform(0.7, 1.0)
                em["spd"] = random.uniform(0.6, 2.2)

        # Animate holographic scanline sweep
        self._scanline_y = (self._scanline_y + 1.8) % max(400, self.height())

        # ── Advance Quantum Plasma Orb ────────────────────────────────────────
        orb_drift = max(0.20 if anim_mode != "kinetic" else 0.60, rot_spd)
        self._orb_ang_x = (self._orb_ang_x + 0.45 * orb_drift + amp * 2.8) % 360.0
        self._orb_ang_y = (self._orb_ang_y + 0.65 * orb_drift + amp * 3.4) % 360.0
        self._orb_ang_z = (self._orb_ang_z + 0.30 * orb_drift + amp * 1.8) % 360.0

        # ── Advance Cyber Matrix Rain ─────────────────────────────────────────
        matrix_mult = (1.0 + amp * 2.5) if is_active else 0.30
        for mc in getattr(self, "_matrix_cols", []):
            mc["y"] += mc["spd"] * matrix_mult
            if mc["y"] > 1.3:
                mc["y"] = -0.3
                if random.random() < 0.35:
                    chars = "0123456789ABCDEFJARVISSTARK"
                    mc["chars"] = [random.choice(chars) for _ in range(20)]

        # Update stardust particles only when active or in kinetic mode
        if is_active or anim_mode == "kinetic":
            for p in self._stardust:
                p["phase"] += 0.045 * p["spd"]
                p["y"] -= 0.0012 * p["spd"]
                p["x"] += math.sin(p["phase"] * 0.8) * 0.0006

                if amp > 0.07:
                    dist = math.hypot(p["x"], p["y"]) + 0.001
                    p["dx"] += (p["x"] / dist) * amp * 0.006
                    p["dy"] += (p["y"] / dist) * amp * 0.006

                p["dx"] *= 0.88
                p["dy"] *= 0.88

                if p["y"] < -0.92:
                    p["y"] = 0.90
                    max_w = 0.80
                    p["x"] = random.gauss(0, max_w * 0.42)

        # Trigger energy shockwaves on vocal onset bursts (only if enabled AND active)
        if self._hud_fx.get("shockwaves", True) and is_active:
            if (self.speaking or (self.state == "LISTENING" and amp > 0.15)) and amp > 0.16 and random.random() < 0.22:
                self._shockwaves.append({
                    "r": 12.0,
                    "max_r": 180.0 + amp * 120.0,
                    "alpha": 220,
                    "spd": 4.5 + amp * 6.5,
                })

        active_sw = []
        for sw in self._shockwaves:
            sw["r"] += sw["spd"]
            sw["alpha"] = max(0, int(sw["alpha"] * 0.93 - 2))
            if sw["r"] < sw["max_r"] and sw["alpha"] > 5:
                active_sw.append(sw)
        self._shockwaves = active_sw

        # Blinking logic for status
        self._blink_tick += 1
        if self._blink_tick >= 38:
            self._blink = not self._blink
            self._blink_tick = 0
            _blinked = True
        else:
            _blinked = False

        # Repaint throttling
        self._paint_tick = (self._paint_tick + 1) % 3
        if is_active or _blinked or (anim_mode != "reactive" and self._paint_tick == 0):
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        W, H = self.width(), self.height()
        cx, cy = W / 2.0, H / 2.0
        fw = min(W, H)
        amp = self._amp_disp

        is_active = (
            self.speaking or
            (self.state == "LISTENING" and amp > 0.025) or
            (self.state in ("THINKING", "PROCESSING"))
        )
        anim_mode = getattr(self, "_anim_mode", "reactive")
        glow_mult = getattr(self, "_hud_glow", 60) / 60.0

        # Fill deep space void
        p.fillRect(self.rect(), qcol(C.BG))

        # Ambient starlight grid (if starfield enabled)
        if self._hud_fx.get("starfield", True):
            _gkey = (W, H, C.PRI_GHO)
            if self._grid_cache is None or self._grid_key != _gkey:
                self._grid_cache = self._make_grid(W, H)
                self._grid_key = _gkey
            p.drawPixmap(0, 0, self._grid_cache)

        # ── Determine Color Palette Based on State & Expression ───────────────
        expr_info = None
        if getattr(self, "_expression", ""):
            try:
                from core.expression_engine import get_expression_details
                expr_info = get_expression_details(self._expression)
            except Exception:
                expr_info = None

        if expr_info:
            primary_c = QColor(expr_info["primary"])
            sec_c     = QColor(expr_info["secondary"])
            bloom_c   = QColor(expr_info["bloom"])
            white_c   = QColor(255, 255, 255)
            status_txt = expr_info["label"]
            status_col = QColor(expr_info["primary"])
        elif self.speaking:
            primary_c = QColor(255, 204, 51)     # Solar gold
            sec_c     = QColor(255, 153, 0)      # Amber flare
            white_c   = QColor(255, 255, 255)
            bloom_c   = QColor(255, 170, 0)
            status_txt, status_col = "●  SPEAKING", qcol(C.ACC)
        elif self.state == "LISTENING":
            primary_c = QColor(0, 255, 187)      # Radiant emerald
            sec_c     = QColor(0, 229, 255)      # Starlight cyan
            white_c   = QColor(255, 255, 255)
            bloom_c   = QColor(0, 230, 200)
            status_txt, status_col = ("●  LISTENING" if self._blink else "○  LISTENING"), qcol(C.GREEN)
        elif self.state in ("THINKING", "PROCESSING"):
            primary_c = QColor(0, 212, 255)      # Hyper cyan
            sec_c     = QColor(179, 102, 255)    # Quantum violet
            white_c   = QColor(255, 255, 255)
            bloom_c   = QColor(0, 191, 255)
            sym = "◈" if self._blink else "◇"
            status_txt, status_col = f"{sym}  {self.state}", qcol(C.ACC2)
        elif self.muted:
            primary_c = QColor(255, 68, 68)      # Ember crimson
            sec_c     = QColor(153, 34, 34)
            white_c   = QColor(255, 200, 200)
            bloom_c   = QColor(255, 50, 50)
            status_txt, status_col = "⊘  MUTED", qcol(C.MUTED_C)
        else:
            primary_c = QColor(255, 204, 68)     # Celestial Gold
            sec_c     = QColor(255, 170, 34)     # Warm amber
            white_c   = QColor(255, 255, 255)
            bloom_c   = QColor(255, 180, 50)
            status_txt, status_col = ("●  READY" if self._blink else "○  READY"), qcol(C.PRI)

        mode = getattr(self, "_avatar_mode", "celestial")

        # ── MODE RENDERING ────────────────────────────────────────────────────
        if mode == "reactor":
            # ══════════════════════════════════════════════════════════════════
            # MODE: STARK ARC REACTOR (Mechanical Concentric Rings & Core)
            # ══════════════════════════════════════════════════════════════════
            R = fw * 0.36

            # 1. Ambient Magnetic Flux Glow (Soft Radial Halo Behind Reactor)
            halo_grad = QRadialGradient(cx, cy, R * 1.15)
            halo_grad.setColorAt(0.0, QColor(bloom_c.red(), bloom_c.green(), bloom_c.blue(), int(38 * glow_mult + amp * 55)))
            halo_grad.setColorAt(0.65, QColor(primary_c.red(), primary_c.green(), primary_c.blue(), int(16 * glow_mult + amp * 25)))
            halo_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(halo_grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx, cy), R * 1.15, R * 1.15)

            # 2. Outer Titanium Bezel & Concentric Precision Rails
            p.setPen(QPen(qcol(C.PRI_DIM, int(130 * glow_mult)), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), R, R)
            p.drawEllipse(QPointF(cx, cy), R * 0.91, R * 0.91)
            p.drawEllipse(QPointF(cx, cy), R * 0.85, R * 0.85)

            # 3. 360-Degree High-Precision Ticks (Major 30° notches, Minor 10° ticks)
            for deg in range(0, 360, 10):
                rad = math.radians(deg)
                is_major = (deg % 30 == 0)
                t_len = 10 if is_major else 4
                pen_w = 2.0 if is_major else 1.0
                p.setPen(QPen(primary_c if is_major else sec_c, pen_w))
                x1 = cx + math.cos(rad) * (R - t_len)
                y1 = cy + math.sin(rad) * (R - t_len)
                x2 = cx + math.cos(rad) * R
                y2 = cy + math.sin(rad) * R
                p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

            # 4. Outward Drifting Quantum Fusion Embers / Sparks
            for em in getattr(self, "_reactor_embers", []):
                er = em.get("r", 20)
                e_ang = em.get("ang", 0.0)
                ex = cx + math.cos(e_ang) * er
                ey = cy + math.sin(e_ang) * er
                e_alpha = int(255 * em.get("life", 1.0) * glow_mult)
                if e_alpha > 5:
                    p.setBrush(QBrush(QColor(bloom_c.red(), bloom_c.green(), bloom_c.blue(), e_alpha)))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(QPointF(ex, ey), em.get("sz", 2.0), em.get("sz", 2.0))

            # 5. 12 Transformer Electromagnetic Copper-Gold Coils (Matching Icon)
            coil_r = R * 0.72
            for i in range(12):
                coil_ang = i * 30 + self._reactor_outer_ang
                th = math.radians(coil_ang)
                ccx = cx + math.cos(th) * coil_r
                ccy = cy + math.sin(th) * coil_r

                p.save()
                p.translate(ccx, ccy)
                p.rotate(coil_ang + 90)

                # Coil core obsidian block
                p.setBrush(QBrush(QColor(14, 18, 24, 235)))
                p.setPen(QPen(primary_c, 1.2))
                p.drawRoundedRect(QRectF(-8, -14, 16, 28), 2.5, 2.5)

                # Copper wire wraps
                p.setPen(QPen(QColor(225, 140, 35, int(220 * glow_mult)), 1.5))
                for gy in [-9, -5, -1, 3, 7]:
                    p.drawLine(-6, gy, 6, gy)

                # Glowing center filament
                fil_alpha = max(80, min(255, int((150 + amp * 90) * glow_mult)))
                p.setPen(QPen(QColor(bloom_c.red(), bloom_c.green(), bloom_c.blue(), fil_alpha), 1.6))
                p.drawLine(0, -11, 0, 11)

                p.restore()

            # 6. Counter-Rotating Slotted Energy Arc Rails
            inner_ring_r = R * 0.52
            p.setPen(QPen(primary_c, 3.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for a_idx in range(6):
                start_a = int((self._reactor_inner_ang + a_idx * 60) * 16)
                p.drawArc(QRectF(cx - inner_ring_r, cy - inner_ring_r, inner_ring_r * 2, inner_ring_r * 2),
                          start_a, 44 * 16)

            # 7. 6 Inward Magnetic Focus Compression Vanes
            vane_r_out = R * 0.48
            vane_r_in = R * 0.34
            for vi in range(6):
                v_ang = math.radians(vi * 60 + self._reactor_inner_ang * 0.8)
                vx_out = cx + math.cos(v_ang) * vane_r_out
                vy_out = cy + math.sin(v_ang) * vane_r_out
                vx_in = cx + math.cos(v_ang) * vane_r_in
                vy_in = cy + math.sin(v_ang) * vane_r_in
                p.setPen(QPen(sec_c, 2.2))
                p.drawLine(QPointF(vx_out, vy_out), QPointF(vx_in, vy_in))
                p.setBrush(QBrush(white_c))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(vx_in, vy_in), 2.2, 2.2)

            # 8. Central Quantum Fusion Reaction Chamber
            idle_pulse = math.sin(self._tick * 0.055) * (R * 0.018)
            core_r = R * 0.29 + (amp * (R * 0.24) if is_active else idle_pulse)
            grad = QRadialGradient(cx, cy, core_r)
            grad.setColorAt(0.0, QColor(255, 255, 255, 255))
            grad.setColorAt(0.28, QColor(bloom_c.red(), bloom_c.green(), bloom_c.blue(), max(0, min(255, int((210 + amp * 45) * glow_mult)))))
            grad.setColorAt(0.65, QColor(primary_c.red(), primary_c.green(), primary_c.blue(), max(0, min(255, int((130 + amp * 60) * glow_mult)))))
            grad.setColorAt(1.0, QColor(sec_c.red(), sec_c.green(), sec_c.blue(), 0))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx, cy), core_r, core_r)

            # 9. 3D Rotating Geometric Core Matrix (Icosahedron / Octahedron)
            hex_pts = []
            hex_r = core_r * 0.58
            for h_i in range(6):
                h_rad = math.radians(h_i * 60 + self._reactor_outer_ang * 0.6)
                hex_pts.append(QPointF(cx + math.cos(h_rad) * hex_r, cy + math.sin(h_rad) * hex_r))
            p.setPen(QPen(white_c, 1.6))
            for h_i in range(6):
                p.drawLine(hex_pts[h_i], hex_pts[(h_i + 1) % 6])
                p.drawLine(QPointF(cx, cy), hex_pts[h_i])

            # Inner Tri-axial Cross
            cross_r = core_r * 0.32
            for c_i in range(3):
                c_rad = math.radians(c_i * 120 + self._reactor_inner_ang * 0.5)
                px1 = cx + math.cos(c_rad) * cross_r
                py1 = cy + math.sin(c_rad) * cross_r
                px2 = cx - math.cos(c_rad) * cross_r
                py2 = cy - math.sin(c_rad) * cross_r
                p.setPen(QPen(sec_c, 1.2))
                p.drawLine(QPointF(px1, py1), QPointF(px2, py2))

            # 10. Optical Lens Cross Flare (4-Point Radiant Spike from Core)
            flare_len = core_r * (1.3 + amp * 0.9 + math.sin(self._tick * 0.08) * 0.12)
            flare_col = QColor(255, 255, 255, int(180 * glow_mult))
            p.setPen(QPen(flare_col, 1.8))
            p.drawLine(QPointF(cx - flare_len, cy), QPointF(cx + flare_len, cy))
            p.drawLine(QPointF(cx, cy - flare_len), QPointF(cx, cy + flare_len))

            # 11. Subtle Holographic Scanline Pass
            sc_y = getattr(self, "_scanline_y", 0.0)
            p.setPen(QPen(QColor(bloom_c.red(), bloom_c.green(), bloom_c.blue(), 35), 1.2))
            p.drawLine(QPointF(cx - R * 1.05, sc_y), QPointF(cx + R * 1.05, sc_y))

        elif mode == "orb":
            # ══════════════════════════════════════════════════════════════════
            # MODE: QUANTUM PLASMA ORB (3D Gyroscopic Rings & Energy Sphere)
            # ══════════════════════════════════════════════════════════════════
            orb_r = fw * 0.32

            # 3D Gyro Orbital Rings with perspective depth
            ring_confs = [
                (orb_r * 0.95, 0.42, self._orb_ang_x, primary_c),
                (orb_r * 0.82, 0.65, self._orb_ang_y, sec_c),
                (orb_r * 0.70, 0.35, self._orb_ang_z, bloom_c),
            ]

            for r_rad, tilt_factor, rot_deg, col in ring_confs:
                p.save()
                p.translate(cx, cy)
                p.rotate(rot_deg)
                p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), max(0, min(255, int((140 + amp * 70) * glow_mult)))), 2.0))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QPointF(0, 0), r_rad, r_rad * tilt_factor)

                # Orbiting quantum node on ring
                node_rad = math.radians(rot_deg * 2.2)
                nx = math.cos(node_rad) * r_rad
                ny = math.sin(node_rad) * (r_rad * tilt_factor)
                p.setBrush(QBrush(white_c))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(nx, ny), 3.2 + amp * 2.5, 3.2 + amp * 2.5)
                p.restore()

            # Central Pulsing Plasma Sphere
            orb_idle_pulse = math.sin(self._tick * 0.04) * (orb_r * 0.018)
            core_r = orb_r * 0.40 + (amp * (orb_r * 0.28) if is_active else orb_idle_pulse)
            grad = QRadialGradient(cx, cy, core_r)
            grad.setColorAt(0.0, QColor(255, 255, 255, 255))
            grad.setColorAt(0.3, QColor(bloom_c.red(), bloom_c.green(), bloom_c.blue(), max(0, min(255, int((190 + amp * 45) * glow_mult)))))
            grad.setColorAt(0.7, QColor(primary_c.red(), primary_c.green(), primary_c.blue(), max(0, min(255, int((110 + amp * 60) * glow_mult)))))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx, cy), core_r, core_r)

            # Electrical discharge arcs on voice burst
            if is_active and amp > 0.08:
                p.setPen(QPen(white_c, 1.2))
                for _ in range(3):
                    ang_arc = random.uniform(0, math.pi * 2)
                    d_len = core_r + random.uniform(10, 38)
                    mid_x = cx + math.cos(ang_arc) * (core_r + 8) + random.uniform(-5, 5)
                    mid_y = cy + math.sin(ang_arc) * (core_r + 8) + random.uniform(-5, 5)
                    end_x = cx + math.cos(ang_arc) * d_len
                    end_y = cy + math.sin(ang_arc) * d_len
                    p.drawLine(QPointF(cx, cy), QPointF(mid_x, mid_y))
                    p.drawLine(QPointF(mid_x, mid_y), QPointF(end_x, end_y))

        elif mode == "matrix":
            # ══════════════════════════════════════════════════════════════════
            # MODE: CYBER MATRIX RAIN & HOLOGRAPHIC GRID
            # ══════════════════════════════════════════════════════════════════
            p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            for mc in getattr(self, "_matrix_cols", []):
                col_x = mc["col_x"] * W
                y_base = mc["y"] * H
                for ci, ch in enumerate(mc["chars"][:mc["length"]]):
                    py = y_base + ci * 14
                    if -10 <= py <= H + 10:
                        if ci == 0:
                            p.setPen(QPen(white_c, 1))
                        else:
                            alpha = max(10, min(240, int(200 * (1.0 - ci / mc["length"]) * glow_mult)))
                            p.setPen(QPen(QColor(primary_c.red(), primary_c.green(), primary_c.blue(), alpha), 1))
                        p.drawText(QPointF(col_x, py), ch)

            # Center Hologram Cyber Shield & Ring
            hex_r = fw * 0.22 + (amp * 20.0 if is_active else 0.0)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(primary_c, 1.5))
            hex_pts = []
            for h_i in range(6):
                h_rad = math.radians(h_i * 60 + self._tick * 0.8)
                hex_pts.append(QPointF(cx + math.cos(h_rad) * hex_r, cy + math.sin(h_rad) * hex_r))
            for h_i in range(6):
                p.drawLine(hex_pts[h_i], hex_pts[(h_i + 1) % 6])

            # Center Oscilloscope Circle
            p.setPen(QPen(QColor(white_c.red(), white_c.green(), white_c.blue(), int((140 + amp * 90) * glow_mult)), 1.5))
            p.drawEllipse(QPointF(cx, cy), hex_r * 0.55 + amp * 18.0, hex_r * 0.55 + amp * 18.0)

        else:
            # ══════════════════════════════════════════════════════════════════
            # MODE: CELESTIAL AVATAR (Harmonized, Clean & Beautiful)
            # ══════════════════════════════════════════════════════════════════
            av_h = min(int(H * 0.76), int(W * 1.32))
            av_w = int(av_h * getattr(self, "_face_aspect", 0.62))
            av_x = int(cx - av_w / 2.0)
            av_y = int(cy - av_h * 0.50)

            head_cx = cx
            head_cy = av_y + av_h * 0.355

            r_x = av_w * 0.72 + (amp * 38.0 if is_active else 0.0)
            r_y = r_x * math.sin(self._halo_tilt) * 1.15

            # Ambient halo aura behind head
            aura_r = av_w * 0.55 + (amp * 30.0 if is_active else 0.0)
            aura_grad = QRadialGradient(head_cx, head_cy, aura_r)
            if is_active:
                aura_grad.setColorAt(0.0, QColor(bloom_c.red(), bloom_c.green(), bloom_c.blue(), int((55 + amp * 90) * glow_mult)))
                aura_grad.setColorAt(0.5, QColor(sec_c.red(), sec_c.green(), sec_c.blue(), int((28 + amp * 40) * glow_mult)))
            else:
                # Dignified, calm resting aura
                aura_grad.setColorAt(0.0, QColor(bloom_c.red(), bloom_c.green(), bloom_c.blue(), int(25 * glow_mult)))
                aura_grad.setColorAt(0.5, QColor(sec_c.red(), sec_c.green(), sec_c.blue(), int(10 * glow_mult)))
            aura_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(QBrush(aura_grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(head_cx, head_cy), aura_r, aura_r)

            # Draw Avatar Pixmap (feathered silhouette)
            if self._face_px:
                q_sz = (max(1, (av_w // 4) * 4), max(1, (av_h // 4) * 4))
                if self._face_cache is None or self._face_cache_sz != q_sz:
                    self._face_cache = self._face_px.scaled(
                        q_sz[0], q_sz[1],
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self._face_cache_sz = q_sz
                scaled = self._face_cache
                draw_w = int(scaled.width() * self._scale)
                draw_h = int(scaled.height() * self._scale)
                dx = int(head_cx - draw_w / 2.0)
                dy = int(av_y + (av_h - draw_h) / 2.0)
                p.drawPixmap(dx, dy, draw_w, draw_h, scaled)
            else:
                orb_r = int(fw * 0.26 * self._scale)
                for i in range(8, 0, -1):
                    r2 = int(orb_r * i / 8)
                    frc = i / 8.0
                    a = max(0, min(255, int(self._halo * 1.2 * frc * glow_mult)))
                    p.setBrush(QBrush(QColor(primary_c.red(), primary_c.green(), primary_c.blue(), a)))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.drawEllipse(QRectF(cx - r2, cy - r2, r2 * 2, r2 * 2))

            # Orbiting Stardust Photons along the outer halo path (only when active or in kinetic mode)
            if self._hud_fx.get("photons", True) and (is_active or anim_mode == "kinetic"):
                halo_rot_rad = math.radians(self._halo_angle)
                for ph in self._photons:
                    ang = (ph["angle"] + halo_rot_rad) % (math.pi * 2)
                    px = head_cx + (r_x + ph["rad_jit"]) * math.cos(ang)
                    py = head_cy - (r_y + ph["rad_jit"] * 0.28) * math.sin(ang)

                    if abs(px - head_cx) > av_w * 0.28 or py < head_cy - av_h * 0.12 or py > head_cy + av_h * 0.18:
                        alpha = max(0, min(255, int(ph["alpha"] * (0.75 + amp * 0.40) * glow_mult)))
                        sz = ph["sz"] * (1.1 + amp * 0.4)
                        p.setBrush(QBrush(QColor(255, 235, 175, alpha)))
                        p.setPen(Qt.PenStyle.NoPen)
                        p.drawEllipse(QPointF(px, py), sz, sz)

        # ── GLOBAL FX: Shockwaves (if enabled AND actively speaking/bursting) ─
        if self._hud_fx.get("shockwaves", True) and is_active:
            for sw in self._shockwaves:
                col_sw = QColor(bloom_c.red(), bloom_c.green(), bloom_c.blue(), int(sw["alpha"] * glow_mult))
                p.setPen(QPen(col_sw, 1.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                rx_sw = sw["r"]
                ry_sw = sw["r"] * math.sin(self._halo_tilt) * 1.15
                p.drawEllipse(QRectF(cx - rx_sw, cy - ry_sw, rx_sw * 2.0, ry_sw * 2.0))

        # ── GLOBAL FX: Floating Stardust Particle Swarm (if enabled) ──────────
        if self._hud_fx.get("particles", True) and (is_active or anim_mode != "reactive"):
            for s in self._stardust:
                px = cx + (s["x"] + s["dx"]) * (fw * 0.52)
                py = cy + (s["y"] + s["dy"]) * (fw * 0.48)
                twinkle = 0.65 + 0.35 * math.sin(self._tick * 0.08 + s["phase"])
                cur_a = max(0, min(255, int(s["base_a"] * twinkle * (0.80 + amp * 0.35) * glow_mult)))
                if s["col"] == "white":
                    pt_col = QColor(255, 255, 255, cur_a)
                elif s["col"] == "cyan":
                    pt_col = QColor(0, 229, 255, cur_a)
                elif s["col"] == "amber":
                    pt_col = QColor(255, 170, 0, cur_a)
                else:
                    pt_col = QColor(255, 204, 51, cur_a)

                p.setBrush(QBrush(pt_col))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(px, py), s["sz"], s["sz"])

        # ── GLOBAL FX: Retro CRT Scanlines (if enabled) ───────────────────────
        if self._hud_fx.get("scanlines", False):
            p.setPen(QPen(qcol(C.PRI_GHO, int(36 * glow_mult)), 1))
            for sl_y in range(0, H, 3):
                p.drawLine(0, sl_y, W, sl_y)

        # ── HUD Frame, Status Indicators & Voice Waveform ─────────────────────
        if self._hud_fx.get("brackets", True):
            bl = 22
            bc = qcol(C.PRI, int(180 * glow_mult))
            hl, hr = cx - fw // 2 + 12, cx + fw // 2 - 12
            ht, hb = cy - fw // 2 + 12, cy + fw // 2 - 12
            p.setPen(QPen(bc, 1.5))
            for bx, by, dx, dy in [(hl, ht, 1, 1), (hr, ht, -1, 1), (hl, hb, 1, -1), (hr, hb, -1, -1)]:
                p.drawLine(QPointF(bx, by), QPointF(bx + dx * bl, by))
                p.drawLine(QPointF(bx, by), QPointF(bx, by + dy * bl))

        # Status text below avatar (with expressive mood badge when emotional state active)
        sy = cy + fw * 0.38
        if expr_info:
            p.save()
            bw_w = 260
            badge_r = QRectF(cx - bw_w / 2.0, sy - 2, bw_w, 24)
            p.setPen(QPen(QColor(expr_info["primary"]), 1))
            p.setBrush(QBrush(QColor(0, 10, 16, 215)))
            p.drawRoundedRect(badge_r, 4, 4)
            p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            p.setPen(QPen(QColor(expr_info["primary"]), 1))
            p.drawText(badge_r, Qt.AlignmentFlag.AlignCenter, status_txt)
            p.restore()
        else:
            p.setPen(QPen(status_col, 1))
            p.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
            p.drawText(QRectF(0, sy, W, 22), Qt.AlignmentFlag.AlignCenter, status_txt)

        # Center-weighted voice spectrum equalizer (if enabled)
        if self._hud_fx.get("spectrum", True):
            wy = sy + 24
            N, bw = 36, 7
            wx0 = (W - N * bw) / 2.0
            mid = (N - 1) / 2.0
            for i in range(N):
                if self.muted:
                    hgt, cl = 2, qcol(C.MUTED_C)
                elif not is_active and anim_mode == "reactive":
                    hgt, cl = 2, qcol(C.BORDER_B, 110) # clean, calm resting standby line
                else:
                    env = (1.0 - abs(i - mid) / mid) ** 0.65
                    shimmer = 0.55 + 0.45 * math.sin(self._tick * 0.18 + i * 0.7)
                    idle = 2.5 + 1.5 * math.sin(self._tick * 0.09 + i * 0.6)
                    hgt = int(max(2, min(26, idle + amp * 25.0 * env * shimmer)))
                    if amp > 0.05:
                        cl = qcol(C.PRI) if hgt > 12 else qcol(C.PRI_DIM)
                    else:
                        cl = qcol(C.BORDER_B)
                p.fillRect(QRectF(wx0 + i * bw, wy + 20 - hgt, bw - 1, hgt), cl)

        p.end()   # end deterministically so the backing store never flushes an active painter

class MetricBar(QWidget):

    def __init__(self, label: str, color: str = C.PRI, parent=None):
        super().__init__(parent)
        self._label = label
        self._color = color
        self._value = 0.0       # 0–100
        self._text  = "--"
        self.setFixedHeight(38)
        self.setMinimumWidth(80)

    def set_value(self, pct: float, text: str):
        v = max(0.0, min(100.0, pct))
        if v == self._value and text == self._text:
            return          # unchanged — skip the repaint
        self._value = v
        self._text  = text
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.setBrush(QBrush(qcol(C.PANEL2)))
        p.setPen(QPen(qcol(C.BORDER_A), 1))
        p.drawRoundedRect(QRectF(1, 1, W - 2, H - 2), 4, 4)

        bar_h   = 4
        bar_y   = H - bar_h - 5
        bar_w   = W - 12
        bar_x   = 6
        fill_w  = int(bar_w * self._value / 100)

        p.setBrush(QBrush(qcol(C.BAR_BG)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2, 2)

        if self._value > 85:
            bar_col = qcol(C.RED)
        elif self._value > 65:
            bar_col = qcol(C.ACC)
        else:
            bar_col = qcol(self._color)

        if fill_w > 0:
            p.setBrush(QBrush(bar_col))
            p.drawRoundedRect(QRectF(bar_x, bar_y, fill_w, bar_h), 2, 2)

        p.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(8, 5, 50, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(bar_col if self._text != "--" else qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(0, 4, W - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self._text)

        p.end()

class LogWidget(QTextEdit):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        # Cap scrollback so an hours-long session can't grow the document
        # without bound — keeps memory flat and every insert cheap. Oldest
        # lines drop off the top automatically.
        self.document().setMaximumBlockCount(600)
        self.setFont(QFont("Courier New", 9))
        self.setStyleSheet(f"""
            QTextEdit {{
                background: {C.PANEL};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                padding: 6px;
                selection-background-color: {C.PRI_GHO};
            }}
            QScrollBar:vertical {{
                background: {C.BG};
                width: 8px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_B};
                border-radius: 4px;
                min-height: 20px;
            }}
        """)
        self._queue: list[str] = []
        self._typing  = False
        self._text    = ""
        self._pos     = 0
        self._tag     = "sys"
        self._last_raw = ""
        self._repeat_cnt = 1
        self._ai_name_lc = "jarvis"   # updated when assistant name changes
        self._streaming_active: bool = False
        self._streaming_speaker: str = ""
        self._streaming_has_content: bool = False
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._sig.connect(self._enqueue)

    def append_log(self, text: str):
        self._sig.emit(text)

    def stream_log_chunk(self, speaker: str, chunk: str, is_final: bool = False):
        """Display live spoken speech tokens directly in the HUD sidebar in real time."""
        try:
            # If typewriter is currently animating an old line, flush it immediately so live audio is not held back
            if self._typing:
                self._tmr.stop()
                if self._pos < len(self._text):
                    rem = self._text[self._pos:]
                    cur = self.textCursor()
                    cur.movePosition(cur.MoveOperation.End)
                    fmt = cur.charFormat()
                    col = {
                        "you":  qcol(C.WHITE),
                        "ai":   qcol(C.PRI),
                        "err":  qcol(C.RED),
                        "file": qcol(C.GREEN),
                        "sys":  qcol(C.ACC2),
                    }.get(self._tag, qcol(C.TEXT))
                    fmt.setForeground(QBrush(col))
                    cur.insertText(rem + "\n", fmt)
                    self.setTextCursor(cur)
                    self.ensureCursorVisible()
                self._typing = False
                self._text = ""
                self._pos = 0

            # If not currently in active streaming mode, start line with speaker prefix
            if not self._streaming_active:
                if not chunk and is_final:
                    return
                spk = (speaker or "").strip()
                spk_lower = spk.lower()
                is_user = spk_lower == "you" or spk_lower.startswith("user")
                col = qcol(C.WHITE) if is_user else qcol(C.PRI)
                pfx = "You: " if is_user else f"{spk}: "

                cur = self.textCursor()
                cur.movePosition(cur.MoveOperation.End)
                fmt = cur.charFormat()
                fmt.setForeground(QBrush(col))
                cur.insertText(pfx, fmt)
                self.setTextCursor(cur)
                self.ensureCursorVisible()

                self._streaming_active = True
                self._streaming_speaker = spk
                self._streaming_has_content = False

            # Insert chunk text if present
            if chunk:
                cur = self.textCursor()
                cur.movePosition(cur.MoveOperation.End)
                fmt = cur.charFormat()
                spk_lower = (self._streaming_speaker or "").strip().lower()
                is_user = spk_lower == "you" or spk_lower.startswith("user")
                col = qcol(C.WHITE) if is_user else qcol(C.PRI)
                fmt.setForeground(QBrush(col))

                clean_chunk = chunk
                if self._streaming_has_content and not clean_chunk.startswith((" ", ",", ".", "!", "?", ":", ";", "'", "\n")):
                    clean_chunk = " " + clean_chunk

                cur.insertText(clean_chunk, fmt)
                self.setTextCursor(cur)
                self.ensureCursorVisible()
                self._streaming_has_content = True

            # Finalize turn
            if is_final:
                if self._streaming_active:
                    cur = self.textCursor()
                    cur.movePosition(cur.MoveOperation.End)
                    cur.insertText("\n")
                    self.setTextCursor(cur)
                    self.ensureCursorVisible()
                self._streaming_active = False
                self._streaming_speaker = ""
                self._streaming_has_content = False
                if self._queue and not self._typing:
                    self._next()
        except Exception as e:
            print(f"[ActivityLog] stream error: {e}")

    def clear_log(self):
        self._queue.clear()
        self._typing = False
        self._text = ""
        self._pos = 0
        self._last_raw = ""
        self._streaming_active = False
        self._streaming_speaker = ""
        self._streaming_has_content = False
        self.clear()

    def _enqueue(self, text: str):
        st = text.strip()
        # De-duplicate identical consecutive system status lines
        if st == self._last_raw:
            self._repeat_cnt += 1
            # Filter out repeated idle/sleep noise
            if "sleeping. say 'hey jarvis'" in st.lower() or self._repeat_cnt > 2:
                return
        else:
            self._last_raw = st
            self._repeat_cnt = 1

        self._queue.append(text)
        if not self._typing:
            self._next()

    def _next(self):
        if not self._queue:
            self._typing = False
            return
        self._typing = True
        self._text   = self._queue.pop(0)
        self._pos    = 0
        tl = self._text.lower()
        _ai_pfx = f"{self._ai_name_lc}:"
        if   tl.startswith("you:"):                              self._tag = "you"
        elif tl.startswith(_ai_pfx) or tl.startswith("jarvis:"): self._tag = "ai"
        elif tl.startswith("file:"):                             self._tag = "file"
        elif "err" in tl:                                        self._tag = "err"
        else:                                                    self._tag = "sys"
        self._tmr.start(6)

    def _step(self):
        if self._pos < len(self._text):
            ch  = self._text[self._pos]
            cur = self.textCursor()
            fmt = cur.charFormat()
            col = {
                "you":  qcol(C.WHITE),
                "ai":   qcol(C.PRI),
                "err":  qcol(C.RED),
                "file": qcol(C.GREEN),
                "sys":  qcol(C.ACC2),
            }.get(self._tag, qcol(C.TEXT))
            fmt.setForeground(QBrush(col))
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText(ch, fmt)
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            self._pos += 1
        else:
            self._tmr.stop()
            cur = self.textCursor()
            cur.movePosition(cur.MoveOperation.End)
            cur.insertText("\n")
            self.setTextCursor(cur)
            self.ensureCursorVisible()
            QTimer.singleShot(20, self._next)

_FILE_ICONS = {
    "image":   ("🖼", "#00d4ff"), "video":   ("🎬", "#ff6b00"),
    "audio":   ("🎵", "#cc44ff"), "pdf":     ("📄", "#ff4444"),
    "word":    ("📝", "#4488ff"), "excel":   ("📊", "#44bb44"),
    "code":    ("💻", "#ffcc00"), "archive": ("📦", "#ff8844"),
    "pptx":    ("📊", "#ff6622"), "text":    ("📃", "#aaaaaa"),
    "data":    ("🔧", "#88ddff"), "unknown": ("📎", "#888888"),
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg","jpeg","png","gif","webp","bmp","tiff","svg","ico"], "image"),
    **dict.fromkeys(["mp4","avi","mov","mkv","wmv","flv","webm","m4v"],         "video"),
    **dict.fromkeys(["mp3","wav","ogg","m4a","aac","flac","wma","opus"],        "audio"),
    **dict.fromkeys(["pdf"],                                                     "pdf"),
    **dict.fromkeys(["doc","docx"],                                              "word"),
    **dict.fromkeys(["xls","xlsx","ods"],                                        "excel"),
    **dict.fromkeys(["ppt","pptx"],                                              "pptx"),
    **dict.fromkeys(["py","js","ts","jsx","tsx","html","css","java","c","cpp",
                     "cs","go","rs","rb","php","swift","kt","sh","sql","lua"],   "code"),
    **dict.fromkeys(["zip","rar","tar","gz","7z","bz2","xz"],                   "archive"),
    **dict.fromkeys(["txt","md","rst","log"],                                    "text"),
    **dict.fromkeys(["csv","tsv","json","xml"],                                  "data"),
}

def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")

def _fmt_size(size: int) -> str:
    if   size < 1024:    return f"{size} B"
    elif size < 1024**2: return f"{size/1024:.1f} KB"
    elif size < 1024**3: return f"{size/1024**2:.1f} MB"
    else:                return f"{size/1024**3:.1f} GB"


class FileDropZone(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(100)
        self._current_file: str | None = None
        self._hovering  = False
        self._drag_over = False
        self._dash_offset = 0.0
        self._anim_tmr = QTimer(self)
        self._anim_tmr.timeout.connect(self._animate)
        self._anim_tmr.start(40)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._canvas = _DropCanvas(self)
        layout.addWidget(self._canvas)

    def _animate(self):
        # The marching-ants dashed border is only meaningful while the user is
        # hovering or dragging a file over the zone. When idle, skip the repaint
        # entirely instead of redrawing the whole zone 25×/s forever — that idle
        # repaint held the GIL and stole time from the audio/response threads.
        if not (self._hovering or self._drag_over):
            return
        self._dash_offset = (self._dash_offset + 0.8) % 20
        self._canvas.update()

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._drag_over = True; self._canvas.update()

    def dragLeaveEvent(self, e):
        self._drag_over = False; self._canvas.update()

    def dropEvent(self, e: QDropEvent):
        self._drag_over = False
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self._set_file(path)
        self._canvas.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._browse()

    def enterEvent(self, e):
        self._hovering = True; self._canvas.update()

    def leaveEvent(self, e):
        self._hovering = False; self._canvas.update()

    def current_file(self) -> str | None:
        return self._current_file

    def clear_file(self):
        self._current_file = None; self._canvas.update()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file for JARVIS", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._set_file(path)

    def _set_file(self, path: str):
        self._current_file = path
        self._canvas.update()
        self.file_selected.emit(path)


class _DropCanvas(QWidget):
    def __init__(self, zone: FileDropZone):
        super().__init__(zone)
        self._z = zone

    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        z    = self._z
        W, H = self.width(), self.height()
        pad  = 6
        rect = QRectF(pad, pad, W - pad * 2, H - pad * 2)

        bg_col = qcol("#001a24" if z._drag_over else ("#001218" if z._hovering else C.PANEL))
        p.setBrush(QBrush(bg_col)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   border_col = qcol(C.GREEN, 200)
        elif z._drag_over:    border_col = qcol(C.PRI, 230)
        elif z._hovering:     border_col = qcol(C.BORDER_B, 200)
        else:                 border_col = qcol(C.BORDER, 160)

        pen = QPen(border_col, 1.5, Qt.PenStyle.DashLine)
        pen.setDashOffset(z._dash_offset)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 6, 6)

        if z._current_file:   self._paint_file(p, W, H)
        elif z._drag_over:    self._paint_drag_over(p, W, H)
        else:                 self._paint_idle(p, W, H, z._hovering)

        p.end()

    def _paint_idle(self, p, W, H, hover):
        cx, cy = W / 2, H / 2
        col = qcol(C.PRI_DIM if not hover else C.PRI)
        p.setPen(QPen(col, 2)); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(cx, cy - 14), QPointF(cx, cy + 4))
        p.drawLine(QPointF(cx - 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx + 8, cy - 6), QPointF(cx, cy - 14))
        p.drawLine(QPointF(cx - 14, cy + 4), QPointF(cx + 14, cy + 4))
        p.setFont(QFont("Courier New", 8))
        p.setPen(QPen(qcol(C.PRI_DIM if not hover else C.TEXT), 1))
        p.drawText(QRectF(0, cy + 8, W, 16), Qt.AlignmentFlag.AlignCenter,
                   "Drop file here  or  Click to Browse")
        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol("#1a4a5a"), 1))
        p.drawText(QRectF(0, cy + 24, W, 14), Qt.AlignmentFlag.AlignCenter,
                   "Images · Video · Audio · PDF · Docs · Code · Data")

    def _paint_drag_over(self, p, W, H):
        cx, cy = W / 2, H / 2
        p.setFont(QFont("Courier New", 20))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy - 24, W, 32), Qt.AlignmentFlag.AlignCenter, "⬇")
        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.PRI), 1))
        p.drawText(QRectF(0, cy + 12, W, 16), Qt.AlignmentFlag.AlignCenter, "Release to load")

    def _paint_file(self, p, W, H):
        path = Path(self._z._current_file)
        cat  = _file_category(path)
        icon, icon_col = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size_str = _fmt_size(path.stat().st_size)
        ext_str  = path.suffix.upper().lstrip(".") or "FILE"

        block_x, block_w = 10, 60
        p.setFont(QFont("Segoe UI Emoji", 22) if _OS == "Windows" else QFont("Arial", 22))
        p.setPen(QPen(qcol(icon_col), 1))
        p.drawText(QRectF(block_x, 0, block_w, H), Qt.AlignmentFlag.AlignCenter, icon)

        tx = block_x + block_w + 6
        tw = W - tx - 38

        p.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.WHITE), 1))
        name = path.name if len(path.name) <= 34 else path.name[:31] + "..."
        p.drawText(QRectF(tx, H * 0.18, tw, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        p.setFont(QFont("Courier New", 7))
        p.setPen(QPen(qcol(C.TEXT_DIM), 1))
        p.drawText(QRectF(tx, H * 0.18 + 18, tw, 14),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{ext_str}  ·  {size_str}")

        p.setFont(QFont("Courier New", 6))
        p.setPen(QPen(qcol("#1e5c6a"), 1))
        par = str(path.parent)
        if len(par) > 42: par = "…" + par[-41:]
        p.drawText(QRectF(tx, H * 0.18 + 34, tw, 12),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, par)

        p.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        p.setPen(QPen(qcol(C.RED, 180), 1))
        p.drawText(QRectF(W - 34, 0, 28, H), Qt.AlignmentFlag.AlignCenter, "✕")

    def mousePressEvent(self, e):
        z = self._z
        if z._current_file and e.pos().x() > self.width() - 34:
            z.clear_file()
        else:
            z.mousePressEvent(e)


class _CameraPreview(QWidget):
    """Floating overlay that briefly shows what the camera captured."""

    _W, _H = 244, 188

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            _CameraPreview {{
                background: rgba(0, 6, 10, 242);
                border: 1px solid {C.PRI};
                border-radius: 6px;
            }}
        """)
        self.setFixedWidth(self._W)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 5, 6, 6)
        lay.setSpacing(4)

        hdr = QHBoxLayout()
        title = QLabel("◈  VISUAL INPUT")
        title.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hdr.addWidget(title)
        hdr.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(16, 16)
        close_btn.setFont(QFont("Courier New", 8))
        close_btn.setStyleSheet(
            f"color: {C.TEXT_DIM}; background: transparent; border: none;"
        )
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.hide)
        hdr.addWidget(close_btn)
        lay.addLayout(hdr)

        self._img_lbl = QLabel()
        self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_lbl.setStyleSheet("background: transparent;")
        lay.addWidget(self._img_lbl)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

        self.hide()

    def show_frame(self, img_bytes: bytes) -> None:
        px = QPixmap()
        px.loadFromData(img_bytes)
        if not px.isNull():
            max_w = self._W - 12
            scaled = px.scaled(
                max_w, 160,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._img_lbl.setPixmap(scaled)
            self._img_lbl.setFixedSize(scaled.width(), scaled.height())
            self.adjustSize()
        self.show()
        self.raise_()
        self._timer.start(6_000)   # auto-dismiss after 6 s


class SetupOverlay(QWidget):
    done = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: rgba(0, 6, 10, 245);
                border: 1px solid {C.BORDER_B};
                border-radius: 6px;
            }}
        """)

        detected = {"darwin": "mac", "windows": "windows"}.get(
            _OS.lower(), "linux"
        )
        self._sel_os = detected

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 22, 30, 22)
        layout.setSpacing(8)

        def _lbl(txt, font_size=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont("Courier New", font_size,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("◈  INITIALISATION REQUIRED", 13, True))
        layout.addWidget(_lbl("Configure J.A.R.V.I.S. before first boot.", 9, color=C.PRI_DIM))
        layout.addSpacing(6)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep)
        layout.addSpacing(4)

        layout.addWidget(_lbl("GEMINI API KEY", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza…")
        self._key_input.setFont(QFont("Courier New", 10))
        self._key_input.setFixedHeight(32)
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d12; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        layout.addWidget(self._key_input)
        layout.addSpacing(12)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep2)
        layout.addSpacing(4)

        layout.addWidget(_lbl("OPERATING SYSTEM", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected: {det_name}", 8, color=C.ACC2,
                               align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(6)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows","⊞  Windows"),("mac","  macOS"),("linux","🐧  Linux")]:
            btn = QPushButton(label)
            btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel(detected)
        layout.addSpacing(12)

        init_btn = QPushButton("▸  INITIALISE SYSTEMS WITH API KEY")
        init_btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        init_btn.setFixedHeight(34)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{
                background: {C.PRI_GHO}; border: 1px solid {C.PRI};
            }}
        """)
        init_btn.clicked.connect(self._submit)
        layout.addWidget(init_btn)

        free_btn = QPushButton("⚡ START 100% FREE (BUILT-IN GEMINI WEB PROXY)")
        free_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        free_btn.setFixedHeight(34)
        free_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        free_btn.setStyleSheet(f"""
            QPushButton {{
                background: #002211; color: #00ffaa;
                border: 1px solid #00aa66; border-radius: 3px;
            }}
            QPushButton:hover {{
                background: #00331a; border-color: #00ffaa;
            }}
        """)
        free_btn.clicked.connect(lambda: self.done.emit("", self._sel_os))
        layout.addWidget(free_btn)

    def _sel(self, key: str):
        self._sel_os = key
        pal = {"windows":(C.PRI,"#001a22"),"mac":(C.ACC2,"#1a1400"),"linux":(C.GREEN,"#001a0d")}
        for k, btn in self._os_btns.items():
            if k == key:
                fg, bg = pal[k]
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {fg}; color: {bg};
                        border: none; border-radius: 3px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: #000d12; color: {C.TEXT_DIM};
                        border: 1px solid {C.BORDER}; border-radius: 3px;
                    }}
                    QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
                """)

    def _submit(self):
        key = self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(
                self._key_input.styleSheet() +
                f" QLineEdit {{ border: 1px solid {C.RED}; }}"
            )
            return
        self.done.emit(key, self._sel_os)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)


class HueWheel(QWidget):
    """
    Circular colour picker. The user drags the handle (small white circle)
    around the wheel to choose from ALL hues. The filled circle in the centre
    is a live preview of the selected colour.
    """

    hue_picked    = pyqtSignal(str)   # while dragging (live)
    hue_committed = pyqtSignal(str)   # when the handle is released

    _RING = 16   # ring thickness (px)

    def __init__(self, initial_hex: str = DEFAULT_UI_COLOR, parent=None):
        super().__init__(parent)
        self.setFixedSize(148, 148)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hue  = 0.53
        self._drag = False
        self.set_color(initial_hex)

    # ── API ──────────────────────────────────────────────────────────────────
    def color(self) -> str:
        return QColor.fromHsvF(self._hue, 1.0, 1.0).name()

    def set_color(self, hex_str: str):
        c = QColor((hex_str or "").strip())
        if c.isValid() and c.hsvHueF() >= 0:
            self._hue = c.hsvHueF()
            self.update()

    # ── geometry helpers ─────────────────────────────────────────────────────
    def _ring_rect(self) -> QRectF:
        m = self._RING / 2 + 3
        return QRectF(self.rect()).adjusted(m, m, -m, -m)

    def _hue_from_pos(self, pos: QPointF) -> float:
        c  = QRectF(self.rect()).center()
        dx = pos.x() - c.x()
        dy = c.y() - pos.y()          # screen y goes down — flip to math axis
        ang = math.atan2(dy, dx)      # [-π, π], counter-clockwise
        return (ang / (2 * math.pi)) % 1.0

    # ── drawing ──────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect   = self._ring_rect()
        center = rect.center()

        grad = QConicalGradient(center, 0)
        for i in range(0, 361, 20):
            grad.setColorAt(i / 360.0, QColor.fromHsvF((i % 360) / 360.0, 1.0, 1.0))
        p.setPen(QPen(QBrush(grad), self._RING))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)

        # centre preview circle
        preview = QColor.fromHsvF(self._hue, 1.0, 1.0)
        inner   = rect.adjusted(30, 30, -30, -30)
        p.setPen(QPen(qcol(C.BORDER_B), 1))
        p.setBrush(QBrush(preview))
        p.drawEllipse(inner)

        # draggable handle
        r   = rect.width() / 2
        ang = self._hue * 2 * math.pi
        hx  = center.x() + r * math.cos(ang)
        hy  = center.y() - r * math.sin(ang)
        p.setPen(QPen(QColor("#00060a"), 2))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(QPointF(hx, hy), 7.5, 7.5)
        p.end()

    # ── fare ─────────────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        self._drag = True
        self._hue  = self._hue_from_pos(e.position())
        self.update()
        self.hue_picked.emit(self.color())

    def mouseMoveEvent(self, e):
        if self._drag:
            self._hue = self._hue_from_pos(e.position())
            self.update()
            self.hue_picked.emit(self.color())

    def mouseReleaseEvent(self, e):
        if self._drag:
            self._drag = False
            self.hue_committed.emit(self.color())



class ProviderSettingsOverlay(QWidget):
    """Floating cyberpunk overlay — tabbed configuration for AI Brains, Voice Testing Lab, and System Telemetry."""

    saved = pyqtSignal(str)
    voice_tested = pyqtSignal(bool, str)
    provider_tested = pyqtSignal(str, bool, str, float)
    models_fetched = pyqtSignal(str, list)

    _OW, _OH = 490, 720

    def __init__(self, cfg: dict = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            ProviderSettingsOverlay {{
                background: rgba(0, 7, 12, 248);
                border: 1px solid {C.BORDER_B};
                border-radius: 8px;
            }}
        """)
        self.cfg = cfg or {}

        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(18, 14, 18, 14)
        main_lay.setSpacing(6)

        def _lbl(txt, fs=8, bold=False, color=C.PRI, align=Qt.AlignmentFlag.AlignLeft):
            w = QLabel(txt); w.setAlignment(align)
            w.setFont(QFont("Courier New", fs, QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        self._fs = (
            f"QLineEdit, QComboBox {{ background: #000d12; color: {C.TEXT}; "
            f"border: 1px solid {C.BORDER}; border-radius: 3px; padding: 3px 8px; }}"
            f"QLineEdit:focus, QComboBox:focus {{ border: 1px solid {C.PRI}; }}"
            f"QComboBox QAbstractItemView {{ "
            f"background: #000c14; color: {C.TEXT}; border: 1px solid {C.BORDER_B}; "
            f"selection-background-color: #002233; selection-color: {C.PRI}; "
            f"padding: 2px; outline: none; }}"
            f"QComboBox QAbstractItemView QScrollBar:vertical {{ "
            f"background: #000810; width: 8px; border: none; margin: 0px; }}"
            f"QComboBox QAbstractItemView QScrollBar::handle:vertical {{ "
            f"background: {C.BORDER_B}; min-height: 20px; border-radius: 3px; }}"
            f"QComboBox QAbstractItemView QScrollBar::handle:vertical:hover {{ "
            f"background: {C.PRI}; }}"
            f"QComboBox QAbstractItemView QScrollBar::add-line:vertical, "
            f"QComboBox QAbstractItemView QScrollBar::sub-line:vertical {{ height: 0px; }}"
        )

        # Header
        main_lay.addWidget(_lbl("⚡  STARK NEURAL CONFIG & LAB", 11, True, color=C.PRI, align=Qt.AlignmentFlag.AlignCenter))
        main_lay.addWidget(_lbl("Multi-Brain Matrix • Offline Piper Voice Lab • Telemetry", 7, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignCenter))

        # Top Navigation Tabs (Pikachu-Style)
        tab_row = QHBoxLayout()
        tab_row.setSpacing(6)
        self._btn_tab_ai = QPushButton("🤖 AI PROVIDERS")
        self._btn_tab_voice = QPushButton("🎙️ VOICE LAB")
        self._btn_tab_sys = QPushButton("🌐 TELEMETRY & APIS")

        for b in (self._btn_tab_ai, self._btn_tab_voice, self._btn_tab_sys):
            b.setFixedHeight(26)
            b.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)

        tab_row.addWidget(self._btn_tab_ai)
        tab_row.addWidget(self._btn_tab_voice)
        tab_row.addWidget(self._btn_tab_sys)
        main_lay.addLayout(tab_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        main_lay.addWidget(sep)

        # Stacked Pages
        self._stack = QStackedWidget()
        main_lay.addWidget(self._stack, 1)

        # ── Page 1: AI Providers & Live Model Hub ──────────────────────────────
        page_ai = QWidget()
        lay_ai = QVBoxLayout(page_ai)
        lay_ai.setContentsMargins(4, 4, 4, 4)
        lay_ai.setSpacing(5)

        lay_ai.addWidget(_lbl("ACTIVE BRAIN / LLM PROVIDER", 8, bold=True, color=C.PRI))
        self._provider_combo = QComboBox()
        self._provider_combo.setFont(QFont("Courier New", 9))
        self._provider_combo.setStyleSheet(self._fs)
        self._provider_combo.setMaxVisibleItems(10)
        self._provider_combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        from core.multi_llm import PROVIDER_REGISTRY

        curr_prov = (self.cfg.get("preferred_llm_provider") or "gemini").lower().strip()
        idx_to_select = 0
        for idx, (p_id, reg) in enumerate(PROVIDER_REGISTRY.items()):
            self._provider_combo.addItem(reg.get("name", p_id), p_id)
            if curr_prov == p_id:
                idx_to_select = idx
        self._provider_combo.setCurrentIndex(idx_to_select)
        lay_ai.addWidget(self._provider_combo)

        # Active Model Selector for Selected Provider (Dynamic / User Configurable)
        lay_ai.addWidget(_lbl("ACTIVE MODEL FOR SELECTED PROVIDER (Dynamic / Custom)", 7, bold=True, color=C.TEXT_MED))
        self._model_combo = QComboBox()
        self._model_combo.setEditable(True)
        self._model_combo.setFont(QFont("Courier New", 8))
        self._model_combo.setStyleSheet(self._fs)
        self._model_combo.setMaxVisibleItems(10)
        self._model_combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        lay_ai.addWidget(self._model_combo)

        # Scrollable Key and Test Row
        key_scroll = QScrollArea()
        key_scroll.setWidgetResizable(True)
        key_scroll.setFrameShape(QFrame.Shape.NoFrame)
        key_scroll.setStyleSheet("background: transparent;")
        key_container = QWidget()
        k_lay = QVBoxLayout(key_container)
        k_lay.setContentsMargins(0, 0, 0, 0)
        k_lay.setSpacing(5)

        self._key_inputs = {}
        self._stat_labels = {}

        def _make_key_row(title, placeholder, value, prov_id):
            k_lay.addWidget(_lbl(title, 7, color=C.TEXT_MED))
            r = QHBoxLayout(); r.setSpacing(5)
            inp = QLineEdit(value)
            inp.setEchoMode(QLineEdit.EchoMode.Password)
            inp.setPlaceholderText(placeholder)
            inp.setFont(QFont("Courier New", 8))
            inp.setStyleSheet(self._fs)
            r.addWidget(inp, 1)

            t_btn = QPushButton("⚡ TEST")
            t_btn.setFixedSize(68, 24)
            t_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            t_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            t_btn.setStyleSheet(f"""
                QPushButton {{ background: #001a24; color: {C.PRI}; border: 1px solid {C.PRI_DIM}; border-radius: 3px; }}
                QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
            """)
            r.addWidget(t_btn)
            k_lay.addLayout(r)

            stat_lbl = QLabel("⚪ Untested")
            stat_lbl.setFont(QFont("Courier New", 7))
            stat_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; padding-left: 2px;")
            k_lay.addWidget(stat_lbl)

            self._key_inputs[prov_id] = inp
            self._stat_labels[prov_id] = stat_lbl

            def _on_test():
                stat_lbl.setText("🟡 Pinging...")
                stat_lbl.setStyleSheet("color: #ffaa00;")
                val = inp.text().strip()
                def _run():
                    try:
                        from core.multi_llm import test_llm_provider, fetch_provider_models
                        ok, msg, lat = test_llm_provider(prov_id, api_key=val)
                        models = fetch_provider_models(prov_id, api_key=val)
                        self.provider_tested.emit(prov_id, ok, msg, lat)
                        self.models_fetched.emit(prov_id, models)
                    except Exception as ex:
                        self.provider_tested.emit(prov_id, False, str(ex)[:35], 0.0)
                threading.Thread(target=_run, daemon=True).start()

            t_btn.clicked.connect(_on_test)
            return inp, stat_lbl

        # Live feedback on provider test completion
        def _on_provider_tested(prov_id, ok, msg, lat):
            lbl = self._stat_labels.get(prov_id)
            if lbl:
                icon = "🟢" if ok else "🔴"
                color = "#00ffaa" if ok else "#ff5555"
                lat_str = f" • {lat:.0f}ms" if lat > 0 else ""
                lbl.setText(f"{icon} {msg}{lat_str}")
                lbl.setStyleSheet(f"color: {color}; padding-left: 2px;")

        self.provider_tested.connect(_on_provider_tested)

        def _update_model_dropdown(p_id):
            self._model_combo.blockSignals(True)
            self._model_combo.clear()
            reg = PROVIDER_REGISTRY.get(p_id, {})
            curated = list(reg.get("models", []))
            saved_models = self.cfg.get("selected_models", {})
            active_m = saved_models.get(p_id) or reg.get("default_model", "")
            for m in curated:
                self._model_combo.addItem(m)
            if active_m and active_m not in curated:
                self._model_combo.insertItem(0, active_m)
            if active_m:
                self._model_combo.setCurrentText(active_m)
            self._model_combo.blockSignals(False)

        def _on_models_fetched(prov_id, models):
            curr_p = self._provider_combo.currentData()
            if curr_p == prov_id and models:
                cur_text = self._model_combo.currentText().strip()
                self._model_combo.blockSignals(True)
                existing = [self._model_combo.itemText(i) for i in range(self._model_combo.count())]
                for m in models:
                    if m not in existing:
                        self._model_combo.addItem(m)
                        existing.append(m)
                if cur_text:
                    self._model_combo.setCurrentText(cur_text)
                self._model_combo.blockSignals(False)

        self.models_fetched.connect(_on_models_fetched)

        def _on_provider_changed(index):
            p_id = self._provider_combo.currentData() or "gemini"
            _update_model_dropdown(p_id)
            def _bg():
                try:
                    from core.multi_llm import fetch_provider_models
                    inp = self._key_inputs.get(p_id)
                    key_val = inp.text().strip() if inp else ""
                    live_m = fetch_provider_models(p_id, api_key=key_val)
                    if live_m:
                        self.models_fetched.emit(p_id, live_m)
                except Exception:
                    pass
            threading.Thread(target=_bg, daemon=True).start()

        self._provider_combo.currentIndexChanged.connect(_on_provider_changed)
        _update_model_dropdown(curr_prov)

        # Primary Key Inputs (Legacy attribute aliases retained)
        self._gemini_input, self._gemini_stat = _make_key_row(
            "GEMINI API KEY (Live Voice & Vision)", "AIzaSy...",
            self.cfg.get("gemini_api_key", ""), "gemini"
        )
        self._cerebras_input, self._cerebras_stat = _make_key_row(
            "CEREBRAS API KEY (Ultra-Fast ~2,000 tok/s - 1M tokens/day)", "csk-...",
            self.cfg.get("cerebras_api_key", ""), "cerebras"
        )
        self._groq_input, self._groq_stat = _make_key_row(
            "GROQ API KEY (Recommended: 350+ tok/s)", "gsk_...",
            self.cfg.get("groq_api_key", ""), "groq"
        )
        self._openrouter_input, self._openrouter_stat = _make_key_row(
            "OPENROUTER API KEY (DeepSeek R1 / Claude)", "sk-or-...",
            self.cfg.get("openrouter_api_key", ""), "openrouter"
        )
        self._deepseek_input, self._deepseek_stat = _make_key_row(
            "DEEPSEEK API KEY", "sk-...",
            self.cfg.get("deepseek_api_key", ""), "deepseek"
        )

        # Additional Registered Providers
        other_provs = [
            ("nvidia", "NVIDIA NIM API KEY (70+ Models, 1000 Free Calls/mo)"),
            ("mistral", "MISTRAL AI API KEY (Codestral & Mistral - 1B tok/mo)"),
            ("cloudflare", "CLOUDFLARE WORKERS AI API KEY (10K Neurons/day Free)"),
            ("cohere", "COHERE API KEY (Command-R & RAG Embeddings)"),
            ("zhipu", "ZHIPU AI API KEY (GLM-4-Flash Permanent Free)"),
            ("github", "GITHUB MODELS TOKEN / PAT (Free GPT-4o, DeepSeek-R1)"),
            ("huggingface", "HUGGING FACE TOKEN (500K+ Models Serverless)"),
            ("sambanova", "SAMBANOVA CLOUD API KEY (Free Llama 3.1 405B & 70B)"),
            ("kluster", "KLUSTER AI API KEY (DeepSeek R1, Llama, Qwen3)"),
            ("llm7", "LLM7.IO TOKEN (Optional - Zero-Friction 30-120 RPM)"),
            ("freellmapi", "FREELLMAPI KEY (1.7B Tokens/mo Failover Aggregator)"),
            ("orcarouter", "ORCAROUTER KEY ($0/token, 200+ Free Models)"),
            ("vercel", "VERCEL AI GATEWAY KEY (Unified Multi-Provider)"),
            ("freetheai", "FREETHEAI KEY (60+ Community Models Free Forever)"),
        ]
        for p_id, row_label in other_provs:
            reg = PROVIDER_REGISTRY.get(p_id, {})
            kfield = reg.get("key_field", f"{p_id}_api_key")
            _make_key_row(row_label, reg.get("placeholder", "key..."), self.cfg.get(kfield, ""), p_id)

        # Custom / Ollama
        k_lay.addWidget(_lbl("CUSTOM / OLLAMA ENDPOINT URL & MODEL", 7, color=C.TEXT_MED))
        c_row = QHBoxLayout(); c_row.setSpacing(5)
        self._custom_url = QLineEdit(self.cfg.get("custom_llm_url", "http://localhost:11434/v1"))
        self._custom_url.setFont(QFont("Courier New", 8)); self._custom_url.setStyleSheet(self._fs)
        c_row.addWidget(self._custom_url, 1)

        self._custom_model = QLineEdit(self.cfg.get("custom_llm_model", "llama3.2"))
        self._custom_model.setPlaceholderText("model name")
        self._custom_model.setFont(QFont("Courier New", 8)); self._custom_model.setStyleSheet(self._fs)
        c_row.addWidget(self._custom_model, 1)

        c_test_btn = QPushButton("⚡ TEST")
        c_test_btn.setFixedSize(68, 24)
        c_test_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        c_test_btn.setStyleSheet(f"""
            QPushButton {{ background: #001a24; color: {C.PRI}; border: 1px solid {C.PRI_DIM}; border-radius: 3px; }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
        """)
        c_row.addWidget(c_test_btn)
        k_lay.addLayout(c_row)

        self._custom_stat = QLabel("⚪ Untested (Ollama / LocalAI)")
        self._custom_stat.setFont(QFont("Courier New", 7))
        self._custom_stat.setStyleSheet(f"color: {C.TEXT_DIM}; padding-left: 2px;")
        k_lay.addWidget(self._custom_stat)
        self._stat_labels["custom"] = self._custom_stat

        def _on_custom_test():
            self._custom_stat.setText("🟡 Pinging local endpoint...")
            self._custom_stat.setStyleSheet("color: #ffaa00;")
            url = self._custom_url.text().strip()
            def _run():
                from core.multi_llm import test_llm_provider, fetch_provider_models
                ok, msg, lat = test_llm_provider("custom", custom_url=url)
                models = fetch_provider_models("custom", custom_url=url)
                self.provider_tested.emit("custom", ok, msg, lat)
                self.models_fetched.emit("custom", models)
            threading.Thread(target=_run, daemon=True).start()

        c_test_btn.clicked.connect(_on_custom_test)

        # Gemini Web FREE Proxy Row
        k_lay.addWidget(_lbl("GEMINI WEB FREE PROXY (Built-in Anonymous Server)", 7, color=C.PRI))
        gw_row = QHBoxLayout(); gw_row.setSpacing(5)
        self._gemini_web_info = QLineEdit("http://127.0.0.1:8081/v1  (Model: gemini-3.7-flash)")
        self._gemini_web_info.setReadOnly(True)
        self._gemini_web_info.setFont(QFont("Courier New", 8))
        self._gemini_web_info.setStyleSheet(self._fs + "; color: #00ffaa;")
        gw_row.addWidget(self._gemini_web_info, 1)

        from core.gemini_free_proxy import is_running as _proxy_is_running, start_proxy as _proxy_start, stop_proxy as _proxy_stop

        gw_toggle_btn = QPushButton("⏹ STOP PROXY" if _proxy_is_running() else "▶ START PROXY")
        gw_toggle_btn.setFixedSize(100, 24)
        gw_toggle_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        gw_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        gw_toggle_btn.setStyleSheet(f"""
            QPushButton {{ background: #001a15; color: #00ffaa; border: 1px solid #00aa66; border-radius: 3px; }}
            QPushButton:hover {{ background: #002e24; border-color: #00ffaa; }}
        """)
        gw_row.addWidget(gw_toggle_btn)

        gw_test_btn = QPushButton("⚡ TEST")
        gw_test_btn.setFixedSize(60, 24)
        gw_test_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        gw_test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        gw_test_btn.setStyleSheet(f"""
            QPushButton {{ background: #002211; color: #00ffaa; border: 1px solid #00aa66; border-radius: 3px; }}
            QPushButton:hover {{ background: #00331a; border-color: #00ffaa; }}
        """)
        gw_row.addWidget(gw_test_btn)
        k_lay.addLayout(gw_row)

        _init_st = "🟢 Proxy Running on Port 8081 (100% Free, No Key Required)" if _proxy_is_running() else "⚪ Proxy Idle (Stopped — click Start to run manually)"
        _init_clr = "#00ffaa" if _proxy_is_running() else C.TEXT_DIM
        self._gemini_web_stat = QLabel(_init_st)
        self._gemini_web_stat.setFont(QFont("Courier New", 7))
        self._gemini_web_stat.setStyleSheet(f"color: {_init_clr}; padding-left: 2px;")
        k_lay.addWidget(self._gemini_web_stat)
        self._stat_labels["gemini-web"] = self._gemini_web_stat

        def _on_proxy_toggle():
            if _proxy_is_running():
                _proxy_stop()
                gw_toggle_btn.setText("▶ START PROXY")
                self._gemini_web_stat.setText("⚪ Proxy Server Stopped (Port 8081 closed)")
                self._gemini_web_stat.setStyleSheet(f"color: {C.TEXT_DIM}; padding-left: 2px;")
            else:
                _proxy_start(port=8081, silent=True)
                gw_toggle_btn.setText("⏹ STOP PROXY")
                self._gemini_web_stat.setText("🟢 Proxy Server Running on http://127.0.0.1:8081/v1")
                self._gemini_web_stat.setStyleSheet("color: #00ffaa; padding-left: 2px;")

        gw_toggle_btn.clicked.connect(_on_proxy_toggle)

        def _on_gemini_web_test():
            if not _proxy_is_running():
                _proxy_start(port=8081, silent=True)
                gw_toggle_btn.setText("⏹ STOP PROXY")
            self._gemini_web_stat.setText("🟡 Testing local proxy connection...")
            self._gemini_web_stat.setStyleSheet("color: #ffaa00;")
            def _run():
                from core.multi_llm import test_llm_provider
                ok, msg, lat = test_llm_provider("gemini-web")
                self.provider_tested.emit("gemini-web", ok, msg, lat)
            threading.Thread(target=_run, daemon=True).start()
        gw_test_btn.clicked.connect(_on_gemini_web_test)

        # OmniRoute Gateway Row
        k_lay.addWidget(_lbl("OMNIROUTE GATEWAY (352+ Providers, 1200+ Models Unified)", 7, color=C.TEXT_MED))
        omni_row = QHBoxLayout(); omni_row.setSpacing(5)
        self._omni_url = QLineEdit("http://localhost:20128/v1")
        self._omni_url.setReadOnly(True)
        self._omni_url.setFont(QFont("Courier New", 8))
        self._omni_url.setStyleSheet(self._fs)
        omni_row.addWidget(self._omni_url, 1)

        omni_test_btn = QPushButton("⚡ TEST OMNI")
        omni_test_btn.setFixedSize(90, 24)
        omni_test_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        omni_test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        omni_test_btn.setStyleSheet(f"""
            QPushButton {{ background: #001a24; color: {C.PRI}; border: 1px solid {C.PRI_DIM}; border-radius: 3px; }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
        """)
        omni_row.addWidget(omni_test_btn)
        k_lay.addLayout(omni_row)

        self._omni_stat = QLabel("⚪ Untested (Install: npm i -g omniroute && omniroute start)")
        self._omni_stat.setFont(QFont("Courier New", 7))
        self._omni_stat.setStyleSheet(f"color: {C.TEXT_DIM}; padding-left: 2px;")
        k_lay.addWidget(self._omni_stat)
        self._stat_labels["omniroute"] = self._omni_stat

        def _on_omni_test():
            self._omni_stat.setText("🟡 Checking OmniRoute on :20128...")
            self._omni_stat.setStyleSheet("color: #ffaa00;")
            def _run():
                from core.multi_llm import test_llm_provider
                ok, msg, lat = test_llm_provider("omniroute")
                self.provider_tested.emit("omniroute", ok, msg, lat)
            threading.Thread(target=_run, daemon=True).start()
        omni_test_btn.clicked.connect(_on_omni_test)

        key_scroll.setWidget(key_container)
        lay_ai.addWidget(key_scroll, 1)
        self._stack.addWidget(page_ai)

        # ── Page 2: Voice & Sound Lab ──────────────────────────────────────────
        page_voice = QWidget()
        lay_voice = QVBoxLayout(page_voice)
        lay_voice.setContentsMargins(4, 4, 4, 4)
        lay_voice.setSpacing(8)

        lay_voice.addWidget(_lbl("VOICE ENGINE & SYNTHESIZER", 8, bold=True, color=C.PRI))
        self._tts_combo = QComboBox()
        self._tts_combo.setFont(QFont("Courier New", 9))
        self._tts_combo.setStyleSheet(self._fs)
        self._tts_combo.setMaxVisibleItems(10)
        self._tts_combo.view().setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        tts_options = [
            ("gemini_live", "Google Gemini Live (Multilingual Realtime Voice)"),
            ("piper_hindi", "Piper Offline Hindi (Devanagari - hi_IN Pratham)"),
            ("edgetts", "Microsoft EdgeTTS (Cloud Natural - Guy / Swara)"),
            ("kokoro", "Kokoro Neural TTS (Offline English - af_heart)"),
        ]
        curr_tts = (self.cfg.get("tts_engine") or "gemini_live").lower().strip()
        for idx, (t_id, t_label) in enumerate(tts_options):
            self._tts_combo.addItem(t_label, t_id)
            if curr_tts == t_id:
                self._tts_combo.setCurrentIndex(idx)
        lay_voice.addWidget(self._tts_combo)

        # Voice Info Banner
        self._voice_info_card = QLabel(
            "⚡ Piper Hindi: 100% Offline Neural Speech\n"
            "   Devanagari script support | Zero latency | Zero cloud tokens"
        )
        self._voice_info_card.setFont(QFont("Courier New", 7))
        self._voice_info_card.setStyleSheet(f"""
            background: rgba(0, 20, 30, 180);
            color: {C.PRI};
            border: 1px dashed {C.PRI_DIM};
            border-radius: 4px;
            padding: 6px 10px;
        """)
        lay_voice.addWidget(self._voice_info_card)

        # Prominent Glowing Test Voice Button (Pikachu-Style)
        self._voice_test_btn = QPushButton("🔊  TEST VOICE  (आवाज़ टेस्ट करें)")
        self._voice_test_btn.setFixedHeight(38)
        self._voice_test_btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        self._voice_test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._voice_test_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #002233, stop:1 #004455);
                color: #00ffff;
                border: 1px solid #00cccc;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #003344, stop:1 #006677);
                border: 1px solid #00ffff;
            }}
        """)
        lay_voice.addWidget(self._voice_test_btn)

        self._voice_stat_lbl = QLabel("⚪ Click to hear a live sample in the selected voice model.")
        self._voice_stat_lbl.setFont(QFont("Courier New", 7))
        self._voice_stat_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; padding-left: 2px;")
        lay_voice.addWidget(self._voice_stat_lbl)

        def _on_test_voice_click():
            eng = self._tts_combo.currentData() or "piper_hindi"
            self._voice_stat_lbl.setText("🟡 [Synthesizing & Playing preview...]")
            self._voice_stat_lbl.setStyleSheet("color: #ffaa00;")
            self._voice_test_btn.setEnabled(False)

            def _synth():
                from core.tts import test_tts_voice
                ok, msg = test_tts_voice(eng)
                self.voice_tested.emit(ok, msg)

            threading.Thread(target=_synth, daemon=True).start()

        self._voice_test_btn.clicked.connect(_on_test_voice_click)

        sep_v = QFrame(); sep_v.setFrameShape(QFrame.Shape.HLine)
        sep_v.setStyleSheet(f"color: {C.BORDER}; margin: 4px 0;")
        lay_voice.addWidget(sep_v)

        # SFX Controls
        self._sfx_checkbox = QCheckBox("🔊  Enable Stark UI Sound Effects (Boot, Wake, HUD Chimes)")
        self._sfx_checkbox.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._sfx_checkbox.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._sfx_checkbox.setChecked(bool(self.cfg.get("sfx_enabled", True)))
        lay_voice.addWidget(self._sfx_checkbox)

        sfx_row = QHBoxLayout(); sfx_row.setSpacing(6)
        sfx_lbl = QLabel("Test Procedural SFX:"); sfx_lbl.setFont(QFont("Courier New", 7)); sfx_lbl.setStyleSheet(f"color: {C.TEXT_MED};")
        sfx_row.addWidget(sfx_lbl)

        for sfx_name in ("boot", "wake", "ack", "confirm"):
            btn = QPushButton(sfx_name.upper())
            btn.setFixedHeight(22)
            btn.setFont(QFont("Courier New", 7))
            btn.setStyleSheet(f"background: #00121a; color: {C.PRI}; border: 1px solid {C.BORDER}; border-radius: 2px;")
            def _play(n=sfx_name):
                from core.sfx import play_sfx
                play_sfx(n)
            btn.clicked.connect(_play)
            sfx_row.addWidget(btn)
        lay_voice.addLayout(sfx_row)
        lay_voice.addStretch(1)
        self._stack.addWidget(page_voice)

        # ── Page 3: Telemetry & APIs Dashboard ─────────────────────────────────
        page_sys = QWidget()
        lay_sys = QVBoxLayout(page_sys)
        lay_sys.setContentsMargins(2, 2, 2, 2)
        lay_sys.setSpacing(4)

        _card_css = (f"background: rgba(0, 18, 26, 200); border: 1px solid {C.BORDER};"
                     f" border-radius: 4px; padding: 6px; color: {C.TEXT};")

        # Refresh button at top
        refresh_sys_btn = QPushButton("🔄  REFRESH ALL TELEMETRY")
        refresh_sys_btn.setFixedHeight(24)
        refresh_sys_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        refresh_sys_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_sys_btn.setStyleSheet(f"background: #001a24; color: {C.PRI}; border: 1px solid {C.PRI_DIM}; border-radius: 3px;")
        refresh_sys_btn.clicked.connect(self._refresh_system_metrics)
        lay_sys.addWidget(refresh_sys_btn)

        # Scroll area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }"
                             "QScrollBar:vertical { background: #000d12; width: 6px; }"
                             f"QScrollBar::handle:vertical {{ background: {C.BORDER}; border-radius: 3px; }}"
                             "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }")
        scroll_w = QWidget()
        self._telem_lay = QVBoxLayout(scroll_w)
        self._telem_lay.setContentsMargins(2, 2, 2, 2)
        self._telem_lay.setSpacing(5)

        # Card 1: 📍 Geo-Location & Network
        self._geo_card = QLabel("📍  GEO-LOCATION & NETWORK\n\n   Initialising location services…")
        self._geo_card.setFont(QFont("Courier New", 7))
        self._geo_card.setWordWrap(True)
        self._geo_card.setStyleSheet(_card_css)
        self._telem_lay.addWidget(self._geo_card)

        # Card 2: ⛅ Weather
        self._weather_card = QLabel("⛅  LIVE WEATHER\n\n   Fetching hyper-local forecast…")
        self._weather_card.setFont(QFont("Courier New", 7))
        self._weather_card.setWordWrap(True)
        self._weather_card.setStyleSheet(_card_css)
        self._telem_lay.addWidget(self._weather_card)

        # Card 3: 💾 Storage Drives
        self._drives_container = QWidget()
        self._drives_container.setStyleSheet(_card_css)
        self._drives_lay = QVBoxLayout(self._drives_container)
        self._drives_lay.setContentsMargins(4, 4, 4, 4)
        self._drives_lay.setSpacing(3)
        _drv_hdr = QLabel("💾  MULTI-DRIVE STORAGE ANALYZER")
        _drv_hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        _drv_hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; border: none;")
        self._drives_lay.addWidget(_drv_hdr)
        self._telem_lay.addWidget(self._drives_container)

        # Card 4: ⚡ Hardware Telemetry
        self._hw_card = QLabel("⚡  HARDWARE TELEMETRY\n\n   Reading system sensors…")
        self._hw_card.setFont(QFont("Courier New", 7))
        self._hw_card.setWordWrap(True)
        self._hw_card.setStyleSheet(_card_css)
        self._telem_lay.addWidget(self._hw_card)

        # Card 5: 📰 Developer News
        self._news_card = QLabel("📰  DEV NEWS FEED (HackerNews)\n\n   Loading top stories…")
        self._news_card.setFont(QFont("Courier New", 7))
        self._news_card.setWordWrap(True)
        self._news_card.setStyleSheet(_card_css)
        self._telem_lay.addWidget(self._news_card)

        self._telem_lay.addStretch(1)
        scroll.setWidget(scroll_w)
        lay_sys.addWidget(scroll)
        self._stack.addWidget(page_sys)

        # Tab Switching Logic
        def _set_tab(idx):
            self._stack.setCurrentIndex(idx)
            for i, b in enumerate((self._btn_tab_ai, self._btn_tab_voice, self._btn_tab_sys)):
                if i == idx:
                    b.setStyleSheet(f"background: {C.PRI_DIM}; color: #000; border: 1px solid {C.PRI}; border-radius: 3px;")
                else:
                    b.setStyleSheet(f"background: #00121a; color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 3px;")

        self._btn_tab_ai.clicked.connect(lambda: _set_tab(0))
        self._btn_tab_voice.clicked.connect(lambda: _set_tab(1))
        self._btn_tab_sys.clicked.connect(lambda: (_set_tab(2), self._refresh_system_metrics()))
        _set_tab(0)

        # Wire Signals
        self.voice_tested.connect(self._on_voice_tested)
        self.provider_tested.connect(self._on_provider_tested)

        # Dynamic TTS description update
        def _on_tts_change():
            eng = self._tts_combo.currentData() or ""
            if eng == "piper_hindi":
                self._voice_info_card.setText("⚡ Piper Hindi: 100% Offline Neural Speech\n   Devanagari script support | Zero latency | Zero cloud tokens")
            elif eng == "edgetts":
                self._voice_info_card.setText("🌐 EdgeTTS: Microsoft Azure Natural Voice (Guy/Swara)\n   Clear pronunciation | Requires active internet connection")
            elif eng == "gemini_live":
                self._voice_info_card.setText("🎙️ Gemini Live: Real-time bi-directional voice\n   Ultra-low latency streaming voice over WebSockets")
            elif eng == "kokoro":
                self._voice_info_card.setText("⚡ Kokoro TTS: 100% Offline English Neural (af_heart)\n   Warm conversational English tone")
        self._tts_combo.currentIndexChanged.connect(_on_tts_change)
        _on_tts_change()

        # Bottom Save and Cancel
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        save_btn = QPushButton("▸  SAVE PROVIDER & VOICE SETTINGS")
        save_btn.setFixedHeight(32)
        save_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton("CANCEL")
        cancel_btn.setFixedHeight(32)
        cancel_btn.setFont(QFont("Courier New", 8))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_DIM};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        cancel_btn.clicked.connect(self.hide)
        btn_row.addWidget(cancel_btn)

        main_lay.addLayout(btn_row)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)

    def _on_voice_tested(self, ok: bool, msg: str):
        self._voice_test_btn.setEnabled(True)
        if ok:
            self._voice_stat_lbl.setText(f"🟢 {msg}")
            self._voice_stat_lbl.setStyleSheet("color: #00ffaa;")
        else:
            self._voice_stat_lbl.setText(f"🔴 {msg}")
            self._voice_stat_lbl.setStyleSheet("color: #ff4444;")

    def _on_provider_tested(self, prov_id: str, ok: bool, msg: str, lat: float):
        badge = (
            self._gemini_stat if prov_id == "gemini" else (
                self._gemini_web_stat if prov_id == "gemini-web" else (
                    self._omni_stat if prov_id in ("omniroute", "omni") else (
                        self._groq_stat if prov_id == "groq" else (
                            self._openrouter_stat if prov_id == "openrouter" else (
                                self._deepseek_stat if prov_id == "deepseek" else self._custom_stat
                            )
                        )
                    )
                )
            )
        )
        if ok:
            badge.setText(f"🟢 {msg} ({lat:.0f}ms)")
            badge.setStyleSheet("color: #00ffaa;")
        else:
            badge.setText(f"🔴 {msg}")
            badge.setStyleSheet("color: #ff4444;")

    def _refresh_system_metrics(self):
        def _worker():
            try:
                from core.system_info import (
                    get_drive_stats, get_free_weather, get_ip_location,
                    get_hardware_telemetry, get_network_latency, fetch_top_dev_news,
                )
                geo = get_ip_location()
                weather = get_free_weather()
                drives = get_drive_stats()
                hw = get_hardware_telemetry()
                net = get_network_latency()
                news = fetch_top_dev_news()
                return {"geo": geo, "weather": weather, "drives": drives,
                        "hw": hw, "net": net, "news": news}
            except Exception:
                return {}

        def _bg():
            data = _worker()
            QTimer.singleShot(0, lambda: self._render_system_metrics(data))

        threading.Thread(target=_bg, daemon=True).start()

    def _render_system_metrics(self, data: dict):
        geo = data.get("geo", {})
        weather = data.get("weather", {})
        drives = data.get("drives", [])
        hw = data.get("hw", {})
        net = data.get("net", {})
        news = data.get("news", [])

        # ── Card 1: Geo-Location & Network ──
        ping_txt = f"🟢 {net.get('status', '--')}" if net.get("online") else "🔴 Offline"
        self._geo_card.setText(
            f"📍  GEO-LOCATION & NETWORK\n"
            f"   City       : {geo.get('city', '--')}\n"
            f"   Region     : {geo.get('region', '--')}, {geo.get('country', '--')}\n"
            f"   IP         : {geo.get('ip', '--')}\n"
            f"   ISP        : {geo.get('isp', '--')}\n"
            f"   Timezone   : {geo.get('timezone', '--')}\n"
            f"   Ping       : {ping_txt}"
        )

        # ── Card 2: Weather ──
        if weather.get("success"):
            self._weather_card.setText(
                f"{weather.get('icon', '⛅')}  LIVE WEATHER — {weather.get('city', 'Local')}\n"
                f"   Sky        : {weather.get('desc', '--')}\n"
                f"   Temp       : {weather.get('temp', '--')}  (Feels {weather.get('feels_like', '--')})\n"
                f"   Humidity   : {weather.get('humidity', '--')}\n"
                f"   Wind       : {weather.get('wind', '--')}\n"
                f"   Pressure   : {weather.get('pressure', '--')}"
            )
        else:
            self._weather_card.setText("⛅  LIVE WEATHER\n\n   Weather service unavailable (check internet)")

        # ── Card 3: Storage Drives ──
        # Clear old drive widgets but keep the header label (index 0)
        while self._drives_lay.count() > 1:
            item = self._drives_lay.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        for d in drives:
            d_card = QWidget()
            d_card.setStyleSheet("background: transparent; border: none;")
            d_box = QVBoxLayout(d_card); d_box.setContentsMargins(2, 1, 2, 1); d_box.setSpacing(1)
            row = QHBoxLayout()
            lbl = QLabel(f"  {d['letter']} {d.get('label', '')} — {d['free_gb']}GB free / {d['total_gb']}GB")
            lbl.setFont(QFont("Courier New", 7)); lbl.setStyleSheet(f"color: {C.TEXT}; border: none;")
            pct_lbl = QLabel(f"{d['percent']}%")
            pct_lbl.setFont(QFont("Courier New", 7))
            pct_lbl.setStyleSheet(f"color: {'#00ffaa' if d['percent'] < 80 else '#ff5533'}; border: none;")
            row.addWidget(lbl); row.addStretch(1); row.addWidget(pct_lbl)
            d_box.addLayout(row)
            pb = QProgressBar()
            pb.setFixedHeight(5); pb.setTextVisible(False)
            pb.setRange(0, 100); pb.setValue(int(d['percent']))
            pb.setStyleSheet(f"""
                QProgressBar {{ background: #00121a; border: 1px solid {C.BORDER}; border-radius: 2px; }}
                QProgressBar::chunk {{ background: {'#00ffff' if d['percent'] < 80 else '#ff5533'}; }}
            """)
            d_box.addWidget(pb)
            self._drives_lay.addWidget(d_card)

        # ── Card 4: Hardware Telemetry ──
        bat_str = "--"
        if hw.get("battery_percent") is not None:
            plug = "⚡" if hw.get("battery_plugged") else "🔋"
            bat_str = f"{plug} {hw['battery_percent']}%"
        self._hw_card.setText(
            f"⚡  HARDWARE TELEMETRY\n"
            f"   CPU        : {hw.get('cpu_percent', 0)}%  ({hw.get('cpu_cores', '-')} cores)\n"
            f"   RAM        : {hw.get('ram_used_gb', 0)}GB / {hw.get('ram_total_gb', 0)}GB  ({hw.get('ram_percent', 0)}%)\n"
            f"   Battery    : {bat_str}\n"
            f"   Uptime     : {hw.get('uptime_str', '--')}"
        )

        # ── Card 5: Developer News ──
        if news:
            lines = ["📰  DEV NEWS FEED (HackerNews)\n"]
            for i, n in enumerate(news[:4], 1):
                lines.append(f"   {i}. {n.get('title', '')[:55]}")
                lines.append(f"      ↑{n.get('score', 0)} • by {n.get('by', '?')}")
            self._news_card.setText("\n".join(lines))
        else:
            self._news_card.setText("📰  DEV NEWS FEED\n\n   No stories available")

    def _save(self):
        prov_id = self._provider_combo.currentData() or "gemini"
        try:
            from core.multi_llm import PROVIDER_REGISTRY
            data = _read_full_config()

            # Preserve core legacy inputs
            gem_key = ""
            if hasattr(self, "_gemini_input"):
                gem_key = self._gemini_input.text().strip()
                if gem_key:
                    data["gemini_api_key"] = gem_key

            # Auto-activate Gemini Live WebSocket Stream if Gemini key is provided
            if gem_key and (prov_id in ("gemini", "gemini-web") or not prov_id):
                prov_id = "gemini"
                data["preferred_llm_provider"] = "gemini"
            else:
                data["preferred_llm_provider"] = prov_id

            data["tts_engine"] = self._tts_combo.currentData() or "gemini_live"
            data["sfx_enabled"] = self._sfx_checkbox.isChecked()

            # Save chosen model for provider
            active_m = self._model_combo.currentText().strip()
            if "selected_models" not in data or not isinstance(data.get("selected_models"), dict):
                data["selected_models"] = {}
            if active_m:
                data["selected_models"][prov_id] = active_m
                data["custom_llm_model"] = active_m

            if hasattr(self, "_groq_input"):
                data["groq_api_key"] = self._groq_input.text().strip()
            if hasattr(self, "_openrouter_input"):
                data["openrouter_api_key"] = self._openrouter_input.text().strip()
            if hasattr(self, "_deepseek_input"):
                data["deepseek_api_key"] = self._deepseek_input.text().strip()
            if hasattr(self, "_custom_url"):
                data["custom_llm_url"] = self._custom_url.text().strip()

            # Save all dynamic registered provider keys
            if hasattr(self, "_key_inputs"):
                for p_name, inp in self._key_inputs.items():
                    val = inp.text().strip()
                    reg = PROVIDER_REGISTRY.get(p_name, {})
                    kfield = reg.get("key_field")
                    if kfield:
                        if val or kfield not in data:
                            data[kfield] = val
                        elif not val and kfield in data and p_name != "gemini":
                            data[kfield] = ""

            API_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
            try:
                from core.sfx import play_sfx
                play_sfx("confirm")
            except Exception:
                pass
        except Exception as e:
            print(f"Failed to save provider config: {e}")
        self.saved.emit(prov_id)
        self.hide()


class CustomizeOverlay(QWidget):
    """
    Next-Gen HUD Studio & Customisation Overlay.
    Tabs:
      1. 🎭 VISUALS & HUD: Multi-mode avatar engine (Celestial, Reactor, Orb, Matrix),
         Animation Dynamics (Reactive sleep-on-idle, subtle ambient, kinetic),
         HUD Bloom & Glow slider (10-100%), 1-Click Theme Presets, Particle density slider (20-400),
         and granular HUD FX toggles (Shockwaves, Starfield, Particles, Photons, Spectrum, Brackets, Scanlines).
      2. 🎨 COLOR WHEEL: Hue wheel + custom hex input + default palette reset.
      3. ⚙ IDENTITY & VOICE: Assistant name, user name, Gemini voice pills, and Stark SFX toggle.
    """

    saved = pyqtSignal(str, str, str, str, str, int, dict, bool, str, int, str, str, str, str, dict, str)
    _OW, _OH = 580, 640

    def __init__(self, assistant_name="JARVIS", user_name="",
                 ui_color=DEFAULT_UI_COLOR, voice="", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            CustomizeOverlay {{
                background: rgba(0, 6, 12, 250);
                border: 1px solid {C.BORDER_B};
                border-radius: 6px;
            }}
        """)
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(18, 14, 18, 14)
        main_lay.setSpacing(8)

        def _lbl(txt, fs=9, bold=False, color=C.PRI, align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt); w.setAlignment(align)
            w.setFont(QFont("Courier New", fs,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        _fs = (f"QLineEdit {{ background: #000d12; color: {C.TEXT}; "
               f"border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px; }}"
               f"QLineEdit:focus {{ border: 1px solid {C.PRI}; }}")

        # Initial Values
        self._initial_color = (ui_color or DEFAULT_UI_COLOR).strip().lower()
        self._sel_color     = self._initial_color
        self._initial_avatar_mode = get_avatar_mode()
        self._sel_avatar_mode     = self._initial_avatar_mode
        self._initial_anim_mode   = get_anim_mode()
        self._sel_anim_mode       = self._initial_anim_mode
        self._initial_hud_glow    = get_hud_glow()
        self._sel_hud_glow        = self._initial_hud_glow
        self._initial_density     = get_particle_density()
        self._sel_density         = self._initial_density
        self._initial_hud_fx      = dict(get_hud_fx())
        self._sel_hud_fx          = dict(self._initial_hud_fx)
        self._initial_sfx         = get_sfx_enabled()
        self._initial_persona     = get_persona_mode()
        self._sel_persona         = self._initial_persona
        self._initial_gender      = get_assistant_gender()
        self._sel_gender          = self._initial_gender
        self._initial_language    = get_preferred_language()
        self._sel_language        = self._initial_language
        self._initial_tts_engine  = get_tts_engine()
        self._sel_tts_engine      = self._initial_tts_engine
        self._initial_edge_voice  = get_edge_voice()
        self._sel_edge_voice      = self._initial_edge_voice
        self._initial_edge_pitch  = get_edge_pitch()
        self._sel_edge_pitch      = self._initial_edge_pitch
        self._obsidian_cfg        = dict(get_obsidian_config())

        # Preview Callbacks
        self.on_preview                  = None   # callable(hex)
        self.on_avatar_mode_preview      = None   # callable(mode)
        self.on_anim_mode_preview        = None   # callable(mode)
        self.on_hud_glow_preview         = None   # callable(glow)
        self.on_particle_density_preview = None   # callable(density)
        self.on_hud_fx_preview           = None   # callable(fx_dict)
        self.on_preview_expression       = None   # callable(expr_name)

        # Header Title (&& prevents Qt mnemonic parsing of & into underscore)
        main_lay.addWidget(_lbl("⚙  HUD STUDIO && CUSTOMISATION", 11, True))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        main_lay.addWidget(sep)

        # Tab Buttons
        tab_bar = QHBoxLayout(); tab_bar.setSpacing(4)
        self._tab_btn_presets = QPushButton("✨ 1-CLICK PRESETS")
        self._tab_btn_avatar  = QPushButton("🎭 VISUALS")
        self._tab_btn_color   = QPushButton("🎨 COLORS")
        self._tab_btn_ident   = QPushButton("⚙ IDENTITY")

        for b in (self._tab_btn_presets, self._tab_btn_avatar, self._tab_btn_color, self._tab_btn_ident):
            b.setFixedHeight(26)
            b.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            tab_bar.addWidget(b)
        main_lay.addLayout(tab_bar)

        self._stack = QStackedWidget()
        main_lay.addWidget(self._stack, 1)

        # ══════════════════════════════════════════════════════════════════════
        # TAB 0: ✨ 1-CLICK ALL-IN-ONE VIBE PRESETS
        # ══════════════════════════════════════════════════════════════════════
        scroll_presets = QScrollArea()
        scroll_presets.setWidgetResizable(True)
        scroll_presets.setFrameShape(QFrame.Shape.NoFrame)
        scroll_presets.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: #000d14; width: 6px; margin: 0px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 212, 255, 0.35); min-height: 20px; border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 212, 255, 0.75);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        page_presets = QWidget()
        lay_presets = QVBoxLayout(page_presets)
        lay_presets.setContentsMargins(4, 4, 8, 4)
        lay_presets.setSpacing(8)

        lay_presets.addWidget(_lbl("ONE-CLICK COMPLETE VIBE & PERSONALITY SETUPS", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        lay_presets.addWidget(_lbl("Instantly configure Theme, Voice, Pitch, Language, Avatar & Persona with 1 click:", 7, color=C.TEXT_MED, align=Qt.AlignmentFlag.AlignLeft))

        self._preset_status_lbl = QLabel("⚪ Click a preset below to instantly transform and save all settings.")
        self._preset_status_lbl.setFont(QFont("Courier New", 7))
        self._preset_status_lbl.setStyleSheet(f"color: {C.PRI}; padding: 3px 6px; background: #00121a; border: 1px solid {C.BORDER}; border-radius: 3px;")
        lay_presets.addWidget(self._preset_status_lbl)

        presets_data = [
            (
                "gf",
                "💖 DEVOTED GF SOULMATE",
                "#ff2a70",
                "Swara (Hi ♀) • +8Hz Sweet Pitch • Rose Neon • Quantum Orb • Hinglish",
                "Exclusively loyal girlfriend with Hinglish warmth, playful teasing, cute jealousy, and tender care routines.",
            ),
            (
                "jarvis",
                "🛡️ STARK JARVIS TACTICAL",
                "#00dcff",
                "Chris (US ♂) • -4Hz Deep Pitch • Stark Cyan • Arc Reactor • English",
                "Precision tactical engineering assistant with low-latency English cadence, HUD diagnostic telemetry, and system mastery.",
            ),
            (
                "devops",
                "⚡ ELITE DEVOPS BEAST",
                "#00ff88",
                "Madhur (Hi ♂) • +0Hz Normal • Matrix Green • Cyber Matrix • Hinglish",
                "High-throughput terminal and cloud infrastructure commander with containerized automation and troubleshooting focus.",
            ),
            (
                "mentor",
                "🎓 MENTOR & GURU",
                "#ffaa00",
                "Madhur (Hi ♂) • +0Hz Normal • Solar Gold • Planetary Halo • Hindi",
                "Patient, thoughtful mentor delivering structured explanations, conceptual depth, and academic guidance in clear Hindi.",
            ),
        ]

        for p_id, p_title, p_col, p_specs, p_desc in presets_data:
            box = QFrame()
            box.setStyleSheet(f"""
                QFrame {{
                    background: #00121a;
                    border: 1px solid {C.BORDER};
                    border-left: 3px solid {p_col};
                    border-radius: 4px;
                    padding: 4px;
                }}
                QFrame:hover {{
                    border-color: {p_col};
                    background: #001924;
                }}
            """)
            box_lay = QVBoxLayout(box)
            box_lay.setContentsMargins(6, 4, 6, 4)
            box_lay.setSpacing(2)

            top_row = QHBoxLayout()
            lbl_title = QLabel(p_title)
            lbl_title.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            lbl_title.setStyleSheet(f"color: {p_col};")
            top_row.addWidget(lbl_title)
            top_row.addStretch(1)

            btn_apply = QPushButton("APPLY VIBE")
            btn_apply.setFixedHeight(22)
            btn_apply.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_apply.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {p_col};
                    border: 1px solid {p_col}; border-radius: 2px; padding: 2px 10px;
                }}
                QPushButton:hover {{
                    background: {p_col}; color: #000;
                }}
            """)
            btn_apply.clicked.connect(lambda _=False, pk=p_id: self._apply_preset(pk))
            top_row.addWidget(btn_apply)
            box_lay.addLayout(top_row)

            lbl_specs = QLabel(p_specs)
            lbl_specs.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            lbl_specs.setStyleSheet("color: #ffffff;")
            box_lay.addWidget(lbl_specs)

            lbl_desc = QLabel(p_desc)
            lbl_desc.setWordWrap(True)
            lbl_desc.setFont(QFont("Courier New", 6))
            lbl_desc.setStyleSheet(f"color: {C.TEXT_MED};")
            box_lay.addWidget(lbl_desc)

            lay_presets.addWidget(box)

        lay_presets.addStretch(1)
        scroll_presets.setWidget(page_presets)
        self._stack.addWidget(scroll_presets)

        # ══════════════════════════════════════════════════════════════════════
        # TAB 1: 🎭 VISUALS && HUD (Avatar, Dynamics, Glow, Themes, FX)
        # ══════════════════════════════════════════════════════════════════════
        scroll_vis = QScrollArea()
        scroll_vis.setWidgetResizable(True)
        scroll_vis.setFrameShape(QFrame.Shape.NoFrame)
        scroll_vis.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: #000d14; width: 6px; margin: 0px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 212, 255, 0.35); min-height: 20px; border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 212, 255, 0.75);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        page_vis = QWidget()
        lay_vis = QVBoxLayout(page_vis)
        lay_vis.setContentsMargins(4, 4, 8, 4)
        lay_vis.setSpacing(8)

        # 1. Avatar Core Engine
        lay_vis.addWidget(_lbl("AVATAR CORE ENGINE", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        av_row = QHBoxLayout(); av_row.setSpacing(4)
        self._av_btns = {}
        av_modes = [
            ("celestial", "🌌 CELESTIAL"),
            ("reactor",   "⚛ ARC REACTOR"),
            ("orb",       "🔮 QUANTUM ORB"),
            ("matrix",    "🟢 MATRIX RAIN"),
        ]
        for mode_key, label in av_modes:
            b = QPushButton(label)
            b.setFixedHeight(28)
            b.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, mk=mode_key: self._on_avatar_mode_pick(mk))
            self._av_btns[mode_key] = b
            av_row.addWidget(b)
        lay_vis.addLayout(av_row)
        self._refresh_avatar_btns()

        # 2. Animation Dynamics (Idle Standby vs Activity)
        lay_vis.addWidget(_lbl("ANIMATION DYNAMICS (STANDBY BEHAVIOR)", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        dyn_row = QHBoxLayout(); dyn_row.setSpacing(4)
        self._dyn_btns = {}
        dyn_modes = [
            ("reactive", "🌙 SLEEP ON IDLE (REACTIVE)"),
            ("subtle",   "🍃 SUBTLE AMBIENT"),
            ("kinetic",  "⚡ FULL KINETIC"),
        ]
        for d_key, d_label in dyn_modes:
            db = QPushButton(d_label)
            db.setFixedHeight(26)
            db.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            db.setCursor(Qt.CursorShape.PointingHandCursor)
            db.clicked.connect(lambda _=False, dk=d_key: self._on_anim_mode_pick(dk))
            self._dyn_btns[d_key] = db
            dyn_row.addWidget(db)
        lay_vis.addLayout(dyn_row)
        self._refresh_dyn_btns()

        # 3. HUD Glow & Bloom Intensity
        self._glow_lbl = _lbl(f"HUD GLOW && BLOOM INTENSITY: {self._sel_hud_glow}%", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft)
        lay_vis.addWidget(self._glow_lbl)

        self._glow_slider = QSlider(Qt.Orientation.Horizontal)
        self._glow_slider.setRange(10, 100)
        self._glow_slider.setSingleStep(5)
        self._glow_slider.setValue(self._sel_hud_glow)
        self._glow_slider.setFixedHeight(22)
        self._glow_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px; background: #001520; border: 1px solid {C.BORDER}; border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{ background: {C.PRI}; border-radius: 2px; }}
            QSlider::handle:horizontal {{
                background: {C.WHITE}; border: 1px solid {C.PRI}; width: 14px; margin: -5px 0; border-radius: 7px;
            }}
        """)
        self._glow_slider.valueChanged.connect(self._on_glow_changed)
        lay_vis.addWidget(self._glow_slider)

        # 4. Theme Presets (1-Click Color Sync)
        lay_vis.addWidget(_lbl("THEME PRESETS (1-CLICK COLOR SYNC)", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        theme_row = QHBoxLayout(); theme_row.setSpacing(4)
        presets = [
            ("☀️ Gold",    "#ffcc33"),
            ("⚡ Cyan",    "#00e5ff"),
            ("🌿 Emerald", "#00ffaa"),
            ("🔮 Violet",  "#b366ff"),
            ("🔥 Crimson", "#ff3355"),
            ("❄️ Arctic",  "#d8f8ff"),
            ("🌌 Nebula",  "#a855f7"),
        ]
        for t_name, t_hex in presets:
            tb = QPushButton(t_name)
            tb.setFixedHeight(24)
            tb.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            tb.setCursor(Qt.CursorShape.PointingHandCursor)
            tb.setStyleSheet(f"""
                QPushButton {{
                    background: #00121a; color: {t_hex};
                    border: 1px solid {t_hex}; border-radius: 3px;
                }}
                QPushButton:hover {{ background: {t_hex}; color: #000; }}
            """)
            tb.clicked.connect(lambda _=False, hx=t_hex: self._set_color(hx))
            theme_row.addWidget(tb)
        lay_vis.addLayout(theme_row)

        # 5. Particle Density Slider
        self._density_lbl = _lbl(f"PARTICLE DENSITY: {self._sel_density} PARTICLES", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft)
        lay_vis.addWidget(self._density_lbl)

        self._density_slider = QSlider(Qt.Orientation.Horizontal)
        self._density_slider.setRange(20, 400)
        self._density_slider.setSingleStep(10)
        self._density_slider.setValue(self._sel_density)
        self._density_slider.setFixedHeight(22)
        self._density_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px; background: #001520; border: 1px solid {C.BORDER}; border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{ background: {C.PRI}; border-radius: 2px; }}
            QSlider::handle:horizontal {{
                background: {C.WHITE}; border: 1px solid {C.PRI}; width: 14px; margin: -5px 0; border-radius: 7px;
            }}
        """)
        self._density_slider.valueChanged.connect(self._on_density_changed)
        lay_vis.addWidget(self._density_slider)

        # 6. HUD Visual FX Toggles
        lay_vis.addWidget(_lbl("HUD VISUAL FX MODULES", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))

        chk_col1 = QVBoxLayout(); chk_col1.setSpacing(4)
        chk_col2 = QVBoxLayout(); chk_col2.setSpacing(4)
        _chk_style = f"QCheckBox {{ color: {C.TEXT}; font-family: 'Courier New'; font-size: 8pt; }} QCheckBox::indicator:checked {{ background: {C.PRI}; border: 1px solid {C.PRI}; }}"

        self._chk_shockwaves = QCheckBox("Vocal Energy Shockwaves")
        self._chk_shockwaves.setChecked(self._sel_hud_fx.get("shockwaves", True))
        self._chk_shockwaves.setStyleSheet(_chk_style)
        self._chk_shockwaves.stateChanged.connect(self._on_fx_toggle)
        chk_col1.addWidget(self._chk_shockwaves)

        self._chk_starfield = QCheckBox("Deep Space Starfield Grid")
        self._chk_starfield.setChecked(self._sel_hud_fx.get("starfield", True))
        self._chk_starfield.setStyleSheet(_chk_style)
        self._chk_starfield.stateChanged.connect(self._on_fx_toggle)
        chk_col1.addWidget(self._chk_starfield)

        self._chk_particles = QCheckBox("Floating Stardust Particles")
        self._chk_particles.setChecked(self._sel_hud_fx.get("particles", True))
        self._chk_particles.setStyleSheet(_chk_style)
        self._chk_particles.stateChanged.connect(self._on_fx_toggle)
        chk_col1.addWidget(self._chk_particles)

        self._chk_photons = QCheckBox("Orbiting Starlight Photons")
        self._chk_photons.setChecked(self._sel_hud_fx.get("photons", True))
        self._chk_photons.setStyleSheet(_chk_style)
        self._chk_photons.stateChanged.connect(self._on_fx_toggle)
        chk_col1.addWidget(self._chk_photons)

        self._chk_spectrum = QCheckBox("Voice Waveform Spectrum")
        self._chk_spectrum.setChecked(self._sel_hud_fx.get("spectrum", True))
        self._chk_spectrum.setStyleSheet(_chk_style)
        self._chk_spectrum.stateChanged.connect(self._on_fx_toggle)
        chk_col2.addWidget(self._chk_spectrum)

        self._chk_brackets = QCheckBox("Tactical Framing Brackets")
        self._chk_brackets.setChecked(self._sel_hud_fx.get("brackets", True))
        self._chk_brackets.setStyleSheet(_chk_style)
        self._chk_brackets.stateChanged.connect(self._on_fx_toggle)
        chk_col2.addWidget(self._chk_brackets)

        self._chk_scanlines = QCheckBox("Retro CRT Scanlines")
        self._chk_scanlines.setChecked(self._sel_hud_fx.get("scanlines", False))
        self._chk_scanlines.setStyleSheet(_chk_style)
        self._chk_scanlines.stateChanged.connect(self._on_fx_toggle)
        chk_col2.addWidget(self._chk_scanlines)

        fx_row = QHBoxLayout(); fx_row.setSpacing(12)
        fx_row.addLayout(chk_col1)
        fx_row.addLayout(chk_col2)
        lay_vis.addLayout(fx_row)

        lay_vis.addStretch(1)
        scroll_vis.setWidget(page_vis)
        self._stack.addWidget(scroll_vis)

        # ══════════════════════════════════════════════════════════════════════
        # TAB 2: 🎨 COLOR WHEEL (Custom Hue Wheel + Hex Input)
        # ══════════════════════════════════════════════════════════════════════
        page_col = QWidget()
        lay_col = QVBoxLayout(page_col)
        lay_col.setContentsMargins(4, 4, 4, 4)
        lay_col.setSpacing(8)

        clr_hdr = QHBoxLayout()
        clr_hdr.addWidget(_lbl("DRAG WHEEL HANDLE OR ENTER HEX CODE", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        clr_hdr.addStretch()
        df_btn = QPushButton("RESET DEFAULT")
        df_btn.setFixedSize(96, 20)
        df_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        df_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        df_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        df_btn.clicked.connect(lambda: self._set_color(DEFAULT_UI_COLOR))
        clr_hdr.addWidget(df_btn)
        lay_col.addLayout(clr_hdr)

        self._wheel = HueWheel(self._sel_color)
        wheel_row = QHBoxLayout()
        wheel_row.addStretch(); wheel_row.addWidget(self._wheel); wheel_row.addStretch()
        lay_col.addLayout(wheel_row)
        self._wheel.hue_picked.connect(self._on_wheel_pick)
        self._wheel.hue_committed.connect(self._on_wheel_commit)

        self._hex_input = QLineEdit(self._sel_color)
        self._hex_input.setPlaceholderText("#00d4ff   (custom hex colour)")
        self._hex_input.setFont(QFont("Courier New", 10))
        self._hex_input.setFixedHeight(28)
        self._hex_input.setStyleSheet(_fs)
        self._hex_input.textEdited.connect(self._on_hex_edited)
        lay_col.addWidget(self._hex_input)

        lay_col.addStretch(1)
        self._stack.addWidget(page_col)

        # ══════════════════════════════════════════════════════════════════════
        # TAB 3: ⚙ IDENTITY && VOICE (Persona, Gender, Audio Engines, Obsidian)
        # ══════════════════════════════════════════════════════════════════════
        scroll_id = QScrollArea()
        scroll_id.setWidgetResizable(True)
        scroll_id.setFrameShape(QFrame.Shape.NoFrame)
        scroll_id.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: #000d14; width: 6px; margin: 0px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 212, 255, 0.35); min-height: 20px; border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(0, 212, 255, 0.75);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        page_id = QWidget()
        lay_id = QVBoxLayout(page_id)
        lay_id.setContentsMargins(4, 4, 8, 4)
        lay_id.setSpacing(7)

        # 1. Identity Names
        lay_id.addWidget(_lbl("ASSISTANT NAME", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._name_input = QLineEdit(assistant_name)
        self._name_input.setFont(QFont("Courier New", 10))
        self._name_input.setFixedHeight(28)
        self._name_input.setStyleSheet(_fs)
        lay_id.addWidget(self._name_input)

        lay_id.addWidget(_lbl("YOUR NAME (for personalized salutation)", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._user_input = QLineEdit(user_name)
        self._user_input.setPlaceholderText("e.g. Tony (leave blank for auto)")
        self._user_input.setFont(QFont("Courier New", 10))
        self._user_input.setFixedHeight(28)
        self._user_input.setStyleSheet(_fs)
        lay_id.addWidget(self._user_input)

        # 2. AI Persona Selector
        lay_id.addWidget(_lbl("AI PERSONA && CHARACTER MODE", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        p_row1 = QHBoxLayout(); p_row1.setSpacing(4)
        p_row2 = QHBoxLayout(); p_row2.setSpacing(4)
        self._persona_btns = {}
        personas = [
            ("jarvis", "🛡️ JARVIS (Tactical AI)", p_row1),
            ("teacher", "🎓 TEACHER (Mentor)", p_row1),
            ("companion", "💖 GF SOULMATE (Romantic)", p_row2),
            ("devops", "⚡ DEVOPS (Cloud)", p_row2),
        ]
        for p_key, p_label, target_row in personas:
            b = QPushButton(p_label)
            b.setFixedHeight(26)
            b.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, pk=p_key: self._on_persona_pick(pk))
            self._persona_btns[p_key] = b
            target_row.addWidget(b)
        lay_id.addLayout(p_row1)
        lay_id.addLayout(p_row2)
        self._refresh_persona_btns()

        # 3. Assistant Gender & Hindi Grammar
        lay_id.addWidget(_lbl("ASSISTANT GENDER && GRAMMAR (Verb Conjugation)", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        lay_id.addWidget(_lbl("• Male: करता हूँ, बोलूँगा, आया हूँ   |   • Female: करती हूँ, बोलूँगी, आई हूँ", 7, color=C.TEXT_MED, align=Qt.AlignmentFlag.AlignLeft))
        gen_row = QHBoxLayout(); gen_row.setSpacing(4)
        self._gender_btns = {}
        for g_key, g_label in [("male", "♂️ MALE ASSISTANT"), ("female", "♀️ FEMALE ASSISTANT")]:
            b = QPushButton(g_label)
            b.setFixedHeight(26)
            b.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, gk=g_key: self._on_gender_pick(gk))
            self._gender_btns[g_key] = b
            gen_row.addWidget(b)
        lay_id.addLayout(gen_row)
        self._refresh_gender_btns()

        # 3b. Preferred Conversation Language
        lay_id.addWidget(_lbl("PREFERRED CONVERSATION LANGUAGE", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        lang_row = QHBoxLayout(); lang_row.setSpacing(4)
        self._lang_btns = {}
        languages = [
            ("hinglish", "🇮🇳 HINGLISH"),
            ("hindi", "🇮🇳 HINDI"),
            ("english", "🇬🇧 ENGLISH"),
            ("auto", "🌐 AUTO"),
        ]
        for l_key, l_label in languages:
            b = QPushButton(l_label)
            b.setFixedHeight(26)
            b.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, lk=l_key: self._on_language_pick(lk))
            self._lang_btns[l_key] = b
            lang_row.addWidget(b)
        lay_id.addLayout(lang_row)
        self._refresh_language_btns()

        # 4. Speech Engine Selector
        lay_id.addWidget(_lbl("SPEECH AUDIO ENGINE", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        tts_row = QHBoxLayout(); tts_row.setSpacing(4)
        self._tts_btns = {}
        tts_engines = [
            ("edge_tts", "⚡ EDGE-TTS (Neural)"),
            ("piper", "🎙️ PIPER (Offline)"),
            ("gemini", "🌐 GEMINI LIVE"),
        ]
        for eng_key, eng_label in tts_engines:
            b = QPushButton(eng_label)
            b.setFixedHeight(26)
            b.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, ek=eng_key: self._on_tts_engine_pick(ek))
            self._tts_btns[eng_key] = b
            tts_row.addWidget(b)
        lay_id.addLayout(tts_row)
        self._refresh_tts_engine_btns()

        # 5. Edge-TTS Voices
        lay_id.addWidget(_lbl("EDGE-TTS VOICES (Free, Ultra-Realistic & Expressive)", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        ev_row = QHBoxLayout(); ev_row.setSpacing(4)
        self._edge_voice_btns = {}
        edge_voices = [
            ("hi-IN-MadhurNeural", "Madhur (Hi ♂)"),
            ("hi-IN-SwaraNeural", "Swara (Hi ♀)"),
            ("en-US-ChristopherNeural", "Chris (US ♂)"),
            ("en-US-JennyNeural", "Jenny (US ♀)"),
        ]
        for ev_key, ev_label in edge_voices:
            b = QPushButton(ev_label)
            b.setFixedHeight(24)
            b.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, vk=ev_key: self._on_edge_voice_pick(vk))
            self._edge_voice_btns[ev_key] = b
            ev_row.addWidget(b)
        lay_id.addLayout(ev_row)
        self._refresh_edge_voice_btns()

        # 5b. Voice Pitch & Tone Modulation (Autonomous / Custom)
        lay_id.addWidget(_lbl("VOICE PITCH & TONE (Customizable / GF Mode / Deep)", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        pitch_row = QHBoxLayout(); pitch_row.setSpacing(4)
        self._pitch_btns = {}
        pitch_options = [
            ("+0Hz", "0Hz (Default)"),
            ("+8Hz", "💖 +8Hz (Cute GF)"),
            ("+14Hz", "✨ +14Hz (Sweet)"),
            ("-8Hz", "🛡️ -8Hz (Deep)"),
        ]
        for p_val, p_lbl_txt in pitch_options:
            b = QPushButton(p_lbl_txt)
            b.setFixedHeight(24)
            b.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, pv=p_val: self._on_edge_pitch_pick(pv))
            self._pitch_btns[p_val] = b
            pitch_row.addWidget(b)
        lay_id.addLayout(pitch_row)
        self._refresh_edge_pitch_btns()

        # 6. Gemini Voices
        from memory.config_manager import AVAILABLE_VOICES, DEFAULT_VOICE
        lay_id.addWidget(_lbl("GEMINI LIVE VOICES (When using Gemini Live audio)", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._sel_voice = (voice or DEFAULT_VOICE)
        if self._sel_voice not in AVAILABLE_VOICES:
            self._sel_voice = DEFAULT_VOICE
        self._voice_btns = {}
        voice_row = QHBoxLayout(); voice_row.setSpacing(4)
        for _v in AVAILABLE_VOICES:
            b = QPushButton(_v)
            b.setCheckable(True)
            b.setFixedHeight(24)
            b.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, name=_v: self._on_voice_pick(name))
            self._voice_btns[_v] = b
            voice_row.addWidget(b)
        lay_id.addLayout(voice_row)
        self._refresh_voice_btns()

        # 7. Stark SFX Checkbox
        self._chk_sfx = QCheckBox("Enable Stark Tactical Audio Feedback (SFX)")
        self._chk_sfx.setChecked(self._initial_sfx)
        self._chk_sfx.setStyleSheet(_chk_style)
        lay_id.addWidget(self._chk_sfx)

        # 8. Obsidian Second-Brain Integration
        sep_obs = QFrame(); sep_obs.setFrameShape(QFrame.Shape.HLine)
        sep_obs.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;"); lay_id.addWidget(sep_obs)

        lay_id.addWidget(_lbl("OBSIDIAN SECOND BRAIN INTEGRATION (Local REST API && Vault)", 8, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._chk_obsidian = QCheckBox("Enable Obsidian Second Brain Dual-Sync")
        self._chk_obsidian.setChecked(self._obsidian_cfg.get("enabled", True))
        self._chk_obsidian.setStyleSheet(_chk_style)
        lay_id.addWidget(self._chk_obsidian)

        obs_row1 = QHBoxLayout(); obs_row1.setSpacing(6)
        obs_row1.addWidget(_lbl("PORT:", 7, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._obs_port_input = QLineEdit(str(self._obsidian_cfg.get("port", 27124)))
        self._obs_port_input.setFixedWidth(64)
        self._obs_port_input.setFixedHeight(24)
        self._obs_port_input.setStyleSheet(_fs)
        obs_row1.addWidget(self._obs_port_input)

        self._chk_obs_https = QCheckBox("Use HTTPS")
        self._chk_obs_https.setChecked(self._obsidian_cfg.get("use_https", True))
        self._chk_obs_https.setStyleSheet(_chk_style)
        obs_row1.addWidget(self._chk_obs_https)
        obs_row1.addStretch()
        lay_id.addLayout(obs_row1)

        lay_id.addWidget(_lbl("OBSIDIAN REST API BEARER TOKEN", 7, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._obs_key_input = QLineEdit(self._obsidian_cfg.get("api_key", ""))
        self._obs_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._obs_key_input.setPlaceholderText("Paste Bearer Token from Obsidian Local REST API...")
        self._obs_key_input.setFixedHeight(26)
        self._obs_key_input.setStyleSheet(_fs)
        lay_id.addWidget(self._obs_key_input)

        lay_id.addWidget(_lbl("LOCAL VAULT FOLDER PATH (Fallback)", 7, color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._obs_vault_input = QLineEdit(self._obsidian_cfg.get("vault_path", ""))
        self._obs_vault_input.setPlaceholderText("e.g. C:/Users/Documents/ObsidianVault")
        self._obs_vault_input.setFixedHeight(26)
        self._obs_vault_input.setStyleSheet(_fs)
        lay_id.addWidget(self._obs_vault_input)

        obs_test_row = QHBoxLayout(); obs_test_row.setSpacing(6)
        self._obs_test_btn = QPushButton("⚡ TEST OBSIDIAN CONNECTION")
        self._obs_test_btn.setFixedHeight(26)
        self._obs_test_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        self._obs_test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._obs_test_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 2px 8px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
        """)
        self._obs_test_btn.clicked.connect(self._test_obsidian)
        obs_test_row.addWidget(self._obs_test_btn)

        self._obs_status_lbl = QLabel("")
        self._obs_status_lbl.setFont(QFont("Courier New", 7))
        self._obs_status_lbl.setStyleSheet(f"color: {C.TEXT_DIM};")
        obs_test_row.addWidget(self._obs_status_lbl, 1)
        lay_id.addLayout(obs_test_row)

        lay_id.addStretch(1)
        scroll_id.setWidget(page_id)
        self._stack.addWidget(scroll_id)

        # Tab Switching Handler
        def _set_tab(idx: int):
            self._stack.setCurrentIndex(idx)
            for i, b in enumerate((self._tab_btn_presets, self._tab_btn_avatar, self._tab_btn_color, self._tab_btn_ident)):
                if i == idx:
                    b.setStyleSheet(f"background: {C.PRI_DIM}; color: #000; border: 1px solid {C.PRI}; border-radius: 3px;")
                else:
                    b.setStyleSheet(f"background: #00121a; color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 3px;")

        self._tab_btn_presets.clicked.connect(lambda: _set_tab(0))
        self._tab_btn_avatar.clicked.connect(lambda: _set_tab(1))
        self._tab_btn_color.clicked.connect(lambda: _set_tab(2))
        self._tab_btn_ident.clicked.connect(lambda: _set_tab(3))
        _set_tab(0)

        # Bottom Actions
        main_lay.addSpacing(4)
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)

        save_btn = QPushButton("▸  APPLY && SAVE ALL")
        save_btn.setFixedHeight(34)
        save_btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: #001f2e; color: {C.PRI};
                border: 1px solid {C.PRI}; border-radius: 3px;
            }}
            QPushButton:hover {{ background: {C.PRI}; color: #000; }}
        """)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton("CANCEL")
        cancel_btn.setFixedHeight(34)
        cancel_btn.setFont(QFont("Courier New", 9))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        cancel_btn.clicked.connect(self._cancel)
        btn_row.addWidget(cancel_btn)
        main_lay.addLayout(btn_row)

    # ── 1-Click Persona & Vibe Presets ──────────────────────────────────────
    def _apply_preset(self, p_key: str):
        presets = {
            "gf": {
                "color": "#ff2a70",
                "avatar": "orb",
                "voice": "hi-IN-SwaraNeural",
                "pitch": "+8Hz",
                "persona": "companion",
                "gender": "female",
                "lang": "hinglish",
                "tts": "edge",
                "name": "Friday",
                "glow": 90,
                "msg": "💖 Devoted GF Soulmate Preset applied & persisted!",
            },
            "jarvis": {
                "color": "#00dcff",
                "avatar": "arc_reactor",
                "voice": "en-US-ChristopherNeural",
                "pitch": "-4Hz",
                "persona": "jarvis",
                "gender": "male",
                "lang": "english",
                "tts": "edge",
                "name": "JARVIS",
                "glow": 80,
                "msg": "🛡️ Stark JARVIS Tactical Preset applied & persisted!",
            },
            "devops": {
                "color": "#00ff88",
                "avatar": "cyber_matrix",
                "voice": "hi-IN-MadhurNeural",
                "pitch": "+0Hz",
                "persona": "devops",
                "gender": "male",
                "lang": "hinglish",
                "tts": "edge",
                "name": "Matrix",
                "glow": 85,
                "msg": "⚡ Elite DevOps Beast Preset applied & persisted!",
            },
            "mentor": {
                "color": "#ffaa00",
                "avatar": "halo",
                "voice": "hi-IN-MadhurNeural",
                "pitch": "+0Hz",
                "persona": "teacher",
                "gender": "male",
                "lang": "hindi",
                "tts": "edge",
                "name": "Guru",
                "glow": 75,
                "msg": "🎓 Mentor & Guru Preset applied & persisted!",
            },
        }
        cfg = presets.get(p_key)
        if not cfg:
            return

        if hasattr(self, "_name_input") and cfg.get("name"):
            self._name_input.setText(cfg["name"])

        self._on_avatar_mode_pick(cfg["avatar"])
        self._on_persona_pick(cfg["persona"])
        self._on_gender_pick(cfg["gender"])
        self._on_language_pick(cfg["lang"])
        self._on_tts_engine_pick(cfg["tts"])
        self._on_edge_voice_pick(cfg["voice"])
        self._on_edge_pitch_pick(cfg["pitch"])
        self._set_color(cfg["color"], update_wheel=True, preview=True)
        self._on_glow_changed(cfg["glow"])

        if p_key == "gf" and self.on_preview_expression:
            self.on_preview_expression("love")
        elif self.on_preview_expression:
            self.on_preview_expression("tactical")

        self._save()

    # ── Avatar mode pick & refresh ───────────────────────────────────────────
    def _on_avatar_mode_pick(self, mode: str):
        self._sel_avatar_mode = mode
        self._refresh_avatar_btns()
        if self.on_avatar_mode_preview:
            self.on_avatar_mode_preview(mode)

    def _refresh_avatar_btns(self):
        for mode, b in self._av_btns.items():
            on = (mode == self._sel_avatar_mode)
            if on:
                b.setStyleSheet(f"background: {C.PRI_DIM}; color: #000; border: 1px solid {C.PRI}; border-radius: 3px;")
            else:
                b.setStyleSheet(f"background: #00121a; color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 3px;")

    # ── Animation Dynamics pick & refresh ────────────────────────────────────
    def _on_anim_mode_pick(self, mode: str):
        self._sel_anim_mode = mode
        self._refresh_dyn_btns()
        if self.on_anim_mode_preview:
            self.on_anim_mode_preview(mode)

    def _refresh_dyn_btns(self):
        for mode, b in self._dyn_btns.items():
            on = (mode == self._sel_anim_mode)
            if on:
                b.setStyleSheet(f"background: {C.PRI_DIM}; color: #000; border: 1px solid {C.PRI}; border-radius: 3px;")
            else:
                b.setStyleSheet(f"background: #00121a; color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 3px;")

    # ── Glow & Density & FX handlers ─────────────────────────────────────────
    def _on_glow_changed(self, val: int):
        self._sel_hud_glow = val
        self._glow_lbl.setText(f"HUD GLOW && BLOOM INTENSITY: {val}%")
        if self.on_hud_glow_preview:
            self.on_hud_glow_preview(val)

    def _on_density_changed(self, val: int):
        self._sel_density = val
        self._density_lbl.setText(f"PARTICLE DENSITY: {val} PARTICLES")
        if self.on_particle_density_preview:
            self.on_particle_density_preview(val)

    def _on_fx_toggle(self):
        self._sel_hud_fx = {
            "shockwaves": self._chk_shockwaves.isChecked(),
            "starfield": self._chk_starfield.isChecked(),
            "particles": self._chk_particles.isChecked(),
            "photons": self._chk_photons.isChecked(),
            "spectrum": self._chk_spectrum.isChecked(),
            "brackets": self._chk_brackets.isChecked(),
            "scanlines": self._chk_scanlines.isChecked(),
        }
        if self.on_hud_fx_preview:
            self.on_hud_fx_preview(self._sel_hud_fx)

    # ── Voice selection ──────────────────────────────────────────────────────
    def _on_voice_pick(self, name: str):
        self._sel_voice = name
        self._refresh_voice_btns()

    def _refresh_voice_btns(self):
        for name, b in self._voice_btns.items():
            on = (name == self._sel_voice)
            b.setChecked(on)
            if on:
                b.setStyleSheet(f"background: {C.PRI_GHO}; color: {C.PRI}; border: 1px solid {C.PRI}; border-radius: 3px;")
            else:
                b.setStyleSheet(f"background: transparent; color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 3px;")

    # ── Persona selection ──────────────────────────────────────────────────
    def _on_persona_pick(self, mode: str):
        self._sel_persona = mode
        self._refresh_persona_btns()

    def _refresh_persona_btns(self):
        for mode, b in self._persona_btns.items():
            on = (mode == self._sel_persona)
            if on:
                b.setStyleSheet(f"background: {C.PRI_DIM}; color: #000; border: 1px solid {C.PRI}; border-radius: 3px;")
            else:
                b.setStyleSheet(f"background: #00121a; color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 3px;")

    # ── Gender selection ───────────────────────────────────────────────────
    def _on_gender_pick(self, g: str):
        self._sel_gender = g
        self._refresh_gender_btns()

    def _refresh_gender_btns(self):
        for g, b in self._gender_btns.items():
            on = (g == self._sel_gender)
            if on:
                b.setStyleSheet(f"background: {C.PRI_DIM}; color: #000; border: 1px solid {C.PRI}; border-radius: 3px;")
            else:
                b.setStyleSheet(f"background: #00121a; color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 3px;")

    # ── Language selection ─────────────────────────────────────────────────
    def _on_language_pick(self, lang: str):
        self._sel_language = lang
        self._refresh_language_btns()

    def _refresh_language_btns(self):
        for l_key, b in self._lang_btns.items():
            on = (l_key == self._sel_language)
            if on:
                b.setStyleSheet(f"background: {C.PRI_DIM}; color: #000; border: 1px solid {C.PRI}; border-radius: 3px;")
            else:
                b.setStyleSheet(f"background: #00121a; color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 3px;")

    # ── Speech engine selection ────────────────────────────────────────────
    def _on_tts_engine_pick(self, eng: str):
        self._sel_tts_engine = eng
        self._refresh_tts_engine_btns()

    def _refresh_tts_engine_btns(self):
        for eng, b in self._tts_btns.items():
            on = (eng == self._sel_tts_engine)
            if on:
                b.setStyleSheet(f"background: {C.PRI_DIM}; color: #000; border: 1px solid {C.PRI}; border-radius: 3px;")
            else:
                b.setStyleSheet(f"background: #00121a; color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 3px;")

    # ── Edge-TTS voice selection ───────────────────────────────────────────
    def _on_edge_voice_pick(self, voice_id: str):
        self._sel_edge_voice = voice_id
        self._refresh_edge_voice_btns()

    def _refresh_edge_voice_btns(self):
        for vid, b in self._edge_voice_btns.items():
            on = (vid == self._sel_edge_voice)
            if on:
                b.setStyleSheet(f"background: {C.PRI_GHO}; color: {C.PRI}; border: 1px solid {C.PRI}; border-radius: 3px;")
            else:
                b.setStyleSheet(f"background: transparent; color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 3px;")

    # ── Edge-TTS pitch selection ───────────────────────────────────────────
    def _on_edge_pitch_pick(self, pitch_val: str):
        self._sel_edge_pitch = pitch_val
        self._refresh_edge_pitch_btns()

    def _refresh_edge_pitch_btns(self):
        for pv, b in getattr(self, "_pitch_btns", {}).items():
            on = (pv == self._sel_edge_pitch)
            if on:
                b.setStyleSheet(f"background: {C.PRI_GHO}; color: {C.PRI}; border: 1px solid {C.PRI}; border-radius: 3px;")
            else:
                b.setStyleSheet(f"background: transparent; color: {C.TEXT_MED}; border: 1px solid {C.BORDER}; border-radius: 3px;")

    # ── Obsidian test connection ───────────────────────────────────────────
    def _test_obsidian(self):
        try:
            self._obs_status_lbl.setText("Testing connection...")
            self._obs_status_lbl.setStyleSheet(f"color: {C.PRI};")
            from actions.obsidian_brain import test_connection
            self._obsidian_cfg["api_key"] = self._obs_key_input.text().strip()
            try:
                self._obsidian_cfg["port"] = int(self._obs_port_input.text().strip())
            except ValueError:
                self._obsidian_cfg["port"] = 27124
            self._obsidian_cfg["vault_path"] = self._obs_vault_input.text().strip()
            self._obsidian_cfg["use_https"] = self._chk_obs_https.isChecked()
            save_obsidian_config(self._obsidian_cfg)

            ok, msg = test_connection()
            if ok:
                self._obs_status_lbl.setText(f"✓ {msg}")
                self._obs_status_lbl.setStyleSheet("color: #00ff88;")
            else:
                self._obs_status_lbl.setText(f"✗ {msg}")
                self._obs_status_lbl.setStyleSheet("color: #ff3b30;")
        except Exception as e:
            self._obs_status_lbl.setText(f"✗ Error: {e}")
            self._obs_status_lbl.setStyleSheet("color: #ff3b30;")

    # ── Color flow ───────────────────────────────────────────────────────────
    def _set_color(self, hx: str, update_wheel: bool = True, preview: bool = True):
        self._sel_color = hx.strip().lower()
        self._hex_input.blockSignals(True)
        self._hex_input.setText(self._sel_color)
        self._hex_input.blockSignals(False)
        if update_wheel:
            self._wheel.set_color(self._sel_color)
        if preview and self.on_preview:
            self.on_preview(self._sel_color)

    def _on_wheel_pick(self, hx: str):
        self._sel_color = hx
        self._hex_input.blockSignals(True)
        self._hex_input.setText(hx)
        self._hex_input.blockSignals(False)

    def _on_wheel_commit(self, hx: str):
        self._set_color(hx, update_wheel=False)

    def _on_hex_edited(self, text: str):
        t = text.strip().lower()
        if t.startswith("#") and len(t) == 7:
            try:
                int(t[1:], 16)
            except ValueError:
                return
            self._set_color(t, update_wheel=True, preview=True)

    def _cancel(self):
        # Revert all live previews back to initial state
        if self.on_preview and self._sel_color != self._initial_color:
            self.on_preview(self._initial_color)
        if self.on_avatar_mode_preview and self._sel_avatar_mode != self._initial_avatar_mode:
            self.on_avatar_mode_preview(self._initial_avatar_mode)
        if self.on_anim_mode_preview and self._sel_anim_mode != self._initial_anim_mode:
            self.on_anim_mode_preview(self._initial_anim_mode)
        if self.on_hud_glow_preview and self._sel_hud_glow != self._initial_hud_glow:
            self.on_hud_glow_preview(self._initial_hud_glow)
        if self.on_particle_density_preview and self._sel_density != self._initial_density:
            self.on_particle_density_preview(self._initial_density)
        if self.on_hud_fx_preview and self._sel_hud_fx != self._initial_hud_fx:
            self.on_hud_fx_preview(self._initial_hud_fx)
        self.hide()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self._cancel()
        else:
            super().keyPressEvent(e)

    def _save(self):
        name = self._name_input.text().strip() or "JARVIS"
        user = self._user_input.text().strip()

        # Persist visual settings immediately
        save_avatar_mode(self._sel_avatar_mode)
        save_anim_mode(self._sel_anim_mode)
        save_hud_glow(self._sel_hud_glow)
        save_particle_density(self._sel_density)
        save_hud_fx(self._sel_hud_fx)
        save_sfx_enabled(self._chk_sfx.isChecked())
        save_persona_mode(self._sel_persona)
        save_assistant_gender(self._sel_gender)
        save_preferred_language(self._sel_language)
        save_tts_engine(self._sel_tts_engine)
        save_edge_voice(self._sel_edge_voice)
        save_edge_pitch(self._sel_edge_pitch)

        self._obsidian_cfg["enabled"] = self._chk_obsidian.isChecked()
        self._obsidian_cfg["api_key"] = self._obs_key_input.text().strip()
        try:
            self._obsidian_cfg["port"] = int(self._obs_port_input.text().strip())
        except ValueError:
            self._obsidian_cfg["port"] = 27124
        self._obsidian_cfg["vault_path"] = self._obs_vault_input.text().strip()
        self._obsidian_cfg["use_https"] = self._chk_obs_https.isChecked()
        save_obsidian_config(self._obsidian_cfg)

        self.saved.emit(
            name, user, self._sel_color or DEFAULT_UI_COLOR, self._sel_voice,
            self._sel_avatar_mode, self._sel_density, self._sel_hud_fx, self._chk_sfx.isChecked(),
            self._sel_anim_mode, self._sel_hud_glow,
            self._sel_persona, self._sel_gender, self._sel_tts_engine, self._sel_edge_voice, self._obsidian_cfg,
            self._sel_language
        )
        self.hide()


class PluginManagerOverlay(QWidget):
    """Floating overlay — lists discovered plugins with per-plugin ON/OFF toggles."""

    _OW = 420

    def __init__(self, plugins: list[dict], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            PluginManagerOverlay {{
                background: rgba(0, 6, 10, 245);
                border: 1px solid {C.BORDER_B};
                border-radius: 6px;
            }}
        """)
        self.setFixedWidth(self._OW)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(6)

        hdr = QLabel("🧩  PLUGIN MANAGER")
        hdr.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        lay.addWidget(hdr)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        if not plugins:
            empty = QLabel("No plugins found in /plugins.")
            empty.setFont(QFont("Courier New", 8))
            empty.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            lay.addWidget(empty)

        for p in plugins:
            lay.addLayout(self._build_row(p))

        lay.addSpacing(4)
        close_btn = QPushButton("CLOSE")
        close_btn.setFixedHeight(30)
        close_btn.setFont(QFont("Courier New", 9))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self.hide)
        lay.addWidget(close_btn)
        self.adjustSize()

    def _build_row(self, p: dict) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(6)

        label_text = p["name"] if p["valid"] else f"{p['name']}  (⚠ {p['file']})"
        lbl = QLabel(label_text)
        lbl.setFont(QFont("Courier New", 8))
        lbl.setStyleSheet(f"color: {C.TEXT if p['valid'] else C.TEXT_DIM}; background: transparent;")
        lbl.setToolTip(p["description"] if p["valid"] else p["error"])
        lbl.setWordWrap(False)
        row.addWidget(lbl, stretch=1)

        btn = QPushButton()
        btn.setFixedSize(72, 24)
        btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        if not p["valid"]:
            btn.setText("BROKEN")
            btn.setEnabled(False)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT_DIM};
                    border: 1px solid {C.BORDER}; border-radius: 3px;
                }}
            """)
        else:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._style_toggle(btn, p["enabled"])
            btn.clicked.connect(lambda _, name=p["name"], b=btn: self._toggle(name, b))
        row.addWidget(btn)
        return row

    def _style_toggle(self, btn: QPushButton, enabled: bool):
        if enabled:
            btn.setText("ON")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #001a08; color: {C.GREEN};
                    border: 1px solid {C.GREEN_D}; border-radius: 3px;
                }}
                QPushButton:hover {{ background: #002010; }}
            """)
        else:
            btn.setText("OFF")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT_DIM};
                    border: 1px solid {C.BORDER}; border-radius: 3px;
                }}
                QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
            """)

    def _toggle(self, name: str, btn: QPushButton):
        from memory.config_manager import get_plugin_enabled, save_plugin_enabled
        new_val = not get_plugin_enabled(name)
        save_plugin_enabled(name, new_val)
        self._style_toggle(btn, new_val)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)


class _HudOverlay(QWidget):
    """Base for the floating panels placed by hand over the HUD.

    They are children of the central widget but sit in no layout, so Qt never
    invalidates the region they occupy when they hide or shrink: the HUD keeps
    painting around them and their last frame stays on screen as a ghost. Any
    overlay positioned with _centre_overlay needs this."""

    def hideEvent(self, e):
        p = self.parentWidget()
        if p is not None:
            # Repaint exactly what we were covering, before we stop covering it.
            p.update(self.geometry())
        super().hideEvent(e)

    def closeEvent(self, e):
        p = self.parentWidget()
        if p is not None:
            p.update(self.geometry())
        super().closeEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)


class ConfirmBanner(_HudOverlay):
    """The gate in front of an action that cannot be taken back.

    The old confirmation was a tool parameter the model filled in itself, which
    means it confirmed its own shutdown requests. This is the interface asking,
    and the answer travels from a human finger to core/confirm.py without the
    model in the loop. Nothing blocks while it is up: the assistant keeps
    talking, so this costs no latency — unlike the old gate, which spent two
    tool round trips on every power command."""

    answered = pyqtSignal(bool)
    _OW = 430

    def __init__(self, title: str, detail: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            ConfirmBanner {{
                background: rgba(14, 3, 0, 250);
                border: 1px solid {C.ACC};
                border-radius: 6px;
            }}
        """)
        self.setFixedWidth(self._OW)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(8)

        hdr = QLabel("⚠  CONFIRM")
        hdr.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.ACC}; background: transparent;")
        lay.addWidget(hdr)

        ttl = QLabel(title)
        ttl.setWordWrap(True)
        ttl.setFont(QFont("Courier New", 10, QFont.Weight.Bold))
        ttl.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        lay.addWidget(ttl)

        if detail:
            dtl = QLabel(detail)
            dtl.setWordWrap(True)
            dtl.setFont(QFont("Courier New", 8))
            dtl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            lay.addWidget(dtl)

        row = QHBoxLayout(); row.setSpacing(8)

        yes = QPushButton("▸  CONFIRM")
        yes.setFixedHeight(32)
        yes.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        yes.setCursor(Qt.CursorShape.PointingHandCursor)
        yes.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.ACC};
                border: 1px solid {C.ACC}; border-radius: 3px; }}
            QPushButton:hover {{ background: rgba(255,107,0,40); }}
        """)
        def _on_confirm():
            try:
                from core.sfx import play_sfx
                play_sfx("confirm")
            except Exception:
                pass
            self.answered.emit(True)
        yes.clicked.connect(_on_confirm)
        row.addWidget(yes)

        no = QPushButton("CANCEL")
        no.setFixedHeight(32)
        no.setFont(QFont("Courier New", 9))
        no.setCursor(Qt.CursorShape.PointingHandCursor)
        no.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        no.clicked.connect(lambda: self.answered.emit(False))
        row.addWidget(no)
        lay.addLayout(row)

        # Default focus on CANCEL: if someone hits Enter without reading, the
        # safe answer wins.
        no.setDefault(True)
        no.setFocus()


class AudioDeviceOverlay(_HudOverlay):
    """Choose which microphone JARVIS listens to and which speakers it uses.

    Both audio streams used to open with no `device=` at all, so they always
    took the OS default — which on Windows moves by itself the moment a headset
    is plugged in. 'JARVIS can't hear me' is usually 'JARVIS is listening to the
    webcam'."""

    picked = pyqtSignal()      # emitted after Apply, when something changed
    _OW = 460

    def __init__(self, parent=None):
        super().__init__(parent)
        from core.audio_devices import list_devices, DEFAULT_LABEL
        from memory.config_manager import get_input_device, get_output_device

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            AudioDeviceOverlay {{
                background: rgba(0, 6, 10, 245);
                border: 1px solid {C.BORDER_B};
                border-radius: 6px;
            }}
        """)
        self.setFixedWidth(self._OW)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(6)

        hdr = QLabel("🎧  AUDIO DEVICES")
        hdr.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        lay.addWidget(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        _combo_css = (
            f"QComboBox {{ background: #000d12; color: {C.TEXT}; "
            f"border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px; }}"
            f"QComboBox:hover {{ border-color: {C.BORDER_B}; }}"
            f"QComboBox QAbstractItemView {{ background: #000d12; color: {C.TEXT}; "
            f"selection-background-color: {C.PRI_GHO}; border: 1px solid {C.BORDER}; }}"
        )

        def _row(label: str, kind: str, current: str) -> QComboBox:
            cap = QLabel(label)
            cap.setFont(QFont("Courier New", 8))
            cap.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            lay.addWidget(cap)

            box = QComboBox()
            box.setFont(QFont("Courier New", 9))
            box.setFixedHeight(30)
            box.setStyleSheet(_combo_css)
            box.setMaxVisibleItems(8)
            box.view().setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            # The list is served from a cache warmed on a background thread at
            # startup, so opening this panel never blocks the Qt thread on the
            # host audio API.
            box.addItem(DEFAULT_LABEL, "")
            for name in list_devices(kind):
                box.addItem(name, name)
            idx = box.findData(current) if current else 0
            box.setCurrentIndex(idx if idx >= 0 else 0)
            if current and idx < 0:
                # Saved device is not plugged in right now. Show it rather than
                # silently resetting the user's choice to default.
                box.addItem(f"{current}  (not connected)", current)
                box.setCurrentIndex(box.count() - 1)
            lay.addWidget(box)
            return box

        self._in_box  = _row("MICROPHONE — what JARVIS hears you with",
                             "input", get_input_device())
        lay.addSpacing(4)
        self._out_box = _row("SPEAKERS — what JARVIS talks through",
                             "output", get_output_device())

        note = QLabel("Applying reconnects the session. Your conversation is kept.")
        note.setWordWrap(True)
        note.setFont(QFont("Courier New", 7))
        note.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addSpacing(6)
        lay.addWidget(note)

        row = QHBoxLayout(); row.setSpacing(8)
        ok = QPushButton("▸  APPLY")
        ok.setFixedHeight(32)
        ok.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px; }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
        """)
        ok.clicked.connect(self._apply)
        row.addWidget(ok)

        cancel = QPushButton("CLOSE")
        cancel.setFixedHeight(32)
        cancel.setFont(QFont("Courier New", 9))
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        cancel.clicked.connect(self.hide)
        row.addWidget(cancel)
        lay.addLayout(row)

    def _apply(self):
        from memory.config_manager import (
            get_input_device, get_output_device,
            save_input_device, save_output_device,
        )
        new_in  = self._in_box.currentData()  or ""
        new_out = self._out_box.currentData() or ""
        changed = (new_in != get_input_device()) or (new_out != get_output_device())
        save_input_device(new_in)
        save_output_device(new_out)
        self.hide()
        # Only rebuild the session if something actually moved — a no-op Apply
        # should not cost a reconnect.
        if changed:
            self.picked.emit()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)


class MemoryOverlay(_HudOverlay):
    """Everything JARVIS has stored about you, and when it learned it.

    Memory used to be a 2200-character store that deleted its oldest entries
    when full and mentioned it only on stdout. The cap is gone; this panel is
    the other half of that change — a memory you cannot inspect is a memory you
    cannot trust, and 'delete' has to be something the person can do."""

    _OW = 520

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            MemoryOverlay {{
                background: rgba(0, 6, 10, 246);
                border: 1px solid {C.BORDER_B};
                border-radius: 6px;
            }}
        """)
        self.setFixedWidth(self._OW)

        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(20, 16, 20, 16)
        self._lay.setSpacing(5)
        self._rebuild()

    def _clear_layout(self):
        """Take every item out of the layout and detach it from the widget tree
        in this call.

        deleteLater() on its own is not enough: it queues destruction for the
        next event-loop pass, and until then the old rows are still children of
        this widget and still paint — which is what drew half of the previous
        panel over the new one. setParent(None) removes them from the tree now;
        deleteLater() then frees them safely."""
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None:
                # hide() stops it painting in this frame; deleteLater() frees it
                # safely afterwards. setParent(None) would also stop the paint,
                # but it turns the widget into a top-level window for the moment
                # between the two calls, which is not something to leave lying
                # around inside a click handler.
                w.hide()
                w.deleteLater()
                continue
            sub = item.layout()
            if sub is not None:
                while sub.count():
                    si = sub.takeAt(0)
                    sw = si.widget()
                    if sw is not None:
                        sw.hide()
                        sw.deleteLater()
                sub.deleteLater()

    def _settle(self, before):
        """Size the panel to its content, re-centre it, and repaint what the old
        size covered.

        The re-size has to happen here rather than at the end of _rebuild
        because Qt has not polished the freshly-created children at that point,
        so the size hint it would read is the empty-layout one. Measured: a
        first adjustSize() returned 32 px for a panel whose content needed 155,
        and a second call — after the same widgets had been through the event
        loop — returned 155. So this runs twice: once now, once on the next
        turn, from _rebuild.

        The re-centre and the repaint are needed because the overlay is placed
        by hand and is in no layout: shrinking it leaves it off-centre and
        leaves its former pixels on screen, since nothing tells the parent that
        region changed. The repaint has to cover the union of the old and new
        rectangles."""
        self._lay.invalidate()
        self._lay.activate()
        self.updateGeometry()
        self.adjustSize()

        p = self.parentWidget()
        if p is None:
            self.update()
            return
        self.move(max(0, (p.width()  - self.width())  // 2),
                  max(0, (p.height() - self.height()) // 2))
        p.update(before.united(self.geometry()))
        self.update()

    def _rebuild(self):
        before = self.geometry()
        self._clear_layout()

        from memory.memory_manager import all_entries_for_ui

        hdr = QLabel("🧠  WHAT JARVIS REMEMBERS")
        hdr.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._lay.addWidget(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        self._lay.addWidget(sep)

        rows = all_entries_for_ui()

        cap = QLabel(f"{len(rows)} stored facts — newest first. "
                     f"Nothing here is sent anywhere; it lives in "
                     f"memory/long_term.json on this machine.")
        cap.setWordWrap(True)
        cap.setFont(QFont("Courier New", 7))
        cap.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._lay.addWidget(cap)

        if not rows:
            empty = QLabel("Nothing stored yet.")
            empty.setFont(QFont("Courier New", 9))
            empty.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            self._lay.addWidget(empty)
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFixedHeight(min(420, 34 * len(rows) + 10))
            scroll.setStyleSheet(
                f"QScrollArea {{ border: 1px solid {C.BORDER}; border-radius: 3px; "
                f"background: transparent; }}"
            )
            inner = QWidget()
            ilay  = QVBoxLayout(inner)
            ilay.setContentsMargins(6, 6, 6, 6)
            ilay.setSpacing(3)

            for r in rows:
                line = QHBoxLayout(); line.setSpacing(6)
                txt = QLabel(f"<b>{r['key'].replace('_', ' ')}</b> "
                             f"<span style='color:{C.TEXT_MED}'>— {r['value']}</span>")
                txt.setWordWrap(True)
                txt.setFont(QFont("Courier New", 8))
                txt.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
                line.addWidget(txt, 1)

                meta = QLabel(f"{r['category'][:4]} · {r['updated'] or '—'}")
                meta.setFont(QFont("Courier New", 7))
                meta.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
                line.addWidget(meta)

                rm = QPushButton("✕")
                rm.setFixedSize(20, 20)
                rm.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
                rm.setCursor(Qt.CursorShape.PointingHandCursor)
                rm.setToolTip("Forget this")
                rm.setStyleSheet(f"""
                    QPushButton {{ background: transparent; color: {C.TEXT_DIM};
                        border: 1px solid {C.BORDER}; border-radius: 3px; }}
                    QPushButton:hover {{ color: {C.RED}; border-color: {C.RED}; }}
                """)
                rm.clicked.connect(
                    lambda _=False, c=r["category"], k=r["key"]: self._forget(c, k))
                line.addWidget(rm)

                holder = QWidget()
                holder.setLayout(line)
                ilay.addWidget(holder)

            ilay.addStretch()
            scroll.setWidget(inner)
            self._lay.addWidget(scroll)

        close = QPushButton("CLOSE")
        close.setFixedHeight(30)
        close.setFont(QFont("Courier New", 9))
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        close.clicked.connect(self.hide)
        self._lay.addWidget(close)

        self._settle(before)
        # …and again once Qt has polished the new children, because the size
        # hint is not final until then. Harmless when the first pass already
        # got it right: _settle is idempotent.
        QTimer.singleShot(0, lambda g=before: self._settle(g))

    def _forget(self, category: str, key: str):
        from memory.memory_manager import forget
        forget(key, category)
        # Rebuild on the NEXT event-loop turn, not inside this click handler.
        # The rebuild destroys the very ✕ button that emitted this signal, and
        # Qt is entitled to touch the sender after a slot returns; tearing it
        # down mid-emission is how a widget ends up half-alive on screen.
        QTimer.singleShot(0, self._rebuild)


class ClipboardPanel(QWidget):
    """Floating panel shown when text is copied — offers quick Jarvis actions."""

    action_requested = pyqtSignal(str)
    _W, _H = 326, 112

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            ClipboardPanel {{
                background: rgba(0, 8, 14, 248);
                border: 1px solid {C.BORDER_B};
                border-radius: 6px;
            }}
        """)
        self.setFixedWidth(self._W)
        self._clip_text = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 7)
        lay.setSpacing(4)

        hdr = QHBoxLayout(); hdr.setSpacing(4)
        icon_lbl = QLabel("◈  CLIPBOARD DETECTED")
        icon_lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        icon_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent;")
        hdr.addWidget(icon_lbl); hdr.addStretch()
        x_btn = QPushButton("✕")
        x_btn.setFixedSize(16, 16)
        x_btn.setFont(QFont("Courier New", 8))
        x_btn.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        x_btn.clicked.connect(self.hide)
        hdr.addWidget(x_btn)
        lay.addLayout(hdr)

        self._preview = QLabel()
        self._preview.setFont(QFont("Courier New", 8))
        self._preview.setStyleSheet(f"""
            color: {C.TEXT}; background: {C.PANEL2};
            border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 6px;
        """)
        self._preview.setWordWrap(False)
        self._preview.setFixedHeight(28)
        lay.addWidget(self._preview)

        btn_row = QHBoxLayout(); btn_row.setSpacing(4)
        _bs = (f"QPushButton {{ background: {C.PANEL2}; color: {C.TEXT_MED}; "
               f"border: 1px solid {C.BORDER}; border-radius: 2px; }}"
               f"QPushButton:hover {{ color: {C.PRI}; border-color: {C.BORDER_B}; }}")
        for label, cmd_fmt in [
            ("TRANSLATE", "Translate this text to English: {text}"),
            ("SUMMARISE", "Summarise this: {text}"),
            ("EXPLAIN",   "Explain this: {text}"),
            ("FIX",       "Fix grammar and spelling: {text}"),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(22)
            b.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(_bs)
            b.clicked.connect(lambda _, c=cmd_fmt: self._trigger(c))
            btn_row.addWidget(b)
        lay.addLayout(btn_row)

        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.hide)
        self.hide()

    def _trigger(self, cmd_fmt: str):
        if self._clip_text:
            self.action_requested.emit(cmd_fmt.format(text=self._clip_text[:800]))
        self.hide()

    def show_clipboard(self, text: str):
        self._clip_text = text
        preview = text[:58].replace('\n', ' ')
        if len(text) > 58:
            preview += "…"
        self._preview.setText(f'"{preview}"')
        self.show(); self.raise_()
        self._dismiss_timer.start(8000)


class PluginSettingsOverlay(QWidget):
    """Floating overlay — renders per-plugin settings forms.

    Fully generic: it iterates the settings schemas a plugin declared via its
    PLUGIN_SETTINGS constant (delivered by PluginRegistry.settings_schemas) and
    builds a form for each. It knows NOTHING about any specific plugin, so the
    core stays clean and plugins remain pure drop-in — install a plugin that
    declares fields (e.g. the 3D-printer suite) and its section appears here;
    install none and this panel simply says there's nothing to configure.
    """

    _test_done = pyqtSignal(str, bool, str)   # namespace, ok, message
    _OW = 460

    def __init__(self, sections: list[dict], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            PluginSettingsOverlay {{
                background: rgba(0, 6, 10, 245);
                border: 1px solid {C.BORDER_B};
                border-radius: 6px;
            }}
        """)
        self._sections = sections or []
        self._widgets: dict[tuple, object] = {}    # (namespace, key) -> input widget
        self._types:   dict[tuple, str]    = {}     # (namespace, key) -> field type
        self._status_labels: dict[str, QLabel] = {} # namespace -> status QLabel
        self._test_done.connect(self._on_test_done)

        self._fs = (f"QLineEdit {{ background: #000d12; color: {C.TEXT}; "
                    f"border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px; }}"
                    f"QLineEdit:focus {{ border: 1px solid {C.PRI}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 16, 22, 16)
        root.setSpacing(8)

        root.addWidget(self._lbl("⚙  PLUGIN SETTINGS", 12, True))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        root.addWidget(sep)

        if not self._sections:
            root.addWidget(self._lbl(
                "No configurable plugins are installed.\nDrop a plugin that needs "
                "settings (like the 3D-printer suite) into the plugins folder and "
                "it will show up here.", 9, color=C.TEXT_DIM))
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setStyleSheet("QScrollArea { background: transparent; }")
            inner = QWidget()
            inner.setStyleSheet("background: transparent;")
            form = QVBoxLayout(inner)
            form.setContentsMargins(0, 0, 6, 0)
            form.setSpacing(6)
            for sec in self._sections:
                self._build_section(form, sec)
            form.addStretch(1)
            scroll.setWidget(inner)
            root.addWidget(scroll, 1)

        # ── bottom buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        if self._sections:
            save_btn = QPushButton("▸  SAVE")
            save_btn.setFixedHeight(34)
            save_btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            save_btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {C.PRI};
                    border: 1px solid {C.PRI_DIM}; border-radius: 3px; }}
                QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
            """)
            save_btn.clicked.connect(self._save_all)
            btn_row.addWidget(save_btn)

        close_btn = QPushButton("CLOSE")
        close_btn.setFixedHeight(34)
        close_btn.setFont(QFont("Courier New", 9))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self.hide)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    # ── helpers ───────────────────────────────────────────────────────────────
    def _lbl(self, txt, fs=9, bold=False, color=C.PRI,
             align=Qt.AlignmentFlag.AlignLeft):
        w = QLabel(txt); w.setAlignment(align); w.setWordWrap(True)
        w.setFont(QFont("Courier New", fs,
                        QFont.Weight.Bold if bold else QFont.Weight.Normal))
        w.setStyleSheet(f"color: {color}; background: transparent;")
        return w

    def _build_section(self, form: QVBoxLayout, sec: dict):
        ns     = sec.get("namespace") or sec.get("plugin") or "plugin"
        title  = sec.get("title") or ns
        fields = sec.get("fields") or []
        values = sec.get("values") or {}

        form.addSpacing(4)
        form.addWidget(self._lbl(title, 10, True, C.PRI))

        for field in fields:
            if not isinstance(field, dict) or not field.get("key"):
                continue
            key   = field["key"]
            ftype = (field.get("type") or "text").lower()
            label = field.get("label") or key
            default = field.get("default")
            stored  = values.get(key, default)

            form.addWidget(self._lbl(label.upper(), 8, color=C.TEXT_DIM))

            if ftype == "choice":
                w = QComboBox()
                w.addItems([str(o) for o in field.get("options", [])])
                w.setFont(QFont("Courier New", 9))
                w.setFixedHeight(30)
                w.setMaxVisibleItems(8)
                w.view().setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
                w.setStyleSheet(
                    f"QComboBox {{ background: #000d12; color: {C.TEXT}; "
                    f"border: 1px solid {C.BORDER}; border-radius: 3px; padding: 2px 8px; }}"
                    f"QComboBox QAbstractItemView {{ background: #000d12; color: {C.TEXT}; "
                    f"selection-background-color: {C.PRI_GHO}; }}")
                if stored is not None:
                    w.setCurrentText(str(stored))
            elif ftype == "toggle":
                w = QPushButton()
                w.setCheckable(True)
                w.setChecked(bool(stored))
                w.setFixedHeight(28)
                w.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
                w.setCursor(Qt.CursorShape.PointingHandCursor)
                self._style_toggle(w)
                w.toggled.connect(lambda _=False, b=w: self._style_toggle(b))
            else:  # text / password
                w = QLineEdit("" if stored is None else str(stored))
                w.setFont(QFont("Courier New", 10))
                w.setFixedHeight(30)
                w.setStyleSheet(self._fs)
                if field.get("placeholder"):
                    w.setPlaceholderText(str(field["placeholder"]))
                if ftype == "password":
                    w.setEchoMode(QLineEdit.EchoMode.Password)

            self._widgets[(ns, key)] = w
            self._types[(ns, key)]   = ftype
            form.addWidget(w)

        # optional test/connect action button + status line
        action = sec.get("action")
        if isinstance(action, dict) and callable(action.get("run")):
            form.addSpacing(2)
            ab = QPushButton(str(action.get("label") or "TEST"))
            ab.setFixedHeight(30)
            ab.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
            ab.setCursor(Qt.CursorShape.PointingHandCursor)
            ab.setStyleSheet(f"""
                QPushButton {{ background: #00091a; color: {C.PRI};
                    border: 1px solid {C.PRI_DIM}; border-radius: 3px; }}
                QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
            """)
            ab.clicked.connect(lambda _=False, n=ns: self._run_action(n))
            form.addWidget(ab)

        status = self._lbl("", 8, color=C.TEXT_DIM)
        self._status_labels[ns] = status
        form.addWidget(status)

        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {C.BORDER}; margin: 4px 0;")
        form.addWidget(line)

    def _style_toggle(self, btn: QPushButton):
        on = btn.isChecked()
        btn.setText("ON" if on else "OFF")
        if on:
            btn.setStyleSheet(f"QPushButton {{ background: {C.PRI_GHO}; color: {C.PRI}; "
                              f"border: 1px solid {C.PRI}; border-radius: 3px; }}")
        else:
            btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {C.TEXT_MED}; "
                              f"border: 1px solid {C.BORDER}; border-radius: 3px; }}")

    # ── data ──────────────────────────────────────────────────────────────────
    def _gather(self, ns: str) -> dict:
        out = {}
        for (n, key), w in self._widgets.items():
            if n != ns:
                continue
            t = self._types.get((n, key), "text")
            if t == "choice":
                out[key] = w.currentText()
            elif t == "toggle":
                out[key] = w.isChecked()
            else:
                out[key] = w.text().strip()
        return out

    def _save_ns(self, ns: str):
        from memory.config_manager import save_plugin_config
        save_plugin_config(ns, self._gather(ns))

    def _save_all(self):
        for sec in self._sections:
            ns = sec.get("namespace") or sec.get("plugin")
            if ns:
                self._save_ns(ns)
                lbl = self._status_labels.get(ns)
                if lbl:
                    lbl.setText("Saved ✓")
                    lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")

    def _run_action(self, ns: str):
        sec = next((s for s in self._sections
                    if (s.get("namespace") or s.get("plugin")) == ns), None)
        if not sec:
            return
        run_fn = (sec.get("action") or {}).get("run")
        if not callable(run_fn):
            return
        self._save_ns(ns)                 # persist what the user typed before testing
        values = self._gather(ns)
        lbl = self._status_labels.get(ns)
        if lbl:
            lbl.setText("Testing…")
            lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")

        def worker():
            try:
                res = run_fn(values)
                if isinstance(res, tuple) and len(res) == 2:
                    ok, msg = bool(res[0]), str(res[1])
                else:
                    ok, msg = bool(res), str(res)
            except Exception as e:
                ok, msg = False, str(e)
            self._test_done.emit(ns, ok, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _on_test_done(self, ns: str, ok: bool, msg: str):
        lbl = self._status_labels.get(ns)
        if not lbl:
            return
        lbl.setText(msg)
        color = C.PRI if ok else "#ff6b6b"
        lbl.setStyleSheet(f"color: {color}; background: transparent;")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)


class RemoteKeyOverlay(QWidget):
    """Floating overlay — QR code for instant phone pairing + manual key fallback."""

    closed = pyqtSignal()

    _OW, _OH = 400, 465

    def __init__(self, url: str, key: str, auto_login_url: str = "",
                 manual_url: str = "", expiry_secs: int = 600, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            RemoteKeyOverlay {{
                background: rgba(0, 4, 12, 0.95);
                border: 1px solid {C.BORDER_B};
                border-radius: 14px;
            }}
        """)
        self._expiry          = time.time() + expiry_secs
        self._on_new_key      = None
        self._auto_login_url  = auto_login_url
        self._manual_url      = manual_url or url

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 16, 24, 16)
        lay.setSpacing(5)

        def _lbl(txt, fs=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(QFont("Courier New", fs,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            w.setWordWrap(True)
            return w

        lay.addWidget(_lbl("◈  REMOTE ACCESS", 12, True))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 1px 0;")
        lay.addWidget(sep)

        # ── QR code ───────────────────────────────────────────────────────────
        self._qr_label = QLabel()
        self._qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_label.setFixedSize(176, 176)
        self._qr_label.setStyleSheet(
            "background: white; border-radius: 10px; padding: 4px;"
        )
        qr_row = QHBoxLayout()
        qr_row.addStretch()
        qr_row.addWidget(self._qr_label)
        qr_row.addStretch()
        lay.addLayout(qr_row)

        self._update_qr(auto_login_url)

        lay.addWidget(_lbl("Scan with phone camera to connect instantly", 8, color=C.TEXT_DIM))

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER}; margin: 1px 0;")
        lay.addWidget(sep2)

        lay.addWidget(_lbl("Or enter manually:", 7, color=C.TEXT_DIM,
                           align=Qt.AlignmentFlag.AlignLeft))

        self._url_lbl = QLabel(self._manual_url)
        self._url_lbl.setFont(QFont("Courier New", 8))
        self._url_lbl.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        self._url_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._url_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self._url_lbl)

        self._key_lbl = QLabel(key)
        self._key_lbl.setFont(QFont("Courier New", 28, QFont.Weight.Bold))
        self._key_lbl.setStyleSheet(f"""
            color: {C.ACC};
            background: {C.PANEL2};
            border: 1px solid {C.BORDER_B};
            border-radius: 8px;
            padding: 6px 4px;
            letter-spacing: 10px;
        """)
        self._key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._key_lbl)

        self._timer_lbl = QLabel()
        self._timer_lbl.setFont(QFont("Courier New", 8))
        self._timer_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._timer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._timer_lbl)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        new_btn = QPushButton("NEW KEY")
        new_btn.setFixedHeight(32)
        new_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 5px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        new_btn.clicked.connect(self._refresh_key)
        btn_row.addWidget(new_btn)

        close_btn = QPushButton("DISMISS")
        close_btn.setFixedHeight(32)
        close_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 5px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self._do_close)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        self._ctimer = QTimer(self)
        self._ctimer.timeout.connect(self._tick)
        self._ctimer.start(1000)
        self._tick()

    def set_new_key_callback(self, fn) -> None:
        self._on_new_key = fn

    def _update_qr(self, url: str) -> None:
        if not url:
            self._qr_label.setText("—")
            return
        try:
            import qrcode as _qrmod
            from io import BytesIO
            qr = _qrmod.QRCode(
                box_size=5, border=2,
                error_correction=_qrmod.constants.ERROR_CORRECT_M,
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap()
            px.loadFromData(buf.getvalue())
            self._qr_label.setPixmap(
                px.scaled(170, 170,
                          Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
            )
        except ImportError:
            self._qr_label.setText("pip install\nqrcode[pil]")
            self._qr_label.setFont(QFont("Courier New", 8))
            self._qr_label.setStyleSheet(
                "color: #888; background: white; border-radius: 10px; padding: 4px;"
            )
        except Exception:
            self._qr_label.setText(url[:28])
            self._qr_label.setFont(QFont("Courier New", 7))
            self._qr_label.setStyleSheet(
                f"color: {C.PRI}; background: white; border-radius: 10px; padding: 4px;"
            )

    def _tick(self):
        remaining = max(0, int(self._expiry - time.time()))
        m, s = divmod(remaining, 60)
        self._timer_lbl.setText(f"Key expires in  {m:02d}:{s:02d}")
        if remaining == 0:
            self._do_close()

    def mark_connected(self) -> None:
        """Call from any thread when a phone successfully connects."""
        self._ctimer.stop()
        self._key_lbl.setText("CONNECTED")
        self._key_lbl.setStyleSheet(f"""
            color: {C.GREEN};
            background: rgba(34,197,94,0.08);
            border: 2px solid rgba(34,197,94,0.4);
            border-radius: 8px;
            padding: 6px 4px;
            letter-spacing: 4px;
        """)
        self._qr_label.setText("✓")
        self._qr_label.setFont(QFont("Courier New", 54, QFont.Weight.Bold))
        self._qr_label.setStyleSheet(
            "color: #00ff88; background: #001a0d; border-radius: 10px;"
        )
        self._timer_lbl.setText("Phone connected — JARVIS ready")
        self._timer_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent;")

    def _refresh_key(self):
        if self._on_new_key:
            result = self._on_new_key()
            if result:
                url    = result[0]
                key    = result[1]
                auto   = result[2] if len(result) >= 3 else ""
                manual = result[3] if len(result) >= 4 else url
                self._manual_url     = manual or url
                self._url_lbl.setText(self._manual_url)
                self._key_lbl.setText(key)
                self._auto_login_url = auto
                self._update_qr(auto or url)
                self._expiry = time.time() + 600
                self._key_lbl.setStyleSheet(f"""
                    color: {C.ACC};
                    background: {C.PANEL2};
                    border: 1px solid {C.BORDER_B};
                    border-radius: 8px;
                    padding: 6px 4px;
                    letter-spacing: 10px;
                """)
                self._timer_lbl.setStyleSheet(
                    f"color: {C.TEXT_MED}; background: transparent;"
                )
                self._ctimer.start(1000)
                self._tick()

    def _do_close(self):
        self._ctimer.stop()
        self.hide()
        self.closed.emit()


class MainWindow(QMainWindow):
    _log_sig        = pyqtSignal(str)
    _stream_log_sig = pyqtSignal(str, str, bool)   # (speaker, chunk, is_final) — live real-time speech streaming
    _state_sig      = pyqtSignal(str)
    _content_sig    = pyqtSignal(str, str)   # (title, text) — thread-safe content display
    _reconfig_sig   = pyqtSignal()           # trigger setup overlay from any thread
    _camera_sig     = pyqtSignal(bytes)      # show camera frame preview (small overlay)
    _cam_stream_sig = pyqtSignal(bool)       # True=start live stream, False=stop
    _cam_frame_sig  = pyqtSignal(bytes)      # live camera frame → HUD area
    _clipboard_sig  = pyqtSignal(str)        # clipboard text changed (thread-safe)
    _confirm_sig    = pyqtSignal(str, str)   # (title, detail) — irreversible-action gate
    _confirm_hide_sig = pyqtSignal()
    _wake_dl_sig    = pyqtSignal(bool, str)  # wake-word install finished (ok, message)
    _expression_sig = pyqtSignal(str, float) # (expression_name, duration_sec) live HUD avatar reaction

    def __init__(self, face_path: str):
        super().__init__()
        self._face_path = face_path

        # Load customization from config
        _cfg = _read_full_config()
        self._assistant_name: str = (_cfg.get("assistant_name") or "JARVIS").strip()
        _display = self._assistant_name.upper()

        # Apply the saved UI colour BEFORE panels/stylesheets are built
        _ui_color = (_cfg.get("ui_color") or "").strip()
        if _ui_color and _ui_color.lower() != DEFAULT_UI_COLOR:
            apply_ui_accent(_ui_color)

        self.setWindowTitle(f"{_display} — {APP_VERSION}")
        # Apply custom Arc Reactor icon to Window, Taskbar & Alt-Tab
        ico_file = Path(__file__).resolve().parent / "config" / "jarvis.ico"
        if ico_file.exists():
            from PyQt6.QtGui import QIcon
            app_icon = QIcon(str(ico_file))
            self.setWindowIcon(app_icon)
            QApplication.setWindowIcon(app_icon)
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SudhirDevOps1.JARVIS.AI")
            except Exception:
                pass
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - _DEFAULT_W) // 2,
            (screen.height() - _DEFAULT_H) // 2,
        )

        self.on_text_command   = None
        self.on_remote_clicked = None   # callable: () -> (url, key) | None
        self.on_interrupt      = None   # callable: () -> None — stop JARVIS mid-speech
        self.on_voice_change   = None   # callable: () -> None — rebuild session with new voice
        self.on_audio_device_change = None  # callable: () -> None — reopen audio streams
        self._confirm_overlay  = None   # live ConfirmBanner, if one is on screen
        self.get_plugins       = None   # callable: () -> list[dict], set by JarvisLive
        self.get_plugin_settings = None # callable: () -> list[dict] settings schemas, set by JarvisLive
        self.on_wake_toggle    = None   # callable: (enable: bool) -> str, set by JarvisLive
        self.on_wake_manual    = None   # callable: () -> None — manual sleep/wake
        self.wake_get_state    = None   # callable: () -> dict {enabled, awake, ready}
        self._muted            = False
        self._current_file: str | None = None
        self._remote_overlay: RemoteKeyOverlay | None = None
        self._customize_overlay: CustomizeOverlay | None = None
        self._provider_overlay: ProviderSettingsOverlay | None = None

        central = QWidget()
        central.setStyleSheet(f"background: {C.BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._left_panel = self._build_left_panel()
        body.addWidget(self._left_panel, stretch=0)

        # Center column: HUD + resizable content panel via QSplitter
        self.hud = HudCanvas(face_path, _display)
        self.hud.set_avatar_mode(get_avatar_mode())
        self.hud.set_anim_mode(get_anim_mode())
        self.hud.set_hud_glow(get_hud_glow())
        self.hud.set_particle_density(get_particle_density())
        self.hud.set_hud_fx(get_hud_fx())
        self.hud.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._content_panel = self._build_content_panel()

        # Live camera container — replaces HUD when camera stream is active
        _cam_cont = QWidget()
        _cam_cont.setStyleSheet("background: #000308;")
        _cam_v = QVBoxLayout(_cam_cont)
        _cam_v.setContentsMargins(0, 0, 0, 0)
        _cam_v.setSpacing(0)
        _cam_hdr = QHBoxLayout()
        _cam_hdr.setContentsMargins(8, 5, 8, 5)
        _cam_title = QLabel("◈  CAMERA FEED")
        _cam_title.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        _cam_title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        _cam_hdr.addWidget(_cam_title)
        _cam_hdr.addStretch()
        _cam_x = QPushButton("✕  CLOSE")
        _cam_x.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        _cam_x.setCursor(Qt.CursorShape.PointingHandCursor)
        _cam_x.setStyleSheet(f"""
            QPushButton {{
                color: {C.TEXT_DIM}; background: transparent;
                border: none; padding: 2px 6px;
            }}
            QPushButton:hover {{ color: {C.PRI}; }}
        """)
        _cam_x.clicked.connect(self.stop_camera_stream)
        _cam_hdr.addWidget(_cam_x)
        _cam_v.addLayout(_cam_hdr)
        self._cam_live_lbl = QLabel()
        self._cam_live_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cam_live_lbl.setStyleSheet("background: transparent;")
        self._cam_live_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        _cam_v.addWidget(self._cam_live_lbl, stretch=1)

        # Stack: 0 = animated HUD, 1 = live camera
        self._hud_cam_stack = QStackedWidget()
        self._hud_cam_stack.addWidget(self.hud)
        self._hud_cam_stack.addWidget(_cam_cont)

        self._center_split = QSplitter(Qt.Orientation.Vertical)
        self._center_split.setStyleSheet(f"""
            QSplitter::handle {{
                background: {C.BORDER};
                height: 4px;
            }}
            QSplitter::handle:hover {{
                background: {C.PRI_DIM};
            }}
        """)
        self._center_split.addWidget(self._hud_cam_stack)
        self._center_split.addWidget(self._content_panel)
        self._center_split.setStretchFactor(0, 3)
        self._center_split.setStretchFactor(1, 1)
        self._center_split.setCollapsible(0, False)
        body.addWidget(self._center_split, stretch=5)

        self._right_panel = self._build_right_panel()
        body.addWidget(self._right_panel, stretch=0)

        root.addLayout(body, stretch=1)
        root.addWidget(self._build_footer())

        # Quick-access drawer (floating overlay, built after central widget layout is done)
        self._quick_drawer = self._build_quick_drawer()
        self._update_autostart_btn(self._check_autostart())
        from memory.config_manager import get_brief_enabled as _gbe
        self._update_brief_btn(_gbe())

        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()

        # Metric update timer
        self._metric_tmr = QTimer(self)
        self._metric_tmr.timeout.connect(self._update_metrics)
        self._metric_tmr.start(2000)
        self._update_metrics()

        # Free Open-Meteo Weather update timer (every 10 minutes)
        self._weather_tmr = QTimer(self)
        self._weather_tmr.timeout.connect(self._refresh_weather_async)
        self._weather_tmr.start(600_000)
        self._refresh_weather_async()

        # Free HackerNews Developer news ticker timer (every 20 seconds)
        self._news_items: list[dict] = []
        self._news_idx = 0
        self._news_tmr = QTimer(self)
        self._news_tmr.timeout.connect(self._rotate_news_ticker)
        self._news_tmr.start(20_000)
        QTimer.singleShot(1500, self._rotate_news_ticker)

        self._log_sig.connect(self._log.append_log)
        self._stream_log_sig.connect(self._log.stream_log_chunk)
        self._state_sig.connect(self._apply_state)
        self._content_sig.connect(self._show_content)
        self._reconfig_sig.connect(self._show_setup)
        self._camera_sig.connect(self._show_camera_frame)
        self._confirm_sig.connect(self._show_confirm_banner)
        self._confirm_hide_sig.connect(self._hide_confirm_banner)
        self._cam_stream_sig.connect(self._on_cam_stream)
        self._cam_frame_sig.connect(self._on_cam_frame)
        self._clipboard_sig.connect(self._show_clipboard_panel)
        self._wake_dl_sig.connect(self._on_wake_install_done)
        self._expression_sig.connect(lambda expr, dur: self.hud.set_expression(expr, dur))
        self._cam_stop = threading.Event()

        # Camera preview overlay (child of central widget, positioned in resizeEvent)
        self._cam_preview = _CameraPreview(self.centralWidget())

        # Clipboard panel (child of central widget, bottom-center)
        self._clipboard_panel = ClipboardPanel(self.centralWidget())
        self._clipboard_panel.action_requested.connect(self._on_clipboard_action)
        QApplication.clipboard().dataChanged.connect(self._on_clipboard_changed)

        self._overlay: SetupOverlay | None = None
        self._ready = self._check_config()
        if not self._ready:
            self._show_setup()

        sc_mute = QShortcut(QKeySequence("F4"), self)
        sc_mute.activated.connect(self._toggle_mute)
        sc_full = QShortcut(QKeySequence("F11"), self)
        sc_full.activated.connect(self._toggle_fullscreen)
        sc_intr = QShortcut(QKeySequence("Escape"), self)
        sc_intr.activated.connect(self._do_interrupt)

        try:
            from core.sfx import play_sfx
            play_sfx("boot")
        except Exception:
            pass

    def _show_camera_frame(self, img_bytes: bytes):
        """Slot — display camera preview overlay (main thread)."""
        self._cam_preview.show_frame(img_bytes)
        cw = self.centralWidget()
        pw = _CameraPreview._W
        ph = self._cam_preview.height()
        self._cam_preview.setGeometry(
            cw.width() - _RIGHT_W - pw - 12,
            cw.height() - ph - 28,
            pw, ph,
        )

    # --- Live camera stream in HUD area ------------------------------------
    def _on_cam_stream(self, start: bool) -> None:
        if start:
            self._hud_cam_stack.setCurrentIndex(1)
        else:
            self._hud_cam_stack.setCurrentIndex(0)
            self._cam_live_lbl.clear()

    def _on_cam_frame(self, data: bytes) -> None:
        px = QPixmap()
        px.loadFromData(data)
        if not px.isNull():
            w, h = self._cam_live_lbl.width(), self._cam_live_lbl.height()
            if w > 1 and h > 1:
                self._cam_live_lbl.setPixmap(
                    px.scaled(w, h,
                              Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
                )

    def start_camera_stream(self) -> None:
        self._cam_stop.clear()
        self._cam_stream_sig.emit(True)
        t = threading.Thread(target=self._cam_loop, daemon=True, name="cam-stream")
        t.start()

    def _cam_loop(self) -> None:
        try:
            import cv2
            # Reuse camera index detected by screen_processor (cached in api_keys.json)
            cam_idx = 0
            try:
                import json as _j
                cfg = _j.loads((CONFIG_DIR / "api_keys.json").read_text())
                cam_idx = int(cfg.get("camera_index", 0))
            except Exception:
                pass
            try:
                backend = cv2.CAP_DSHOW if _OS == "Windows" else cv2.CAP_ANY
            except AttributeError:
                backend = 0
            cap = cv2.VideoCapture(cam_idx, backend)
            if not cap.isOpened():
                cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return
            # warm-up frames
            for _ in range(5):
                cap.read()
            while not self._cam_stop.wait(0.033) and cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
                    self._cam_frame_sig.emit(buf.tobytes())
            cap.release()
        except Exception as e:
            print(f"[Camera] Stream error: {e}")
        finally:
            self._cam_stream_sig.emit(False)

    def stop_camera_stream(self) -> None:
        self._cam_stop.set()

    # ------------------------------------------------------------------
    # Icon generation — arc-reactor style, rendered with Pillow
    # ------------------------------------------------------------------
    @staticmethod
    def _build_jarvis_icon(out_path: Path) -> bool:
        """
        Render a JARVIS arc-reactor icon at 4× resolution and downsample
        for crisp results at all sizes. Saves a multi-res .ico to out_path.
        Returns True on success.
        """
        try:
            from scripts.generate_icon import build_assets
            build_assets()
            if out_path.exists():
                return True
        except Exception:
            pass
        try:
            import math
            import PIL.Image
            import PIL.ImageDraw
            import PIL.ImageFilter
        except ImportError:
            return False

        CYAN   = (0, 212, 255)
        DIM    = (0, 100, 140)
        DARK   = (0, 6, 10)
        GLOW   = (0, 160, 200)
        WHITE  = (220, 240, 255)

        def _render(sz: int) -> PIL.Image.Image:
            S  = sz * 4                     # draw at 4× then downscale
            img = PIL.Image.new("RGBA", (S, S), (0, 0, 0, 0))
            d   = PIL.ImageDraw.Draw(img)
            cx = cy = S // 2

            # ── filled background circle ──────────────────────────────────
            R = S // 2 - 2
            d.ellipse([cx-R, cy-R, cx+R, cy+R], fill=(*DARK, 255))

            # ── outer border ring ─────────────────────────────────────────
            lw = max(2, S // 40)
            d.ellipse([cx-R, cy-R, cx+R, cy+R],
                      outline=(*CYAN, 220), width=lw)

            # ── mid decorative ring ───────────────────────────────────────
            R2 = int(R * 0.72)
            d.ellipse([cx-R2, cy-R2, cx+R2, cy+R2],
                      outline=(*DIM, 180), width=max(1, lw // 2))

            # ── 6 radial spokes (hex bolt) ────────────────────────────────
            R_inner = int(R * 0.30)
            R_outer = int(R * 0.62)
            spoke_w = max(1, S // 80)
            for i in range(6):
                angle = math.radians(i * 60 - 30)
                x1 = cx + int(R_inner * math.cos(angle))
                y1 = cy + int(R_inner * math.sin(angle))
                x2 = cx + int(R_outer * math.cos(angle))
                y2 = cy + int(R_outer * math.sin(angle))
                d.line([x1, y1, x2, y2], fill=(*GLOW, 200), width=spoke_w)

            # ── 6 tick marks on outer ring ────────────────────────────────
            for i in range(6):
                angle = math.radians(i * 60)
                for dr in range(lw * 2):
                    rx = (R - lw - dr)
                    d.point(
                        [cx + int(rx * math.cos(angle)),
                         cy + int(rx * math.sin(angle))],
                        fill=(*WHITE, 220),
                    )

            # ── inner glowing ring ────────────────────────────────────────
            Ri = int(R * 0.26)
            d.ellipse([cx-Ri, cy-Ri, cx+Ri, cy+Ri],
                      outline=(*CYAN, 255), width=max(2, lw))

            # ── bright glow soft blur applied before core ─────────────────
            # (draw a slightly larger cyan circle on a separate layer)
            glow_layer = PIL.Image.new("RGBA", (S, S), (0, 0, 0, 0))
            gd = PIL.ImageDraw.Draw(glow_layer)
            Rc = int(R * 0.13)
            gd.ellipse([cx-Rc*2, cy-Rc*2, cx+Rc*2, cy+Rc*2],
                       fill=(*CYAN, 110))
            glow_layer = glow_layer.filter(PIL.ImageFilter.GaussianBlur(S // 14))
            img = PIL.Image.alpha_composite(img, glow_layer)
            d   = PIL.ImageDraw.Draw(img)

            # ── core dot ──────────────────────────────────────────────────
            d.ellipse([cx-Rc, cy-Rc, cx+Rc, cy+Rc], fill=(*WHITE, 255))

            # ── downscale to target size ──────────────────────────────────
            return img.resize((sz, sz), PIL.Image.LANCZOS)

        try:
            sizes  = [256, 128, 64, 48, 32, 16]
            frames = [_render(s) for s in sizes]
            frames[0].save(
                out_path,
                format="ICO",
                append_images=frames[1:],
                sizes=[(s, s) for s in sizes],
            )
            return True
        except Exception as e:
            print(f"[Shortcut] ⚠️  Icon generation failed: {e}")
            return False

    @staticmethod
    def _create_lnk_windows(lnk: str, target: str, args: str,
                             work_dir: str, icon_loc: str) -> None:
        """
        Create a Windows .lnk shortcut WITHOUT launching PowerShell or cmd.
        Tries win32com (pywin32) first; falls back to wscript.exe + VBScript.
        wscript.exe is a GUI-mode host — it never opens a console window.
        """
        # ── Option 1: pywin32 (pure Python COM, zero subprocess) ──────────
        try:
            from win32com.client import Dispatch   # type: ignore
            sh = Dispatch("WScript.Shell")
            sc = sh.CreateShortCut(lnk)
            sc.TargetPath       = target
            sc.Arguments        = f'"{args}"'
            sc.WorkingDirectory = work_dir
            sc.Description      = "J.A.R.V.I.S AI Assistant"
            sc.IconLocation     = icon_loc
            sc.save()
            return
        except ImportError:
            pass

        # ── Option 2: wscript.exe + VBScript (always available on Windows,
        #    GUI-mode executable — never opens a console window) ────────────
        vbs = "\n".join([
            'Set ws = CreateObject("WScript.Shell")',
            f'Set sc = ws.CreateShortcut("{lnk}")',
            f'sc.TargetPath = "{target}"',
            f'sc.Arguments = Chr(34) & "{args}" & Chr(34)',
            f'sc.WorkingDirectory = "{work_dir}"',
            'sc.Description = "J.A.R.V.I.S AI Assistant"',
            f'sc.IconLocation = "{icon_loc}"',
            'sc.Save',
        ])
        import tempfile
        fd, tmp = tempfile.mkstemp(suffix=".vbs")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(vbs)
            proc = subprocess.Popen(
                ["wscript.exe", "/nologo", tmp],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            )
            proc.wait(timeout=10)
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass

    @staticmethod
    def _get_desktop_dir() -> Path:
        """
        Resolve the user's REAL desktop directory instead of assuming
        ~/Desktop, which breaks when:
          • OneDrive "Known Folder Move" relocates the desktop
            (C:/Users/x/OneDrive/Desktop) — very common on Win 10/11;
          • the XDG desktop is localized on Linux (~/Masaüstü,
            ~/Schreibtisch, ~/Bureau, …).
        Falls back to ~/Desktop only as a last resort.
        """
        home = Path.home()
        _os = platform.system()

        if _os == "Windows":
            # ── 1) SHGetKnownFolderPath(FOLDERID_Desktop) — the canonical
            #       answer; follows OneDrive redirection. No dependencies. ──
            try:
                import ctypes
                from ctypes import wintypes

                class _GUID(ctypes.Structure):
                    _fields_ = [("Data1", wintypes.DWORD),
                                ("Data2", wintypes.WORD),
                                ("Data3", wintypes.WORD),
                                ("Data4", ctypes.c_ubyte * 8)]

                # FOLDERID_Desktop {B4BFCC3A-DB2C-424C-B029-7FE99A87C641}
                fid = _GUID(0xB4BFCC3A, 0xDB2C, 0x424C,
                            (ctypes.c_ubyte * 8)(0xB0, 0x29, 0x7F, 0xE9,
                                                 0x9A, 0x87, 0xC6, 0x41))
                buf = ctypes.c_wchar_p()
                if ctypes.windll.shell32.SHGetKnownFolderPath(
                        ctypes.byref(fid), 0, None, ctypes.byref(buf)) == 0:
                    p = Path(buf.value)
                    ctypes.windll.ole32.CoTaskMemFree(buf)
                    if p.is_dir():
                        return p
            except Exception:
                pass

            # ── 2) Registry: User Shell Folders (may contain %VARS%) ──────
            try:
                import winreg
                with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion"
                        r"\Explorer\User Shell Folders") as key:
                    val, _t = winreg.QueryValueEx(key, "Desktop")
                p = Path(os.path.expandvars(val))
                if p.is_dir():
                    return p
            except Exception:
                pass

        elif _os == "Linux":
            # ── xdg-user-dir honours localized names (~/Masaüstü, …) ──────
            try:
                out = subprocess.run(["xdg-user-dir", "DESKTOP"],
                                     capture_output=True, text=True, timeout=5)
                p = Path(out.stdout.strip())
                if out.stdout.strip() and p != home and p.is_dir():
                    return p
            except Exception:
                pass
            try:
                cfg = home / ".config" / "user-dirs.dirs"
                for line in cfg.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("XDG_DESKTOP_DIR"):
                        val = line.split("=", 1)[1].strip().strip('"')
                        p = Path(val.replace("$HOME", str(home)))
                        if p != home and p.is_dir():
                            return p
            except Exception:
                pass

        # macOS: ~/Desktop is always the real path (localization is
        # display-only). Everything else lands here as a last resort.
        return home / "Desktop"

    def _create_desktop_shortcut(self):
        """
        Create a desktop shortcut on Windows / macOS / Linux.
        Never opens a terminal, console, or PowerShell window on any platform.
        """
        import stat as _stat
        script  = Path(__file__).resolve().parent / "main.py"
        python  = Path(sys.executable)
        desktop = self._get_desktop_dir()

        # Arc-reactor icon (.ico — also exported as .png for Linux/macOS)
        ico_path = Path(__file__).resolve().parent / "config" / "jarvis.ico"
        if not ico_path.exists():
            self._build_jarvis_icon(ico_path)

        try:
            _os = platform.system()

            # ── Windows ───────────────────────────────────────────────────────
            if _os == "Windows":
                vbs_launcher = script.parent / "launch_silent.vbs"
                wscript = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "wscript.exe"
                target = str(wscript if wscript.exists() else "wscript.exe")
                run_target = str(vbs_launcher if vbs_launcher.exists() else script.parent / "run_jarvis.pyw")
                lnk      = str(desktop / "J.A.R.V.I.S.lnk")
                icon_loc = f"{ico_path},0"
                self._create_lnk_windows(lnk, target, run_target,
                                         str(script.parent), icon_loc)

            # ── macOS — proper .app bundle (no Terminal window) ───────────────
            elif _os == "Darwin":
                app     = desktop / "J.A.R.V.I.S.app"
                mac_dir = app / "Contents" / "MacOS"
                res_dir = app / "Contents" / "Resources"
                mac_dir.mkdir(parents=True, exist_ok=True)
                res_dir.mkdir(exist_ok=True)

                # Launcher executable (bash — runs as background process,
                # macOS does NOT open Terminal for executables inside .app bundles)
                launcher = mac_dir / "JARVIS"
                launcher.write_text(
                    "#!/usr/bin/env bash\n"
                    f'cd "{script.parent}"\n'
                    f'exec "{python}" "{script}"\n'
                )
                launcher.chmod(launcher.stat().st_mode
                               | _stat.S_IEXEC | _stat.S_IXGRP | _stat.S_IXOTH)

                # Minimal Info.plist (required for .app recognition)
                (app / "Contents" / "Info.plist").write_text(
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                    '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                    '<plist version="1.0"><dict>\n'
                    '  <key>CFBundleExecutable</key><string>JARVIS</string>\n'
                    '  <key>CFBundleIdentifier</key>'
                    '<string>com.jarvis.assistant</string>\n'
                    '  <key>CFBundleName</key><string>J.A.R.V.I.S</string>\n'
                    '  <key>CFBundlePackageType</key><string>APPL</string>\n'
                    '  <key>CFBundleVersion</key><string>1.0</string>\n'
                    '</dict></plist>\n'
                )

                # Optional: copy icon as .icns (skip silently if Pillow is missing)
                try:
                    import PIL.Image
                    icns = res_dir / "AppIcon.icns"
                    PIL.Image.open(ico_path).save(icns, format="ICNS")
                    # Inject icon reference into plist
                    plist = app / "Contents" / "Info.plist"
                    txt = plist.read_text()
                    plist.write_text(
                        txt.replace(
                            '</dict></plist>',
                            '  <key>CFBundleIconFile</key>'
                            '<string>AppIcon</string>\n</dict></plist>\n',
                        )
                    )
                except Exception:
                    pass  # icon is optional

            # ── Linux — .desktop file (Terminal=false, no console) ────────────
            else:
                # Export .ico → .png for better desktop integration
                png_path = ico_path.with_suffix(".png")
                if not png_path.exists() and ico_path.exists():
                    try:
                        import PIL.Image
                        PIL.Image.open(ico_path).resize(
                            (256, 256), PIL.Image.LANCZOS
                        ).save(png_path, format="PNG")
                    except Exception:
                        png_path = ico_path  # fallback to .ico

                icon_line = f"Icon={png_path}\n" if png_path.exists() else ""
                desk = desktop / "J.A.R.V.I.S.desktop"
                desk.write_text(
                    "[Desktop Entry]\n"
                    "Name=J.A.R.V.I.S\n"
                    f"Exec={python} {script}\n"
                    f"Path={script.parent}\n"
                    "Type=Application\n"
                    "Terminal=false\n"
                    "Categories=Utility;\n"
                    + icon_line
                )
                desk.chmod(desk.stat().st_mode | 0o755)

            self._log.append_log("SYS: Desktop shortcut created.")
        except Exception as e:
            self._log.append_log(f"ERR: Shortcut failed — {e}")

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cw = self.centralWidget()
        if self._overlay and self._overlay.isVisible():
            ow, oh = 460, 390
            self._overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
        if self._remote_overlay and self._remote_overlay.isVisible():
            ow, oh = RemoteKeyOverlay._OW, RemoteKeyOverlay._OH
            self._remote_overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
        if self._customize_overlay and self._customize_overlay.isVisible():
            ow, oh = CustomizeOverlay._OW, CustomizeOverlay._OH
            self._customize_overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
        if self._provider_overlay and self._provider_overlay.isVisible():
            ow, oh = ProviderSettingsOverlay._OW, ProviderSettingsOverlay._OH
            oh = min(oh, cw.height() - 16)
            self._provider_overlay.setGeometry(
                (cw.width()  - ow) // 2,
                (cw.height() - oh) // 2,
                ow, oh,
            )
        # Camera preview — bottom-right corner of the center/HUD area
        pw = _CameraPreview._W
        ph = self._cam_preview.height() or _CameraPreview._H
        self._cam_preview.setGeometry(
            cw.width() - _RIGHT_W - pw - 12,
            cw.height() - ph - 28,
            pw, ph,
        )
        # Clipboard panel — bottom-center
        if hasattr(self, '_clipboard_panel') and self._clipboard_panel.isVisible():
            self._position_clipboard_panel()
        # Quick drawer — reposition if open
        if hasattr(self, '_quick_drawer') and self._quick_drawer.isVisible():
            self._position_quick_drawer()

    def _update_metrics(self):
        snap = _metrics.snapshot()

        # CPU
        cpu = snap["cpu"]
        self._bar_cpu.set_value(cpu, f"{cpu:.0f}%")

        # MEM
        mem = snap["mem"]
        self._bar_mem.set_value(mem, f"{mem:.0f}%")

        # NET
        net = snap["net"]
        if net < 1.0:
            net_str = f"{net*1024:.0f}KB/s"
        else:
            net_str = f"{net:.1f}MB/s"
        net_pct = min(100, net * 10)  # 10 MB/s = %100
        self._bar_net.set_value(net_pct, net_str)

        # GPU
        gpu = snap["gpu"]
        if gpu >= 0:
            self._bar_gpu.set_value(gpu, f"{gpu:.0f}%")
        else:
            self._bar_gpu.set_value(0, "N/A")

        # TMP
        tmp = snap["tmp"]
        if tmp >= 0:
            tmp_pct = min(100, (tmp / 100) * 100)
            self._bar_tmp.set_value(tmp_pct, f"{tmp:.0f}°C")
        else:
            self._bar_tmp.set_value(0, "N/A")

        try:
            boot_t  = psutil.boot_time()
            elapsed = time.time() - boot_t
            h = int(elapsed // 3600)
            m = int((elapsed % 3600) // 60)
            self._uptime_lbl.setText(f"UP  {h:02d}:{m:02d}")
        except Exception:
            self._uptime_lbl.setText("UP  --:--")

        try:
            proc_count = len(psutil.pids())
            self._proc_lbl.setText(f"PROC  {proc_count}")
        except Exception:
            self._proc_lbl.setText("PROC  --")

        self._update_disk_gauges()

    def _update_disk_gauges(self):
        if not hasattr(self, "_disk_lay"):
            return
        try:
            from core.system_info import get_drive_stats
            drives = get_drive_stats()
            if not hasattr(self, "_disk_widgets"):
                self._disk_widgets = {}

            current_letters = {d["letter"]: d for d in drives[:3]}

            # Clean up widgets for drives that are no longer present
            for letter in list(self._disk_widgets.keys()):
                if letter not in current_letters:
                    _, _, row_w = self._disk_widgets.pop(letter)
                    row_w.setParent(None)
                    row_w.deleteLater()

            for d in drives[:3]:
                letter = d["letter"]
                pct = int(d["percent"])
                bar_col = C.RED if pct > 90 else (C.ACC if pct > 75 else C.PRI)

                if letter in self._disk_widgets:
                    lbl, bar, _ = self._disk_widgets[letter]
                    lbl.setText(f"{letter} {pct}%")
                    bar.setValue(pct)
                    bar.setStyleSheet(f"""
                        QProgressBar {{ background: #00121d; border: 1px solid {C.BORDER}; border-radius: 2px; }}
                        QProgressBar::chunk {{ background: {bar_col}; border-radius: 1px; }}
                    """)
                else:
                    row_w = QWidget()
                    row = QHBoxLayout(row_w)
                    row.setContentsMargins(0, 0, 0, 0)
                    row.setSpacing(4)

                    lbl = QLabel(f"{letter} {pct}%")
                    lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
                    lbl.setStyleSheet(f"color: {C.TEXT_MED}; border: none; background: transparent;")

                    bar = QProgressBar()
                    bar.setFixedHeight(6)
                    bar.setTextVisible(False)
                    bar.setRange(0, 100)
                    bar.setValue(pct)
                    bar.setStyleSheet(f"""
                        QProgressBar {{ background: #00121d; border: 1px solid {C.BORDER}; border-radius: 2px; }}
                        QProgressBar::chunk {{ background: {bar_col}; border-radius: 1px; }}
                    """)

                    row.addWidget(lbl)
                    row.addWidget(bar)
                    self._disk_widgets[letter] = (lbl, bar, row_w)
                    self._disk_lay.addWidget(row_w)
        except Exception:
            pass

    def _refresh_weather_async(self):
        def _fetch():
            try:
                from core.system_info import get_free_weather, get_ip_location
                loc = get_ip_location()
                city = loc.get("city", "Patna")
                lat = loc.get("lat")
                lon = loc.get("lon")
                w = get_free_weather(lat=lat, lon=lon, city=city)
                if w.get("success"):
                    try:
                        c_file = CONFIG_DIR / "weather_cache.json"
                        c_file.write_text(json.dumps(w, ensure_ascii=False), encoding="utf-8")
                    except Exception:
                        pass
                    QTimer.singleShot(0, lambda: self._apply_weather_ui(w))
            except Exception:
                pass
        threading.Thread(target=_fetch, daemon=True).start()

    def _apply_weather_ui(self, w: dict):
        if hasattr(self, '_w_loc_lbl'):
            self._w_loc_lbl.setText(f"📍 {w.get('city', 'LOCAL').upper()[:12]}")
            self._w_temp_lbl.setText(f"{w.get('icon', '🌤️')} {w.get('temp', '--')}")
            self._w_desc_lbl.setText(f"{w.get('desc', '')} · {w.get('wind', '')}")

    def _rotate_news_ticker(self):
        def _fetch_or_cycle():
            try:
                from core.system_info import fetch_top_dev_news
                if not self._news_items:
                    self._news_items = fetch_top_dev_news(5)
                if self._news_items:
                    item = self._news_items[self._news_idx % len(self._news_items)]
                    self._news_idx += 1
                    t = item.get("title", "")
                    if t and hasattr(self, "_news_lbl"):
                        QTimer.singleShot(0, lambda: self._news_lbl.setText(f"📡 DEV NEWS: {t[:55]}..."))
            except Exception:
                pass
        threading.Thread(target=_fetch_or_cycle, daemon=True).start()

    def _quick_test_voice(self):
        self._log.append_log("SYS: Quick testing local voice (Piper Hindi)...")
        def _run():
            from core.tts import test_tts_voice
            ok, msg = test_tts_voice("piper_hindi")
            self._log.append_log(f"VOICE: {msg}")
        threading.Thread(target=_run, daemon=True).start()

    def _quick_toggle_cam(self):
        if self._hud_cam_stack.currentIndex() == 1:
            self.stop_camera_stream()
            self._log.append_log("SYS: Camera feed closed.")
        else:
            self.start_camera_stream()
            self._log.append_log("SYS: Live camera feed opened on central HUD.")

    def _quick_ping_apis(self):
        self._log.append_log("SYS: Pinging active AI provider...")
        def _run():
            try:
                from core.multi_llm import test_llm_provider
                cfg = _read_full_config()
                p = cfg.get("active_provider", "groq")
                k = cfg.get(f"{p}_api_key", "")
                ok, lat, err = test_llm_provider(p, k)
                if ok:
                    self._log.append_log(f"PROVIDER: {p.upper()} reachable ({lat:.0f}ms) [OK]")
                else:
                    self._log.append_log(f"PROVIDER: {p.upper()} ping failed: {err}")
            except Exception as e:
                self._log.append_log(f"PROVIDER: Ping error: {e}")
        threading.Thread(target=_run, daemon=True).start()

    def _quick_clear_log(self):
        self._log.clear_log()
        self._log.append_log("SYS: Activity log cleared.")


    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(54)
        w.setStyleSheet(f"background: {C.DARK}; border-bottom: 1px solid {C.BORDER_B};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(16, 0, 16, 0)

        def _badge(txt, color=C.TEXT_MED):
            l = QLabel(txt)
            l.setFont(QFont("Courier New", 8))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_badge(APP_VERSION, C.PRI_DIM))
        lay.addSpacing(8)
        self._drawer_btn = QPushButton("⚙")
        self._drawer_btn.setFixedSize(26, 26)
        self._drawer_btn.setFont(QFont("Courier New", 11))
        self._drawer_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._drawer_btn.setToolTip("Settings & Controls")
        self._drawer_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_DIM};
                border: 1px solid {C.BORDER}; border-radius: 4px;
            }}
            QPushButton:hover {{ color: {C.PRI}; border-color: {C.PRI_DIM}; }}
            QPushButton:checked {{ color: {C.PRI}; border-color: {C.PRI}; background: {C.PRI_GHO}; }}
        """)
        self._drawer_btn.setCheckable(True)
        self._drawer_btn.clicked.connect(self._toggle_drawer)
        lay.addWidget(self._drawer_btn)
        lay.addStretch()

        mid = QVBoxLayout(); mid.setSpacing(1)
        _disp = self._assistant_name.upper()
        self._title_lbl = QLabel(_disp)
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_lbl.setFont(QFont("Courier New", 17, QFont.Weight.Bold))
        self._title_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        mid.addWidget(self._title_lbl)
        _cur_persona = get_persona_mode()
        persona_subtitles = {
            "jarvis": "Just A Rather Very Intelligent System",
            "teacher": "AI Mentor & Academic Instructor",
            "companion": "💖 Devoted Romantic Partner & Soulmate",
            "devops": "Autonomous DevOps & Cloud Specialist",
        }
        if _disp in ("JARVIS", "J.A.R.V.I.S") and _cur_persona == "jarvis":
            _sub_text = "Just A Rather Very Intelligent System"
        elif _cur_persona in persona_subtitles:
            _sub_text = persona_subtitles[_cur_persona]
        else:
            _sub_text = "Personal AI Assistant"
        self._sub_lbl = QLabel(_sub_text)
        self._sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub_lbl.setFont(QFont("Courier New", 7))
        self._sub_lbl.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        mid.addWidget(self._sub_lbl)
        lay.addLayout(mid)
        lay.addStretch()

        right_col = QVBoxLayout(); right_col.setSpacing(2)
        self._clock_lbl = QLabel("00:00:00")
        self._clock_lbl.setFont(QFont("Courier New", 14, QFont.Weight.Bold))
        self._clock_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._clock_lbl)
        self._date_lbl = QLabel("")
        self._date_lbl.setFont(QFont("Courier New", 7))
        self._date_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_col.addWidget(self._date_lbl)
        lay.addLayout(right_col)
        return w

    def _tick_clock(self):
        self._clock_lbl.setText(time.strftime("%H:%M:%S"))
        self._date_lbl.setText(time.strftime("%a %d %b %Y"))

    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_LEFT_W)
        w.setStyleSheet(f"background: {C.DARK}; border-right: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 10, 8, 10)
        lay.setSpacing(6)

        hdr = QLabel("◈ SYS MONITOR")
        hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; "
                          f"border-bottom: 1px solid {C.BORDER}; padding-bottom: 4px;")
        lay.addWidget(hdr)
        lay.addSpacing(2)

        self._bar_cpu = MetricBar("CPU", C.PRI)
        self._bar_mem = MetricBar("MEM", C.ACC2)
        self._bar_net = MetricBar("NET", C.GREEN)
        self._bar_gpu = MetricBar("GPU", C.ACC)
        self._bar_tmp = MetricBar("TMP", "#ff6688")

        for bar in [self._bar_cpu, self._bar_mem, self._bar_net,
                    self._bar_gpu, self._bar_tmp]:
            lay.addWidget(bar)

        lay.addSpacing(4)

        info_panel = QWidget()
        info_panel.setStyleSheet(
            f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 4px;"
        )
        ip_lay = QVBoxLayout(info_panel)
        ip_lay.setContentsMargins(6, 5, 6, 5)
        ip_lay.setSpacing(3)

        self._uptime_lbl = QLabel("UP  --:--")
        self._uptime_lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._uptime_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent; border: none;")
        ip_lay.addWidget(self._uptime_lbl)

        self._proc_lbl = QLabel("PROC  --")
        self._proc_lbl.setFont(QFont("Courier New", 8))
        self._proc_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; border: none;")
        ip_lay.addWidget(self._proc_lbl)

        os_name = {"Windows": "WIN", "Darwin": "macOS", "Linux": "LINUX"}.get(_OS, _OS.upper())
        os_lbl = QLabel(f"OS  {os_name}")
        os_lbl.setFont(QFont("Courier New", 8))
        os_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent; border: none;")
        ip_lay.addWidget(os_lbl)

        lay.addWidget(info_panel)
        lay.addSpacing(4)

        # ── 1) Storage Gauges (C:, D:, E:) ──────────────────────────────────
        disk_hdr = QLabel("◈ DISK STORAGE")
        disk_hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        disk_hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; border-bottom: 1px solid {C.BORDER}; padding-bottom: 2px;")
        lay.addWidget(disk_hdr)

        self._disk_panel = QWidget()
        self._disk_panel.setStyleSheet(f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 4px;")
        self._disk_lay = QVBoxLayout(self._disk_panel)
        self._disk_lay.setContentsMargins(6, 4, 6, 4)
        self._disk_lay.setSpacing(3)
        lay.addWidget(self._disk_panel)
        self._update_disk_gauges()
        lay.addSpacing(4)

        # ── 2) Atmosphere / Free Open-Meteo Weather ──────────────────────────
        weather_hdr = QLabel("◈ ATMOSPHERE")
        weather_hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        weather_hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; border-bottom: 1px solid {C.BORDER}; padding-bottom: 2px;")
        lay.addWidget(weather_hdr)

        self._weather_card = QWidget()
        self._weather_card.setStyleSheet(f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 4px;")
        w_lay = QVBoxLayout(self._weather_card)
        w_lay.setContentsMargins(6, 4, 6, 4)
        w_lay.setSpacing(2)

        self._w_loc_lbl = QLabel("📍 LOCATING...")
        self._w_loc_lbl.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        self._w_loc_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent; border: none;")
        w_lay.addWidget(self._w_loc_lbl)

        self._w_temp_lbl = QLabel("🌤️ --°C")
        self._w_temp_lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._w_temp_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent; border: none;")
        w_lay.addWidget(self._w_temp_lbl)

        self._w_desc_lbl = QLabel("Live Open-Meteo (0 Tokens)")
        self._w_desc_lbl.setFont(QFont("Courier New", 6))
        self._w_desc_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        self._w_desc_lbl.setWordWrap(True)
        w_lay.addWidget(self._w_desc_lbl)

        # Populate immediately from weather cache if present
        try:
            c_file = CONFIG_DIR / "weather_cache.json"
            if c_file.exists():
                _cw = json.loads(c_file.read_text(encoding="utf-8"))
                if _cw.get("city"):
                    self._w_loc_lbl.setText(f"📍 {_cw.get('city', 'LOCAL').upper()[:12]}")
                    self._w_temp_lbl.setText(f"{_cw.get('icon', '🌤️')} {_cw.get('temp', '--')}")
                    self._w_desc_lbl.setText(f"{_cw.get('desc', '')} · {_cw.get('wind', '')}")
        except Exception:
            pass

        lay.addWidget(self._weather_card)
        lay.addSpacing(4)

        # ── 3) Compact Telemetry Status Badges ──────────────────────────────
        badge_row = QHBoxLayout()
        badge_row.setSpacing(3)
        for txt, col in [
            ("AI CORE\nONLINE", C.GREEN),
            ("SEC\nOK", C.PRI),
            (f"PROTO\n{APP_PROTOCOL[:4]}", C.TEXT_DIM),
        ]:
            lbl = QLabel(txt)
            lbl.setFont(QFont("Courier New", 6, QFont.Weight.Bold))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {col}; background: {C.PANEL2};"
                f"border: 1px solid {C.BORDER_A}; border-radius: 3px; padding: 2px;"
            )
            badge_row.addWidget(lbl)
        lay.addLayout(badge_row)

        return w
    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_RIGHT_W)
        w.setStyleSheet(f"background: {C.DARK}; border-left: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        def _sec(txt):
            l = QLabel(f"▸ {txt}")
            l.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            l.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            return l

        lay.addWidget(_sec("ACTIVITY LOG"))
        self._log = LogWidget()
        lay.addWidget(self._log, stretch=1)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        lay.addWidget(_sec("FILE UPLOAD"))
        self._drop_zone = FileDropZone()
        self._drop_zone.file_selected.connect(self._on_file_selected)
        lay.addWidget(self._drop_zone)

        self._file_hint = QLabel("No file loaded — drop or click above to upload")
        self._file_hint.setFont(QFont("Courier New", 7))
        self._file_hint.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._file_hint.setWordWrap(True)
        lay.addWidget(self._file_hint)

        # Quick Actions Grid (Cyber Matrix)
        lay.addWidget(_sec("QUICK ACTIONS"))
        q_row = QHBoxLayout()
        q_row.setSpacing(4)

        _Q_BTN_STYLE = f"""
            QPushButton {{
                background: #000c14; color: {C.PRI};
                border: 1px solid {C.BORDER_A}; border-radius: 3px;
                padding: 4px 2px;
            }}
            QPushButton:hover {{
                background: {C.PRI_GHO}; border: 1px solid {C.PRI}; color: {C.WHITE};
            }}
            QPushButton:pressed {{
                background: #002233;
            }}
        """

        btn_voice = QPushButton("🔊 VOICE")
        btn_voice.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        btn_voice.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_voice.setStyleSheet(_Q_BTN_STYLE)
        btn_voice.setToolTip("Quick Voice Test (Piper Offline Hindi)")
        btn_voice.clicked.connect(self._quick_test_voice)
        q_row.addWidget(btn_voice)

        btn_cam = QPushButton("📷 CAM")
        btn_cam.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        btn_cam.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cam.setStyleSheet(_Q_BTN_STYLE)
        btn_cam.setToolTip("Toggle Live Camera HUD")
        btn_cam.clicked.connect(self._quick_toggle_cam)
        q_row.addWidget(btn_cam)

        btn_ping = QPushButton("⚡ PING")
        btn_ping.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        btn_ping.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ping.setStyleSheet(_Q_BTN_STYLE)
        btn_ping.setToolTip("Ping Active AI Provider")
        btn_ping.clicked.connect(self._quick_ping_apis)
        q_row.addWidget(btn_ping)

        btn_clr = QPushButton("🧹 CLEAR")
        btn_clr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        btn_clr.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clr.setStyleSheet(_Q_BTN_STYLE)
        btn_clr.setToolTip("Clear Activity Log")
        btn_clr.clicked.connect(self._quick_clear_log)
        q_row.addWidget(btn_clr)

        btn_studio = QPushButton("🎨 HUD")
        btn_studio.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        btn_studio.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_studio.setStyleSheet(_Q_BTN_STYLE)
        btn_studio.setToolTip("Open HUD Customization Studio")
        btn_studio.clicked.connect(self._open_customize)
        q_row.addWidget(btn_studio)

        lay.addLayout(q_row)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep2)

        lay.addWidget(_sec("COMMAND INPUT"))
        lay.addLayout(self._build_input_row())

        self._interrupt_btn = QPushButton("✋  INTERRUPT  [ESC]")
        self._interrupt_btn.setFixedHeight(34)
        self._interrupt_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._interrupt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._interrupt_btn.setStyleSheet(f"""
            QPushButton {{
                background: #140008; color: {C.MUTED_C};
                border: 1px solid {C.MUTED_C}; border-radius: 3px;
            }}
            QPushButton:hover {{
                background: #200010; border: 1px solid #ff6688;
            }}
            QPushButton:pressed {{
                background: #300018;
            }}
        """)
        self._interrupt_btn.clicked.connect(self._do_interrupt)
        lay.addWidget(self._interrupt_btn)

        self._mute_btn = QPushButton("🎙  MICROPHONE ACTIVE")
        self._mute_btn.setFixedHeight(30)
        self._mute_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mute_btn.clicked.connect(self._toggle_mute)
        self._style_mute_btn()
        lay.addWidget(self._mute_btn)

        return w

    def _build_quick_drawer(self) -> QWidget:
        """Floating overlay panel shown when the ⚙ header button is toggled."""
        _BTN_STYLE_PRI = f"""
            QPushButton {{
                background: #00091a; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
                text-align: left; padding: 0 8px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
        """
        _BTN_STYLE_DIM = f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
                text-align: left; padding: 0 8px;
            }}
            QPushButton:hover {{ color: {C.PRI}; border-color: {C.BORDER_B}; }}
        """

        w = QWidget(self.centralWidget())
        w.setObjectName("QuickDrawer")
        w.setStyleSheet(f"""
            QWidget#QuickDrawer {{
                background: {C.DARK};
                border: 1px solid {C.BORDER_B};
                border-top: none;
                border-radius: 0 0 6px 6px;
            }}
        """)
        w.hide()

        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(5)

        hdr = QLabel("◈ CONTROLS")
        hdr.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent; "
                          f"border-bottom: 1px solid {C.BORDER}; padding-bottom: 4px;")
        lay.addWidget(hdr)

        remote_btn = QPushButton("◉  REMOTE CONTROL")
        remote_btn.setFixedHeight(30)
        remote_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        remote_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remote_btn.setStyleSheet(_BTN_STYLE_PRI)
        remote_btn.clicked.connect(self._open_remote)
        lay.addWidget(remote_btn)

        fs_btn = QPushButton("⛶  FULLSCREEN  [F11]")
        fs_btn.setFixedHeight(26)
        fs_btn.setFont(QFont("Courier New", 7))
        fs_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        fs_btn.setStyleSheet(_BTN_STYLE_DIM)
        fs_btn.clicked.connect(self._toggle_fullscreen)
        lay.addWidget(fs_btn)

        sc_btn = QPushButton("⊞  CREATE DESKTOP SHORTCUT")
        sc_btn.setFixedHeight(26)
        sc_btn.setFont(QFont("Courier New", 7))
        sc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        sc_btn.setStyleSheet(_BTN_STYLE_DIM)
        sc_btn.clicked.connect(self._create_desktop_shortcut)
        lay.addWidget(sc_btn)

        self._autostart_btn = QPushButton("◉  AUTO-START: OFF")
        self._autostart_btn.setFixedHeight(26)
        self._autostart_btn.setFont(QFont("Courier New", 7))
        self._autostart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._autostart_btn.clicked.connect(self._toggle_autostart)
        lay.addWidget(self._autostart_btn)

        cust_btn = QPushButton("⚙  HUD STUDIO & CUSTOMISE")
        cust_btn.setFixedHeight(26)
        cust_btn.setFont(QFont("Courier New", 7))
        cust_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cust_btn.setStyleSheet(_BTN_STYLE_DIM)
        cust_btn.clicked.connect(self._open_customize)
        lay.addWidget(cust_btn)

        prov_btn = QPushButton("🌐  LLM PROVIDERS & KEYS")
        prov_btn.setFixedHeight(26)
        prov_btn.setFont(QFont("Courier New", 7))
        prov_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        prov_btn.setStyleSheet(_BTN_STYLE_DIM)
        prov_btn.clicked.connect(self._open_providers)
        lay.addWidget(prov_btn)

        self._brief_btn = QPushButton()
        self._brief_btn.setFixedHeight(26)
        self._brief_btn.setFont(QFont("Courier New", 7))
        self._brief_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._brief_btn.clicked.connect(self._toggle_brief)
        lay.addWidget(self._brief_btn)

        # ── Wake word ──────────────────────────────────────────────────────────
        self._wake_btn = QPushButton()
        self._wake_btn.setFixedHeight(26)
        self._wake_btn.setFont(QFont("Courier New", 7))
        self._wake_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._wake_btn.clicked.connect(self._toggle_wake_word)
        lay.addWidget(self._wake_btn)

        self._wake_sleep_btn = QPushButton()
        self._wake_sleep_btn.setFixedHeight(26)
        self._wake_sleep_btn.setFont(QFont("Courier New", 7))
        self._wake_sleep_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._wake_sleep_btn.clicked.connect(self._tap_wake_manual)
        lay.addWidget(self._wake_sleep_btn)
        # Neutral placeholder now; the real state (which may load the model to
        # check readiness) is resolved lazily the first time the drawer opens.
        self._wake_btn.setText("🎙  WAKE WORD")
        self._wake_btn.setStyleSheet(_BTN_STYLE_DIM)
        self._wake_sleep_btn.hide()

        audio_btn = QPushButton("🎧  AUDIO DEVICES")
        audio_btn.setFixedHeight(26)
        audio_btn.setFont(QFont("Courier New", 7))
        audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        audio_btn.setStyleSheet(_BTN_STYLE_DIM)
        audio_btn.clicked.connect(self._open_audio_devices)
        lay.addWidget(audio_btn)

        mem_btn = QPushButton("🧠  MEMORY")
        mem_btn.setFixedHeight(26)
        mem_btn.setFont(QFont("Courier New", 7))
        mem_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        mem_btn.setStyleSheet(_BTN_STYLE_DIM)
        mem_btn.clicked.connect(self._open_memory_panel)
        lay.addWidget(mem_btn)

        plugin_btn = QPushButton("🧩  PLUGINS")
        plugin_btn.setFixedHeight(26)
        plugin_btn.setFont(QFont("Courier New", 7))
        plugin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        plugin_btn.setStyleSheet(_BTN_STYLE_DIM)
        plugin_btn.clicked.connect(self._open_plugin_manager)
        lay.addWidget(plugin_btn)

        settings_btn = QPushButton("⚙  PLUGIN SETTINGS")
        settings_btn.setFixedHeight(26)
        settings_btn.setFont(QFont("Courier New", 7))
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setStyleSheet(_BTN_STYLE_DIM)
        settings_btn.clicked.connect(self._open_plugin_settings)
        lay.addWidget(settings_btn)

        w.adjustSize()
        return w

    def _toggle_drawer(self, checked: bool):
        if checked:
            self._refresh_wake_btns()   # resolve wake state on open (lazy)
            self._position_quick_drawer()
            self._quick_drawer.show()
            self._quick_drawer.raise_()
        else:
            self._quick_drawer.hide()

    def _position_quick_drawer(self):
        if not hasattr(self, '_quick_drawer'):
            return
        _W = 220
        self._quick_drawer.setFixedWidth(_W)
        self._quick_drawer.adjustSize()
        self._quick_drawer.setGeometry(12, 54, _W, self._quick_drawer.sizeHint().height())

    def _build_input_row(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(5)
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a command or question…")
        self._input.setFont(QFont("Courier New", 9))
        self._input.setFixedHeight(30)
        self._input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d14; color: {C.WHITE};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 3px 7px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        self._input.returnPressed.connect(self._send)
        row.addWidget(self._input)

        send = QPushButton("▸")
        send.setFixedSize(30, 30)
        send.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        send.setCursor(Qt.CursorShape.PointingHandCursor)
        send.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL}; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        send.clicked.connect(self._send)
        row.addWidget(send)
        return row

    def _build_content_panel(self) -> QWidget:
        """
        Collapsible panel below the HUD — shows search results, news, briefings.
        Hidden by default; appears when show_content() is called.
        """
        w = QWidget()
        w.setObjectName("ContentPanel")
        w.setStyleSheet(f"""
            QWidget#ContentPanel {{
                background: {C.PANEL};
                border-top: 1px solid {C.BORDER_B};
            }}
        """)
        w.hide()

        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 7, 12, 8)
        lay.setSpacing(5)

        # ── header row ───────────────────────────────────────────────────────
        hdr = QHBoxLayout(); hdr.setSpacing(6)

        dot = QLabel("◈")
        dot.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        dot.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hdr.addWidget(dot)

        self._content_title_lbl = QLabel("BRIEFING")
        self._content_title_lbl.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        self._content_title_lbl.setStyleSheet(
            f"color: {C.PRI}; background: transparent; letter-spacing: 1px;"
        )
        hdr.addWidget(self._content_title_lbl)
        hdr.addStretch()

        self._content_ts_lbl = QLabel("")
        self._content_ts_lbl.setFont(QFont("Courier New", 7))
        self._content_ts_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        hdr.addWidget(self._content_ts_lbl)

        dismiss = QPushButton("DISMISS  ✕")
        dismiss.setFont(QFont("Courier New", 7))
        dismiss.setFixedHeight(18)
        dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_DIM};
                border: 1px solid {C.BORDER}; border-radius: 2px; padding: 0 5px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        dismiss.clicked.connect(w.hide)
        hdr.addWidget(dismiss)
        lay.addLayout(hdr)

        # ── separator ─────────────────────────────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};"); lay.addWidget(sep)

        # ── text display ──────────────────────────────────────────────────────
        self._content_display = QTextEdit()
        self._content_display.setReadOnly(True)
        self._content_display.setFont(QFont("Courier New", 8))
        self._content_display.setMinimumHeight(60)
        self._content_display.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._content_display.setStyleSheet(f"""
            QTextEdit {{
                background: {C.DARK};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 3px;
                padding: 6px 8px;
                selection-background-color: {C.PRI_GHO};
            }}
            QScrollBar:vertical {{
                background: {C.BG}; width: 6px; border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_B}; border-radius: 3px; min-height: 16px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0; border: none;
            }}
        """)
        lay.addWidget(self._content_display)

        return w

    def _show_content(self, title: str, text: str):
        """Slot — runs on Qt main thread. Updates and shows the content panel."""
        import time as _time
        self._content_title_lbl.setText(title.upper()[:48])
        self._content_ts_lbl.setText(_time.strftime("%H:%M:%S"))
        self._content_display.setPlainText(text)
        self._content_display.moveCursor(
            self._content_display.textCursor().MoveOperation.Start
        )
        first_show = not self._content_panel.isVisible()
        self._content_panel.show()
        if first_show:
            total = self._center_split.height()
            self._center_split.setSizes([max(total - 220, 120), 220])

    def _build_footer(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(22)
        w.setStyleSheet(f"background: {C.DARK}; border-top: 1px solid {C.BORDER};")
        lay = QHBoxLayout(w); lay.setContentsMargins(14, 0, 14, 0)

        def _fl(txt, color=C.TEXT_MED):
            l = QLabel(txt); l.setFont(QFont("Courier New", 7))
            l.setStyleSheet(f"color: {color}; background: transparent;")
            return l

        lay.addWidget(_fl("[F4] Mute  ·  [F11] Fullscreen"))
        lay.addSpacing(14)

        self._news_lbl = QLabel("📡 DEV NEWS: Connecting to HackerNews...")
        self._news_lbl.setFont(QFont("Courier New", 7))
        self._news_lbl.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        lay.addWidget(self._news_lbl)

        lay.addStretch()
        lay.addWidget(_fl("By SudhirDevOps1", C.PRI_DIM))
        return w

    def _on_file_selected(self, path: str):
        self._current_file = path
        p    = Path(path)
        cat  = _file_category(p)
        icon, _ = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        size = _fmt_size(p.stat().st_size)
        self._file_hint.setText(f"{icon}  {p.name}  ·  {size}  ·  Tell {self._assistant_name} what to do with it")
        self._log.append_log(f"FILE: {p.name} ({size}) loaded")
        if self.on_text_command:
            msg = (
                f"[FILE_UPLOADED] path={path} | name={p.name} | "
                f"type={p.suffix.lstrip('.')} | size={size} | "
                f"Briefly tell the user you can see the file '{p.name}' "
                f"({size}) has been uploaded and ask what they'd like to do with it."
            )
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    def notify_phone_connected(self) -> None:
        if self._remote_overlay and self._remote_overlay.isVisible():
            self._remote_overlay.mark_connected()

    def _open_remote(self):
        if not self.on_remote_clicked:
            self._log.append_log("SYS: Dashboard not running — remote unavailable.")
            return
        result = self.on_remote_clicked()
        if not result:
            self._log.append_log("SYS: Could not generate remote key.")
            return
        url    = result[0]
        key    = result[1]
        auto   = result[2] if len(result) >= 3 else ""
        manual = result[3] if len(result) >= 4 else url
        if self._remote_overlay:
            self._remote_overlay._do_close()
        cw  = self.centralWidget()
        ow, oh = RemoteKeyOverlay._OW, RemoteKeyOverlay._OH
        ov  = RemoteKeyOverlay(url, key, auto_login_url=auto, manual_url=manual,
                               expiry_secs=600, parent=cw)
        ov.set_new_key_callback(self.on_remote_clicked)
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.closed.connect(lambda: setattr(self, '_remote_overlay', None))
        ov.show()
        self._remote_overlay = ov
        self._log.append_log(f"SYS: Remote key generated — manual: {manual or url}")

    # ── Auto-start ──────────────────────────────────────────────────────────────

    def _check_autostart(self) -> bool:
        """Returns True if auto-start is currently registered on this OS."""
        try:
            if _OS == "Windows":
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
                try:
                    winreg.QueryValueEx(key, "JARVIS_AI")
                    return True
                except FileNotFoundError:
                    return False
                finally:
                    winreg.CloseKey(key)
            elif _OS == "Darwin":
                return (Path.home() / "Library" / "LaunchAgents"
                        / "com.jarvis.assistant.plist").exists()
            else:
                return (Path.home() / ".config" / "autostart" / "jarvis.desktop").exists()
        except Exception:
            return False

    def _toggle_autostart(self):
        currently_on = self._check_autostart()
        try:
            script = str(Path(__file__).resolve().parent / "main.py")
            if _OS == "Windows":
                import winreg
                reg = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
                if currently_on:
                    winreg.DeleteValue(reg, "JARVIS_AI")
                else:
                    pythonw = Path(sys.executable).parent / "pythonw.exe"
                    exe = str(pythonw if pythonw.exists() else sys.executable)
                    winreg.SetValueEx(reg, "JARVIS_AI", 0, winreg.REG_SZ,
                                      f'"{exe}" "{script}"')
                winreg.CloseKey(reg)
            elif _OS == "Darwin":
                plist_dir = Path.home() / "Library" / "LaunchAgents"
                plist_dir.mkdir(parents=True, exist_ok=True)
                plist = plist_dir / "com.jarvis.assistant.plist"
                if currently_on:
                    plist.unlink(missing_ok=True)
                else:
                    plist.write_text(
                        '<?xml version="1.0" encoding="UTF-8"?>\n'
                        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                        '<plist version="1.0"><dict>\n'
                        '  <key>Label</key><string>com.jarvis.assistant</string>\n'
                        '  <key>ProgramArguments</key><array>\n'
                        f'    <string>{sys.executable}</string>\n'
                        f'    <string>{script}</string>\n'
                        '  </array>\n'
                        '  <key>RunAtLoad</key><true/>\n'
                        '</dict></plist>\n'
                    )
            else:
                desk_dir = Path.home() / ".config" / "autostart"
                desk_dir.mkdir(parents=True, exist_ok=True)
                desk = desk_dir / "jarvis.desktop"
                if currently_on:
                    desk.unlink(missing_ok=True)
                else:
                    desk.write_text(
                        "[Desktop Entry]\n"
                        f"Name={self._assistant_name}\n"
                        f"Exec={sys.executable} {script}\n"
                        "Type=Application\nTerminal=false\n"
                        "X-GNOME-Autostart-enabled=true\n"
                    )
            enabled = not currently_on
            self._update_autostart_btn(enabled)
            self._log.append_log(
                f"SYS: Auto-start {'enabled' if enabled else 'disabled'}.")
        except Exception as e:
            self._log.append_log(f"ERR: Auto-start failed — {e}")

    def _update_autostart_btn(self, enabled: bool):
        if not hasattr(self, '_autostart_btn'):
            return
        if enabled:
            self._autostart_btn.setText("◉  AUTO-START: ON")
            self._autostart_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #001a08; color: {C.GREEN};
                    border: 1px solid {C.GREEN_D}; border-radius: 3px;
                }}
                QPushButton:hover {{ background: #002010; }}
            """)
        else:
            self._autostart_btn.setText("◉  AUTO-START: OFF")
            self._autostart_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT_DIM};
                    border: 1px solid {C.BORDER}; border-radius: 3px;
                }}
                QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
            """)

    def _toggle_brief(self):
        from memory.config_manager import get_brief_enabled, save_brief_enabled
        new_val = not get_brief_enabled()
        save_brief_enabled(new_val)
        self._update_brief_btn(new_val)

    # ── Wake word settings ───────────────────────────────────────────────────

    def _wake_state(self) -> dict:
        """Combined state for the two wake-word buttons. Readiness is a cheap,
        deterministic on-disk check now (see core.wake_word.is_ready), so there
        is nothing to cache — the button never flickers to a stale value."""
        if self.wake_get_state:
            try:
                s = self.wake_get_state()
                return {"ready": bool(s.get("ready")),
                        "enabled": bool(s.get("enabled")),
                        "awake": bool(s.get("awake"))}
            except Exception:
                pass
        # Before JarvisLive has wired its callback (drawer built at startup).
        ready, enabled = False, False
        try:
            from core.wake_word import is_ready
            from memory.config_manager import get_wake_word_enabled
            ready, enabled = is_ready(), get_wake_word_enabled()
        except Exception:
            pass
        return {"ready": ready, "enabled": enabled, "awake": True}

    def _refresh_wake_btns(self):
        if not hasattr(self, '_wake_btn'):
            return
        st = self._wake_state()
        _on = f"""
            QPushButton {{ background: #001a08; color: {C.GREEN};
                border: 1px solid {C.GREEN_D}; border-radius: 3px;
                text-align: left; padding: 0 8px; }}
            QPushButton:hover {{ background: #002010; }}"""
        _off = f"""
            QPushButton {{ background: transparent; color: {C.TEXT_DIM};
                border: 1px solid {C.BORDER}; border-radius: 3px;
                text-align: left; padding: 0 8px; }}
            QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}"""
        self._wake_btn.setEnabled(True)
        if not st["ready"]:
            self._wake_btn.setText("⬇  WAKE WORD: DOWNLOAD")
            self._wake_btn.setStyleSheet(_off)
            self._wake_sleep_btn.hide()
        elif st["enabled"]:
            self._wake_btn.setText("🎙  WAKE WORD: ON")
            self._wake_btn.setStyleSheet(_on)
            self._wake_sleep_btn.show()
            self._wake_sleep_btn.setText("😴  SLEEP NOW" if st["awake"] else "👂  WAKE NOW")
            self._wake_sleep_btn.setStyleSheet(_off)
        else:
            self._wake_btn.setText("🎙  WAKE WORD: OFF")
            self._wake_btn.setStyleSheet(_off)
            self._wake_sleep_btn.hide()

    def _toggle_wake_word(self):
        st = self._wake_state()
        if not st["ready"]:
            # First time: download openwakeword + model in a worker thread.
            self._wake_btn.setText("⬇  DOWNLOADING… (one-time)")
            self._wake_btn.setEnabled(False)
            def _work():
                try:
                    from core.wake_word import install_and_download
                    ok, msg = install_and_download(
                        logger=lambda m: self._log_sig.emit(f"SYS: {m}"))
                except Exception as e:
                    ok, msg = False, str(e)
                if ok and self.on_wake_toggle:
                    try:
                        self.on_wake_toggle(True)   # auto-enable after a successful download
                    except Exception:
                        pass
                self._wake_dl_sig.emit(ok, msg)
            threading.Thread(target=_work, daemon=True).start()
            return
        # Already downloaded → just flip enabled/disabled through JarvisLive.
        if self.on_wake_toggle:
            try:
                self.on_wake_toggle(not st["enabled"])
            except Exception:
                pass
        self._refresh_wake_btns()

    def _on_wake_install_done(self, ok: bool, msg: str):
        self._log_sig.emit(f"SYS: {'Wake word ready.' if ok else 'Wake word setup failed: ' + msg}")
        self._refresh_wake_btns()

    def _tap_wake_manual(self):
        if self.on_wake_manual:
            try:
                self.on_wake_manual()
            except Exception:
                pass
        self._refresh_wake_btns()

    def _update_brief_btn(self, enabled: bool):
        if not hasattr(self, '_brief_btn'):
            return
        if enabled:
            self._brief_btn.setText("☀  MORNING BRIEF: ON")
            self._brief_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #001a08; color: {C.GREEN};
                    border: 1px solid {C.GREEN_D}; border-radius: 3px;
                    text-align: left; padding: 0 8px;
                }}
                QPushButton:hover {{ background: #002010; }}
            """)
        else:
            self._brief_btn.setText("☀  MORNING BRIEF: OFF")
            self._brief_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT_DIM};
                    border: 1px solid {C.BORDER}; border-radius: 3px;
                    text-align: left; padding: 0 8px;
                }}
                QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
            """)

    # ── Customization ────────────────────────────────────────────────────────────

    def _open_customize(self):
        if self._customize_overlay and self._customize_overlay.isVisible():
            self._customize_overlay.hide()
            return
        cfg = _read_full_config()
        if self._customize_overlay:
            self._customize_overlay.hide()
        cw = self.centralWidget()
        ov = CustomizeOverlay(
            cfg.get("assistant_name", "JARVIS") or "JARVIS",
            cfg.get("user_name", ""),
            cfg.get("ui_color", "") or DEFAULT_UI_COLOR,
            cfg.get("voice_name", ""),
            parent=cw,
        )
        ow, oh = CustomizeOverlay._OW, CustomizeOverlay._OH
        oh = min(oh, cw.height() - 16)
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.on_preview = self._preview_ui_color
        ov.on_avatar_mode_preview = lambda m: self.hud.set_avatar_mode(m)
        ov.on_anim_mode_preview = lambda m: self.hud.set_anim_mode(m)
        ov.on_hud_glow_preview = lambda g: self.hud.set_hud_glow(g)
        ov.on_particle_density_preview = lambda d: self.hud.set_particle_density(d)
        ov.on_hud_fx_preview = lambda fx: self.hud.set_hud_fx(fx)
        ov.on_preview_expression = lambda expr: self.hud.set_expression(expr, 5.0)
        ov.saved.connect(self._apply_name_update)
        ov.show()
        self._customize_overlay = ov

    def _open_providers(self):
        if self._provider_overlay and self._provider_overlay.isVisible():
            self._provider_overlay.hide()
            return
        cfg = _read_full_config()
        if self._provider_overlay:
            self._provider_overlay.hide()
        cw = self.centralWidget()
        ov = ProviderSettingsOverlay(cfg, parent=cw)
        ow, oh = ProviderSettingsOverlay._OW, ProviderSettingsOverlay._OH
        oh = min(oh, cw.height() - 16)
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.saved.connect(self._on_providers_saved)
        ov.show()
        self._provider_overlay = ov

    def _on_providers_saved(self, prov: str):
        self._log.append_log(f"SYS: Active LLM Provider set to: {prov.upper()}")
        if self.on_voice_change:
            try:
                self.on_voice_change()
            except Exception:
                pass

    def _preview_ui_color(self, hex_color: str):
        """Live preview — paints the whole interface the new colour (does NOT write to config)."""
        old = current_palette()
        if apply_ui_accent(hex_color):
            retheme_all_widgets(old, current_palette())

    def _apply_name_update(self, name: str, user_name: str, ui_color: str = "",
                           voice: str = "", avatar_mode: str = "celestial",
                           particle_density: int = 200, hud_fx: dict = None,
                           sfx_enabled: bool = True, anim_mode: str = "reactive",
                           hud_glow: int = 60, persona_mode: str = "jarvis",
                           gender: str = "male", tts_engine: str = "edge_tts",
                           edge_voice: str = "hi-IN-MadhurNeural",
                           obsidian_cfg: dict = None,
                           language: str = "hinglish"):
        """Update all name/theme/visual-dependent UI elements and persist to config."""
        self._assistant_name = name.strip() or "JARVIS"
        display = self._assistant_name.upper()
        self.setWindowTitle(f"{display} — {APP_VERSION}")
        self._title_lbl.setText(display)

        persona_subtitles = {
            "jarvis": "Just A Rather Very Intelligent System",
            "teacher": "AI Mentor & Academic Instructor",
            "companion": "💖 Devoted Romantic Partner & Soulmate",
            "devops": "Autonomous DevOps & Cloud Specialist",
        }
        if display in ("JARVIS", "J.A.R.V.I.S") and persona_mode == "jarvis":
            self._sub_lbl.setText("Just A Rather Very Intelligent System")
        elif persona_mode in persona_subtitles:
            self._sub_lbl.setText(persona_subtitles[persona_mode])
        else:
            self._sub_lbl.setText("Personal AI Assistant")

        self._log._ai_name_lc = self._assistant_name.lower()
        self.hud._assistant_name = display

        # Visual HUD Engine Updates
        if avatar_mode:
            self.hud.set_avatar_mode(avatar_mode)
        if anim_mode:
            self.hud.set_anim_mode(anim_mode)
        if hud_glow is not None:
            self.hud.set_hud_glow(hud_glow)
        if particle_density:
            self.hud.set_particle_density(particle_density)
        if hud_fx:
            self.hud.set_hud_fx(hud_fx)

        color_changed = False
        if ui_color:
            old = current_palette()
            if apply_ui_accent(ui_color):
                # Live-paint the whole interface (panels, buttons, borders, HUD)
                retheme_all_widgets(old, current_palette())
                color_changed = old["PRI"] != C.PRI

        # Voice change → persist and, if it actually changed, rebuild the Live
        # session so the new voice takes effect (it's fixed at connect time).
        voice_changed = False
        if voice:
            from memory.config_manager import get_voice, save_voice
            if voice != get_voice():
                save_voice(voice)
                voice_changed = True

        try:
            data = _read_full_config()
            data["assistant_name"] = self._assistant_name
            data["user_name"] = user_name.strip()
            if ui_color:
                data["ui_color"] = ui_color.strip().lower()
            data["avatar_mode"] = avatar_mode
            data["anim_mode"] = anim_mode
            data["hud_glow"] = hud_glow
            data["particle_density"] = particle_density
            if hud_fx is not None:
                data["hud_fx"] = hud_fx
            data["sfx_enabled"] = sfx_enabled
            data["persona_mode"] = persona_mode
            data["assistant_gender"] = gender
            data["preferred_language"] = language
            data["tts_engine"] = tts_engine
            data["edge_voice"] = edge_voice
            from memory.config_manager import get_edge_pitch
            data["edge_pitch"] = get_edge_pitch()
            if obsidian_cfg is not None:
                data["obsidian_config"] = obsidian_cfg

            save_persona_mode(persona_mode)
            save_assistant_gender(gender)
            save_preferred_language(language)
            save_tts_engine(tts_engine)
            save_edge_voice(edge_voice)
            if obsidian_cfg is not None:
                save_obsidian_config(obsidian_cfg)

            API_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
            self._log.append_log(f"SYS: Identity updated — {display} ({avatar_mode.upper()} mode, {anim_mode.upper()} dynamics)")
            self._log.append_log(f"SYS: Persona: {persona_mode.upper()} ({gender.upper()}) | Lang: {language.upper()} | Engine: {tts_engine.upper()}")
            if color_changed:
                self._log.append_log(f"SYS: UI colour applied — {ui_color}")
            if voice_changed:
                self._log.append_log(f"SYS: Voice set — {voice}")
        except Exception as e:
            self._log.append_log(f"ERR: Config save failed — {e}")

        if voice_changed and self.on_voice_change:
            self.on_voice_change()

    def _centre_overlay(self, ov) -> None:
        """Place a floating overlay in the middle of the HUD and show it."""
        cw = self.centralWidget()
        ov.adjustSize()
        ov.setGeometry(
            max(0, (cw.width()  - ov.width())  // 2),
            max(0, (cw.height() - ov.height()) // 2),
            ov.width(), ov.height(),
        )
        ov.show()
        ov.raise_()

    # ── Audio devices ────────────────────────────────────────────────────────

    def _open_audio_devices(self):
        ov = AudioDeviceOverlay(parent=self.centralWidget())
        ov.picked.connect(self._on_audio_devices_applied)
        self._centre_overlay(ov)
        self._audio_overlay = ov            # keep a reference so it isn't GC'd

    def _on_audio_devices_applied(self):
        self._log.append_log("SYS: Audio devices updated.")
        if self.on_audio_device_change:
            self.on_audio_device_change()

    # ── Memory panel ─────────────────────────────────────────────────────────

    def _open_memory_panel(self):
        ov = MemoryOverlay(parent=self.centralWidget())
        self._centre_overlay(ov)
        self._memory_overlay = ov

    # ── Irreversible-action confirmation ─────────────────────────────────────

    def _show_confirm_banner(self, title: str, detail: str):
        self._hide_confirm_banner()
        ov = ConfirmBanner(title, detail, parent=self.centralWidget())
        ov.answered.connect(self._on_confirm_answered)
        self._centre_overlay(ov)
        self._confirm_overlay = ov

    def _hide_confirm_banner(self):
        ov = getattr(self, "_confirm_overlay", None)
        if ov is not None:
            ov.hide()
            ov.deleteLater()
            self._confirm_overlay = None

    def _on_confirm_answered(self, accepted: bool):
        # Tear the banner down first: core.confirm.resolve() may be about to
        # shut the machine down, and a live widget mid-callback is not where you
        # want to be when that happens.
        self._hide_confirm_banner()
        try:
            from core.confirm import resolve
            resolve(bool(accepted))
        except Exception as e:
            self._log.append_log(f"ERR: Confirmation failed — {e}")

    def _open_plugin_manager(self):
        plugins = self.get_plugins() if self.get_plugins else []
        cw = self.centralWidget()
        ov = PluginManagerOverlay(plugins, parent=cw)
        ov.adjustSize()
        ov.setGeometry(
            (cw.width()  - ov.width())  // 2,
            (cw.height() - ov.height()) // 2,
            ov.width(), ov.height(),
        )
        ov.show()
        ov.raise_()
        self._plugin_manager_overlay = ov   # keep a reference so it isn't GC'd

    def _open_plugin_settings(self):
        sections = self.get_plugin_settings() if self.get_plugin_settings else []
        cw = self.centralWidget()
        ov = PluginSettingsOverlay(sections, parent=cw)
        ow = PluginSettingsOverlay._OW
        oh = min(560, cw.height() - 16)
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.show()
        ov.raise_()
        self._plugin_settings_overlay = ov   # keep a reference so it isn't GC'd

    # ── Clipboard intelligence ───────────────────────────────────────────────────

    def _on_clipboard_changed(self):
        try:
            text = QApplication.clipboard().text().strip()
            if len(text) >= 10:
                self._clipboard_sig.emit(text)
        except Exception:
            pass

    def _show_clipboard_panel(self, text: str):
        self._clipboard_panel.show_clipboard(text)
        self._position_clipboard_panel()

    def _position_clipboard_panel(self):
        cw = self.centralWidget()
        pw = ClipboardPanel._W
        ph = self._clipboard_panel.sizeHint().height() or ClipboardPanel._H
        x = (cw.width() - pw) // 2
        y = cw.height() - ph - 6
        self._clipboard_panel.setGeometry(x, y, pw, ph)
        self._clipboard_panel.raise_()

    def _on_clipboard_action(self, cmd: str):
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(cmd,), daemon=True).start()

    # ────────────────────────────────────────────────────────────────────────────

    def _do_interrupt(self):
        if self.on_interrupt:
            self.on_interrupt()

    def _toggle_mute(self):
        self._muted = not self._muted
        self.hud.muted = self._muted
        self._style_mute_btn()
        if self._muted:
            self._apply_state("MUTED")
            self._log.append_log("SYS: Microphone muted.")
        else:
            self._apply_state("LISTENING")
            self._log.append_log("SYS: Microphone active.")

    def _style_mute_btn(self):
        if self._muted:
            self._mute_btn.setText("🔇  MICROPHONE MUTED")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #140006; color: {C.MUTED_C};
                    border: 1px solid {C.MUTED_C}; border-radius: 3px;
                }}
            """)
        else:
            self._mute_btn.setText("🎙  MICROPHONE ACTIVE")
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #00140a; color: {C.GREEN};
                    border: 1px solid {C.GREEN}; border-radius: 3px;
                }}
                QPushButton:hover {{ background: #001f10; }}
            """)

    def _send(self):
        txt = self._input.text().strip()
        if not txt: return
        self._input.clear()
        self._log.append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _apply_state(self, state: str):
        self.hud.state    = state
        self.hud.speaking = (state == "SPEAKING")

    def _check_config(self) -> bool:
        if not API_FILE.exists(): return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            has_os = bool(d.get("os_system"))
            # If free proxy is enabled, or gemini/groq/openrouter/deepseek/custom is configured, it's ready!
            has_ai = bool(
                d.get("free_proxy_enabled", True) or
                d.get("gemini_api_key") or
                d.get("groq_api_key") or
                d.get("openrouter_api_key") or
                d.get("deepseek_api_key") or
                d.get("custom_llm_url")
            )
            return has_os and has_ai
        except Exception:
            return False

    def _show_setup(self):
        ov = SetupOverlay(self.centralWidget())
        cw = self.centralWidget()
        ow, oh = 460, 390
        ov.setGeometry(
            (cw.width()  - ow) // 2,
            (cw.height() - oh) // 2,
            ow, oh,
        )
        ov.done.connect(self._on_setup_done)
        ov.show()
        self._overlay = ov

    def _on_setup_done(self, key: str, os_name: str):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        data = _read_full_config()
        data["os_system"] = os_name
        if key:
            data["gemini_api_key"] = key
            data["preferred_llm_provider"] = "gemini"
        else:
            data["free_proxy_enabled"] = True
            data["preferred_llm_provider"] = "gemini-web"
        API_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
        self._ready = True
        if self._overlay:
            self._overlay.hide()
            self._overlay = None
        self._apply_state("LISTENING")
        self._assistant_name = _read_full_config().get("assistant_name", "JARVIS") or "JARVIS"
        prov_info = "Gemini API" if key else "Gemini Web FREE (Built-in Proxy)"
        self._log.append_log(f"SYS: Initialised. Provider={prov_info}. {self._assistant_name} online.")


class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self):
        self._app.exec()
    def protocol(self, *_):
        pass


class JarvisUI:
    def __init__(self, face_path: str, size=None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        QFont.insertSubstitutions("Courier New", ["Nirmala UI", "Segoe UI", "Arial", "Lucida Console"])
        self._win = MainWindow(face_path)
        self.root = _RootShim(self._app)
        self._win.show()

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return self._win._drop_zone.current_file()

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    @property
    def on_remote_clicked(self):
        return self._win.on_remote_clicked

    @on_remote_clicked.setter
    def on_remote_clicked(self, cb):
        self._win.on_remote_clicked = cb

    @property
    def on_interrupt(self):
        return self._win.on_interrupt

    @on_interrupt.setter
    def on_interrupt(self, cb):
        self._win.on_interrupt = cb

    @property
    def on_voice_change(self):
        return self._win.on_voice_change

    @on_voice_change.setter
    def on_voice_change(self, cb):
        self._win.on_voice_change = cb

    @property
    def on_audio_device_change(self):
        return self._win.on_audio_device_change

    @on_audio_device_change.setter
    def on_audio_device_change(self, cb):
        self._win.on_audio_device_change = cb

    def show_confirm(self, title: str, detail: str) -> None:
        """Thread-safe: raise the irreversible-action gate. Called from action
        handlers running in executor threads, so it goes through a signal."""
        self._win._confirm_sig.emit(str(title)[:120], str(detail)[:300])

    def hide_confirm(self) -> None:
        """Thread-safe: take the gate down."""
        self._win._confirm_hide_sig.emit()

    @property
    def get_plugins(self):
        return self._win.get_plugins

    @get_plugins.setter
    def get_plugins(self, cb):
        self._win.get_plugins = cb

    @property
    def get_plugin_settings(self):
        return self._win.get_plugin_settings

    @get_plugin_settings.setter
    def get_plugin_settings(self, cb):
        self._win.get_plugin_settings = cb

    @property
    def on_wake_toggle(self):
        return self._win.on_wake_toggle

    @on_wake_toggle.setter
    def on_wake_toggle(self, cb):
        self._win.on_wake_toggle = cb

    @property
    def on_wake_manual(self):
        return self._win.on_wake_manual

    @on_wake_manual.setter
    def on_wake_manual(self, cb):
        self._win.on_wake_manual = cb

    @property
    def wake_get_state(self):
        return self._win.wake_get_state

    @wake_get_state.setter
    def wake_get_state(self, cb):
        self._win.wake_get_state = cb

    def set_audio_level(self, level: float) -> None:
        """Thread-safe: feed a 0.0–1.0 live audio level to the HUD waveform.
        Called from the audio threads; a plain float store is atomic under the
        GIL, so no signal/lock is needed for this cosmetic value."""
        try:
            self._win.hud.set_audio_level(level)
        except Exception:
            pass

    def notify_phone_connected(self) -> None:
        self._win.notify_phone_connected()

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

    def stream_log_chunk(self, speaker: str, chunk: str, is_final: bool = False):
        """Thread-safe: stream spoken tokens live to the HUD sidebar while speech occurs."""
        try:
            self._win._stream_log_sig.emit(speaker, chunk, is_final)
        except Exception:
            pass

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def show_content(self, title: str, text: str):
        """Thread-safe: display content in the panel below the HUD."""
        self._win._content_sig.emit(title[:48], text[:4000])

    def prompt_reconfig(self):
        """Thread-safe: show the API key setup overlay (e.g. after an auth error)."""
        self._win._ready = False
        self._win._reconfig_sig.emit()

    def show_camera_frame(self, img_bytes: bytes):
        """Thread-safe: show a webcam frame in the small overlay (screen captures)."""
        self._win._camera_sig.emit(img_bytes)

    def start_camera_stream(self) -> None:
        """Thread-safe: start live camera feed in the full HUD area."""
        self._win.start_camera_stream()

    def stop_camera_stream(self) -> None:
        """Thread-safe: stop the live camera feed."""
        self._win.stop_camera_stream()

    @property
    def assistant_name(self) -> str:
        return self._win._assistant_name

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")

    def set_expression(self, expr: str, duration: float = 6.0) -> None:
        """Thread-safe: trigger an emotional reaction & color pulse on the HUD avatar."""
        try:
            self._win._expression_sig.emit(expr, duration)
        except Exception:
            pass