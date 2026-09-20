"""
Multi-turn Context Buffer & Anaphora Resolution Engine for J.A.R.V.I.S.
Tracks active conversation entities (last_app, last_file, last_note, last_topic,
last_location, last_url, active_window) and transparently resolves pronouns
(isko, use, wahan, is par, it, this, that) into concrete entity references.
"""
from __future__ import annotations

import os
import re
import sys
import threading
from typing import Any, Dict, List, Optional


class ContextBuffer:
    """Thread-safe sliding buffer of active conversation context and entities."""

    def __init__(self):
        self._lock = threading.Lock()
        self.last_app: str = ""
        self.last_file: str = ""
        self.last_note: str = ""
        self.last_topic: str = ""
        self.last_location: str = ""
        self.last_url: str = ""
        self.last_window: str = ""
        self.last_tool: str = ""
        self.last_tool_args: Dict[str, Any] = {}
        self.last_user_query: str = ""
        self.last_assistant_response: str = ""
        self.history: List[Dict[str, Any]] = []

    def get_active_window_title(self) -> str:
        """Query operating system for current foreground window title."""
        try:
            if sys.platform == "win32":
                import ctypes
                u32 = ctypes.windll.user32
                hwnd = u32.GetForegroundWindow()
                if hwnd:
                    length = u32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        u32.GetWindowTextW(hwnd, buf, length + 1)
                        t = buf.value.strip()
                        if t:
                            with self._lock:
                                self.last_window = t
                            return t
        except Exception:
            pass
        return self.last_window

    def update(
        self,
        query: str = "",
        response: str = "",
        tool: str = "",
        args: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record turn state and automatically extract semantic entities."""
        with self._lock:
            q = (query or "").strip()
            r = (response or "").strip()
            t = (tool or "").strip()
            a = args or {}

            if q:
                self.last_user_query = q
            if r:
                self.last_assistant_response = r
            if t:
                self.last_tool = t
                self.last_tool_args = dict(a)

            # 1. App extraction
            if t == "open_app":
                app = a.get("app_name") or a.get("name") or ""
                if app and app.lower() not in ("list", "refresh", "scan"):
                    self.last_app = app.strip()
            elif q and any(w in q.lower() for w in ("kholo", "open", "launch", "chalao")):
                m_app = re.search(r"\b(chrome|brave|firefox|edge|notepad|calculator|vlc|spotify|code|cmd|terminal|whatsapp|telegram|obsidian)\b", q.lower())
                if m_app:
                    self.last_app = m_app.group(1)

            # 2. Obsidian Note extraction
            if t == "obsidian_brain":
                p = a.get("path") or a.get("query") or ""
                if p:
                    self.last_note = p.strip()
            elif "obsidian" in q.lower() or "note" in q.lower():
                m_note = re.search(r"note\s+([a-zA-Z0-9_\-\.]+)", q.lower())
                if m_note:
                    self.last_note = m_note.group(1)

            # 3. File extraction
            if t == "file_controller":
                f = a.get("path") or a.get("file") or a.get("target") or ""
                if f:
                    self.last_file = f.strip()

            # 4. Location extraction
            if t in ("weather", "current_weather"):
                loc = a.get("city") or a.get("location") or ""
                if loc:
                    self.last_location = loc.strip()
            elif any(w in q.lower() for w in ("mausam", "weather", "temperature")):
                m_loc = re.search(r"\b(?:in|at|ka|mein|me)\s+([A-Z][a-zA-Z]+|[a-zA-Z]{3,})\b", q)
                if m_loc and m_loc.group(1).lower() not in ("mausam", "weather", "kaisa", "batao", "aaj"):
                    self.last_location = m_loc.group(1).strip()

            # 5. URL extraction
            url_m = re.search(r"https?://[^\s]+", q + " " + str(a))
            if url_m:
                self.last_url = url_m.group(0).strip()

            # 6. Topic extraction
            if t == "web_search":
                top = a.get("query") or ""
                if top:
                    self.last_topic = top.strip()
            elif t == "youtube_search":
                top = a.get("song_name") or a.get("query") or ""
                if top:
                    self.last_topic = top.strip()

            # Keep short sliding turn record
            self.history.append({
                "query": q, "response": r[:150], "tool": t,
                "app": self.last_app, "note": self.last_note, "file": self.last_file
            })
            if len(self.history) > 12:
                self.history.pop(0)

    def resolve_anaphora(self, text: str) -> str:
        """
        Detects Hindi/Hinglish/English pronouns and resolves them using active context.
        Examples:
          'isko band karo' -> 'notepad band karo' (if last_app is notepad)
          'use padho' -> 'ProjectPlan.md padho' (if last_note is ProjectPlan.md)
          'wahan ka mausam' -> 'Mumbai ka mausam' (if last_location is Mumbai)
          'is par research karo' -> 'quantum computing par research karo'
        """
        raw = (text or "").strip()
        if not raw:
            return raw

        t_low = raw.lower()

        # Pronoun indicator triggers
        pronoun_triggers = (
            r"\b(isko|ise|isey|use|usko|unhe|unko|is par|us par|ispe|uspe|isme|mein iske|is cheez ko)\b|"
            r"\b(it|this|that|there|wahan|udhar)\b"
        )
        if not re.search(pronoun_triggers, t_low):
            return raw

        with self._lock:
            cur_app = self.last_app
            cur_note = self.last_note
            cur_file = self.last_file
            cur_topic = self.last_topic
            cur_loc = self.last_location
            cur_win = self.last_window

        # 1. Close / Kill / Stop commands: pronoun refers to app or active window
        if re.search(r"\b(band\s*karo|band\s*kar\s*do|close|kill|quit|stop|exit|hatao|minimize)\b", t_low):
            target_app = cur_app or (cur_win.split("-")[0].strip() if cur_win else "")
            if target_app:
                # Replace pronoun phrase with target_app
                resolved = re.sub(
                    r"\b(isko|ise|isey|use|usko|unhe|it|this|is app ko|is window ko)\b",
                    target_app,
                    raw,
                    flags=re.IGNORECASE
                )
                if resolved != raw:
                    return resolved
                # If pronoun was at start or implicit: e.g. "band karo"
                return f"{target_app} {raw}"

        # 2. Read / Open / Show commands: pronoun refers to note or file
        if re.search(r"\b(padho|read|dikhao|show|open|kholo|content)\b", t_low):
            target_doc = cur_note or cur_file
            if target_doc:
                resolved = re.sub(
                    r"\b(isko|ise|isey|use|usko|unhe|it|this|that|is note ko|is file ko)\b",
                    target_doc,
                    raw,
                    flags=re.IGNORECASE
                )
                if resolved != raw:
                    return resolved

        # 3. Location / Weather / Temperature commands: pronoun 'wahan' / 'udhar' / 'there'
        if re.search(r"\b(wahan|udhar|there)\b", t_low):
            if cur_loc:
                resolved = re.sub(
                    r"\b(wahan|udhar|there)\b",
                    cur_loc,
                    raw,
                    flags=re.IGNORECASE
                )
                if resolved != raw:
                    return resolved

        # 4. Search / Research / Explain commands: pronoun refers to topic
        if re.search(r"\b(research|search|khojo|dhoondho|batao|samjhao|explain|detail|jano)\b", t_low):
            if cur_topic:
                resolved = re.sub(
                    r"\b(is par|us par|ispe|uspe|isme|isko|ise|it|this|that|is topic par)\b",
                    f"{cur_topic} par",
                    raw,
                    flags=re.IGNORECASE
                )
                if resolved != raw:
                    return resolved

        # 5. Rename / Move commands: pronoun refers to last note or file
        if re.search(r"\b(rename|naam\s*badlo|move)\b", t_low):
            target_doc = cur_note or cur_file
            if target_doc:
                resolved = re.sub(
                    r"\b(isko|ise|isey|use|it|this)\b",
                    target_doc,
                    raw,
                    flags=re.IGNORECASE
                )
                if resolved != raw:
                    return resolved

        # 6. Generic Fallback: if 'isko' or 'use' is used and we have an active app or note
        fallback_ent = cur_app or cur_note or cur_topic
        if fallback_ent:
            resolved = re.sub(
                r"\b(isko|ise|isey|use|usko)\b",
                fallback_ent,
                raw,
                flags=re.IGNORECASE
            )
            return resolved

        return raw


_GLOBAL_CONTEXT: Optional[ContextBuffer] = None


def get_context_buffer() -> ContextBuffer:
    """Singleton getter for conversation context buffer."""
    global _GLOBAL_CONTEXT
    if _GLOBAL_CONTEXT is None:
        _GLOBAL_CONTEXT = ContextBuffer()
    return _GLOBAL_CONTEXT


def resolve_anaphora(text: str) -> str:
    """Convenience helper to resolve pronouns against active context buffer."""
    return get_context_buffer().resolve_anaphora(text)


def update_context(
    query: str = "",
    response: str = "",
    tool: str = "",
    args: Optional[Dict[str, Any]] = None,
) -> None:
    """Convenience helper to update active context buffer."""
    get_context_buffer().update(query=query, response=response, tool=tool, args=args)
