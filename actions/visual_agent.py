"""
actions/visual_agent.py — Autonomous Visual Computer-Use & Self-Healing Agent
Maintained by SudhirDevOps1

Provides closed-loop visual perception and computer control:
  1. Observe (Capture screen/window)
  2. Analyze (Multimodal vision detects UI elements, active state, and blockers)
  3. Self-Heal (Detects error dialogs, popups, and alerts; resolves them autonomously)
  4. Act (Click, smart type, hotkey, scroll, or switch windows)
  5. Verify & Loop (Re-inspects screen until goal is confirmed finished or retry limit reached)
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE = _base_dir()
_CONFIG_PATH = _BASE / "config" / "api_keys.json"


def _load_api_key() -> str:
    """Retrieve Gemini API key from config or environment."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    if _CONFIG_PATH.exists():
        try:
            cfg = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            raw = (cfg.get("gemini_api_key") or cfg.get("gemini") or "").strip()
            try:
                from core.secret_vault import decrypt_value
                raw = decrypt_value(raw)
            except Exception:
                pass
            return raw
        except Exception:
            pass
    return ""


def _capture_screen_frame() -> Tuple[bytes, str]:
    """Capture current screen and return compressed JPEG bytes (<150KB)."""
    from actions.screen_processor import _capture_screen
    return _capture_screen()


def _call_vision_model(
    image_bytes: bytes,
    prompt: str,
    mime_type: str = "image/jpeg",
) -> str:
    """Send image frame + prompt to Gemini Vision with resilient model fallback."""
    api_key = _load_api_key()
    if not api_key:
        return ""

    try:
        from google import genai
        from google.genai import types as gtypes
        client = genai.Client(api_key=api_key)

        models = [
            "gemini-2.0-flash",
            "gemini-2.5-flash",
            "gemini-flash-latest",
        ]
        for model in models:
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=[
                        gtypes.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                        prompt,
                    ],
                )
                if resp and resp.text:
                    return resp.text.strip()
            except Exception as e:
                err_str = str(e).lower()
                if "404" in err_str or "not found" in err_str or "resource_exhausted" in err_str:
                    continue
                print(f"[VisualAgent] Vision model '{model}' error: {e}")
                continue
    except Exception as exc:
        print(f"[VisualAgent] Vision client initialization error: {exc}")

    return ""


def _detect_and_solve_error(image_bytes: bytes, player=None) -> Optional[str]:
    """
    Inspect screen for any visible modal error popups, warnings, or crash dialogs.
    If found, clicks the dismiss/retry button or presses Escape to self-heal.
    """
    if not _PYAUTOGUI:
        return None

    prompt = (
        "Look at this screenshot. Is there any error dialog, alert box, crash popup, "
        "permission request, or blocking modal dialog visible on screen?\n"
        "If YES, reply ONLY with a JSON object:\n"
        '{"has_error": true, "error_text": "<brief summary>", "dismiss_button": "<e.g. OK, Close, Cancel, Dismiss>", "x": <button_x_coord>, "y": <button_y_coord>}\n'
        "If NO error or modal popup is blocking the screen, reply ONLY:\n"
        '{"has_error": false}'
    )

    resp_text = _call_vision_model(image_bytes, prompt)
    if not resp_text:
        return None

    # Parse JSON from model output
    try:
        json_match = re.search(r"\{.*\}", resp_text, re.DOTALL)
        if not json_match:
            return None
        data = json.loads(json_match.group(0))
        if data.get("has_error"):
            err_msg = data.get("error_text", "Unknown popup/error")
            btn = data.get("dismiss_button", "Dismiss")
            bx = data.get("x")
            by = data.get("y")

            msg = f"Self-Healing: Detected error/modal '{err_msg}'. Dismissing via '{btn}'..."
            print(f"[VisualAgent] 🛡️ {msg}")
            if player:
                player.write_log(f"VISUAL: 🛡️ {msg}")

            if isinstance(bx, (int, float)) and isinstance(by, (int, float)) and bx > 0 and by > 0:
                pyautogui.click(int(bx), int(by))
            else:
                pyautogui.press("escape")
                time.sleep(0.2)
                pyautogui.press("enter")

            time.sleep(0.6)
            return f"Auto-dismissed error popup: '{err_msg}'"
    except Exception as pe:
        print(f"[VisualAgent] Error check parse note: {pe}")

    return None


def _plan_next_visual_step(
    image_bytes: bytes,
    goal: str,
    history: List[str],
) -> Dict[str, Any]:
    """
    Visual OODA analysis: determines if goal is achieved, or what next action to take.
    """
    history_str = "\n".join(f"- {h}" for h in history[-5:]) if history else "None (Initial step)"

    prompt = (
        f"You are J.A.R.V.I.S., an autonomous visual computer-use agent.\n"
        f"USER GOAL: '{goal}'\n"
        f"PREVIOUS ACTIONS TAKEN:\n{history_str}\n\n"
        f"Look carefully at the current screenshot of the user's computer screen.\n"
        f"Evaluate the screen state and choose the SINGLE NEXT ACTION to achieve the goal.\n\n"
        f"Return ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "goal_achieved": false,\n'
        '  "status_summary": "<what is currently visible on screen>",\n'
        '  "action_type": "<click | double_click | right_click | smart_type | press | hotkey | scroll | wait | done>",\n'
        '  "x": <x coordinate integer if clicking, else null>,\n'
        '  "y": <y coordinate integer if clicking, else null>,\n'
        '  "text": "<text to type if action_type is smart_type, else null>",\n'
        '  "key": "<key name like enter/escape/tab if action_type is press/hotkey, else null>",\n'
        '  "reason": "<why this action was chosen>"\n'
        "}\n\n"
        "IMPORTANT RULES:\n"
        "- If the goal is ALREADY completed on screen, set 'goal_achieved': true and 'action_type': 'done'.\n"
        "- When providing (x, y) coordinates, point precisely at the center of the button, search box, or input field.\n"
        "- Output ONLY JSON. No markdown code fences, no extra conversational text."
    )

    resp_text = _call_vision_model(image_bytes, prompt)
    if not resp_text:
        return {"goal_achieved": False, "action_type": "wait", "reason": "No vision response"}

    try:
        json_match = re.search(r"\{.*\}", resp_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
    except Exception as e:
        print(f"[VisualAgent] JSON parse fallback: {e} | Text: {resp_text[:120]}")

    return {"goal_achieved": False, "action_type": "wait", "reason": "Failed to parse visual plan"}


def _execute_visual_action(action: Dict[str, Any], player=None) -> str:
    """Execute physical keyboard/mouse action determined by visual analysis."""
    if not _PYAUTOGUI:
        return "PyAutoGUI is not available on this system."

    atype = str(action.get("action_type") or "").strip().lower()
    x = action.get("x")
    y = action.get("y")
    text = action.get("text")
    key = action.get("key")
    reason = action.get("reason", "")

    if atype == "done":
        return "Goal confirmed complete."

    if atype in ("click", "left_click"):
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            pyautogui.moveTo(int(x), int(y), duration=0.2)
            pyautogui.click()
            return f"Clicked at ({int(x)}, {int(y)}) [{reason}]"
        return "Missing coordinates for click."

    if atype == "double_click":
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            pyautogui.moveTo(int(x), int(y), duration=0.2)
            pyautogui.doubleClick()
            return f"Double-clicked at ({int(x)}, {int(y)}) [{reason}]"
        return "Missing coordinates for double-click."

    if atype == "right_click":
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            pyautogui.moveTo(int(x), int(y), duration=0.2)
            pyautogui.rightClick()
            return f"Right-clicked at ({int(x)}, {int(y)}) [{reason}]"
        return "Missing coordinates for right-click."

    if atype == "smart_type":
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            pyautogui.click(int(x), int(y))
            time.sleep(0.15)
        # Clear existing text if any, then paste
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.05)
        import pyperclip
        pyperclip.copy(str(text or ""))
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.1)
        return f"Typed '{text}' [{reason}]"

    if atype == "press":
        if key:
            pyautogui.press(str(key))
            return f"Pressed key '{key}' [{reason}]"
        return "No key specified."

    if atype == "hotkey":
        if key:
            keys = [k.strip() for k in str(key).split("+") if k.strip()]
            pyautogui.hotkey(*keys)
            return f"Pressed hotkey '{key}' [{reason}]"
        return "No hotkey specified."

    if atype == "scroll":
        direction = action.get("direction", "down")
        amt = -400 if direction == "down" else 400
        pyautogui.scroll(amt)
        return f"Scrolled {direction} [{reason}]"

    if atype == "wait":
        secs = float(action.get("seconds", 1.0))
        time.sleep(min(5.0, max(0.5, secs)))
        return f"Waited {secs}s [{reason}]"

    return f"Unknown action_type '{atype}'"


def run_visual_loop(
    goal: str,
    app_name: str = "",
    max_steps: int = 6,
    player=None,
    speak_fn=None,
) -> str:
    """
    Main autonomous visual computer-use execution loop.
    Repeats 'Observe -> Heal Errors -> Decide -> Act -> Verify' until goal is met.
    """
    if not goal or not goal.strip():
        return "Visual Agent requires a specific goal to execute."

    print(f"[VisualAgent] 🚀 Starting visual task: '{goal}' (Max steps: {max_steps})")
    if player:
        player.write_log(f"VISUAL: 👁️ Starting Visual Computer-Use Task: '{goal}'")

    # Step 0: If an app is specified, ensure it is open/active
    if app_name and app_name.strip():
        try:
            from actions.open_app import open_app
            open_app({"app_name": app_name.strip()})
            time.sleep(1.2)
        except Exception as oe:
            print(f"[VisualAgent] App open note: {oe}")

    action_history: List[str] = []
    step_count = 0

    for step in range(1, max_steps + 1):
        step_count = step
        log_prefix = f"VISUAL [{step}/{max_steps}]"
        if player:
            player.write_log(f"{log_prefix}: Capturing screen...")

        # 1. Observe
        try:
            img_bytes, mime = _capture_screen_frame()
        except Exception as ce:
            err = f"Screen capture failed at step {step}: {ce}"
            if player:
                player.write_log(f"SYS: ❌ {err}")
            return err

        # 2. Self-Heal: Check for blocking error dialogs or popups first
        healed_note = _detect_and_solve_error(img_bytes, player=player)
        if healed_note:
            action_history.append(healed_note)
            time.sleep(0.8)
            # Re-capture screen after clearing error
            try:
                img_bytes, mime = _capture_screen_frame()
            except Exception:
                pass

        # 3. Orient & Decide: Analyze screen state against goal
        plan = _plan_next_visual_step(img_bytes, goal, action_history)
        status_sum = plan.get("status_summary", "")
        if status_sum and player:
            player.write_log(f"{log_prefix} Status: {status_sum}")

        # Check termination condition
        if plan.get("goal_achieved"):
            success_msg = f"Visual Task '{goal}' completed successfully after {step} step(s)!"
            print(f"[VisualAgent] ✅ {success_msg}")
            if player:
                player.write_log(f"VISUAL: ✅ {success_msg}")
            if speak_fn and callable(speak_fn):
                try:
                    speak_fn(f"Task completed: {goal}")
                except Exception:
                    pass
            return success_msg

        # 4. Act: Execute chosen next action
        act_res = _execute_visual_action(plan, player=player)
        action_history.append(f"Step {step}: {act_res}")
        if player:
            player.write_log(f"{log_prefix} Action: {act_res}")

        # 5. Wait for UI transition before next loop iteration
        time.sleep(1.0)

    # If loop concludes without explicit goal_achieved
    summary = (
        f"Visual Task '{goal}' completed {step_count} step(s). "
        f"Final status: {action_history[-1] if action_history else 'No actions taken'}."
    )
    if player:
        player.write_log(f"VISUAL: 🏁 {summary}")
    return summary


def visual_agent(
    parameters: dict | None = None,
    response=None,
    player=None,
    session_memory=None,
    **_,
) -> str:
    """Entry point for visual_agent tool call."""
    params = parameters or {}
    goal = (params.get("goal") or params.get("prompt") or params.get("task") or "").strip()
    app_name = (params.get("app_name") or params.get("app") or "").strip()
    max_steps = int(params.get("max_steps") or 6)
    action = (params.get("action") or "execute").strip().lower()

    if action in ("inspect", "error_check", "heal_errors", "solve_error"):
        try:
            img_b, _ = _capture_screen_frame()
            res = _detect_and_solve_error(img_b, player=player)
            return res or "Screen par koi error dialog ya blocking popup nahi mila. Screen is clear."
        except Exception as e:
            return f"Error check failed: {e}"

    if not goal:
        return "Please provide a goal for visual_agent (e.g. goal='click Save button and verify')."

    return run_visual_loop(goal=goal, app_name=app_name, max_steps=max_steps, player=player)


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "visual_agent",
    "description": (
        "Autonomous visual computer-use agent. Real-time visual observation of the screen "
        "and active applications. Visually finds buttons and inputs, clicks, types, detects errors "
        "or unexpected dialogs, and self-heals in a closed loop until the task is completely finished. "
        "Use whenever the user asks to operate any app visually, fix an error on screen, or execute UI tasks."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "goal": {
                "type": "STRING",
                "description": "Specific goal to achieve on screen (e.g. 'open Settings and toggle Bluetooth', 'solve the error popup', 'search for flights and click search')."
            },
            "app_name": {
                "type": "STRING",
                "description": "Optional application name to launch or bring to focus before starting (e.g. 'notepad', 'chrome', 'telegram')."
            },
            "action": {
                "type": "STRING",
                "description": "'execute' (full autonomous visual loop) or 'heal_errors' (inspect and dismiss active error dialog)."
            },
            "max_steps": {
                "type": "INTEGER",
                "description": "Maximum visual execution attempts before concluding (default: 6)."
            }
        },
        "required": ["goal"]
    },
    "handler": visual_agent,
}
