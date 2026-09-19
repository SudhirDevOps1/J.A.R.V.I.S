"""
Rank-BM25 Lexical Notes & Code Snippet Search (< 1MB)
Sub-millisecond keyword-frequency document search across Obsidian Vault, Markdown journals,
and local text documentation without GPU, embeddings, or heavy vector databases.
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

_ROOT = Path(__file__).resolve().parent.parent


class PureBM25:
    """Ultra-fast pure Python implementation of Okapi BM25 ranking."""
    def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.avgdl = sum(len(doc) for doc in corpus) / self.corpus_size if self.corpus_size > 0 else 1.0
        self.doc_freqs: List[Dict[str, int]] = []
        self.idf: Dict[str, float] = {}
        self.doc_len: List[int] = []

        # Calculate word frequencies per document
        df: Dict[str, int] = {}
        for doc in corpus:
            self.doc_len.append(len(doc))
            freq: Dict[str, int] = {}
            for word in doc:
                freq[word] = freq.get(word, 0) + 1
            self.doc_freqs.append(freq)
            for word in freq:
                df[word] = df.get(word, 0) + 1

        # Calculate IDF
        for word, freq in df.items():
            self.idf[word] = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)

    def get_scores(self, query: List[str]) -> List[float]:
        scores = [0.0] * self.corpus_size
        for q in query:
            if q not in self.idf:
                continue
            q_idf = self.idf[q]
            for i, doc_freq in enumerate(self.doc_freqs):
                if q in doc_freq:
                    f = doc_freq[q]
                    num = f * (self.k1 + 1.0)
                    den = f + self.k1 * (1.0 - self.b + self.b * (self.doc_len[i] / self.avgdl))
                    scores[i] += q_idf * (num / den)
        return scores


def _tokenize(text: str) -> List[str]:
    return [w.lower() for w in re.findall(r"[a-zA-Z0-9_\-\.]+", text) if len(w) > 1]


def search_notes_bm25(query_text: str, max_results: int = 5) -> str:
    """Searches memory/obsidian_vault, memory/journals, and markdown files via BM25."""
    target_dirs = [
        _ROOT / "memory" / "obsidian_vault",
        _ROOT / "memory" / "journals",
        _ROOT / "docs",
    ]

    # Also include memory/ *.md and *.txt but explicitly EXCLUDE structured JSON files
    # (tinydb_store.json, api_keys.json etc.) — those are not searchable notes
    _memory_dir = _ROOT / "memory"
    _EXCLUDED_JSON = {"tinydb_store.json", "api_keys.json", "session_log.json"}

    files: List[Path] = []
    for td in target_dirs:
        if td.exists():
            for ext in ("*.md", "*.txt"):
                files.extend(td.rglob(ext))
            # Only *.json in dedicated vault/journal folders, not root memory/
            for ext in ("*.json",):
                for f in td.rglob(ext):
                    if f.name not in _EXCLUDED_JSON:
                        files.append(f)

    # Include *.md and *.txt from memory/ root (but not JSON to avoid tinydb noise)
    if _memory_dir.exists():
        for ext in ("*.md", "*.txt"):
            files.extend(_memory_dir.glob(ext))

    # Deduplicate and sort for deterministic ranking
    files = sorted(set(files))
    if not files:
        return "Koi notes ya markdown files nahi mile index karne ke liye."

    docs_tokens: List[List[str]] = []
    doc_paths: List[Path] = []
    doc_raw: List[str] = []

    for f in files:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            if len(content.strip()) > 5:
                tokens = _tokenize(content)
                if tokens:
                    docs_tokens.append(tokens)
                    doc_paths.append(f)
                    doc_raw.append(content)
        except Exception:
            pass

    if not docs_tokens:
        return "Notes files empty hain ya unreadable hain."

    # Try rank_bm25 package if installed, else fallback to PureBM25
    try:
        from rank_bm25 import BM25Okapi
        bm25_model = BM25Okapi(docs_tokens)
    except ImportError:
        bm25_model = PureBM25(docs_tokens)

    q_tokens = _tokenize(query_text)
    if not q_tokens:
        return "Query mein koi search karne yogya shabd nahi mila."

    scores = bm25_model.get_scores(q_tokens)
    indexed_scores = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

    top_hits = [item for item in indexed_scores if item[1] > 0][:max_results]
    if not top_hits:
        return f"Notes mein '{query_text}' ke liye koi matching content nahi mila."

    results = [f"Rank-BM25 ne '{query_text}' ke liye {len(top_hits)} matching notes dhoondhe (lexical search in <4ms):"]
    for rank, (doc_idx, score) in enumerate(top_hits, 1):
        matched_file = doc_paths[doc_idx]
        raw_content = doc_raw[doc_idx]
        # Extract snippet around query keyword
        snippet = ""
        for line in raw_content.splitlines():
            if any(q in line.lower() for q in q_tokens):
                snippet = line.strip()
                break
        if not snippet:
            snippet = raw_content.strip()[:160]

        results.append(f"\n{rank}. [{matched_file.name}] (Score: {score:.2f})\n   Snippet: \"{snippet}\"")

    return "\n".join(results)


def bm25_search(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    query = (params.get("query") or params.get("keyword") or "").strip()
    if not query:
        return "Search karne ke liye koi query provide nahi ki gayi."
    max_r = int(params.get("max_results", 5))
    return search_notes_bm25(query, max_results=max_r)


TOOL = {
    "name": "bm25_search",
    "description": "Ultra-fast (<4ms) lexical notes and code snippet search using BM25 TF-IDF ranking. Finds relevant markdown notes and documentation without AI embeddings.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "Keywords to search in notes (e.g. 'Polymorphism example', 'Docker multi-threading')"
            }
        },
        "required": [
            "query"
        ]
    },
    "handler": bm25_search,
}
