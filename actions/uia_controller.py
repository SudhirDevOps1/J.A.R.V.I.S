"""
Windows UIAutomation (UIA) Semantic Desktop Controller.
Allows JARVIS to directly inspect, click, type, and navigate desktop UI elements
by accessible name and control type without fragile coordinate guessing or DPI scaling issues.
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

try:
    from pywinauto import Application, Desktop
    from pywinauto.findwindows import ElementNotFoundError, WindowNotFoundError
    _UIA_AVAILABLE = True
except ImportError:
    _UIA_AVAILABLE = False


def _get_window(window_title: str, timeout: float = 3.0):
    """Locate top window matching title substring via UIA."""
    if not _UIA_AVAILABLE:
        raise RuntimeError("pywinauto is not installed. Install with 'pip install pywinauto'.")

    desktop = Desktop(backend="uia")
    title_clean = window_title.strip().lower()

    # Fast direct scan of visible windows
    windows = desktop.windows()
    for w in windows:
        try:
            wt = w.window_text()
            if wt and title_clean in wt.lower():
                return w
        except Exception:
            continue

    # Fallback to regex connection
    try:
        app = Application(backend="uia").connect(title_re=f"(?i).*{re.escape(window_title)}.*", timeout=timeout)
        return app.top_window()
    except Exception as e:
        raise WindowNotFoundError(f"Window matching '{window_title}' not found: {e}")


def click_element(window_title: str, element_name: str, control_type: str = "Button") -> str:
    """Click a UI element (button, checkbox, tab, etc.) inside a window by its accessible name."""
    if not _UIA_AVAILABLE:
        return "UIAutomation available nahi hai. 'pip install pywinauto' karein."

    try:
        win = _get_window(window_title)
        elem_clean = element_name.strip().lower()

        # Find candidate element
        target = None
        for child in win.descendants():
            try:
                ct = child.element_info.control_type
                txt = (child.window_text() or "").strip().lower()
                auto_id = (child.element_info.automation_id or "").strip().lower()

                if control_type and ct.lower() != control_type.lower():
                    # If control_type specified, check if it matches, otherwise allow match if name matches exactly
                    if elem_clean not in txt and elem_clean not in auto_id:
                        continue

                if elem_clean in txt or elem_clean in auto_id or (txt and elem_clean == txt):
                    target = child
                    break
            except Exception:
                continue

        if not target:
            # Try best match lookup
            try:
                target = win.child_window(title_re=f"(?i).*{re.escape(element_name)}.*", control_type=control_type)
            except Exception:
                pass

        if not target:
            return f"'{window_title}' me '{element_name}' ({control_type}) element nahi mila."

        # Prefer UIA invoke pattern for instant, non-disruptive activation
        try:
            target.invoke()
            return f"'{window_title}' me '{element_name}' par successfully invoke/click kiya gaya."
        except Exception:
            # Fallback to click_input
            target.click_input()
            return f"'{window_title}' me '{element_name}' par click kiya gaya."

    except WindowNotFoundError:
        return f"'{window_title}' window open nahi mili sir."
    except Exception as e:
        return f"Element click error: {e}"


def list_window_elements(window_title: str, max_depth: int = 2) -> str:
    """List interactive controls (buttons, edits, menus, checkboxes) in the target window."""
    if not _UIA_AVAILABLE:
        return "UIAutomation available nahi hai. 'pip install pywinauto' karein."

    try:
        win = _get_window(window_title)
        items: List[str] = []
        interactive_types = {"Button", "Edit", "MenuItem", "CheckBox", "RadioButton", "ComboBox", "TabItem", "Hyperlink"}

        for child in win.descendants(depth=max_depth):
            try:
                ct = child.element_info.control_type
                txt = (child.window_text() or "").strip()
                if ct in interactive_types and txt:
                    items.append(f"[{ct}] {txt}")
                if len(items) >= 25:
                    break
            except Exception:
                continue

        if not items:
            return f"'{window_title}' me koi visible interactive elements nahi mile."

        preview = "\n  • ".join(items[:20])
        return f"'{window_title}' ke interactive elements ({len(items)}):\n  • {preview}"
    except WindowNotFoundError:
        return f"'{window_title}' window open nahi mili sir."
    except Exception as e:
        return f"Element inspection error: {e}"


def set_element_text(window_title: str, element_name: str, text: str) -> str:
    """Set or type text directly into an Edit or TextBox control."""
    if not _UIA_AVAILABLE:
        return "UIAutomation available nahi hai. 'pip install pywinauto' karein."

    try:
        win = _get_window(window_title)
        elem_clean = element_name.strip().lower()

        target = None
        for child in win.descendants():
            try:
                ct = child.element_info.control_type
                txt = (child.window_text() or "").strip().lower()
                auto_id = (child.element_info.automation_id or "").strip().lower()
                if ct in ("Edit", "Document") and (elem_clean in txt or elem_clean in auto_id or not elem_clean):
                    target = child
                    break
            except Exception:
                continue

        if not target:
            target = win.child_window(control_type="Edit")

        if not target:
            return f"'{window_title}' me koi text field ('{element_name}') nahi mila."

        try:
            target.set_edit_text(text)
            return f"'{window_title}' ke input box me '{text}' likh diya gaya."
        except Exception:
            target.type_keys(text, with_spaces=True)
            return f"'{window_title}' me text type kar diya gaya: {text[:60]}"

    except WindowNotFoundError:
        return f"'{window_title}' window open nahi mili sir."
    except Exception as e:
        return f"Text input error: {e}"


def menu_select(window_title: str, menu_path: str) -> str:
    """Select a menu path in the application (e.g. 'File->Save' or 'Edit->Find')."""
    if not _UIA_AVAILABLE:
        return "UIAutomation available nahi hai."

    try:
        win = _get_window(window_title)
        win.menu_select(menu_path)
        return f"'{window_title}' me '{menu_path}' menu select kar diya gaya."
    except Exception as e:
        return f"Menu select error: {e}"


def uia_controller(
    parameters=None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """JARVIS action dispatcher for Windows UIAutomation (UIA)."""
    params = parameters or {}
    action = str(params.get("action", "")).strip().lower()
    window_title = str(params.get("window_title", params.get("window", params.get("app", "")))).strip()
    element_name = str(params.get("element_name", params.get("element", params.get("name", "")))).strip()
    control_type = str(params.get("control_type", "Button")).strip()
    text = str(params.get("text", params.get("value", ""))).strip()
    menu_path = str(params.get("menu_path", params.get("path", ""))).strip()

    if not window_title and not action:
        return "UIA Controller: Kripya target window title aur action batayein (e.g. click, list_elements, set_text)."

    if action in ("click", "click_element", "press_button"):
        if not window_title or not element_name:
            return "Kripya window title aur element name dono provide karein."
        return click_element(window_title, element_name, control_type)

    elif action in ("list", "list_elements", "inspect", "inspect_window"):
        if not window_title:
            return "Kripya inspect karne ke liye window title batayein."
        return list_window_elements(window_title)

    elif action in ("set_text", "type", "type_text", "write"):
        if not window_title or not text:
            return "Kripya window title aur text dono provide karein."
        return set_element_text(window_title, element_name, text)

    elif action in ("menu", "menu_select"):
        if not window_title or not menu_path:
            return "Kripya window title aur menu path provide karein (e.g. 'File->Save')."
        return menu_select(window_title, menu_path)

    else:
        # Default smart inference
        if element_name and window_title:
            return click_element(window_title, element_name, control_type)
        elif window_title:
            return list_window_elements(window_title)
        return f"Unknown UIA action: '{action}'. Available: click, list_elements, set_text, menu_select."


TOOL = {
    "name": "uia_controller",
    "description": "Windows UIAutomation (UIA) semantic desktop controller. Directly inspects, clicks, types, and selects menus inside any desktop application by accessible element name without pixel guessing.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action to perform: 'click', 'list_elements', 'set_text', 'menu_select', or 'inspect'."
            },
            "window_title": {
                "type": "STRING",
                "description": "Title or substring of the target application window (e.g. 'Notepad', 'Chrome', 'Calculator', 'VSCodium')."
            },
            "element_name": {
                "type": "STRING",
                "description": "Name or text of the UI element to click or type into (e.g. 'Save', 'Submit', 'Search', 'Close', 'File')."
            },
            "text": {
                "type": "STRING",
                "description": "Text to set or type into the element (for 'set_text' action)."
            },
            "control_type": {
                "type": "STRING",
                "description": "Optional UI element type filter: 'Button', 'Edit', 'MenuItem', 'CheckBox', 'ComboBox', 'TabItem', etc."
            },
            "menu_path": {
                "type": "STRING",
                "description": "Menu path for 'menu_select', e.g. 'File->Save' or 'Edit->Preferences'."
            }
        },
        "required": ["action"]
    },
    "handler": uia_controller,
}
