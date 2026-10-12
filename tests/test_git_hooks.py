"""
tests/test_git_hooks.py â€” Tests for the git hook checks and installer.

The README advertised pre-commit/pre-push hooks that did not exist. These pin
the behaviour so the claim stays true: if someone weakens the credential
patterns or breaks the installer, this fails.

Two things are deliberately tested at the function level rather than by
actually running a commit:

  * scan_secrets / syntax_errors are pure and cheap â€” a real commit would only
    prove the same things more slowly.
  * install/uninstall is exercised against a temporary .git directory, so the
    developer's real hooks are never touched by the test suite.
"""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from scripts.git_hooks.checks import (  # noqa: E402
    Finding,
    check_syntax,
    iter_python_files,
    scan_secrets,
    syntax_errors,
)
from scripts import install_git_hooks as hooks  # noqa: E402


# â”€â”€ credential scanning â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.parametrize("text,rule", [
    ("key = 'AIzaSyD-1234567890abcdefghijklmnopqrstu'", "Google API key"),  # scanner-self-exempt
    ("OPENAI_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz012345", "OpenAI key"),  # scanner-self-exempt
    ("token: sk-ant-api03-abcdefghijklmnopqrstuvwxyz", "Anthropic key"),  # scanner-self-exempt
    ("GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123", "GitHub token"),  # scanner-self-exempt
    ("aws_key = 'AKIAQWERTYUIOPASDFGH'", "AWS access key id"),  # scanner-self-exempt
    ("slack = 'xoxb-1234567890-abcdefghijkl'", "Slack token"),  # scanner-self-exempt
    ("hf = 'hf_abcdefghijklmnopqrstuvwxyz'", "Hugging Face token"),  # scanner-self-exempt
    ("-----BEGIN RSA PRIVATE KEY-----", "Private key block"),  # scanner-self-exempt
    ("auth = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVP'", "JWT"),  # scanner-self-exempt
])
def test_real_shaped_credentials_are_caught(text, rule):
    found = scan_secrets(text, "cfg.py")
    assert found, f"expected a finding for {rule}"
    assert found[0].rule == rule


def test_anthropic_key_is_not_misreported_as_openai():
    """sk-ant- also satisfies the generic sk- pattern.

    Both patterns match, so rule order decides. Anthropic first, or every
    Anthropic key gets reported under the wrong provider name.
    """
    found = scan_secrets("k='sk-ant-api03-abcdefghijklmnopqrstuvwxyz'", "c.py")  # scanner-self-exempt
    assert [f.rule for f in found] == ["Anthropic key"]


def test_finding_carries_a_usable_line_number():
    found = scan_secrets("import os\nimport sys\nKEY='AIzaSyD-1234567890abcdefghijklmnopqrstu'\n",  # scanner-self-exempt
                         "cfg.py")
    assert len(found) == 1
    assert found[0].line_no == 3


def test_excerpt_is_redacted_not_the_full_secret():
    """A real secret must not be printed in full to a terminal or a CI log.

    The hook blocks the commit either way, but echoing the value would copy it
    into shell history and any log that captured the output.
    """
    secret = "AIzaSyD-1234567890abcdefghijklmnopqrstu"  # scanner-self-exempt
    found = scan_secrets(f"KEY = '{secret}'", "cfg.py")
    assert found
    assert secret not in found[0].excerpt
    assert "..." in found[0].excerpt


@pytest.mark.parametrize("line", [
    'KEY = "AIzaSyD-1234567890abcdefghijklmnopqrstu"   # EXAMPLE',  # scanner-self-exempt
    'KEY = "AIzaSyD-1234567890abcdefghijklmnopqrstu"   # FAKE for tests',  # scanner-self-exempt
    'KEY = "AIzaSyD-1234567890abcdefghijklmnopqrstu"   # PLACEHOLDER',  # scanner-self-exempt
    'KEY = "AIzaSyD-1234567890abcdefghijklmnopqrstu"   # REDACTED',  # scanner-self-exempt
    "KEY = os.environ['GOOGLE_KEY']",
    "KEY = os.getenv('GOOGLE_KEY')",
])
def test_marked_fixtures_and_env_reads_are_not_flagged(line):
    """Without this the scanner fires on its own rule definitions and on every
    example config, and people disable the hook."""
    assert scan_secrets(line, "cfg.py") == []


def test_a_marker_inside_the_value_does_not_launder_the_key():
    """Markers only count in a comment.

    Checking them anywhere would mean `KEY = "<real key>EXAMPLE"` passes the
    scan, which defeats the point of having one.
    """
    assert scan_secrets('KEY = "AIzaSyD-1234567890abcdefghijklmnopqrstuEXAMPLE"',  # scanner-self-exempt
                        "cfg.py")


def test_aws_documentation_key_is_not_flagged():
    """AKIAIOSFODNN7EXAMPLE is printed in AWS's own docs and appears in real
    code. It is allowlisted by exact value, not by a substring rule."""
    assert scan_secrets("aws = 'AKIAIOSFODNN7EXAMPLE'", "cfg.py") == []


def test_other_aws_shaped_keys_are_still_caught():
    """The doc-value allowlist must not become a general AWS exemption."""
    assert scan_secrets("aws = 'AKIAQWERTYUIOPASDFGH'", "cfg.py")  # scanner-self-exempt


def test_ordinary_code_is_clean():
    src = (
        "import json\n"
        "def load(path):\n"
        "    with open(path, encoding='utf-8') as fh:\n"
        "        return json.load(fh)\n"
        "password = 'hunter2'\n"          # not a recognised credential shape
    )
    assert scan_secrets(src, "m.py") == []


def test_one_finding_per_line():
    text = ("A='AIzaSyD-1234567890abcdefghijklmnopqrstu' "  # scanner-self-exempt
            "B='AKIAQWERTYUIOPASDFGH'")  # scanner-self-exempt
    assert len(scan_secrets(text, "m.py")) == 1


def test_scanning_empty_input_is_safe():
    assert scan_secrets("", "m.py") == []
    assert scan_secrets("\n\n\n", "m.py") == []


# ── the self-exemption marker ───────────────────────────────────────────────

def test_self_exempt_marker_skips_the_line():
    line = "K='AIzaSyD-1234567890abcdefghijklmnopqrstu'  # scanner-self-exempt"
    assert scan_secrets(line, "m.py") == []


def test_self_exempt_marker_does_not_exempt_the_rest_of_the_file():
    """The whole point of a line marker instead of a filename exemption.

    If marking one line silenced the file, the marker would be a backdoor.

    The control literal is assembled from two halves so this file does not
    itself contain a bare credential shape — which is what lets
    test_the_hook_does_not_flag_its_own_test_suite hold. The scanner still
    sees the joined string at runtime, which is the only place it matters.
    """
    marked = "K='AIzaSyD-1234567890abcdefghijklmnopqrstu'  # scanner-self-exempt"
    half = "AIzaSyD-0987654321" + "zyxwvutsrqponmlkjihgf"
    found = scan_secrets(marked + "\n" + f"REAL='{half}'\n", "m.py")
    assert len(found) == 1
    assert found[0].line_no == 2


def test_the_hook_does_not_flag_its_own_test_suite():
    """The end-to-end reason the marker exists.

    Without it the hook blocks the scanner's own tests on every commit, and
    the first thing a developer does about that is disable the hook.
    """
    src = (_ROOT / "tests" / "test_git_hooks.py").read_text(encoding="utf-8-sig")
    assert scan_secrets(src, "test_git_hooks.py") == []


def test_finding_is_immutable():
    """Frozen so a caller cannot mutate a shared finding by accident."""
    f = Finding("p", 1, "r", "x")
    with pytest.raises(Exception):
        f.line_no = 2          # type: ignore[misc]


# â”€â”€ syntax checking â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_valid_python_has_no_error():
    assert syntax_errors("def f():\n    return 1\n", "m.py") is None


def test_syntax_error_is_reported_with_a_line():
    err = syntax_errors("def f(:\n    pass\n", "m.py")
    assert err is not None
    assert "line" in err


def test_syntax_error_is_reported_for_indentation():
    err = syntax_errors("def f():\nreturn 1\n", "m.py")
    assert err is not None


def test_check_syntax_over_files(tmp_path):
    good = tmp_path / "good.py"
    good.write_text("x = 1\n", encoding="utf-8")
    bad = tmp_path / "bad.py"
    bad.write_text("def f(:\n", encoding="utf-8")

    problems = check_syntax([good, bad], tmp_path)
    assert len(problems) == 1
    assert "bad.py" in problems[0]


def test_check_syntax_reports_unreadable_file(tmp_path):
    """A file that vanishes between listing and reading must be reported, not
    raise â€” the hook has to finish and print a verdict either way."""
    missing = tmp_path / "gone.py"
    problems = check_syntax([missing], tmp_path)
    assert problems and "gone.py" in problems[0]


def test_iter_python_files_skips_noise_dirs(tmp_path):
    for d in (".venv", "__pycache__", "node_modules", "build"):
        (tmp_path / d).mkdir()
        (tmp_path / d / "junk.py").write_text("syntax ((( error\n", encoding="utf-8")
    (tmp_path / "real.py").write_text("ok = 1\n", encoding="utf-8")

    found = [p.name for p in iter_python_files(tmp_path)]
    assert "real.py" in found
    assert "junk.py" not in found


def test_every_python_file_in_this_repo_parses():
    """The same whole-tree check the pre-push hook makes.

    Guards against committing a file that cannot be imported.
    """
    problems = check_syntax(iter_python_files(_ROOT), _ROOT)
    assert not problems, "\n".join(problems[:10])


# â”€â”€ installer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    return tmp_path


def test_install_writes_both_hooks(tmp_path):
    root = _make_repo(tmp_path)
    hooks.install(root)
    for name in ("pre-commit", "pre-push"):
        p = root / ".git" / "hooks" / name
        assert p.exists(), f"{name} was not installed"
        assert hooks._MARK_BEGIN in p.read_text(encoding="utf-8")
        assert (root / ".git" / "hooks" / f"{name}.bat").exists()


@pytest.mark.skipif(os.name == "nt",
                    reason="Windows has no executable bit; git for Windows runs "
                           "hooks through sh regardless")
def test_installed_hook_is_executable(tmp_path):
    """Without the exec bit the hook silently never runs on POSIX."""
    root = _make_repo(tmp_path)
    hooks.install(root)
    p = root / ".git" / "hooks" / "pre-commit"
    assert p.stat().st_mode & stat.S_IXUSR


def test_installed_hook_calls_checks_py(tmp_path):
    """The hook must delegate to checks.py rather than duplicate the logic,
    otherwise the two drift and the tests stop meaning anything."""
    root = _make_repo(tmp_path)
    hooks.install(root)
    text = (root / ".git" / "hooks" / "pre-commit").read_text(encoding="utf-8")
    assert "checks.py" in text
    assert "pre-commit" in text


def test_pre_push_hook_runs_the_tests(tmp_path):
    root = _make_repo(tmp_path)
    hooks.install(root)
    text = (root / ".git" / "hooks" / "pre-push").read_text(encoding="utf-8")
    assert "pre-push" in text


def test_install_backs_up_an_existing_hook(tmp_path):
    """Clobbering someone's own pre-commit hook would be a nasty surprise."""
    root = _make_repo(tmp_path)
    existing = root / ".git" / "hooks" / "pre-commit"
    existing.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")

    hooks.install(root)
    backups = list((root / ".git" / "hooks").glob("pre-commit.bak-*"))
    assert len(backups) == 1
    assert "mine" in backups[0].read_text(encoding="utf-8")


def test_uninstall_removes_only_our_block(tmp_path):
    """A hook that had other content before ours must keep that content."""
    root = _make_repo(tmp_path)
    p = root / ".git" / "hooks" / "pre-commit"
    p.write_text(
        "#!/bin/sh\n# my own check\n"
        + hooks._SH_PRE_COMMIT
        + "echo after\n",
        encoding="utf-8",
    )
    hooks.uninstall(root)
    text = p.read_text(encoding="utf-8")
    assert hooks._MARK_BEGIN not in text
    assert "my own check" in text
    assert "echo after" in text


def test_uninstall_deletes_the_file_when_it_was_only_ours(tmp_path):
    root = _make_repo(tmp_path)
    hooks.install(root)
    hooks.uninstall(root)
    assert not (root / ".git" / "hooks" / "pre-commit").exists()


def test_uninstall_removes_the_bat_files(tmp_path):
    root = _make_repo(tmp_path)
    hooks.install(root)
    hooks.uninstall(root)
    assert not (root / ".git" / "hooks" / "pre-commit.bat").exists()


def test_install_is_idempotent(tmp_path):
    """Running it twice must not stack two copies of the block."""
    root = _make_repo(tmp_path)
    hooks.install(root)
    hooks.install(root)
    text = (root / ".git" / "hooks" / "pre-commit").read_text(encoding="utf-8")
    assert text.count(hooks._MARK_BEGIN) == 1


def test_check_reports_missing_hooks(tmp_path):
    root = _make_repo(tmp_path)
    assert hooks.check(root) == 1          # nothing installed yet
    hooks.install(root)
    assert hooks.check(root) == 0


def test_dry_run_writes_nothing(tmp_path):
    root = _make_repo(tmp_path)
    hooks.install(root, dry_run=True)
    assert not (root / ".git" / "hooks" / "pre-commit").exists()


def test_hooks_dir_respects_core_hookspath(tmp_path, monkeypatch):
    """A developer with core.hooksPath set expects hooks to land there."""
    root = _make_repo(tmp_path)
    custom = tmp_path / "myhooks"
    custom.mkdir()
    monkeypatch.setattr(hooks.subprocess if hasattr(hooks, "subprocess") else
                        __import__("subprocess"), "run", _fake_git_run(custom))
    assert hooks._hooks_dir(root) == custom


def _fake_git_run(target: Path):
    class _R:
        returncode = 0
        stdout = str(target) + "\n"
        stderr = ""
    return lambda *a, **k: _R()


# â”€â”€ the real thing works end to end â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.slow
def test_check_passes_on_a_clean_tree():
    """The actual check, run against this repository right now.

    Deliberately skip_tests: running the suite inside the suite would recurse.

    Marked slow because the dominant cost is not the syntax scan - about 3s for
    the whole tree - but the critical-import probe, which imports main.py and
    with it effectively the whole application. That probe is genuinely worth
    keeping: it is what catches a module that parses but cannot be imported.
    It just does not belong in every default run.
    """
    from scripts.git_hooks.checks import run_pre_push
    assert run_pre_push(_ROOT, quiet=True, skip_tests=True) == 0


# ── failure diagnostics ─────────────────────────────────────────────────────

class _FakeResult:
    def __init__(self, returncode=1, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_failure_lines_reads_stderr_when_stdout_is_empty():
    """The bug this function exists to prevent.

    The hook blocked a real push printing a bare "?" because pytest had exited
    with a usage error on stderr. A blocking check that cannot say why is
    indistinguishable from a broken one, and gets disabled.
    """
    from scripts.git_hooks.checks import _failure_lines
    r = _FakeResult(4, stdout="", stderr="pytest: error: unrecognized arguments")
    lines = _failure_lines(r)
    assert any("unrecognized arguments" in ln for ln in lines)


def test_failure_lines_never_returns_a_bare_placeholder():
    """No output at all must still produce something informative."""
    from scripts.git_hooks.checks import _failure_lines
    lines = _failure_lines(_FakeResult(3, stdout="", stderr=""))
    assert lines == ["exit code 3, no output captured"]


def test_failure_lines_prefers_stdout_for_a_normal_test_failure():
    from scripts.git_hooks.checks import _failure_lines
    r = _FakeResult(1, stdout="FAILED tests/x.py::test_y\n1 failed", stderr="")
    assert "1 failed" in " ".join(_failure_lines(r))


def test_failure_lines_appends_a_traceback_from_stderr():
    """A crash after partial output should show both, or the cause is hidden."""
    from scripts.git_hooks.checks import _failure_lines
    r = _FakeResult(1, stdout="1 failed", stderr="Traceback (most recent call last)")
    out = " ".join(_failure_lines(r))
    assert "1 failed" in out and "Traceback" in out


def test_pre_push_does_not_pass_the_pytest_timeout_flag():
    """pytest-timeout is not a dependency here.

    Passing --timeout= without the plugin makes pytest exit 4 with a usage
    error, which the hook then reports as a test failure, blocking pushes for
    a reason unrelated to the tests.
    """
    from scripts.git_hooks import checks
    src = Path(checks.__file__).read_text(encoding="utf-8-sig")
    assert '"--timeout=' not in src
    assert "timeout=1800" in src, "the bound should be applied via subprocess"
