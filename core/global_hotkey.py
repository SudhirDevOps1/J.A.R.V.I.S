"""
Global Hotkey Summon Listener (keyboard library)
Allows user to summon J.A.R.V.I.S. hands-free with Ctrl+Space or Alt+J from any
active program (IDE, browser, games, terminals) with zero polling overhead.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

try:
    import keyboard
    _HAS_KEYBOARD = True
except ImportError:
    _HAS_KEYBOARD = False


class GlobalHotkeyManager:
    """Manages system-wide low-level OS hotkey hooks."""
    def __init__(self, hotkey: str = "ctrl+space", callback: Optional[Callable[[], None]] = None):
        self.hotkey = hotkey
        self.callback = callback
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if not _HAS_KEYBOARD:
            print("[Hotkey] 'keyboard' library not installed. Global hotkey disabled.")
            return

        if self._running:
            return

        self._running = True

        def _on_press():
            print(f"\n[Hotkey] Triggered: {self.hotkey} pressed! Summoning J.A.R.V.I.S...")
            try:
                from core.native_hacks import show_native_alert
                # Native non-blocking notification or custom callback
                if self.callback:
                    self.callback()
                else:
                    show_native_alert("J.A.R.V.I.S. Active", "Listening... Command boliye, sir!", "info")
            except Exception as e:
                print(f"[Hotkey] Callback error: {e}")

        try:
            keyboard.add_hotkey(self.hotkey, _on_press)
            print(f"[Hotkey] Global hotkey registered: [{self.hotkey.upper()}]. Press anywhere to summon J.A.R.V.I.S.")
        except Exception as e:
            print(f"[Hotkey] Registration note: {e}")

    def stop(self):
        if _HAS_KEYBOARD and self._running:
            try:
                keyboard.remove_hotkey(self.hotkey)
            except Exception:
                pass
            self._running = False


_INSTANCE: Optional[GlobalHotkeyManager] = None

def get_hotkey_manager() -> GlobalHotkeyManager:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = GlobalHotkeyManager()
    return _INSTANCE
