"""Optional current-user Windows DPAPI storage. Never print credential values."""

from __future__ import annotations

import ctypes
import getpass
import json
import os
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRET_PATH = ROOT / ".credentials.bin"
KEYS = ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_PASSWORD")


class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(payload: bytes, *, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise SystemExit("Encrypted local credentials require Windows. Use injected environment credentials elsewhere.")
    buffer = ctypes.create_string_buffer(payload)
    source = Blob(len(payload), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    fn = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    fn.argtypes = [
        ctypes.POINTER(Blob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(Blob),
    ]
    fn.restype = wintypes.BOOL
    # UI_FORBIDDEN; never use LOCAL_MACHINE: encrypted data is scoped to this Windows user.
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise SystemExit("Windows credential encryption/decryption failed; no plaintext fallback")
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        if output.data:
            ctypes.memset(output.data, 0, output.size)
            kernel32.LocalFree(output.data)
        ctypes.memset(buffer, 0, len(payload))


def load_secrets(path: Path = SECRET_PATH) -> dict[str, str]:
    values = {key: os.environ.get(key, "") for key in KEYS}
    if not all(values.values()) and path.exists():
        try:
            saved = json.loads(_crypt(path.read_bytes(), decrypt=True))
            if not isinstance(saved, dict) or set(saved) != set(KEYS):
                raise ValueError("invalid schema")
            for key in KEYS:
                if not isinstance(saved[key], str) or not saved[key]:
                    raise ValueError("invalid credential")
                values[key] = values[key] or saved[key]
        except (ValueError, OSError):
            raise SystemExit("Encrypted credential file is invalid; reset it locally") from None
    return values


def save_interactive(path: Path = SECRET_PATH) -> None:
    if os.name != "nt":
        raise SystemExit("Encrypted credential storage requires Windows")
    if path.exists():
        raise SystemExit("Credentials already exist. Clear them explicitly before replacing.")
    values = {key: getpass.getpass(f"{key} (hidden): ").strip() for key in KEYS}
    if not all(values.values()):
        raise SystemExit("All three credentials are required; nothing saved")
    encrypted = _crypt(json.dumps(values).encode("utf-8"))
    with path.open("xb") as handle:
        handle.write(encrypted)
    print("Encrypted credentials saved for this Windows user. No Reddit connection was made.")
