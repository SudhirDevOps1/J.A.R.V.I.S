"""Additive KG-2 tests (unique names + cleanup)."""
import json
from pathlib import Path

_GF = Path("config/knowledge_graph.json")
_TAG = "pytestkg2"


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


def test_pagerank_star_center_wins():
    from memory import knowledge_graph as _kg
    _purge()
    for leaf in ("l1", "l2", "l3"):
        _kg.add_triple(f"{_TAG}_hub", "friend", f"{_TAG}_{leaf}")
    top = _kg.pagerank(top=3)
    assert top and top[0][0] == f"{_TAG}_hub", top
    _purge()


def test_backend_json_no_side_effect():
    from memory import knowledge_graph as _kg
    assert _kg.backend() == "json"
    assert _kg._kuzu() is None
    assert not _GF.with_suffix(".kuzu").exists()


def test_top_action():
    from actions.kg_query import kg_query
    out = kg_query({"action": "top"})
    assert isinstance(out, str) and len(out) > 0
    out2 = kg_query({"action": "stats"})
    assert "backend:" in out2
    _purge()
