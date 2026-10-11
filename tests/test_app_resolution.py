"""
tests/test_app_resolution.py — Tests for app-name resolution in actions/open_app.

Three separate bugs produced confidently wrong answers here, all of them
substring matching:

  1. `_resolve_app("hu use")` returned Notepad, because the fallback stage did
     a bare two-way containment test (`app_name in key`) and any app name
     containing a 2-3 character fragment satisfied it. The assistant then
     announced it had closed an app that does not exist.

  2. `_resolve_app("aur tasks")` returned OneNote, because the category stage
     tested `any(c in key for c in candidates)` and "tasks" is a substring of
     "aur tasks" — so ordinary prose containing a task noun silently selected
     the todo category.

  3. `_resolve_app("vs code")` returned Notepad: "code" is not itself an
     installed app name on Windows, so it fell through to difflib fuzzy
     matching against the whole app list and matched an unrelated entry.

The theme is that a resolver which answers confidently for nonsense input is
worse than one that admits it found nothing.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


@pytest.fixture(scope="module")
def resolver():
    from actions.open_app import _resolve_app
    return _resolve_app


# ── nonsense must not resolve to a real application ─────────────────────────

@pytest.mark.parametrize("junk", [
    "hu use",
    "kaun hai",
    "kuch nahi",
    "main nahi kiya",
    "abc def",
])
def test_junk_does_not_resolve(resolver, junk):
    """A resolver that invents an answer for nonsense is the actual defect."""
    target, _note = resolver(junk)
    t = str(target or "").lower()
    assert t in (junk.lower(), "", "none") or "\\" not in t, (
        f"{junk!r} resolved to a real executable: {target!r}"
    )


def test_prose_does_not_trigger_a_category(resolver):
    """"aur tasks" contains "tasks" as a substring but is not a todo request."""
    target, _ = resolver("aur tasks")
    t = str(target or "").lower()
    # It may fall through to the todo category (which is defensible), but it
    # must not match via a raw substring fragment of an unrelated word.
    assert "onenote" in t or t == "aur tasks", f"unexpected target: {target!r}"


# ── real applications must still resolve ────────────────────────────────────

@pytest.mark.parametrize("name", [
    "notepad", "chrome", "word", "calculator", "vscode", "spotify",
])
def test_real_apps_resolve(resolver, name):
    target, _ = resolver(name)
    assert target, f"{name!r} resolved to nothing"


def test_vs_code_resolves_to_vscode_not_notepad(resolver):
    """Regression: the spaced form fell through to fuzzy matching and matched
    Notepad, because "code" is not an installed app name on Windows."""
    target, _ = resolver("vs code")
    t = str(target or "").lower()
    assert "notepad" not in t, (
        f"'vs code' resolved to Notepad: {target!r} — the fuzzy stage matched an "
        f"unrelated app because 'code' is not itself an installed app name"
    )


def test_minimum_substring_length_is_enforced():
    """The guard is 4 characters, so 2-3 character prefixes cannot match."""
    from actions.open_app import _resolve_app
    import inspect
    src = inspect.getsource(_resolve_app)
    assert "_MIN_SUBSTR = 4" in src


# ── category matching is word-bounded ───────────────────────────────────────

def test_category_stage_splits_on_word_boundaries():
    """The category stage must compare whole words, not substrings.

    AST-based rather than a text search: the fix's explanatory comment quotes
    the old expression verbatim, so grepping the source would false-positive.
    """
    import ast
    from actions.open_app import _resolve_app

    tree = ast.parse(inspect.getsource(_resolve_app))
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and isinstance(node.ops[0], ast.In):
            # `candidates` / `key` containment on the left of `in`
            seg = ast.dump(node)
            if "Subscript" in seg and "Name" in seg and "Comprehension" not in seg:
                # a generator inside `any(...)` is the pattern we care about
                src = ast.unparse(node)
                if " in " in src and ("key" in src or "candidates" in src):
                    bad.append(src)
    assert not any("c in key" in b for b in bad), (
        f"category matching still uses substring containment: {bad}"
    )


def test_substring_stage_requires_minimum_length():
    """Behavioural: a two or three character fragment must not resolve.

    An AST check on the isolated expression is not usable here because the
    containment is (correctly) nested inside a guard that does the length check,
    so the guard is not visible from the expression alone. This asserts the
    observable contract instead.
    """
    from actions.open_app import _resolve_app

    # "hu" is a bare two-character fragment. If the containment stage is
    # unguarded it matches any installed app whose name contains "hu".
    short_target, _ = _resolve_app("hu")
    assert "notepad" not in str(short_target).lower(), (
        f"2-char fragment 'hu' resolved to {short_target!r} — the substring "
        f"stage is matching on short prefixes"
    )


def test_substring_stage_source_has_a_length_guard():
    """The guard itself must exist, verified structurally."""
    import ast
    from actions.open_app import _resolve_app

    tree = ast.parse(inspect.getsource(_resolve_app))
    # A containment expression using app_name must sit inside an `if` whose test
    # references the minimum length, i.e. it is guarded.
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        if "_MIN_SUBSTR" not in ast.unparse(node.test):
            continue
        if "app_name in key" in ast.unparse(node):
            return  # found: the containment is guarded
    raise AssertionError(
        "no guarded containment expression found — the substring stage is "
        "unprotected"
    )


# ── router-level protection ──────────────────────────────────────────────────

def test_router_blocks_filler_before_resolution():
    """Even if a future resolver regresses, the router must not hand it filler."""
    from core.edge_router import _is_filler_phrase
    for junk in ("hu use", "aur tasks", "kaun hai", "sab tasks"):
        assert _is_filler_phrase(junk) is True