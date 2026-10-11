"""
ui/html_sanitize.py — Allowlist sanitizer for text shown with setHtml().

WHY THIS EXISTS
---------------
MainWindow._show_content decides between setPlainText and setHtml by sniffing
for a handful of tags, then passes the string straight to setHtml with no
escaping. That text is not authored by us: it is web_search results, tool
output, deep-research output and model text. Feeding untrusted content to
setHtml is an HTML/script injection sink — a search result containing markup
renders as markup, and anything more hostile can execute.

The rule applied here: our own UI generates its markup, everything else is
text. So only a small, explicitly allowed subset survives, and anything that
looks like a tag we did not permit is escaped rather than dropped. Escaping
rather than stripping keeps the content readable ("use <custom-tag> here")
while making it inert.

WHAT SURVIVES
--------------
  structural : <p> <br> <hr> <ul> <ol> <li> <b> <i> <em> <strong> <code>
               <pre> <blockquote> <h1>-<h6> <span> <div> <a> <table> ...
  attributes : only href (http/https/mailto/#), colspan/rowspan, class, align
  styling    : inline colour/spacing only, and only when the value itself is
               inert (no url(), no expression(), no javascript:)

Everything else — <script>, <style>, <iframe>, <object>, <embed>, every on*
handler, every javascript: URL, every unknown tag — is escaped or dropped.

WHY HTMLParser AND NOT A REGEX
------------------------------
A regex for HTML tags has to guess where an attribute value ends, and every
guess is a hole: `<a href="a>b">` ends early, `</scr` + `ipt>` reassembles, an
attribute containing `<` truncates the tag and leaks the rest as live markup.
The first version of this module was regex-based and all four of those were
observed failing. html.parser is a real tokenizer with a documented
CDATA mode for script/style, so malformed input becomes text instead of markup.

This module imports nothing from PyQt, so it is tested without a display.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import List, Set

# Tags that may pass through. Anything not listed is escaped.
ALLOWED_TAGS: Set[str] = {
    "p", "br", "hr", "div", "span", "b", "i", "em", "strong", "u", "s",
    "code", "pre", "blockquote", "ul", "ol", "li", "dl", "dt", "dd",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption",
    "a", "sub", "sup", "small", "mark", "abbr",
}

# Tags removed together with everything between the open and close.
_DROP_CONTENT_TAGS: Set[str] = {
    "script", "style", "iframe", "object", "embed", "applet",
    "template", "noscript", "svg", "math", "form",
    "textarea", "select", "option", "button",
}

# Void elements: no closing tag, so they must not open a skip region.
_VOID_TAGS: Set[str] = {
    "br", "hr", "img", "input", "link", "meta", "base", "area",
    "col", "source", "track", "wbr", "embed", "param",
}

# Attributes permitted on any allowed tag.
_ALLOWED_ATTRS: Set[str] = {"class", "colspan", "rowspan", "align", "title"}

# Attributes permitted only on <a>.
_LINK_ATTRS: Set[str] = {"href", "target", "rel"}

# CSS properties permitted in a style attribute.
_ALLOWED_CSS = re.compile(
    r"^(?:color|background(?:-color)?|font-(?:weight|style|size)|text-align"
    r"|text-decoration|padding|margin|border(?:-\w+)?|width|height)$",
    re.I,
)

# A CSS value is only safe if it cannot reference an external resource or run
# code. `url(...)`, `expression(...)` and `image-set(...)` all can.
_CSS_VALUE_SAFE = re.compile(r"^(?:[^()]*|[0-9a-z#%.,\-_ ]*)$", re.I)

_SAFE_URL = re.compile(r"^(?:https?://|mailto:|#)", re.I)

# Used only for the cheap has-markup sniff in looks_like_html(); sanitization
# itself is done by the parser, never by this.
_TAG_SCAN = re.compile(r"<\s*/?\s*([A-Za-z][A-Za-z0-9:-]*)")


def _escape(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def _clean_style(value: str) -> str:
    """Keep only inert, allowlisted declarations."""
    kept: List[str] = []
    for decl in (value or "").split(";"):
        if ":" not in decl:
            continue
        prop, _, val = decl.partition(":")
        prop = prop.strip().lower()
        val = val.strip()
        if not _ALLOWED_CSS.match(prop):
            continue
        if not val or not _CSS_VALUE_SAFE.match(val):
            continue        # url(...) / expression(...) / anything computed
        kept.append(f"{prop}:{val}")
    return ";".join(kept)


class _Sanitizer(HTMLParser):
    """Rewrites a token stream against the allowlist.

    Unknown tags are emitted as escaped text rather than dropped, so the user
    still sees what the source said instead of silently losing a sentence.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: List[str] = []
        self.saw_allowed_tag = False
        self._skip: List[str] = []      # stack of drop-set tags being skipped

    # ── helpers ─────────────────────────────────────────────────────────────

    @property
    def _skipping(self) -> bool:
        return bool(self._skip)

    def _attrs_for(self, tag: str, attrs) -> str:
        rendered: List[str] = []
        has_href = False
        for raw_name, value in attrs:
            name = (raw_name or "").lower()
            val = value or ""

            if name.startswith("on"):
                continue                    # every event handler
            if name in ("srcdoc", "formaction", "background",
                        "dynsrc", "lowsrc", "src", "srcset", "ping"):
                continue                    # resource loaders

            if name == "style":
                css = _clean_style(val)
                if css:
                    rendered.append(f'style="{_escape(css)}"')
                continue

            if name in _LINK_ATTRS and tag == "a":
                if name == "href":
                    if not _SAFE_URL.match(val.strip()):
                        continue            # javascript:, data:, vbscript:
                    has_href = True
                    rendered.append(f'href="{_escape(val.strip())}"')
                # target and rel are re-derived below, never taken from input
                continue

            if name in _ALLOWED_ATTRS:
                rendered.append(f'{name}="{_escape(val)}"')

        if tag == "a" and has_href:
            # Opening a link in the assistant's own view would hand navigation
            # to whatever page a tool returned, so force a new context.
            rendered.append('target="_blank"')
            rendered.append('rel="noopener noreferrer"')

        return (" " + " ".join(rendered)) if rendered else ""

    # ── parser callbacks ─────────────────────────────────────────────────────

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if self._skipping:
            # Still track nesting so the matching close does not end the skip.
            if tag in _DROP_CONTENT_TAGS and tag not in _VOID_TAGS:
                self._skip.append(tag)
            return

        if tag in _DROP_CONTENT_TAGS:
            if tag not in _VOID_TAGS:
                self._skip.append(tag)
            return                        # void ones just vanish

        if tag not in ALLOWED_TAGS:
            self.out.append(_escape(self.get_starttag_text() or f"<{tag}>"))
            return

        self.saw_allowed_tag = True
        close = " /" if tag in _VOID_TAGS else ""
        self.out.append(f"<{tag}{self._attrs_for(tag, attrs)}{close}>")

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if self._skipping:
            return
        if tag in _DROP_CONTENT_TAGS:
            return
        if tag not in ALLOWED_TAGS:
            self.out.append(_escape(self.get_starttag_text() or f"<{tag}/>"))
            return
        self.saw_allowed_tag = True
        self.out.append(f"<{tag}{self._attrs_for(tag, attrs)} />")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self._skipping:
            if self._skip and self._skip[-1] == tag:
                self._skip.pop()
            elif tag in self._skip:
                # Mismatched close: unwind to the nearest matching open.
                while self._skip and self._skip.pop() != tag:
                    pass
            return

        if tag in _DROP_CONTENT_TAGS or tag in _VOID_TAGS:
            return                        # nothing was emitted to close
        if tag not in ALLOWED_TAGS:
            self.out.append(_escape(f"</{tag}>"))
            return
        self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if self._skipping:
            return
        self.out.append(_escape(data or ""))

    # Comments, doctypes, processing instructions and unknown declarations
    # carry no content for the user and are a known parser-confusion vector.
    def handle_comment(self, data):
        return

    def handle_decl(self, decl):
        return

    def handle_pi(self, data):
        return

    def unknown_decl(self, data):
        return


def sanitize_html(raw: str, max_len: int = 200_000) -> str:
    """Return HTML safe to hand to QTextEdit.setHtml.

    Truncates to `max_len` characters first, since the content panel silently
    clipped at 4,000 before and anything longer was lost without warning.
    """
    text = str(raw or "")
    if len(text) > max_len:
        text = text[:max_len] + "\n… (truncated)"

    parser = _Sanitizer()
    try:
        parser.feed(text)
        parser.close()
    except Exception:
        # A tokenizer failure must not lose the content. Escape everything and
        # show it as plain text, which is always safe.
        return _escape(text)
    return "".join(parser.out)


def looks_like_html(raw: str) -> bool:
    """Whether the text contains real markup worth rendering as HTML.

    Replaces the old `any(tag in text for tag in ("<table", "<div", ...))` sniff,
    which produced two bugs: a plain sentence mentioning "<p" was rendered as
    broken markup, and markup without one of those six exact tags was shown as
    literal angle brackets.

    Only allowlisted tags count. A sentence that mentions <blink> should be
    shown as text, not handed to the HTML renderer.
    """
    for m in _TAG_SCAN.finditer(str(raw or "")):
        if m.group(1).lower() in ALLOWED_TAGS:
            return True
    return False