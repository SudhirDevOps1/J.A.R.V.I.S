"""PiP mode — mini always-on-top companion window. New file, auto-discovered.
"pip mode on karo" -> chhoti window browser ke upar: state dot + transcript + input.
Voice mic main loop me hai (chalti rehti hai); PiP sirf dekhne + type karne ke liye.
"""
from __future__ import annotations


def pip_mode(parameters: dict | None = None, player=None, session_memory=None, **_) -> str:
    params = parameters or {}
    action = str(params.get("action", "toggle") or "toggle").lower().strip()
    try:
        toggle = getattr(player, "toggle_pip", None)
        pip_win = getattr(player, "_pip", None)

        if action in ("expand", "bada", "maximize"):
            if not pip_win or not pip_win.isVisible():
                if callable(toggle):
                    toggle()
            if pip_win and not getattr(pip_win, "_expanded", False):
                pip_win._toggle_expand()
            return "PiP window ko expand kar diya hai."

        if action in ("compact", "chhota", "shrink", "normal"):
            if pip_win and getattr(pip_win, "_expanded", False):
                pip_win._toggle_expand()
            return "PiP window ko compact size par set kar diya hai."

        if action in ("clear", "safai", "clear_chat"):
            if pip_win:
                pip_win.clear_chat()
            return "PiP chat history clear ho gayi."

        if action in ("inspect", "status", "dekho", "check"):
            if not pip_win or not pip_win.isVisible():
                return "PiP companion window abhi screen par open nahi hai (hidden/closed hai). 'pip mode on karo' se open kar sakte hain."
            size_mode = "expanded" if getattr(pip_win, "_expanded", False) else "compact"
            recent_text = ""
            try:
                chat_w = getattr(pip_win, "_chat", None)
                if chat_w and hasattr(chat_w, "toPlainText"):
                    raw = chat_w.toPlainText().strip()
                    if raw:
                        lines = [l.strip() for l in raw.splitlines() if l.strip()]
                        recent_text = f" | Last messages: {' ; '.join(lines[-3:])}"
            except Exception:
                pass
            return f"PiP companion window abhi top-level par active aur visible hai ({size_mode} mode).{recent_text}"

        if not callable(toggle):
            return "PiP HUD me hai — 🪟 PIP button dabao."
        if action in ("on", "open", "show", "kholo"):
            # ensure visible: toggle twice if needed
            if not toggle():
                toggle()
            return "PiP mini window on hai — browser ke upar rahegi. Type karo ya bolo."
        if action in ("off", "close", "hide", "band"):
            if toggle():
                toggle()
            return "PiP band kar diya."
        vis = toggle()
        return ("PiP on hai — upar rahegi." if vis else "PiP band hai.")
    except Exception as e:
        return f"PiP failed: {e}"


TOOL = {
    "name": "pip_mode",
    "description": (
        "Toggle mini always-on-top PiP companion window (transcript + input over browser). "
        "Trigger on 'pip mode on karo', 'mini window kholo', 'pip band karo', 'pip bada karo', 'pip chhota karo', 'pip mode dekho', 'pip status'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "toggle | on | off | expand | compact | clear | inspect | status"},
        },
        "required": ["action"],
    },
    "handler": pip_mode,
}
