"""
tests/test_error_summaries.py — Tests for turning tracebacks into answers.

WHY
---
Observed on a real machine: J.A.R.V.I.S generated a calculator, wrote it to
disk and ran it. It divided by zero and the reply contained:

    Traceback (most recent call last):
      File "calculator.py", line 12, in divide
    ZeroDivisionError: division by zero

That reached the user verbatim, because actions/code_helper.py returned
`result.stderr` unchanged. Any crash in generated code produced the same wall
of CPython internals.

The two ways to get this wrong are: dump the traceback (unhelpful) or swallow
it (undebuggable). These tests pin the middle path - the exception type, the
message and the location survive; the frames go to the log.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from core.errors import (  # noqa: E402
    extract_frames,
    full_context,
    summarize_python_error,
)


# The exact failure from the session log.
CALCULATOR = '''Traceback (most recent call last):
  File "calculator.py", line 12, in divide
    return a / b
           ~~^~~
ZeroDivisionError: division by zero
'''

TYPICAL = '''Traceback (most recent call last):
  File "app.py", line 3, in <module>
    import missing_module
ModuleNotFoundError: No module named 'missing_module'
'''


# ── the reported case ───────────────────────────────────────────────────────

def test_calculator_traceback_names_the_exception():
    out = summarize_python_error(CALCULATOR)
    assert "ZeroDivisionError" in out
    assert "division by zero" in out


def test_calculator_traceback_names_the_file_and_line():
    """That is what a person needs to act on: which file, which line."""
    out = summarize_python_error(CALCULATOR)
    assert "calculator.py" in out
    assert "12" in out


def test_calculator_traceback_is_short():
    """The whole point. A summary that dumps the frames has not fixed it."""
    out = summarize_python_error(CALCULATOR)
    assert len(out) < 200
    assert "Traceback (most recent call last)" not in out
    assert "~~^~~" not in out


def test_function_name_is_kept_when_present():
    assert "divide" in summarize_python_error(CALCULATOR)


# ── other shapes ────────────────────────────────────────────────────────────

def test_module_not_found():
    out = summarize_python_error(TYPICAL)
    assert "ModuleNotFoundError" in out
    assert "missing_module" in out


def test_key_error_has_no_colon_message():
    err = ("Traceback (most recent call last):\n"
           '  File "a.py", line 9, in f\nKeyError: \'thing\'\n')
    out = summarize_python_error(err)
    assert "KeyError" in out
    assert "thing" in out


def test_bare_exception_without_message():
    err = ("Traceback (most recent call last):\n"
           '  File "a.py", line 2, in f\nSystemExit\n')
    out = summarize_python_error(err)
    assert "SystemExit" in out


def test_multiple_frames_points_at_the_raising_one():
    """The last frame is the one that threw, not the outermost call."""
    err = ('Traceback (most recent call last):\n'
           '  File "a.py", line 3, in <module>\n'
           "    main()\n"
           '  File "a.py", line 7, in main\n'
           "    helper()\n"
           '  File "b.py", line 21, in helper\n'
           "    raise ValueError('boom')\n"
           "ValueError: boom\n")
    out = summarize_python_error(err)
    assert "ValueError" in out and "boom" in out
    assert "b.py" in out and "21" in out
    assert "a.py" not in out, "should point at the raising frame"


def test_windows_path_is_reduced_to_a_filename():
    err = ('Traceback (most recent call last):\n'
           '  File "C:\\\\Users\\\\x\\\\proj\\\\calc.py", line 5, in divide\n'
           "ZeroDivisionError: division by zero\n")
    out = summarize_python_error(err)
    assert "calc.py" in out
    assert "Users" not in out
    assert "5" in out


def test_long_message_is_truncated():
    err = "ValueError: " + ("x" * 5000)
    out = summarize_python_error(err, max_message=50)
    assert "..." in out
    assert len(out) < 200


def test_empty_stderr_says_so():
    assert "no error output" in summarize_python_error("")
    assert "no error output" in summarize_python_error(None)


def test_whitespace_only_stderr_says_so():
    assert "no error output" in summarize_python_error("   \n  \n")


def test_unrecognised_stderr_is_still_summarised():
    """npm, node and yarn failures are not CPython tracebacks and are worth
    summarising too; a blank message would be worse than a rough one."""
    err = "npm ERR! code ELIFECYCLE\nnpm ERR! errno 1"
    out = summarize_python_error(err)
    assert out
    assert "failed" in out.lower()


def test_a_warning_at_the_end_does_not_become_the_error():
    """The last line is not always the failure; a trailing warning line is
    noise and must not be reported as the cause."""
    err = ('Traceback (most recent call last):\n'
           '  File "a.py", line 2, in f\n'
           "ValueError: real problem\n"
           "warning: deprecated thing\n")
    out = summarize_python_error(err)
    assert "ValueError" in out
    assert "deprecated thing" not in out


def test_empty_message_is_handled():
    err = ('Traceback (most recent call last):\n'
           '  File "a.py", line 1, in f\nRuntimeError\n')
    assert "RuntimeError" in summarize_python_error(err)


# ── frames extraction ───────────────────────────────────────────────────────

def test_extract_frames_returns_ordered_tuples():
    frames = extract_frames(TYPICAL)
    assert len(frames) == 1
    fname, lineno, func = frames[0]
    assert fname == "app.py"
    assert lineno == 3
    assert func == "<module>"


def test_extract_frames_on_non_traceback_is_empty():
    assert extract_frames("just some text") == []


def test_extract_frames_handles_missing_function():
    frames = extract_frames('  File "a.py", line 4\n')
    assert frames == [("a.py", 4, "")]


# ── nothing is lost ─────────────────────────────────────────────────────────

def test_full_context_preserves_the_whole_traceback():
    """The summary is for the user; this is for whoever has to debug it."""
    ctx = full_context(CALCULATOR)
    assert "Traceback" in ctx
    assert "return a / b" in ctx


def test_full_context_truncates_something_huge():
    ctx = full_context("x" * 50_000, max_chars=100)
    assert len(ctx) < 200
    assert "truncated" in ctx


def test_full_context_of_empty_is_empty():
    assert full_context("") == ""
    assert full_context(None) == ""


# ── the call sites actually use it ──────────────────────────────────────────

def test_code_helper_no_longer_returns_raw_stderr():
    """Behavioural, not a grep.

    A grep for the old pattern would match the comment that explains why it
    was replaced, and pass for the wrong reason.
    """
    src = (_ROOT / "actions" / "code_helper.py").read_text(encoding="utf-8-sig")
    code = [ln for ln in src.splitlines()
            if "STDERR" in ln and not ln.strip().startswith("#")]
    assert not code, f"raw stderr still surfaced: {code}"
    assert "summarize_python_error" in src


def test_dev_agent_no_longer_returns_raw_stderr():
    src = (_ROOT / "actions" / "dev_agent.py").read_text(encoding="utf-8-sig")
    code = [ln for ln in src.splitlines()
            if "STDERR:" in ln and not ln.strip().startswith("#")]
    assert not code, f"raw stderr still surfaced: {code}"
    assert "summarize_python_error" in src


def test_every_call_site_keeps_the_full_traceback_in_the_log():
    """Summarising must not mean losing it."""
    for name in ("code_helper.py", "dev_agent.py"):
        src = (_ROOT / "actions" / name).read_text(encoding="utf-8-sig")
        assert "full_context" in src, f"{name} discards the traceback entirely"