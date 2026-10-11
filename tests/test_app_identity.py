"""
tests/test_app_identity.py — Tests for the identity module.

WHY THIS IS TESTED
------------------
The AppUserModelID was previously the literal "SudhirDevOps1.JARVIS.AI" in
three files. It is the key Windows uses to group a process under a taskbar
icon, so every fork and every install registered itself under the upstream
author's account. Nothing in the settings UI could change it.

Two properties matter and are easy to get wrong:

  * an invalid AUMID is silently ignored by the shell, so sanitising must
    always produce something usable — never an empty string
  * existing users must keep their configured name. Only the DEFAULT changed,
    so a behavioural test is the only way to notice if that stops being true
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from core.app_identity import (  # noqa: E402
    DEFAULT_APP_NAME,
    build_aumid,
    get_aumid,
    sanitize_aumid,
    set_app_user_model_id,
)


# ── sanitising ──────────────────────────────────────────────────────────────

def test_plain_name_is_kept():
    assert sanitize_aumid("Jarvis") == "Jarvis"


@pytest.mark.parametrize("raw,expected", [
    ("My Assistant", "My.Assistant"),      # spaces are illegal in an AUMID
    ("My-Assistant", "My.Assistant"),
    ("My_Assistant", "My.Assistant"),
    ("  padded  ", "padded"),
])
def test_spaces_and_punctuation_become_dots(raw, expected):
    """A name with a space must not be passed through raw: the shell silently
    rejects it and the process falls back to grouping by exe name."""
    assert sanitize_aumid(raw) == expected


def test_repeated_separators_collapse():
    """Otherwise "My  --  Assistant" becomes My....Assistant, which is not a
    valid identifier and is easy to miss when eyeballing the footer."""
    assert sanitize_aumid("My  --  Assistant") == "My.Assistant"


def test_leading_and_trailing_separators_are_stripped():
    assert sanitize_aumid("---Jarvis---") == "Jarvis"


def test_empty_falls_back_rather_than_returning_empty():
    """An empty AUMID means the shell ignores the registration entirely, so
    falling back is strictly better than passing the empty string through."""
    assert sanitize_aumid("") != ""
    assert sanitize_aumid(None) != ""
    assert sanitize_aumid("   ") != ""


def test_punctuation_only_falls_back():
    assert sanitize_aumid("!!!@@@###") != ""


def test_result_is_truncated_to_the_windows_limit():
    """AUMIDs are capped at 128 characters; longer is rejected outright."""
    out = sanitize_aumid("x" * 300)
    assert len(out) <= 128


def test_sanitised_output_is_always_identifier_safe():
    import re
    for raw in ("My Assistant", "  ", "a b c", "Ünïcödé Näme", "x" * 400, "###"):
        out = sanitize_aumid(raw)
        assert out, f"{raw!r} produced an empty id"
        assert re.fullmatch(r"[A-Za-z0-9]+(\.[A-Za-z0-9]+)*", out), \
            f"{raw!r} -> {out!r} is not a valid dotted identifier"


# ── composing ───────────────────────────────────────────────────────────────

def test_build_aumid_prefixes_the_vendor():
    assert build_aumid("My Assistant") == "Jarvis.My.Assistant"


def test_build_aumid_with_no_name_uses_the_default():
    assert DEFAULT_APP_NAME in build_aumid("")


def test_build_aumid_is_deterministic():
    assert build_aumid("Thing") == build_aumid("Thing")


# ── config integration ──────────────────────────────────────────────────────

def test_get_aumid_returns_something_usable():
    """Whatever the config says, including an absent or corrupt config file."""
    aumid = get_aumid()
    assert aumid
    assert " " not in aumid
    assert len(aumid) <= 128


def test_get_aumid_never_raises_when_config_is_broken(monkeypatch):
    """config_manager raises during early startup and in some tests. The AUMID
    is cosmetic, so a failure there must degrade to the default."""
    import memory.config_manager as cm

    def _boom():
        raise RuntimeError("config unreadable")

    monkeypatch.setattr(cm, "get_app_name", _boom)
    assert get_aumid()  # must not raise


def test_get_aumid_honours_a_configured_name(monkeypatch):
    """The existing-install guarantee: a user who set app_name keeps it."""
    import memory.config_manager as cm
    monkeypatch.setattr(cm, "get_app_name", lambda: "My Assistant")
    assert get_aumid() == "Jarvis.My.Assistant"


# ── registration ────────────────────────────────────────────────────────────

def test_set_app_user_model_id_returns_bool_not_raises():
    """Taskbar grouping is cosmetic and must never be able to stop startup."""
    result = set_app_user_model_id()
    assert isinstance(result, bool)


# ── the regression this exists to prevent ───────────────────────────────────

def test_no_hardcoded_maintainer_aumid_remains():
    """Behavioural check across the whole tree, not a grep for a literal.

    A grep would match the module's own docstring, which deliberately quotes
    the old value to explain what changed.
    """
    offenders = []
    for path in (_ROOT).rglob("*.py*"):
        parts = set(path.parts)
        if {".git", ".venv", "__pycache__", "node_modules"} & parts:
            continue
        # Two files legitimately contain the raw ctypes call: app_identity.py,
        # which wraps it, and this one, which has to name it to search for it.
        if path.name in ("app_identity.py", Path(__file__).name):
            continue
        try:
            src = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        if "SetCurrentProcessExplicitAppUserModelID" in src:
            offenders.append(path.name)
    assert not offenders, (
        f"these files still register a hardcoded AUMID: {offenders}. "
        "Use core.app_identity.set_app_user_model_id()."
    )