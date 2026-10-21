"""Local settings and Windows user-bound credential encryption."""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import tempfile

PUBLIC_KEYS = {'MEDIA_SERVER_URL', 'MEDIA_SYNC_ENABLED', 'ALLOW_PRIVATE_SYNC', 'IMAGE_MODEL',
               'IMAGE_GENERATION_ENABLED', 'IMAGE_ESTIMATE_AUD_CENTS', 'LOCAL_ONLY',
               'GROQ_ASSISTANT_MODEL', 'ESP32_START_RECEIVER', 'ESP32_ENABLE_HOTKEYS'}
SECRET_KEYS = {'MEDIA_SERVER_TOKEN', 'OPENAI_API_KEY', 'GROQ_API_KEY'}


def data_directory() -> Path:
    if os.environ.get('ESP32_COMPANION_DATA_DIR'):
        return Path(os.environ['ESP32_COMPANION_DATA_DIR']).expanduser()
    if os.environ.get('LOCALAPPDATA'):
        return Path(os.environ['LOCALAPPDATA']) / 'ESP32ClassroomCompanion'
    return Path.home() / '.local/share/ESP32ClassroomCompanion'


class _Blob(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(data: bytes, decrypt=False) -> bytes:
    if os.name != 'nt':
        raise RuntimeError('Protected credential storage requires Windows. Use environment variables on other systems.')
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source, output = _Blob(len(data), buffer), _Blob()
    crypt32, kernel = ctypes.WinDLL('crypt32', use_last_error=True), ctypes.WinDLL('kernel32', use_last_error=True)
    # CRYPTPROTECT_UI_FORBIDDEN; default protection scope is the current user.
    if decrypt:
        ok = crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output))
    else:
        ok = crypt32.CryptProtectData(ctypes.byref(source), 'ESP32 companion credentials', None, None, None, 1, ctypes.byref(output))
    if not ok:
        raise RuntimeError('Windows could not access protected companion credentials.')
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel.LocalFree(output.pbData)


def _atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.settings-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def load_settings(root: Path | None = None) -> dict:
    root = root or data_directory()
    output = {}
    path = root / 'settings.json'
    if path.exists():
        values = json.loads(path.read_text(encoding='utf-8'))
        output.update({k:str(v) for k,v in values.items() if k in PUBLIC_KEYS})
    secret_path = root / 'credentials.dpapi'
    if secret_path.exists():
        values = json.loads(_crypt(secret_path.read_bytes(), decrypt=True))
        output.update({k:str(v) for k,v in values.items() if k in SECRET_KEYS})
    return output


def save_settings(values: dict, root: Path | None = None):
    root = root or data_directory()
    previous = load_settings(root)
    previous.update({k:str(v) for k,v in values.items() if k in PUBLIC_KEYS | SECRET_KEYS})
    public = {k:v for k,v in previous.items() if k in PUBLIC_KEYS}
    secrets = {k:v for k,v in previous.items() if k in SECRET_KEYS and v}
    # Encrypt before changing either file, so unsupported platforms never save keys in plain text.
    encrypted = _crypt(json.dumps(secrets).encode('utf-8')) if secrets else None
    if encrypted is not None:
        _atomic_write(root/'credentials.dpapi', encrypted)
    elif (root/'credentials.dpapi').exists():
        (root/'credentials.dpapi').unlink()
    _atomic_write(root/'settings.json', json.dumps(public, indent=2).encode('utf-8'))
