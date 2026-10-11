# Thank you for contributing.

Please read [CONTRIBUTING.md](../CONTRIBUTING.md) — it has the full house rules.
The short version:

- **Demonstrate it works.** Say what the test that would have caught the bug
  is, and what you did to verify the fix.
- **Explain why, not just what.** A good docstring says what was decided and
  what was rejected, and why.
- **Do not delete code to make a test pass.** If something is genuinely
  dead and should go, say so in the description and let the maintainer decide.
- **No fake features.** Every capability must actually run and be verifiable.
- **Nothing personal.** No real credentials, no `memory/` contents, no hardcoded
  identity strings.

## What this PR does

<!-- What changed, and why this approach over the obvious alternative. -->

## How it was verified

<!-- The command you ran and what it printed. "Ran the tests" is not a
     verification; the output is. -->

```
paste the relevant output here
```

## Checklist

- [ ] `python -m pytest -q -m "not network"` passes
- [ ] `python scripts/install_git_hooks.py` then a clean commit passes
- [ ] A test covers the new behaviour (or, for a bug fix, covers the bug)
- [ ] No credentials, personal data, or hardcoded identity in the diff
- [ ] Works offline, or the PR says why it cannot
- [ ] Anything deliberately left undone is written down below

## Known gaps

<!-- What you did not do, and why. This is the most useful section for the
     reviewer and the next contributor. "None" is a fine answer if true. -->