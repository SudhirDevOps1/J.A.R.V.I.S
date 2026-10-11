"""
tests/test_ui_palette_and_shortcuts.py â€” Tests for the new UI layer.

The fuzzy matcher is tested directly without a QApplication. That is
deliberate: subsequence matching is exactly the kind of logic that is easy to
get subtly wrong (an empty query matching everything, short strings scoring
higher than long ones, every short query matching every long one) and all of
those are painful to detect through a GUI.

The widget classes are only smoke-tested for importability, since running them
needs a QApplication and a display.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from ui.command_palette import (  # noqa: E402
    PaletteEntry,
    build_entries,
    filter_entries,
    fuzzy_score,
    selection_to_text,
)


# â”€â”€ fuzzy matching â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_exact_match_scores_highest():
    assert fuzzy_score("notepad", "notepad") == 1.0


def test_prefix_beats_scattered_subsequence():
    """The whole point of the scoring: a prefix match must outrank a
    subsequence that happens to be found somewhere in the string."""
    prefix = fuzzy_score("note", "notepad")
    scattered = fuzzy_score("note", "n_o_t_e_dictionary")
    assert prefix > scattered


def test_word_boundary_beats_mid_word():
    """'code' should rank the tool named 'code' above one that merely contains
    the letters somewhere in a long description."""
    boundary = fuzzy_score("code", "code")
    mid = fuzzy_score("code", "encode decoder")
    assert boundary > mid


def test_no_match_returns_zero():
    assert fuzzy_score("zzz", "notepad") == 0.0


def test_empty_query_returns_zero():
    assert fuzzy_score("", "notepad") == 0.0
    assert fuzzy_score("notepad", "") == 0.0
    assert fuzzy_score(None, None) == 0.0


def test_subsequence_is_required_but_insufficient():
    """"ntp" is a subsequence of "notepad", so it matches, but it must not score
    as high as a real prefix match."""
    assert fuzzy_score("ntp", "notepad") > 0.0
    assert fuzzy_score("ntp", "notepad") < fuzzy_score("not", "notepad")


def test_scores_stay_in_range():
    for q, h in [("a", "a"), ("abc", "abc"), ("xyz", "xyzabcxyz"),
                 ("chrome", "google chrome browser")]:
        s = fuzzy_score(q, h)
        assert 0.0 <= s <= 1.0, f"{q!r}/{h!r} -> {s}"


# â”€â”€ filtering â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.fixture
def entries():
    return [
        PaletteEntry(label="Open settings", category="UI", weight=0),
        PaletteEntry(label="tool: open_app", hint="launch or close an app", category="Tool", weight=20),
        PaletteEntry(label="tool: web_search", hint="search the web", category="Tool", weight=20),
        PaletteEntry(label="tool: notepad", hint="open a text editor", category="Tool", weight=20),
        PaletteEntry(label="plugin: spotify_control", hint="playback control", category="Plugin", weight=30),
    ]


def test_empty_query_shows_everything(entries):
    """Opening the palette is itself a discovery surface."""
    out = filter_entries(entries, "")
    assert len(out) == len(entries)


def test_filters_by_label(entries):
    out = filter_entries(entries, "open_app")
    assert any("open_app" in e.label for e in out)


def test_filters_by_hint(entries):
    out = filter_entries(entries, "playback")
    assert any("spotify" in e.label for e in out)


def test_ui_commands_rank_above_tools(entries):
    out = filter_entries(entries, "")
    assert out[0].category == "UI"


def test_limit_is_respected(entries):
    assert len(filter_entries(entries, "", limit=2)) == 2


def test_unmatched_query_returns_empty(entries):
    assert filter_entries(entries, "zzzzqqq") == []


# â”€â”€ selection mapping â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_selecting_a_tool_produces_a_request():
    e = PaletteEntry(label="tool: web_search", category="Tool")
    assert "web_search" in selection_to_text(e)


def test_selecting_a_plugin_produces_a_request():
    e = PaletteEntry(label="plugin: spotify_control", category="Plugin")
    assert "spotify_control" in selection_to_text(e)


def test_selecting_none_is_safe():
    assert selection_to_text(None) == ""


# â”€â”€ entry building from live registries â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_build_entries_from_action_registry():
    """Tools must appear automatically from the registry with no hand-kept list,
    which is what stops the palette going stale."""
    from core.action_loader import discover_actions
    reg = discover_actions(actions_dir=_ROOT / "actions",
                           reserved_names=set(), logger=lambda m: None)
    out = build_entries(action_registry=reg)
    labels = {e.label for e in out}
    assert "tool: open_app" in labels
    assert "tool: file_controller" in labels
    tool_entries = [e for e in out if e.category == "Tool"]
    assert len(tool_entries) >= 50, "expected the full action set to be listed"


def test_build_entries_includes_ui_commands():
    out = build_entries(ui_commands={"Toggle theme": lambda: None})
    assert any(e.label == "Toggle theme" and e.category == "UI" for e in out)


def test_build_entries_survives_a_broken_registry():
    """A registry that raises must not take the palette down with it."""

    class Broken:
        def names(self):
            raise RuntimeError("registry exploded")

    out = build_entries(action_registry=Broken(), ui_commands={"x": lambda: None})
    assert len(out) == 1


def test_ui_command_entries_are_runnable():
    called = []
    out = build_entries(ui_commands={"Do the thing": lambda: called.append(1)})
    entry = next(e for e in out if e.label == "Do the thing")
    assert entry.run is not None
    entry.run()
    assert called == [1]


# â”€â”€ shortcuts â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.fixture(scope="module")
def qapp():
    """A QApplication for tests that must construct widgets.

    QWidget() without a running QApplication aborts the process outright, so
    there is no way to catch this in the test â€” it has to be provided.
    QT_QPA_PLATFORM=offscreen keeps it off any real display.
    """
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_shortcut_manager_registers_and_lists(qapp):
    from ui.shortcuts import ShortcutManager
    from PyQt6.QtWidgets import QWidget

    mgr = ShortcutManager(QWidget())
    mgr.add("Ctrl+T", "Test", lambda: None, "General")
    specs = mgr.specs()
    assert len(specs) == 1
    assert specs[0].seq == "Ctrl+T"
    assert specs[0].category == "General"


def test_shortcut_help_rendering_includes_every_spec(qapp):
    from ui.shortcuts import ShortcutManager
    from PyQt6.QtWidgets import QWidget

    mgr = ShortcutManager(QWidget())
    mgr.add("Ctrl+T", "Alpha", lambda: None, "General")
    mgr.add("Ctrl+Y", "Beta", lambda: None, "Voice")
    text = mgr.help_markdown()
    assert "Alpha" in text and "Beta" in text
    assert "Ctrl+T" in text
    assert "General" in text and "Voice" in text


def test_duplicate_shortcuts_are_detected(qapp):
    """Qt silently drops a duplicate binding, so a conflict must be visible."""
    from ui.shortcuts import ShortcutManager
    from PyQt6.QtWidgets import QWidget

    mgr = ShortcutManager(QWidget())
    mgr.add("Ctrl+T", "One", lambda: None)
    mgr.add("Ctrl+T", "Two", lambda: None)
    dupes = mgr.conflicts()
    assert dupes and dupes[0][0] == "Ctrl+T"


def test_default_set_has_no_conflicts(qapp):
    """The shipped default bindings must not collide with each other."""
    from ui.shortcuts import ShortcutManager, register_defaults
    from PyQt6.QtWidgets import QWidget

    mgr = ShortcutManager(QWidget())
    register_defaults(mgr, object())     # no handlers needed to check bindings
    assert mgr.conflicts() == [], (
        f"duplicate default shortcut bindings: {mgr.conflicts()}"
    )


def test_default_set_contains_the_key_discoverability_bindings(qapp):
    """These three are the ones that were missing entirely before."""
    from ui.shortcuts import ShortcutManager, register_defaults
    from PyQt6.QtWidgets import QWidget

    mgr = ShortcutManager(QWidget())
    register_defaults(mgr, object())
    seqs = {s.seq for s in mgr.specs()}
    assert "Ctrl+K" in seqs, "command palette must be bound"
    assert "Ctrl+/" in seqs, "shortcut help must be bound"
    assert "Ctrl+H" in seqs, "history must be bound"


def test_register_defaults_tolerates_a_bare_object(qapp):
    """It resolves handlers lazily, so registering against an object with no
    methods must not raise."""
    from ui.shortcuts import ShortcutManager, register_defaults
    from PyQt6.QtWidgets import QWidget

    mgr = ShortcutManager(QWidget())
    register_defaults(mgr, object())
    assert len(mgr.specs()) > 10


def test_missing_handler_is_a_noop_not_a_crash(qapp):
    """A window that has not grown a handler yet must fail silently."""
    from ui.shortcuts import ShortcutManager, register_defaults
    from PyQt6.QtWidgets import QWidget

    mgr = ShortcutManager(QWidget())
    register_defaults(mgr, object())     # object() has no _open_command_palette
    spec = next(s for s in mgr.specs() if s.seq == "Ctrl+K")
    assert spec.handler is not None
    spec.handler()                       # must not raise


# â”€â”€ widget importability â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.parametrize("mod", [
    "ui.palette_widget",
    "ui.history_panel",
    "ui.shortcut_help",
])
def test_widget_modules_import(mod, qapp):
    """Import-only smoke test: constructing these needs a QApplication."""
    __import__(mod)
