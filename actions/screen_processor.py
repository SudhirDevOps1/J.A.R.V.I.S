"""
Screen & webcam capture for JARVIS vision.

Provides the two capture entry points main.py uses — `_capture_screen()` and
`_capture_camera()` — plus their helpers (compression, camera auto-detection,
config access). main.py grabs a frame here on demand, then injects it into the
main Gemini Live session; there is no separate vision session here.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import numpy as np

try:
    import cv2
    _CV2 = True
except ImportError:
    _CV2 = False

try:
    import mss
    import mss.tools
    _MSS = True
except ImportError:
    _MSS = False

try:
    import PIL.Image
    _PIL = True
except ImportError:
    _PIL = False


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE        = _base_dir()
_CONFIG_PATH = _BASE / "config" / "api_keys.json"


def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config_key(key: str, value) -> None:
    try:
        cfg = _load_config()
        cfg[key] = value
        _CONFIG_PATH.write_text(json.dumps(cfg, indent=4), encoding="utf-8")
    except Exception as e:
        print(f"[Vision] ⚠️  Could not save config key '{key}': {e}")


def _get_os() -> str:
    return _load_config().get("os_system", "windows").lower()


_IMG_MAX_W = 1280
_IMG_MAX_H = 720
_JPEG_Q    = 82

# ADDITIVE camera fail-fast: temporary backoff when camera is busy
_CAM_DEAD_UNTIL = 0.0
_CAM_COOLDOWN = 10.0


def _silence_cv2():
    """OpenCV C++ WARN spam (stderr) ko suppress karo. Returns restore-fn. Never raises."""
    try:
        import os as _os
        _fd = _os.dup(2)
        _dev = open(_os.devnull, "w")
        _os.dup2(_dev.fileno(), 2)
        def _restore():
            try:
                _os.dup2(_fd, 2)
                _dev.close()
                _os.close(_fd)
            except Exception:
                pass
        return _restore
    except Exception:
        return lambda: None


def _cam_dead() -> bool:
    try:
        import time as _t
        return _t.monotonic() < _CAM_DEAD_UNTIL
    except Exception:
        return False


def _mark_cam_dead() -> None:
    global _CAM_DEAD_UNTIL
    try:
        import time as _t
        _CAM_DEAD_UNTIL = _t.monotonic() + _CAM_COOLDOWN
    except Exception:
        pass


def _compress(img_bytes: bytes, source_format: str = "PNG") -> tuple[bytes, str]:
    if not _PIL:
        return img_bytes, f"image/{source_format.lower()}"

    try:
        img = PIL.Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img.thumbnail((_IMG_MAX_W, _IMG_MAX_H), PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_Q, optimize=False)
        return buf.getvalue(), "image/jpeg"
    except Exception as e:
        print(f"[Vision] ⚠️  Image compress failed: {e}")
        return img_bytes, f"image/{source_format.lower()}"


def _capture_screen() -> tuple[bytes, str]:
    try:
        from core.privacy_guard import is_screen_capture_allowed, generate_shield_frame
        allowed, reason = is_screen_capture_allowed(is_stream=False)
        if not allowed:
            print(f"[Vision] 🛡️  Screen capture shielded: {reason}")
            return generate_shield_frame(reason)
    except Exception as _p_err:
        pass

    if not _MSS:
        raise RuntimeError("mss is not installed. Run: pip install mss")

    # Hide PiP so it doesn't obstruct VSCodium/code errors
    pip_win = None
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QMetaObject, Qt
        import time
        app = QApplication.instance()
        if app and hasattr(app, '_pip') and app._pip.isVisible():
            pip_win = app._pip
            QMetaObject.invokeMethod(pip_win, "hide", Qt.ConnectionType.BlockingQueuedConnection)
            time.sleep(0.1) # allow compositor to clear
    except Exception:
        pass

    with mss.mss() as sct:
        monitors = sct.monitors          # [0] = all combined, [1..n] = real screens
        target   = monitors[1] if len(monitors) > 1 else monitors[0]
        shot     = sct.grab(target)
        png      = mss.tools.to_png(shot.rgb, shot.size)

    # Restore PiP
    if pip_win:
        try:
            from PyQt6.QtCore import QMetaObject, Qt
            QMetaObject.invokeMethod(pip_win, "show", Qt.ConnectionType.BlockingQueuedConnection)
        except Exception:
            pass

    return _compress(png, "PNG")


def _cv2_backend() -> int:
    """Return the best OpenCV camera backend for the current OS."""
    if not _CV2:
        return 0
    os_name = _get_os()
    if os_name == "windows":
        return cv2.CAP_DSHOW
    if os_name == "mac":
        return cv2.CAP_AVFOUNDATION
    return cv2.CAP_ANY


def _probe_camera(index: int, backend: int, warmup: int = 5) -> bool:

    if not _CV2:
        return False
    _restore = _silence_cv2()  # ADDITIVE: DSHOW WARN flood band
    try:
        cap = cv2.VideoCapture(index, backend)
        if not cap.isOpened():
            cap.release()
            return False
        for _ in range(warmup):
            cap.read()
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            return False
        return bool(np.mean(frame) > 8)
    finally:
        try:
            _restore()
        except Exception:
            pass


def _detect_camera_index() -> int:

    backend = _cv2_backend()
    print("[Vision] 🔍 Auto-detecting camera...")
    for idx in range(6):
        if _probe_camera(idx, backend):
            print(f"[Vision] ✅ Camera found at index {idx}")
            _save_config_key("camera_index", idx)
            return idx
        print(f"[Vision] ⚠️  Camera index {idx}: no usable frame")

    print("[Vision] ⚠️  No camera found — defaulting to index 0")
    _save_config_key("camera_index", 0)
    return 0


def _get_camera_index() -> int:
    cfg = _load_config()
    if "camera_index" in cfg:
        return int(cfg["camera_index"])
    return _detect_camera_index()


def _capture_camera() -> tuple[bytes, str]:
    if not _CV2:
        raise RuntimeError("OpenCV (cv2) is not installed. Run: pip install opencv-python")

    # ADDITIVE fail-fast: temporary backoff when camera is busy
    if _cam_dead():
        raise RuntimeError("Camera unavailable (recent failure). Check if another app is using the webcam or camera privacy settings.")

    index   = _get_camera_index()
    backend = _cv2_backend()
    _restore = _silence_cv2()
    cap = None
    frame = None
    try:
        cap = cv2.VideoCapture(index, backend)
        if not cap.isOpened():
            # Quick fallback: release and try alternate backend
            try:
                cap.release()
            except Exception:
                pass
            import time as _t
            _t.sleep(0.2)
            alt_backend = cv2.CAP_ANY if backend != cv2.CAP_ANY else cv2.CAP_DSHOW
            cap = cv2.VideoCapture(index, alt_backend)

        if not cap.isOpened():
            _mark_cam_dead()
            raise RuntimeError(f"Camera index {index} could not be opened. Another application (like Windows Camera) may be using it.")

        for _ in range(5):
            cap.read()

        ret, frame = cap.read()
        try:
            cap.release()
        except Exception:
            pass
        cap = None

        if not ret or frame is None:
            _mark_cam_dead()
            raise RuntimeError("Camera returned no frame. Check privacy shutter or webcam permissions.")
    finally:
        try:
            if cap is not None and cap.isOpened():
                cap.release()
        except Exception:
            pass
        try:
            _restore()
        except Exception:
            pass

    if _PIL:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(rgb)
        img.thumbnail((_IMG_MAX_W, _IMG_MAX_H), PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=_JPEG_Q)
        return buf.getvalue(), "image/jpeg"

    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_Q])
    return buf.tobytes(), "image/jpeg"
