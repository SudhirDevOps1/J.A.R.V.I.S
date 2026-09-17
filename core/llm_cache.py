"""
core/llm_cache.py -- Smart LLM Response Cache for J.A.R.V.I.S.

SQLite-backed LRU cache to reduce token usage on repetitive requests.
Cache TTL is configurable per request type.
"""
import sqlite3
import hashlib
import json
import time
import threading
from pathlib import Path
import sys

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()
DB_PATH = BASE_DIR / "config" / "llm_cache.db"
MAX_ENTRIES = 500
_lock = threading.Lock()
_conn: sqlite3.Connection = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                expires_at REAL NOT NULL,
                created_at REAL NOT NULL,
                hit_count INTEGER DEFAULT 0
            )
        """)
        _conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires_at)")
        _conn.commit()
    return _conn


def _make_key(prompt: str, provider: str = "") -> str:
    raw = f"{provider}::{prompt[:500]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get(prompt: str, provider: str = "") -> str | None:
    """
    Retrieve cached response for prompt.
    Returns None if not found or expired.
    """
    with _lock:
        try:
            conn = _get_conn()
            key = _make_key(prompt, provider)
            cur = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
            )
            row = cur.fetchone()
            if row is None:
                return None
            value, expires_at = row
            if time.time() > expires_at:
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
                return None
            # Update hit count
            conn.execute("UPDATE cache SET hit_count = hit_count + 1 WHERE key = ?", (key,))
            conn.commit()
            return value
        except Exception:
            return None


def set(prompt: str, response: str, ttl_seconds: int, provider: str = ""):
    """
    Store response in cache with TTL.
    ttl_seconds=0 means do not cache.
    """
    if ttl_seconds <= 0:
        return
    with _lock:
        try:
            conn = _get_conn()
            key = _make_key(prompt, provider)
            now = time.time()
            conn.execute("""
                INSERT OR REPLACE INTO cache (key, value, expires_at, created_at, hit_count)
                VALUES (?, ?, ?, ?, 0)
            """, (key, response, now + ttl_seconds, now))
            conn.commit()
            # Evict if over limit
            _evict_if_needed(conn)
        except Exception as e:
            pass  # Cache failure should never break the app


def _evict_if_needed(conn: sqlite3.Connection):
    """Remove expired entries and oldest entries if over MAX_ENTRIES."""
    now = time.time()
    conn.execute("DELETE FROM cache WHERE expires_at < ?", (now,))
    count = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
    if count > MAX_ENTRIES:
        excess = count - MAX_ENTRIES
        conn.execute("""
            DELETE FROM cache WHERE key IN (
                SELECT key FROM cache ORDER BY created_at ASC LIMIT ?
            )
        """, (excess,))
    conn.commit()


def get_stats() -> dict:
    """Return cache statistics."""
    with _lock:
        try:
            conn = _get_conn()
            total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            hits = conn.execute("SELECT SUM(hit_count) FROM cache").fetchone()[0] or 0
            expired = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE expires_at < ?", (time.time(),)
            ).fetchone()[0]
            return {"total": total, "total_hits": hits, "expired": expired, "max": MAX_ENTRIES}
        except Exception:
            return {"total": 0, "total_hits": 0, "expired": 0, "max": MAX_ENTRIES}


def clear():
    """Clear all cache entries."""
    with _lock:
        try:
            conn = _get_conn()
            conn.execute("DELETE FROM cache")
            conn.commit()
        except Exception:
            pass


# TTL presets for common request types (seconds)
class TTL:
    NO_CACHE = 0          # Never cache (live chat, commands)
    NEWS = 1800           # 30 minutes
    WEATHER = 600         # 10 minutes
    SEARCH = 900          # 15 minutes
    GENERAL = 0           # No cache for general chat
    FACTS = 3600          # 1 hour for factual queries
