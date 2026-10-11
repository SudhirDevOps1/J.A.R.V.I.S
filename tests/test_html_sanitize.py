"""
tests/test_html_sanitize.py — Tests for the HTML sanitizer used by the content panel.

MainWindow._show_content fed web_search results, tool output and model text
straight into QLabel.setHtml. That is an injection sink: content fetched from a
search engine could render as markup rather than as text. These tests pin the
allowlist behaviour.

The bar is "inert and readable", not "stripped": a page that says
"use <div> for layout" should still show those characters, and a comparison
table should still render as a table.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from ui.html_sanitize import (  # noqa: E402
    ALLOWED_TAGS,
    looks_like_html,
    sanitize_html,
)


# ── script and friends must never survive ───────────────────────────────────

@pytest.mark.parametrize("payload", [
    "<script>alert(1)</script>",
    "<SCRIPT>alert(1)</SCRIPT>",
    "<script src='http://evil/x.js'></script>",
    "<iframe src='http://evil'></iframe>",
    "<object data='http://evil'></object>",
    "<embed src='http://evil'>",
    "<style>body{display:none}</style>",
    "<link rel=stylesheet href='http://evil/x.css'>",
    "<meta http-equiv=refresh content=0;url=http://evil>",
    "<base href='http://evil/'>",
    "<form action='http://evil'><input name=x></form>",
    "<svg onload=alert(1)>",
    "<math><mtext></mtext></math>",
])
def test_dangerous_tags_are_removed(payload):
    out = sanitize_html(payload)
    assert "<script" not in out.lower()
    assert "<iframe" not in out.lower()
    assert "<object" not in out.lower()
    assert "<embed" not in out.lower()
    assert "<style" not in out.lower()
    assert "<link" not in out.lower()
    assert "<meta" not in out.lower()
    assert "<base" not in out.lower()
    assert "<form" not in out.lower()
    assert "<input" not in out.lower()
    assert "<svg" not in out.lower()


def test_script_body_does_not_leak_as_text():
    """The CONTENT of a script tag is dropped too, not just the tags —
    otherwise '</scr' + 'ipt>alert(1)</scr' + 'ipt>' would reassemble."""
    out = sanitize_html("<script>alert('xss')</script>")
    assert "alert(" not in out


# ── event handlers must be stripped ─────────────────────────────────────────

@pytest.mark.parametrize("payload", [
    '<div onclick="alert(1)">x</div>',
    '<div ONCLICK="alert(1)">x</div>',
    '<p onmouseover=alert(1)>x</p>',
    '<a href="http://x" onclick="alert(1)">x</a>',
])
def test_event_handlers_are_stripped(payload):
    """An allowlisted tag must never keep an on* handler."""
    out = sanitize_html(payload).lower()
    assert "onclick" not in out
    assert "onmouseover" not in out


@pytest.mark.parametrize("payload", [
    '<img src=x onerror=alert(1)>',
    '<body onload=alert(1)>',
])
def test_handlers_on_disallowed_tags_are_inert(payload):
    """`img` and `body` are not allowlisted, so they become escaped text.

    That is safe AND readable — the user still sees what the source said — but
    the assertion has to be about inertness, not about the substring being
    absent, because escaped text legitimately contains "onload".
    """
    out = sanitize_html(payload).lower()
    assert "<img" not in out          # not live markup
    assert "<body" not in out
    assert "&lt;" in out              # survived as visible text
    assert "&gt;" in out


def test_no_live_tag_ever_carries_a_handler():
    """Whole-output check across several payloads.

    Scans for real tags — an unescaped '<name' — which is what Qt would parse,
    rather than for substrings, since escaped text mentions handlers
    legitimately.
    """
    payloads = [
        '<img src=x onerror=alert(1)>',
        '<body onload=alert(1)>',
        '<div onclick="alert(1)">x</div>',
        '<a href="http://x" onmouseover="alert(1)">x</a>',
        '<svg onload=alert(1)>',
    ]
    for p in payloads:
        out = sanitize_html(p)
        for _name, attrs in re.findall(
                r"<(?!/)([A-Za-z][A-Za-z0-9:-]*)([^>]*)>", out):
            assert not re.search(r"\bon[a-z]+\s*=", attrs, re.I), f"{p!r}"


# ── javascript: URLs must be dropped ────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
])
def test_dangerous_urls_are_dropped(url):
    out = sanitize_html(f'<a href="{url}">click</a>').lower()
    assert "javascript:" not in out
    assert "data:text/html" not in out
    assert "vbscript:" not in out


def test_safe_urls_survive():
    out = sanitize_html('<a href="https://example.com">x</a>')
    assert "https://example.com" in out
    assert "<a" in out


# ── legitimate formatting must survive ──────────────────────────────────────

def test_tables_survive():
    out = sanitize_html("<table><tr><th>A</th><td>1</td></tr></table>")
    assert "<table" in out and "<td" in out and "<th" in out


def test_formatting_survives():
    out = sanitize_html("<p><b>bold</b> and <i>italic</i></p>")
    assert "<b>" in out and "<i>" in out and "<p>" in out


def test_lists_survive():
    out = sanitize_html("<ul><li>one</li><li>two</li></ul>")
    assert "<ul" in out and "<li" in out


def test_safe_inline_style_survives():
    out = sanitize_html('<span style="color:#ff0000">red</span>')
    assert "color" in out
    assert "#ff0000" in out.lower() or "#FF0000" in out


def test_dangerous_css_is_dropped():
    out = sanitize_html('<div style="background:url(javascript:alert(1))">x</div>')
    assert "javascript:" not in out.lower()


def test_colspan_survives():
    out = sanitize_html('<table><tr><td colspan="3">x</td></tr></table>')
    assert "colspan" in out


# ── unknown tags become readable text, not markup ───────────────────────────

def test_unknown_tag_is_escaped_not_executed():
    out = sanitize_html("<blink>hello</blink>")
    assert "<blink>" not in out
    assert "&lt;blink&gt;" in out
    assert "hello" in out


def test_angle_brackets_in_plain_text_are_preserved_readably():
    """A comparison or code sample mentioning tags must stay legible.

    Tags outside the allowlist are escaped rather than stripped, so the user
    still reads what the source actually said.
    """
    out = sanitize_html("use <custom-element> and <blink> for old browsers")
    assert "&lt;custom-element&gt;" in out
    assert "&lt;blink&gt;" in out
    assert "<custom-element>" not in out
    assert "<blink>" not in out


def test_lone_angle_bracket_does_not_eat_the_rest():
    """A stray '<' with no tag after it must stay a character, not swallow the
    remainder of the sentence as a malformed tag."""
    out = sanitize_html("5 < 7 and 9 > 2")
    assert "5" in out and "7" in out and "9" in out
    assert "&lt;" in out and "&gt;" in out


def test_plain_text_passes_through_escaped():
    out = sanitize_html("plain answer with & ampersand")
    assert out == "plain answer with &amp; ampersand"


# ── structure preservation ──────────────────────────────────────────────────

def test_nesting_is_preserved():
    out = sanitize_html("<div><p>a</p><p>b</p></div>")
    assert out.count("<p>") == 2
    assert out.count("</p>") == 2


def test_malformed_html_does_not_crash():
    for bad in ("<div", "<<>>", "<p", "</p>", "<<<>>>", "<div <span>"):
        sanitize_html(bad)          # must not raise


def test_none_and_empty_are_safe():
    assert sanitize_html(None) == ""
    assert sanitize_html("") == ""


# ── truncation ──────────────────────────────────────────────────────────────

def test_overlong_input_is_truncated_with_a_marker():
    out = sanitize_html("a" * 300_000, max_len=1000)
    assert len(out) < 5000
    assert "truncated" in out.lower()


# ── looks_like_html ─────────────────────────────────────────────────────────

def test_detects_real_markup():
    assert looks_like_html("<table><tr><td>x</td></tr></table>") is True
    assert looks_like_html("<p>hi</p>") is True


def test_plain_text_is_not_html():
    assert looks_like_html("just a normal sentence") is False


def test_empty_is_not_html():
    assert looks_like_html("") is False
    assert looks_like_html(None) is False


def test_unknown_tags_do_not_count_as_html():
    """So a sentence mentioning <blink> renders as text rather than being
    mangled by the HTML renderer."""
    assert looks_like_html("use <blink> for old browsers") is False


def test_allowed_tag_set_is_nonempty():
    """Guards against an accidental edit emptying the allowlist, which would
    silently escape everything and break the price-comparison cards."""
    assert len(ALLOWED_TAGS) > 10
    assert "table" in ALLOWED_TAGS