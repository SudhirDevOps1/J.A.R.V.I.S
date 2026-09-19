"""Additive tests for new plugins shape (no network calls)."""


def _shape(modname, toolname):
    import importlib
    m = importlib.import_module(f"plugins.{modname}")
    assert isinstance(m.PLUGIN, dict)
    assert m.PLUGIN["name"] == toolname
    assert callable(m.run)


def test_plugin_shapes():
    _shape("spotify_control", "spotify_control")
    _shape("pomodoro_timer", "pomodoro_timer")
    _shape("stock_price", "stock_price")
    _shape("notion_sync", "notion_sync")


def test_pomodoro_validates():
    from plugins.pomodoro_timer import run
    out = run({"minutes": "abc", "label": "t"})
    assert "Pomodoro" in out
