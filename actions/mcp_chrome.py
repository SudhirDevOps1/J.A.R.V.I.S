"""
actions/mcp_chrome.py — Live Chrome DevTools MCP Action for J.A.R.V.I.S.

Allows J.A.R.V.I.S. to inspect, navigate, click, and interact with the user's active
Google Chrome browser session via the Model Context Protocol (chrome-devtools-mcp).
Auto-discovered by core.action_loader.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from typing import Any, Dict, Optional

from core.mcp_host import McpSession, execute_mcp_tool_once


def _check_chrome_debugging() -> bool:
    """Quick socket check to verify if Chrome Remote Debugging port (9222) is open."""
    import socket
    try:
        with socket.create_connection(("127.0.0.1", 9222), timeout=0.5):
            return True
    except Exception:
        return False


def mcp_chrome(
    parameters: dict | None = None,
    player=None,
    speak=None,
    **_
) -> str:
    params = parameters or {}
    action = str(params.get("action", "inspect") or "inspect").lower().strip()
    url = str(params.get("url", "") or "").strip()
    selector = str(params.get("selector", "") or "").strip()
    text = str(params.get("text", "") or "").strip()

    if not shutil.which("npx"):
        return "Node.js (npx) is not found in system PATH. Please ensure Node.js is installed."

    if player:
        player.write_log(f"[ChromeDevTools] Action: {action} (Target: {url or selector or 'active page'})")

    # Map J.A.R.V.I.S. action to chrome-devtools-mcp tool call
    npx_args = ["-y", "chrome-devtools-mcp@latest"]

    if action in ("navigate", "open"):
        if not url:
            return "Please provide a URL to navigate to in Chrome."
        target_url = url if "://" in url else f"https://{url}"
        success, out = execute_mcp_tool_once("npx", npx_args, "navigate_page", {"url": target_url}, timeout=20.0)
        if success:
            return f"Chrome navigated to {target_url}."
        # Fallback to standard URL open if devtools port is not active
        import webbrowser
        webbrowser.open(target_url)
        return f"Chrome opened with {target_url}."

    elif action in ("screenshot", "capture"):
        success, out = execute_mcp_tool_once("npx", npx_args, "take_screenshot", {}, timeout=20.0)
        if success:
            return "Chrome page screenshot captured successfully via DevTools."
        # Fallback to screen capture
        try:
            from actions.screen_processor import _capture_screen
            _capture_screen()
            return "Captured screen snapshot of Chrome."
        except Exception as e:
            return f"Could not capture screenshot: {e}"

    elif action in ("click", "press"):
        if not selector:
            return "Please specify the selector or element text to click in Chrome."
        success, out = execute_mcp_tool_once("npx", npx_args, "click", {"selector": selector}, timeout=15.0)
        return out if success else f"Click action failed on '{selector}': {out}"

    elif action in ("type", "input", "fill"):
        if not text:
            return "Please provide text to enter into the field."
        success, out = execute_mcp_tool_once("npx", npx_args, "fill", {"selector": selector or "input", "value": text}, timeout=15.0)
        return out if success else f"Input action failed: {out}"

    else:
        # Default: inspect active page
        success, out = execute_mcp_tool_once("npx", npx_args, "list_pages", {}, timeout=15.0)
        if success:
            return f"Chrome DevTools Active Pages:\n{out}"
        return (
            "Chrome DevTools MCP is ready. Tip: Launch Chrome with "
            "'chrome.exe --remote-debugging-port=9222' to allow live DOM inspection and automation."
        )


TOOL = {
    "name": "mcp_chrome",
    "description": (
        "Controls, inspects, and automates Google Chrome browser sessions via Chrome DevTools MCP. "
        "Supports navigating pages, clicking buttons, typing text, and taking browser-level screenshots."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action to perform: 'inspect', 'navigate', 'click', 'type', 'screenshot'."
            },
            "url": {
                "type": "STRING",
                "description": "The destination URL when action is 'navigate'."
            },
            "selector": {
                "type": "STRING",
                "description": "CSS selector or element name for 'click' or 'type'."
            },
            "text": {
                "type": "STRING",
                "description": "Text to type into an input field."
            }
        },
        "required": ["action"]
    },
    "handler": mcp_chrome,
}
