"""
tests/conftest.py — Shared fixtures and test isolation.

ROUTER TESTS AND THE CONFIDENCE GATE
------------------------------------
core/edge_router.py routes via a regex cascade that is now gated by
core.reflex_policy: a match executes only if the usage-learning loop has
evidence the phrase previously worked, otherwise it defers to the cloud model.

Most router tests assert on the REGEX LOGIC ("this phrase should produce a
web_search call"), not on the gating policy. Running them against the gate
would make every assertion fail with (None, None) simply because the phrase
has no history — which tests nothing about the router.

So the gate is disabled for the whole suite, and tests/test_reflex_policy.py
re-enables it explicitly. That keeps the two concerns separately and honestly
tested instead of blurring them.

ISOLATION
---------
Tests that record learning-loop outcomes redirect the database themselves
(fixtures in the individual modules). Anything else that touches the user's
real memory is redirected here so a test run can never rewrite
memory/learning.db or config/api_keys.json.
"""
import pytest


def pytest_configure(config):
    """Keep Qt off any real display for the whole run.

    Without this, constructing a QWidget on a headless CI runner aborts the
    process (not an exception — a hard exit), so it cannot be handled in a
    fixture. Setting it at configure time means every test, including ones in
    files this project did not write, gets a usable platform plugin.
    """
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def _reflex_gate_off_by_default():
    """Run the suite with the reflex confidence gate disabled.

    Individual tests that specifically exercise the gate import
    core.reflex_policy and call set_enabled(True) themselves (see
    tests/test_reflex_policy.py).
    """
    from core import reflex_policy
    original = reflex_policy.is_enabled()
    reflex_policy.set_enabled(False)
    try:
        yield
    finally:
        reflex_policy.set_enabled(original)


@pytest.fixture(autouse=True)
def _no_config_writes(request, monkeypatch):
    """Prevent tests from rewriting the user's real config files.

    config_manager._patch_config is the single write path for api_keys.json,
    so redirecting it to a throwaway file is enough to protect the user's
    settings. Skipped for tests that explicitly opt in.
    """
    if request.node.get_closest_marker("allow_config_write"):
        return
    try:
        from memory import config_manager
    except Exception:
        return
    import json
    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp())
    redirected = tmp / "api_keys.json"
    if config_manager.CONFIG_FILE.exists():
        redirected.write_text(
            config_manager.CONFIG_FILE.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    else:
        redirected.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(config_manager, "CONFIG_FILE", redirected)

    # Patch _backup_config too so it does not touch the real config dir.
    monkeypatch.setattr(
        config_manager, "_backup_config",
        lambda *a, **kw: None,
        raising=False,
    )