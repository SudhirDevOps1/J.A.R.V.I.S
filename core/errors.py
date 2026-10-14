"""
core/errors.py — turn a Python traceback into something a person can act on.

THE PROBLEM
-----------
Observed on a real machine. J.A.R.V.I.S generated a calculator, wrote it to
disk and ran it. The script divided by zero, and this came back to the user
verbatim:

    Traceback (most recent call last):
      File "calculator.py", line 12, in divide
        return a / b
    ZeroDivisionError: division by zero

That is developer output, not an answer. It was surfaced by actions/code_helper
returning `result.stderr` unchanged, so every crash of generated code dumped a
raw stack trace into the conversation.

Two failure modes, pulling in opposite directions:

  * dump the traceback  -> user gets a wall of Python internals and no idea what
    their script did or where to fix it
  * swallow it entirely -> the user is told "something failed" with no way to
    debug, and the assistant looks unreliable for reasons it cannot explain

So: the exception type, the message, and the file and line are kept, because
those are what a person needs. The frames, the caret diagrams and the source
echoes go to the log, where a developer can find them.

WHY A MODULE AND NOT AN INLINE FIX
----------------------------------
Two call sites already had this problem in slightly different shapes
(actions/code_helper.py, actions/dev_agent.py) and a third will. Keeping the
parsing here means one place to fix and somewhere to test it, because
traceback parsing is exactly the kind of thing that breaks quietly on an
unusual input.
"""
from __future__ import annotations

import re
from typing import List, Optional

# The final line of a CPython traceback: "ExceptionType: message", where the
# message may span multiple lines (SyntaxError does this) and may be absent
# entirely for a bare class name.
_EXC_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Exit|Interrupt|"
                       r"Warning|Timeout|Failure|Interrupt))\s*:\s*(.*)$")

# "  File "calculator.py", line 12, in divide" and the Windows/Posix variants.
_FILE_LINE = re.compile(r'^\s*File "([^"]+)", line (\d+)(?:, in (.*))?')

# The caret / source-echo block CPython prints under a failing line.
_CARET = re.compile(r"^\s*\^+\s*$")

_BARE_EXC = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Exit|Interrupt|Warning|Timeout|Failure))\s*$")

# Tool-specific noise that is not the failure.
_NOISE_PREFIXES = (
    "warning:", "note:", "deprecationwarning",
    "see https://", "  warnings.warn",
)


def _last_meaningful(lines: List[str]) -> Optional[str]:
    for raw in reversed(lines):
        line = raw.rstrip()
        if not line.strip():
            continue
        low = line.strip().lower()
        if low.startswith(_NOISE_PREFIXES):
            continue
        if _CARET.match(line):
            continue
        return line.strip()
    return None


def extract_frames(stderr: str) -> List[tuple]:
    """(filename, lineno, function) for each frame, in order.

    Useful for pointing at the exact line a user needs to open. The last frame
    is the one that raised, which is almost always the one they care about.
    """
    frames: List[tuple] = []
    for raw in (stderr or "").splitlines():
        m = _FILE_LINE.match(raw)
        if m:
            frames.append((m.group(1), int(m.group(2)),
                           (m.group(3) or "").strip()))
    return frames


def summarize_python_error(stderr: str, *, max_message: int = 240) -> str:
    """A one-or-two line description of what went wrong.

    Falls back to the tail of stderr when it is not a recognisable CPython
    traceback, because a Node, Ruby or npm failure is also worth summarising
    and a blank message would be worse than a rough one.
    """
    text = str(stderr or "")
    if not text.strip():
        return "The script failed with no error output."

    frames = extract_frames(text)
    lines = text.splitlines()
    tail = _last_meaningful(lines)

    exc_type = None
    exc_msg = ""
    if tail:
        m = _EXC_LINE.match(tail)
        if m:
            exc_type, exc_msg = m.group(1), m.group(2).strip()
        else:
            m = _BARE_EXC.match(tail)
            if m:
                exc_type, exc_msg = m.group(1), ""

    # SyntaxError prints the offending source before the message, and the
    # message can be long; the first line of it is what matters.
    if exc_msg and len(exc_msg) > max_message:
        exc_msg = exc_msg[:max_message].rstrip() + "..."

    where = ""
    if frames:
        fname, lineno, func = frames[-1]
        base = fname.replace("\\", "/").split("/")[-1]
        where = f" ({base}, line {lineno}"
        if func:
            where += f", in {func}"
        where += ")"

    if exc_type:
        head = f"{exc_type}: {exc_msg}" if exc_msg else exc_type
        return f"The script failed with {head}{where}."

    # Unrecognised shape: quote the tail rather than inventing a diagnosis.
    fallback = " / ".join(l.strip() for l in lines[-3:] if l.strip())
    if len(fallback) > max_message:
        fallback = fallback[:max_message].rstrip() + "..."
    return f"The script failed: {fallback}" if fallback else \
        "The script failed with an unrecognised error."


def full_context(stderr: str, *, max_chars: int = 4000) -> str:
    """The complete traceback, for the log rather than for the user.

    Called alongside summarize_python_error so nothing is lost - the summary
    is for the conversation, this is for whoever has to debug it.
    """
    text = (stderr or "").rstrip()
    if not text:
        return ""
    if len(text) > max_chars:
        text = text[:max_chars] + "\n… (truncated)"
    return text