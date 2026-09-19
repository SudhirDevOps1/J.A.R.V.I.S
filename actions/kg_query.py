"""Knowledge Graph queries — 2-hop relationship recall + lexical fallback (hybrid).
New file, auto-discovered. recall_memory untouched — yah uska graph wala bhai hai.
"""
from __future__ import annotations

import re


def _log(player, msg: str) -> None:
    try:
        if player:
            player.write_log(msg)
    except Exception:
        pass
    print(msg)


def _entities(text: str) -> list[str]:
    """Query se candidate entity names (capitalized + multiword). Never raises."""
    try:
        words = re.findall(r"[A-Za-z\u0900-\u097F]{3,}(?:\s+[A-Za-z\u0900-\u097F]{3,})?", text or "")
        stop = {"what", "who", "does", "like", "likes", "kya", "kaun", "kaunsi", "hai",
                "karta", "karti", "karti", "the", "and", "ko", "ki", "ka", "mein", "me",
                "sister", "brother", "mother", "father", "wife", "friend"}
        out = []
        for w in words:
            wl = w.lower().strip()
            if wl not in stop and wl not in out:
                out.append(wl)
        return out[:4]
    except Exception:
        return []


def kg_query(parameters: dict | None = None, player=None, session_memory=None, **_) -> str:
    from memory import knowledge_graph as _kg
    params = parameters or {}
    action = str(params.get("action", "ask") or "ask").lower().strip()
    q = str(params.get("query", params.get("question", "")) or "").strip()

    # contacts lazy ingest (once per process, additive)
    try:
        _kg.ingest_contacts()
    except Exception:
        pass

    if action in ("stats", "status"):
        s = _kg.stats()
        out = f"Knowledge graph: {s['nodes']} entities, {s['edges']} relations (backend: {_kg.backend()})."
        # ADDITIVE KG-2: sabse important entities (PageRank) — purani stats line same
        try:
            top = _kg.pagerank(top=3)
            if top:
                out += "\nTop: " + ", ".join(f"{n} ({sc:.2f})" for n, sc in top)
        except Exception:
            pass
        return out

    if action in ("top", "important", "central"):
        # ADDITIVE KG-2: central entities
        try:
            top = _kg.pagerank(top=5)
        except Exception:
            top = []
        if not top:
            return "Graph khali hai — pehle kuch yaad karao."
        return "Important entities:\n" + "\n".join(f"{i+1}. {n}" for i, (n, _) in enumerate(top))

    if action in ("neighbors", "padosi"):
        if not q:
            return "Kiska rishta dekhun? Naam bolo."
        nbs = _kg.neighbors(q, limit=10)
        if not nbs:
            return f"'{q}' graph me nahi mila."
        return f"{q} ke rishte:\n" + "\n".join(f"- {r}: {n}" for r, n in nbs)

    if action in ("path", "rasta"):
        parts = [p.strip() for p in re.split(r"\s+(?:se|to|tak|->)\s+", q) if p.strip()]
        if len(parts) < 2:
            return "'A se B tak' format me bolo."
        path = _kg.shortest_path(parts[0], parts[-1])
        if not path:
            return f"{parts[0]} se {parts[-1]} tak koi rasta nahi mila."
        return "Rasta:\n" + "\n".join(path)

    # ask: graph walk first, lexical fallback second (research hybrid)
    if not q:
        return "Kya poochna hai? (e.g. 'Aarav ki sister ko kya pasand hai?')"
    lines: list[str] = []
    for ent in _entities(q):
        w = _kg.walk(ent, depth=2, limit=6)
        lines.extend(w)
        if len(lines) >= 10:
            break
    if lines:
        seen, uniq = set(), []
        for ln in lines:
            if ln not in seen:
                seen.add(ln)
                uniq.append(ln)
        _log(player, f"[kg] {len(uniq)} relations")
        return "Graph se mila:\n" + "\n".join(f"- {u}" for u in uniq[:10])
    # fallback: existing lexical search (purana flow reuse, kuch naya overwrite nahi)
    try:
        from memory.memory_manager import search_memory
        return search_memory(q, limit=8)
    except Exception as e:
        return f"Graph me nahi mila, search bhi fail: {e}"


TOOL = {
    "name": "kg_query",
    "description": (
        "Answer relationship questions via knowledge graph (2-hop walk) with lexical "
        "fallback. Trigger on 'X ka Y se kya rishta', 'X ko kya pasand', 'kaun hai X'. "
        "Do NOT use recall_memory for relationship chains — use this instead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "ask | neighbors | path | stats"},
            "query": {"type": "STRING", "description": "Question or entity name"},
        },
        "required": ["action"],
    },
    "handler": kg_query,
}
