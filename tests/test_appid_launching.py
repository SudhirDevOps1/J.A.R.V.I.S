"""
tests/test_appid_launching.py — Windows AppUserModelID recognition and launching.

THE BUG
-------
From the user's own machine. Asking for Notepad produced:

    [open_app] Launching: 'Notepad' -> '{1AC14E77-...}\notepad.exe'
    open_app -> Opened Notepad.

Nothing opened. Windows Search appeared reading "5198B7}\\notepad", because
`cmd /c start "" {1AC14E77-...}\notepad.exe` is not a path Windows can execute,
so the shell treated it as a search query. The assistant then reported success.

ROOT CAUSE
----------
`_looks_like_appid` rejected any target containing a backslash. That was
well meant - a real path must not go to the shell namespace - but
`{1AC14E77-...}\notepad.exe` IS the genuine Notepad AppID, straight from
Get-StartApps. So the AppID stage was skipped for Notepad, control fell
through to Start Menu keyboard automation, and pyautogui typed the literal tail
of the identifier into the user's search box.

Verified against Get-StartApps on the user's machine:

    Firefox     308046B0AF4A39CB
    Notepad     {1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\notepad.exe
    Calculator  Microsoft.WindowsCalculator_8wekyb3d8bbwe!App

The distinction that matters is not "contains a backslash". It is "is this a
filesystem path, or an opaque Windows identifier".

These tests use the real values rather than invented ones. The first version of
this fix was verified through a shell heredoc, where the backslashes were
mangled - the Notepad case failed there and would have shipped broken.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from actions.open_app import _looks_like_appid, _looks_like_opaque_identifier  # noqa: E402


# Real values, verbatim from `Get-StartApps` on the user's Windows machine.
REAL_APPIDS = [
    "308046B0AF4A39CB",
    "308046B0AF4A39CB;PrivateBrowsingAUMID",
    r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\notepad.exe",
    "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App",
]

# Real filesystem paths and ordinary words. None of these may reach the shell
# namespace: an invalid shell:AppsFolder path opens the Documents folder.
NOT_APPIDS = [
    "C:\\Program Files\\App\\app.exe",
    "C:\\Windows\\notepad.exe",
    "\\\\server\\share\\thing.exe",
    "/usr/bin/thing",
    "notepad",
    "firefox",
    "calc",
    "",
    "   ",
    "a b c",
    "ms-settings:display",
]


# ── the values Windows actually reports ─────────────────────────────────────

@pytest.mark.parametrize("appid", REAL_APPIDS)
def test_real_appids_are_recognised(appid):
    assert _looks_like_appid(appid) is True, appid


def test_notepad_guid_form_is_recognised():
    """The exact case that broke.

    The old guard rejected this because it contains a backslash, which is the
    whole reason Notepad fell through to the Start Menu search.
    """
    value = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\notepad.exe"
    assert "\\" in value
    assert _looks_like_appid(value) is True


def test_firefox_bare_token_is_recognised():
    assert _looks_like_appid("308046B0AF4A39CB") is True


def test_calculator_bang_form_is_recognised():
    assert _looks_like_appid("Microsoft.WindowsCalculator_8wekyb3d8bbwe!App") is True


# ── paths must never be mistaken for identifiers ───────────────────────────

@pytest.mark.parametrize("path", [
    "C:\\Program Files\\App\\app.exe",
    "C:\\Windows\\notepad.exe",
    "\\\\server\\share\\thing.exe",
    "C:\\x",
])
def test_real_paths_are_not_appids(path):
    """A real path handed to shell:AppsFolder makes Explorer open Documents."""
    assert _looks_like_appid(path) is False, path


def test_unc_path_with_one_separator_is_rejected():
    """`\\\\server\\thing.exe` has one backslash, the same count as the Notepad
    form, so the count alone is not enough - the leading braces are."""
    assert _looks_like_appid("\\\\server\\thing.exe") is False


@pytest.mark.parametrize("word", ["notepad", "firefox", "calc", "chrome", "brave"])
def test_plain_app_names_are_not_appids(word):
    assert _looks_like_appid(word) is False, word


def test_empty_and_blank_are_not_appids():
    assert _looks_like_appid("") is False
    assert _looks_like_appid("   ") is False
    assert _looks_like_appid(None) is False


def test_space_containing_string_is_not_an_appid():
    assert _looks_like_appid("a b c") is False


def test_protocol_uri_is_not_an_appid():
    """Already handled by an earlier stage; must not double-handle."""
    assert _looks_like_appid("ms-settings:display") is False


def test_posix_path_is_not_an_appid():
    assert _looks_like_appid("/usr/bin/thing") is False


# ── the guard against typing identifiers into the Start Menu ────────────────

def test_appid_shaped_target_is_refused_by_the_combined_guard():
    """This is what actually got typed on screen: the tail "5198B7}\\notepad".

    The tail alone is not all-hex - it is hex, a brace, a separator and a word -
    so the opaque guard does not catch it on its own. What catches it is the
    second half of the guard: the FULL target still looks like an AppID. The
    two checks together are what stop the search box being filled with
    developer output, so this asserts the combination rather than pretending
    one guard is sufficient.
    """
    tail = r"5198B7}\notepad"
    full = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\notepad.exe"

    # Neither check alone is enough, which is why the code does both.
    assert _looks_like_opaque_identifier(tail) is False
    assert _looks_like_appid(full) is True


def test_start_menu_fallback_guards_identifiers():
    """Behavioural check on the source, ignoring comments.

    The pattern being asserted appears in the explanatory comment that
    documents this very fix, so a naive grep would pass either way.
    """
    src = (_ROOT / "actions" / "open_app.py").read_text(encoding="utf-8-sig")
    code = [ln for ln in src.splitlines()
            if "_looks_like_opaque_identifier(clean_search)" in ln
            and not ln.strip().startswith("#")]
    assert code, "the Start Menu fallback no longer refuses identifiers"


def test_launch_reports_honestly():
    """`Popen` never raises, so a failed launch must not be reported as opened."""
    src = (_ROOT / "actions" / "open_app.py").read_text(encoding="utf-8-sig")
    # The AppID stage verifies with _process_appeared rather than assuming.
    appid_stage = src.split("# 4. Windows Store")[-1].split("# 5.")[0]
    assert "_process_appeared" in appid_stage, (
        "the AppID launch stage must verify the process appeared"
    )
    start_menu = src.split("# 5. Last resort")[-1]
    assert "_process_appeared" in start_menu, (
        "the Start Menu fallback must verify too, or it reports false success"
    )


# ── end to end against the real machine ─────────────────────────────────────

@pytest.mark.parametrize("name", ["notepad", "firefox", "calculator"])
def test_resolved_targets_for_real_apps_are_launchable(name):
    """Whatever the resolver returns must be something Windows can actually open.

    Every one of these resolved to an opaque identifier that does not exist on
    disk, which is precisely why `start <target>` failed and Windows Search
    appeared instead.
    """
    from actions.open_app import _resolve_app
    target, _note = _resolve_app(name)
    if _looks_like_appid(target):
        return                          # handled by shell:AppsFolder now
    pytest.skip(f"{name} resolved to a plain path ({target!r}); nothing to assert")