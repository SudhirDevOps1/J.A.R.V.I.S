"""
actions/learning_ctl.py — Voice/chat control surface for the learning loop.

The loop in core/learning_loop.py learns passively: every Tier-1 action records
its outcome. This action is how the user inspects and steers it.

Trigger phrases:
  "kya seekha" / "learning dikhao" / "kya seekha tumne"
  "stats" / "learning stats"
  "promote <phrase>" / "ye command aage se seedha chalao"
  "forget <phrase>"  / "ye bhul ja"
  "reset learning"   / "sab bhul ja"
  "corrections"      / "galtiyan dikhao"
"""
from __future__ import annotations

import time
from typing import Any, Dict

from core import learning_loop as LL


def _log(player, msg: str) -> None:
    try:
        if player and hasattr(player, "write_log"):
            player.write_log(msg)
    except Exception:
        pass
    print(msg)


def _fmt_rate(row: Dict[str, Any]) -> str:
    hits = int(row.get("hits") or 0)
    succ = int(row.get("successes") or 0)
    rate = (100.0 * succ / hits) if hits else 0.0
    flags = []
    if int(row.get("promoted") or 0):
        flags.append("⚡promoted")
    if int(row.get("corrections") or 0):
        flags.append("📌corrected")
    suffix = f" [{', '.join(flags)}]" if flags else ""
    return f"{succ}/{hits} ({rate:.0f}%){suffix}"


def learning_ctl(
    parameters: dict | None = None,
    player=None,
    session_memory=None,
    **_,
) -> str:
    params = parameters or {}
    action = str(params.get("action") or "summary").strip().lower()
    phrase = str(params.get("phrase") or params.get("command") or "").strip()

    if action in ("summary", "status", "show", "kya_seekha"):
        _log(player, "Learning loop status requested")
        return LL.summary_text()

    if action in ("stats", "numbers", "detail"):
        s = LL.stats()
        lines = [
            "🧠 Learning Loop — Detailed Stats",
            f"   Patterns learned : {s['patterns']}",
            f"   Commands observed: {s['hits']}",
            f"   Successes        : {s['successes']}",
            f"   Failures         : {s['failures']}",
            f"   Success rate     : {s['success_rate']}%",
            f"   Promoted (fast)  : {s['promoted']}",
            f"   Corrections      : {s['corrections']}",
        ]
        top = LL.top_patterns(10)
        if top:
            lines.append("   Top commands:")
            for r in top:
                lines.append(f"     • \"{r['phrase']}\" → {r['tool']}  {_fmt_rate(r)}")
        return "\n".join(lines)

    if action in ("patterns", "list", "commands"):
        top = LL.top_patterns(20)
        if not top:
            return "Abhi koi command pattern seekha nahi gaya. Thoda aur use karo."
        lines = ["🧠 Learned command patterns:"]
        for r in top:
            lines.append(f"   • \"{r['phrase']}\" → {r['tool']}  {_fmt_rate(r)}")
        return "\n".join(lines)

    if action in ("promotions", "ready"):
        ready = LL.suggest_promotions(10)
        if not ready:
            return "Abhi koi command promote hone ke liye ready nahi hai."
        lines = ["🔜 Ye commands seedha chalne ke liye ready hain (promote kar sakte ho):"]
        for r in ready:
            lines.append(f"   • \"{r['phrase']}\" → {r['tool']}  {_fmt_rate(r)}")
        return "\n".join(lines)

    if action in ("promote", "always"):
        if not phrase:
            return "Kaunsa command promote karna hai? Phrase batao."
        if LL.set_promoted(phrase, True):
            _log(player, f"Promoted: {phrase}")
            return (f"⚡ Ho gaya — ab \"{phrase}\" har baar bina puchhe seedha chalega "
                    f"(jab tak tum reset na karo).")
        return f"\"{phrase}\" pattern me abhi nahi hai. Use pehle 2-3 baar chalao."

    if action in ("unpromote", "reset_promotion"):
        if not phrase:
            return "Kaunsa command un-promote karna hai?"
        LL.set_promoted(phrase, False)
        return f"\"{phrase}\" ka promotion hata diya."

    if action in ("forget", "delete", "bhul_ja"):
        if not phrase:
            return "Kaunsa command bhulana hai?"
        if LL.forget_pattern(phrase):
            _log(player, f"Forgot pattern: {phrase}")
            return f"\"{phrase}\" ka pattern memory se mita diya."
        return f"\"{phrase}\" koi learned pattern nahi mila."

    if action in ("reset", "clear", "sab_bhul_ja"):
        LL.reset_all()
        LL.reset_promotions()
        _log(player, "Learning loop reset")
        return "🧹 Saara learning data reset kar diya. Phir se fresh seekhna shuru."

    if action in ("corrections", "galtiyan", "lessons"):
        corrs = LL.list_corrections(10)
        if not corrs:
            return "Abhi koi correction note nahi hai."
        lines = ["📌 Recent corrections / lessons:"]
        for c in corrs:
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(c["ts"]))
            tool = c.get("tool") or ""
            target = f" → {tool}" if tool else ""
            lines.append(f"   • \"{c['phrase']}\"{target}   [{when}]")
            if c.get("rule"):
                lines.append(f"       rule: {c['rule'][:120]}")
        return "\n".join(lines)

    return (f"Unknown action '{action}'. Use: summary, stats, patterns, "
            "promotions, promote, unpromote, forget, reset, corrections.")


TOOL = {
    "name": "learning_ctl",
    "description": (
        "Inspect and steer JARVIS's usage-learning loop: what it has learned, "
        "command success rates, which commands are ready to auto-run, promote "
        "or forget a pattern, reset learning, or review corrections. "
        "Trigger on 'kya seekha', 'learning dikhao', 'stats', 'promotions', "
        "'sab bhul ja', 'corrections'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "summary | stats | patterns | promotions | promote | "
                    "unpromote | forget | reset | corrections"
                ),
                "enum": ["summary", "stats", "patterns", "promotions", "promote",
                         "unpromote", "forget", "reset", "corrections"],
            },
            "phrase": {
                "type": "STRING",
                "description": "The command phrase for promote / unpromote / forget.",
            },
        },
        "required": ["action"],
    },
    "handler": learning_ctl,
}