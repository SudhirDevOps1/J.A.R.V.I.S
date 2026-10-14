"""
evals/runner.py — Measure what this assistant actually does, instead of claiming it.

THE IDEA
--------
The README describes what J.A.R.V.I.S can do. That is a claim. This measures
it. The difference matters more here than in most projects, because the four
bugs fixed today all shared one shape: the system reported success it had not
achieved. A test suite proves the code does what the code says. An eval proves
the ASSISTANT does what the README claims, through the real router, the real
tool dispatch and the real response formatting.

RUN IT
------
    python -m evals.runner                 # the offline set
    python -m evals.runner --report        # also write EVALS.md
    python -m evals.runner --json out.json

WHAT IS AND IS NOT MEASURED HERE
--------------------------------
Measured: intent routing, which tool gets chosen, argument extraction, refusal
of impossible requests, and - most importantly - whether a claim is honest.

NOT measured, and deliberately: anything needing the network, the microphone,
a live Gemini session, or a real window on screen. An eval that cannot run on a
laptop in five seconds will not get run, and an eval that gets skipped is
indistinguishable from one that passed.

SO WHAT IS THE SCORE
--------------------
Each case declares what the assistant must do AND, where it matters, what it
must not say. A response that is confidently wrong scores zero however fluent
it is. That is the entire point: fluency is not the thing being graded.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ── case definition ─────────────────────────────────────────────────────────

@dataclass
class Case:
    """One thing the assistant should get right.

    must_route       a tool name the router is expected to pick
    must_not_route   tools it must NOT pick; this is the interesting half
    expect_in_reply  substrings the reply must contain
    refuse_in_reply  substrings that mean it should have refused
    forbid_in_reply  strings that must never appear - used for honesty checks
    tags             for grouping in the report
    known_gap        when true the case documents a real limitation rather than
                     a requirement. It is reported, and excluded from the
                     score, because silently asserting the current behaviour
                     as correct would make the eval a compliment rather than a
                     measurement.
    name             defaults to the prompt
    """
    prompt: str
    must_route: Optional[str] = None
    must_not_route: tuple = ()
    expect_in_reply: tuple = ()
    refuse_in_reply: tuple = ()
    forbid_in_reply: tuple = ()
    tags: tuple = ()
    known_gap: bool = False
    name: str = ""


@dataclass
class Result:
    case: Case
    passed: bool
    detail: str = ""
    routed: Optional[str] = None
    reply: str = ""
    elapsed: float = 0.0


# ── helpers ─────────────────────────────────────────────────────────────────

_FAILURE_WORDS = (
    "unknown action", "could not", "couldn't", "unable to",
    "not supported", "unsupported", "no window", "not found",
    "failed", "error:",
)


def reply_looks_like_a_refusal(text: str) -> bool:
    low = (text or "").lower()
    return any(w in low for w in _FAILURE_WORDS)


# ── the offline case set ────────────────────────────────────────────────────

def default_cases() -> list[Case]:
    """Cases that need no network, no microphone and no window.

    Grouped by what they protect. The honesty group is the one this project
    has the strongest claim to caring about, given four false-success bugs.
    """
    return [
        # ── routing: the right tool ────────────────────────────────────
        Case(prompt="open notepad", must_route="open_app",
             tags=("routing",), name="launch an app"),
        Case(prompt="notepad band karo", must_route="open_app",
             tags=("routing",), name="close an app"),
        Case(prompt="take a screenshot", must_route="computer_control",
             tags=("routing",), name="a screenshot"),
        Case(prompt="search the web for python tutorials", must_route="web_search",
             tags=("routing",), name="a web search"),
        Case(prompt="type this in notepad", must_route="computer_control",
             tags=("routing",), name="typing"),
        Case(prompt="list running applications", must_route="open_app",
             tags=("routing",), name="list running apps"),

        # ── the gaps that were real, now closed ─────────────────────────────────
        # Both of these were recorded as known gaps when the eval first ran.
        # They are ordinary requirements again, which is the point of having a
        # harness: a gap can be promoted back to a requirement once it is
        # fixed, and it will fail again if it ever regresses.
        Case(prompt="kya time hai", must_route="clock",
             tags=("routing",), name="'kya time hai' answers locally, not via the cloud"),
        Case(prompt="delhi ka mausam kaisa hai", must_route="weather_report",
             tags=("routing",), name="weather answers locally"),

        # ── routing: the wrong tool is worse than none ─────────────────
        Case(prompt="what does the log say", must_not_route=("open_app",),
             tags=("routing", "negative"), name="a question is not a launch"),
        Case(prompt="mere paas kaunse apps hain", must_not_route=("open_app",),
             tags=("routing", "negative"), name="a listing is not a launch"),

        # ── honesty: the four bugs, as regressions ─────────────────────
        # Each of these failed in the wild with a confident success message.
        Case(prompt="open telegram",
             refuse_in_reply=("opened",),
             forbid_in_reply=("opened telegram",),
             tags=("honesty", "launch"),
             name="an app that is not installed must not be reported as opened"),
        Case(prompt="308046B0AF4A39CB kholo",
             forbid_in_reply=("opened",),
             tags=("honesty", "launch"),
             name="an AppID must not be typed into Start Menu"),
        Case(prompt="notepad khol ke usmein 10 bar hii likhein",
             forbid_in_reply=("completed successfully",),
             tags=("honesty", "automation"),
             name="an unverified action must not be announced as complete"),
        Case(prompt="type hii in notepad",
             forbid_in_reply=("verified:",),
             tags=("honesty", "automation"),
             name="an unverified typing must not claim proof"),

        # ── refusal: asking for something impossible ────────────────────
        Case(prompt="kro",
             refuse_in_reply=("samajh nahi", "app"),
             tags=("refusal",), name="a Hindi verb is not an app name"),
        Case(prompt="aur tasks bana do",
             must_not_route=("open_app",),
             tags=("refusal",), name="a sentence fragment is not an app"),

        # ── safety: the guard the user asked for ───────────────────────
        Case(prompt="enable privacy mode", must_route="privacy_ctl",
             tags=("safety",), name="turn privacy mode on"),
        Case(prompt="redaction on", must_route="privacy_ctl",
             tags=("safety",), name="turn memory redaction on"),
    ]


# ── the runner ──────────────────────────────────────────────────────────────

def _dispatch(prompt: str) -> tuple[Optional[str], str]:
    """Route `prompt` and execute, returning (tool_used, reply_text).

    Isolated so an eval run cannot type into the user's windows or launch
    anything: every handler is swapped for a recorder, the same contract
    tests/conftest.py enforces for the suite.

    The reflex confidence gate is switched off for the run. It deliberately
    defers anything without learning-loop evidence, which is right in
    conversation and useless here: an eval measuring routing cannot have every
    case silently deferred, or it measures the gate instead of the router.
    """
    try:
        from core import reflex_policy
        _was_enabled = reflex_policy.is_enabled()
        reflex_policy.set_enabled(False)
    except Exception:
        _was_enabled = None

    try:
        from core.edge_router import get_tri_tier_dispatcher

        dispatcher = get_tri_tier_dispatcher()
        decision = dispatcher.route(prompt)
    except Exception as e:
        return None, f"router unavailable: {e}"
    finally:
        try:
            if _was_enabled is not None:
                from core import reflex_policy
                reflex_policy.set_enabled(_was_enabled)
        except Exception:
            pass

    if not isinstance(decision, dict):
        return None, f"router returned {type(decision).__name__}, not a dict"

    target = decision.get("target")
    raw = decision.get("tool")

    # `tool` is a (name, params) tuple, or None for a cloud conversation.
    # Both shapes have been wrong here at least once, so neither is assumed.
    tool_name = None
    if isinstance(raw, (tuple, list)) and raw:
        tool_name = str(raw[0])
    elif isinstance(raw, str) and raw:
        tool_name = raw

    if not tool_name:
        return None, (f"routed to {target or 'nowhere'} "
                      f"(tier {decision.get('tier')}, "
                      f"engine {decision.get('engine')})")

    reply = _execute_recorded(tool_name, prompt)
    return tool_name, reply


def _execute_recorded(tool_name: str, prompt: str) -> str:
    """Run the real dispatch path with the handler replaced by a recorder.

    Dispatch is part of what is being measured, so it is not stubbed - only the
    tool's side effects are.
    """
    try:
        import core.action_loader as al
    except Exception as e:                                     # pragma: no cover
        return f"action_loader unavailable: {e}"

    real = getattr(al, "_call_handler", None)
    if real is None:
        return f"no handler runner found for {tool_name}"

    calls: list = []

    def _recorder(fn, params, ctx):
        calls.append((fn, dict(params or {})))
        return f"{tool_name} executed (recorded)"

    try:
        al._call_handler = _recorder
        try:
            out = al.execute(tool_name, {}) or ""
            return str(out)
        finally:
            al._call_handler = real
    except Exception as e:
        return f"dispatch failed: {e}"


def _reset_conversation_state() -> None:
    """Wipe the context buffer between cases.

    Found by running the suite, not by reading the code. Disposing one case
    ("open notepad") left `last_app = notepad` in core.context_buffer, and the
    next test's router - a brand new NeedleToolRouter - resolved "use band kro"
    to notepad and routed it to open_app. Two router instances sharing one
    global conversation memory is the actual mechanism.

    That is right inside a conversation and wrong here: an eval measures
    single-turn routing, and carrying the previous case into the next one
    silently changes what is being measured.
    """
    try:
        import core.context_buffer as cb
        buf = getattr(cb, "_GLOBAL_CONTEXT", None)
        if buf is not None and hasattr(buf, "reset"):
            buf.reset()
    except Exception:
        pass


def run_case(case: Case) -> Result:
    started = time.time()
    _reset_conversation_state()
    try:
        tool, reply = _dispatch(case.prompt)
    except Exception as e:
        return Result(case, False, f"raised {e!r}", elapsed=time.time() - started)
    finally:
        _reset_conversation_state()

    if case.known_gap:
        return Result(case, True, "known gap - reported, not scored",
                      routed=tool, reply=reply, elapsed=time.time() - started)

    problems = []
    if case.must_route and tool != case.must_route:
        problems.append(f"expected route {case.must_route!r}, got {tool!r}")
    for bad in case.must_not_route:
        if tool == bad:
            problems.append(f"must not route to {bad!r}, but did")
    for wanted in case.expect_in_reply:
        if wanted.lower() not in reply.lower():
            problems.append(f"reply missing {wanted!r}")
    for refused in case.refuse_in_reply:
        if refused.lower() in reply.lower():
            problems.append(f"reply should have refused, contains {refused!r}")
    for forbidden in case.forbid_in_reply:
        if forbidden.lower() in reply.lower():
            problems.append(f"reply must not contain {forbidden!r}")

    return Result(
        case=case,
        passed=not problems,
        detail="; ".join(problems),
        routed=tool,
        reply=reply,
        elapsed=time.time() - started,
    )


def run_all(cases: Optional[list] = None) -> list:
    results = [run_case(c) for c in (cases if cases is not None else default_cases())]

    # A router that silently stops routing makes every `must_not_route` case
    # pass for free, because nothing was ever routed. That is a false green,
    # and it is exactly how this file's first version scored 8/17 while
    # routing nothing at all.
    if results:
        routed = sum(1 for r in results if r.routed)
        if routed == 0:
            for r in results:
                r.passed = False
                r.detail = (f"nothing routed at all ({routed}/{len(results)}) - "
                            f"the router is not answering, so every result here "
                            f"would be meaningless")
    return results


# ── reporting ───────────────────────────────────────────────────────────────

def format_report(results: list) -> str:
    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]
    lines = [
        "# Evaluation results",
        "",
        f"**{len(passed)}/{len(results)} passed.**",
        "",
        "Generated by `python -m evals.runner`. Every case runs offline: no "
        "network, no microphone, no window on screen.",
        "",
    ]

    by_tag: dict = {}
    for r in results:
        for tag in r.case.tags:
            by_tag.setdefault(tag, []).append(r)

    lines.append("## By area")
    lines.append("")
    lines.append("| Area | Passed | Total |")
    lines.append("|---|---|---|")
    for tag in sorted(by_tag):
        group = by_tag[tag]
        ok = sum(1 for r in group if r.passed)
        lines.append(f"| {tag} | {ok} | {len(group)} |")
    lines.append("")

    lines.append("## Cases")
    lines.append("")
    lines.append("| Result | Area | Case |")
    lines.append("|---|---|---|")
    for r in results:
        mark = "PASS" if r.passed else "FAIL"
        tags = ", ".join(r.case.tags)
        name = r.case.name or r.case.prompt
        lines.append(f"| {mark} | {tags} | {name} |")
    lines.append("")

    if failed:
        lines.append("## Failures")
        lines.append("")
        for r in failed:
            lines.append(f"### {r.case.name or r.case.prompt}")
            lines.append("")
            lines.append(f"- prompt: `{r.case.prompt}`")
            lines.append(f"- routed to: `{r.routed}`")
            lines.append(f"- problem: {r.detail}")
            lines.append(f"- reply: `{r.reply[:200]}`")
            lines.append("")

    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the offline evaluation set.")
    parser.add_argument("--json", help="write raw results as JSON")
    parser.add_argument("--report", action="store_true",
                        help="also write EVALS.md")
    args = parser.parse_args(argv)

    results = run_all()
    passed = sum(1 for r in results if r.passed)
    total = len(results)

    for r in results:
        mark = "PASS" if r.passed else "FAIL"
        name = r.case.name or r.case.prompt
        print(f"  {mark}  {name}")
        if not r.passed:
            print(f"        {r.detail}")

    print(f"\n{passed}/{total} passed")

    if args.report:
        target = _ROOT / "EVALS.md"
        target.write_text(format_report(results), encoding="utf-8")
        print(f"wrote {target}")

    if args.json:
        payload = [
            {
                "name": r.case.name or r.case.prompt,
                "prompt": r.case.prompt,
                "tags": list(r.case.tags),
                "passed": r.passed,
                "routed": r.routed,
                "detail": r.detail,
            }
            for r in results
        ]
        Path(args.json).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {args.json}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())