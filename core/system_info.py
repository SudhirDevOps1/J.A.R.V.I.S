"""
System info, storage analyzer, and free Open-Meteo weather utility.
Requires 0 tokens and 0 API keys.
"""
from __future__ import annotations

import os
import shutil
import string
from typing import Optional
import psutil
import requests


def get_drive_stats() -> list[dict]:
    """Get all connected disk drives with total, used, and free space."""
    drives = []
    # Check drive letters on Windows
    for letter in string.ascii_uppercase:
        drive_path = f"{letter}:\\"
        if os.path.exists(drive_path):
            try:
                usage = psutil.disk_usage(drive_path)
                total_gb = round(usage.total / (1024 ** 3), 1)
                used_gb  = round(usage.used / (1024 ** 3), 1)
                free_gb  = round(usage.free / (1024 ** 3), 1)
                pct      = round(usage.percent, 1)
                drives.append({
                    "drive": drive_path,
                    "letter": f"{letter}:",
                    "total_gb": total_gb,
                    "used_gb": used_gb,
                    "free_gb": free_gb,
                    "percent": pct,
                })
            except Exception:
                continue
    return drives


def get_free_weather(lat: float = 28.6139, lon: float = 77.2090, city: str = "New Delhi") -> dict:
    """Fetch current weather from Open-Meteo API (100% Free, NO API key, 0 tokens)."""
    try:
        # If city name given, resolve coords via geocoding
        if city and city.lower() != "new delhi":
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
            g_resp = requests.get(geo_url, timeout=3.0)
            if g_resp.status_code == 200:
                results = g_resp.json().get("results", [])
                if results:
                    lat = results[0]["latitude"]
                    lon = results[0]["longitude"]
                    city = results[0].get("name", city)

        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&current_weather=true"
            f"&hourly=relativehumidity_2m&timezone=auto"
        )
        resp = requests.get(url, timeout=4.0)
        if resp.status_code == 200:
            data = resp.json()
            cw = data.get("current_weather", {})
            temp = cw.get("temperature", "--")
            wind = cw.get("windspeed", "--")
            wcode = cw.get("weathercode", 0)
            
            # WMO Weather interpretation code
            weather_desc = "Clear sky"
            if wcode in (1, 2, 3):
                weather_desc = "Mainly clear / Partly cloudy"
            elif wcode in (45, 48):
                weather_desc = "Fog"
            elif wcode in (51, 53, 55, 61, 63, 65):
                weather_desc = "Rain / Showers"
            elif wcode in (71, 73, 75):
                weather_desc = "Snow"
            elif wcode in (95, 96, 99):
                weather_desc = "Thunderstorm"

            return {
                "city": city,
                "temp": f"{temp}°C",
                "wind": f"{wind} km/h",
                "desc": weather_desc,
                "success": True,
            }
    except Exception as e:
        return {"success": False, "error": str(e), "city": city}

    return {"success": False, "error": "Weather fetch failed", "city": city}


def get_core_telemetry() -> dict:
    """CPU, RAM, and Battery percentage."""
    try:
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        battery = psutil.sensors_battery()
        bat_pct = round(battery.percent) if battery else None
        return {
            "cpu_percent": cpu,
            "ram_percent": ram,
            "battery_percent": bat_pct,
        }
    except Exception:
        return {"cpu_percent": 0.0, "ram_percent": 0.0, "battery_percent": None}


_news_cache: dict = {"time": 0.0, "data": []}

def fetch_top_dev_news(limit: int = 3) -> list[dict]:
    """
    Fetch top developer & tech headlines from HackerNews API.
    100% Free, NO API Key, 0 LLM tokens, 10-minute cache.
    """
    import time
    global _news_cache
    now = time.time()
    if _news_cache["data"] and (now - _news_cache["time"] < 600):
        return _news_cache["data"]

    items = []
    try:
        top_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        resp = requests.get(top_url, timeout=3.0)
        if resp.status_code == 200:
            story_ids = resp.json()[:limit]
            for sid in story_ids:
                try:
                    s_resp = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=2.0)
                    if s_resp.status_code == 200:
                        s_data = s_resp.json()
                        title = s_data.get("title", "")
                        url = s_data.get("url", "")
                        score = s_data.get("score", 0)
                        if title:
                            items.append({"title": title, "url": url, "score": score})
                except Exception:
                    continue
        if items:
            _news_cache = {"time": now, "data": items}
            return items
    except Exception:
        pass

    return _news_cache.get("data") or [{"title": "DevOps & AI Core Ready", "url": "", "score": 100}]


_ip_cache: dict = {"time": 0.0, "data": {}}

def get_ip_location() -> dict:
    """Get location/ISP info via free ip-api.com (0 keys, 0 tokens, 30-min cache)."""
    import time
    global _ip_cache
    now = time.time()
    if _ip_cache["data"] and (now - _ip_cache["time"] < 1800):
        return _ip_cache["data"]

    try:
        resp = requests.get("http://ip-api.com/json/?fields=status,city,country,isp,query", timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                res = {
                    "city": data.get("city", "Unknown"),
                    "country": data.get("country", "Unknown"),
                    "isp": data.get("isp", "Local"),
                    "ip": data.get("query", "127.0.0.1"),
                }
                _ip_cache = {"time": now, "data": res}
                return res
    except Exception:
        pass
    return {"city": "New Delhi", "country": "India", "isp": "Local", "ip": "127.0.0.1"}

