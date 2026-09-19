"""Knowledge Graph — entities + relationships over existing memory. New file, additive.
Zero-dep (stdlib only), <5ms queries. Purana memory format untouched — graph UPAR banta hai.

Store: config/knowledge_graph.json {nodes: {id: {type, label}}, edges: [[src, rel, dst]]}
Ingest: save_memory hook (regex triples, NO LLM) + contacts lazy ingest.
Recall: BFS 2-hop walk + lexical fallback = research-backed hybrid.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

_GRAPH_FILE = Path(__file__).resolve().parent.parent / "config" / "knowledge_graph.json"
_MAX_EDGES = 5000
_lock = threading.Lock()
_contacts_ingested = False

# relation normalizer: varied phrasing -> canonical edge label
_REL_PATTERNS = (
    (r"\b(older sister|elder sister|sister)\b", "sister"),
    (r"\b(older brother|elder brother|brother)\b", "brother"),
    (r"\b(mother|mom|mum|mummy|maa)\b", "mother"),
    (r"\b(father|dad|papa|daddy)\b", "father"),
    (r"\b(wife|partner|girlfriend)\b", "partner"),
    (r"\b(friend|best friend|dost)\b", "friend"),
    (r"\b(colleague|coworker|boss|manager)\b", "colleague"),
    (r"\b(likes?|loves?|pasand|favourite|favorite)\b", "likes"),
    (r"\b(dislikes?|hates?|napasand)\b", "dislikes"),
    (r"\b(works?\s+(?:on|at|for)|working on|kaam (?:karta|karti) (?:hai|par))\b", "works_on"),
    (r"\b(lives?\s+in|rehta|rehti|lives)\b", "lives_in"),
    (r"\b(studies|studying|padhta|padhti)\b", "studies"),
    (r"\b(plays?|khelta|khelti)\b", "plays"),
)


def _norm(name: str) -> str:
    n = re.sub(r"[^a-zA-Z0-9\u0900-\u097F ]", " ", str(name or "")).strip().lower()
    n = re.sub(r"\s+", "_", n)
    return n[:60]


def _load() -> dict:
    try:
        if _GRAPH_FILE.exists():
            data = json.loads(_GRAPH_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("nodes", {})
                data.setdefault("edges", [])
                return data
    except Exception:
        pass
    return {"nodes": {}, "edges": []}


def _save(g: dict) -> None:
    try:
        _GRAPH_FILE.parent.mkdir(parents=True, exist_ok=True)
        g["edges"] = g.get("edges", [])[-_MAX_EDGES:]
        _tmp = _GRAPH_FILE.with_suffix(".json.tmp")
        _tmp.write_text(json.dumps(g, indent=1, ensure_ascii=False), encoding="utf-8")
        import os as _os
        _os.replace(str(_tmp), str(_GRAPH_FILE))
    except Exception:
        pass


def add_triple(subj: str, rel: str, obj: str, subj_type: str = "entity") -> bool:
    """Ek edge jodo (dedupe). Never raises."""
    try:
        s, r, o = _norm(subj), _norm(rel), _norm(obj)
        if not s or not r or not o or s == o:
            return False
        with _lock:
            g = _load()
            g["nodes"].setdefault(s, {"type": subj_type, "label": s})
            g["nodes"].setdefault(o, {"type": "entity", "label": o})
            if [s, r, o] not in g["edges"]:
                g["edges"].append([s, r, o])
            _save(g)
        return True
    except Exception:
        return False


def neighbors(name: str, rel: str | None = None, limit: int = 10) -> list[tuple[str, str]]:
    """1-hop: [(relation, node)]. Never raises."""
    try:
        n = _norm(name)
        out = []
        with _lock:
            g = _load()
            for s, r, o in g.get("edges", []):
                if s == n and (rel is None or r == _norm(rel)):
                    out.append((r, o))
                elif o == n and (rel is None or r == _norm(rel)):
                    out.append((f"{r} (incoming)", s))
                if len(out) >= limit:
                    break
        return out
    except Exception:
        return []


def walk(name: str, depth: int = 2, limit: int = 15) -> list[str]:
    """BFS 2-hop readable lines: 'aarav --sister--> ayse'. Never raises."""
    try:
        start = _norm(name)
        with _lock:
            g = _load()
            edges = list(g.get("edges", []))
        seen = {start}
        frontier = [start]
        lines: list[str] = []
        for _ in range(max(1, min(3, depth))):
            nxt = []
            for node in frontier:
                for s, r, o in edges:
                    if s == node and o not in seen:
                        seen.add(o)
                        nxt.append(o)
                        lines.append(f"{s} --{r}--> {o}")
                    elif o == node and s not in seen:
                        seen.add(s)
                        nxt.append(s)
                        lines.append(f"{s} --{r}--> {o}")
                    if len(lines) >= limit:
                        return lines
            frontier = nxt
            if not frontier:
                break
        return lines
    except Exception:
        return []


def shortest_path(a: str, b: str) -> list[str]:
    """A se B tak path (BFS). Never raises."""
    try:
        src, dst = _norm(a), _norm(b)
        with _lock:
            g = _load()
            edges = list(g.get("edges", []))
        adj: dict[str, list[tuple[str, str]]] = {}
        for s, r, o in edges:
            adj.setdefault(s, []).append((r, o))
            adj.setdefault(o, []).append((f"{r} (incoming)", s))
        prev: dict[str, tuple[str, str]] = {src: ("", "")}
        queue = [src]
        while queue:
            cur = queue.pop(0)
            if cur == dst:
                break
            for r, nxt in adj.get(cur, []):
                if nxt not in prev:
                    prev[nxt] = (cur, r)
                    queue.append(nxt)
        if dst not in prev:
            return []
        path, cur = [], dst
        while cur != src:
            p, r = prev[cur]
            path.append(f"{p} --{r}--> {cur}")
            cur = p
        return list(reversed(path))
    except Exception:
        return []


def extract_triples(category: str, key: str, value: str) -> list[tuple[str, str, str]]:
    """save_memory entry -> triples (regex, NO LLM). Never raises."""
    out: list[tuple[str, str, str]] = []
    try:
        cat = (category or "").lower().strip()
        k = _norm(key)
        v = str(value or "").strip()
        if not k or not v:
            return out
        # relationships category: key=ayse_sister value=Ayşe -> person edges.
        # NOTE: raw key (spaces) par match karo — _norm underscores \b todata hai.
        if cat == "relationships":
            k_raw = re.sub(r"[_]+", " ", str(key or "")).strip().lower()
            for pat, rel in _REL_PATTERNS[:7]:
                if re.search(pat, k_raw):
                    person = re.sub(pat, "", k_raw).strip(" _") or "someone"
                    out.append((_norm(person) or "someone", rel, _norm(v) or v.lower()))
                    break
            else:
                out.append((_norm(v) or v.lower(), "related_to", k))
        # preferences: key=favorite_food value=pizza -> (user --likes--> pizza)
        if cat == "preferences":
            k_raw = re.sub(r"[_]+", " ", str(key or "")).strip().lower()
            for pat, rel in _REL_PATTERNS[7:9]:
                if re.search(pat, k_raw):
                    thing = re.sub(pat, "", k_raw).strip(" _") or v.lower()
                    out.append(("user", rel, _norm(thing) or _norm(v)))
                    break
        # value text me relation: "Aarav's sister" / "works at Google"
        low = v.lower()
        m = re.search(r"([a-z]+)'s\s+(sister|brother|mother|father|wife|friend)", low)
        if m:
            out.append((_norm(m.group(1)), m.group(2), k if k != _norm(m.group(1)) else "user"))
        m = re.search(r"works?\s+(?:on|at|for)\s+([a-z0-9 _]+)", low)
        if m:
            out.append((k, "works_on", _norm(m.group(1))))
        m = re.search(r"likes?\s+([a-z0-9 _]+)", low)
        if m and cat != "preferences":
            out.append((k, "likes", _norm(m.group(1))))
    except Exception:
        pass
    # dedupe preserve order
    seen, uniq = set(), []
    for t in out:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq[:8]


def ingest_memory_update(memory_update: dict) -> int:
    """update_memory hook: {category: {key: {value}}} -> triples. Returns count. Never raises."""
    n = 0
    try:
        if not isinstance(memory_update, dict):
            return 0
        for cat, entries in memory_update.items():
            if not isinstance(entries, dict):
                continue
            for key, entry in entries.items():
                val = entry.get("value", "") if isinstance(entry, dict) else str(entry or "")
                for s, r, o in extract_triples(str(cat), str(key), str(val)):
                    if add_triple(s, r, o):
                        n += 1
    except Exception:
        pass
    return n


def ingest_contacts(force: bool = False) -> int:
    """contacts.json -> (name --has_phone--> digits) + platform. Once per process. Never raises."""
    global _contacts_ingested
    if _contacts_ingested and not force:
        return 0
    _contacts_ingested = True
    n = 0
    try:
        from memory import contacts as _cb
        for name in _cb.list_contacts():
            hit = _cb.resolve_contact(name)
            if hit.get("phone") and add_triple(name, "has_phone", hit["phone"], "person"):
                n += 1
            if add_triple(name, "contact_via", hit.get("platform", "whatsapp"), "person"):
                n += 1
    except Exception:
        pass
    return n


def stats() -> dict:
    """Graph size. Never raises."""
    try:
        with _lock:
            g = _load()
        return {"nodes": len(g.get("nodes", {})), "edges": len(g.get("edges", []))}
    except Exception:
        return {"nodes": 0, "edges": 0}


# ── KG-2: PageRank centrality + optional Kuzu backend (additive) ─────────────

def pagerank(top: int = 5, iters: int = 20, damping: float = 0.85) -> list[tuple[str, float]]:
    """Pure-Python PageRank over undirected graph view. [(node, score)]. Never raises."""
    try:
        with _lock:
            g = _load()
            edges = list(g.get("edges", []))
            nodes = list(g.get("nodes", {}).keys())
        if not nodes:
            return []
        adj: dict[str, set[str]] = {n: set() for n in nodes}
        for s, _, o in edges:
            if s in adj and o in adj and s != o:
                adj[s].add(o)
                adj[o].add(s)
        n = len(nodes)
        rank = {x: 1.0 / n for x in nodes}
        for _ in range(max(1, min(50, iters))):
            new = {}
            for x in nodes:
                s = 0.0
                for y in nodes:
                    if x in adj.get(y, ()): 
                        deg = len(adj[y]) or 1
                        s += rank[y] / deg
                new[x] = (1.0 - damping) / n + damping * s
            rank = new
        return sorted(rank.items(), key=lambda kv: kv[1], reverse=True)[:max(1, top)]
    except Exception:
        return []


def _kuzu():
    """Kuzu connection ya None. Sirf future swap ke liye — abhi koi call nahi karta,
    isliye koi DB file nahi banti. Never raises."""
    try:
        import importlib.util as _u
        if _u.find_spec("kuzu") is None:
            return None
        import kuzu as _k
        _dbf = str(_GRAPH_FILE.with_suffix(".kuzu"))
        db = _k.Database(_dbf)
        return _k.Connection(db)
    except Exception:
        return None


def backend() -> str:
    """'kuzu' agar pip-installed, warna 'json'. Side-effect free (sirf spec check)."""
    try:
        import importlib.util as _u
        return "kuzu" if _u.find_spec("kuzu") is not None else "json"
    except Exception:
        return "json"
