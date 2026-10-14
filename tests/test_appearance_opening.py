"""
tests/test_appearance_opening.py - Opening the theme picker must not hide the app.

THE BUG
-------
The first version of _open_appearance() started with:

    self._tray_toggle_window()

with the comment "so the panel will be visible". _tray_toggle_window TOGGLES:
its own docstring says it hides the window when it is already up. So pressing
Ctrl+Shift+T while J.A.R.V.I.S was showing hid the entire interface, and the
panel went with it as a child. The user reported that pressing the shortcut
made things disappear.

Two smaller errors came with it: the panel was parented to the MainWindow
instead of centralWidget(), so it spanned the metrics rail and the activity
log, and _place_overlay() was never called, which is what centres an overlay
that lives outside the layout.

The fix follows _open_history exactly: show-if-hidden rather than toggle,
parent to centralWidget(), then _place_overlay().

WHY A TEST
----------
The panel itself had 17 passing tests. None of them touched the code that
opens it, which is how a working panel ended up with a shortcut that closed the
app. The gap is not "does the panel work" but "is it reachable safely", and
that is what is asserted here.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qt():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


class _Stub:
    """Enough of MainWindow for _open_appearance, and nothing else.

    A real MainWindow drags in the whole HUD, the tray and a 10,000-line
    module's import side effects. What is under test is the sequence of calls,
    so the collaborators are recorded instead of executed.
    """

    def __init__(self):
        self.calls = []
        self._visible = True
        self._minimized = False
        self._theme_panel = None
        self._central = None
        self._placed = None

    def isVisible(self):
        self.calls.append("isVisible")
        return self._visible

    def isMinimized(self):
        self.calls.append("isMinimized")
        return self._minimized

    def showNormal(self):
        self.calls.append("showNormal")

    def raise_(self):
        self.calls.append("raise_")

    def activateWindow(self):
        self.calls.append("activateWindow")

    def hide(self):
        self.calls.append("hide")
        self._visible = False

    def centralWidget(self):
        self.calls.append("centralWidget")
        return self._central

    def _place_overlay(self, ov, width=None, height=None):
        self.calls.append(("place_overlay", width, height))
        self._placed = (ov, width, height)


@pytest.fixture()
def opener(qt):
    """_open_appearance lives on MainWindow, not on the JarvisUI wrapper.

    The wrapper is a thin shim over MainWindow, and the tray resolves handler
    names against the wrapped window. Getting this wrong is the same class of
    error as the original bug - a method that exists but is never reachable -
    so the fixture resolves it from the class that actually owns it.
    """
    from ui import MainWindow
    assert hasattr(MainWindow, "_open_appearance"), (
        "_open_appearance is not on MainWindow - the tray and the shortcut both "
        "resolve against it"
    )
    return MainWindow._open_appearance


def test_opening_the_picker_never_toggles_the_window(opener, monkeypatch):
    """The regression. The toggle hid the whole interface."""
    stub = _Stub()

    class _Panel:
        def __init__(self, *a, **kw):
            stub.calls.append("ThemePanel")

        def show_and_load(self):
            stub.calls.append("show_and_load")

        def raise_(self):
            stub.calls.append("panel.raise_")

    monkeypatch.setattr("ui.theme_panel.ThemePanel", _Panel)
    opener(stub)

    assert "hide" not in stub.calls, (
        f"opening the theme picker hid the window: {stub.calls}"
    )


def test_opening_the_picker_does_not_reach_the_toggle_at_all():
    """Stronger than the absence of hide(): the toggle must not be CALLED.

    Parsed with ast rather than a substring search, because the explanatory
    comment above this method names _tray_toggle_window in full - the very
    sentence describing the bug it replaced. A text search matches that comment
    and then fails forever no matter how correct the code is. Only a call node
    is the real thing.
    """
    import ast
    import inspect
    import ui

    tree = ast.parse(inspect.getsource(ui.MainWindow))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == "_open_appearance"),
              None)
    assert fn is not None, "_open_appearance not found"

    called = {
        node.func.attr
        for node in ast.walk(fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "_tray_toggle_window" not in called, (
        f"a toggle cannot be idempotent - it hides an already-visible window, "
        f"which is the bug this replaced. Calls found: {sorted(called)}"
    )
    assert "showNormal" in called, (
        f"a hidden window would not be restored. Calls found: {sorted(called)}"
    )


def test_opening_while_hidden_restores_the_window(opener, monkeypatch):
    """The genuine need _tray_toggle_window was serving: a tray-hidden window
    must come back, but without a toggle."""
    stub = _Stub()
    stub._visible = False
    stub._minimized = True
    stub._theme_panel = object()

    class _Panel:
        def show_and_load(self):
            stub.calls.append("show_and_load")

        def raise_(self):
            stub.calls.append("panel.raise_")

    monkeypatch.setattr("ui.theme_panel.ThemePanel", _Panel)
    opener(stub)

    assert "showNormal" in stub.calls, "a hidden window was not restored"
    assert "hide" not in stub.calls


def test_the_panel_is_placed_centre_over_the_central_widget(opener, monkeypatch):
    """Unplaced, a child sits at (0,0) on top of the metrics rail."""
    stub = _Stub()

    class _Panel:
        def __init__(self, parent, *a, **kw):
            stub.calls.append(("ThemePanel(parent)", parent))

        def show_and_load(self):
            stub.calls.append("show_and_load")

        def raise_(self):
            pass

    monkeypatch.setattr("ui.theme_panel.ThemePanel", _Panel)
    opener(stub)

    assert stub._placed is not None, "the panel was never placed"
    assert stub._placed[1] and stub._placed[2], "no size given, so it may collapse"


def test_the_panel_is_parented_to_the_central_widget_not_the_window(opener, monkeypatch):
    """Parenting to MainWindow made the panel span the left rail and the
    activity log."""
    stub = _Stub()
    sentinel = object()
    stub._central = sentinel

    parented = []

    class _Panel:
        def __init__(self, parent, *a, **kw):
            parented.append(parent)

        def show_and_load(self):
            pass

        def raise_(self):
            pass

    monkeypatch.setattr("ui.theme_panel.ThemePanel", _Panel)
    opener(stub)

    assert parented == [sentinel], (
        f"panel parented to {parented}, expected centralWidget()"
    )


def test_opening_twice_does_not_build_two_panels(opener, monkeypatch):
    """Rebuilding on every press throws away the live preview state and
    leaves the old one behind."""

    built = []

    class _Panel:
        def __init__(self, *a, **kw):
            built.append(1)

        def show_and_load(self):
            pass

        def raise_(self):
            pass

    import ui
    monkeypatch.setattr("ui.theme_panel.ThemePanel", _Panel)

    stub = _Stub()
    opener(stub)
    opener(stub)

    assert len(built) == 1, f"built {len(built)} panels for two presses"


def test_a_failure_inside_the_panel_does_not_propagate(opener, monkeypatch):
    """An overlay that raises must not take the window down with it."""

    class _Panel:
        def __init__(self, *a, **kw):
            raise RuntimeError("theme panel exploded")

    monkeypatch.setattr("ui.theme_panel.ThemePanel", _Panel)
    opener(_Stub())          # must not raise


# ── the three routes all reach the same place ───────────────────────────────

def test_the_shortcut_targets_a_method_that_exists():
    src = (_ROOT / "ui" / "shortcuts.py").read_text(encoding="utf-8-sig")
    assert "Ctrl+Shift+T" in src
    assert "_open_appearance" in src


def test_the_tray_menu_offers_appearance():
    from ui.tray import build_menu_actions
    labels = [a.label for group in build_menu_actions(True, False) for a in group]
    assert any("Appearance" in label for label in labels), labels
    assert any("_tray_open_theme" == a.callback
               for group in build_menu_actions(True, False) for a in group)


def test_the_command_palette_offers_appearance():
    src = (_ROOT / "ui.py").read_text(encoding="utf-8-sig")
    assert "Appearance (theme, light mode)" in src