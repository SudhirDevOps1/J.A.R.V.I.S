"""
ui/markdown.py — render model and tool output as readable HTML.

THE PROBLEM
-----------
Ask J.A.R.V.I.S to write an HTML file and it replies with the markup flattened
into a wall of plain text. Ask it to explain a stack trace, show a table, or
paste a shell command, and the same thing. The assistant is a coding tool; the
single most common thing it produces is code, and the output surface showed
that code with all its structure stripped out.

ui/html_sanitize.py made the content panel safe. This makes it readable. The
two fit together deliberately: markdown renders to HTML, and that HTML then
goes through the same allowlist sanitizer, so rendering a document can never
open a hole that sanitizing alone was closing.

SCOPE, DELIBERATELY
-------------------
This is not CommonMark and does not try to be. It handles what actually comes
out of a personal assistant answering questions about a computer:

  fenced code blocks ``` with an optional language hint
  indented code blocks
  ATX headings # .. ######
  unordered and ordered lists
  blockquotes
  horizontal rules
  pipe tables
  paragraphs and hard line breaks
  inline: bold, italic, strikethrough, inline code, links, bare URLs

Everything else degrades to escaped text rather than being dropped, because a
renderer that silently loses a paragraph is worse than one that renders it
plain.

WHY A HAND-ROLLED RENDERER AND NOT A LIBRARY
--------------------------------------------
It has to run inside the content panel's existing sanitize path, and it has to
be readable and fixable in one sitting. A markdown library emits HTML with its
own opinions about which tags to allow, which is exactly the decision the
sanitizer exists to own. Rendering produces a narrow, known set of tags; the
sanitizer then independently decides what survives. Defence in depth, not
either/or.

No PyQt import here, so all of this is testable headless.
"""
from __future__ import annotations

import html
import re
from typing import List, Optional

# ── inline rules ────────────────────────────────────────────────────────────
#
# Order matters. Inline code is extracted first and its contents are never
# re-scanned, so `**bold**` inside a code span stays literal instead of being
# rendered as emphasis. That is the single most common way markdown renderers
# corrupt code, and this program exists mostly to show code.

_CODE_SPAN_RE = re.compile(r"(`+)(.+?)\1", re.S)
_BOLD_RE = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.S)
_BOLD_ALT_RE = re.compile(r"__(?=\S)(.+?)(?<=\S)__", re.S)
_ITALIC_RE = re.compile(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])")
_ITALIC_ALT_RE = re.compile(r"(?<![\w_])_(?=\S)([^_\n]+?)(?<=\S)_(?![\w_])")
_STRIKE_RE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~", re.S)
_LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
_BARE_URL_RE = re.compile(r"(?<![\"'=>])\b(https?://[^\s<>\"')]+)")


class _Inline:
    """Escape once, then apply inline rules, then protect code spans.

    Escaping first is what makes the rest safe: after this, a literal `<` in
    the source is `&lt;`, so none of the later substitutions can accidentally
    re-introduce a tag. Code spans are held aside as placeholders for the same
    reason - a model answering "what does <div> do" should see <div>, not have
    it swallowed as markup.
    """

    def __init__(self):
        self._spans: List[str] = []

    def _stash(self, code: str) -> str:
        self._spans.append(code)
        return f"\x00CODE{len(self._spans) - 1}\x00"

    def _restore(self, text: str) -> str:
        for i, code in enumerate(self._spans):
            text = text.replace(f"\x00CODE{i}\x00", code)
        return text

    def render(self, source: str) -> str:
        # 1. Pull code spans out before anything else can touch them.
        #
        # The body is escaped HERE, not left to the pass below. Everything
        # else in the source has already been escaped by the time it gets
        # restored, so a code span holding the raw text would come back as
        # live markup - `what does <div> do` would actually inject a div,
        # and an answer explaining a script tag would execute it.
        def _code_sub(m: re.Match) -> str:
            body = html.escape(m.group(2).strip(), quote=False)
            return self._stash(f"<code>{body}</code>")

        text = _CODE_SPAN_RE.sub(_code_sub, source)

        # 2. Escape everything that remains.
        text = html.escape(text, quote=False)

        # 3. Inline rules over the escaped text.
        text = _LINK_RE.sub(
            lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
        text = _BARE_URL_RE.sub(
            lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>', text)
        text = _BOLD_RE.sub(r"<b>\1</b>", text)
        text = _BOLD_ALT_RE.sub(r"<b>\1</b>", text)
        text = _STRIKE_RE.sub(r"<s>\1</s>", text)
        text = _ITALIC_RE.sub(r"<i>\1</i>", text)
        text = _ITALIC_ALT_RE.sub(r"<i>\1</i>", text)

        # 4. Hard line break: two trailing spaces, or a trailing backslash.
        text = re.sub(r"(?: {2,}|\\)\n", "<br>\n", text)

        return self._restore(text)


def render_inline(source: str) -> str:
    return _Inline().render(source or "")


# ── block rules ─────────────────────────────────────────────────────────────

_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})\s*([A-Za-z0-9_+-]*)\s*$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_UL_RE = re.compile(r"^\s*[-*+]\s+(.*)$")
_OL_RE = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_HR_RE = re.compile(r"^\s*([-*_])\s*(\1\s*){2,}$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")

# Language hint -> nothing. A CSS class would need a stylesheet we do not own,
# and the goal is legibility, not syntax colour.
_CODE_OPEN = "<pre><code>"
_CODE_CLOSE = "</code></pre>"


def render_markdown(source: str, max_len: int = 200_000) -> str:
    """Render markdown to HTML suitable for setHtml.

    The result is still expected to pass through sanitize_html; this function
    does not itself promise the output is safe to render, only that it is the
    right shape to sanitize.
    """
    text = str(source or "")
    if not text.strip():
        return ""
    if len(text) > max_len:
        text = text[:max_len] + "\n… (truncated)"

    out: List[str] = []
    lines = text.split("\n")
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # --- fenced code --------------------------------------------------
        m = _FENCE_RE.match(line)
        if m:
            marker, _lang = m.group(1), m.group(2)
            i += 1
            block: List[str] = []
            while i < n and not lines[i].strip().startswith(marker[0] * 3):
                block.append(lines[i])
                i += 1
            if i < n:
                i += 1                      # consume the closing fence
            # Escaped whole: a code block is never interpreted as markup.
            body = html.escape("\n".join(block), quote=False)
            out.append(_CODE_OPEN + body + _CODE_CLOSE)
            continue

        # --- blank --------------------------------------------------------
        if not line.strip():
            i += 1
            continue

        # --- horizontal rule ----------------------------------------------
        if _HR_RE.match(line):
            out.append("<hr>")
            i += 1
            continue

        # --- heading -------------------------------------------------------
        m = _HEADING_RE.match(line)
        if m:
            level = min(len(m.group(1)), 6)
            out.append(f"<h{level}>{render_inline(m.group(2))}</h{level}>")
            i += 1
            continue

        # --- blockquote -----------------------------------------------------
        if line.lstrip().startswith(">"):
            quoted: List[str] = []
            while i < n and lines[i].lstrip().startswith(">"):
                quoted.append(lines[i].lstrip()[1:].lstrip())
                i += 1
            inner = render_markdown("\n".join(quoted))
            out.append(f"<blockquote>{inner}</blockquote>")
            continue

        # --- table ----------------------------------------------------------
        if ("|" in line and i + 1 < n
                and _TABLE_SEP_RE.match(lines[i + 1])
                and "|" in lines[i + 1]):
            head = _split_row(line)
            i += 2
            rows: List[List[str]] = []
            while i < n and "|" in lines[i] and lines[i].strip():
                rows.append(_split_row(lines[i]))
                i += 1
            parts = ["<table><thead><tr>"]
            parts += [f"<th>{render_inline(c)}</th>" for c in head]
            parts.append("</tr></thead><tbody>")
            for r in rows:
                parts.append("<tr>")
                parts += [f"<td>{render_inline(c)}</td>" for c in r]
                parts.append("</tr>")
            parts.append("</tbody></table>")
            out.append("".join(parts))
            continue

        # --- lists -----------------------------------------------------------
        if _UL_RE.match(line) or _OL_RE.match(line):
            ordered = bool(_OL_RE.match(line))
            items: List[str] = []
            while i < n:
                cur = lines[i]
                m_ul = _UL_RE.match(cur)
                m_ol = _OL_RE.match(cur)
                if m_ul and not ordered:
                    items.append(f"<li>{render_inline(m_ul.group(1))}</li>")
                elif m_ol and ordered:
                    items.append(f"<li>{render_inline(m_ol.group(1))}</li>")
                else:
                    # Indented continuation lines belong to the item above.
                    if items and cur.startswith(("  ", "\t")) and cur.strip():
                        items[-1] = (items[-1].rsplit("</li>", 1)[0]
                                     + " " + render_inline(cur.strip())
                                     + "</li>")
                    else:
                        break
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>{''.join(items)}</{tag}>")
            continue

        # --- indented code ----------------------------------------------------
        if line.startswith("    ") and line.strip():
            block = []
            while i < n and (lines[i].startswith("    ") or not lines[i].strip()):
                if not lines[i].strip() and not any(
                        b.startswith("    ") for b in lines[i + 1:] or [""]):
                    break
                block.append(lines[i][4:] if lines[i].startswith("    ") else "")
                i += 1
            while block and not block[-1].strip():
                block.pop()
                i -= 1
            body = html.escape("\n".join(block), quote=False)
            out.append(_CODE_OPEN + body + _CODE_CLOSE)
            continue

        # --- paragraph --------------------------------------------------------
        para: List[str] = []
        while i < n and lines[i].strip():
            if (_HEADING_RE.match(lines[i]) or _FENCE_RE.match(lines[i])
                    or _HR_RE.match(lines[i])
                    or lines[i].lstrip().startswith(">")
                    or _UL_RE.match(lines[i]) or _OL_RE.match(lines[i])):
                break
            para.append(lines[i])
            i += 1
        if para:
            out.append("<p>" + render_inline("\n".join(para)) + "</p>")

    return "\n".join(out)


def _split_row(line: str) -> List[str]:
    """Split a pipe table row into trimmed cells."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def looks_like_markdown(source: str) -> bool:
    """Whether the text is worth running through the renderer.

    A cheap sniff, used only to decide whether to render or to show plain text.
    Deliberately conservative: a false negative just means plain text, while a
    false positive on a sentence with a stray asterisk would reflow it.
    """
    text = str(source or "")
    if not text.strip():
        return False
    if _FENCE_RE.search(text) or text.count("\n") and "```" in text:
        return True
    for line in text.split("\n"):
        if _HEADING_RE.match(line) or _HR_RE.match(line):
            return True
        if line.lstrip().startswith(("> ", "- ", "* ")) or _OL_RE.match(line):
            return True
    if "| " in text and _TABLE_SEP_RE.search(text):
        return True
    return False


def first_code_language(source: str) -> Optional[str]:
    """The language hint on the first fenced block, if any.

    Useful for choosing how to open a file or run a block, which is the thing a
    user actually wants from an assistant that just wrote them a file.
    """
    for line in str(source or "").split("\n"):
        m = _FENCE_RE.match(line)
        if m:
            return (m.group(2) or None)
    return None