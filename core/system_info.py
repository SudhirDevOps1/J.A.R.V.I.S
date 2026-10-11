"""
System info, storage analyzer, hyper-local Open-Meteo weather, and free Open APIs.
Requires 0 tokens and 0 API keys.
"""
from __future__ import annotations

import os
import shutil
import string
import socket
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional
import psutil
import requests


def get_drive_stats() -> list[dict]:
    """Get all connected disk drives with total, used, and free space."""
    drives = []
    for letter in string.ascii_uppercase:
        drive_path = f"{letter}:\\"
        if os.path.exists(drive_path):
            try:
                usage = psutil.disk_usage(drive_path)
                total_gb = round(usage.total / (1024 ** 3), 1)
                used_gb  = round(usage.used / (1024 ** 3), 1)
                free_gb  = round(usage.free / (1024 ** 3), 1)
                pct      = round(usage.percent, 1)

                label = "System" if letter == "C" else "Storage"
                drives.append({
                    "drive": drive_path,
                    "letter": f"{letter}:",
                    "label": label,
                    "total_gb": total_gb,
                    "used_gb": used_gb,
                    "free_gb": free_gb,
                    "percent": pct,
                })
            except Exception:
                continue
    return drives


_ip_cache: dict = {"time": 0.0, "data": {}}

def get_ip_location() -> dict:
    """Get rich location & ISP info via multi-tier free geo APIs (0 keys, 0 tokens, 15-min cache)."""
    global _ip_cache
    now = time.time()
    if _ip_cache["data"] and (now - _ip_cache["time"] < 900):
        return _ip_cache["data"]

    # Tier 1: ip-api.com
    try:
        url = "http://ip-api.com/json/?fields=status,city,regionName,country,isp,query,lat,lon,timezone"
        resp = requests.get(url, timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                res = {
                    "city": data.get("city", "Local"),
                    "region": data.get("regionName", ""),
                    "country": data.get("country", "Earth"),
                    "isp": data.get("isp", "Local Network"),
                    "ip": data.get("query", "127.0.0.1"),
                    "lat": float(data.get("lat", 28.6139)),
                    "lon": float(data.get("lon", 77.2090)),
                    "timezone": data.get("timezone", "UTC"),
                }
                _ip_cache = {"time": now, "data": res}
                return res
    except Exception:
        pass

    # Tier 2: ipwho.is
    try:
        resp = requests.get("https://ipwho.is/", timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success", False):
                res = {
                    "city": data.get("city", "Local"),
                    "region": data.get("region", ""),
                    "country": data.get("country", "Earth"),
                    "isp": (data.get("connection") or {}).get("isp", "Local Network"),
                    "ip": data.get("ip", "127.0.0.1"),
                    "lat": float(data.get("latitude", 28.6139)),
                    "lon": float(data.get("longitude", 77.2090)),
                    "timezone": (data.get("timezone") or {}).get("id", "UTC"),
                }
                _ip_cache = {"time": now, "data": res}
                return res
    except Exception:
        pass

    fallback = {
        "city": "Local Station",
        "region": "System",
        "country": "Online",
        "isp": "Active ISP",
        "ip": "127.0.0.1",
        "lat": 28.6139,
        "lon": 77.2090,
        "timezone": "Asia/Kolkata",
    }
    return _ip_cache.get("data") or fallback


def get_network_latency() -> dict:
    """Measure live internet ping latency via low-overhead DNS socket test."""
    targets = [("1.1.1.1", 53), ("8.8.8.8", 53)]
    for host, port in targets:
        try:
            t0 = time.perf_counter()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.5)
            s.connect((host, port))
            s.close()
            ms = round((time.perf_counter() - t0) * 1000.0, 1)
            return {"online": True, "ping_ms": ms, "status": f"{ms:.0f} ms"}
        except Exception:
            continue
    return {"online": False, "ping_ms": 999.0, "status": "Offline / Slow"}


def get_free_weather(lat: float = None, lon: float = None, city: str = None) -> dict:
    """
    Fetch hyper-local weather from Open-Meteo API (100% Free, NO API key, 0 tokens).
    If city is provided, resolves exact latitude/longitude via Open-Meteo geocoding API.
    If coordinates and city are not provided, auto-resolves via user's live IP geo-location.
    """
    try:
        resolved_city = city
        resolved_region = ""
        resolved_country = ""

        # If a specific city is requested, resolve coordinates via Open-Meteo Geocoding
        if city and (lat is None or lon is None):
            try:
                from urllib.parse import quote_plus
                geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={quote_plus(city.strip())}&count=1&language=en&format=json"
                geo_resp = requests.get(geo_url, timeout=3.0)
                if geo_resp.status_code == 200:
                    geo_data = geo_resp.json()
                    results = geo_data.get("results")
                    if results and len(results) > 0:
                        top = results[0]
                        lat = float(top.get("latitude"))
                        lon = float(top.get("longitude"))
                        resolved_city = top.get("name", city)
                        resolved_region = top.get("admin1", "")
                        resolved_country = top.get("country", "")
            except Exception:
                pass

        # Fallback to IP geolocation if still None
        if lat is None or lon is None:
            loc = get_ip_location()
            lat = loc.get("lat", 28.6139)
            lon = loc.get("lon", 77.2090)
            if not resolved_city:
                resolved_city = loc.get("city", "Local")
            if not resolved_region:
                resolved_region = loc.get("region", "")
            if not resolved_country:
                resolved_country = loc.get("country", "")

        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&current_weather=true"
            f"&hourly=relativehumidity_2m,apparent_temperature,surface_pressure,precipitation_probability"
            f"&timezone=auto"
        )
        resp = requests.get(url, timeout=4.0)
        if resp.status_code == 200:
            data = resp.json()
            cw = data.get("current_weather", {})
            temp = cw.get("temperature", "--")
            wind = cw.get("windspeed", "--")
            wcode = cw.get("weathercode", 0)

            # Extract first hourly humidity and apparent temp if available
            hourly = data.get("hourly", {})
            h_hum = hourly.get("relativehumidity_2m", [])
            h_app = hourly.get("apparent_temperature", [])
            h_prs = hourly.get("surface_pressure", [])

            humidity = f"{h_hum[0]}%" if h_hum else "--"
            feels_like = f"{h_app[0]}°C" if h_app else f"{temp}°C"
            pressure = f"{round(h_prs[0])} hPa" if h_prs else "--"

            # WMO Weather interpretation code & emojis
            weather_desc = "Clear Sky"
            weather_icon = "☀️"
            if wcode in (1, 2, 3):
                weather_desc = "Partly Cloudy"
                weather_icon = "⛅"
            elif wcode in (45, 48):
                weather_desc = "Fog / Hazy"
                weather_icon = "🌫️"
            elif wcode in (51, 53, 55, 61, 63, 65, 80, 81):
                weather_desc = "Rain Showers"
                weather_icon = "🌧️"
            elif wcode in (71, 73, 75, 85, 86):
                weather_desc = "Snowing"
                weather_icon = "❄️"
            elif wcode in (95, 96, 99):
                weather_desc = "Thunderstorm"
                weather_icon = "⛈️"

            return {
                "city": resolved_city or city or "Local",
                "region": resolved_region,
                "country": resolved_country,
                "temp": f"{temp}°C",
                "feels_like": feels_like,
                "wind": f"{wind} km/h",
                "humidity": humidity,
                "pressure": pressure,
                "desc": weather_desc,
                "icon": weather_icon,
                "success": True,
            }
    except Exception as e:
        return {"success": False, "error": str(e), "city": city or "Local"}

    return {"success": False, "error": "Weather service unreachable", "city": city or "Local"}


def get_hardware_telemetry() -> dict:
    """Live CPU, RAM (used/total), Battery, and Uptime telemetry."""
    try:
        cpu = psutil.cpu_percent(interval=None)
        cpu_cores = psutil.cpu_count(logical=True) or 4
        vm = psutil.virtual_memory()
        ram_used_gb = round(vm.used / (1024 ** 3), 1)
        ram_total_gb = round(vm.total / (1024 ** 3), 1)
        ram_pct = vm.percent

        battery = psutil.sensors_battery()
        bat_pct = round(battery.percent) if battery else None
        bat_plugged = battery.power_plugged if battery else True

        # System boot uptime
        boot_ts = psutil.boot_time()
        uptime_sec = max(0, int(time.time() - boot_ts))
        hours = uptime_sec // 3600
        mins = (uptime_sec % 3600) // 60
        uptime_str = f"{hours}h {mins}m"

        return {
            "cpu_percent": cpu,
            "cpu_cores": cpu_cores,
            "ram_used_gb": ram_used_gb,
            "ram_total_gb": ram_total_gb,
            "ram_percent": ram_pct,
            "battery_percent": bat_pct,
            "battery_plugged": bat_plugged,
            "uptime_str": uptime_str,
        }
    except Exception:
        return {
            "cpu_percent": 0.0,
            "cpu_cores": 4,
            "ram_used_gb": 0.0,
            "ram_total_gb": 0.0,
            "ram_percent": 0.0,
            "battery_percent": None,
            "battery_plugged": True,
            "uptime_str": "--",
        }


_news_cache: dict = {"time": 0.0, "data": []}

def fetch_top_dev_news(limit: int = 3) -> list[dict]:
    """
    Fetch top developer & tech headlines from HackerNews Firebase API.
    100% Free, NO API Key, 0 LLM tokens, 10-minute cache.
    """
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
                        by = s_data.get("by", "author")
                        if title:
                            items.append({"title": title, "url": url, "score": score, "by": by})
                except Exception:
                    continue
        if items:
            _news_cache = {"time": now, "data": items}
            return items
    except Exception:
        pass

    fallback = [
        {"title": "DevOps & Autonomous Agent Architecture Live", "url": "", "score": 120, "by": "StarkDev"},
        {"title": "Open-Meteo & Free Public APIs Scale Across Systems", "url": "", "score": 98, "by": "DevCore"},
        {"title": "Zero-Token Edge Telemetry Running Locally", "url": "", "score": 85, "by": "JARVIS"},
    ]
    return _news_cache.get("data") or fallback


_rss_news_cache: dict = {"time": 0.0, "data": []}

def fetch_live_rss_news(limit: int = 5) -> list[dict]:
    """
    Fetch live real-world news headlines from verified RSS feeds (Google News India & BBC World).
    100% Free, NO API Key, 0 LLM tokens, 10-minute cache.
    """
    global _rss_news_cache
    now = time.time()
    if _rss_news_cache["data"] and (now - _rss_news_cache["time"] < 600):
        return _rss_news_cache["data"]

    feeds = [
        ("Google News", "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"),
        ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ]
    results = []
    for source_name, feed_url in feeds:
        try:
            req = urllib.request.Request(
                feed_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=3.5) as response:
                content = response.read()
            root = ET.fromstring(content)
            for item in root.findall(".//item"):
                title_elem = item.find("title")
                link_elem = item.find("link")
                title = (title_elem.text if title_elem is not None and title_elem.text else "").strip()
                link = (link_elem.text if link_elem is not None and link_elem.text else "").strip()
                if title and not any(r["title"] == title for r in results):
                    results.append({"title": title, "url": link, "source": source_name})
                if len(results) >= limit:
                    break
        except Exception:
            continue
        if len(results) >= limit:
            break

    if results:
        _rss_news_cache = {"time": now, "data": results}
        return results

    # Graceful fallback to dev news if RSS is blocked by ISP
    dev_items = fetch_top_dev_news(limit)
    return [{"title": d["title"], "url": d.get("url", ""), "source": "TechNews"} for d in dev_items]

