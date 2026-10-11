# Security Policy

## Reporting a vulnerability

**Please report security issues privately. Do not open a public GitHub issue.**

Email: **security@jarvis-ai.local** (replace with your project's real address
before publishing — see *Before you publish* below)

Use GitHub's private vulnerability reporting if you prefer:
**Security → Report a vulnerability** on the repository page.

Please include:

- what you did, step by step
- what you expected and what happened instead
- the version or commit hash
- your OS and Python version
- any proof-of-concept code or logs

You should get an acknowledgement within **72 hours** and a substantive
response within **7 days**. If a report is accepted we will agree a disclosure
date with you before publishing anything.

## What counts as a security issue here

J.A.R.V.I.S controls a real machine: it opens and closes applications, runs
shell commands, reads and writes files, captures the screen, uses the webcam
and microphone, and holds API keys. Treat it as privileged software.

In scope:

- code execution without the user asking for it
- the **confirmation gate** being bypassed — a dangerous action running without
  an explicit user confirmation
- the **undo stack** failing to undo something it claimed to undo
- screen, webcam or microphone capture happening when it should not
- secrets (API keys, tokens, credentials) readable from disk, logs, the
  dashboard, or an HTTP response
- authentication or authorisation bypass on the local dashboard, including the
  WebSocket
- the local dashboard or remote-control surface reachable from outside the
  machine when it should not be
- remote code execution through an MCP server, a plugin, or a tool argument
- a privacy or redaction control silently failing open
- path traversal or arbitrary file read/write through any tool

Not a vulnerability:

- J.A.R.V.I.S does something it is documented to do when you ask it to
- a local user can already read their own config files
- missing hardening on an endpoint that requires local authentication and is
  only bound to `127.0.0.1`
- findings from automated scanners with no demonstrated impact
- social engineering of the user into approving an action

## Supported versions

The `main` branch. There are no tagged releases yet.

## Security design notes

Useful context if you are reviewing this codebase. These are the controls that
exist; if you find a gap, these are the places to look.

| Control | Where | What it does |
|---|---|---|
| Confirmation gate | `core/confirm_gate.py` | Dangerous actions require a physical UI confirmation. A confirmation token is issued by the UI, never by the model. |
| Danger tools never auto-execute | `core/reflex_policy.py` | The reflex tier can never auto-run a tool on the `_NEVER_TRUST_TOOLS` list, regardless of how much history it has accumulated. |
| Audit log | `memory/audit.jsonl` | Records every sensitive action: what ran, when, and whether it was confirmed. |
| Undo stack | see `core/undo_stack.py` | Sensitive actions are reversible. |
| Secret vault | `core/secret_vault.py` | Credentials are stored separately from ordinary config and are never sent back in listings. |
| Dashboard auth | `dashboard/server.py` | Token auth with expiry and sweeping. Auto self-signed TLS. |
| Upload guard | `dashboard/server.py` | Blocks executable uploads, enforces a size cap, and rejects traversal in names. |
| Privacy guard | `core/privacy_guard.py` | Redacts sensitive data before it reaches a model or a log. **Fails closed.** |
| HTML sanitizer | `ui/html_sanitize.py` | Allowlist sanitiser for anything rendered with `setHtml`. |
| Credential scanner | `scripts/git_hooks/checks.py` | `pre-commit` blocks known credential shapes from being committed. |

### Known weaknesses, stated plainly

- **It is not sandboxed.** J.A.R.V.I.S runs actions as the logged-in user with
  the user's full privileges. The confirmation gate is a speed bump against
  accidents, not a security boundary against a determined attacker.
- **Plugins are trusted code.** A plugin runs with the same privileges as the
  assistant. Install plugins you would be willing to run as yourself.
- **MCP servers are trusted code.** The same applies.
- **The model can be talked into approving things.** The confirmation gate
  exists precisely because instruction-following is not a guarantee.
- **Screen and webcam capture are sensitive by nature.** Capture only happens
  on an explicit command, but the data is then in memory and possibly in logs.

## Before you publish

This policy references `security@jarvis-ai.local`, which is a placeholder.
Replace it with a real address you control, or delete the email line and rely
on GitHub private vulnerability reporting only.

For a project with this level of access to a user's machine, a published
security contact is what makes a responsible disclosure possible at all.