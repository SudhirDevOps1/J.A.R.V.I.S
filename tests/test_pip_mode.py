"""Additive PiP tests (offscreen, no window shown on screen)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_pip_routing():
    from core.edge_router import NeedleToolRouter
    r = NeedleToolRouter()
    assert r.classify_tool_intent("pip mode on karo")[0] == "pip_mode"
    got = r.classify_tool_intent("mini window band karo")
    assert got[0] == "pip_mode" and got[1]["action"] == "off"


def test_pip_widget_offscreen():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import ui as _ui
    w = _ui.PipWindow()
    w.push_line("You: hello")
    w.push_line("MAYA: hi")
    w.set_dot("SPEAKING")
    w.show()
    assert w.isVisible()
    w.hide()
    assert hasattr(_ui.MainWindow, "toggle_pip")


def test_pip_action_no_player():
    from actions.pip_mode import pip_mode, TOOL
    assert TOOL["name"] == "pip_mode"
    out = pip_mode({"action": "toggle"}, player=None)
    assert isinstance(out, str) and "PIP" in out
