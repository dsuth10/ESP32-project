"""Isolated local Teaching Board autosave with validated previous-checkpoint recovery.

One caller-provided directory stores one lesson and its bounded undo/redo session.
Current/previous files are fixed names; temporary writes are never promoted on
reopen. An OS lock and file fingerprints reject concurrent/stale writers.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import threading
import uuid

from board_model import BoardModel, BoardConflictError, BoardValidationError, MAX_STATE_BYTES, canonical_json

MAX_FILE_BYTES = MAX_STATE_BYTES + 1024


class BoardStoreError(RuntimeError):
    pass


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BoardValidationError('Duplicate JSON fields are unsupported.')
        result[key] = value
    return result


def _nonfinite(_value):
    raise BoardValidationError('Non-finite JSON numbers are unsupported.')


class BoardStore:
    def __init__(self, root):
        if not isinstance(root, (str, Path)) or not str(root).strip():
            raise BoardStoreError('Provide an isolated lesson data directory.')
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.current_path = self.root / 'lesson.json'
        self.previous_path = self.root / 'lesson.previous.json'
        self.recovery_status = 'unopened'
        self._observed = None
        self._lesson_id = None
        self._saved_revision = None
        self._saved_data = None
        self._lock = threading.RLock()

    @contextmanager
    def _exclusive(self):
        with self._lock:
            lock_path = self.root / '.board.lock'
            if lock_path.is_symlink():
                raise BoardStoreError('Lesson lock must be a local regular file.')
            with lock_path.open('a+b') as stream:
                stream.seek(0, os.SEEK_END)
                if stream.tell() == 0:
                    stream.write(b'0'); stream.flush()
                stream.seek(0)
                try:
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    raise BoardStoreError('This lesson is busy in another writer.') from None
                try:
                    yield
                finally:
                    stream.seek(0)
                    if os.name == 'nt':
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _read(path):
        if path.is_symlink():
            raise BoardStoreError('Lesson files must be local regular files.')
        try:
            with path.open('rb') as stream:
                metadata = os.fstat(stream.fileno())
                if metadata.st_size > MAX_FILE_BYTES:
                    return ('oversized', metadata.st_size, metadata.st_mtime_ns, metadata.st_ino)
                data = stream.read(MAX_FILE_BYTES + 1)
        except FileNotFoundError:
            return None
        if len(data) > MAX_FILE_BYTES:
            return ('oversized', len(data), metadata.st_mtime_ns, metadata.st_ino)
        return data

    def _files(self):
        return self._read(self.current_path), self._read(self.previous_path)

    @staticmethod
    def _fingerprint(files):
        return tuple(hashlib.sha256(data).hexdigest() if isinstance(data, bytes) else data for data in files)

    @staticmethod
    def _decode(data):
        if not isinstance(data, bytes):
            raise BoardStoreError('No saved lesson checkpoint was found.')
        try:
            envelope = json.loads(data.decode('utf-8'), object_pairs_hook=_unique_pairs,
                                  parse_constant=_nonfinite)
            if (not isinstance(envelope, dict) or set(envelope) != {'format', 'schema', 'sha256', 'state'}
                    or envelope['format'] != 'companion-teaching-board'
                    or type(envelope['schema']) is not int or envelope['schema'] != 1):
                raise BoardValidationError('Unsupported checkpoint schema.')
            state = envelope['state']
            if hashlib.sha256(canonical_json(state)).hexdigest() != envelope['sha256']:
                raise BoardValidationError('Checkpoint digest does not match its state.')
            return BoardModel.from_state(state)
        except (ValueError, TypeError, UnicodeError, RecursionError, KeyError):
            raise BoardStoreError('Lesson checkpoint is invalid or damaged.') from None

    @staticmethod
    def _encode(model):
        if not isinstance(model, BoardModel):
            raise BoardStoreError('Save a validated BoardModel session.')
        state = model.export_state()
        # Validate all persisted history as well as the visible document.
        BoardModel.from_state(state)
        envelope = {'format': 'companion-teaching-board', 'schema': 1,
                    'sha256': hashlib.sha256(canonical_json(state)).hexdigest(), 'state': state}
        data = canonical_json(envelope)
        if len(data) > MAX_FILE_BYTES:
            raise BoardStoreError('Lesson checkpoint exceeds the file size limit.')
        return data, state['document']['lesson_id'], state['document']['revision']

    def _atomic_write(self, destination, data):
        temporary = self.root / ('.board-pending-' + uuid.uuid4().hex)
        try:
            with temporary.open('xb') as stream:
                stream.write(data); stream.flush(); os.fsync(stream.fileno())
            os.replace(temporary, destination)
            if os.name != 'nt':
                descriptor = os.open(self.root, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def load(self):
        with self._exclusive():
            files = self._files()
            if files == (None, None):
                raise BoardStoreError('No saved lesson was found.')
            try:
                model = self._decode(files[0])
                status = 'current'
            except BoardStoreError:
                try:
                    model = self._decode(files[1])
                except BoardStoreError:
                    raise BoardStoreError('No valid current or previous lesson checkpoint is available.') from None
                status = 'recovered_previous'
            self._observed = self._fingerprint(files)
            self._lesson_id = model.snapshot()['lesson_id']
            self._saved_revision = model.revision
            self._saved_data = files[0] if status == 'current' else files[1]
            self.recovery_status = status
            return model

    def save(self, model):
        data, lesson_id, revision = self._encode(model)
        with self._exclusive():
            files = self._files()
            fingerprint = self._fingerprint(files)
            if self._observed is None:
                if files != (None, None):
                    raise BoardConflictError('Load the existing lesson before saving over this directory.')
            elif fingerprint != self._observed:
                raise BoardConflictError('The saved lesson changed in another writer. Reopen before saving.')
            if self._lesson_id is not None and lesson_id != self._lesson_id:
                raise BoardConflictError('This directory belongs to a different lesson.')
            if (self._saved_revision is not None and (revision < self._saved_revision
                    or (revision == self._saved_revision and data != self._saved_data))):
                raise BoardConflictError('A save cannot overwrite a newer or different lesson revision.')
            # Only a validated current checkpoint may replace the previous one.
            try:
                self._decode(files[0])
                current_valid = True
            except BoardStoreError:
                current_valid = False
            if current_valid:
                self._atomic_write(self.previous_path, files[0])
            self._atomic_write(self.current_path, data)
            self._observed = self._fingerprint(self._files())
            self._lesson_id = lesson_id
            self._saved_revision = revision
            self._saved_data = data
            self.recovery_status = 'current'
            return revision
