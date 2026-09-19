"""Additive vault tests (temp values only, real config untouched)."""


def test_vault_roundtrip():
    from core.secret_vault import encrypt_value, decrypt_value
    e = encrypt_value("pytest-secret-12345")
    assert e.startswith("ENC(")
    assert decrypt_value(e) == "pytest-secret-12345"
    assert decrypt_value("plain") == "plain"
    assert decrypt_value("") == ""


def test_mask_never_leaks():
    from core.secret_vault import mask_secret
    m = mask_secret("AIzaSecretFullValue123")
    assert "SecretFull" not in m and len(m) < 15


def test_decrypt_dict():
    from core.secret_vault import decrypt_dict
    d = decrypt_dict({"gemini_api_key": "plain", "assistant_name": "maya",
                      "obsidian_config": {"api_key": "plain2"}})
    assert d["gemini_api_key"] == "plain" and d["assistant_name"] == "maya"
    assert d["obsidian_config"]["api_key"] == "plain2"


def test_load_decrypts_transparently():
    from memory.config_manager import load_api_keys
    d = load_api_keys()
    assert isinstance(d, dict)
    for v in d.values():
        assert not (isinstance(v, str) and v.startswith("ENC(")), "leaked blob to reader"
