"""
actions/quick_notes.py — Voice Quick-Notes & Thought Journal for J.A.R.V.I.S.

Directly integrated with the Unified SQLite WAL + FTS5 engine (core/unified_memory.py).
Allows the user to dictate fleeting thoughts, scratch notes, and meeting memos,
and instantly recall them via full-text search (< 0.5ms) with zero RAM overhead.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from core.unified_memory import (
    get_db,
    log_journal_entry,
    recall_memories,
    search_journal,
    store_memory,
)


def quick_notes(
    parameters: dict | None = None,
    player=None,
    speak=None,
    response=None,
    session_memory=None,
    **_
) -> str:
    params = parameters or {}
    action = str(params.get("action", "add") or "add").lower().strip()
    text = str(params.get("text", "") or params.get("content", "") or "").strip()
    query = str(params.get("query", "") or text).strip()

    # 1. ADD QUICK NOTE
    if action in ("add", "save", "write", "note"):
        if not text:
            return "Note ka content khali hai. Kripya batayein kya note karna hai."
            
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        key = f"note_{int(time.time())}"
        
        # Save both to structured memories and FTS5 journal
        store_memory("quick_notes", key, f"[{timestamp_str}] {text}")
        log_journal_entry(f"NOTE: {text}", category="quick_notes")
        
        if player:
            player.write_log(f"[QuickNotes] Saved note: {text[:50]}")
            
        return f"Note successfully save ho gaya ({timestamp_str}): \"{text}\""

    # 2. SEARCH NOTES (FTS5 BM25)
    elif action in ("search", "find", "recall"):
        if not query:
            return "Search karne ke liye query batayein (e.g. query='meeting')."
            
        # Try full-text search first
        fts_hits = search_journal(query, limit=5)
        note_hits = [h for h in fts_hits if h.get("category") == "quick_notes"]
        
        if not note_hits:
            # Fallback to structured memories recall
            mem_hits = recall_memories(query, limit=5)
            note_hits = [
                {"content": m["value"], "timestamp": m["updated_at"][:16]}
                for m in mem_hits if m.get("category") == "quick_notes"
            ]

        if not note_hits:
            return f"'{query}' se related koi notes nahi mile."

        lines = [f"Found {len(note_hits)} Note(s) matching '{query}':"]
        for i, h in enumerate(note_hits, 1):
            ts = h.get("timestamp", "")
            cnt = h.get("content", "").replace("NOTE: ", "")
            lines.append(f"{i}. [{ts}] {cnt}")
        return "\n".join(lines)

    # 3. LIST RECENT NOTES
    elif action in ("list", "recent", "all"):
        hits = recall_memories("", limit=10)
        recent_notes = [m for m in hits if m.get("category") == "quick_notes"]
        
        if not recent_notes:
            return "Abhi koi saved notes nahi hain. Bol sakte hain: 'Note likho: ...'"

        lines = ["Recent Saved Notes:"]
        for i, m in enumerate(recent_notes[:5], 1):
            val = m.get("value", "")
            lines.append(f"{i}. {val}")
        return "\n".join(lines)

    return f"Quick Notes: Unknown action '{action}'. Options: add, search, list."


TOOL = {
    "name": "quick_notes",
    "description": (
        "Quickly notes down thoughts, meeting summaries, or reminders, and searches them "
        "using ultra-fast SQLite FTS5 full-text search. Trigger on 'note likho', 'quick note', "
        "'notes search karo', 'purane notes dikhao'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "add | search | list"
            },
            "text": {
                "type": "STRING",
                "description": "Content of the note to save"
            },
            "query": {
                "type": "STRING",
                "description": "Search keyword when action is 'search'"
            }
        },
        "required": ["action"]
    },
    "handler": quick_notes
}
