# Contributing to J.A.R.V.I.S

Thanks for looking. This is a voice-controlled assistant that runs entirely on
your own machine and can genuinely control it — open windows, move files, run
shell commands. Contributions are welcome, and the bar for a change is
"it demonstrably works on a real machine".

## Getting it running

```bash
git clone https://github.com/SudhirDevOps1/J.A.R.V.I.S.git
cd J.A.R.V.I.S
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
```

Then:

```bash
python main.py               # run it
python -m pytest -q -m "not network"    # the test suite
run_tests.bat                # Windows: the same thing plus the network tests
```

There is no build step for normal use. It runs from source.

### Installing as a package (optional)

If you want the `jarvis` command on your PATH:

```bash
pip install -e .
jarvis
```

This does **not** install dependencies. `requirements.txt` carries
`sys_platform` markers so a Linux user never pulls Windows-only wheels, and
`[project].dependencies` in `pyproject.toml` cannot express those without
duplicating the file and letting the two drift apart. So still run
`pip install -r requirements.txt` (or `python setup.py`) separately.

**Please do not commit `config/api_keys.json`.** It is in `.gitignore` and it
holds real credentials. Copy `config/api_keys.example.json` instead.

## Before you open a pull request

Run all three:

```bash
.venv\Scripts\python.exe -m pytest -q -m "not network"   # tests
.venv\Scripts\python.exe scripts\install_git_hooks.py      # install the hooks
```

The hooks are the ones CI enforces, running locally first so you find out in
three seconds rather than in a pull request:

- `pre-commit` — syntax, whole-tree parse, credential scan, flake8
- `pre-push` — whole-tree syntax, a critical-import probe, and the fast tests

If a hook is wrong, fix the hook rather than reaching for `--no-verify`, and
say so in the PR.

## What makes a good change here

**Demonstrate it works.** A pull request that says "improved the router" is
not reviewable. "This misrouted `hu use` to an app named `hu use`; here is the
test that reproduces it and the fix" is.

**Explain why, not just what.** The house style is a docstring that explains
the decision. `core/reflex_policy.py` is the reference: it has a *THE PROBLEM*,
a *WHY NOT JUST DELETE THE ROUTER*, and an explicit analysis of what it costs
to be wrong. Match that.

**Fix the cause, not the symptom.** When something misbehaved in this codebase,
the router was usually blamed and the real cause was three substring bugs in
`actions/open_app.py`. Look for the actual fault.

**Say what you did not do.** If a fix is partial, incomplete, or leaves a known
gap, write that down. It is more useful than discovering it later.

## House rules

- **Do not delete code to make a test pass.** If something is broken, fix it or
  explain why it cannot be. Removing a feature is a decision for the
  maintainer, and it needs a reason in the PR.
- **Do not add fake features.** Every capability must actually work and be
  verifiable. A stub that returns a plausible-looking result is worse than an
  honest "not implemented yet".
- **Do not hardcode personal identity.** App name, taskbar id, author strings
  and outbound API headers come from configuration — see
  `core/app_identity.py`. Every fork and every user is expected to be able to
  set their own.
- **Do not commit anything from `memory/` or a real `config/api_keys.json`.**
  That is the user's own data and credentials.
- **Keep it offline-capable.** The assistant must remain useful with no network.
  Do not make a cloud dependency part of the core path.
- **Wrap external calls in try/except** and report the failure in the UI. A
  background thread that dies silently is a bug.

## Tests

- Put new tests in `tests/`, named `test_<what_it_covers>.py`.
- A bug fix needs a test that fails before the fix and passes after. Say in the
  PR which test would have caught it.
- Pure logic gets tested directly with no GUI or network.
- Anything touching Qt needs a `QApplication`; `tests/conftest.py` sets
  `QT_QPA_PLATFORM=offscreen` so this works headless.
- Anything hitting the network gets `@pytest.mark.network` so CI can skip it.
- Never assert by grepping a source file for a string. It matches the
  explanatory comments about the fix and passes for the wrong reason. Assert
  on behaviour.

## Adding a tool

A tool is one file in `actions/` with a `NAME`, a `DESCRIPTION`, and a
`run()`.

The `DESCRIPTION` is not documentation for humans — it is what the model reads
to decide whether your tool is the right one. This matters more than it looks:
an earlier tool set had six descriptions between 32 and 92 characters long, and
the model confidently invented app names because it had nothing to go on.

Write it as:

```
DESCRIPTION = """USE FOR: <the specific requests this handles>
DO NOT USE FOR: <nearby requests that must go elsewhere>

<what it does, what it returns, any constraints>"""
```

See the rewritten descriptions in `actions/open_app.py` and
`actions/web_search.py` for the pattern.

## Adding a plugin

Copy `plugins/_template.py`. That is genuinely the whole process. Plugins
discover themselves from `plugins/*.py`, appear in the plugin manager, and can
be enabled and disabled per install.

Plugins run with full privileges. Say so in your documentation.

## Style

No enforced formatter, so match the file you are editing.

- 4-space indent, ~79–100 column soft limit
- `try/except Exception` around anything touching the filesystem, network, or
  subprocess
- Comments explain *why*. A comment restating the code is noise.
- Module docstring at the top of new files explaining what it is for

## Licensing

By contributing you agree your work is licensed under **GPL-3.0**, matching the
project. See [LICENSE](LICENSE).

A note on why this is GPL and not MIT: the GUI is PyQt6, which Riverbank
distributes as GPL-3.0-only. An MIT licence over a GPL-only dependency would not
be enforceable. If you want to contribute something that cannot be GPL — for
example you insist on a permissive licence for your own code — open an issue
first and we will work something out.

## Reporting bugs

Open an issue with:

- what you did
- what you expected
- what happened
- version or commit hash, OS, Python version
- the relevant part of `logs/jarvis_runtime.log`

**Remove your API keys from anything you paste.** If you are unsure, paste
into a text editor and read it first.

## Code of conduct

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Security issues

Do not open a public issue. See [SECURITY.md](SECURITY.md).