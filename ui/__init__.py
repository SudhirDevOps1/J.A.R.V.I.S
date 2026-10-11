"""
ui/ — J.A.R.V.I.S. user interface package.

IMPORTANT: why this file exists
------------------------------
The original HUD lives in a MODULE named `ui.py` at the repository root, and
main.py imports it as `from ui import JarvisUI`.

Once this directory was created, Python's import system resolved `ui` to the
PACKAGE (packages take precedence over same-named modules), so `from ui import
JarvisUI` raised ImportError and the application stopped starting.

Rather than rename either side — `ui.py` is imported from main.py, ui_icons.py
and the whole test suite — this __init__ re-exports the original module's
public names. `ui` therefore means "the ui.py module plus the widgets in this
package", which is what every existing caller already expects.

What is added here:
    shortcuts.py           global keyboard shortcut registry + help rendering
    command_palette.py     fuzzy search over tools, plugins and UI commands
    palette_widget.py      the Ctrl+K Qt overlay
    history_panel.py       the Ctrl+H conversation browser
    shortcut_help.py       the Ctrl+/ reference sheet
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_UI_MODULE_PATH = _ROOT / "ui.py"


def _load_legacy_ui_module():
    """Import ui.py explicitly, under its own name, and graft its public names
    onto this package.

    `import ui` inside the module would recurse into this package, so the file is
    loaded from its path with a distinct module name and registered under that
    name. Doing it by path (rather than relying on sys.path ordering) is what
    makes this robust: the package directory and ui.py sit in the same folder,
    and resolution order between them is not something to depend on.
    """
    if not _UI_MODULE_PATH.exists():
        return None

    mod_name = "jarvis_legacy_ui"
    existing = sys.modules.get(mod_name)
    if existing is not None:
        return existing

    spec = importlib.util.spec_from_file_location(mod_name, _UI_MODULE_PATH)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    # Register before exec so that a module which does `import ui` from inside
    # finds this package rather than recursing.
    sys.modules[mod_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(mod_name, None)
        raise
    return module


def _reexport():
    """Copy ui.py's public names onto this package.

    Deliberately excludes private names (leading underscore) EXCEPT the few
    that main.py imports by name: `_metrics` is a module-level singleton the
    shutdown path stops, so it has to survive the re-export.
    """
    module = _load_legacy_ui_module()
    if module is None:
        return

    for name in dir(module):
        if name.startswith("__"):
            continue
        if name.startswith("_") and name not in ("_metrics",):
            continue
        globals()[name] = getattr(module, name)

    # Expose the module itself under a stable attribute for the shutdown path
    # and for anything that wants the legacy module directly.
    globals()["_legacy_ui"] = module
    globals().setdefault("JarvisUI", getattr(module, "JarvisUI", None))


_reexport()