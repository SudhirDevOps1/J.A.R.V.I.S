"""Additive tests: obsidian status explicit, weather default city (live API, tolerant)."""


def test_obsidian_status_explicit():
    from actions.obsidian_brain import obsidian_brain
    out = obsidian_brain({"action": "status"})
    assert "Obsidian Brain Status" in out
    assert "Local Vault" in out or "NOT FOUND" in out


def test_weather_default_city():
    from actions.weather_report import weather_action, _default_city
    # city blank -> memory/IP fallback (may be '' offline, never crash)
    assert isinstance(_default_city(), str)
    out = weather_action({"city": "Delhi"})
    assert isinstance(out, str) and len(out) > 0
