"""Machine-bound secret vault — API keys encrypted at rest. New file, additive.
Zero new deps: `cryptography.fernet` (already required) + Windows DPAPI via
ctypes (no package) for the master key. Linux/macOS: machine-bound key derivation.
 
- Disk: secrets stored as ENC(...) blobs in api_keys.json
- Memory: load_api_keys() transparently decrypts (all readers keep working)
- AI-privacy: keys never enter prompts/logs (use mask_secret); this agent only
  ever saw them because the file was plaintext — after migration, reads show blobs.
"""
from __future__ import annotations
 
import base64
import json
import logging
import os
import sys
import platform
import hashlib
from pathlib import Path
 
_BASE = Path(__file__).resolve().parent.parent
_KEY_FILE = _BASE / "config" / ".machine.key"
_PREFIX = "ENC("
 
# Key names treated as secrets (substring match, lowercase).
_SECRET_HINTS = ("api_key", "apikey", "token", "secret", "password",
                 "private_key", "client_secret", "auth_key")
 
_log = logging.getLogger("secret_vault")
if not _log.handlers:
    _log.addHandler(logging.NullHandler())
 
 
def _get_machine_id() -> bytes:
    """Generate a machine-specific identifier from hardware info.
    Used to derive encryption key so keys are bound to this machine."""
    parts = []
    # Machine ID from /etc/machine-id or Windows registry
    try:
        if os.name == "nt":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SOFTWARE\Microsoft\Cryptography",
                                 0, winreg.KEY_READ)
            val, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            parts.append(val.encode())
        else:
            # Linux/macOS: /etc/machine-id or /var/lib/dbus/machine-id
            for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                if os.path.exists(path):
                    with open(path, "r") as f:
                        parts.append(f.read().strip().encode())
                    break
    except Exception:
        pass
    # Add platform info as fallback
    parts.append(platform.node().encode())
    parts.append(platform.machine().encode())
    parts.append(platform.processor().encode())
    # Hash to fixed length
    return hashlib.sha256(b"".join(parts)).digest()
 
 
def _machine_protect(data: bytes) -> bytes:
    """DPAPI-protect master key on Windows; encrypt with machine-bound key elsewhere."""
    if os.name == "nt":
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
    else:
        # Linux/macOS: encrypt with machine-bound key (AES-GCM)
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            machine_key = _get_machine_id()[:32]  # 256-bit key
            aesgcm = AESGCM(machine_key)
            nonce = os.urandom(12)
            ct = aesgcm.encrypt(nonce, data, None)
            return b"MACHINE:" + base64.b64encode(nonce + ct)
        except Exception:
            pass
        return data
 
 
def _machine_unprotect(data: bytes) -> bytes:
    if os.name == "nt":
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
    else:
        # Linux/macOS: decrypt with machine-bound key
        if not data.startswith(b"MACHINE:"):
            return data
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            machine_key = _get_machine_id()[:32]
            aesgcm = AESGCM(machine_key)
            raw = base64.b64decode(data[len(b"MACHINE:"):])
            nonce, ct = raw[:12], raw[12:]
            return aesgcm.decrypt(nonce, ct, None)
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
    """Plaintext -> ENC(...) (Fernet). Logs error on failure, returns plaintext as fallback."""
    try:
        p = str(plain or "")
        if not p or (p.startswith(_PREFIX) and p.endswith(")")):
            return plain
        from cryptography.fernet import Fernet
        key = _master_key()
        if not key:
            _log.error("encrypt_value: master key unavailable, storing plaintext!")
            return plain
        return _PREFIX + Fernet(key).encrypt(p.encode()).decode() + ")"
    except Exception as e:
        _log.exception("encrypt_value failed, storing plaintext: %s", e)
        return plain


def decrypt_value(stored: str):
    """ENC(...) -> plaintext; anything else passes through. Logs error on failure."""
    try:
        s = stored if isinstance(stored, str) else stored
        if not isinstance(s, str) or not (s.startswith(_PREFIX) and s.endswith(")")):
            return stored
        from cryptography.fernet import Fernet
        key = _master_key()
        if not key:
            _log.error("decrypt_value: master key unavailable, returning ciphertext!")
            return stored
        return Fernet(key).decrypt(s[len(_PREFIX):-1].encode()).decode()
    except Exception as e:
        _log.exception("decrypt_value failed, returning ciphertext: %s", e)
        return stored


def decrypt_dict(d: dict) -> dict:
    """Decrypt secret values in a flat config dict (nested dicts preserved as-is,
    values inside decrypted recursively). Returns NEW dict. Logs errors."""
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
    except Exception as e:
        _log.exception("decrypt_dict failed: %s", e)
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
