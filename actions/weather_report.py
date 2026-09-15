import webbrowser
from urllib.parse import quote_plus


def weather_action(
    parameters: dict,
    player=None,
    session_memory=None,
) -> str:
    city     = parameters.get("city")
    when     = parameters.get("time", "today")  

    if not city or not isinstance(city, str) or not city.strip():
        msg = "Sir, the city is missing for the weather report."
        _log(msg, player)
        return msg

    city = city.strip()
    when = (when or "today").strip()

    # Instant live weather from Open-Meteo (0 tokens, 100% free)
    live_info = ""
    try:
        from core.system_info import get_free_weather
        w_data = get_free_weather(city=city)
        if w_data.get("success"):
            live_info = f"Current weather in {w_data.get('city', city)}: {w_data.get('temp')} with {w_data.get('desc')} and wind at {w_data.get('wind')}."
    except Exception:
        pass

    search_query  = f"weather in {city} {when}"
    url           = f"https://www.google.com/search?q={quote_plus(search_query)}"

    try:
        webbrowser.open(url)
    except Exception:
        pass

    if live_info:
        msg = f"{live_info} Showing full forecast in browser, sir."
    else:
        msg = f"Showing the weather for {city}, {when}, sir."

    _log(msg, player)

    if session_memory:
        try:
            session_memory.set_last_search(query=search_query, response=msg)
        except Exception:
            pass

    return msg


def _log(message: str, player=None) -> None:
    print(f"[Weather] {message}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "weather_report",
    "description": "Gives the weather report to user",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "city": {
                "type": "STRING",
                "description": "City name"
            }
        },
        "required": [
            "city"
        ]
    },
    "handler": weather_action,
}
