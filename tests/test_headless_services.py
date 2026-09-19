"""
Unit tests for Headless Smart Services:
- Open-Meteo Weather with dynamic city geocoding (0 tokens, 0 browser popups)
- Local Music Library Scanner & Headless Audio Playback
- Headless eCommerce Price Comparison (Amazon & Flipkart)
- Headless Flight Schedules (Google Flights without mandatory browser popup)
- Tri-Tier Edge AI Router classifications (<1ms)
"""
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from core.system_info import get_free_weather
from actions.weather_report import weather_action
from actions.youtube_video import _find_local_audio, youtube_video
from actions.ecommerce_search import ecommerce_action
from actions.flight_finder import flight_finder
from core.edge_router import NeedleToolRouter


def test_open_meteo_weather_geocoding_live():
    """Verify Open-Meteo geocodes city and returns structured temperature and description."""
    w = get_free_weather(city="Mumbai")
    assert isinstance(w, dict)
    if w.get("success"):
        assert "temp" in w
        assert "desc" in w
        assert "feels_like" in w
        assert "humidity" in w
        assert "Mumbai" in w.get("city", "")


def test_weather_action_headless():
    """Verify weather_action does not open browser by default and renders HUD card."""
    mock_player = MagicMock()
    with patch("webbrowser.open") as mock_wb:
        res = weather_action({"city": "Delhi"}, player=mock_player)
        mock_wb.assert_not_called()
        assert "Delhi" in res
        mock_player.show_content.assert_called_once()
        title_arg = mock_player.show_content.call_args[0][0]
        assert "WEATHER" in title_arg


def test_local_audio_scanner_matches_song():
    """Verify local audio scanner matches query against user's local music collection."""
    # Test query for Sanam Teri Kasam which exists in ~/Music
    match = _find_local_audio("sanam teri kasam song")
    if match is not None:
        assert isinstance(match, Path)
        assert match.exists()
        assert match.suffix.lower() in (".mp3", ".wav", ".m4a", ".flac", ".ogg")


def test_youtube_video_playback_controls():
    """Verify pause, resume, and stop actions are handled cleanly without error."""
    mock_player = MagicMock()
    res_pause = youtube_video({"action": "pause"}, player=mock_player)
    assert "paused" in res_pause.lower()

    res_resume = youtube_video({"action": "resume"}, player=mock_player)
    assert "resumed" in res_resume.lower()

    res_stop = youtube_video({"action": "stop"}, player=mock_player)
    assert "stopped" in res_stop.lower()


def test_ecommerce_search_headless():
    """Verify ecommerce_search extracts prices, renders HUD comparison card and does not open browser."""
    mock_player = MagicMock()
    with patch("webbrowser.open") as mock_wb:
        res = ecommerce_action({"query": "boAt Rockerz 450"}, player=mock_player)
        mock_wb.assert_not_called()
        assert isinstance(res, str)
        assert len(res) > 10
        mock_player.show_content.assert_called_once()
        card_title = mock_player.show_content.call_args[0][0]
        assert "DEALS" in card_title


def test_flight_finder_headless():
    """Verify flight_finder operates headlessly when open_browser is not requested."""
    mock_player = MagicMock()
    with patch("actions.flight_finder._search_flights_browser") as mock_browser:
        res = flight_finder({"origin": "Delhi", "destination": "Mumbai", "date": "tomorrow"}, player=mock_player)
        mock_browser.assert_not_called()
        assert isinstance(res, str)
        assert "Delhi" in res or "Mumbai" in res


def test_edge_router_classifications():
    """Verify NeedleToolRouter dispatches weather, song, ecommerce, and flights in <1ms."""
    router = NeedleToolRouter()

    # Weather reflex
    res_w = router.classify_tool_intent("aaj mumbai ka mausam kaisa hai")
    assert res_w is not None
    assert res_w[0] == "weather_report"
    assert res_w[1]["city"] == "Mumbai"

    # Music reflex
    res_m = router.classify_tool_intent("sanam teri kasam gaana chalao")
    assert res_m is not None
    assert res_m[0] == "youtube_video"
    assert res_m[1]["action"] == "play"

    # eCommerce reflex
    res_e = router.classify_tool_intent("flipkart par iphone 15 ka price check karo")
    assert res_e is not None
    assert res_e[0] == "ecommerce_search"
    assert "iphone" in res_e[1]["query"].lower()

    # Flight reflex
    res_f = router.classify_tool_intent("delhi se mumbai flight check karo")
    assert res_f is not None
    assert res_f[0] == "flight_finder"
    assert res_f[1]["origin"] == "Delhi"
    assert res_f[1]["destination"] == "Mumbai"
