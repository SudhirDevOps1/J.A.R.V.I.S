"""Additive safety-guard tests (no apps launched, no windows touched)."""


def test_garbage_words_refused():
    from actions.open_app import open_app
    for bad in ("kro", "karo", "kholo", "me", "a"):
        out = open_app({"action": "open", "app_name": bad})
        assert "samajh nahi aaya" in out, bad


def test_walker_empty_title_safe():
    from actions.window_tools import window_tools
    out = window_tools({"action": "walker", "title": ""})
    assert isinstance(out, str) and "window" in out.lower()


def test_routine_save_and_cleanup():
    import json
    from pathlib import Path
    from actions.open_app import open_app
    out = open_app({"action": "save_routine", "routine": "_pytest_tmp",
                    "apps": "code, chrome"})
    assert "save ho gayi" in out
    # cleanup apni test entry (sample dev/movie untouched)
    p = Path("config/routines.json")
    d = json.loads(p.read_text(encoding="utf-8"))
    d.pop("_pytest_tmp", None)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    assert "_pytest_tmp" not in json.loads(p.read_text(encoding="utf-8"))


def test_confirm_queue_fifo():
    from core import confirm
    shown = []
    confirm.bind(lambda t, d: shown.append(t), lambda: None, lambda m: None)
    # reset module state (test-only, app start par fresh hota hai)
    confirm._pending = None
    confirm._queue.clear()
    confirm.request("k1", "First", "d1", lambda: "done1")
    r2 = confirm.request("k2", "Second", "d2", lambda: "done2")
    assert "position 1" in r2
    assert confirm._queued_count() == 1
    confirm.resolve(True)
    import time
    time.sleep(0.6)
    assert shown == ["First", "Second"], shown
    assert confirm._queued_count() == 0
    confirm._pending = None
    confirm._queue.clear()
