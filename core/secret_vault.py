"""Machine-bound secret vault — API keys encrypted at rest. New file, additive.
Zero new deps: `cryptography.fernet` (already required) + Windows DPAPI via
ctypes (no package) for the master key. Linux/macOS: 0600 file.

- Disk: secrets stored as ENC(...) blobs in api_keys.json
- Memory: load_api_keys() transparently decrypts (all readers keep working)
- AI-privacy: keys never enter prompts/logs (use mask_secret); this agent only
  ever saw them because the file was plaintext — after migration, reads show blobs.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
_KEY_FILE = _BASE / "config" / ".machine.key"
_PREFIX = "ENC("

# Key names treated as secrets (substring match, lowercase).
_SECRET_HINTS = ("api_key", "apikey", "token", "secret", "password",
                 "private_key", "client_secret", "auth_key")


def _machine_protect(data: bytes) -> bytes:
    """DPAPI-protect master key on Windows; passthrough elsewhere (file perms guard)."""
    if os.name != "nt":
        return data
    try:
        import ctypes
        from ctypes import wintypes

        class _Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD),
                        ("pbData", ctypes.POINTER(ctypes.c_byte))]

        crypt = ctypes.windll.crypt32
        inp = _Blob(len(data), (ctypes.c_byte * len(data)).from_buffer_copy(data))
        out = _Blob()
        if crypt.CryptProtectData(ctypes.byref(inp), None, None, None, None, 0, ctypes.byref(out)):
            buf = bytes((ctypes.c_byte * out.cbData).from_address(ctypes.addressof(out.pbData.contents)))
            ctypes.windll.kernel32.LocalFree(out.pbData)
            return b"DPAPI:" + base64.b64encode(buf)
    except Exception:
        pass
    return data


def _machine_unprotect(data: bytes) -> bytes:
    if os.name != "nt":
        return data
    if not data.startswith(b"DPAPI:"):
        return data
    try:
        import ctypes
        from ctypes import wintypes

        class _Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD),
                        ("pbData", ctypes.POINTER(ctypes.c_byte))]

        raw = base64.b64decode(data[len(b"DPAPI:"):])
        inp = _Blob(len(raw), (ctypes.c_byte * len(raw)).from_buffer_copy(raw))
        out = _Blob()
        crypt = ctypes.windll.crypt32
        if crypt.CryptUnprotectData(ctypes.byref(inp), None, None, None, None, 0, ctypes.byref(out)):
            buf = bytes((ctypes.c_byte * out.cbData).from_address(ctypes.addressof(out.pbData.contents)))
            ctypes.windll.kernel32.LocalFree(out.pbData)
            return buf
    except Exception:
        pass
    return data


def _master_key() -> bytes | None:
    """Load-or-create Fernet key (44-char urlsafe base64 form Fernet wants).
    Never raises. FIX: no b64decode — stored key already IS base64."""
    try:
        if _KEY_FILE.exists():
            raw = _KEY_FILE.read_bytes().strip()
            if raw:
                key = _machine_unprotect(raw)
                if len(key) == 44:
                    return key
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        try:
            _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
            _KEY_FILE.write_bytes(_machine_protect(key))
            if os.name != "nt":
                os.chmod(_KEY_FILE, 0o600)
        except Exception:
            pass
        return key
    except Exception:
        return None


def is_secret_key(name: str) -> bool:
    n = (name or "").lower()
    return any(h in n for h in _SECRET_HINTS)


def encrypt_value(plain: str) -> str:
    """Plaintext -> ENC(...) (Fernet). Passthrough on any failure. Never raises."""
    try:
        p = str(plain or "")
        if not p or (p.startswith(_PREFIX) and p.endswith(")")):
            return plain
        from cryptography.fernet import Fernet
        key = _master_key()
        if not key:
            return plain
        return _PREFIX + Fernet(key).encrypt(p.encode()).decode() + ")"
    except Exception:
        return plain


def decrypt_value(stored: str):
    """ENC(...) -> plaintext; anything else passes through. Never raises."""
    try:
        s = stored if isinstance(stored, str) else stored
        if not isinstance(s, str) or not (s.startswith(_PREFIX) and s.endswith(")")):
            return stored
        from cryptography.fernet import Fernet
        key = _master_key()
        if not key:
            return stored
        return Fernet(key).decrypt(s[len(_PREFIX):-1].encode()).decode()
    except Exception:
        return stored


def decrypt_dict(d: dict) -> dict:
    """Decrypt secret values in a flat config dict (nested dicts preserved as-is,
    values inside decrypted recursively). Returns NEW dict. Never raises."""
    try:
        out: dict = {}
        for k, v in (d or {}).items():
            if isinstance(v, dict):
                out[k] = decrypt_dict(v)
            elif isinstance(v, str) and is_secret_key(str(k)):
                out[k] = decrypt_value(v)
            else:
                out[k] = v
        return out
    except Exception:
        return d if isinstance(d, dict) else {}


def mask_secret(s: str, keep: int = 4) -> str:
    """For logs: 'AIzaSy...Dr-U'. Never raises, never leaks."""
    try:
        t = str(s or "")
        if len(t) <= keep + 3:
            return "***"
        return f"{t[:keep]}...{t[-keep:]}"
    except Exception:
        return "***"
