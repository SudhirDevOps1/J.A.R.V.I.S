r"""
tests/test_delete_routing.py - "delete karo" has to reach file_controller.

(Raw docstring: it quotes a real Windows path, C:\Users\..., which Python would
otherwise read as a truncated \U escape.)

WHAT WAS OBSERVED
-----------------
Real session, verbatim:

    You: use delete kro to muna.txt ko
    maya: Oof, wait, pehle mujhe ye बताओ कि तुम्हें Notepad बंद करना है या
          फिर munna.txt file को delete करना है? ...clarify कर दो please

    You: fle delete kro jo hain
    maya: Pyaar, context clear nahi ho raha hai ... Please, जल्दी से bata do

    You: ha
    maya: Munna.txt delete करना है na? Okay main abhi delete कर देती हूँ
          [file] delete C:\Users\sudhi\Desktop\munna.txt

Three turns of clarification for a request that was unambiguous, and the file
name was in the conversation the whole time.

THE GAP
-------
file_controller has had a `delete` action for as long as it has had `write`.
Nothing in the router dispatched to it. "xyz dhoondh ke delete karo" worked
because hunt_delete had a pattern; the ordinary case had none.

Both word orders are covered, because Hindi puts the object first as often as
not. And "the file" - a bare pronoun with no name in it - is resolved from the
conversation's own last_file rather than sent to a cloud model that will only
ask the same question again.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


@pytest.fixture()
def dispatcher():
    from core import reflex_policy
    reflex_policy.set_enabled(False)
    from core.edge_router import get_tri_tier_dispatcher
    return get_tri_tier_dispatcher()


@pytest.fixture(autouse=True)
def clean_context():
    """These cases depend on the conversation buffer, so each starts empty."""
    import core.context_buffer as cb
    buf = cb.get_context_buffer()
    buf.reset()
    yield
    buf.reset()


def _tool(dispatcher, prompt):
    decision = dispatcher.route(prompt)
    return decision.get("tool")


def _name(dispatcher, prompt):
    tool = _tool(dispatcher, prompt)
    return tool[1].get("name") if tool else None


# ── both word orders ────────────────────────────────────────────────────────

@pytest.mark.parametrize("prompt,expected", [
    ("delete kro munna.txt", "munna.txt"),
    ("munna.txt delete karo", "munna.txt"),
    ("use delete kro to muna.txt ko", "muna.txt"),
    ("remove file report.pdf", "report.pdf"),
    ("hatado notes.txt", "notes.txt"),
    ("mitado old.log", "old.log"),
])
def test_a_named_file_delete_reaches_the_tool(dispatcher, prompt, expected):
    """These three phrasings are straight from the session transcript."""
    tool = _tool(dispatcher, prompt)
    assert tool is not None, f"{prompt!r} fell through to the cloud"
    assert tool[0] == "file_controller"
    assert tool[1]["action"] == "delete"
    assert tool[1].get("name") == expected, (
        f"{prompt!r} resolved to {tool[1].get('name')!r}, expected {expected!r}"
    )


def test_a_bare_pronoun_resolves_to_the_last_file_touched(dispatcher):
    """"fle delete kro jo hain" names nothing, but the conversation does."""
    import core.context_buffer as cb

    cb.get_context_buffer().update(
        query="munna.txt", response="Written to: munna.txt",
        tool="file_controller", args={"path": "munna.txt"},
    )
    tool = _tool(dispatcher, "fle delete kro jo hain")
    assert tool is not None, (
        "a pronoun with a known referent was sent to the cloud instead"
    )
    assert tool[1]["action"] == "delete"
    assert "munna.txt" in (tool[1].get("name") or tool[1].get("path") or "")


@pytest.mark.parametrize("prompt", [
    "usi ko delete kar do",
    "delete kro jo file hai",
    "jo file hai use delete karo",
])
def test_pronoun_forms_all_resolve(dispatcher, prompt):
    import core.context_buffer as cb

    cb.get_context_buffer().update(
        query="munna.txt", response="Written to: munna.txt",
        tool="file_controller", args={"path": "munna.txt"},
    )
    tool = _tool(dispatcher, prompt)
    assert tool is not None and tool[1]["action"] == "delete", (
        f"{prompt!r} did not resolve to a delete"
    )


def test_nothing_is_deleted_when_there_is_nothing_to_delete(dispatcher):
    """With an empty buffer and no filename there is no referent, so it must not
    invent one. Falling through to a clarifying question is correct here."""
    assert _tool(dispatcher, "fle delete kro jo hain") is None


# ── what must not regress ───────────────────────────────────────────────────

def test_find_and_delete_still_uses_hunt_delete(dispatcher):
    """A different action with a different confirmation gate. Routing plain
    deletes must not swallow the confirm-gated one."""
    tool = _tool(dispatcher, "xyz dhoondh ke delete karo")
    assert tool is not None
    assert tool[0] == "file_controller"
    assert tool[1]["action"] == "hunt_delete"


def test_delete_without_a_filename_is_not_treated_as_a_path(dispatcher):
    """"delete kro" alone must not become a delete of "." or the home folder."""
    tool = _tool(dispatcher, "delete karo")
    if tool is not None and tool[1].get("action") == "delete":
        target = str(tool[1].get("path") or "").strip()
        assert target not in (".", "..", "/", "~"), (
            f"an empty delete became a delete of {target!r}"
        )


def test_unrelated_delete_words_are_not_hijacked(dispatcher):
    """The pattern is verb-led, so prose containing a noun must be safe."""
    for prompt in ("delete button ka colour kya hai",
                   "mujhe ek delete key chahiye keyboard me"):
        tool = _tool(dispatcher, prompt)
        if tool is not None:
            assert tool[1].get("action") != "delete" or \
                "." in str(tool[1].get("name") or ""), (
                f"{prompt!r} was turned into a delete: {tool!r}"
                )


def test_close_app_still_routes_to_open_app(dispatcher):
    """'band karo' means close an app. A delete rule must not swallow it."""
    for prompt in ("notepad band karo", "chrome band kar do"):
        tool = _tool(dispatcher, prompt)
        assert tool is not None and tool[0] == "open_app", (
            f"{prompt!r} was hijacked: {tool!r}"
        )