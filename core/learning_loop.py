"""
core/learning_loop.py — Closed-loop usage learning for J.A.R.V.I.S.

THE GAP THIS FILLS
------------------
J.A.R.V.I.S could already be *taught* things ("jab main X bolu to Y karo") via
actions/self_learning.py. What it could not do was learn from ordinary use. A
user could say the same command two hundred times and the assistant would still
route every one of them through the slowest path, with no memory that the
shorthand worked. Nothing recorded whether a tool call succeeded, nothing
penalised a phrase that kept failing, nothing promoted a proven phrase into the
fast Tier-1 reflex router.

So "jitna use karunga utna improve hoga" was not actually true.

WHAT THIS DOES
--------------
Every tool invocation is observed. Outcomes accumulate per (normalised phrase →
tool), and from that:

  * success rate     — drives confidence; low-confidence phrases stop being
                       auto-executed and start asking for confirmation
  * promotion         — a phrase that reliably succeeds is promoted into the
                       Tier-1 reflex path so it skips the cloud round-trip
  * demotion          — a phrase that keeps failing is suppressed for a while
                       rather than retried forever
  * corrections       — an explicit "ye galat hai" is attached to the exact
                       phrase/tool pair that produced it
  * suggestions       — the engine can name the phrases it has learned and the
                       ones it is still unsure about

Storage is SQLite (memory/learning.db) rather than JSON so that a crash cannot
lose a day of learning, and so aggregates can be queried without loading the
whole history.

PRIVACY
-------
Everything stays on disk, on this machine, in the same database directory as
the rest of the assistant's memory. No part of this is ever sent to a provider.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = _BASE_DIR / "memory" / "learning.db"

# A phrase needs this many observations before the engine will act on it. Below
# this, statistics are noise and acting on them causes flapping.
MIN_OBSERVATIONS = 3
# Success rate at or above which a phrase may be promoted to the fast path.
PROMOTE_SUCCESS_RATE = 0.85
# Success rate below which a phrase is suppressed for a while.
DEMOTE_SUCCESS_RATE = 0.35
# How long to suppress a failing phrase before retrying it.
DEMOTE_COOLDOWN_S = 1800.0

_LOCK = threading.RLock()
_CONN: Optional[sqlite3.Connection] = None


# ── normalisation ───────────────────────────────────────────────────────────

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")


def normalize_phrase(text: str) -> str:
    """Reduce a spoken/written command to a stable key.

    The point is to recognise that "kholo notepad", "notepad kholo" and
    "Notepad   kholo!!!" are the same intent, so evidence accumulates on one
    bucket instead of three. Deliberately conservative: it strips punctuation,
    folds whitespace and lowercases, but does NOT remove stopwords, because
    removing them would over-merge distinct commands ("open notepad" vs "close
    notepad").
    """
    t = unicodedata.normalize("NFKC", str(text or "")).strip().lower()
    t = _PUNCT.sub(" ", t)
    t = _WS.sub(" ", t).strip()
    return t[:160]


# ── database ────────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    global _CONN
    if _CONN is not None:
        return _CONN
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS patterns (
            phrase       TEXT PRIMARY KEY,
            tool         TEXT NOT NULL,
            hits         INTEGER NOT NULL DEFAULT 0,
            successes    INTEGER NOT NULL DEFAULT 0,
            failures     INTEGER NOT NULL DEFAULT 0,
            total_ms     INTEGER NOT NULL DEFAULT 0,
            corrections  INTEGER NOT NULL DEFAULT 0,
            promoted     INTEGER NOT NULL DEFAULT 0,
            suppressed_until REAL NOT NULL DEFAULT 0,
            last_seen    REAL NOT NULL DEFAULT 0,
            first_seen   REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS events (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            ts       REAL NOT NULL,
            phrase   TEXT NOT NULL,
            tool     TEXT NOT NULL,
            ok       INTEGER NOT NULL,
            ms       INTEGER NOT NULL DEFAULT 0,
            note     TEXT
        );

        CREATE TABLE IF NOT EXISTS corrections (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            ts     REAL NOT NULL,
            phrase TEXT NOT NULL,
            tool   TEXT NOT NULL DEFAULT '',
            rule   TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_events_phrase ON events(phrase);
        CREATE INDEX IF NOT EXISTS idx_events_ts     ON events(ts);
    """)
    conn.commit()
    _CONN = conn
    return conn


def reset_connection() -> None:
    """Drop the cached handle (used by tests that point DB_PATH elsewhere)."""
    global _CONN
    with _LOCK:
        if _CONN is not None:
            try:
                _CONN.close()
            except Exception:
                pass
        _CONN = None


# ── recording ───────────────────────────────────────────────────────────────

def record_outcome(
    phrase: str,
    tool: str,
    ok: bool,
    duration_ms: int = 0,
    note: str = "",
    logger: Optional[Callable[[str], None]] = None,
) -> None:
    """Record one tool invocation outcome. Never raises.

    This is the single entry point the whole learning loop depends on, so it is
    written to be safe to call from any thread on any failure path — losing a
    learning observation must never break the action it was observing.
    """
    p = normalize_phrase(phrase)
    t = str(tool or "").strip()
    if not p or not t:
        return
    now = time.time()
    try:
        with _LOCK:
            conn = _connect()
            conn.execute(
                """INSERT INTO patterns (phrase, tool, hits, successes, failures,
                                        total_ms, last_seen, first_seen)
                   VALUES (?,?,1,?,?,?,?,?)
                   ON CONFLICT(phrase) DO UPDATE SET
                       hits         = hits + 1,
                       successes    = successes + ?,
                       failures     = failures + ?,
                       total_ms     = total_ms + ?,
                       tool         = excluded.tool,
                       last_seen    = excluded.last_seen""",
                (p, t, 1 if ok else 0, 0 if ok else 1, max(0, int(duration_ms)),
                 now, now, 1 if ok else 0, 0 if ok else 1, max(0, int(duration_ms))),
            )
            conn.execute(
                "INSERT INTO events (ts, phrase, tool, ok, ms, note) VALUES (?,?,?,?,?,?)",
                (now, p, t, 1 if ok else 0, max(0, int(duration_ms)), str(note or "")[:200]),
            )
            conn.commit()
    except Exception as e:
        if logger:
            logger(f"learning record failed: {e}")


def record_correction(phrase: str, tool: str = "", rule: str = "") -> int:
    """Attach an explicit user correction to a phrase.

    Returns the resulting correction count for that phrase. Corrections also
    demote: a phrase the user has corrected should not be auto-executed until it
    has demonstrated it learned the lesson.
    """
    p = normalize_phrase(phrase)
    if not p:
        return 0
    now = time.time()
    try:
        with _LOCK:
            conn = _connect()
            conn.execute(
                "INSERT INTO corrections (ts, phrase, tool, rule) VALUES (?,?,?,?)",
                (now, p, str(tool or "")[:80], str(rule or "")[:400]),
            )
            conn.execute(
                """INSERT INTO patterns (phrase, tool, corrections, suppressed_until, last_seen, first_seen)
                   VALUES (?,?,1,?,?,?)
                   ON CONFLICT(phrase) DO UPDATE SET
                       corrections      = corrections + 1,
                       suppressed_until = MAX(suppressed_until, ?),
                       last_seen        = excluded.last_seen""",
                (p, str(tool or "")[:80], now + DEMOTE_COOLDOWN_S, now, now, now + DEMOTE_COOLDOWN_S),
            )
            conn.commit()
            row = conn.execute(
                "SELECT corrections FROM patterns WHERE phrase = ?", (p,)
            ).fetchone()
            return int(row["corrections"]) if row else 1
    except Exception:
        return 0


# ── queries ─────────────────────────────────────────────────────────────────

def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    return dict(row) if row is not None else None


def get_pattern(phrase: str) -> Optional[Dict[str, Any]]:
    p = normalize_phrase(phrase)
    if not p:
        return None
    try:
        with _LOCK:
            conn = _connect()
            return _row_to_dict(conn.execute(
                "SELECT * FROM patterns WHERE phrase = ?", (p,)
            ).fetchone())
    except Exception:
        return None


def success_rate(row: Dict[str, Any]) -> float:
    hits = int(row.get("hits") or 0)
    return (int(row.get("successes") or 0) / hits) if hits else 0.0


def confidence_for(phrase: str) -> float:
    """Blended success rate and observation count, in [0, 1].

    Uses a Laplace-style prior so a single success does not read as certainty:
    (successes + 1) / (hits + 2). A phrase with 1/1 scores 0.67; 20/20 scores
    0.95. That matters because the promotion threshold is 0.85.
    """
    row = get_pattern(phrase)
    if not row:
        return 0.0
    hits = int(row.get("hits") or 0)
    succ = int(row.get("successes") or 0)
    return (succ + 1.0) / (hits + 2.0)


def should_auto_execute(phrase: str) -> bool:
    """May this phrase bypass confirmation and run without asking?

    Requires enough evidence, a good success rate, no active suppression, and
    either previous promotion or an already-strong track record.

    An explicit promotion overrides an active correction-suppression: if the
    user promotes a phrase themselves (via `learning_ctl promote`, which is a
    deliberate act), that outranks the automatic cooldown the correction
    installed. Otherwise a corrected phrase could never become trusted again
    without waiting out a 30-minute cooldown the user cannot see or shorten.
    """
    row = get_pattern(phrase)
    if not row:
        return False
    if int(row.get("hits") or 0) < MIN_OBSERVATIONS:
        return False
    if success_rate(row) < PROMOTE_SUCCESS_RATE:
        return False
    if int(row.get("promoted") or 0):
        # Explicitly promoted by the user: trust it, ignore the cooldown.
        return True
    if time.time() < float(row.get("suppressed_until") or 0):
        return False
    if int(row.get("corrections") or 0) > 0:
        # Corrected but never re-validated: treat as untrusted.
        return False
    return True


def suggest_promotions(limit: int = 20) -> List[Dict[str, Any]]:
    """Phrases the engine believes are ready to run without confirmation."""
    now = time.time()
    try:
        with _LOCK:
            conn = _connect()
            rows = conn.execute(
                """SELECT * FROM patterns
                   WHERE hits >= ? AND suppressed_until < ? AND promoted = 0
                   ORDER BY (CAST(successes AS REAL) / hits) DESC, hits DESC
                   LIMIT ?""",
                (MIN_OBSERVATIONS, now, limit * 3),
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if success_rate(d) >= PROMOTE_SUCCESS_RATE:
                out.append(d)
            if len(out) >= limit:
                break
        return out
    except Exception:
        return []


def suggest_demotions(limit: int = 20) -> List[Dict[str, Any]]:
    """Phrases that are failing and should be suppressed."""
    try:
        with _LOCK:
            conn = _connect()
            rows = conn.execute(
                """SELECT * FROM patterns
                   WHERE hits >= ? AND suppressed_until < ?
                   ORDER BY failures DESC, hits DESC
                   LIMIT ?""",
                (MIN_OBSERVATIONS, time.time(), limit),
            ).fetchall()
        return [dict(r) for r in rows
                if success_rate(dict(r)) < DEMOTE_SUCCESS_RATE]
    except Exception:
        return []


def set_promoted(phrase: str, promoted: bool = True) -> bool:
    p = normalize_phrase(phrase)
    if not p:
        return False
    try:
        with _LOCK:
            conn = _connect()
            cur = conn.execute(
                "UPDATE patterns SET promoted = ? WHERE phrase = ?",
                (1 if promoted else 0, p),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception:
        return False


def reset_promotions() -> int:
    """Clear all promotions. Exposed so the user can undo the engine's
    decisions wholesale rather than hunting for them one at a time."""
    try:
        with _LOCK:
            conn = _connect()
            cur = conn.execute("UPDATE patterns SET promoted = 0")
            conn.commit()
            return cur.rowcount
    except Exception:
        return 0


def stats() -> Dict[str, Any]:
    """Aggregate counters for the HUD / 'mcp status'-style summaries."""
    try:
        with _LOCK:
            conn = _connect()
            row = conn.execute(
                """SELECT COUNT(*)                      AS patterns,
                          COALESCE(SUM(hits), 0)         AS hits,
                          COALESCE(SUM(successes), 0)    AS successes,
                          COALESCE(SUM(failures), 0)     AS failures,
                          COALESCE(SUM(promoted), 0)     AS promoted,
                          COALESCE(SUM(corrections), 0)  AS corrections
                   FROM patterns"""
            ).fetchone()
            events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            return {
                "patterns": int(row["patterns"]),
                "hits": int(row["hits"]),
                "successes": int(row["successes"]),
                "failures": int(row["failures"]),
                "promoted": int(row["promoted"]),
                "corrections": int(row["corrections"]),
                "events": int(events),
                "success_rate": (round(100.0 * int(row["successes"]) / int(row["hits"]), 1)
                                 if int(row["hits"]) else 0.0),
            }
    except Exception:
        return {"patterns": 0, "hits": 0, "successes": 0, "failures": 0,
                "promoted": 0, "corrections": 0, "events": 0, "success_rate": 0.0}


def top_patterns(limit: int = 10) -> List[Dict[str, Any]]:
    try:
        with _LOCK:
            conn = _connect()
            rows = conn.execute(
                "SELECT * FROM patterns ORDER BY hits DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def recent_events(limit: int = 20) -> List[Dict[str, Any]]:
    try:
        with _LOCK:
            conn = _connect()
            rows = conn.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def list_corrections(limit: int = 10) -> List[Dict[str, Any]]:
    try:
        with _LOCK:
            conn = _connect()
            rows = conn.execute(
                "SELECT * FROM corrections ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def forget_pattern(phrase: str) -> bool:
    p = normalize_phrase(phrase)
    if not p:
        return False
    try:
        with _LOCK:
            conn = _connect()
            cur = conn.execute("DELETE FROM patterns WHERE phrase = ?", (p,))
            conn.commit()
            return cur.rowcount > 0
    except Exception:
        return False


def reset_all() -> None:
    """Wipe learned data. Used by the user-facing reset action."""
    try:
        with _LOCK:
            conn = _connect()
            conn.executescript(
                "DELETE FROM patterns; DELETE FROM events; DELETE FROM corrections;"
            )
            conn.commit()
    except Exception:
        pass


def summary_text() -> str:
    """Hinglish status line for voice / chat."""
    s = stats()
    if not s["patterns"]:
        return ("🧠 Learning loop: abhi koi pattern nahi seekha. Jaise-jaise aap commands "
                "repeat karenge, main unhe pehchanne aur seedha chalane lagunga.")
    lines = [
        f"🧠 Learning loop: {s['patterns']} pattern(s) seekhe hain, "
        f"{s['hits']} command(s) observe kiye, {s['success_rate']}% success.",
    ]
    if s["promoted"]:
        lines.append(f"   ⚡ {s['promoted']} command(s) ab bina puchhe seedha chalte hain.")
    if s["corrections"]:
        lines.append(f"   📌 {s['corrections']} correction(s) note kiye gaye hain.")
    ready = suggest_promotions(limit=5)
    if ready:
        lines.append("   🔜 promote hone wale:")
        for r in ready[:5]:
            lines.append(f"      • \"{r['phrase']}\" → {r['tool']} "
                         f"({int(r['successes'])}/{int(r['hits'])})")
    return "\n".join(lines)