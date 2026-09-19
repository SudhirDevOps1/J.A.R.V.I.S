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
                raw = json.loads(self.file_path.read_text(encoding="utf-8"))
                # Handle both list-format and dict-format tables (normalize to list)
                normalized = {}
                for tbl, tbl_data in raw.items():
                    if isinstance(tbl_data, list):
                        normalized[tbl] = tbl_data
                    elif isinstance(tbl_data, dict):
                        # TinyDB native dict format → convert back to list
                        normalized[tbl] = list(tbl_data.values())
                    else:
                        normalized[tbl] = []
                self._data = normalized
            except Exception:
                self._data = {}

    def _save(self):
        try:
            save_data = {}
            for tbl_name, items in self._data.items():
                if isinstance(items, list):
                    save_data[tbl_name] = {
                        str(d.get("_id", i + 1)): d
                        for i, d in enumerate(items)
                        if isinstance(d, dict)
                    }
                elif isinstance(items, dict):
                    save_data[tbl_name] = items
                else:
                    save_data[tbl_name] = {}
            self.file_path.write_text(json.dumps(save_data, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[TinyDB] Save error: {e}")

    def table(self, name: str):
        return _SimpleTable(self, name)

    def close(self):
        pass  # No-op for compatibility with TinyDB API


class _SimpleTable:
    def __init__(self, db: _SimpleNoSQL, name: str):
        self.db = db
        self.name = name
        if self.name not in self.db._data:
            self.db._data[self.name] = []

    def insert(self, doc: Dict[str, Any]) -> int:
        # FIX: Use max(_id) + 1 to avoid collision after deletions
        existing = self.db._data.get(self.name, [])
        existing_ids = [d.get("_id", 0) for d in existing if isinstance(d, dict)]
        doc_id = (max(existing_ids) if existing_ids else 0) + 1
        doc["_id"] = doc_id
        doc["_created_at"] = datetime.now().isoformat()
        self.db._data[self.name].append(doc)
        self.db._save()
        return doc_id

    def all(self) -> List[Dict[str, Any]]:
        data = self.db._data.get(self.name, [])
        # Filter out any non-dict entries (safety guard)
        return [d for d in data if isinstance(d, dict)]

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

    def update_by_id(self, doc_id: int, fields: dict) -> bool:
        items = self.db._data.get(self.name, [])
        for d in items:
            if isinstance(d, dict) and d.get("_id") == doc_id:
                d.update(fields)
                self.db._save()
                return True
        return False


def _normalize_tinydb_file():
    """Ensure tinydb_store.json uses dictionary-backed tables for TinyDB compatibility."""
    if not _STORE_FILE.exists():
        return
    try:
        content = _STORE_FILE.read_text(encoding="utf-8").strip()
        if not content:
            _STORE_FILE.write_text("{}", encoding="utf-8")
            return
        raw = json.loads(content)
        if not isinstance(raw, dict):
            _STORE_FILE.write_text("{}", encoding="utf-8")
            return
        modified = False
        for tbl_name, tbl_data in list(raw.items()):
            if isinstance(tbl_data, list):
                # TinyDB requires dict keyed by doc_id string
                tbl_dict = {}
                for idx, item in enumerate(tbl_data, 1):
                    if isinstance(item, dict):
                        doc_id = str(item.get("_id", idx))
                        item["_id"] = int(doc_id) if str(doc_id).isdigit() else idx
                        tbl_dict[doc_id] = item
                raw[tbl_name] = tbl_dict
                modified = True
            elif isinstance(tbl_data, dict):
                # Ensure dict items have _id
                for k, v in tbl_data.items():
                    if isinstance(v, dict) and "_id" not in v and str(k).isdigit():
                        v["_id"] = int(k)
                        modified = True
        if modified:
            _STORE_FILE.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    except Exception:
        try:
            _STORE_FILE.write_text("{}", encoding="utf-8")
        except Exception:
            pass


def _get_db():
    _STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _normalize_tinydb_file()
    if _HAS_TINYDB:
        return TinyDB(str(_STORE_FILE))
    return _SimpleNoSQL(_STORE_FILE)

get_db = _get_db


def add_task_reminder(task: str, due: str = "soon", category: str = "general") -> str:
    """Save a task/reminder to TinyDB."""
    db = _get_db()
    try:
        table = db.table("tasks")
        doc_data = {
            "task": task,
            "due": due,
            "category": category,
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        doc_id = table.insert(doc_data)
        if _HAS_TINYDB:
            table.update({"_id": doc_id}, doc_ids=[doc_id])
        return f"✅ Task #{doc_id} yaad rakh liya: '{task}' (Due: {due}). 'tasks list karo' se dekh sakte ho."
    finally:
        if _HAS_TINYDB:
            db.close()


def get_pending_tasks() -> str:
    """Retrieve all pending tasks from TinyDB."""
    db = _get_db()
    try:
        table = db.table("tasks")
        tasks = table.all()
        pending = [t for t in tasks if t.get("status") == "pending"]
        if not pending:
            return "✅ Abhi koi pending task ya reminder nahi hai! Sab clear hai."

        lines = [f"📋 Aapke {len(pending)} pending tasks:"]
        for t in pending:
            tid = t.get("_id", "?")
            due_str = f" 📅 {t.get('due')}" if t.get("due") and t.get("due") != "soon" else ""
            cat_str = f" [{t.get('category', 'general')}]" if t.get("category") not in ("general", None) else ""
            lines.append(f"  #{tid}{cat_str} {t.get('task')}{due_str}")
        lines.append("\n💡 Complete karne ke liye: 'task #ID complete karo'")
        return "\n".join(lines)
    finally:
        if _HAS_TINYDB:
            db.close()


def complete_task(task_id: int | str) -> str:
    """Mark a task as done/completed."""
    try:
        tid = int(task_id)
    except (ValueError, TypeError):
        return f"Invalid task ID: '{task_id}'. 'tasks list karo' se ID dekho."

    db = _get_db()
    try:
        table = db.table("tasks")
        if _HAS_TINYDB:
            Task = Query()
            results = table.search(Task["_id"] == tid)
            target_doc_id = None
            task_title = ""
            if results:
                target_doc_id = getattr(results[0], "doc_id", tid)
                task_title = results[0].get("task", "")
            elif table.contains(doc_id=tid):
                doc = table.get(doc_id=tid)
                if doc:
                    target_doc_id = tid
                    task_title = doc.get("task", "")
            if target_doc_id is None:
                return f"Task #{tid} nahi mila. 'tasks list karo' se IDs dekho."
            table.update({"status": "done", "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M")},
                         doc_ids=[target_doc_id])
            return f"✅ Task #{tid} mark done kar diya: '{task_title}'"
        else:
            task_obj = next((t for t in table.all() if t.get("_id") == tid), None)
            if not task_obj:
                return f"Task #{tid} nahi mila. 'tasks list karo' se IDs dekho."
            table.update_by_id(tid, {"status": "done",
                                     "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
            return f"✅ Task #{tid} complete kar diya: '{task_obj.get('task', '')}'"
    finally:
        if _HAS_TINYDB:
            db.close()


def delete_task(task_id: int | str) -> str:
    """Delete a task by ID."""
    try:
        tid = int(task_id)
    except (ValueError, TypeError):
        return f"Invalid task ID: '{task_id}'."

    db = _get_db()
    try:
        table = db.table("tasks")
        if _HAS_TINYDB:
            Task = Query()
            results = table.search(Task["_id"] == tid)
            target_doc_id = None
            task_title = ""
            if results:
                target_doc_id = getattr(results[0], "doc_id", tid)
                task_title = results[0].get("task", "")
            elif table.contains(doc_id=tid):
                doc = table.get(doc_id=tid)
                if doc:
                    target_doc_id = tid
                    task_title = doc.get("task", "")
            if target_doc_id is None:
                return f"Task #{tid} nahi mila."
            table.remove(doc_ids=[target_doc_id])
            return f"🗑️ Task #{tid} delete kar diya: '{task_title}'"
        else:
            task_obj = next((t for t in table.all() if t.get("_id") == tid), None)
            if not task_obj:
                return f"Task #{tid} nahi mila."
            table.remove_by_id(tid)
            return f"🗑️ Task #{tid} delete kar diya: '{task_obj.get('task', '')}'"
    finally:
        if _HAS_TINYDB:
            db.close()


def tinydb_memory(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "add").strip().lower()
    task_text = params.get("task") or params.get("text") or params.get("note") or ""
    task_id = params.get("id") or params.get("task_id") or ""

    if action in ("list", "get", "show", "pending"):
        return get_pending_tasks()

    if action in ("complete", "done", "finish", "completed"):
        # Extract ID from task_text if not explicitly provided
        if not task_id and task_text:
            import re
            m = re.search(r"#?(\d+)", task_text)
            if m:
                task_id = m.group(1)
        if not task_id:
            return "Kaun sa task complete karna hai? ID batao (e.g. 'task #2 complete karo')."
        return complete_task(task_id)

    if action in ("delete", "remove", "hatao"):
        if not task_id and task_text:
            import re
            m = re.search(r"#?(\d+)", task_text)
            if m:
                task_id = m.group(1)
        if not task_id:
            return "Kaun sa task delete karna hai? ID batao."
        return delete_task(task_id)

    if not task_text:
        return "Koi task ya note specify nahi kiya gaya."

    due = params.get("due", "kal")
    cat = params.get("category", "study" if "revise" in task_text.lower() else "general")
    return add_task_reminder(task_text, due, cat)


TOOL = {
    "name": "tinydb_memory",
    "description": "Structured NoSQL memory for saving reminders, study tasks, and revision goals. Persistent across restarts. Use to add tasks, list pending tasks, mark tasks as complete, or delete tasks.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "'add' to record a task/reminder, "
                    "'list'/'pending' to view active tasks, "
                    "'complete'/'done' to mark a task done, "
                    "'delete'/'remove' to delete a task."
                )
            },
            "task": {
                "type": "STRING",
                "description": "Task description to remember, or '#ID' when completing/deleting (e.g. '#2 complete karo')"
            },
            "id": {
                "type": "STRING",
                "description": "Task ID number when completing or deleting a specific task"
            },
            "due": {
                "type": "STRING",
                "description": "Optional deadline (e.g. 'kal shaam 6 baje', 'Friday')"
            },
            "category": {
                "type": "STRING",
                "description": "Optional category (e.g. 'study', 'work', 'personal')"
            }
        },
        "required": ["action"]
    },
    "handler": tinydb_memory,
}
