# 🏷️ J.A.R.V.I.S. Release Rules & Version Control Policy

> **Current Phase:** Active Development (`v0.1.0-dev`)  
> **Philosophy:** Defensive, Structured, and Milestone-Gated. No premature micro-releases.

---

## 1. Development Phase Principles
- **No Accidental Micro-Tags:** We do not publish release tags or GitHub Releases for single or trivial commits. The project stays cleanly in active development on `main`.
- **Zero-Trust Credential Gate:** Every pre-commit, pre-push, and CI pipeline strictly audits that private API keys (`config/api_keys.json`, `.env`, tokens) are never committed or packaged.
- **Conventional Commits Standard:** All commit messages must follow structured prefixes:
  - `feat(...)`: A new user-facing feature or tool action.
  - `fix(...)`: A bug fix, regex correction, or error handler.
  - `perf(...)`: Performance optimization (e.g. latency reduction, caching).
  - `refactor(...)`: Code change that neither fixes a bug nor adds a feature.
  - `docs(...)`: Documentation changes only.
  - `test(...)`: Adding or updating tests.
  - `chore(...)`: Routine maintenance, package updates.

---

## 2. The 20-Commit Milestone Threshold Rule
An automated release tag (`vX.Y.Z`) and official release package will **ONLY** be cut when:
1. **Minimum Volume:** At least **20 qualifying conventional commits** (`feat:`, `fix:`, `perf:`) have accumulated since the baseline/previous milestone.
2. **Quality Gate:** The full CI/CD test suite passes on both Windows and Linux across all tested Python matrix versions (3.11 & 3.12).
3. **Automated Changelog:** `CHANGELOG.md` is automatically updated and categorized into Features, Bug Fixes, and Performance Improvements.
4. **Manual Dispatch Option:** Maintainers can manually trigger an emergency release via GitHub Actions `workflow_dispatch` with an explicit reason.

---

## 3. Automation Tooling
We provide an automated verification engine:
```bash
# Check current progress towards the 20-commit release threshold
python scripts/check_release_readiness.py --check

# Force evaluate and bump version if threshold is satisfied
python scripts/check_release_readiness.py --bump
```

---

## 4. Branching Strategy
- **`main`**: The single source of truth. Always deployable and protected with pre-push hooks and CI checks.
- **Feature Branches**: `feat/<feature-name>` or `fix/<bug-name>` for large architectural changes.
