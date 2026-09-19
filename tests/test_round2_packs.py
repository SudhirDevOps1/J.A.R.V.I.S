"""Additive shape tests for round-2 packs (no side effects, no network)."""


def test_new_action_shapes():
    import importlib
    for mod, tool in [("actions.text_expander", "text_expander"),
                      ("actions.deep_research", "deep_research"),
                      ("actions.shot_page", "shot_page")]:
        m = importlib.import_module(mod)
        assert isinstance(m.TOOL, dict)
        assert m.TOOL["name"] == tool
        assert callable(m.TOOL["handler"])


def test_new_plugin_shapes():
    import importlib
    for mod, tool in [("plugins.github_tool", "github_tool"),
                      ("plugins.slack_tool", "slack_tool")]:
        m = importlib.import_module(mod)
        assert isinstance(m.PLUGIN, dict)
        assert m.PLUGIN["name"] == tool
        assert callable(m.run)


def test_expander_validates():
    from actions.text_expander import text_expander
    out = text_expander({"action": "add", "trigger": "", "value": ""})
    assert "trigger" in out.lower()


def test_github_validates():
    from plugins.github_tool import run
    out = run({"action": "list_issues", "repo": "badformat"})
    assert "owner/repo" in out


def test_walker_branch_exists():
    from actions import window_tools as _w
    out = _w.window_tools({"action": "walker", "title": ""})
    assert isinstance(out, str) and len(out) > 0
