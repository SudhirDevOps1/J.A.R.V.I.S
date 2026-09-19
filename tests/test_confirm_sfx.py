"""Additive tests for confirm gate + sfx assets (no audio played)."""
import os


def test_confirm_gate_expandable():
    from core import confirm
    assert hasattr(confirm, "needs_confirmation")
    assert confirm.needs_confirmation("mass_delete_50_plus", {}) is True
    assert confirm.needs_confirmation("github_push_main", {}) is True
    assert confirm.needs_confirmation("github_push", {"branch": "main"}) is True
    assert confirm.needs_confirmation("open_app", {}) is False


def test_sfx_files_exist_or_generatable():
    from core import sfx
    assert hasattr(sfx, "play_sfx")
    assert os.path.isdir(sfx.SFX_DIR)
