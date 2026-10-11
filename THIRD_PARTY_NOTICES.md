# Third-Party Notices

J.A.R.V.I.S itself is licensed under GPL-3.0 — see [LICENSE](LICENSE).

This file records the third-party code that is **vendored into this
repository**, meaning copied into the source tree rather than installed from a
package index. Those obligations attach to the files themselves, not to
anything installed by `pip install -r requirements.txt`; ordinary dependencies
are covered by their own licences.

If you vendor more code, add it here. A missing entry is a licence violation,
and a stale entry is worse than none because it looks like compliance.

---

## CryptoJS — `dashboard/static/crypto-js.min.js`

CryptoJS is a JavaScript crypto library, used by the dashboard for
client-side hashing.

- **Project:** https://github.com/brix/crypto-js
- **Licence:** MIT
- **Vendored form:** minified bundle

### Notice-compliance problem, unresolved

The vendored file has had its licence banner **stripped**. The original
CryptoJS distribution carries a header reading approximately:

```
// CryptoJS v4.x.x
// (c) 2009-2019 Jeff Mott. 2009-2019 Jeff Mott.
```

MIT section 1 requires the copyright notice and permission notice to be
included in all copies or substantial portions of the software. A minified
build with the banner removed is still a copy, and removing the notice is a
violation regardless of how permissively the licence is worded.

### How to fix

Either of these resolves it:

1. **Re-vendor with the banner intact.** Fetch the upstream
   `crypto-js.min.js` and prepend the header:

   ```powershell
   # or any equivalent
   curl.exe -o dashboard/static/crypto-js.min.js `
       https://raw.githubusercontent.com/brix/crypto-js/develop/crypto-js.min.js
   ```

   then prepend the CryptoJS copyright header if the download lacks it.

2. **Stop vendoring it.** Serve CryptoJS from a CDN and drop the file, or
   replace the one hash the dashboard needs with Python's `hashlib` exposed
   through an endpoint.

### Recording the version

The exact CryptoJS version is currently **unknown** because the banner that
would state it was removed. `4.2.0` is a guess and must be confirmed against
whatever is actually in the file before this entry is considered complete.

---

## gemini-web2api — `core/gemini_free_proxy.py`

An embedded Gemini web-to-OpenAI proxy, adapted from an existing MIT-licensed
project and modified for this codebase.

- **Upstream:** https://github.com/Sophomoresty/gemini-web2api
- **Licence:** MIT
- **Changes:** substantial. This is a modified work, not a verbatim copy.

The file carries a one-line attribution in its docstring. That is enough to
credit the author but **not** enough to satisfy MIT, which requires the full
copyright notice and permission notice in copies or substantial portions.

### How to fix

Add the upstream project's full MIT notice to the top of the file, and record
the upstream commit hash the adaptation was taken from:

```python
# ---------------------------------------------------------------------------
# Portions derived from gemini-web2api
# Copyright (c) <year> <upstream author>
# Licensed under the MIT License - see THIRD_PARTY_NOTICES.md for the full text.
# Adapted from commit <sha>.
# ---------------------------------------------------------------------------
```

Confirm the upstream author name, year and licence text from the repository
itself before adding them — do not infer them.

---

## Branding assets

`config/jarvis.ico`, `config/jarvis.png` and `config/jarvis_master.jpg` are
**generated procedurally** by `scripts/generate_icon.py` using Pillow, and are
original work covered by this project's GPL-3.0 licence.

`core/assets/avatar/celestial_avatar.jpg` and `face.png` at the repository
root are **byte-identical photographs** with **unknown provenance**. They are
not covered by any licence grant in this repository and their status is
unresolved:

- If they are stock photography, the licence may forbid redistribution.
- If they are AI-generated, there may be no third-party rights at all.
- If they were uploaded by a user, they belong to that user.

`face.png` is a duplicate of `core/assets/avatar/celestial_avatar.jpg`
(identical MD5) sitting at the repository root.

### How to fix

Establish where they came from and either

- replace them with assets of known provenance, or
- add a `docs/ASSET_PROVENANCE.md` recording the source and licence for each, or
- remove them from the repository if they cannot be cleared.

Do not ship them to a public release until this is settled.