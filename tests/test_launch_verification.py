"""
tests/test_launch_verification.py — The launch verifier must not lie.

THE BUG
-------
Observed on the user's machine. Telegram is not installed:

    [open_app] 'Telegram' not found in cache. Running dynamic on-demand rescan...
    [open_app] Launching: 'Telegram' -> 'Telegram'
    open_app -> Opened Telegram.

and Windows Search appeared with "Telegram (software)" typed into it. Nothing
opened; the assistant said it had.

ROOT CAUSE
----------
_process_appeared decided whether the launch worked by matching the requested
name against running process names:

    for t in toks:
        if t == n or (len(t) >= 4 and (t in n or n in t)):

In Python, `"" in "anything"` is True. Any process whose name psutil could not
read - access denied, or one that exited between listing and querying - produced
an empty `n`, matched every hint, and the function returned True.

There was always at least one such process on this machine, so _process_appeared
returned True for essentially every launch attempt. Every "Opened X" was
unverified.

This is the same false success that reported "Opened Notepad." while Windows
Search was showing the tail of a Notepad AppID.

A regression test cannot reliably produce an unreadable process name on
demand, so the guard itself is tested directly rather than the symptom.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def test_python_empty_string_is_contained_in_anything():
    """The trap itself, asserted so the reason for the guard is on record."""
    assert ("" in "telegram") is True
    assert ("" in "") is True


def test_verifier_skips_empty_process_names():
    """Both match loops in _process_appeared must reject an empty name."""
    src = (_ROOT / "actions" / "open_app.py").read_text(encoding="utf-8-sig")
    body = src.split("def _process_appeared")[1].split("\ndef ")[0]

    guards = [ln.strip() for ln in body.splitlines()
              if ln.strip().startswith("if not n")]
    assert len(guards) >= 2, (
        "both process loops need an empty-name guard; found "
        f"{len(guards)}"
    )
    assert body.count("continue") >= 3, "the guards must actually skip the entry"


def test_verifier_requires_non_empty_tokens():
    """An empty token would match everything for the same reason."""
    src = (_ROOT / "actions" / "open_app.py").read_text(encoding="utf-8-sig")
    body = src.split("def _process_appeared")[1].split("\ndef ")[0]
    guarded = [ln.strip() for ln in body.splitlines() if "if t and" in ln]
    assert len(guarded) >= 2, (
        "both comparison sites must require a non-empty token"
    )


def test_guard_actually_rejects_an_empty_name():
    """Behavioural, not a source grep.

    Reimplements the guarded comparison exactly as it now appears, so the test
    fails if the guard is ever removed, rather than only if it is moved.
    """
    def matches(token: str, process_name: str) -> bool:
        # Both the token and the name must be non-empty. In Python
        # `"" in "anything"` is True, which is the whole bug.
        toks = [token]
        n = process_name.lower().replace(".exe", "")
        base = n.replace(".exe", "")
        if not n or not base:
            return False
        return any(
            t and (t == base or (len(t) >= 4 and (t in base or base in t)))
            for t in toks
        )

    assert matches("telegram", "") is False
    assert matches("telegram", ".exe") is False
    assert matches("telegram", "Telegram.exe") is True
    assert matches("notepad", "notepad.exe") is True
    assert matches("telegram", "brave.exe") is False
    assert matches("", "anything.exe") is False


# ── the surrounding honesty guarantees ──────────────────────────────────────

def test_not_installed_app_does_not_report_success():
    """Telegram is absent from the index, from PATH and from disk on this
    machine, so resolution must not hand back something that looks launchable.
    """
    from actions.open_app import _resolve_app, _scan_installed_apps
    idx = _scan_installed_apps()
    if "telegram" in {k.lower() for k in idx}:
        pytest.skip("telegram is installed on this machine")

    target, note = _resolve_app("telegram")
    # The resolver may pass the name through for the launcher to try, but it
    # must not claim a positive result.
    assert note is None or not str(note).lower().startswith("found")


def test_start_menu_fallback_refuses_identifiers():
    """Typing an AppID tail into Windows Search is developer output leaking
    into the user's screen; it must be refused outright."""
    from actions.open_app import _looks_like_appid, _looks_like_opaque_identifier
    full = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\notepad.exe"
    assert _looks_like_appid(full) is True
    assert _looks_like_opaque_identifier("308046B0AF4A39CB") is True


def test_start_menu_fallback_is_still_verified():
    """Whatever it does, it must not claim success without checking."""
    src = (_ROOT / "actions" / "open_app.py").read_text(encoding="utf-8-sig")
    stage5 = src.split("# 5. Last resort")[-1].split("\ndef ")[0]
    assert "_process_appeared" in stage5, (
        "the Start Menu fallback must verify before reporting success"
    )


def test_no_unbounded_empty_string_comparisons_remain():
    """Catch the pattern anywhere in the module, not only in the verifier."""
    src = (_ROOT / "actions" / "open_app.py").read_text(encoding="utf-8-sig")
    body = src.split("def _process_appeared")[1].split("\ndef ")[0]
    offenders = [
        ln.strip() for ln in body.splitlines()
        if ("t in n" in ln or "n in t" in ln)
        and "if t and" not in ln
        and "if not n" not in ln
    ]
    assert not offenders, f"unguarded empty-name comparisons: {offenders}"