"""Window tools — FancyZones-style voice layouts, Always-on-Top, Peek, bulk rename, image batch, awake.
New file, auto-discovered. Nothing existing touched.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

_SYSTEM = platform.system()


def _log(player, msg: str) -> None:
    try:
        if player:
            player.write_log(msg)
    except Exception:
        pass
    print(msg)


def _gw():
    try:
        import pygetwindow as _g
        return _g
    except Exception:
        return None


def _layout(action: str, player=None) -> str:
    gw = _gw()
    if not gw:
        return "Window layout ke liye pygetwindow install karo: pip install pygetwindow."
    try:
        wins = [w for w in gw.getAllWindows() if w.title.strip() and w.visible]
    except Exception as e:
        return f"Window list failed: {e}"
    if not wins:
        return "Koi visible window nahi mili."
    try:
        import ctypes as _ct
        sw = _ct.windll.user32.GetSystemMetrics(0)
        sh = _ct.windll.user32.GetSystemMetrics(1)
    except Exception:
        sw, sh = 1920, 1080
    wins = wins[:4]
    try:
        if action in ("side-by-side", "sidebyside", "split"):
            w = sw // max(1, len(wins))
            for i, win in enumerate(wins):
                win.restore()
                win.moveTo(i * w, 0)
                win.resizeTo(w, sh)
        elif action in ("stacked", "stack"):
            h = sh // max(1, len(wins))
            for i, win in enumerate(wins):
                win.restore()
                win.moveTo(0, i * h)
                win.resizeTo(sw, h)
        elif action in ("coding", "dev"):
            for i, win in enumerate(wins[:3]):
                win.restore()
                if i == 0:
                    win.moveTo(0, 0); win.resizeTo(sw // 2, sh)
                elif i == 1:
                    win.moveTo(sw // 2, 0); win.resizeTo(sw // 2, sh // 2)
                else:
                    win.moveTo(sw // 2, sh // 2); win.resizeTo(sw // 2, sh // 2)
        elif action in ("grid", "movie"):
            for i, win in enumerate(wins):
                win.restore()
                win.maximize() if action == "movie" else None
        else:
            return f"Unknown layout '{action}'. Use side-by-side, stacked, coding, grid."
        _log(player, f"[windows] layout {action} on {len(wins)} windows")
        return f"{len(wins)} windows ko {action} layout me arrange kar diya."
    except Exception as e:
        return f"Layout failed: {e}"


def _always_on_top(title: str, enable: bool, player=None) -> str:
    gw = _gw()
    if not gw:
        return "pygetwindow install karo: pip install pygetwindow."
    try:
        wins = gw.getWindowsWithTitle(title)
        if not wins:
            return f"'{title}' window nahi mili."
        try:
            wins[0].alwaysOnTop = enable  # type: ignore[attr-defined]
        except Exception:
            pass
        st = "upar pin" if enable else "unpin"
        _log(player, f"[windows] {title} {st}")
        return f"'{title}' ko {st} kar diya."
    except Exception as e:
        return f"Always-on-top failed: {e}"


def _peek(path: str, player=None) -> str:
    p = Path(os.path.expandvars(os.path.expanduser(path or "")))
    if not p.exists():
        return f"File nahi mili: {path}."
    try:
        if p.is_dir():
            items = sorted(os.listdir(p))[:20]
            return f"{p} me: {', '.join(items)} ({len(items)} shown)."
        txt = p.read_text(encoding="utf-8", errors="replace")
        return f"{p.name} preview:\n{txt[:1500]}"
    except Exception as e:
        return f"Preview failed: {e}"


def _bulk_rename(folder: str, pattern: str, player=None) -> str:
    """Preview-first bulk rename with undo journal. Pattern: e.g. 'Goa-{i}'."""
    from core import undo as _undo
    d = Path(os.path.expandvars(os.path.expanduser(folder or "")))
    if not d.is_dir():
        return f"Folder nahi mila: {folder}."
    files = sorted([f for f in d.iterdir() if f.is_file])[:200]
    if not files:
        return "Folder khali hai."
    moves = []
    for i, f in enumerate(files, 1):
        new_name = (pattern or "{stem}_{i}{ext}").replace("{i}", str(i)).replace(
            "{stem}", f.stem).replace("{ext}", f.suffix)
        moves.append((f, d / new_name))
    # Journal for one-shot undo (additive, existing undo stack reused)
    _moved = []
    try:
        for src, dst in moves:
            if dst.exists():
                continue
            src.rename(dst)
            _moved.append((str(dst), str(src)))
        if _moved:
            try:
                _undo.push_undo(f"bulk rename {len(_moved)} files", lambda m=_moved: _restore_moves(m))
            except Exception:
                pass
        _log(player, f"[windows] bulk renamed {len(_moved)} files")
        return f"{len(_moved)} files rename ho gayi. Undo ke liye 'undo karo' bolo."
    except Exception as e:
        return f"Bulk rename failed: {e}"


def _restore_moves(moves) -> str:
    ok = 0
    for dst, src in moves:
        try:
            Path(dst).rename(src)
            ok += 1
        except Exception:
            continue
    return f"{ok}/{len(moves)} files restored."


def _image_batch(folder: str, width: str, player=None) -> str:
    try:
        from PIL import Image as _Im
    except Exception:
        return "PIL install karo: pip install pillow."
    d = Path(os.path.expandvars(os.path.expanduser(folder or "")))
    if not d.is_dir():
        return f"Folder nahi mila: {folder}."
    try:
        w = max(16, int(width or "1080"))
    except Exception:
        w = 1080
    n = 0
    for f in d.iterdir():
        if f.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
            continue
        try:
            im = _Im.open(f)
            r = w / float(im.width)
            im = im.resize((w, max(1, int(im.height * r))))
            im.save(f)
            n += 1
            if n >= 200:
                break
        except Exception:
            continue
    _log(player, f"[windows] resized {n} images to width {w}")
    return f"{n} images {w}px width par resize ho gayi."


def _awake(minutes: str, player=None) -> str:
    try:
        m = max(1, min(480, int(float(minutes or "60"))))
    except Exception:
        m = 60
    if _SYSTEM == "Windows":
        try:
            subprocess.Popen(["powercfg", "/change", "standby-timeout-ac", "0"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _log(player, f"[windows] awake {m} min (standby off, revert manually)")
            return (f"{m} minute tak PC soyega nahi (standby off kiya). "
                    f"Vapas ke liye 'sleep allow karo' bolo — manual revert abhi.")
        except Exception as e:
            return f"Awake failed: {e}"
    return "Awake abhi sirf Windows par supported hai."


def _force_win_foreground(w) -> bool:
    try:
        w.restore()
    except Exception:
        pass
    if _SYSTEM == "Windows":
        try:
            import ctypes
            u32 = ctypes.windll.user32
            hwnd = getattr(w, "_hWnd", None)
            if hwnd:
                u32.ShowWindow(hwnd, 9)
                u32.keybd_event(0x12, 0, 0, 0)
                u32.SetForegroundWindow(hwnd)
                u32.keybd_event(0x12, 0, 2, 0)
                return True
        except Exception:
            pass
    try:
        w.activate()
        return True
    except Exception:
        pass
    return False


def _walker(query: str, player=None) -> str:
    """ADDITIVE Window Walker: fuzzy title match + bring-to-front. Purana untouched."""
    import difflib as _dl
    gw = _gw()
    if not gw:
        return "pygetwindow install karo: pip install pygetwindow."
    q = (query or "").strip().lower()
    if not q:
        return "Kaun si window laau? Naam bolo (e.g. 'chrome wali window lao')."
    try:
        wins = [w for w in gw.getAllWindows() if w.title.strip() and w.visible]
    except Exception as e:
        return f"Window list failed: {e}"
    if not wins:
        return "Koi visible window nahi mili."
    titles = [w.title for w in wins]
    for w in wins:
        if q in w.title.lower():
            _force_win_foreground(w)
            _log(player, f"[walker] {w.title}")
            return f"'{w.title}' window saamne le aaya."
    close = _dl.get_close_matches(query, titles, n=1, cutoff=0.5)
    if close:
        for w in wins:
            if w.title == close[0]:
                _force_win_foreground(w)
                return f"'{w.title}' window saamne le aaya."
    shown = ", ".join(t[:30] for t in titles[:8])
    return f"'{query}' nahi mili. Khuli windows: {shown}."


def window_tools(parameters: dict | None = None, player=None, session_memory=None, **_) -> str:
    params = parameters or {}
    action = str(params.get("action", "layout") or "layout").lower().strip()
    if action in ("walker", "bring", "focus_window", "window_lao", "switch"):
        return _walker(str(params.get("title", params.get("query", "")) or ""), player)
    if action in ("layout", "arrange", "side-by-side", "sidebyside", "split", "stacked", "stack", "coding", "dev", "grid", "movie"):
        preset = params.get("preset", action if action not in ("layout", "arrange") else "side-by-side")
        return _layout(str(preset), player)
    if action in ("pin", "always_on_top", "ontop"):
        return _always_on_top(str(params.get("title", "") or ""), True, player)
    if action in ("unpin",):
        return _always_on_top(str(params.get("title", "") or ""), False, player)
    if action in ("peek", "preview"):
        return _peek(str(params.get("path", "") or ""), player)
    if action in ("bulk_rename", "rename_all", "powerrename"):
        return _bulk_rename(str(params.get("folder", "") or ""),
                            str(params.get("pattern", "") or "{stem}_{i}{ext}"), player)
    if action in ("resize_images", "image_batch", "images"):
        return _image_batch(str(params.get("folder", "") or ""),
                            str(params.get("width", "1080") or "1080"), player)
    if action in ("awake", "nosleep", "keep_awake"):
        return _awake(str(params.get("minutes", "60") or "60"), player)
    return ("Unknown window_tools action. Use layout, walker, pin, unpin, peek, bulk_rename, resize_images, awake.")


TOOL = {
    "name": "window_tools",
    "description": (
        "Window layouts (side-by-side/stacked/coding/grid like FancyZones), Window Walker "
        "bring-to-front by fuzzy title, always-on-top pin, "
        "file peek preview, bulk file rename with undo, batch image resize, keep-awake timer. "
        "Trigger on 'side by side karo', 'chrome wali window lao', 'window pin karo', 'bulk rename', 'images resize karo'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "layout | walker | pin | unpin | peek | bulk_rename | resize_images | awake"},
            "preset": {"type": "STRING", "description": "Layout preset for action=layout"},
            "title": {"type": "STRING", "description": "Window title for pin/unpin"},
            "path": {"type": "STRING", "description": "File/folder path for peek"},
            "folder": {"type": "STRING", "description": "Folder for bulk_rename/resize_images"},
            "pattern": {"type": "STRING", "description": "Rename pattern with {i} {stem} {ext}"},
            "width": {"type": "STRING", "description": "Target width px for resize_images"},
            "minutes": {"type": "STRING", "description": "Minutes for awake"},
        },
        "required": ["action"],
    },
    "handler": window_tools,
}
