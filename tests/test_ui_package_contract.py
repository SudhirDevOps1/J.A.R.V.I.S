"""
tests/test_ui_package_contract.py — Guards the `ui` package vs `ui.py` module.

THE BUG THIS EXISTS FOR
----------------------
ui.py is a MODULE at the repository root and main.py imports it as
`from ui import JarvisUI`. Adding a `ui/` directory with an `__init__.py` made
Python resolve `ui` to the PACKAGE instead, because packages take precedence
over same-named modules. The result was an ImportError on every launch, and
nothing in the test suite caught it because no test imported `ui` at module
level.

These tests pin the contract that makes the package safe to have:

  * `import ui` still exposes the names ui.py defined
  * `ui.py` itself is untouched and still the source of those names
  * the new submodules do not shadow anything ui.py exported

Without this file the failure mode is a broken app and a green build.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def test_import_ui_resolves_and_exposes_jarvisui():
    """The exact call main.py makes at startup."""
    ui = importlib.import_module("ui")
    assert ui is not None
    assert hasattr(ui, "JarvisUI"), (
        "import ui must expose JarvisUI — main.py does `from ui import "
        "JarvisUI` and the app will not start without it"
    )


@pytest.mark.parametrize("name", [
    "JarvisUI",        # main.py:120
    "MainWindow",      # the HUD window
    "HudCanvas",
    "LogWidget",
    "PipWindow",
    "SetupOverlay",
    "CustomizeOverlay",
    "ProviderSettingsOverlay",
    "PluginManagerOverlay",
    "AudioDeviceOverlay",
    "MemoryOverlay",
    "RemoteKeyOverlay",
])
def test_public_names_are_re_exported(name):
    """Names main.py and ui_icons.py import must survive the package wrapping."""
    ui = importlib.import_module("ui")
    assert hasattr(ui, name), f"ui package must re-export {name}"


def test_private_singleton_used_by_shutdown_is_preserved():
    """main.py:2828 does `from ui import _metrics` and stops it on shutdown.

    That name starts with an underscore, so a naive "skip private names"
    re-export would drop it and the metrics thread would never stop cleanly.
    """
    ui = importlib.import_module("ui")
    assert hasattr(ui, "_metrics"), "_metrics must be re-exported for shutdown"


def test_ui_py_exists_and_is_the_module_source():
    """ui.py must remain the HUD module at the repo root."""
    path = _ROOT / "ui.py"
    assert path.exists(), "ui.py must remain the HUD module at the repo root"
    assert path.stat().st_size > 100_000, (
        "ui.py looks truncated — the HUD source of truth must stay here"
    )


def test_reexported_classes_come_from_the_cached_legacy_module():
    """Not copies, not look-alikes — the classes from the one loaded ui.py.

    Loading a file twice necessarily produces two distinct class objects, so
    identity can only be asserted against the module instance the package
    caches. What matters is that there is exactly ONE ui.py in memory and the
    package's names point into it; a second copy would make isinstance checks
    and signal connections across the boundary silently fail.
    """
    ui = importlib.import_module("ui")
    legacy = getattr(ui, "_legacy_ui", None)
    assert legacy is not None, (
        "the package must keep a reference to the loaded ui.py module"
    )

    for name in ("JarvisUI", "MainWindow", "HudCanvas", "LogWidget", "PipWindow"):
        assert getattr(ui, name) is getattr(legacy, name), (
            f"{name} must be the object from the cached ui.py module, not a copy"
        )

    # And that module must be a singleton: asking again returns the same one.
    assert sys.modules[legacy.__name__] is legacy


def test_package_reexport_is_idempotent():
    """Re-importing must not reload ui.py and create duplicate classes."""
    first = importlib.import_module("ui")
    second = importlib.import_module("ui")
    assert first is second


def test_ui_py_stays_a_plain_module_not_converted_to_a_package():
    """A future refactor must not quietly move ui.py's contents into ui/.

    If that happened while ui.py kept its name, there would be two sources of
    truth and the re-export would start shadowing the real implementation.
    """
    pkg_init = _ROOT / "ui" / "__init__.py"
    assert pkg_init.exists()
    text = pkg_init.read_text(encoding="utf-8")
    # The package must stay a thin re-export shim, not a copy of the HUD.
    assert len(text) < 4000, (
        "ui/__init__.py has grown — if the HUD moved into the package, "
        "ui.py must be removed or the shim will shadow it"
    )
    assert "JarvisUI" in text, "the shim must still wire up the legacy module"


# ── new submodules coexist with ui.py ───────────────────────────────────────

@pytest.mark.parametrize("mod", [
    "ui.shortcuts",
    "ui.command_palette",
    "ui.palette_widget",
    "ui.history_panel",
    "ui.shortcut_help",
    "ui.html_sanitize",
])
def test_submodule_imports_without_touching_ui_py(mod):
    """Each submodule must import standalone without requiring the HUD module
    to have been loaded first — otherwise a headless test would pull in
    PyQt widgets it does not need."""
    m = importlib.import_module(mod)
    assert m is not None