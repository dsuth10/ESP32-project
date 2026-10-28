"""Local settings and Windows user-bound credential encryption."""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import base64
from contextlib import contextmanager
import errno
import json
import os
from pathlib import Path
import tempfile
import time

PUBLIC_KEYS = {'MEDIA_SERVER_URL', 'MEDIA_SYNC_ENABLED', 'IMAGE_MODEL', 'IMAGE_PROVIDER', 'GOOGLE_IMAGE_MODEL',
               'IMAGE_GENERATION_ENABLED', 'IMAGE_ESTIMATE_AUD_CENTS', 'LOCAL_ONLY',
               'GROQ_ASSISTANT_MODEL', 'ESP32_START_RECEIVER', 'ESP32_ENABLE_HOTKEYS',
               'HERMES_ENABLED', 'HERMES_URL'}
PUBLIC_KEYS |= {'GOOGLE_IMAGE_SIZE', 'GOOGLE_IMAGE_ASPECT_RATIO', 'GOOGLE_IMAGE_THINKING',
                'GOOGLE_IMAGE_ESTIMATE_1K_AUD_CENTS', 'GOOGLE_IMAGE_ESTIMATE_2K_AUD_CENTS',
                'GOOGLE_IMAGE_ESTIMATE_4K_AUD_CENTS'}
PUBLIC_KEYS.add('DEVICE_FEEDBACK_PORT')
PUBLIC_KEYS.add('IMAGE_SPENDING_UNCAPPED')
SECRET_KEYS = {'MEDIA_SERVER_TOKEN', 'OPENAI_API_KEY', 'GOOGLE_IMAGE_API_KEY', 'GROQ_API_KEY', 'HERMES_TOKEN'}
SECRET_KEYS.add('DEVICE_FEEDBACK_ID')
_JOURNAL_NAME = '.settings-transaction.json'
_LOCK_NAME = '.settings.lock'
_MAX_TRANSACTION_BYTES = 2 * 1024 * 1024


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


@contextmanager
def _settings_lock(root: Path):
    """Serialise readers and writers; OS locks are released if a process dies."""
    root.mkdir(parents=True, exist_ok=True)
    with (root / _LOCK_NAME).open('a+b') as lock_file:
        if os.name == 'nt':
            import msvcrt
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b'\0')
                lock_file.flush()
                os.fsync(lock_file.fileno())
            while True:
                try:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if exc.errno not in {errno.EACCES, errno.EDEADLK, errno.EAGAIN}:
                        raise
                    time.sleep(0.05)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _decode_journal(journal_path: Path) -> dict:
    try:
        raw = journal_path.read_bytes()
        if len(raw) > _MAX_TRANSACTION_BYTES:
            raise ValueError
        journal = json.loads(raw.decode('utf-8'))
        if (not isinstance(journal, dict) or journal.get('version') != 1 or
                journal.get('phase') not in {'prepared', 'committed'}):
            raise ValueError
        previous = journal.get('previous')
        if not isinstance(previous, dict) or set(previous) != {'settings.json', 'credentials.dpapi'}:
            raise ValueError
        decoded = {}
        for name, value in previous.items():
            if value is None:
                decoded[name] = None
            elif isinstance(value, str):
                decoded[name] = base64.b64decode(value, validate=True)
            else:
                raise ValueError
        return {'phase': journal['phase'], 'previous': decoded}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
        raise RuntimeError('Protected settings transaction is unreadable; settings are locked for recovery.') from None


def _journal_bytes(phase: str, public: bytes | None, credentials: bytes | None) -> bytes:
    previous = {
        'settings.json': None if public is None else base64.b64encode(public).decode('ascii'),
        'credentials.dpapi': None if credentials is None else base64.b64encode(credentials).decode('ascii'),
    }
    raw = json.dumps({'version': 1, 'phase': phase, 'previous': previous}, separators=(',', ':')).encode('utf-8')
    if len(raw) > _MAX_TRANSACTION_BYTES:
        raise ValueError('Protected settings transaction exceeds the supported size limit.')
    return raw


def _restore_previous(root: Path, previous: dict):
    for name in ('credentials.dpapi', 'settings.json'):
        path = root / name
        contents = previous[name]
        if contents is None:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        else:
            _atomic_write(path, contents)


def _recover_settings(root: Path):
    journal_path = root / _JOURNAL_NAME
    if not journal_path.exists():
        return
    journal = _decode_journal(journal_path)
    try:
        if journal['phase'] == 'prepared':
            _restore_previous(root, journal['previous'])
        journal_path.unlink()
    except OSError:
        # Keep the journal so a later process can retry; never read a possibly
        # mixed public/credential pair after a failed rollback.
        raise RuntimeError('Protected settings recovery is incomplete; settings remain locked until recovery succeeds.') from None


def _load_settings_unlocked(root: Path) -> dict:
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


def load_settings(root: Path | None = None) -> dict:
    root = Path(root or data_directory())
    with _settings_lock(root):
        _recover_settings(root)
        return _load_settings_unlocked(root)


def save_settings(values: dict, root: Path | None = None):
    root = Path(root or data_directory())
    with _settings_lock(root):
        _recover_settings(root)
        previous = _load_settings_unlocked(root)
        previous.update({k:str(v) for k,v in values.items() if k in PUBLIC_KEYS | SECRET_KEYS})
        public = {k:v for k,v in previous.items() if k in PUBLIC_KEYS}
        secrets = {k:v for k,v in previous.items() if k in SECRET_KEYS and v}
        # Encrypt before journalling or changing either file. The journal only
        # contains this protected blob and public settings, never secret text.
        encrypted = _crypt(json.dumps(secrets).encode('utf-8')) if secrets else None
        public_path = root / 'settings.json'
        credentials_path = root / 'credentials.dpapi'
        old_public = public_path.read_bytes() if public_path.exists() else None
        old_credentials = credentials_path.read_bytes() if credentials_path.exists() else None
        journal_path = root / _JOURNAL_NAME
        _atomic_write(journal_path, _journal_bytes('prepared', old_public, old_credentials))
        try:
            if encrypted is not None:
                _atomic_write(credentials_path, encrypted)
            elif credentials_path.exists():
                credentials_path.unlink()
            _atomic_write(public_path, json.dumps(public, indent=2).encode('utf-8'))
            # This durable marker is the commit point. Before it, recovery
            # restores the old pair; after it, recovery keeps the new pair.
            _atomic_write(journal_path, _journal_bytes('committed', old_public, old_credentials))
        except Exception:
            try:
                on_disk = _decode_journal(journal_path)
                if on_disk['phase'] == 'committed':
                    # The marker may have reached disk just before an fsync
                    # error. Both new files were already written atomically.
                    return
                _restore_previous(root, on_disk['previous'])
                journal_path.unlink()
            except Exception:
                raise RuntimeError('Settings update failed and recovery is required before settings can be loaded.') from None
            raise
        try:
            journal_path.unlink()
        except OSError:
            # The committed marker makes this safe to clean up on the next
            # read or write; failure to remove it cannot expose a mixed pair.
            pass
