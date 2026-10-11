"""
core/reflex_policy.py — Confidence gate for the Tier-1 reflex router.

THE PROBLEM
-----------
core/edge_router.py routes voice commands with a ~180-branch regex cascade
matched in order, first-match-wins, with no scoring. It cannot distinguish a
real request from prose that merely contains a verb:

    "notepad band karo"                 -> close "notepad"   (correct)
    "timers aur tasks band karo"         -> close "aur tasks" (nonsense)
    "main nahi kiya hu use band kro"     -> close "hu use"    (nonsense)

Both used to execute unconditionally, and the result was announced to the user
as fact. A wrong guess here is not a cosmetic error — it moves the mouse,
closes an app, or runs a command on someone's real machine.

WHY NOT JUST DELETE THE ROUTER
------------------------------
Deleting it would fix the misroutes but break three things that matter:

  * latency  — every "open notepad" would become a cloud round-trip
  * offline  — with no internet the assistant could do nothing at all
  * cost     — trivial commands would consume tokens forever

Production assistants do not solve this by deleting anything. Anthropic's own
guidance is to "make the model fit the tools" and to prioritise direct tool
access over guessing; the reflex tier survives in those systems as a cache of
known-good routes, not as a parser.

WHAT THIS DOES
--------------
Keeps the reflex tier but demotes it from authority to cache. A regex match is
now a *proposal*. It executes immediately only when the usage-learning loop has
evidence that this exact phrase previously worked. Otherwise the router returns
"no match" and the cloud model — which sees all 57 tool descriptions and
understands natural language — chooses the tool.

Cost of being wrong:
    unproven + reflex guess  -> one cloud round-trip
    proven   + wrong reflex -> nothing new; it already worked before

The learning loop does the promotion. core/action_loader.py records the real
outcome of every execution, so a phrase becomes trusted only after it has
actually succeeded several times, and a phrase the user corrects stops being
trusted automatically.
"""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional, Tuple

# Minimum observations before a reflex match is acted on.
MIN_EVIDENCE = 2

# Refusals we should never let a stale reflex override.
# A reflex must not be able to run these, even if a phrase was once promoted:
# the surrounding context has changed since it was learned.
_NEVER_TRUST_TOOLS = {
    "run_command", "devops_sentinel", "computer_settings", "file_controller",
    "shutdown_jarvis", "process_manager", "browser_control", "send_message",
    "macro", "desktop_control", "agent_mode", "subagent_swarm", "dev_agent",
}

_state: Dict[str, Any] = {
    # When False, every reflex match executes immediately. This is the legacy
    # behaviour, kept as an escape hatch and used by tests that assert the raw
    # regex cascade still works.
    "enabled": True,
    # Per-tool override: "always" trusts a tool regardless of evidence.
    "trust": {},
}
_lock = threading.Lock()


def is_enabled() -> bool:
    return bool(_state.get("enabled", True))


def apply_config() -> None:
    """Sync the gate with config/api_keys.json.

    The user-facing switch is `reflex_learning_enabled`. It is read on every
    call so toggling it in settings takes effect immediately, and it defaults to
    True so an existing install gets the safe behaviour without a migration.
    """
    try:
        from memory.config_manager import get_reflex_learning_enabled
        set_enabled(get_reflex_learning_enabled())
    except Exception:
        pass


def set_enabled(enabled: bool) -> None:
    with _lock:
        _state["enabled"] = bool(enabled)


def trust_tool(tool: str, mode: str = "always") -> None:
    """Pin a tool's reflex route. mode: 'always' | 'learn'."""
    with _lock:
        _state["trust"][str(tool)] = str(mode)


def untrust_tool(tool: str) -> None:
    with _lock:
        _state["trust"].pop(str(tool), None)


def _tool_mode(tool: str) -> str:
    return str(_state["trust"].get(str(tool), "learn"))


def _evidence_for(phrase: str) -> Tuple[int, int, int]:
    """(hits, successes, failures) for a phrase, or zeros if unknown."""
    try:
        from core import learning_loop as ll
        row = ll.get_pattern(phrase)
    except Exception:
        return (0, 0, 0)
    if not row:
        return (0, 0, 0)
    return (int(row.get("hits") or 0),
            int(row.get("successes") or 0),
            int(row.get("failures") or 0))


def is_trusted(phrase: str, tool: str) -> bool:
    """May this reflex match execute without asking the model?

    Evidence comes ONLY from real executions recorded by ActionRegistry. A
    regex match is not evidence — it is the thing being tested. Trust requires
    a clean record: no failures, no user corrections, not suppressed, and at
    least MIN_EVIDENCE successful runs.

    The one exception is an explicit promotion, which is the user's own
    decision and outranks everything the loop inferred.
    """
    if not is_enabled():
        return True
    if _tool_mode(tool) == "always":
        return True

    try:
        from core import learning_loop as ll
    except Exception:
        # Learning loop unavailable -> keep the reflex working. Routing every
        # command to the cloud because a local DB is broken would make the
        # assistant unusable, and that is worse than the original problem.
        return True

    try:
        row = ll.get_pattern(phrase)
    except Exception:
        return True

    if not row:
        return False

    # An explicit promotion is a deliberate user decision.
    if int(row.get("promoted") or 0):
        return True

    # A recorded failure anywhere in the history disqualifies the phrase.
    # Using should_auto_execute alone would let a long clean run hide a recent
    # failure, since it only looks at the aggregate success rate.
    hits       = int(row.get("hits") or 0)
    successes  = int(row.get("successes") or 0)
    failures   = int(row.get("failures") or 0)
    corrections = int(row.get("corrections") or 0)

    if corrections > 0:
        return False
    if failures > 0:
        return False
    if hits < MIN_EVIDENCE:
        return False
    return successes >= hits


def gate(phrase: str, tool: str) -> Tuple[bool, str]:
    """Return (execute_now, reason) for a proposed reflex route."""
    if not is_enabled():
        return (True, "gate disabled (legacy mode)")
    if _tool_mode(tool) == "always":
        return (True, f"tool '{tool}' pinned to always")
    if tool in _NEVER_TRUST_TOOLS:
        return (False, f"'{tool}' always defers to the model")
    apply_config()
    if not is_enabled():
        return (True, "gate disabled by config")
    if is_trusted(phrase, tool):
        return (True, "phrase proven by past use")
    hits, successes, failures = _evidence_for(phrase)
    return (False,
            f"unproven ({successes}/{hits} ok)" if hits else "no evidence yet")


def describe(phrase: str, tool: str) -> str:
    """Human-readable gate state, for the learning_ctl status output."""
    ok, reason = gate(phrase, tool)
    verdict = "AUTO-EXECUTE" if ok else "ask the model"
    return f"{verdict}  ({reason})"


def snapshot() -> Dict[str, Any]:
    return {
        "enabled": is_enabled(),
        "pinned_tools": dict(_state.get("trust", {})),
        "never_trust": sorted(_NEVER_TRUST_TOOLS),
        "min_evidence": MIN_EVIDENCE,
    }