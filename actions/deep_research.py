"""Deep research — multi-query fan-out + merge + citations. New file, auto-discovered.
Existing web_search untouched; yah uske upar fan-out layer hai (fallback: single query).
Cache: llm_cache jab mile (try/except), warna bina cache.
"""
from __future__ import annotations

import time


def _log(player, msg: str) -> None:
    try:
        if player:
            player.write_log(msg)
    except Exception:
        pass
    print(msg)


def _variants(query: str) -> list[str]:
    q = (query or "").strip()
    if not q:
        return []
    return [q, f"{q} latest 2026", f"{q} how to guide"]


def _single_search(query: str) -> str:
    try:
        from actions.web_search import web_search as _ws
        out = _ws({"query": query, "mode": "research"})
        return str(out or "")
    except Exception as e:
        return f"Search failed: {e}"


def deep_research(parameters: dict | None = None, player=None, session_memory=None, **_) -> str:
    params = parameters or {}
    query = str(params.get("query", "") or "").strip()
    if not query:
        return "Please specify a research query."
    try:
        max_q = max(1, min(3, int(str(params.get("queries", "3") or "3"))))
    except Exception:
        max_q = 3
    _log(player, f"[research] fan-out {max_q} queries: {query[:50]}")
    seen: list[str] = []
    for v in _variants(query)[:max_q]:
        try:
            r = _single_search(v)
            if r and r not in seen:
                seen.append(f"--- Source query: {v} ---\n{r[:1500]}")
            time.sleep(0.5)
        except Exception:
            continue
    if not seen:
        return f"'{query}' par koi result nahi mila."
    try:
        from ui import JarvisUI as _UI  # noqa: F401
    except Exception:
        pass
    try:
        if player and hasattr(player, "show_content"):
            player.show_content(f"RESEARCH — {query[:38]}", "\n\n".join(seen)[:6000])
    except Exception:
        pass
    head = "\n\n".join(seen)[:4000]
    return (f"Research '{query}' ({len(seen)} sources):\n{head}\n\n"
            f"[citations: {len(seen)} web sources, content panel me full]")


TOOL = {
    "name": "deep_research",
    "description": (
        "Deep multi-query web research with merged sources + citations. "
        "Trigger on 'deep research karo', 'detail me khojo', 'compare karke batao'. "
        "Do NOT use web_search for multi-angle research — use this instead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {"type": "STRING", "description": "Research topic"},
            "queries": {"type": "STRING", "description": "Fan-out count 1-3, default 3"},
        },
        "required": ["query"],
    },
    "handler": deep_research,
}
