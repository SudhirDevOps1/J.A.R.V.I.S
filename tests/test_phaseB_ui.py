"""Additive Phase-B tests (no GUI needed)."""


def test_feedback_store():
    from memory.feedback import log_feedback, stats
    assert log_feedback("up", "pytest") is True
    s = stats()
    assert s["up"] >= 1


def test_onboard_flag():
    from memory import config_manager as _cm
    assert hasattr(_cm, "get_onboarded") and hasattr(_cm, "save_onboarded")
    assert isinstance(_cm.get_onboarded(), bool)


def test_toast_class_shape():
    import ui as _ui
    assert hasattr(_ui, "ToastStack")
    assert hasattr(_ui.MainWindow, "toast")
    assert hasattr(_ui.MainWindow, "_show_toast")
    assert hasattr(_ui.MainWindow, "_maybe_onboard")
    assert hasattr(_ui.MainWindow, "_thumb")
