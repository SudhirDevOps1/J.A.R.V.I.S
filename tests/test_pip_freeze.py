"""Additive tests: PiP threading, camera fail-fast, filler guard (no hardware touched)."""


def test_pip_send_threaded():
    import inspect
    import ui as _ui
    src = inspect.getsource(_ui.PipWindow._do_send)
    assert "Thread" in src and "on_text_command" not in src.split("Thread")[0][-200:]


def test_camera_failfast_helpers():
    from actions import screen_processor as _sp
    assert hasattr(_sp, "_silence_cv2")
    assert hasattr(_sp, "_cam_dead")
    assert hasattr(_sp, "_mark_cam_dead")
    # cooldown marker roundtrip (no camera touched)
    assert _sp._cam_dead() is False
    _sp._mark_cam_dead()
    assert _sp._cam_dead() is True
    _sp._CAM_DEAD_UNTIL = 0.0
    assert _sp._cam_dead() is False


def test_filler_search_refused():
    from actions.web_search import web_search
    out = web_search({"query": "arey"})
    assert out.startswith("NO_SEARCH")
    out2 = web_search({"query": "laptop price"})
    assert not out2.startswith("NO_SEARCH")
