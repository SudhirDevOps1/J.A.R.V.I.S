"""
core/pii_redactor.py - Redact secrets and personal identifiers before they persist.

WHY THIS EXISTS
---------------
J.A.R.V.I.S writes every exchange to an append-only journal at
memory/journals/YYYY-MM-DD.md, and that journal is described in the code as an
"immutable second-brain activity record". Nothing was ever filtered out of it.

The consequence is not theoretical. A full scan of this repository's history
found config/knowledge_graph.json in commits 573a30a5 and 49f38404 containing
a person's relationships: which relative contacts them through which messenger,
and which friend is named what. The repo is public. That data left the machine
because a conversation was written to disk verbatim and later committed.

So this is not about hiding secrets from the user. It is about the assistant
silently copying a credential out of a spoken sentence into a file that a fork
can read.

WHY CHECKSUMS
-------------
A redactor that guesses is worse than no redactor, because a false positive
destroys a real record and teaches the user the tool cannot be trusted. The
patterns that CAN be verified are verified:

    card number  -> Luhn checksum
    Aadhaar      -> Verhoeff checksum

Those two have a 1-in-10 false-positive rate by checksum alone, and the
digit-count and word-boundary rules take it lower. Anything that cannot be
verified is only matched with a strong prefix or an explicit keyword nearby,
never on its own.

DESIGN
------
    scan(text)     -> list[Finding], text untouched
    redact(text)   -> text with typed placeholders
    is_enabled()   -> honours config/privacy_settings.json

Redaction keeps the last few digits of a card or Aadhaar. A journal entry that
says "[REDACTED]" cannot be recognised by the person who wrote it, and the
point of a second-brain record is that the owner can still read it. Secrets and
keys are never partially kept - there is no useful partial key.

Nothing here raises. It runs on every memory write, so a crash in redaction
must not cost the user their journal entry.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, NamedTuple, Optional


# ── checksums ───────────────────────────────────────────────────────────────

def luhn_ok(digits: str) -> bool:
    """Standard Luhn. Rejects typos, transpositions and most random numbers."""
    if not digits.isdigit() or len(digits) < 12:
        return False
    total = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        d = ord(ch) - 48
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
_VERHOEFF_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def verhoeff_ok(digits: str) -> bool:
    """Verhoeff checksum, as used by the Indian Aadhaar authority.

    A 12-digit number that is not a real Aadhaar fails this. That is the point:
    it means a timestamp, a phone number or a count is left alone.
    """
    if not digits.isdigit() or len(digits) != 12:
        return False
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][ord(ch) - 48]]
    return c == _VERHOEFF_INV[c % 10]


# ── findings ────────────────────────────────────────────────────────────────

class Finding(NamedTuple):
    kind: str          # "openai-key", "aadhaar", ...
    start: int
    end: int
    sample: str        # a short masked preview, never the raw value


# A recognisable prefix is a far stronger signal than a generic shape, because
# these are vendor-assigned and cannot collide with ordinary English text.
_PREFIXED = [
    ("github-fine-grained-token", r"github_pat_[A-Za-z0-9_]{22,}"),
    ("github-token",             r"gh[pousr]_[A-Za-z0-9]{20,}"),
    ("gitlab-token",             r"glpat-[A-Za-z0-9_\-]{16,}"),
    ("slack-token",              r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    ("openai-key",               r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{16,}"),
    ("google-api-key",           r"\bAIza[0-9A-Za-z_\-]{30,}"),
    ("aws-access-key",           r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b"),
    ("stripe-key",               r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}"),
    ("sendgrid-key",             r"\bSG\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,}"),
    ("npm-token",                r"\bnpm_[A-Za-z0-9]{30,}"),
    ("huggingface-token",        r"\bhf_[A-Za-z0-9]{30,}"),
    ("discord-bot-token",        r"\b[MNO][A-Za-z0-9_\-]{23}\.[\w\-]{6}\.[\w\-]{27}\b"),
    ("jwt",                      r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"),
    ("bearer-token",             r"\b[Bb]earer\s+([A-Za-z0-9_\-.=]{16,})"),
]

_ASSIGNED = re.compile(
    r"(?i)\b(pass(?:word|wd)?|api[_\- ]?key|secret|auth[_\- ]?token|access[_\- ]?token"
    r"|client[_\- ]?secret|private[_\- ]?key|bearer)\b"
    r"\s*(?:is|=|:)\s*"
    r"""(?P<q>["']?)(?P<val>[^\s"'`,;)]{6,})(?P=q)"""
)

_PRIVATE_KEY = re.compile(
    r"-----BEGIN\s+(?:[A-Z0-9 ]+\s)?PRIVATE KEY-----"
    r"[\s\S]*?"
    r"-----END\s+(?:[A-Z0-9 ]+\s)?PRIVATE KEY-----"
)

_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

_PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")

_URL_CREDENTIALS = re.compile(r"\b([a-z][a-z0-9+.\-]*://)([^\s:/@]+):([^\s@/]+)@", re.I)

# 12 digits, but only accepted when Verhoeff agrees AND the number is shaped
# like something a person would label.
#
# Verhoeff alone is not enough. It accepts one arbitrary 12-digit string in
# ten, so "202601141230" - a timestamp - passed it. Found by the checker, not
# by reading the code.
_AADHAAR = re.compile(r"(?<!\d)(\d{4}[\s\-]?\d{4}[\s\-]?\d{4})(?!\d)")

# 13-19 digits, only accepted when Luhn agrees.
_CARD = re.compile(r"(?<!\d)(?:\d[ \-]?){12,18}\d(?!\d)")

# A bare 10-digit number is far too ambiguous to redact: it is also a count, a
# year range, an amount in paise. Require the +91 prefix or a nearby keyword.
_PHONE = re.compile(
    r"(?i)(?:(?<=\+91)|(?<=\+91[\s\-])|(?<=phone)|(?<=mobile)|(?<=number))"
    r"[\s\-]?[6-9]\d{4}[\s\-]?\d{5}(?!\d)"
)
_IND_PHONE = re.compile(r"(?i)(?<!\w)\+?91[\s\-]?[6-9]\d{4}[\s\-]?\d{5}\b")

# Labels that make a bare 12-digit number unambiguous.
_AADHAAR_CONTEXT = re.compile(
    r"(?i)aadhaar|आधार|uidai|आधार\s*नंबर|aadhaar\s*(?:no|number|card)"
)


def _aadhaar_plausible(raw: str, src: str, start: int) -> bool:
    """Verhoeff plus one more condition, because Verhoeff alone is 1-in-10.

    It accepts one arbitrary 12-digit string in ten, so "202601141230" - a
    timestamp - passed it. Found by the checker, not by reading the code.

    Order matters, and getting it wrong hides a real Aadhaar. An explicit label
    beats the shape heuristic: if the user typed the word "aadhaar", that is a
    far stronger signal than any rule about what the digits look like, and the
    first version rejected "aadhaar 202601141230" because it checked the shape
    first. The user named the thing. Believe them.

    Accepts when Verhoeff agrees and either:
      * a label appears within a short window before the number, or
      * the number carries a separator, which is how Aadhaar is always written
        out ("2345 6789 0124").

    Otherwise it is a bare 12-digit number that could be a timestamp, a job
    number or a serial, and is left alone.
    """
    clean = _clean_number(raw)
    if not verhoeff_ok(clean):
        return False

    window = src[max(0, start - 40):start]
    if _AADHAAR_CONTEXT.search(window):
        return True

    if re.search(r"[\s\-]", raw):
        return True

    # No label and no separator: reject the shapes most likely to collide.
    if re.fullmatch(r"(?:19|20)\d{10}", clean):
        return False
    return False


def _clean_number(raw: str) -> str:
    return re.sub(r"[\s\-]", "", raw)


def _mask(kind: str, raw: str) -> str:
    """A preview that identifies the finding without reproducing it."""
    digits = re.sub(r"\D", "", raw)
    if kind in ("card", "aadhaar") and len(digits) >= 4:
        return f"{kind} ending {digits[-4:]}"
    head = raw[:3]
    return f"{kind} starting {head}… ({len(raw)} chars)"


def _iter_prefixed():
    for kind, pat in _PREFIXED:
        yield kind, re.compile(pat)


def scan(text: str) -> List[Finding]:
    """Everything sensitive in `text`, without modifying it."""
    src = str(text or "")
    if not src:
        return []

    found: List[Finding] = []
    taken: List[tuple] = []

    def overlaps(a: int, b: int) -> bool:
        return any(a < e and s < b for s, e in taken)

    def add(kind: str, start: int, end: int) -> None:
        if not overlaps(start, end):
            taken.append((start, end))
            found.append(Finding(kind, start, end, _mask(kind, src[start:end])))

    # Order matters: the widest, most specific shapes claim their span first so
    # a private key is not shredded into four "assigned secret" hits.
    for m in _PRIVATE_KEY.finditer(src):
        add("private-key", m.start(), m.end())

    for kind, rx in _iter_prefixed():
        for m in rx.finditer(src):
            s, e = m.span()
            # A bearer match includes the literal "Bearer "; keep the token
            # only, so the redaction does not eat the word.
            if kind == "bearer-token" and m.groups():
                s = m.start(m.lastindex or 0)
            add(kind, s, e)

    for m in _ASSIGNED.finditer(src):
        s, e = m.span("val")
        if m.group("q"):
            s -= 1
            e += 1
        add("assigned-secret", s, e)

    for m in _URL_CREDENTIALS.finditer(src):
        add("url-credentials", m.start(3), m.end(3))

    for m in _EMAIL.finditer(src):
        add("email", m.start(), m.end())

    for m in _PAN.finditer(src):
        add("pan-card", m.start(), m.end())

    for m in _AADHAAR.finditer(src):
        if _aadhaar_plausible(m.group(1), src, m.start()):
            add("aadhaar", m.start(), m.end())

    for m in _CARD.finditer(src):
        raw = m.group(0)
        clean = _clean_number(raw)
        if 13 <= len(clean) <= 19 and luhn_ok(clean):
            add("card", m.start(), m.end())

    for rx in (_IND_PHONE, _PHONE):
        for m in rx.finditer(src):
            add("phone", m.start(), m.end())

    return sorted(found, key=lambda f: f.start)


def redact(text: str, keep_last: int = 4) -> str:
    """`text` with every finding replaced by a typed, recognisable marker.

    Cards and Aadhaar keep their last digits; keys and tokens keep nothing.

    The placeholder is deliberately ASCII. An earlier version used a bullet
    character and it came out as mojibake the moment anything read the journal
    through a cp1252 console - which is exactly where the user sees it.
    """
    src = str(text or "")
    hits = scan(src)
    if not hits:
        return src

    out: List[str] = []
    cursor = 0
    for f in hits:
        out.append(src[cursor:f.start])
        raw = src[f.start:f.end]
        if f.kind in ("card", "aadhaar") and keep_last > 0:
            digits = re.sub(r"\D", "", raw)
            tail = digits[-keep_last:] if len(digits) > keep_last else ""
            out.append(f"[REDACTED:{f.kind} ****{tail}]" if tail
                       else f"[REDACTED:{f.kind}]")
        else:
            out.append(f"[REDACTED:{f.kind}]")
        cursor = f.end
    out.append(src[cursor:])
    return "".join(out)


def summarize(text: str) -> str:
    """One line describing what was redacted, or '' when nothing was."""
    kinds = []
    for f in scan(text):
        if f.kind not in kinds:
            kinds.append(f.kind)
    if not kinds:
        return ""
    return "Redacted " + ", ".join(kinds) + f" ({len(kinds)} kind(s))."


# ── configuration ───────────────────────────────────────────────────────────

def is_enabled() -> bool:
    """Honours config/privacy_settings.json. Defaults to on.

    Defaults to ON deliberately. A privacy control that ships disabled is a
    control nobody turns on, and the failure it prevents is irreversible -
    the data has already been written and may already be committed.
    """
    try:
        from core.privacy_guard import load_privacy_settings
        settings: Dict[str, Any] = load_privacy_settings()
    except Exception:
        return True
    return bool(settings.get("redact_pii_in_memory", True))


def redact_if_enabled(text: str, keep_last: int = 4) -> str:
    """The call the write paths use. Never raises."""
    try:
        if not is_enabled():
            return str(text or "")
        return redact(text, keep_last=keep_last)
    except Exception as e:
        # Losing the journal entry would be worse than storing it unredacted,
        # and the user can still see this printed in the log.
        print(f"[PII] redaction failed, storing as-is: {e}")
        return str(text or "")


__all__ = [
    "Finding",
    "luhn_ok",
    "verhoeff_ok",
    "scan",
    "redact",
    "summarize",
    "is_enabled",
    "redact_if_enabled",
]