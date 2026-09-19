"""Additive KG-1 tests (unique entity names + cleanup, user graph untouched)."""
import json
from pathlib import Path

_GF = Path("config/knowledge_graph.json")
_TAG = "pytestkg"


def _purge():
    try:
        if _GF.exists():
            g = json.loads(_GF.read_text(encoding="utf-8"))
            g["nodes"] = {k: v for k, v in g.get("nodes", {}).items() if _TAG not in k}
            g["edges"] = [e for e in g.get("edges", [])
                           if not any(_TAG in str(x) for x in e)]
            _GF.write_text(json.dumps(g, indent=1, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def test_extract_triples():
    from memory.knowledge_graph import extract_triples
    ts = extract_triples("relationships", f"{_TAG}_sister", "Asha")
    assert any(r == "sister" for _, r, _ in ts), ts
    ts2 = extract_triples("preferences", "favorite_food", "pizza")
    assert any(r == "likes" for _, r, _ in ts2), ts2


def test_walk_two_hop():
    from memory import knowledge_graph as _kg
    _purge()
    assert _kg.add_triple(f"{_TAG}_a", "sister", f"{_TAG}_b")
    assert _kg.add_triple(f"{_TAG}_b", "likes", "coffee")
    lines = _kg.walk(f"{_TAG}_a", depth=2)
    assert any(_TAG in ln for ln in lines), lines
    assert any("coffee" in ln for ln in lines), lines
    _purge()


def test_shortest_path():
    from memory import knowledge_graph as _kg
    _purge()
    _kg.add_triple(f"{_TAG}_x", "friend", f"{_TAG}_y")
    _kg.add_triple(f"{_TAG}_y", "works_on", f"{_TAG}_proj")
    path = _kg.shortest_path(f"{_TAG}_x", f"{_TAG}_proj")
    assert len(path) == 2, path
    _purge()


def test_kg_query_shape_and_stats():
    from actions.kg_query import kg_query, TOOL
    assert TOOL["name"] == "kg_query" and callable(TOOL["handler"])
    out = kg_query({"action": "stats"})
    assert "entities" in out
    out2 = kg_query({"action": "ask", "query": f"{_TAG}_nobody_xyz"})
    assert isinstance(out2, str) and len(out2) > 0
    _purge()


def test_router_kg_gating():
    """Known entity -> kg_query; unknown/celebrity/task purane raste (bina hataye)."""
    from core.edge_router import NeedleToolRouter
    from memory import knowledge_graph as _kg
    _purge()
    _kg.add_triple(f"{_TAG}_mom", "likes", "bhajan")
    r = NeedleToolRouter()
    got = r.classify_tool_intent(f"{_TAG}_mom ko kya pasand hai")
    assert got is not None and got[0] == "kg_query", got
    assert r.classify_tool_intent("kaun hai modi")[0] == "web_search"
    t = r.classify_tool_intent("yaad rakhna kal meeting hai")
    assert t is not None and t[0] == "tinydb_memory", t
    _purge()
