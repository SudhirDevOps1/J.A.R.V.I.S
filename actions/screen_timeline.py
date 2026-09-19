"""
100% Private Local Screen Memory & Timeline Recall.
Stores and searches timeline snapshots of active windows, apps, and desktop activity
in a local SQLite FTS5 database (memory/screen_timeline.db).
Zero cloud transmission — 100% on-device privacy.
"""
from __future__ import annotations

import datetime
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_DB_PATH = Path(__file__).resolve().parent.parent / "memory" / "screen_timeline.db"

# Blacklist of keywords that should NEVER be stored in the timeline
_PRIVACY_BLACKLIST = (
    "password", "passcode", "credit card", "bank", "netbanking", "login",
    "signin", "sign-in", "keepass", "1password", "bitwarden", "authenticator",
    "private browsing", "incognito", "inprivate", "secret", "cvv", "otp"
)


def _init_db() -> None:
    """Initialize SQLite database with FTS5 virtual table for full-text search."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(_DB_PATH)) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS screen_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                timestamp_iso TEXT,
                window_title TEXT,
                app_name TEXT,
                ocr_text TEXT,
                summary TEXT,
                tags TEXT
            );
        """)
        # Create FTS5 virtual table for fast semantic/keyword search
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS screen_timeline_fts USING fts5(
                window_title,
                app_name,
                ocr_text,
                summary,
                tags,
                content='screen_snapshots',
                content_rowid='id'
            );
        """)
        # Trigger to keep FTS in sync with snapshots table
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_snapshots_ai AFTER INSERT ON screen_snapshots BEGIN
                INSERT INTO screen_timeline_fts(rowid, window_title, app_name, ocr_text, summary, tags)
                VALUES (new.id, new.window_title, new.app_name, new.ocr_text, new.summary, new.tags);
            END;
        """)
        conn.commit()


def _is_sensitive(text: str) -> bool:
    """Check if text contains sensitive terms."""
    if not text:
        return False
    low = text.lower()
    return any(term in low for term in _PRIVACY_BLACKLIST)


def get_active_window_info() -> Tuple[str, str]:
    """Retrieve active window title and process name safely."""
    title = ""
    app_name = ""

    # Try pygetwindow
    try:
        import pygetwindow as gw
        active = gw.getActiveWindow()
        if active and active.title:
            title = active.title.strip()
    except Exception:
        pass

    # Try win32gui / psutil for app name
    try:
        import win32gui
        import win32process
        import psutil

        hwnd = win32gui.GetForegroundWindow()
        if hwnd:
            if not title:
                title = win32gui.GetWindowText(hwnd).strip()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            app_name = proc.name().strip()
    except Exception:
        pass

    return title, app_name


def record_snapshot(
    window_title: Optional[str] = None,
    app_name: Optional[str] = None,
    ocr_text: str = "",
    summary: str = "",
    tags: str = "",
) -> bool:
    """
    Record a timeline snapshot to SQLite FTS5.
    Respects privacy guard and privacy blacklist.
    """
    try:
        from core.privacy_guard import is_screen_capture_allowed
        allowed, reason = is_screen_capture_allowed(is_stream=False)
        if not allowed:
            return False
    except Exception:
        pass

    if not window_title or not app_name:
        cur_title, cur_app = get_active_window_info()
        window_title = window_title or cur_title
        app_name = app_name or cur_app

    if not window_title:
        return False

    # Privacy check
    if _is_sensitive(window_title) or _is_sensitive(ocr_text) or _is_sensitive(summary):
        return False

    _init_db()
    now_ts = time.time()
    now_iso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with sqlite3.connect(str(_DB_PATH)) as conn:
            cursor = conn.cursor()
            # Avoid duplicate inserts if active window and app haven't changed in the last 15 seconds
            cursor.execute(
                "SELECT window_title, timestamp FROM screen_snapshots ORDER BY id DESC LIMIT 1"
            )
            last = cursor.fetchone()
            if last and last[0] == window_title and (now_ts - last[1]) < 15:
                return True

            cursor.execute("""
                INSERT INTO screen_snapshots (timestamp, timestamp_iso, window_title, app_name, ocr_text, summary, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (now_ts, now_iso, window_title, app_name, ocr_text, summary, tags))
            conn.commit()
            return True
    except Exception as e:
        print(f"[ScreenTimeline] Record error: {e}")
        return False


def recall_screen_history(query: str = "", minutes: int = 180, limit: int = 5) -> str:
    """
    Search and recall recent screen and activity history from local SQLite FTS5.
    """
    _init_db()
    cutoff_ts = time.time() - (minutes * 60)
    query_clean = query.strip()

    try:
        with sqlite3.connect(str(_DB_PATH)) as conn:
            cursor = conn.cursor()

            if query_clean:
                # FTS5 search
                # Clean query of special sqlite fts characters
                safe_query = "".join(c for c in query_clean if c.isalnum() or c.isspace()).strip()
                if safe_query:
                    cursor.execute("""
                        SELECT s.timestamp_iso, s.window_title, s.app_name, s.summary
                        FROM screen_timeline_fts f
                        JOIN screen_snapshots s ON f.rowid = s.id
                        WHERE screen_timeline_fts MATCH ? AND s.timestamp >= ?
                        ORDER BY s.timestamp DESC LIMIT ?
                    """, (safe_query, cutoff_ts, limit))
                    rows = cursor.fetchall()
                else:
                    rows = []

                if not rows:
                    # Fallback to LIKE substring search
                    cursor.execute("""
                        SELECT timestamp_iso, window_title, app_name, summary
                        FROM screen_snapshots
                        WHERE (window_title LIKE ? OR app_name LIKE ? OR ocr_text LIKE ?) AND timestamp >= ?
                        ORDER BY timestamp DESC LIMIT ?
                    """, (f"%{query_clean}%", f"%{query_clean}%", f"%{query_clean}%", cutoff_ts, limit))
                    rows = cursor.fetchall()
            else:
                # Recent activity list
                cursor.execute("""
                    SELECT timestamp_iso, window_title, app_name, summary
                    FROM screen_snapshots
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (cutoff_ts, limit))
                rows = cursor.fetchall()

            if not rows:
                if query_clean:
                    return f"Aapke timeline me '{query_clean}' se related koi activity nahi mili sir."
                return "Screen timeline me pichhle kuch ghanto me koi recorded activity nahi mili."

            lines = []
            for iso_time, w_title, app, summ in rows:
                t_str = iso_time.split(" ")[-1] if " " in iso_time else iso_time
                if summ and w_title and summ != w_title:
                    detail = f"{w_title} ({summ})"
                else:
                    detail = summ or w_title
                lines.append(f"• [{t_str}] {app or 'App'}: {detail}")

            return "Aapki recent screen activity timeline:\n" + "\n".join(lines)

    except Exception as e:
        return f"Screen timeline recall error: {e}"


def screen_timeline(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """JARVIS action dispatcher for Screen Timeline."""
    params = parameters or {}
    action = str(params.get("action", "recall")).strip().lower()
    query = str(params.get("query", params.get("search", ""))).strip()
    minutes = int(params.get("minutes", params.get("time_range", 180)))
    limit = int(params.get("limit", 5))

    if action in ("record", "save", "snapshot"):
        ok = record_snapshot()
        return "Screen activity timeline me save ho gayi hai." if ok else "Screen snapshot record nahi ho saka (privacy ya inactive window)."

    # Default: recall
    return recall_screen_history(query=query, minutes=minutes, limit=limit)


TOOL = {
    "name": "screen_timeline",
    "description": "100% private local screen memory & timeline recall. Remembers what apps, windows, and tasks the user was working on, with full-text search across past activity.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: 'recall' (search/show past activity) or 'record' (save current activity snapshot)."
            },
            "query": {
                "type": "STRING",
                "description": "Keyword or topic to search for in past screen activity (e.g. 'python', 'vscodium', 'github', 'invoice')."
            },
            "minutes": {
                "type": "INTEGER",
                "description": "How many minutes into the past to look (default 180 = 3 hours)."
            },
            "limit": {
                "type": "INTEGER",
                "description": "Max number of timeline events to return (default 5)."
            }
        },
        "required": []
    },
    "handler": screen_timeline,
}
