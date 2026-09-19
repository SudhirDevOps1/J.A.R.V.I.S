import json
import re
from datetime import datetime
from threading import Lock
from pathlib import Path
import sys


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR         = get_base_dir()
MEMORY_PATH      = BASE_DIR / "memory" / "long_term.json"
_lock            = Lock()
MAX_VALUE_LENGTH = 380

# ── Prompt-block cache ───────────────────────────────────────────────────────
# format_memory_for_prompt() is a pure function of its `memory` argument, but
# it sorts every entry on every call — and it is called on every session
# connect AND every typed multi-LLM query. The cache below memoises the
# result keyed by a SHA-256 of the input, so repeated calls with unchanged
# memory are O(hash) instead of O(n log n). Every writer funnels through
# save_memory() / pop_last_session() / save_session_summary(), and each of
# those calls invalidate_prompt_cache() — stale reads are impossible unless a
# writer bypasses all three (none do).
_prompt_cache: dict[str, str] = {}
_prompt_cache_lock = Lock()
_PROMPT_CACHE_MAX = 8


def _prompt_cache_key(memory: dict) -> str:
    try:
        import hashlib
        raw = json.dumps(memory, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
    except Exception:
        return ""


def invalidate_prompt_cache() -> None:
    """Drop all cached prompt blocks. Called by every memory writer."""
    with _prompt_cache_lock:
        _prompt_cache.clear()

# ── Why there are two very different numbers here ────────────────────────────
#
# There used to be one: MEMORY_MAX_CHARS = 2200, applied to the whole store. It
# was a *storage* limit, and it existed only because the entire memory was
# pasted into the system prompt on every connect — so growing the memory grew
# every single request. When it filled, _trim_to_limit() deleted the oldest
# entries and printed one line to a console nobody reads. A memory described as
# "deeply remembers projects, preferences and personal context" was in practice
# two pages long, and quietly forgot your sister's name after a few weeks.
#
# Storage and prompt budget are now separate concerns:
#
#   MEMORY_MAX_CHARS  — a runaway guard, not a feature limit. Nothing normal
#                       reaches it; a bug writing in a loop does.
#   PROMPT_CORE_CHARS — what actually rides in the system prompt every session.
#                       Smaller than the old whole-memory dump, so sessions
#                       start *faster* than before, not slower.
#
# Everything above the core stays on disk and is fetched on demand by the
# recall_memory tool — see search_memory() and format_memory_for_prompt().
MEMORY_MAX_CHARS  = 200_000
PROMPT_CORE_CHARS = 900
PROMPT_INDEX_CHARS = 420
# Most entries any one category may contribute to the core block, so a person
# with forty stored preferences still gets their sister into the prompt.
PROMPT_MAX_PER_CATEGORY = 6

def _empty_memory() -> dict:
    return {
        "identity":      {},
        "preferences":   {},
        "projects":      {},
        "relationships": {},
        "wishes":        {},
        "notes":         {},
    }

def load_memory() -> dict:
    if not MEMORY_PATH.exists():
        return _empty_memory()
    with _lock:
        try:
            data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                base = _empty_memory()
                for key in base:
                    if key not in data:
                        data[key] = {}
                return data
            return _empty_memory()
        except Exception as e:
            print(f"[Memory] ⚠️ Load error: {e}")
            return _empty_memory()

def _all_entries(memory: dict) -> list[tuple]:
    entries = []
    for cat, items in memory.items():
        if not isinstance(items, dict):
            continue
        for key, entry in items.items():
            if isinstance(entry, dict) and "value" in entry:
                entries.append((cat, key, entry))
    return entries


# Set by main.py so a trim can reach the activity log. Deleting something a
# person told you and mentioning it only on stdout is how a memory loses trust.
_trim_notifier = None


def set_trim_notifier(fn) -> None:
    """Register a callable(str) that surfaces trims to the user."""
    global _trim_notifier
    _trim_notifier = fn


def _trim_to_limit(memory: dict) -> dict:
    if len(json.dumps(memory, ensure_ascii=False)) <= MEMORY_MAX_CHARS:
        return memory
    entries = _all_entries(memory)
    entries.sort(key=lambda t: t[2].get("updated", "0000-00-00"))
    dropped = []
    for cat, key, _ in entries:
        if len(json.dumps(memory, ensure_ascii=False)) <= MEMORY_MAX_CHARS:
            break
        del memory[cat][key]
        dropped.append(f"{cat}/{key}")
        print(f"[Memory] 🗑️  Trimmed {cat}/{key}")
    if dropped and _trim_notifier:
        try:
            _trim_notifier(
                f"SYS: Memory full — forgot {len(dropped)} oldest entries "
                f"({', '.join(dropped[:3])}{'…' if len(dropped) > 3 else ''})"
            )
        except Exception:
            pass
    return memory

_MEMORY_BAK_KEEP = 5


def _prune_memory_backups() -> None:
    """Keep max _MEMORY_BAK_KEEP long_term.json.bak-* files (mirrors config backups)."""
    try:
        olds = sorted(MEMORY_PATH.parent.glob("long_term.json.bak-*"))
        for _old in olds[:-_MEMORY_BAK_KEEP]:
            try:
                _old.unlink()
            except Exception:
                pass
    except Exception:
        pass


def _backup_memory() -> None:
    """Timestamped backup before overwriting long_term.json. Never raises."""
    try:
        if not MEMORY_PATH.exists():
            return
        import shutil as _sh
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        _sh.copy2(str(MEMORY_PATH), str(MEMORY_PATH.parent / f"long_term.json.bak-{ts}"))
        _prune_memory_backups()
    except Exception as e:
        print(f"[Memory] ⚠️ Backup note: {e}")


def save_memory(memory: dict) -> None:
    if not isinstance(memory, dict):
        return
    memory = _trim_to_limit(memory)
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        _backup_memory()
        MEMORY_PATH.write_text(
            json.dumps(memory, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    invalidate_prompt_cache()


def _truncate_value(val: str) -> str:
    if isinstance(val, str) and len(val) > MAX_VALUE_LENGTH:
        return val[:MAX_VALUE_LENGTH].rstrip() + "…"
    return val


def _find_duplicate_key(memory: dict, new_val: str, skip_cat: str = "", skip_key: str = "") -> str:
    """Find an existing 'cat/key' holding the identical value ('' if none).

    Prevents 'ayse' vs 'ayse_sister' style duplicates from piling up: the same
    fact saved under a second key is skipped with a log line instead of stored
    twice. Short values (<4 chars) are exempt — 'yes'/'ok' collide by nature.
    """
    try:
        needle = str(new_val or "").strip()
        if len(needle) < 4:
            return ""
        for cat, items in (memory or {}).items():
            if not isinstance(items, dict):
                continue
            for key, entry in items.items():
                if cat == skip_cat and key == skip_key:
                    continue
                if _entry_value(entry) == needle:
                    return f"{cat}/{key}"
    except Exception:
        pass
    return ""


def _recursive_update(target: dict, updates: dict, _root: dict | None = None) -> bool:
    changed = False
    if _root is None:
        _root = target  # top-level call: dupe scan covers the whole store
    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, dict) and "value" not in value:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
                changed = True
            if _recursive_update(target[key], value, _root):
                changed = True
        else:
            new_val  = _truncate_value(str(value["value"] if isinstance(value, dict) else value))
            entry    = {"value": new_val, "updated": datetime.now().strftime("%Y-%m-%d")}
            existing = target.get(key, {})
            if not isinstance(existing, dict) or existing.get("value") != new_val:
                dupe = _find_duplicate_key(_root, new_val)
                if dupe:
                    print(f"[Memory] ♻️  Duplicate skipped (already at {dupe}): {new_val[:60]}")
                    continue
                target[key] = entry
                changed = True
    return changed


def update_memory(memory_update: dict) -> dict:
    if not isinstance(memory_update, dict) or not memory_update:
        return load_memory()
    memory = load_memory()
    if _recursive_update(memory, memory_update):
        save_memory(memory)
        print(f"[Memory] 💾 Saved: {list(memory_update.keys())}")
        # ADDITIVE KG hook: graph triples (regex, no LLM). Fail-safe, purana save untouched.
        try:
            from memory.knowledge_graph import ingest_memory_update
            ingest_memory_update(memory_update)
        except Exception:
            pass
    return memory

def _entry_value(entry) -> str:
    """Accept both the {'value': ..., 'updated': ...} shape and a bare string,
    because early versions of the store wrote plain strings."""
    if isinstance(entry, dict):
        return str(entry.get("value", "") or "").strip()
    return str(entry or "").strip()


def _pretty(key: str) -> str:
    return key.replace("_", " ").strip()


# Identity is always in the prompt; these categories compete for the remaining
# budget by recency.
_CATEGORY_LABELS = {
    "preferences":   "Preferences",
    "projects":      "Active projects / goals",
    "relationships": "People in their life",
    "wishes":        "Wishes / plans",
    "notes":         "Notes",
}

_IDENTITY_FIELDS = ["name", "age", "birthday", "city", "job",
                    "language", "school", "nationality"]


def format_memory_for_prompt(memory: dict | None) -> str:
    """Build the memory block that goes into the system prompt.

    This used to dump everything. It now sends three things:

      1. IDENTITY  - always, in full. It is small, and it is wrong for the
         assistant to have to look up your name.
      2. RECENT    - the most recently updated entries from every other
         category, up to PROMPT_CORE_CHARS. Recency is the cheapest useful
         relevance signal available without embeddings.
      3. AN INDEX  - the *keys* of everything else, values omitted.

    Point 3 is what makes recall work at all. A model cannot decide to look
    something up if it does not know the thing exists: with only points 1 and 2,
    "who is Ayse?" would get "I don't know" while ayse_sister sat on disk
    unread. The index costs a few hundred characters and turns recall from a
    gamble into a lookup.

    Net effect on latency: this block is SMALLER than the old full dump, so
    every session connects with fewer tokens. Occasionally the model spends one
    extra round trip on recall_memory - covered by the acknowledgment it
    already speaks before any slow step."""
    if not memory:
        return ""

    # Memoised: identical memory → identical block, no re-sort.
    _ckey = _prompt_cache_key(memory)
    if _ckey:
        with _prompt_cache_lock:
            _hit = _prompt_cache.get(_ckey)
        if _hit is not None:
            return _hit

    core_lines: list[str] = []

    # 1. Identity - always, in full
    identity = memory.get("identity", {}) or {}
    for field in _IDENTITY_FIELDS:
        val = _entry_value(identity.get(field))
        if not val:
            continue
        if field == "language":
            # Labelled as an observation, not a setting. A bare "Language:
            # English" line written months ago reads like a standing order and
            # was one of the reasons a Turkish question came back in English.
            core_lines.append(
                f"Has spoken to you in: {val} (an observation about the past — "
                f"always answer in the language of their CURRENT message)")
        else:
            core_lines.append(f"{field.title()}: {val}")
    for key, entry in identity.items():
        if key in _IDENTITY_FIELDS:
            continue
        val = _entry_value(entry)
        if val:
            core_lines.append(f"{_pretty(key).title()}: {val}")

    # 2. Everything else, most recently updated first
    rest: list[tuple[str, str, str, str]] = []   # (updated, cat, key, value)
    for cat in _CATEGORY_LABELS:
        for key, entry in (memory.get(cat, {}) or {}).items():
            val = _entry_value(entry)
            if not val:
                continue
            updated = (entry.get("updated", "") if isinstance(entry, dict) else "") or "0000-00-00"
            rest.append((updated, cat, key, val))
    rest.sort(key=lambda t: t[0], reverse=True)

    used    = sum(len(l) + 1 for l in core_lines)
    shown: dict[str, list[str]] = {}
    overflow: dict[str, list[str]] = {}

    # Recency decides order, but no single category may take the whole budget.
    # Without the cap, someone with forty stored preferences gets a prompt that
    # is forty preferences and not one person's name — the categories that
    # matter most in conversation are also the ones that change least often, so
    # pure recency systematically buries them.
    per_cat_used: dict[str, int] = {}
    for _updated, cat, key, val in rest:
        line = f"  - {_pretty(key).title()}: {val}"
        if (per_cat_used.get(cat, 0) < PROMPT_MAX_PER_CATEGORY
                and used + len(line) + 1 <= PROMPT_CORE_CHARS):
            shown.setdefault(cat, []).append(line)
            per_cat_used[cat] = per_cat_used.get(cat, 0) + 1
            used += len(line) + 1
        else:
            overflow.setdefault(cat, []).append(_pretty(key))

    # The index is a table of contents, so it is interleaved across categories
    # rather than continuing in recency order. Sorted by recency it would list
    # twenty-four preferences before the first relationship, and the one entry
    # the index exists for — the old fact the model has no other way to know
    # about — would fall off the end.
    indexed: list[str] = []
    if overflow:
        cats  = [c for c in _CATEGORY_LABELS if overflow.get(c)]
        cursor = {c: 0 for c in cats}
        while cats:
            for cat in list(cats):
                i = cursor[cat]
                if i >= len(overflow[cat]):
                    cats.remove(cat)
                    continue
                indexed.append(overflow[cat][i])
                cursor[cat] = i + 1

    for cat, label in _CATEGORY_LABELS.items():
        if shown.get(cat):
            core_lines.append("")
            core_lines.append(f"{label}:")
            core_lines.extend(shown[cat])

    if not core_lines and not indexed:
        return ""

    def _cache_store(result: str) -> str:
        if _ckey:
            with _prompt_cache_lock:
                if len(_prompt_cache) >= _PROMPT_CACHE_MAX:
                    _prompt_cache.clear()
                _prompt_cache[_ckey] = result
        return result

    out = [
        "[WHAT YOU KNOW ABOUT THIS PERSON — use naturally, never recite like a list]",
        *core_lines,
    ]

    # 3. The index of what is on disk but not in this prompt
    if indexed:
        budget, names = PROMPT_INDEX_CHARS, []
        for n in indexed:
            if budget - len(n) - 2 < 0:
                break
            names.append(n)
            budget -= len(n) + 2
        if names:
            out.append("")
            out.append(
                "[ALSO REMEMBERED — values not shown here. Call recall_memory "
                "with a keyword to read any of these before saying you do not know]"
            )
            out.append(", ".join(names)
                       + (f" (+{len(indexed) - len(names)} more)"
                          if len(indexed) > len(names) else ""))

    return _cache_store("\n".join(out) + "\n")


# ── Recall ────────────────────────────────────────────────────────────────────

def _lev_ratio(a: str, b: str) -> float:
    """Tiny dependency-free similarity ratio (0..100, SequenceMatcher-style).

    Used when thefuzz isn't installed so typo-tolerance works out of the box.
    O(len(a)*len(b)) with early exit for very long strings.
    """
    try:
        if not a or not b:
            return 0.0
        if len(a) > 64 or len(b) > 64:
            return 0.0
        # Classic DP Levenshtein on the shorter-first pair.
        if len(a) > len(b):
            a, b = b, a
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cost = 0 if ca == cb else 1
                cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
            prev = cur
        dist = prev[len(b)]
        return (1.0 - dist / max(len(a), len(b))) * 100.0
    except Exception:
        return 0.0


def _fuzzy_bonus(word: str, hay: str) -> int:
    """Typo-tolerant fallback (similarity ≥ 75 → small bonus).

    Runs ONLY when exact/substring matching already scored 0 for the word, so
    the hot path stays as fast as before and 'Ayse' still finds 'Ayşe'.
    Prefers thefuzz when installed, else the built-in Levenshtein ratio.
    """
    try:
        if not word or not hay or len(word) < 3:
            return 0
        try:
            from thefuzz import fuzz as _fuzz
            ratio = float(_fuzz.partial_ratio(word, hay))
        except Exception:
            # partial_ratio ≈ best alignment of the shorter string: slide
            # `word` over `hay` windows and take the max ratio.
            w, h = word.lower(), hay.lower()
            if len(w) > len(h):
                w, h = h, w
            ratio = 0.0
            step = max(1, (len(h) - len(w)) // 8 + 1)
            for i in range(0, len(h) - len(w) + 1, step):
                r = _lev_ratio(w, h[i:i + len(w)])
                if r > ratio:
                    ratio = r
                    if ratio >= 90.0:
                        break
        # 75 ≈ ≤2 edits on a 9-char word ('restorant'~'restaurant' = 80).
        # Bonus stays tiny (+2) so typos never outrank exact matches.
        return 2 if ratio >= 75.0 else 0
    except Exception:
        return 0


def _score(query_words: list[str], cat: str, key: str, value: str) -> int:
    """Cheap lexical relevance. No embeddings, no network, no model call - this
    runs in well under a millisecond, which is the entire point: recall must
    cost one model round trip, never two."""
    hay_key = _pretty(key).lower()
    hay_val = value.lower()
    score   = 0
    for w in query_words:
        if not w:
            continue
        word_hit = False
        if w == hay_key:
            score += 10
            word_hit = True
        elif w in hay_key:
            score += 6
            word_hit = True
        if w in hay_val:
            score += 3
            word_hit = True
        if w in cat:
            score += 1
            word_hit = True
        if not word_hit:
            # Typo fallback: 'ayse' ~ 'ayşe', 'restorant' ~ 'restaurant'.
            score += max(_fuzzy_bonus(w, hay_key), _fuzzy_bonus(w, hay_val))
    return score


def search_memory(query: str, limit: int = 8) -> str:
    """Find stored facts matching `query`. Backs the recall_memory tool.

    An empty query is treated as "show me everything you know", capped - the
    model asks that when the user says "what do you remember about me?"."""
    memory = load_memory()
    words  = [w for w in re.split(r"[^\w]+", (query or "").lower()) if len(w) > 1]

    rows: list[tuple[int, str, str, str]] = []
    for cat, items in memory.items():
        if cat == "sessions" and isinstance(items, list):
            # Past session summaries ARE searchable (previously invisible).
            for sess in items:
                if not isinstance(sess, dict):
                    continue
                summary = str(sess.get("summary", "") or "").strip()
                if not summary:
                    continue
                s = _score(words, "sessions", sess.get("date", "session"), summary) if words else 1
                if s > 0:
                    rows.append((s, "sessions", str(sess.get("date", "past")), summary))
            continue
        if not isinstance(items, dict):
            continue
        for key, entry in items.items():
            val = _entry_value(entry)
            if not val:
                continue
            s = _score(words, cat, key, val) if words else 1
            if s > 0:
                rows.append((s, cat, key, val))

    if not rows:
        return (f"Nothing stored about '{query}'." if query
                else "I have not stored anything about this person yet.")

    rows.sort(key=lambda r: (-r[0], r[2]))
    lines = [f"{cat}/{_pretty(key)}: {val}" for _s, cat, key, val in rows[:max(1, limit)]]
    head  = (f"Stored facts matching '{query}':" if query
             else "Everything currently stored:")
    more  = (f"\n(+{len(rows) - len(lines)} more — search with a narrower keyword)"
             if len(rows) > len(lines) else "")
    return head + "\n" + "\n".join(lines) + more


def all_entries_for_ui() -> list[dict]:
    """Flat list for the memory panel: what JARVIS knows, and when it learned it.
    Sorted newest first so the panel opens on what changed most recently."""
    memory = load_memory()
    rows = []
    for cat, items in memory.items():
        if not isinstance(items, dict):
            continue
        for key, entry in items.items():
            val = _entry_value(entry)
            if not val:
                continue
            rows.append({
                "category": cat,
                "key":      key,
                "value":    val,
                "updated":  (entry.get("updated", "") if isinstance(entry, dict) else ""),
            })
    rows.sort(key=lambda r: (r["updated"] or "0000-00-00"), reverse=True)
    return rows

def remember(key: str, value: str, category: str = "notes") -> str:
    valid = {"identity", "preferences", "projects", "relationships", "wishes", "notes"}
    if category not in valid:
        category = "notes"
    update_memory({category: {key: {"value": value}}})
    return f"Remembered: {category}/{key} = {value}"


def forget(key: str, category: str = "notes") -> str:
    memory = load_memory()
    cat    = memory.get(category, {})
    if key in cat:
        del cat[key]
        memory[category] = cat
        save_memory(memory)
        return f"Forgotten: {category}/{key}"
    return f"Not found: {category}/{key}"


forget_memory = forget


# ── Session memory ─────────────────────────────────────────────────────────────

_SESSION_MAX = 3   # safety cap — in practice 0-1 entries after pop


def save_session_summary(summary: str, language: str = "") -> None:
    """Append a 1-2 sentence session summary to long_term.json['sessions']."""
    summary = (summary or "").strip()
    if not summary:
        return
    memory   = load_memory()
    sessions = memory.get("sessions", [])
    if not isinstance(sessions, list):
        sessions = []
    entry: dict = {
        "date":    datetime.now().strftime("%Y-%m-%d"),
        "summary": summary[:280],
    }
    if language:
        entry["language"] = language
    sessions.append(entry)
    memory["sessions"] = sessions[-_SESSION_MAX:]
    with _lock:
        MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        MEMORY_PATH.write_text(
            json.dumps(memory, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    invalidate_prompt_cache()
    print(f"[Memory] 📝 Session saved ({entry['date']}): {summary[:60]}…")


def pop_last_session() -> dict | None:
    """
    Pop + return the most recent session entry and persist (never repeated).
    Safe: backup + atomic write. Empty/corrupt par None.
    """
    with _lock:
        if not MEMORY_PATH.exists():
            return None
        try:
            memory   = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            sessions = memory.get("sessions", [])
            if not isinstance(sessions, list) or not sessions:
                return None
            last = sessions.pop()
            memory["sessions"] = sessions
            try:
                from datetime import datetime as _dt
                import shutil as _sh
                _ts = _dt.now().strftime("%Y%m%d-%H%M%S")
                _bak = MEMORY_PATH.parent / f"long_term.json.bak-{_ts}"
                _sh.copy2(str(MEMORY_PATH), str(_bak))
                _prune_memory_backups()
            except Exception:
                pass
            try:
                import tempfile as _tf
                import os as _os
                _fd, _tmp = _tf.mkstemp(dir=str(MEMORY_PATH.parent), prefix="long_term.json.tmp-")
                try:
                    with _os.fdopen(_fd, "w", encoding="utf-8") as _f:
                        json.dump(memory, _f, indent=2, ensure_ascii=False)
                    _os.replace(_tmp, MEMORY_PATH)
                except Exception:
                    try:
                        if _os.path.exists(_tmp):
                            _os.remove(_tmp)
                    except Exception:
                        pass
                    raise
            except Exception:
                MEMORY_PATH.write_text(
                    json.dumps(memory, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            invalidate_prompt_cache()
            return last
        except Exception as e:
            print(f"[Memory] ⚠️ pop_last_session error: {e}")
            return None


def get_last_session() -> dict | None:
    """Legacy read-only peek (pop nahi karta). Purane callers ke liye rakha hai, hataya nahi."""
    with _lock:
        if not MEMORY_PATH.exists():
            return None
        try:
            memory   = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            sessions = memory.get("sessions", [])
            if not isinstance(sessions, list) or not sessions:
                return None
            return sessions[-1]
        except Exception as e:
            print(f"[Memory] ⚠️ get_last_session error: {e}")
            return None


# ── Daily Activity Journaling (Permanent Second Brain) ─────────────────────────

JOURNALS_DIR = BASE_DIR / "memory" / "journals"


def log_daily_activity(user_text: str, ai_response: str = "", action_name: str = "") -> None:
    """
    Log an interaction or action to today's daily journal (memory/journals/YYYY-MM-DD.md).
    This creates an immutable second-brain activity record for remembering past days.
    """
    user_text = (user_text or "").strip()
    if not user_text:
        return
    # Ignore pure internal protocol tags
    if user_text.startswith("[STARTUP_BRIEFING]") or user_text.startswith("[PROACTIVE_CHECK]"):
        return

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%I:%M %p")
    target_file = JOURNALS_DIR / f"{date_str}.md"

    with _lock:
        try:
            JOURNALS_DIR.mkdir(parents=True, exist_ok=True)
            if not target_file.exists():
                target_file.write_text(f"# 📅 Daily Activity Journal — {date_str}\n\n", encoding="utf-8")

            entry = f"### [{time_str}]\n"
            if action_name:
                entry += f"- **Action/Tool**: `{action_name}`\n"
            entry += f"- **User**: {user_text}\n"
            if ai_response:
                ai_clean = ai_response.replace("\n", " ").strip()[:240]
                entry += f"- **Assistant**: {ai_clean}\n"
            entry += "\n"

            with open(target_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            print(f"[Journal] Error writing daily log: {e}")


# Weekday names (English + Hindi) → Python weekday() number (Mon=0..Sun=6).
_WEEKDAYS = {
    "monday": 0, "somvar": 0, "somvaar": 0,
    "tuesday": 1, "mangal": 1, "mangalvar": 1,
    "wednesday": 2, "budh": 2, "budhvar": 2,
    "thursday": 3, "guruvar": 3, "guruwar": 3, "brihaspati": 3,
    "friday": 4, "shukravar": 4, "shukrvar": 4,
    "saturday": 5, "shanivar": 5, "shanivaar": 5,
    "sunday": 6, "ravivar": 6, "ravivaar": 6, "itvar": 6,
}

# Cap concatenated multi-day output so a "last week" query can't flood the prompt.
_JOURNAL_CHARS_CAP = 4000


def _resolve_journal_dates(day_query: str) -> list[str]:
    """Resolve a natural day expression to one or more YYYY-MM-DD dates.

    Supports: today/aaj, yesterday/kal, day-before-yesterday/parso,
    'N days ago' / 'N din pehle' (N≤30), weekday names (EN+HI, most recent
    occurrence incl. today), 'last week'/'pichle hafte' (last 7 days),
    'this week'/'is hafte' (Monday..today), ISO dates. Anything else falls
    back to [yesterday] (legacy behavior preserved).
    """
    from datetime import timedelta
    now = datetime.now()
    q = (day_query or "yesterday").lower().strip()
    today = now.date()
    fmt = lambda d: d.strftime("%Y-%m-%d")

    if q in ("today", "aaj", "current", "0"):
        return [fmt(today)]
    if q in ("yesterday", "kal", "prev", "-1"):
        return [fmt(today - timedelta(days=1))]
    if q in ("day before yesterday", "day-before-yesterday", "parso", "parson"):
        return [fmt(today - timedelta(days=2))]

    m = re.search(r"(\d{1,2})\s*(days?\s*ago|din\s*(pehle|pahle))", q)
    if m:
        try:
            n = max(1, min(30, int(m.group(1))))
        except Exception:
            n = 1
        return [fmt(today - timedelta(days=n))]

    if q in ("last week", "pichle hafte", "pichhle hafte", "past week", "last 7 days"):
        return [fmt(today - timedelta(days=i)) for i in range(7, 0, -1)]
    if q in ("this week", "is hafte", "is saptah"):
        days = []
        d = today - timedelta(days=today.weekday())  # Monday
        while d <= today:
            days.append(fmt(d))
            d += timedelta(days=1)
        return days

    for name, wd in _WEEKDAYS.items():
        if name in q:
            back = (today.weekday() - wd) % 7  # 0 when today IS that weekday
            return [fmt(today - timedelta(days=back))]

    m = re.search(r"\d{4}-\d{2}-\d{2}", q)
    if m:
        return [m.group(0)]
    return [fmt(today - timedelta(days=1))]


def get_daily_journal(day_query: str = "yesterday") -> str:
    """
    Read the markdown journal for a day expression — 'today', 'yesterday',
    'parso'/'day before yesterday', '3 days ago'/'3 din pehle', weekday names
    (EN+HI), 'last week'/'this week', or a specific YYYY-MM-DD.
    Multi-day queries are concatenated (capped) oldest-first.
    """
    q = (day_query or "yesterday").strip()
    dates = _resolve_journal_dates(q)
    chunks: list[str] = []
    missing: list[str] = []
    used = 0
    for target_date in dates:
        target_file = JOURNALS_DIR / f"{target_date}.md"
        if not target_file.exists():
            missing.append(target_date)
            continue
        try:
            content = target_file.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading journal for {target_date}: {e}"
        block = f"--- Activity Log for {target_date} ---\n{content}"
        if used + len(block) > _JOURNAL_CHARS_CAP and chunks:
            chunks.append(f"\n[… output capped at {_JOURNAL_CHARS_CAP} chars — ask for a narrower day …]")
            break
        chunks.append(block)
        used += len(block)

    if not chunks:
        if len(dates) == 1:
            return (f"No activity log found for {dates[0]} ({q}). "
                    f"The assistant was either not active or nothing was recorded.")
        return (f"No activity logs found for {', '.join(dates)}. "
                f"The assistant was either not active or nothing was recorded.")
    out = "\n".join(chunks)
    if missing and len(dates) > 1:
        out += f"\n(No logs for: {', '.join(missing)})"
    return out


def recall_past_activities(day: str = "yesterday") -> str:
    """
    Tool called by the model to look up what the user or assistant did on a past day(s).
    """
    return get_daily_journal(day)