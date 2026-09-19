"""
J.A.R.V.I.S. Real-time Active Timer & Countdown Manager.
Tracks live alarms, countdown timers, cron reminders, and pending developer tasks.
Synchronizes with UI HUD Clock watch, left telemetry panel, and audio alerts.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

_TIMERS_FILE = Path(__file__).resolve().parent.parent / "config" / "active_timers.json"


class ActiveTimer:
    def __init__(
        self,
        timer_id: str,
        message: str,
        target_iso: str,
        total_seconds: int,
        category: str = "alarm",
        created_iso: Optional[str] = None,
        fired: bool = False,
    ):
        self.id = timer_id
        self.message = message
        self.target_iso = target_iso
        self.total_seconds = max(1, total_seconds)
        self.category = category
        self.created_iso = created_iso or datetime.now().isoformat()
        self.fired = fired

    @property
    def target_datetime(self) -> datetime:
        try:
            return datetime.fromisoformat(self.target_iso)
        except Exception:
            return datetime.now()

    @property
    def remaining_seconds(self) -> int:
        delta = (self.target_datetime - datetime.now()).total_seconds()
        return max(0, int(delta))

    @property
    def progress_percent(self) -> int:
        if self.total_seconds <= 0:
            return 100
        rem = self.remaining_seconds
        elapsed = self.total_seconds - rem
        pct = int((elapsed / self.total_seconds) * 100)
        return max(0, min(100, pct))

    def format_countdown(self) -> str:
        s = self.remaining_seconds
        if s <= 0:
            return "00:00"
        m, sec = divmod(s, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{sec:02d}"
        return f"{m:02d}:{sec:02d}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "message": self.message,
            "target_iso": self.target_iso,
            "total_seconds": self.total_seconds,
            "category": self.category,
            "created_iso": self.created_iso,
            "fired": self.fired,
            "remaining_seconds": self.remaining_seconds,
            "formatted": self.format_countdown(),
            "progress": self.progress_percent,
        }


class TimerManager:
    _instance: Optional[TimerManager] = None
    _lock = threading.Lock()

    def __init__(self):
        self._timers: Dict[str, ActiveTimer] = {}
        self._listeners: List[Any] = []
        self._load()

    @classmethod
    def get_instance(cls) -> TimerManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = TimerManager()
            return cls._instance

    def _load(self):
        if not _TIMERS_FILE.exists():
            return
        try:
            raw = json.loads(_TIMERS_FILE.read_text(encoding="utf-8"))
            now = datetime.now()
            for item in raw:
                try:
                    tgt = datetime.fromisoformat(item["target_iso"])
                    # Keep timers that haven't passed or expired within the last 5 minutes
                    if tgt > now or (now - tgt).total_seconds() < 300:
                        t = ActiveTimer(
                            timer_id=item["id"],
                            message=item.get("message", "Alarm"),
                            target_iso=item["target_iso"],
                            total_seconds=item.get("total_seconds", 300),
                            category=item.get("category", "alarm"),
                            created_iso=item.get("created_iso"),
                            fired=item.get("fired", False),
                        )
                        self._timers[t.id] = t
                except Exception:
                    continue
        except Exception:
            pass

    def _save(self):
        try:
            _TIMERS_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = [t.to_dict() for t in self._timers.values()]
            _TIMERS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def add_timer(
        self,
        timer_id: str,
        message: str,
        target_dt: datetime,
        total_seconds: Optional[int] = None,
        category: str = "alarm",
    ) -> ActiveTimer:
        with self._lock:
            now = datetime.now()
            if total_seconds is None or total_seconds <= 0:
                total_seconds = max(1, int((target_dt - now).total_seconds()))

            timer = ActiveTimer(
                timer_id=timer_id,
                message=message,
                target_iso=target_dt.isoformat(),
                total_seconds=total_seconds,
                category=category,
            )
            self._timers[timer_id] = timer
            self._save()
            return timer

    def cancel_timer(self, timer_id: str) -> bool:
        with self._lock:
            if timer_id in self._timers:
                del self._timers[timer_id]
                self._save()
                return True
            return False

    def get_active_timers(self) -> List[ActiveTimer]:
        with self._lock:
            now = datetime.now()
            # Return active timers sorted by soonest target
            active = [
                t for t in self._timers.values()
                if not t.fired and t.remaining_seconds > 0
            ]
            active.sort(key=lambda x: x.target_datetime)
            return active

    def get_primary_countdown(self) -> Optional[ActiveTimer]:
        """Return the soonest expiring active timer, if any."""
        active = self.get_active_timers()
        return active[0] if active else None

    def check_and_trigger_expired(self) -> List[ActiveTimer]:
        """Check for timers that have reached 0 and need to fire speech/alerts."""
        with self._lock:
            now = datetime.now()
            expired_to_alert = []
            for t in list(self._timers.values()):
                if not t.fired and t.target_datetime <= now:
                    t.fired = True
                    expired_to_alert.append(t)
            if expired_to_alert:
                self._save()
            return expired_to_alert

    def get_pending_tasks(self, limit: int = 3) -> List[Dict[str, Any]]:
        """Fetch pending tasks from TinyDB memory store for HUD display."""
        try:
            from actions.tinydb_memory import _get_db, _HAS_TINYDB
            db = _get_db()
            try:
                table = db.table("tasks")
                tasks = table.all()
                pending = [
                    t for t in tasks
                    if isinstance(t, dict) and t.get("status") == "pending"
                ]
                return pending[:limit]
            finally:
                if _HAS_TINYDB:
                    db.close()
        except Exception:
            return []


# Module-level convenience functions
def get_timer_manager() -> TimerManager:
    return TimerManager.get_instance()

def add_active_timer(timer_id: str, message: str, target_dt: datetime, category: str = "alarm") -> ActiveTimer:
    return get_timer_manager().add_timer(timer_id, message, target_dt, category=category)

def get_primary_timer() -> Optional[ActiveTimer]:
    return get_timer_manager().get_primary_countdown()

def check_expired_timers() -> List[ActiveTimer]:
    return get_timer_manager().check_and_trigger_expired()

def get_pending_tasks_for_ui(limit: int = 3) -> List[Dict[str, Any]]:
    return get_timer_manager().get_pending_tasks(limit=limit)
