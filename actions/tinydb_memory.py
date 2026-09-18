"""
TinyDB NoSQL Persistent Memory & Task Reminders (< 1MB)
Structured, zero-server document store for developer tasks, user reminders, and learned facts.
Includes pure-Python JSON fallback engine if tinydb package is not installed.
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_STORE_FILE = Path(__file__).resolve().parent.parent / "memory" / "tinydb_store.json"

try:
    from tinydb import TinyDB, Query
    _HAS_TINYDB = True
except ImportError:
    _HAS_TINYDB = False


class _SimpleNoSQL:
    """Lightweight pure-Python NoSQL engine matching TinyDB API with zero external dependencies."""
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, List[Dict[str, Any]]] = {}
        self._load()

    def _load(self):
        if self.file_path.exists():
            try:
                self._data = json.loads(self.file_path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def _save(self):
        try:
            self.file_path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[TinyDB] Save note: {e}")

    def table(self, name: str):
        return _SimpleTable(self, name)


class _SimpleTable:
    def __init__(self, db: _SimpleNoSQL, name: str):
        self.db = db
        self.name = name
        if self.name not in self.db._data:
            self.db._data[self.name] = []

    def insert(self, doc: Dict[str, Any]) -> int:
        doc_id = len(self.db._data[self.name]) + 1
        doc["_id"] = doc_id
        doc["_created_at"] = datetime.now().isoformat()
        self.db._data[self.name].append(doc)
        self.db._save()
        return doc_id

    def all(self) -> List[Dict[str, Any]]:
        return list(self.db._data.get(self.name, []))

    def search_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        kw = keyword.lower().strip()
        results = []
        for doc in self.all():
            doc_str = json.dumps(doc).lower()
            if kw in doc_str:
                results.append(doc)
        return results

    def remove_by_id(self, doc_id: int) -> bool:
        items = self.db._data.get(self.name, [])
        initial_len = len(items)
        self.db._data[self.name] = [d for d in items if d.get("_id") != doc_id]
        if len(self.db._data[self.name]) != initial_len:
            self.db._save()
            return True
        return False


def _get_db():
    _STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _HAS_TINYDB:
        return TinyDB(str(_STORE_FILE))
    return _SimpleNoSQL(_STORE_FILE)


def add_task_reminder(task: str, due: str = "soon", category: str = "general") -> str:
    """Save a task/reminder to TinyDB."""
    db = _get_db()
    if _HAS_TINYDB:
        table = db.table("tasks")
        doc_id = table.insert({
            "task": task,
            "due": due,
            "category": category,
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
    else:
        table = db.table("tasks")
        doc_id = table.insert({
            "task": task,
            "due": due,
            "category": category,
            "status": "pending",
        })
    return f"Task note #{doc_id} yaad rakh liya gaya hai: '{task}' (Due: {due})."


def get_pending_tasks() -> str:
    """Retrieve all pending tasks from TinyDB."""
    db = _get_db()
    table = db.table("tasks")
    tasks = table.all()
    pending = [t for t in tasks if t.get("status") == "pending"]
    if not pending:
        return "Abhi koi pending task ya reminder nahi hai, sir! Sab clear hai."
    
    lines = [f"Aapke {len(pending)} pending tasks hain:"]
    for i, t in enumerate(pending, 1):
        due_str = f" [Due: {t.get('due')}]" if t.get('due') else ""
        lines.append(f"{i}. {t.get('task')}{due_str}")
    return "\n".join(lines)


def tinydb_memory(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "add").strip().lower()
    task_text = params.get("task") or params.get("text") or params.get("note") or ""

    if action in ("list", "get", "show", "pending"):
        return get_pending_tasks()

    if not task_text:
        return "Koi task ya note specify nahi kiya gaya."

    due = params.get("due", "kal")
    cat = params.get("category", "study" if "revise" in task_text.lower() else "general")
    return add_task_reminder(task_text, due, cat)


TOOL = {
    "name": "tinydb_memory",
    "description": "Structured NoSQL memory for saving reminders, study tasks, and revision goals in TinyDB. Zero-server, persistent across restarts.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'add' to record a task/reminder, 'list' or 'pending' to view active tasks."
            },
            "task": {
                "type": "STRING",
                "description": "Details of what to remember (e.g. 'kal Java multi-threading concepts revise karne hain')"
            },
            "due": {
                "type": "STRING",
                "description": "Optional deadline or time (e.g. 'kal shaam 6 baje', 'tomorrow')"
            }
        },
        "required": [
            "action"
        ]
    },
    "handler": tinydb_memory,
}
