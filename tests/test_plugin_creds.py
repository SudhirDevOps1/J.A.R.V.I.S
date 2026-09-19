"""Additive credential-hub tests (no writes to real config)."""


def test_specs_shape():
    from core import plugin_creds as _pc
    assert len(_pc.SPECS) >= 10
    for spec in _pc.SPECS:
        assert spec.get("plugin") and spec.get("label") and spec.get("kind")
        assert callable(spec.get("detect"))


def test_status_all_bool():
    from core.plugin_creds import status_all
    for label, ok in status_all():
        assert isinstance(label, str) and isinstance(ok, bool)


def test_save_keys_noop_and_import_fail():
    from core.plugin_creds import save_keys, import_cred_file
    assert save_keys({}) is False
    ok, msg = import_cred_file("gmail", "C:/no/such/file.json")
    assert ok is False and isinstance(msg, str)


def test_overlay_builds_offscreen():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import ui as _ui
    ov = _ui.PluginSettingsOverlay([], parent=None)
    assert ov is not None
