#!/usr/bin/env python3
"""
Interactive First-Time Onboarding & API Key Setup Wizard for J.A.R.V.I.S.
Runs cleanly on first launch if config/api_keys.json is missing or blank.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_DIR = _ROOT / "config"
_API_KEYS_PATH = _CONFIG_DIR / "api_keys.json"


def is_onboarding_needed() -> bool:
    """Check if API keys configuration needs first-time setup."""
    if not _API_KEYS_PATH.exists():
        return True
    try:
        with open(_API_KEYS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            key = (data.get("gemini_api_key") or "").strip()
            pool = data.get("gemini_api_keys") or []
            has_pool_key = isinstance(pool, list) and any(
                str(k).strip() for k in pool
            )
            if key or has_pool_key:
                return False
    except Exception:
        return True
    return False


def run_interactive_onboarding():
    """Run friendly interactive Hinglish CLI setup for Gemini API key."""
    # Check if running in non-interactive environment (CI / pipe)
    if not sys.stdin.isatty():
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not _API_KEYS_PATH.exists():
            with open(_API_KEYS_PATH, "w", encoding="utf-8") as f:
                json.dump({"gemini_api_key": ""}, f, indent=2)
        return

    print()
    print("=" * 70)
    print("     * SUDHIRDEVOPS1 AI ASSISTANT (J.A.R.V.I.S. / FRIDAY) *")
    print("           First-Time Quick Onboarding (India Edition)")
    print("=" * 70)
    print()
    print("  [Namaste!] J.A.R.V.I.S. me aapka swagat hai!")
    print("  High-speed voice conversation & Gemini Live ke liye aapko")
    print("  apni Google Gemini API Key add karni hogi.")
    print()
    print("  -> Bilkul FREE key yahan se lein:")
    print("     https://aistudio.google.com/app/apikey")
    print()

    try:
        entered_key = input(
            "  Apni Gemini API Key paste karein (Enter to skip): "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        entered_key = ""

    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing_data = {}
    if _API_KEYS_PATH.exists():
        try:
            with open(_API_KEYS_PATH, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception:
            existing_data = {}

    if entered_key:
        existing_data["gemini_api_key"] = entered_key
        existing_data["gemini_api_keys"] = [entered_key]
        with open(_API_KEYS_PATH, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=2)
        print()
        print("  [OK] Bahut badhiya! API Key safaltapoorvak save ho gayi.")
        print("  [OK] J.A.R.V.I.S. ab ready hai start hone ke liye!")
    else:
        if "gemini_api_key" not in existing_data:
            existing_data["gemini_api_key"] = ""
        with open(_API_KEYS_PATH, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=2)
        print()
        print("  [INFO] Key skip ki gayi. Anonymous mode active.")
        print("         Baad me config/api_keys.json me add kar sakte hain.")

    print("=" * 70)
    print()


def main():
    if "--check" in sys.argv:
        if is_onboarding_needed():
            print("[ONBOARDING] Needed: config/api_keys.json unconfigured.")
            sys.exit(1)
        else:
            print("[ONBOARDING] Ready: API keys configured.")
            sys.exit(0)

    if is_onboarding_needed():
        run_interactive_onboarding()


if __name__ == "__main__":
    main()
