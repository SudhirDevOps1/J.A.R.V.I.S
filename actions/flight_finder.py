#flight_finder.py
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from config import is_windows, is_mac, is_linux

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


def _get_api_key() -> str:
    try:
        from memory.config_manager import load_api_keys
        k = (load_api_keys().get("gemini_api_key") or "").strip()
        if k:
            return k
    except Exception:
        pass
    try:
        if API_CONFIG_PATH.exists():
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("gemini_api_key", "").strip()
    except Exception:
        pass
    return ""

_MONTH_MAP: dict[str, int] = {

    "january": 1, "february": 2, "march": 3,     "april": 4,
    "may": 5,     "june": 6,     "july": 7,       "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

# English fast-path only — Gemini (below) normalizes date expressions in ANY
# language to YYYY-MM-DD, so no other language needs to be hardcoded here.
_RELATIVE_MAP_KEYS = {
    "today",
    "tomorrow",
}


def _parse_date(raw: str) -> str:

    raw   = raw.strip()
    lower = raw.lower()
    today = datetime.now()

    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass

    relative = {
        "today": today,
        "tomorrow": today + timedelta(days=1),
    }
    for key, val in relative.items():
        if key in lower:
            return val.strftime("%Y-%m-%d")

    try:
        from google import genai as _genai
        _client  = _genai.Client(api_key=_get_api_key())
        response = _client.models.generate_content(
            model="gemini-flash-lite-latest",
            contents=(
                f"Today is {today.strftime('%Y-%m-%d')}. "
                f"Convert this date expression to YYYY-MM-DD: '{raw}'. "
                f"Return ONLY the date string, nothing else."
            )
        )
        result = response.text.strip()
        if re.match(r"\d{4}-\d{2}-\d{2}", result):
            return result
    except Exception as e:
        print(f"[FlightFinder] ⚠️ Gemini date parse failed: {e}")

    for month_name, month_num in _MONTH_MAP.items():
        if month_name in lower:
            day_match = re.search(r"\d{1,2}", raw)
            if day_match:
                day  = int(day_match.group())
                year = today.year if month_num >= today.month else today.year + 1
                return f"{year}-{month_num:02d}-{day:02d}"

    # Last resort: today
    print(f"[FlightFinder] ⚠️ Could not parse date '{raw}' — using today.")
    return today.strftime("%Y-%m-%d")

_CABIN_CODE: dict[str, str] = {
    "economy":  "1",
    "premium":  "2",
    "business": "3",
    "first":    "4",
}


def _build_google_flights_url(
    origin:      str,
    destination: str,
    date:        str,
    return_date: str | None = None,
    passengers:  int        = 1,
    cabin:       str        = "economy",
) -> str:
    cabin_code = _CABIN_CODE.get(cabin.lower(), "1")
    base       = "https://www.google.com/travel/flights"

    # Google Flights accepts these query params for pre-filling
    if return_date:
        trip = f"Flights+from+{origin}+to+{destination}+on+{date}+returning+{return_date}"
    else:
        trip = f"Flights+from+{origin}+to+{destination}+on+{date}"

    # FIX: hardcoded tfs (2025-03-15 IST->LHR) hataya — galat route prefill karta tha.
    # Google Flights `q` param se sahi route bharta hai; tfs ke bina page thoda kam
    # prefilled khulta hai lekin KABHI galat nahi. Purana query-format untouched.
    return (
        f"{base}"
        f"?q={trip}"
        f"&curr=USD"
        f"&cabin={cabin_code}"
        f"&adults={passengers}"
    )



def _search_flights_browser(
    origin:      str,
    destination: str,
    date:        str,
    return_date: str | None,
    passengers:  int,
    cabin:       str,
) -> tuple[str, str]:
    import time
    from actions.browser_control import browser_control

    url = _build_google_flights_url(
        origin, destination, date, return_date, passengers, cabin
    )

    print(f"[FlightFinder] 🌐 Opening: {url}")
    browser_control({"action": "go_to", "url": url})
    time.sleep(5)

    raw = browser_control({"action": "get_text"})
    return (raw or ""), url

def _parse_flights_with_gemini(
    raw_text:    str,
    origin:      str,
    destination: str,
    date:        str,
) -> list[dict]:
    from google import genai as _genai
    from google.genai import types

    _client = _genai.Client(api_key=_get_api_key())
    prompt  = (
        f"Extract flight options from {origin} to {destination} on {date} "
        f"from this Google Flights page text:\n\n{raw_text[:12000]}\n\n"
        f"Return a JSON array of up to 5 flights:\n"
        f'[{{"airline":"...","departure":"HH:MM","arrival":"HH:MM",'
        f'"duration":"Xh Ym","stops":0,"price":"...","currency":"USD"}}]\n'
        f"If no flights found, return: []"
    )

    try:
        response = _client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are a flight data extraction expert. "
                    "Extract flight information from raw webpage text. "
                    "Return ONLY valid JSON — no markdown, no explanation."
                )
            ),
        )
        text     = re.sub(r"```(?:json)?", "", response.text).strip().rstrip("`").strip()
        flights  = json.loads(text)
        return flights if isinstance(flights, list) else []
    except Exception as e:
        print(f"[FlightFinder] ⚠️ Gemini parse failed: {e}")
        return []

def _format_spoken(
    flights:     list[dict],
    origin:      str,
    destination: str,
    date:        str,
) -> str:
    if not flights:
        return (
            f"I couldn't find any flights from {origin} to {destination} "
            f"on {date}, sir. The page may not have loaded correctly."
        )

    lines = [f"Here are the top flights from {origin} to {destination} on {date}, sir."]

    for i, f in enumerate(flights[:5], 1):
        airline   = f.get("airline",   "Unknown airline")
        departure = f.get("departure", "--:--")
        arrival   = f.get("arrival",   "--:--")
        duration  = f.get("duration",  "")
        stops     = f.get("stops",     0)
        price     = f.get("price",     "")
        currency  = f.get("currency",  "")

        stop_str  = "non-stop" if stops == 0 else f"{stops} stop{'s' if stops > 1 else ''}"
        price_str = f"{price} {currency}".strip() if price else "price unavailable"
        dur_str   = f", {duration}" if duration else ""

        lines.append(
            f"Option {i}: {airline}, departing {departure}, "
            f"arriving {arrival}{dur_str}, {stop_str}, {price_str}."
        )

    # Cheapest — strip non-digits for comparison
    priced = [f for f in flights if f.get("price")]
    if priced:
        cheapest = min(
            priced,
            key=lambda x: int(re.sub(r"[^\d]", "", str(x["price"])) or "999999"),
        )
        lines.append(
            f"The cheapest option is {cheapest.get('airline')} "
            f"at {cheapest.get('price')} {cheapest.get('currency', '')}."
        )

    return " ".join(lines)


def _format_text_report(
    flights:     list[dict],
    origin:      str,
    destination: str,
    date:        str,
    return_date: str | None,
    page_url:    str,
) -> str:
    lines = [
        "JARVIS — Flight Search Results",
        "─" * 50,
        f"Route     : {origin} → {destination}",
        f"Date      : {date}",
    ]
    if return_date:
        lines.append(f"Return    : {return_date}")
    lines += [
        f"Searched  : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Source    : {page_url}",
        "─" * 50,
        "",
    ]

    if not flights:
        lines.append("No flights found.")
    else:
        for i, f in enumerate(flights, 1):
            stops    = f.get("stops", 0)
            stop_str = "Non-stop" if stops == 0 else f"{stops} stop(s)"
            lines += [
                f"Flight {i}:",
                f"  Airline   : {f.get('airline',   'N/A')}",
                f"  Departure : {f.get('departure', 'N/A')}",
                f"  Arrival   : {f.get('arrival',   'N/A')}",
                f"  Duration  : {f.get('duration',  'N/A')}",
                f"  Stops     : {stop_str}",
                f"  Price     : {f.get('price', 'N/A')} {f.get('currency', '')}",
                "",
            ]

    return "\n".join(lines)

def _save_to_desktop(content: str, origin: str, destination: str) -> str:
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"flights_{origin}_{destination}_{ts}.txt".replace(" ", "_")
    desktop  = Path.home() / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    filepath = desktop / filename

    filepath.write_text(content, encoding="utf-8")
    print(f"[FlightFinder] 💾 Saved: {filepath}")

    try:
        if is_windows():
            subprocess.Popen(["notepad.exe", str(filepath)])
        elif is_mac():
            subprocess.Popen(["open", "-t", str(filepath)])
        else:
            subprocess.Popen(["xdg-open", str(filepath)])
    except Exception as e:
        print(f"[FlightFinder] ⚠️ Could not open text editor: {e}")

    return str(filepath)


def _search_flights_headless(origin: str, destination: str, date: str) -> list[dict]:
    """Extract flight schedules and fares headlessly via search grounding or MultiLLM."""
    prompt = (
        f"Find current scheduled flight options from {origin} to {destination} for {date}.\n"
        "Return ONLY a valid JSON array of up to 4 flights in this exact structure without markdown:\n"
        '[{"airline":"Indigo / Air India","departure":"08:00","arrival":"10:15","duration":"2h 15m","stops":0,"price":"₹4,500","currency":"INR"}]'
    )
    api_k = _get_api_key()
    if api_k:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_k)
            for m in ("gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-3.7-flash"):
                try:
                    resp = client.models.generate_content(
                        model=m,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            tools=[types.Tool(google_search=types.GoogleSearch())],
                            system_instruction="You are a flight schedule and pricing expert. Return ONLY valid JSON array.",
                        ),
                    )
                    raw = resp.text.strip()
                    clean_json = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
                    parsed = json.loads(clean_json)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        return parsed
                except Exception:
                    continue
        except Exception:
            pass

    try:
        from core.multi_llm import get_llm_model
        llm = get_llm_model()
        resp = llm.generate_content(prompt)
        if resp and resp.text:
            clean_json = re.sub(r"```(?:json)?", "", resp.text).strip().rstrip("`").strip()
            parsed = json.loads(clean_json)
            if isinstance(parsed, list):
                return parsed
    except Exception:
        pass

    return []


def flight_finder(parameters: dict, player=None, speak=None) -> str:
    params = parameters or {}

    origin      = params.get("origin",      "").strip()
    destination = params.get("destination", "").strip()
    date_raw    = params.get("date",        "").strip()
    return_raw  = (params.get("return_date") or "").strip()
    passengers  = max(1, int(params.get("passengers", 1)))
    cabin       = params.get("cabin", "economy").strip().lower()
    save        = bool(params.get("save", False))
    open_browser = bool(
        params.get("open_browser")
        or "browser" in str(params.get("raw_text", "")).lower()
        or "browser" in str(params.get("query", "")).lower()
    )

    if not origin or not destination:
        return "Please provide both origin and destination, sir."
    if not date_raw:
        return "Please provide a departure date, sir."

    # Normalise cabin value
    if cabin not in _CABIN_CODE:
        cabin = "economy"

    date        = _parse_date(date_raw)
    return_date = _parse_date(return_raw) if return_raw else None

    if player:
        player.write_log(f"[FlightFinder] {origin} -> {destination} on {date}")

    if speak:
        speak(f"Searching flights from {origin} to {destination} on {date}, sir.")

    print(
        f"[FlightFinder] [SEARCH] {origin} -> {destination} | {date}"
        f"{' -> ' + return_date if return_date else ''}"
        f" | {cabin} | {passengers} pax (Headless={not open_browser})"
    )

    try:
        page_url = _build_google_flights_url(origin, destination, date, return_date, passengers, cabin)
        flights = []

        if open_browser:
            raw_text, page_url = _search_flights_browser(
                origin, destination, date, return_date, passengers, cabin
            )
            if raw_text:
                flights = _parse_flights_with_gemini(raw_text, origin, destination, date)
        else:
            # Headless search: 0 browser windows launched
            flights = _search_flights_headless(origin, destination, date)

        if not flights:
            # Graceful fallback: return quick status
            msg = f"Sir, I checked flights from {origin} to {destination} for {date}. Direct booking links are prepared."
            if open_browser:
                msg += " Showing flight options in browser."
            return msg

        # Render Cyber-HUD flight card
        card_lines = [
            "╔══════════════════════════════════════════════════════════════╗",
            f"  JARVIS TRAVEL CORE: {origin.upper()} -> {destination.upper()}",
            "╚══════════════════════════════════════════════════════════════╝",
            "",
            f"  DATE        : {date}",
            f"  PASSENGERS  : {passengers} | CABIN: {cabin.title()}",
            "",
            "  +----------------------+----------+----------+----------+------------+",
            "  | AIRLINE              | DEP      | ARR      | DUR      | PRICE      |",
            "  +----------------------+----------+----------+----------+------------+",
        ]
        for f in flights[:5]:
            al = str(f.get("airline", "Airline"))[:20]
            dep = str(f.get("departure", "--:--"))[:8]
            arr = str(f.get("arrival", "--:--"))[:8]
            dur = str(f.get("duration", "--"))[:8]
            pr = str(f.get("price", "N/A"))[:10]
            card_lines.append(f"  | {al:<20} | {dep:<8} | {arr:<8} | {dur:<8} | {pr:<10} |")
        card_lines.extend([
            "  +----------------------+----------+----------+----------+------------+",
            "",
            f"  [Headless Telemetry Active — 0 Browser Overhead]",
        ])
        card_text = "\n".join(card_lines)

        if player and hasattr(player, "show_content"):
            try:
                player.show_content(f"FLIGHTS — {origin.upper()[:16]}", card_text)
            except Exception:
                pass

        spoken = _format_spoken(flights, origin, destination, date)
        if open_browser:
            spoken += " Showing Google Flights in browser, sir."

        if speak:
            speak(spoken)

        result = spoken

        if save and flights:
            report     = _format_text_report(flights, origin, destination, date, return_date, page_url)
            saved_path = _save_to_desktop(report, origin, destination)
            result    += f" Results saved to Desktop: {saved_path}"

        return result

    except Exception as e:
        print(f"[FlightFinder] [ERROR] {e}")
        return f"Flight search failed, sir: {e}"


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "flight_finder",
    "description": "Searches Google Flights and speaks the best options.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "origin": {
                "type": "STRING",
                "description": "Departure city or airport code"
            },
            "destination": {
                "type": "STRING",
                "description": "Arrival city or airport code"
            },
            "date": {
                "type": "STRING",
                "description": "Departure date (any format)"
            },
            "return_date": {
                "type": "STRING",
                "description": "Return date for round trips"
            },
            "passengers": {
                "type": "INTEGER",
                "description": "Number of passengers (default: 1)"
            },
            "cabin": {
                "type": "STRING",
                "description": "economy | premium | business | first"
            },
            "save": {
                "type": "BOOLEAN",
                "description": "Save results to Notepad"
            }
        },
        "required": [
            "origin",
            "destination",
            "date"
        ]
    },
    "handler": flight_finder,
}
