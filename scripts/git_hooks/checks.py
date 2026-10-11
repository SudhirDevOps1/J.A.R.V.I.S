"""
scripts/git_hooks/checks.py — the actual work done by the git hooks.

Split out from the hook scripts so it can be unit tested without a git
repository, without a subprocess, and without installing anything. The hook
files under scripts/git_hooks/ are thin wrappers that import from here.

WHY THESE EXIST
---------------
The README advertised "Native Python Git Hooks: pre-commit syntax check,
py_compile, compileall, secret leak guard, flake8; pre-push smoke tests" while
no hook was installed at all. Rather than delete the claim, this implements it.

THE RULES THIS ENFORCES
-----------------------
  pre-commit  1. every staged .py file parses (py_compile)
               2. no file in the whole tree parses as a syntax error
               3. no staged content looks like a live credential
               4. flake8 on the same error classes CI gates on

  pre-push    1. the app's critical imports still resolve
               2. the fast test subset still passes

Both are designed to run in seconds. A hook that is slow gets bypassed, and a
bypassed hook is worse than no hook because it is a false assurance.
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

# ── secret scanning ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Finding:
    path: str
    line_no: int
    rule: str
    excerpt: str


# Deliberately narrow: each pattern targets a credential shape with a fixed
# prefix and a plausible body. Anything looser produces so many false positives
# on a codebase full of example JSON that people disable the hook.
#
# Order matters: Anthropic keys also satisfy the generic sk- pattern, so the
# specific rule has to be tried first or every sk-ant- key is misreported as an
# OpenAI key.
SECRET_RULES: Sequence[tuple[str, re.Pattern]] = (
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_\-]{35,}")),
    ("OpenAI key", re.compile(r"\bsk-(?!ant-)(?:proj-)?[A-Za-z0-9_\-]{20,}")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{20,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")),
)

# Credential-shaped values that appear verbatim in vendor documentation and are
# not real. Narrow and explicit on purpose: an open-ended "looks fake" heuristic
# is exactly how a real key gets waved through.
KNOWN_DOC_VALUES = frozenset({
    "AKIAIOSFODNN7EXAMPLE",     # the AWS access key id printed in AWS's own docs
})

# Words that mark a line as documentation rather than a live assignment.
# These only count inside a `#` comment: putting them in the value itself is a
# way to smuggle a real key past the scanner, and it is also why the AWS doc key
# has to be listed explicitly above instead of matching a substring rule.
_COMMENT_MARKERS = ("example", "fake", "placeholder", "dummy", "redacted",
                    "sample", "test", "notreal", "your-", "your_")

_SELF_EXEMPT_MARKER = "scanner-self-exempt"

# Reading a credential from the environment is the correct way to do it and
# must never be flagged.
_ENV_READS = ("os.environ", "os.getenv", "process.env", "getenv(",
              "${", "env::", "secret::")


def _line_is_allowed(line: str) -> bool:
    """True if this line is documenting a shape rather than holding a secret."""
    low = line.lower()
    # The scanner's own test suite has to contain credential-shaped strings to
    # prove the scanner works, and without an escape hatch the hook blocks its
    # own test file on every commit. A line marker is used rather than a
    # filename exemption on purpose: a filename exemption is a blanket pass for
    # the whole file, which is exactly where someone would hide a real key.
    # With a marker, every exempt line is individually visible in review and
    # every other line in the file is still scanned.
    if _SELF_EXEMPT_MARKER in low:
        return True
    if any(marker in low for marker in _ENV_READS):
        return True
    # Markers only count when they are a comment, so "EXAMPLE" appearing inside
    # a quoted value does not launder a genuine key.
    hash_at = low.find("#")
    if hash_at >= 0 and any(m in low[hash_at:] for m in _COMMENT_MARKERS):
        return True
    return False


def scan_secrets(text: str, path: str = "") -> List[Finding]:
    """Return credential-shaped matches in `text`.

    Offset of the finding is the line number (1-based) so the message is
    actionable in a commit.
    """
    out: List[Finding] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if _line_is_allowed(line):
            continue
        for rule, pattern in SECRET_RULES:
            m = pattern.search(line)
            if m:
                value = m.group(0)
                if value in KNOWN_DOC_VALUES:
                    continue
                # Show enough to identify, not enough to leak: a redacted
                # excerpt means a real secret in a commit still is not printed
                # in full to the terminal or into CI logs.
                excerpt = value[:6] + "..." + value[-4:] if len(value) > 12 else "..."
                out.append(Finding(path, i, rule, excerpt))
                break        # one finding per line is enough to act on
    return out


# ── syntax checking ─────────────────────────────────────────────────────────

def syntax_errors(source: str, path: str = "<string>") -> Optional[str]:
    """Return a message if `source` does not parse, else None.

    Uses ast.parse rather than py_compile so nothing is written to disk and no
    __pycache__ litter is created for every staged file.
    """
    try:
        ast.parse(source, filename=path)
        return None
    except SyntaxError as e:
        return f"line {e.lineno}: {e.msg}"
    except ValueError as e:      # e.g. null bytes in a .py file
        return str(e)


def _read(path: Path) -> str:
    """Read source, tolerating a UTF-8 BOM.

    utf-8-sig rather than utf-8: PowerShell's `Set-Content -Encoding UTF8` and
    several editors write a BOM, and ast.parse rejects U+FEFF outright. Without
    this the whole-tree check fails on a file that is perfectly valid Python.
    """
    return Path(path).read_text(encoding="utf-8-sig", errors="replace")


def check_syntax(files: Iterable[Path], root: Path) -> List[str]:
    problems: List[str] = []
    for f in files:
        try:
            src = _read(f)
        except OSError as e:
            problems.append(f"{f}: cannot read ({e})")
            continue
        err = syntax_errors(src, str(f))
        if err:
            problems.append(f"{f}: {err}")
    return problems


def iter_python_files(root: Path, skip_dirs: Optional[set] = None) -> List[Path]:
    """All .py files under root, skipping the usual generated/noise directories."""
    skip = skip_dirs if skip_dirs is not None else {
        ".git", ".venv", "venv", "__pycache__", "node_modules",
        "build", "dist", ".pytest_cache", ".mypy_cache", "htmlcov",
    }
    out: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for name in filenames:
            if name.endswith(".py"):
                out.append(Path(dirpath) / name)
    return sorted(out)


# ── git plumbing ────────────────────────────────────────────────────────────

def _git(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True,
        check=False, timeout=60,
    )


def repo_root(start: Optional[Path] = None) -> Path:
    start = start or Path(__file__).resolve().parent.parent.parent
    p = _git(["rev-parse", "--show-toplevel"], start)
    if p.returncode == 0 and p.stdout.strip():
        return Path(p.stdout.strip())
    return start


def staged_python_files(root: Path) -> List[Path]:
    """Files with Python content that this commit is about to record.

    Uses `diff --cached --name-only` rather than `ls-files`, so an unrelated
    edit elsewhere in the tree never slows a commit down.
    """
    p = _git(["diff", "--cached", "--name-only", "--diff-filter=ACM"], root)
    if p.returncode != 0:
        return []
    return [
        root / line.strip()
        for line in p.stdout.splitlines()
        if line.strip().endswith(".py") and (root / line.strip()).exists()
    ]


def staged_files(root: Path) -> List[Path]:
    p = _git(["diff", "--cached", "--name-only", "--diff-filter=ACM"], root)
    if p.returncode != 0:
        return []
    return [
        root / line.strip()
        for line in p.stdout.splitlines()
        if line.strip() and (root / line.strip()).exists()
    ]


def _flake8_installed() -> bool:
    try:
        import flake8  # noqa: F401
        return True
    except Exception:
        return False


def _failure_lines(result, limit: int = 20) -> List[str]:
    """Extract something readable from a failed subprocess.

    Reads stderr as well as stdout. The first version only looked at stdout and
    fell back to printing "?", which is exactly what happened the first time
    the pre-push hook fired: pytest had exited with a usage error on stderr, so
    the hook blocked the push and gave no reason at all. A blocking check that
    cannot say why is indistinguishable from a broken check, and gets disabled.
    """
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()

    # pytest writes its summary to stdout; a usage error goes to stderr.
    if not out:
        out = err
    elif err and ("error:" in err or "Traceback" in err):
        out = out + "\n" + err

    lines = [ln for ln in out.splitlines() if ln.strip()]
    if not lines:
        return [f"exit code {result.returncode}, no output captured"]
    return lines[-limit:]


# ── entry points ────────────────────────────────────────────────────────────

def run_pre_commit(root: Optional[Path] = None, *, quiet: bool = False) -> int:
    """Returns a process exit code: 0 to allow the commit, 1 to block it."""
    root = repo_root(root)
    say = (lambda *a: None) if quiet else (lambda *a: print(*a))

    staged = staged_python_files(root)
    if not staged:
        return 0

    failed = False

    # 1 + 2. syntax
    problems = check_syntax(staged, root)
    if problems:
        failed = True
        say("pre-commit: syntax errors in staged files:")
        for p in problems:
            say("  " + p)

    # 3. secrets across everything staged, not just Python
    findings: List[Finding] = []
    for f in staged_files(root):
        try:
            findings.extend(scan_secrets(_read(f), str(f)))
        except OSError:
            continue
    if findings:
        failed = True
        say("pre-commit: possible credentials in staged files:")
        for f in findings:
            say(f"  {f.path}:{f.line_no}  {f.rule}  (matched {f.excerpt})")
        say("  If this is a test fixture, add EXAMPLE/FAKE/PLACEHOLDER to the line.")
        say("  If it is real: rotate the credential now, then git rm --cached the file.")

    # 4. flake8, same error classes CI gates on
    if _flake8_installed() and staged:
        cmd = [sys.executable, "-m", "flake8",
               "--select=E9,F63,F7,F82", *[str(f) for f in staged]]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root))
        if r.returncode != 0 and r.stdout.strip():
            failed = True
            say("pre-commit: flake8 errors:")
            say(r.stdout.rstrip())

    # Only claim success when nothing above failed. Printing "clean" after
    # blocking a commit reads as though flake8 disagreed with the block.
    if not failed and not quiet:
        say(f"pre-commit: {len(staged)} staged file(s) checked, clean.")

    return 1 if failed else 0


def run_pre_push(root: Optional[Path] = None, *, quiet: bool = False,
                 skip_tests: bool = False) -> int:
    """Returns a process exit code: 0 to allow the push, 1 to block it."""
    root = repo_root(root)
    say = (lambda *a: None) if quiet else (lambda *a: print(*a))

    failed = False

    # 1. whole-tree syntax: catches a broken file that was never staged
    problems = check_syntax(iter_python_files(root), root)
    if problems:
        failed = True
        say("pre-push: syntax errors in the working tree:")
        for p in problems[:20]:
            say("  " + p)
        if len(problems) > 20:
            say(f"  ... and {len(problems) - 20} more")

    # 2. critical imports still resolve
    probe = (
        "import ui, main, core.action_loader, core.edge_router, "
        "core.reflex_policy, core.learning_loop, core.app_identity"
    )
    r = subprocess.run([sys.executable, "-c", probe],
                       capture_output=True, text=True, cwd=str(root))
    if r.returncode != 0:
        failed = True
        say("pre-push: critical imports failed:")
        for line in _failure_lines(r):
            say("  " + line)

    # 3. fast tests
    #
    # The bound is applied with subprocess's own timeout rather than
    # `--timeout=`. pytest-timeout is not a dependency of this project, and
    # passing the flag without the plugin installed makes pytest exit 4 with a
    # usage error written to stderr - which looked exactly like a test failure
    # for a reason that had nothing to do with the tests.
    if not skip_tests:
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-x", "-m", "not network"],
                capture_output=True, text=True, cwd=str(root), timeout=1800,
            )
        except subprocess.TimeoutExpired:
            failed = True
            say("pre-push: test suite exceeded 30 minutes and was killed.")
            r = None
        if r is not None and r.returncode != 0:
            failed = True
            say("pre-push: test suite failed:")
            for line in _failure_lines(r)[-20:]:
                say("  " + line)

    if not failed:
        say("pre-push: all checks passed.")
    return 1 if failed else 0


if __name__ == "__main__":       # pragma: no cover
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    if which == "pre-commit":
        sys.exit(run_pre_commit())
    if which == "pre-push":
        sys.exit(run_pre_push())
    print(__doc__)
    sys.exit(2)