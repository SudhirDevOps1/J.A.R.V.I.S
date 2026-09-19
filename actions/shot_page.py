"""Website full-page screenshot / PDF capture. New file, auto-discovered.
Playwright optional: missing par clean Hindi error. Output ~/Downloads/JARVIS Captures.
Browser_control engine untouched — yah standalone capture hai.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

_OUT_DIR = Path.home() / "Downloads" / "JARVIS Captures"


def _log(player, msg: str) -> None:
    try:
        if player:
            player.write_log(msg)
    except Exception:
        pass
    print(msg)


def shot_page(parameters: dict | None = None, player=None, session_memory=None, **_) -> str:
    params = parameters or {}
    url = str(params.get("url", "") or "").strip()
    mode = str(params.get("mode", "shot") or "shot").lower().strip()
    if not url:
        return "Please specify a URL to capture."
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url
    try:
        from playwright.sync_api import sync_playwright as _pw
    except Exception:
        return "Screenshot ke liye Playwright install karo: pip install playwright + python -m playwright install chromium."
    try:
        _OUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        host = url.split("//", 1)[-1].split("/", 1)[0].replace(":", "_")[:40]
        with _pw() as p:
            b = p.chromium.launch(headless=True)
            pg = b.new_page(viewport={"width": 1366, "height": 900})
            pg.goto(url, timeout=30000, wait_until="networkidle")
            pg.wait_for_timeout(1500)
            if mode in ("pdf", "save_pdf"):
                out = str(_OUT_DIR / f"{host}-{stamp}.pdf")
                pg.pdf(path=out)
            else:
                out = str(_OUT_DIR / f"{host}-{stamp}.png")
                pg.screenshot(path=out, full_page=True)
            b.close()
        _log(player, f"[shot] saved {os.path.basename(out)}")
        return f"Capture save ho gaya: {out}"
    except Exception as e:
        return f"Capture failed: {e}"


TOOL = {
    "name": "shot_page",
    "description": (
        "Capture full-page screenshot or PDF of any website. "
        "Trigger on 'screenshot le website ka', 'page ka pdf banao'. "
        "Do NOT use browser_control get_text for captures — use this instead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "url": {"type": "STRING", "description": "Website URL"},
            "mode": {"type": "STRING", "description": "shot (PNG) | pdf, default shot"},
        },
        "required": ["url"],
    },
    "handler": shot_page,
}
