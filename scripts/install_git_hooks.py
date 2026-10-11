"""
scripts/install_git_hooks.py — install or remove J.A.R.V.I.S. git hooks.

    python scripts/install_git_hooks.py            # install
    python scripts/install_git_hooks.py --uninstall # remove
    python scripts/install_git_hooks.py --check    # report, change nothing

WHY A GENERATOR RATHER THAN TRACKED HOOK FILES
----------------------------------------------
.git/hooks is not tracked by git, so a hook committed to the repository would
never run for anyone who clones it. The only way this ships is as an installer
the developer runs once, which writes the hook files. That is what this does.

It writes both a POSIX shell hook and a .bat variant because the project
targets Windows first: git for Windows runs hooks through sh, but a developer
double-clicking or running the .bat explicitly should get the same result.

Existing hooks are never clobbered silently. A pre-commit hook that is already
there gets backed up to <name>.bak-<timestamp> and the fact is reported.

    pre-commit  syntax check on staged files, whole-tree parse, credential
                scan on everything staged, flake8 on CI's error classes
    pre-push    whole-tree syntax, critical import probe, fast test subset
"""
from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKS = "scripts/git_hooks/checks.py"

_MARK_BEGIN = "# >>> jarvis git hook >>>"
_MARK_END = "# <<< jarvis git hook <<<"

_SH_PRE_COMMIT = f"""#!/bin/sh
{_MARK_BEGIN}
# Installed by scripts/install_git_hooks.py - edit checks.py, not this file.
ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT" || exit 1
PY=$(command -v python3 || command -v python)
if [ -x "$ROOT/.venv/Scripts/python.exe" ]; then
  PY="$ROOT/.venv/Scripts/python.exe"
fi
"$PY" "{CHECKS}" pre-commit
rc=$?
if [ $rc -ne 0 ]; then
  echo ""
  echo "Commit blocked. Fix the problems above, or stage around with:"
  echo "  git commit --no-verify"
fi
exit $rc
{_MARK_END}
"""

_SH_PRE_PUSH = f"""#!/bin/sh
{_MARK_BEGIN}
# Installed by scripts/install_git_hooks.py - edit checks.py, not this file.
ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT" || exit 1
PY=$(command -v python3 || command -v python)
if [ -x "$ROOT/.venv/Scripts/python.exe" ]; then
  PY="$ROOT/.venv/Scripts/python.exe"
fi
"$PY" "{CHECKS}" pre-push
rc=$?
if [ $rc -ne 0 ]; then
  echo ""
  echo "Push blocked. To push anyway: git push --no-verify"
fi
exit $rc
{_MARK_END}
"""

_BAT_PRE_COMMIT = f"""@echo off
REM {_MARK_BEGIN}
REM Installed by scripts/install_git_hooks.py - edit checks.py, not this file.
cd /d "%~dp0.."
set PY=python
if exist ".venv\\Scripts\\python.exe" set PY=.venv\\Scripts\\python.exe
%PY% "{CHECKS}" pre-commit
exit /b %ERRORLEVEL%
{_MARK_END}
"""

_BAT_PRE_PUSH = f"""@echo off
REM {_MARK_BEGIN}
REM Installed by scripts/install_git_hooks.py - edit checks.py, not this file.
cd /d "%~dp0.."
set PY=python
if exist ".venv\\Scripts\\python.exe" set PY=.venv\\Scripts\\python.exe
%PY% "{CHECKS}" pre-push
exit /b %ERRORLEVEL%
{_MARK_END}
"""

HOOKS = {
    "pre-commit": {"sh": _SH_PRE_COMMIT, "bat": _BAT_PRE_COMMIT},
    "pre-push": {"sh": _SH_PRE_PUSH, "bat": _BAT_PRE_PUSH},
}


def _hooks_dir(root: Path) -> Path:
    """Prefer core.hooksPath if git is configured to use one."""
    import subprocess
    r = subprocess.run(["git", "rev-parse", "--git-path", "hooks"],
                       cwd=str(root), capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        p = Path(r.stdout.strip())
        return p if p.is_absolute() else (root / p)
    return root / ".git" / "hooks"


def _backup(path: Path) -> Path | None:
    """Preserve an existing hook rather than overwriting it."""
    if not path.exists():
        return None
    stamp = __import__("time").strftime("%Y%m%d%H%M%S")
    dest = path.with_name(f"{path.name}.bak-{stamp}")
    i = 0
    while dest.exists():
        i += 1
        dest = path.with_name(f"{path.name}.bak-{stamp}-{i}")
    dest.write_bytes(path.read_bytes())
    return dest


def _remove_jarrows(path: Path) -> bool:
    """Strip only a previously-installed J.A.R.V.I.S. block, keep anything else."""
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    if _MARK_BEGIN not in text or _MARK_END not in text:
        return False
    head, _, rest = text.partition(_MARK_BEGIN)
    _, _, tail = rest.partition(_MARK_END)
    # What survives is the text outside our markers. A file that was only ever
    # ours still has the shebang we generated above the first marker, so a
    # leftover `#!/bin/sh` must not keep an empty hook installed forever.
    kept = [ln for ln in (head + tail).splitlines()
            if ln.strip() and not ln.startswith("#!")]
    if kept:
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    else:
        path.unlink()          # the file was only ever ours
    return True


def install(root: Path | None = None, dry_run: bool = False) -> int:
    root = root or ROOT
    hd = _hooks_dir(root)
    hd.mkdir(parents=True, exist_ok=True)
    print(f"hooks directory: {hd}")

    for name, variants in HOOKS.items():
        sh_path = hd / name
        backup = None if dry_run else _backup(sh_path)
        if backup:
            print(f"  existing {name} preserved as {backup.name}")

        if not dry_run:
            sh_path.write_text(variants["sh"], encoding="utf-8", newline="\n")
            # Make it executable. On Windows this is a no-op but harmless; on a
            # WSL or macOS checkout it is the difference between running and not.
            sh_path.chmod(sh_path.stat().st_mode | stat.S_IXUSR
                          | stat.S_IXGRP | stat.S_IXOTH)
            (hd / f"{name}.bat").write_text(variants["bat"],
                                            encoding="utf-8", newline="\r\n")
        print(f"  installed {name}" + (f" (+ {name}.bat)" if not dry_run else " (dry run)"))

    if not dry_run:
        print("\nHooks installed. They check:")
        print("  pre-commit  staged syntax, whole-tree parse, credential scan, flake8")
        print("  pre-push    whole-tree syntax, critical imports, fast tests")
        print("\nBypass once with:  git commit --no-verify")
    return 0


def uninstall(root: Path | None = None) -> int:
    root = root or ROOT
    hd = _hooks_dir(root)
    removed = 0
    for name in HOOKS:
        sh_path = hd / name
        if _remove_jarrows(sh_path):
            removed += 1
            print(f"  removed J.A.R.V.I.S. block from {name}")
        bat = hd / f"{name}.bat"
        if bat.exists() and _MARK_BEGIN in bat.read_text(encoding="utf-8",
                                                         errors="replace"):
            bat.unlink()
            removed += 1
            print(f"  removed {name}.bat")
    print("nothing to do" if not removed else f"removed {removed} file(s)")
    return 0


def check(root: Path | None = None) -> int:
    root = root or ROOT
    hd = _hooks_dir(root)
    ok = True
    for name in HOOKS:
        p = hd / name
        installed = p.exists() and _MARK_BEGIN in p.read_text(
            encoding="utf-8", errors="replace")
        print(f"  {name:<12} {'installed' if installed else 'NOT INSTALLED'}")
        ok = ok and installed
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--uninstall", action="store_true", help="remove the hooks")
    ap.add_argument("--check", action="store_true", help="report status only")
    ap.add_argument("--dry-run", action="store_true", help="show what would happen")
    args = ap.parse_args()

    if args.uninstall:
        return uninstall()
    if args.check:
        return check()
    return install(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())