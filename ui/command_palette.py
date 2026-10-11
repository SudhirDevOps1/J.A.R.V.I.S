"""
ui/command_palette.py — Ctrl+K fuzzy command palette.

THE POINT
---------
Every capability in J.A.R.V.I.S used to be reachable only by finding the right
button with the mouse. With 57 tools and 10 plugins that is not possible in
practice, which is why the assistant had a discoverability problem: the user
cannot use what they cannot find.

The palette puts everything in one searchable list: every tool, every action,
every plugin, plus UI commands. Typing filters by fuzzy subsequence match, so
"ntp" finds "notepad", and Enter runs it.

It builds its list from the live registries rather than a hand-maintained table,
so a tool added to actions/ appears automatically with no extra work.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class PaletteEntry:
    label: str
    hint: str = ""
    category: str = "Action"
    run: Optional[Callable[[], None]] = None
    # Lower is better; used for ordering so UI commands sit above raw tools.
    weight: int = 50

    def display(self) -> str:
        return f"{self.label}  —  {self.hint}" if self.hint else self.label


# ── fuzzy matching ──────────────────────────────────────────────────────────

def fuzzy_score(needle: str, haystack: str) -> float:
    """Score `needle` against `haystack` as a subsequence.

    Returns 0.0 for no match, higher is better. Rewards, in order:
      * exact match
      * prefix match
      * word-boundary match ("ntp" -> "note**p**ad" style hits)
      * contiguous runs of characters
      * short haystacks (less noise relative to the match)

    A subsequence match alone scores poorly, because almost any short query is a
    subsequence of almost any string. That is why the bonuses matter: without
    them "open" would match "o...p...e...n" anywhere in a long description.
    """
    n = (needle or "").strip().lower()
    h = (haystack or "").strip().lower()
    if not n or not h:
        return 0.0
    if n == h:
        return 1.0

    pos = 0
    matched_positions: List[int] = []
    for ch in n:
        idx = h.find(ch, pos)
        if idx < 0:
            return 0.0
        matched_positions.append(idx)
        pos = idx + 1

    # Base: how much of the haystack the query consumes.
    score = 0.30 + 0.40 * (len(n) / max(len(h), 1))

    # Contiguity bonus — every adjacent pair earns credit.
    runs = sum(1 for a, b in zip(matched_positions, matched_positions[1:]) if b == a + 1)
    score += 0.18 * (runs / max(len(matched_positions) - 1, 1))

    # Word-boundary bonus.
    if matched_positions and matched_positions[0] == 0:
        score += 0.20
    for i in matched_positions:
        if i > 0 and (h[i - 1] in " _-./"):
            score += 0.05

    return min(score, 1.0)


def filter_entries(entries: List[PaletteEntry], query: str,
                   limit: int = 40) -> List[PaletteEntry]:
    """Filter and rank. An empty query returns the entries in declared order,
    which is the intended discovery behaviour: opening the palette shows you
    what is available."""
    q = (query or "").strip()
    if not q:
        return entries[:limit]
    scored: List[Tuple[float, PaletteEntry]] = []
    for e in entries:
        # Label is what the user is typing; hint is secondary context.
        s_label = fuzzy_score(q, e.label)
        s_hint = fuzzy_score(q, e.hint) * 0.45 if e.hint else 0.0
        s = max(s_label, s_hint)
        if s <= 0:
            continue
        scored.append((s + e.weight / 1000.0, e))
    scored.sort(key=lambda x: -x[0])
    return [e for _s, e in scored[:limit]]


# ── entry building ──────────────────────────────────────────────────────────

def build_entries(
    action_registry=None,
    plugin_registry=None,
    ui_commands: Optional[Dict[str, Callable[[], None]]] = None,
) -> List[PaletteEntry]:
    """Assemble the palette from live registries plus UI commands.

    Tools are labelled "tool: <name>" so the model-facing name is visible and
    searchable, and each carries a short hint taken from the tool's own
    description so the palette doubles as documentation.
    """
    entries: List[PaletteEntry] = []

    for name, fn in (ui_commands or {}).items():
        entries.append(PaletteEntry(
            label=name,
            hint="",
            category="UI",
            run=fn,
            weight=0,  # UI commands surface first
        ))

    if action_registry is not None:
        # Wrapped: a registry that raises must not take the whole palette down.
        # The palette is a UI affordance; it is never worth crashing it because
        # discovery data is unavailable. UI commands still work without it.
        try:
            names = sorted(action_registry.names())
        except Exception as e:
            print(f"[CommandPalette] action listing unavailable: {e}")
            names = []
        for name in names:
            try:
                rec = getattr(action_registry, "_actions", {}).get(name)
                hint = (getattr(rec, "description", "") or "")[:110]
            except Exception:
                rec, hint = None, ""
            entries.append(PaletteEntry(
                label=f"tool: {name}",
                hint=hint,
                category="Tool",
                run=None,          # tool execution still needs the model
                weight=20,
            ))

    if plugin_registry is not None:
        try:
            # PluginRegistry keeps valid and invalid records together in
            # _all_records and marks validity per record; only valid ones are
            # worth offering.
            for rec in plugin_registry._all_records:
                if not getattr(rec, "valid", True):
                    continue
                name = getattr(rec, "name", "")
                if not name:
                    continue
                hint = (getattr(rec, "description", "") or "")[:110]
                entries.append(PaletteEntry(
                    label=f"plugin: {name}",
                    hint=hint,
                    category="Plugin",
                    run=None,
                    weight=30,
                ))
        except Exception as e:
            print(f"[CommandPalette] plugin listing unavailable: {e}")

    return entries


# ── selection → action ──────────────────────────────────────────────────────

def selection_to_text(entry: Optional[PaletteEntry]) -> str:
    """Turn a chosen entry into text to run through the assistant.

    A UI command with a handler runs directly; a tool becomes a natural-language
    request that the model routes to the right tool. Selecting a tool in the
    palette should not require the user to also know the syntax.
    """
    if entry is None:
        return ""
    if entry.category == "Tool":
        name = entry.label.split("tool:", 1)[-1].strip()
        return f"run the {name} tool"
    if entry.category == "Plugin":
        name = entry.label.split("plugin:", 1)[-1].strip()
        return f"show info about the {name} plugin"
    return ""