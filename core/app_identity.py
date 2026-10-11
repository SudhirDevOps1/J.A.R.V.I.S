"""
core/app_identity.py — the project's identity strings, in one place.

WHY THIS EXISTS
---------------
Three different things hardcoded the maintainer's personal handle:

    main.py         SetCurrentProcessExplicitAppUserModelID("SudhirDevOps1.JARVIS.AI")
    ui.py           SetCurrentProcessExplicitAppUserModelID("SudhirDevOps1.JARVIS.AI")
    run_jarvis.pyw  SetCurrentProcessExplicitAppUserModelID("SudhirDevOps1.JARVIS.AI")

On Windows that ID is what groups a process under a taskbar icon and what
ties its notification settings to an app. It is a public, stable identifier,
so every fork and every install of this software was registering itself under
the upstream author's GitHub account. Users could not set it, and nothing in
the settings UI could change it.

The name itself also fell back to "SudhirDevOps1 AI" in
memory/config_manager.get_app_name, so a fresh clone was named after one
person by default.

This module makes identity a config concern with a neutral default, and keeps
existing installs unchanged: a user who already has an app_name set keeps it.

AUMID RULES (Windows)
---------------------
A user mode app id is a string of at most 128 characters in the form
Company.SubProduct.SubApplication, separated by dots. Spaces are not allowed
and it must not be empty. A configured name like "My Assistant" is therefore
sanitised rather than passed through, or the call silently fails and the
process keeps its default (exe name) grouping.
"""
from __future__ import annotations

import re

# Neutral defaults. Deliberately not tied to any person.
DEFAULT_APP_NAME = "J.A.R.V.I.S"
DEFAULT_ASSISTANT_NAME = "J.A.R.V.I.S"
DEFAULT_PROTOCOL_NAME = "JARVIS"

# Vendor segment of the AUMID. This is the project's name, not a person's.
VENDOR_ID = "Jarvis"


def sanitize_aumid(raw: str, fallback: str = "Jarvis.App") -> str:
    """Turn an arbitrary configured name into something Windows accepts.

    Keeps letters and digits, converts every run of anything else to a single
    dot, collapses repeated dots, and drops leading/trailing dots. Returns the
    fallback rather than an empty string, because an empty AUMID makes the
    shell ignore the registration entirely.
    """
    text = str(raw or "").strip()
    if not text:
        return fallback
    # Split on anything that is not alphanumeric so spaces, dashes and
    # underscores all become segment separators.
    parts = re.split(r"[^A-Za-z0-9]+", text)
    parts = [p for p in parts if p]
    if not parts:
        return fallback
    out = ".".join(parts)
    out = out.strip(".")
    if not out:
        return fallback
    return out[:128]


def build_aumid(app_name: str = "", assistant_name: str = "") -> str:
    """Compose the Windows app user model id for the current configuration."""
    name = sanitize_aumid(app_name or DEFAULT_APP_NAME, fallback="Jarvis.App")
    return sanitize_aumid(f"{VENDOR_ID}.{name}", fallback="Jarvis.App")


def get_aumid() -> str:
    """The AUMID for this installation, honouring the configured app name.

    Falls back to the neutral default if the config layer is unavailable —
    which it will be during very early startup, and in tests.
    """
    try:
        from memory.config_manager import get_app_name
        name = get_app_name()
    except Exception:
        name = ""
    return build_aumid(name)


def set_app_user_model_id() -> bool:
    """Register the AUMID with the Windows shell.

    Returns True when registration was attempted and accepted. Non-Windows and
    API failures return False rather than raising: taskbar grouping is a
    cosmetic concern and must never stop the app from starting.
    """
    if not _is_windows():
        return False
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(get_aumid())
        return True
    except Exception:
        return False


def _is_windows() -> bool:
    import sys
    return sys.platform == "win32"