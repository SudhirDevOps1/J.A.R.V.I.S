"""Scheduler 2.0 — cron/interval/date + file/battery/app triggers. New file, auto-discovered.
APScheduler (SQLite jobstore) time jobs ke liye; watchdog file-trigger; psutil poll
battery/app ke liye. Reminder (one-shot OS) untouched — yah recurring/smart layer hai.
"""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

_STORE = Path(__file__).resolve().parent.parent / "config" / "scheduled_jobs.json"
_SQLITE = Path(__file__).resolve().parent.parent / "config" / "scheduler_jobs.sqlite"
_sched = None
_sched_lock = threading.Lock()
_watchers: dict = {}
_poll_started = False


def _log(player, msg: str) -> None:
    try:
        if player:
            player.write_log(msg)
    except Exception:
        pass
    print(msg)


def _audit(action: str, detail: str = "") -> None:
    try:
        from core.audit import log_event as _ae
        _ae(action, detail)
    except Exception:
        pass


def _load() -> list:
    try:
        if _STORE.exists():
            data = json.loads(_STORE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def _save(jobs: list) -> None:
    try:
        _STORE.parent.mkdir(parents=True, exist_ok=True)
        _tmp = _STORE.with_suffix(".json.tmp")
        _tmp.write_text(json.dumps(jobs[-100:], indent=2, ensure_ascii=False), encoding="utf-8")
        import os as _os
        _os.replace(str(_tmp), str(_STORE))
    except Exception:
        pass


def _fire(job: dict, player=None) -> None:
    """Job fire: HUD log + speak + optional routine. Never raises."""
    try:
        msg = job.get("message", "Scheduled task.")
        _log(player, f"[scheduler] {job.get('name', 'job')}: {msg}")
        routine = str(job.get("routine", "") or "").strip()
        if routine:
            try:
                from actions.open_app import open_app as _oa
                _oa({"action": "routine", "routine": routine})
            except Exception:
                pass
        _audit("scheduler_fire", job.get("name", ""))
    except Exception:
        pass


def _get_sched():
    """APScheduler singleton (lazy, SQLite jobstore). None agar lib missing."""
    global _sched
    with _sched_lock:
        if _sched is not None:
            return _sched
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
            _sched = BackgroundScheduler(
                jobstores={"default": SQLAlchemyJobStore(url=f"sqlite:///{_SQLITE}")},
                daemon=True)
            _sched.start()
        except Exception as e:
            print(f"[scheduler] APScheduler unavailable: {e}")
            _sched = False
        return _sched or None


def _parse_natural(text: str) -> dict | None:
    """Hindi/English time text -> {kind, ...}. None agar na samjhe."""
    t = (text or "").lower().strip()
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(baje|am|pm|o'clock)", t)
    if m and ("roz" in t or "daily" in t or "subah" in t or "sham" in t or "everyday" in t):
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        if "pm" in t or "sham" in t:
            h = (h % 12) + 12
        return {"kind": "cron", "hour": h, "minute": mi}
    m = re.search(r"har\s+(\d+)\s*(minute|min|ghante|hour|second)", t)
    if m:
        n = int(m.group(1))
        unit = "hours" if ("ghante" in t or "hour" in t) else ("seconds" if "second" in t else "minutes")
        return {"kind": "interval", "unit": unit, "value": n}
    m = re.search(r"(\d+)\s*(minute|min|ghante|hour)s?\s*(me|mein|baad|later)", t)
    if m:
        n = int(m.group(1))
        secs = n * (3600 if ("ghante" in t or "hour" in t) else 60)
        return {"kind": "once", "seconds": secs}
    return None


def _add_time_job(name: str, message: str, spec: dict, routine: str, player=None) -> str:
    sched = _get_sched()
    if sched is None:
        return "Scheduler lib (apscheduler) install karo: pip install apscheduler."
    jobs = _load()
    job = {"name": name, "message": message, "routine": routine,
           "spec": spec, "at": time.strftime("%Y-%m-%d %I:%M %p")}
    try:
        from datetime import datetime as _dt, timedelta as _td
        jid = f"jarvis_{int(time.time())}_{len(jobs)}"
        cb = lambda j=job: _fire(j, player)
        if spec["kind"] == "cron":
            sched.add_job(cb, "cron", hour=spec["hour"], minute=spec["minute"], id=jid, replace_existing=True)
            when = f"roz {spec['hour']:02d}:{spec['minute']:02d}"
        elif spec["kind"] == "interval":
            kw = {spec["unit"]: spec["value"]}
            sched.add_job(cb, "interval", id=jid, replace_existing=True, **kw)
            when = f"har {spec['value']} {spec['unit']}"
        else:
            run_at = _dt.now() + _td(seconds=spec.get("seconds", 300))
            sched.add_job(cb, "date", run_date=run_at, id=jid, replace_existing=True)
            when = run_at.strftime("%I:%M %p")
        job["sched_id"] = jid
        jobs.append(job)
        _save(jobs)
        _audit("scheduler_add", f"{name} ({when})")
        _log(player, f"[scheduler] '{name}' set: {when}")
        return f"Schedule lag gaya '{name}': {when}."
    except Exception as e:
        return f"Schedule failed: {e}"


def _add_file_trigger(name: str, message: str, folder: str, player=None) -> str:
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except Exception:
        return "File trigger ke liye watchdog install karo: pip install watchdog."
    d = Path(folder.replace('"', "").strip()).expanduser()
    if not d.is_dir():
        return f"Folder nahi mila: {folder}."
    if name in _watchers:
        return f"'{name}' trigger pehle se chal raha hai."
    fired: list = []

    class _H(FileSystemEventHandler):
        def on_created(self, event):
            if not event.is_directory and len(fired) < 50:
                fired.append(event.src_path)
                _fire({"name": name, "message": f"{message} (nayi file: {Path(event.src_path).name})"}, player)

    try:
        ob = Observer()
        ob.schedule(_H(), str(d), recursive=False)
        ob.start()
        _watchers[name] = ob
        jobs = _load()
        jobs.append({"name": name, "message": message, "spec": {"kind": "file", "folder": str(d)},
                     "at": time.strftime("%Y-%m-%d %I:%M %p")})
        _save(jobs)
        _audit("scheduler_file", f"{name} -> {d}")
        return f"File trigger lag gaya '{name}': {d} me nayi file aate hi bataunga."
    except Exception as e:
        return f"File trigger failed: {e}"


def _ensure_poll_thread() -> None:
    """Battery/app poll thread (ek hi baar). Additive daemon."""
    global _poll_started
    if _poll_started:
        return
    _poll_started = True

    def _loop():
        last = 0.0
        while True:
            try:
                time.sleep(60)
                if time.time() - last < 300:
                    continue
                jobs = _load()
                trig_jobs = [j for j in jobs if j.get("spec", {}).get("kind") in ("battery", "app")]
                if not trig_jobs:
                    continue
                last = time.time()
                import psutil as _ps
                try:
                    bat = _ps.sensors_battery()
                    pct = bat.percent if bat else None
                except Exception:
                    pct = None
                try:
                    procs = { (p.info.get("name") or "").lower() for p in _ps.process_iter(["name"]) }
                except Exception:
                    procs = set()
                for j in trig_jobs:
                    sp = j.get("spec", {})
                    if sp.get("kind") == "battery" and pct is not None:
                        try:
                            if pct <= float(sp.get("below", 20)):
                                _fire(j)
                        except Exception:
                            pass
                    elif sp.get("kind") == "app":
                        want = str(sp.get("app", "")).lower()
                        if want and any(want in p for p in procs):
                            _fire(j)
            except Exception:
                continue

    threading.Thread(target=_loop, daemon=True, name="scheduler-poll").start()


def scheduler(parameters: dict | None = None, player=None, session_memory=None, **_) -> str:
    params = parameters or {}
    action = str(params.get("action", "list") or "list").lower().strip()
    name = str(params.get("name", "task") or "task").strip()[:40]
    message = str(params.get("message", name) or name).strip()
    routine = str(params.get("routine", "") or "").strip()
    if action in ("list", "show"):
        jobs = _load()
        if not jobs:
            return "Koi schedule nahi hai. 'roz subah 9 baje backup' jaise bolo."
        return "Schedules:\n" + "\n".join(
            f"{i+1}. {j.get('name')} ({j.get('spec', {}).get('kind')})" for i, j in enumerate(jobs[-10:]))
    if action in ("cancel", "stop", "delete"):
        jobs = _load()
        keep = [j for j in jobs if j.get("name", "").lower() != name.lower()]
        if len(keep) == len(jobs):
            return f"'{name}' nahi mila."
        _save(keep)
        try:
            sched = _get_sched()
            if sched:
                for j in sched.get_jobs():
                    if name.lower() in j.id.lower():
                        sched.remove_job(j.id)
        except Exception:
            pass
        if name in _watchers:
            try:
                _watchers.pop(name).stop()
            except Exception:
                pass
        _audit("scheduler_cancel", name)
        return f"Schedule '{name}' cancel kar diya."
    # add
    when = str(params.get("when", params.get("schedule", "")) or "").strip()
    kind = str(params.get("kind", "") or "").lower().strip()
    if kind == "file" or "folder" in (params or {}) or "nayi file" in when:
        folder = str(params.get("folder", "") or "").strip() or when
        return _add_file_trigger(name, message, folder, player)
    if kind == "battery" or "battery" in when:
        m = re.search(r"(\d+)", when)
        jobs = _load()
        jobs.append({"name": name, "message": message,
                     "spec": {"kind": "battery", "below": float(m.group(1)) if m else 20.0},
                     "at": time.strftime("%Y-%m-%d %I:%M %p")})
        _save(jobs)
        _ensure_poll_thread()
        return f"Battery trigger lag gaya '{name}'."
    if kind == "app" or "app khule" in when or "app open" in when:
        app = str(params.get("app", "") or "").strip() or when
        jobs = _load()
        jobs.append({"name": name, "message": message,
                     "spec": {"kind": "app", "app": app},
                     "at": time.strftime("%Y-%m-%d %I:%M %p")})
        _save(jobs)
        _ensure_poll_thread()
        return f"App trigger lag gaya '{name}' ({app})."
    spec = _parse_natural(when)
    if not spec:
        if kind == "cron":
            spec = {"kind": "cron", "hour": 9, "minute": 0}
        elif kind == "interval":
            spec = {"kind": "interval", "unit": "minutes", "value": 30}
        else:
            return ("Samajh nahi aaya. Bolo: 'roz subah 9 baje X', 'har 30 minute Y', "
                    "'10 minute me Z', ya file/battery/app trigger.")
    return _add_time_job(name, message, spec, routine, player)


TOOL = {
    "name": "scheduler",
    "description": (
        "Recurring schedules + smart triggers (cron/interval/once, file-arrival, "
        "battery-low, app-open). Trigger on 'roz subah', 'har 30 minute', 'nayi file aaye', "
        "'battery kam ho'. Do NOT use reminder for recurring/smart triggers."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "add | list | cancel"},
            "name": {"type": "STRING", "description": "Schedule name"},
            "when": {"type": "STRING", "description": "Natural time: 'roz subah 9 baje', 'har 30 minute', '10 minute me'"},
            "message": {"type": "STRING", "description": "What to say/do on fire"},
            "routine": {"type": "STRING", "description": "Optional routine to launch on fire"},
            "kind": {"type": "STRING", "description": "file | battery | app | cron | interval"},
            "folder": {"type": "STRING", "description": "Folder for file trigger"},
            "app": {"type": "STRING", "description": "App name for app trigger"},
        },
        "required": ["action"],
    },
    "handler": scheduler,
}
