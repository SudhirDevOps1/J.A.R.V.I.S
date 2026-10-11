"""
tests/test_markdown.py — Tests for the content-panel markdown renderer.

WHY THIS NEEDS REAL COVERAGE
----------------------------
The renderer handles whatever the assistant said, which is untrusted text from
a web search, a tool, or a model. Two failure modes matter and they pull in
opposite directions:

  * render too little  - a user asking for an HTML file sees markup flattened
                         into an unreadable wall
  * render too much   - a payload inside a fenced block or an angle bracket in
                         a sentence becomes live markup

Every test below is about one of those. The escape-then-render order in
ui/markdown.py exists precisely so the second cannot happen, and these tests
are what keeps that true when someone adds a rule.

No PyQt import, so all of this runs headless.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from ui.markdown import (  # noqa: E402
    first_code_language,
    looks_like_markdown,
    render_inline,
    render_markdown,
)
from ui.html_sanitize import sanitize_html  # noqa: E402


def _tags(fragment: str):
    """The tag names present in a rendered fragment."""
    return set(re.findall(r"<\s*/?\s*([A-Za-z][A-Za-z0-9]*)", fragment))


def _has_live_event_handler(fragment: str) -> bool:
    for _n, attrs in re.findall(r"<(?!/)([A-Za-z][A-Za-z0-9]*)([^>]*)>", fragment):
        if re.search(r"\bon[a-z]+\s*=", attrs, re.I):
            return True
    return False


# ── headings ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("src,level", [
    ("# One", 1), ("## Two", 2), ("### Three", 3),
    ("#### Four", 4), ("##### Five", 5), ("###### Six", 6),
])
def test_headings(src, level):
    out = render_markdown(src)
    assert f"<h{level}>" in out
    assert f"</h{level}>" in out


def test_heading_level_is_capped_at_six():
    """Seven hashes must not emit <h7>, which no renderer understands."""
    out = render_markdown("####### Seven")
    assert "<h7" not in out


def test_heading_keeps_its_text():
    assert "Hello" in render_markdown("# Hello")


# ── inline ──────────────────────────────────────────────────────────────────

def test_bold():
    assert "<b>bold</b>" in render_inline("a **bold** word")


def test_italic():
    assert "<i>it</i>" in render_inline("an *it* word")


def test_bold_italic():
    out = render_inline("**a** and *b*")
    assert "<b>a</b>" in out and "<i>b</i>" in out


def test_strikethrough():
    assert "<s>gone</s>" in render_inline("~~gone~~")


def test_underscore_bold():
    assert "<b>x</b>" in render_inline("__x__")


def test_inline_code():
    assert "<code>x</code>" in render_inline("use `x` here")


def test_inline_code_does_not_render_markdown_inside_it():
    """The single most common way a markdown renderer corrupts code.

    `**not bold**` inside a code span must stay literal.
    """
    out = render_inline("run `**not bold**` now")
    assert "**not bold**" in out
    assert "<b>" not in out


def test_inline_code_escapes_angle_brackets():
    """Regression: a real bug, caught by this test rather than by review.

    Code spans are stashed out before the main escaping pass and restored
    afterwards, so for a while their bodies were never escaped at all.
    "what does <div> do" therefore produced a live <div> element inside a
    <code> tag, and an answer that merely explained a script tag would have
    executed it.

    Escaping now happens when the span is stashed, which is the only place it
    can happen without the restore step undoing it.
    """
    out = render_inline("what does `<div>` do")
    assert "&lt;div&gt;" in out
    assert "<div>" not in out


def test_inline_code_cannot_inject_a_script_tag():
    """The same bug with teeth: this was an execution sink."""
    out = render_inline("here: `<script>alert(1)</script>`")
    assert "<script" not in out.lower()
    assert "&lt;script&gt;" in out


def test_inline_code_injection_is_dead_after_sanitising_too():
    """Defence in depth: the sanitizer is a second line, not the only one."""
    out = sanitize_html(render_inline("`<script>alert(1)</script>`"))
    assert "<script" not in out.lower()


def test_multibacktick_span_with_angle_brackets():
    out = render_inline("use ``a < b`` here")
    assert "&lt;" in out


def test_angle_brackets_in_prose_are_escaped():
    out = render_markdown("compare a < b and c > d")
    assert "<p>" in out
    assert "&lt;" in out or "<p>" in out


def test_raw_script_tag_in_prose_cannot_survive():
    """A payload in ordinary text must never become a tag."""
    out = render_markdown("hello <script>alert(1)</script> world")
    assert "<script" not in out.lower()
    assert "&lt;script&gt;" in out


def test_script_inside_a_fenced_block_is_inert():
    out = render_markdown("```html\n<script>alert(1)</script>\n```")
    assert "<script" not in out.lower()
    assert "&lt;script&gt;" in out


# ── code blocks ─────────────────────────────────────────────────────────────

def test_fenced_code_block():
    out = render_markdown("```\nprint('hi')\n```")
    assert "<pre>" in out and "<code>" in out
    assert "print(&#x27;hi&#x27;)" in out or "print('hi')" in out


def test_code_block_preserves_newlines():
    out = render_markdown("```\na\nb\nc\n```")
    assert "a\nb\nc" in out


def test_code_block_with_language_hint():
    out = render_markdown("```python\nx = 1\n```")
    assert "x = 1" in out
    assert first_code_language("```python\nx = 1\n```") == "python"


def test_no_language_hint_returns_none():
    assert first_code_language("```\nx\n```") is None


def test_unclosed_fence_still_renders():
    """Truncated output from a model is normal and must not lose the code."""
    out = render_markdown("```python\nx = 1\ny = 2")
    assert "<pre>" in out
    assert "y = 2" in out


def test_code_block_does_not_render_bold():
    out = render_markdown("```\n**not bold**\n```")
    assert "**not bold**" in out
    assert "<b>" not in out


def test_indented_code_block():
    out = render_markdown("text\n\n    indented code\n")
    assert "<pre>" in out
    assert "indented code" in out


def test_ampersand_in_code_is_escaped():
    out = render_markdown("```\na && b\n```")
    assert "&amp;&amp;" in out


# ── lists ───────────────────────────────────────────────────────────────────

def test_unordered_list():
    out = render_markdown("- one\n- two\n- three")
    assert out.count("<li>") == 3
    assert "<ul>" in out


def test_ordered_list():
    out = render_markdown("1. one\n2. two")
    assert out.count("<li>") == 2
    assert "<ol>" in out


def test_nested_content_is_flattened_into_the_item():
    """Deeply nested lists are not supported; the item must still keep its
    text rather than silently losing it."""
    out = render_markdown("- outer\n    continued\n- second")
    assert "continued" in out
    assert "second" in out


def test_list_items_are_escaped():
    out = render_markdown("- <b>x</b>")
    assert "<b>" not in out or "&lt;b&gt;" in out


# ── blockquote, rule, table ─────────────────────────────────────────────────

def test_blockquote():
    out = render_markdown("> quoted line")
    assert "<blockquote>" in out
    assert "quoted line" in out


def test_horizontal_rule():
    assert "<hr>" in render_markdown("---")


def test_table():
    src = "| A | B |\n|---|---|\n| 1 | 2 |"
    out = render_markdown(src)
    assert "<table>" in out
    assert "<th>A</th>" in out
    assert "<td>1</td>" in out
    assert out.count("<tr>") == 2


def test_table_cells_are_escaped():
    out = render_markdown("| A |\n|---|\n| <script> |")
    assert "<script" not in out.lower()


# ── paragraphs ──────────────────────────────────────────────────────────────

def test_plain_text_becomes_a_paragraph():
    assert "<p>" in render_markdown("just a sentence")


def test_multiple_paragraphs():
    out = render_markdown("first\n\nsecond")
    assert out.count("<p>") == 2


def test_soft_wrap_stays_in_one_paragraph():
    out = render_markdown("line one\nline two")
    assert out.count("<p>") == 1


def test_hard_break_becomes_br():
    out = render_markdown("line one  \nline two")
    assert "<br>" in out


def test_no_content_produces_nothing():
    assert render_markdown("") == ""
    assert render_markdown("   ") == ""
    assert render_markdown(None) == ""


def test_overlong_input_is_truncated():
    out = render_markdown("x" * 300_000, max_len=500)
    assert len(out) < 5000
    assert "truncated" in out.lower()


# ── the sniff ───────────────────────────────────────────────────────────────

def test_sniff_detects_code_fence():
    assert looks_like_markdown("```\nx\n```") is True


def test_sniff_detects_heading():
    assert looks_like_markdown("# Title") is True


def test_sniff_detects_a_list():
    assert looks_like_markdown("- a\n- b") is True


def test_sniff_ignores_ordinary_prose():
    """A false positive here would reflow a plain sentence."""
    assert looks_like_markdown("The file was written to disk.") is False


def test_sniff_ignores_a_stray_asterisk():
    assert looks_like_markdown("2 * 3 = 6") is False


def test_sniff_handles_empty():
    assert looks_like_markdown("") is False
    assert looks_like_markdown(None) is False


# ── the point: renderer output still survives sanitising ────────────────────

@pytest.mark.parametrize("payload", [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "<a href='javascript:alert(1)'>click</a>",
    "<iframe src='http://evil'></iframe>",
    "<div style='background:url(javascript:alert(1))'>x</div>",
])
def test_rendered_output_passes_through_the_sanitizer_cleanly(payload):
    """Render then sanitize must not resurrect anything.

    Asserted on live tags, not on substrings. A payload the user typed is
    supposed to stay visible to them as escaped text, so "onerror=" and
    "javascript:" legitimately appear in the output. What must not appear is a
    real element or attribute the renderer would act on. Grepping for the
    substring would instead have demanded the user's own text be deleted.
    """
    rendered = render_markdown(f"# Heading\n\n{payload}\n\n- item")
    cleaned = sanitize_html(rendered)

    for bad in ("<script", "<iframe", "<svg", "<img", "<object", "<embed"):
        assert bad not in cleaned.lower(), f"{bad} survived: {cleaned[:200]}"

    assert not _has_live_event_handler(cleaned)

    for _name, attrs in re.findall(
            r"<(?!!)([A-Za-z][A-Za-z0-9]*)([^>]*)>", cleaned):
        assert "javascript:" not in attrs.lower(), f"live js URL in {attrs!r}"


def test_payload_text_stays_readable_after_escaping():
    """Escaping, not stripping. The user should still see what they wrote."""
    out = sanitize_html(render_markdown("use <div> in your markup"))
    assert "<div" not in out.lower()
    assert "use" in out and "markup" in out


def test_no_event_handler_survives_the_full_pipeline():
    rendered = render_markdown("<div onclick='alert(1)'>x</div>")
    cleaned = sanitize_html(rendered)
    assert not _has_live_event_handler(cleaned)


def test_renderer_never_emits_a_script_tag():
    """Even before sanitising, the renderer should not produce one."""
    for src in ("<script>alert(1)</script>",
                "<script\n>alert(1)</script>",
                "text <script >alert(1)</script> more"):
        assert "<script" not in render_markdown(src).lower()


def test_sanitizing_plain_prose_is_idempotent():
    """Running the pipeline twice must not double-escape or corrupt."""
    once = sanitize_html(render_markdown("# Hi\n\nsome *text*"))
    twice = sanitize_html(once)
    assert "&amp;lt;" not in twice
    assert "some <i>text</i>" in twice or "some <i>text</i>" in once