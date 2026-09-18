"""
actions/api_sniffer.py -- The Dynamic API Sniffer & Reverse-Engineering Engine.

Uses Playwright native network interception + requests + BeautifulSoup4 + Gemini 2.5 Flash
to silently intercept XHR/Fetch endpoints, auth headers, and JSON responses from any
web page or single-page app (SPA), auto-generating reusable Python extraction scripts.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()
OUTPUT_SCRIPTS_DIR = BASE_DIR / "config" / "generated_sniffers"
OUTPUT_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


def _get_api_key() -> str:
    path = BASE_DIR / "config" / "api_keys.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("gemini_api_key", "").strip()
        except Exception:
            pass
    return ""


def _llm_reverse_engineer(captured_traffic: List[Dict[str, Any]], target_url: str, goal: str = "") -> str:
    """Uses Gemini 2.5 Flash to inspect intercepted network requests and write a clean standalone Python script."""
    api_k = _get_api_key()
    traffic_summary = json.dumps(captured_traffic[:15], indent=2)

    prompt = f"""You are an expert reverse-engineering and API analysis agent for J.A.R.V.I.S.
The user inspected the website: {target_url}
Goal: {goal or 'Extract clean JSON/tabular data directly without opening browser'}

Here is the intercepted XHR/Fetch network traffic from the page session:
{traffic_summary}

Please analyze the traffic:
1. Identify the primary internal data API endpoints (URLs, query parameters, headers, authorization).
2. Write a clean, self-contained Python script using requests that replicates the call and prints the structured data.
3. Provide a concise 2-line explanation in Hinglish of how the API works and what was extracted.
"""
    try:
        from core.multi_llm import get_llm_model
        client = get_llm_model(model="gemini-2.5-flash")
        res = client.generate_content(prompt)
        return (res.text or "").strip()
    except Exception as e:
        return f"Gemini reverse-engineering analysis note: {e}\nCaptured {len(captured_traffic)} API endpoints."


def _get_browser_executable_or_kwargs() -> dict:
    """Finds installed Chromium-based browser (Brave, Chrome, Edge) to run Playwright headlessly without 200MB download."""
    import shutil
    candidates = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return {"executable_path": c}
    for bin_name in ("brave", "google-chrome", "chrome", "chromium", "microsoft-edge", "msedge"):
        w = shutil.which(bin_name)
        if w:
            return {"executable_path": w}
    return {}


def sniff_web_api(
    url: str,
    wait_seconds: int = 4,
    filter_keyword: str = "",
    goal: str = "",
) -> Dict[str, Any]:
    """
    Launches headless Playwright, intercepts all outgoing fetch/xhr network traffic,
    extracts JSON responses, and returns structured API maps.
    """
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    captured: List[Dict[str, Any]] = []
    page_title = ""

    async def _async_sniff():
        nonlocal page_title
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            launch_kwargs = _get_browser_executable_or_kwargs()
            try:
                browser = await p.chromium.launch(headless=True, **launch_kwargs)
            except Exception:
                browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            async def _on_response(response):
                try:
                    req = response.request
                    r_type = req.resource_type
                    if r_type in ("xhr", "fetch") or "json" in response.headers.get("content-type", "").lower():
                        r_url = response.url
                        if filter_keyword and filter_keyword.lower() not in r_url.lower():
                            return
                        try:
                            body = await response.json()
                        except Exception:
                            txt = await response.text()
                            body = txt[:500] if txt else ""

                        captured.append({
                            "url": r_url,
                            "method": req.method,
                            "status": response.status,
                            "headers": {k: v for k, v in req.headers.items() if k.lower() in ("authorization", "x-api-key", "cookie", "accept", "content-type")},
                            "post_data": req.post_data,
                            "sample_response": body,
                        })
                except Exception:
                    pass

            page.on("response", _on_response)

            try:
                await page.goto(url, wait_until="networkidle", timeout=25000)
            except Exception:
                try:
                    await page.goto(url, wait_until="load", timeout=15000)
                except Exception:
                    pass

            page_title = await page.title()
            await page.wait_for_timeout(wait_seconds * 1000)
            await browser.close()

    try:
        asyncio.run(_async_sniff())
    except Exception as e:
        print(f"[APISniffer] Playwright run note: {e}")

    # Fallback to requests + BeautifulSoup if SPA returned few network calls
    bs4_data: List[str] = []
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            for script in soup.find_all("script"):
                stext = script.string or ""
                if "api" in stext.lower() or "endpoint" in stext.lower():
                    matches = re.findall(r'https?://[^\s"\'<>]+', stext)
                    for m in matches:
                        if "api" in m.lower():
                            bs4_data.append(m)
    except Exception:
        pass

    analysis = _llm_reverse_engineer(captured, url, goal=goal)

    # Save generated sniffer script to config/generated_sniffers
    domain = urlparse(url).netloc.replace(".", "_")
    script_file = OUTPUT_SCRIPTS_DIR / f"sniffer_{domain}_{int(time.time())}.py"
    try:
        script_file.write_text(
            f"# Auto-generated reverse engineering script for {url}\n"
            f"# Generated by J.A.R.V.I.S. Dynamic API Sniffer\n\n"
            f"{analysis}\n",
            encoding="utf-8"
        )
    except Exception:
        pass

    return {
        "success": True,
        "url": url,
        "title": page_title,
        "endpoints_captured": len(captured),
        "traffic": captured[:10],
        "discovered_api_urls": bs4_data[:5],
        "analysis": analysis,
        "script_saved": str(script_file),
    }


def api_sniffer(
    parameters: dict,
    player=None,
    speak=None,
    response=None,
    session_memory=None,
) -> str:
    """Action entry point for J.A.R.V.I.S."""
    url = (parameters.get("url") or parameters.get("website") or "").strip()
    goal = (parameters.get("goal") or parameters.get("query") or "").strip()
    filter_kw = (parameters.get("filter") or "").strip()
    wait_sec = int(parameters.get("wait_seconds", 4))

    if not url:
        return "Please specify a website URL to sniff APIs from (e.g. 'sniff api https://quotes.toscrape.com')."

    if player:
        player.write_log(f"[APISniffer] Sniffing network & reverse engineering: {url}")

    res = sniff_web_api(url=url, wait_seconds=wait_sec, filter_keyword=filter_kw, goal=goal)
    ep_count = res.get("endpoints_captured", 0)
    analysis = res.get("analysis", "")
    saved_path = res.get("script_saved", "")

    summary = f"Sir, maine '{url}' par {ep_count} network endpoints sniff kiye hain.\n\n{analysis}\n\nReusable script save ho gayi hai: {saved_path}"
    return summary


TOOL = {
    "name": "api_sniffer",
    "description": "Dynamic network API sniffer and reverse engineer. Inspects live fetch/XHR traffic, auth tokens, and JSON endpoints from any website or SPA using Playwright + BeautifulSoup4 + Gemini 2.5 Flash, generating reusable automated scraping scripts.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "url": {
                "type": "STRING",
                "description": "Website or web-app URL to sniff and reverse-engineer."
            },
            "goal": {
                "type": "STRING",
                "description": "Specific data or API endpoint user wants to extract (e.g. 'product prices', 'weather api', 'user profile data')."
            },
            "filter": {
                "type": "STRING",
                "description": "Optional keyword filter for network URLs (e.g. 'api', 'v1', 'graphql')."
            },
            "wait_seconds": {
                "type": "INTEGER",
                "description": "Seconds to wait for SPA AJAX traffic to settle (default: 4)."
            }
        },
        "required": ["url"]
    },
    "handler": api_sniffer,
}
