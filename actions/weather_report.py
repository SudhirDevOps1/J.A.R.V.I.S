import webbrowser
from urllib.parse import quote_plus


def _default_city() -> str:
    """ADDITIVE: param city na ho to memory identity -> IP location. Never raises."""
    try:
        from memory.memory_manager import load_memory
        ident = (load_memory().get("identity", {}) or {})
        city = ident.get("city", {})
        city = (city.get("value", "") if isinstance(city, dict) else str(city or "")).strip()
        if city:
            return city
    except Exception:
        pass
    try:
        from core.system_info import get_ip_location
        loc = get_ip_location() or {}
        city = str(loc.get("city", "") or "").strip()
        if city:
            return city
    except Exception:
        pass
    return ""


def weather_action(
    parameters: dict,
    player=None,
    session_memory=None,
) -> str:
    city     = parameters.get("city")
    when     = parameters.get("time", "today")

    if not city or not isinstance(city, str) or not city.strip():
        # ADDITIVE: bina city ke dead-end nahi — memory/IP se uthao (purana msg fallback rakha)
        city = _default_city()
    if not city or not isinstance(city, str) or not city.strip():
        msg = "Sir, the city is missing for the weather report."
        _log(msg, player)
        return msg

    city = city.strip()
    when = (when or "today").strip()

    # Instant live weather from Open-Meteo (0 tokens, 100% free)
    w_data = {}
    try:
        from core.system_info import get_free_weather
        w_data = get_free_weather(city=city)
    except Exception:
        pass

    resolved_city = w_data.get("city", city) if w_data.get("success") else city
    temp = w_data.get("temp", "--")
    desc = w_data.get("desc", "Conditions clear")
    feels = w_data.get("feels_like", temp)
    wind = w_data.get("wind", "--")
    humidity = w_data.get("humidity", "--")
    pressure = w_data.get("pressure", "--")
    icon = w_data.get("icon", "⛅")

    # Format Cyber-HUD Display Card
    card_lines = [
        f"╔══════════════════════════════════════════════════════════════╗",
        f"  ATMOSPHERIC TELEMETRY: {resolved_city.upper()}",
        f"╚══════════════════════════════════════════════════════════════╝",
        f"",
        f"  STATUS       : {icon}  {desc}",
        f"  TEMPERATURE  : {temp} (Feels like: {feels})",
        f"  HUMIDITY     : {humidity}",
        f"  WIND SPEED   : {wind}",
        f"  AIR PRESSURE : {pressure}",
        f"  TIMEFRAME    : {when.title()}",
        f"  DATA SOURCE  : Open-Meteo High-Resolution Satellite & Radar",
        f"",
        f"  [Headless Telemetry Active — 0 Browser Overhead]",
    ]
    card_text = "\n".join(card_lines)

    if player and hasattr(player, "show_content"):
        try:
            player.show_content(f"WEATHER — {resolved_city.upper()}", card_text)
        except Exception:
            pass

    search_query = f"weather in {resolved_city} {when}"
    url = f"https://www.google.com/search?q={quote_plus(search_query)}"

    # Headless Default: Only open browser if explicitly asked
    open_browser = bool(
        parameters.get("open_browser")
        or "browser" in str(parameters.get("query", "")).lower()
        or "browser" in str(parameters.get("raw_text", "")).lower()
    )

    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    if w_data.get("success"):
        msg = (
            f"Sir, in {resolved_city} it's currently {temp} with {desc}. "
            f"Feels like {feels}, humidity is {humidity}, and wind is {wind}."
        )
        if open_browser:
            msg += " Showing satellite forecast in browser, sir."
    else:
        msg = f"Showing the weather for {resolved_city}, {when}, sir."
        if open_browser:
            msg += " Opening browser."

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
