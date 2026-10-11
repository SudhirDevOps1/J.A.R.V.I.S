#!/usr/bin/env python3
"""
Release Readiness & Milestone Verification Engine for J.A.R.V.I.S.
Enforces the 20 Conventional Commits (feat/fix/perf) threshold rule
before permitting automated release tags or changelog publishing.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = Path(__file__).resolve().parent.parent
_THRESHOLD = 20  # Minimum qualifying commits required for milestone release


def _run_cmd(cmd: List[str]) -> str:
    """Run git command safely and return output."""
    try:
        res = subprocess.run(
            cmd, cwd=str(_ROOT), capture_output=True, text=True, check=True
        )
        return res.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def get_latest_tag() -> str:
    """Return the most recent git tag or empty string if none exists."""
    return _run_cmd(["git", "describe", "--tags", "--abbrev=0"])


def get_commits_since(tag: str = "") -> List[str]:
    """Get commit messages since specified tag or recent commits."""
    if tag:
        raw = _run_cmd(
            ["git", "log", f"{tag}..HEAD", "--oneline", "--no-merges"]
        )
    else:
        raw = _run_cmd(
            ["git", "log", "--oneline", "--no-merges", "-n", "100"]
        )

    if not raw:
        return []
    return [line.strip() for line in raw.splitlines() if line.strip()]


def categorize_commits(
    commits: List[str]
) -> Tuple[Dict[str, List[str]], int]:
    """Categorize commit messages into Conventional Commits groups."""
    categories: Dict[str, List[str]] = {
        "Features": [],
        "Bug Fixes": [],
        "Performance": [],
        "Refactoring & Core": [],
        "Other": [],
    }
    qualifying_count = 0

    p_feat = re.compile(
        r"^[0-9a-f]+\s+feat(\([^\)]+\))?:\s*(.+)$", re.IGNORECASE
    )
    p_fix = re.compile(
        r"^[0-9a-f]+\s+fix(\([^\)]+\))?:\s*(.+)$", re.IGNORECASE
    )
    p_perf = re.compile(
        r"^[0-9a-f]+\s+perf(\([^\)]+\))?:\s*(.+)$", re.IGNORECASE
    )
    p_ref = re.compile(
        r"^[0-9a-f]+\s+(refactor|chore|test|docs)(\([^\)]+\))?:\s*(.+)$",
        re.IGNORECASE
    )

    for c in commits:
        m_feat = p_feat.match(c)
        if m_feat:
            categories["Features"].append(m_feat.group(2))
            qualifying_count += 1
            continue

        m_fix = p_fix.match(c)
        if m_fix:
            categories["Bug Fixes"].append(m_fix.group(2))
            qualifying_count += 1
            continue

        m_perf = p_perf.match(c)
        if m_perf:
            categories["Performance"].append(m_perf.group(2))
            qualifying_count += 1
            continue

        m_refactor = p_ref.match(c)
        if m_refactor:
            categories["Refactoring & Core"].append(m_refactor.group(3))
            continue

        parts = c.split(" ", 1)
        msg = parts[1] if len(parts) > 1 else c
        categories["Other"].append(msg)

    return categories, qualifying_count


def generate_changelog_snippet(
    categories: Dict[str, List[str]], version: str
) -> str:
    """Generate markdown changelog block for a release."""
    lines = [f"## [{version}] - Milestone Release", ""]
    for cat, items in categories.items():
        if items:
            lines.append(f"### {cat}")
            for item in items:
                lines.append(f"- {item}")
            lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="J.A.R.V.I.S. Release Readiness Evaluator"
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Display commit progress towards release threshold"
    )
    parser.add_argument(
        "--bump", action="store_true",
        help="Evaluate if repository is eligible for a milestone bump"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Bypass the 20-commit threshold"
    )
    parser.add_argument(
        "--threshold", type=int, default=_THRESHOLD,
        help=f"Commit threshold (default: {_THRESHOLD})"
    )
    args = parser.parse_args()

    latest_tag = get_latest_tag()
    commits = get_commits_since(latest_tag)
    categories, qualifying = categorize_commits(commits)
    threshold = args.threshold

    print("=" * 65)
    print("      J.A.R.V.I.S. Release Milestone & Conventional Commit Engine")
    print("=" * 65)
    print(f"[*] Baseline Tag        : {latest_tag or 'Development baseline'}")
    print(f"[*] Total Commits Analyzed : {len(commits)}")
    print(f"[*] Qualifying (feat/fix) : {qualifying} / {threshold} required")
    print("-" * 65)
    print(f"  * Features (feat)     : {len(categories['Features'])}")
    print(f"  * Bug Fixes (fix)     : {len(categories['Bug Fixes'])}")
    print(f"  * Performance (perf)  : {len(categories['Performance'])}")
    print(f"  * Refactor & Chores   : {len(categories['Refactoring & Core'])}")
    print("-" * 65)

    is_ready = qualifying >= threshold or args.force

    if not is_ready:
        remaining = threshold - qualifying
        print("[STATUS] In Development (Milestone not reached).")
        print(f"[INFO]   Aapko {remaining} aur meaningful commits chahiye")
        print("         milestone release ke liye (ya use karein --force).")
        print("=" * 65)
        sys.exit(0 if args.check else 1)

    print(
        f"[STATUS] RELEASE READY! Milestone threshold satisfied "
        f"({qualifying} >= {threshold})."
    )
    next_ver = "v0.1.0" if not latest_tag else f"{latest_tag}-next"
    print(f"[INFO] Proposed Next Milestone: {next_ver}")
    print("=" * 65)
    print()
    print("Previewing Generated Milestone Notes:")
    print(generate_changelog_snippet(categories, next_ver))
    sys.exit(0)


if __name__ == "__main__":
    main()
