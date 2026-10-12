"""
tests/test_packaging.py — Packaging metadata and the setup.py dispatch.

WHY THIS IS TESTED
------------------
`pip install -e .` did not work at all. The reason is a genuine design clash:
setup.py is not a setuptools script, it is a bootstrap installer that shells
out to pip and downloads Playwright browsers. There was no pyproject.toml and
no project metadata, so setuptools executed setup.py, found no setup() call,
and failed with "Exactly one .egg-info should have been produced, but found 0".

The fix has to satisfy two audiences from one file:
  a person running `python setup.py`   -> run the bootstrap
  pip running `setup.py egg_info`      -> call setup(), read pyproject.toml

Getting the second case wrong in either direction is bad, and both wrong ways
were tried:
  * exiting quietly  -> metadata generation fails
  * bootstrapping    -> pip installs from inside a pip transaction and needs
                        the network during metadata generation

So both are pinned here.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def pyproject() -> dict:
    path = _ROOT / "pyproject.toml"
    assert path.exists(), "pyproject.toml must exist for the project to be installable"
    return tomllib.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def setup_module_():
    """setup.py loaded as a module.

    Loading it as __main__ would run the bootstrap and shell out to pip, so it
    is loaded under a different name where nothing executes.
    """
    spec = importlib.util.spec_from_file_location(
        "_setup_probe", _ROOT / "setup.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── pyproject metadata ──────────────────────────────────────────────────────

def test_build_system_is_declared(pyproject):
    """Without this pip has no backend and `pip install -e .` cannot work."""
    bs = pyproject.get("build-system", {})
    assert bs.get("build-backend")
    assert any("setuptools" in r for r in bs.get("requires", []))


def test_project_metadata_present(pyproject):
    proj = pyproject.get("project", {})
    for key in ("name", "description", "requires-python"):
        assert proj.get(key), f"project.{key} is missing"


def test_version_is_not_hardcoded(pyproject):
    """The single-source rule.

    A literal version here desynchronises the moment Release Please bumps
    core/version.py, and nothing complains: the repository says 0.2.0, the
    package says 1.4.0, and both are correct files. This is not theoretical -
    that is exactly what happened the first time this file was written.
    """
    assert "version" not in pyproject["project"], (
        "project.version must stay absent; declare it in [project] dynamic and "
        "read it from core/version.py, which is what Release Please bumps"
    )
    assert "version" in pyproject["project"].get("dynamic", [])


def test_package_version_matches_the_version_module(pyproject):
    """End to end: what pip would report is what the repo reports."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_version_probe", _ROOT / "core" / "version.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    attr = pyproject["tool"]["setuptools"]["dynamic"]
    # Table form. The list form ([{version = {...}}]) is rejected by setuptools
    # with "configuration error: tool.setuptools.dynamic must be object".
    assert attr == {"version": {"attr": "core.version.__version__"}}, attr

    from core.version import __version__
    assert __version__ == mod.__version__
    # A well-formed version, not None or empty.
    assert __version__ and __version__[0].isdigit(), __version__


def test_version_module_licence_matches_the_license_file(pyproject):
    """core/version.py said __license__ = "MIT" after the relicensing pass.

    Metadata nobody reads is where wrong facts survive longest, so this is
    asserted rather than trusted.
    """
    from core.version import __license__
    licence_text = (_ROOT / "LICENSE").read_text(encoding="utf-8", errors="replace")
    assert "GNU GENERAL PUBLIC LICENSE" in licence_text
    assert "MIT" not in __license__, (
        f"core/version.py still declares {__license__!r}; the project is GPL-3.0"
    )
    declared = pyproject["project"].get("license", {})
    text = declared.get("text", "") if isinstance(declared, dict) else str(declared)
    assert __license__ in text, (
        f"core/version.py says {__license__!r} and pyproject says {text!r}"
    )


def test_readme_is_declared_and_exists(pyproject):
    readme = pyproject["project"]["readme"]
    assert (_ROOT / readme).exists(), f"{readme} is referenced but absent"


def test_licence_matches_the_license_file(pyproject):
    """The licence was MIT in LICENSE while PyQt6 is GPL-3.0-only. The metadata
    must not disagree with the file it ships beside."""
    declared = pyproject["project"].get("license", {})
    text = declared.get("text", "") if isinstance(declared, dict) else str(declared)
    assert "GPL" in text, f"pyproject declares {text!r}"
    licence_text = (_ROOT / "LICENSE").read_text(encoding="utf-8", errors="replace")
    assert "GNU GENERAL PUBLIC LICENSE" in licence_text


def test_classifier_matches_the_licence(pyproject):
    classifiers = pyproject["project"].get("classifiers", [])
    gpl = [c for c in classifiers if "License ::" in c]
    assert any("GPLv3" in c for c in gpl), f"licence classifiers: {gpl}"


def test_requires_python_matches_the_classifiers(pyproject):
    """3.11 and 3.12 are what CI runs; the metadata must not claim otherwise."""
    assert pyproject["project"]["requires-python"].startswith(">=3.11")


def test_homepage_points_at_the_real_repository(pyproject):
    urls = pyproject.get("project", {}).get("urls", {})
    assert any("github.com" in str(v) for v in urls.values())


def test_dependencies_are_empty_because_requirements_txt_owns_them(pyproject):
    """Deliberate.

    requirements.txt carries sys_platform markers so a Linux user never pulls
    Windows-only wheels. setuptools cannot express those in [project]
    dependencies without duplicating the file and letting the two drift.
    """
    assert pyproject["project"]["dependencies"] == []
    assert (_ROOT / "requirements.txt").exists()


def test_declared_packages_are_real(pyproject):
    """A package listed here but absent on disk breaks the build.

    This was a real mistake while writing the file: `actions` and `scripts` have
    no __init__.py (they are loaded by path), and a placeholder module name was
    listed that never existed.
    """
    for name in pyproject["tool"]["setuptools"]["packages"]:
        assert (_ROOT / name / "__init__.py").exists(), (
            f"pyproject declares package {name!r} but "
            f"{name}/__init__.py does not exist"
        )


def test_declared_modules_are_real(pyproject):
    for name in pyproject["tool"]["setuptools"].get("py-modules", []):
        assert (_ROOT / f"{name}.py").exists(), (
            f"pyproject declares module {name!r} but {name}.py does not exist"
        )


def test_entry_point_target_exists(pyproject):
    for target in pyproject["project"].get("scripts", {}).values():
        module_name = target.split(":")[0]
        assert (_ROOT / f"{module_name}.py").exists(), target


def test_tool_config_does_not_claim_stricter_than_ci_enforces(pyproject):
    """ruff's select must match the flake8 classes CI gates on.

    Setting ruff wider than that would fail on first run across ~190 files and
    train contributors to ignore it.
    """
    select = set(pyproject["tool"]["ruff"]["lint"]["select"])
    assert select == {"E9", "F63", "F7", "F82"}


def test_mypy_is_not_strict_on_an_unannotated_codebase(pyproject):
    """Turning on strict checking here would produce noise, not signal."""
    assert pyproject["tool"]["mypy"]["disallow_untyped_defs"] is False


# ── setup.py dispatch ───────────────────────────────────────────────────────

@pytest.mark.parametrize("argv,expect_backend", [
    (["setup.py"], False),
    (["setup.py", "--help"], False),
    (["setup.py", "egg_info"], True),
    (["setup.py", "develop"], True),
    (["setup.py", "editable_wheel"], True),
    (["setup.py", "bdist_wheel"], True),
    (["setup.py", "sdist"], True),
    (["setup.py", "dist_info"], True),
])
def test_setup_py_tells_a_person_from_a_build_tool(setup_module_, monkeypatch,
                                                  argv, expect_backend):
    """A person must get the bootstrap; pip must get setup()."""
    monkeypatch.setattr(sys, "argv", argv)
    assert setup_module_._invoked_by_build_backend() is expect_backend


def test_setup_py_import_has_no_side_effects(setup_module_):
    """Importing it must not shell out to pip or download browsers."""
    assert callable(setup_module_.main)
    assert callable(setup_module_._invoked_by_build_backend)


# ── the real thing ──────────────────────────────────────────────────────────

@pytest.mark.slow
def test_editable_install_resolves_metadata(tmp_path):
    """Actually ask pip to prepare editable metadata.

    Marked slow: it spawns pip and installs build dependencies into a
    throwaway environment. This is the only check that proves the two dispatch
    branches above actually work together, so it is worth running before a
    release.
    """
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--no-deps",
         "--dry-run", "--no-build-isolation"],
        cwd=str(_ROOT), capture_output=True, text=True, timeout=900,
    )
    out = (r.stdout + r.stderr).lower()
    assert r.returncode == 0, out[-1500:]
    assert "egg-info should have been produced" not in out, (
        "setup.py did not call setup() for the build backend"
    )
    assert "jarvis-assistant" in out