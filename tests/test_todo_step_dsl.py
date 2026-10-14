"""
tests/test_todo_step_dsl.py — Autonomous task steps: parsing and honest reporting.

TWO BUGS, BOTH OBSERVED ON THE USER'S MACHINE
---------------------------------------------
Asking for "Notepad khol ke usmein 10 bar hii likhein" produced:

    TODO: Step 1/1 — computer_control:type text='hii\nhii...'
    [Computer] status
    TODO: Step 1/1 done — Unknown action: 'status'
    SYS: Task 'Notepad khol ke usmein 10 bar "hii" likhein' completed
         successfully! All 1 sub-tasks finished.

Nothing had been typed into Notepad, and the user was told it had worked.

1. THE STEP WAS DISCARDED. The executor's generic branch saw that
   computer_control has an "action" property and returned {"action": "status"},
   throwing away both the `type` verb and the text payload.

2. THE FAILURE WAS NOT COUNTED. Verification only covered steps that name a
   file on disk. A step that types text names no file, so a tool refusing the
   request sailed through and the task was reported as a success.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from actions.todo_agent import (  # noqa: E402
    _parse_action_dsl,
    _tool_reported_failure,
)


# ── parsing the step DSL ────────────────────────────────────────────────────

def test_the_exact_failing_step_parses():
    """From the log: computer_control:type text='hii\\nhii\\n...'"""
    parsed = _parse_action_dsl(r"type text='hii\nhii\nhii'")
    assert parsed["action"] == "type"
    assert parsed["text"] == "hii\nhii\nhii"


def test_newline_escapes_become_real_newlines():
    """Otherwise the literal characters \\ and n reach the keyboard and the
    user gets 'hiinhii' instead of three lines."""
    parsed = _parse_action_dsl(r"type text='hii\nhii'")
    assert "\n" in parsed["text"]
    assert "\\n" not in parsed["text"]


def test_tab_escape_is_expanded():
    parsed = _parse_action_dsl(r"type text='a\tb'")
    assert parsed["text"] == "a\tb"


def test_backslash_in_a_windows_path_survives():
    """The escape handling must not eat a legitimate backslash."""
    parsed = _parse_action_dsl(r"type text='C:\Users'")
    assert "C:" in parsed["text"]


def test_multiple_key_value_pairs():
    parsed = _parse_action_dsl("click x=100 y=200")
    assert parsed == {"action": "click", "x": "100", "y": "200"}


def test_value_containing_equals_signs():
    parsed = _parse_action_dsl('type text="a=b and c=d"')
    assert parsed["text"] == "a=b and c=d"


def test_spaces_inside_a_quoted_value():
    parsed = _parse_action_dsl("type text='hello world'")
    assert parsed["text"] == "hello world"


def test_bare_verb_is_an_action():
    assert _parse_action_dsl("screenshot") == {"action": "screenshot"}
    assert _parse_action_dsl("open") == {"action": "open"}


def test_double_quoted_values_work():
    parsed = _parse_action_dsl('type text="hello"')
    assert parsed["text"] == "hello"


# ── plain language must NOT be hijacked ─────────────────────────────────────
#
# Found while writing the parser: accepting any leading word as a verb turned
# "write the file to desktop" into {"action": "write"}, which would have
# bypassed the plain-language handling that follows and produces far better
# plans. Requiring at least one key=value pair keeps the DSL unambiguous.

@pytest.mark.parametrize("plain", [
    "Notepad khol ke usmein 10 bar hii likhein",
    "write the file to desktop",
    "write a plan for java",
    "open the notepad application",
    "research and save the notes",
    "save everything to my desktop folder",
])
def test_plain_language_is_not_treated_as_dsl(plain):
    assert _parse_action_dsl(plain) == {}, plain


def test_empty_input_is_not_dsl():
    assert _parse_action_dsl("") == {}
    assert _parse_action_dsl("   ") == {}
    assert _parse_action_dsl(None) == {}


# ── honest success reporting ────────────────────────────────────────────────

def test_unknown_action_is_a_failure():
    """The exact string that was announced as success."""
    assert _tool_reported_failure("Unknown action: 'status'") is True


@pytest.mark.parametrize("output", [
    "FAILED: boom",
    "Error: no such file",
    "Could not open the window",
    "Couldn't find the file",
    "Unable to launch the app",
    "Unsupported action",
    "Not supported on this system",
    "No window with that title",
    "File not found",
    "",
])
def test_refusals_are_failures(output):
    assert _tool_reported_failure(output) is True, output


@pytest.mark.parametrize("output", [
    "File created: index.html",
    "Opened Notepad.",
    "Typed 10 lines into Notepad",
    "Search complete: 5 results",
    "Screenshot saved to desktop/shot.png",
    "Task created for 13:39",
    "Answer: 42",
])
def test_real_results_are_not_failures(output):
    """False failures poison the learning signal and make honest work look
    broken, so the detector has to stay narrow."""
    assert _tool_reported_failure(output) is False, output


def test_failure_markers_live_in_one_place():
    """The detector must reuse the shared definition rather than keeping a
    second, subtly different list that can drift."""
    from core.action_loader import _looks_like_failure
    assert _looks_like_failure("Unknown action: 'status'") is True
    assert _looks_like_failure("Opened Notepad.") is False


def test_task_completion_message_reflects_failures():
    """The honest-completion branch must still exist and still branch.

    Asserted on the code rather than the string, because the message mentions
    "completed successfully" in both the true and the failure branch.
    """
    src = (_ROOT / "actions" / "todo_agent.py").read_text(encoding="utf-8-sig")
    code = [ln for ln in src.splitlines()
            if "completed successfully" in ln and not ln.strip().startswith("#")]
    assert code, "the success message disappeared"
    assert "if failed == 0:" in src, "success must still be conditional on failures"
    assert "_tool_reported_failure(step_output)" in src, (
        "a tool refusing the request must mark the step failed"
    )


def test_tool_failure_check_runs_after_the_dispatch():
    """Ordering matters: the check has to see the tool's output, so it cannot
    run before the dispatch."""
    src = (_ROOT / "actions" / "todo_agent.py").read_text(encoding="utf-8-sig")
    dispatch_at = src.index("_dispatch_step_to_tool(step")
    check_at = src.index("_tool_reported_failure(step_output)")
    assert dispatch_at < check_at