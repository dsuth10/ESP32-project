"""Optional OS-backed PC microphone ownership for the unified desktop.

The open file owns the lock, so a worker thread may release it and process exit
releases it automatically. No transcript or device identity enters this file.
"""
from __future__ import annotations

import os
from pathlib import Path
import threading


class ExclusiveFileLease:
    def __init__(self, path):
        self.path = Path(path) if path else None
        self._file = None
        self._guard = threading.Lock()

    def acquire(self):
        if self.path is None:
            return True
        with self._guard:
            if self._file is not None:
                return True
            stream = None
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                stream = self.path.open('a+b')
                if self.path.stat().st_size == 0:
                    stream.write(b'\0'); stream.flush()
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                if stream is not None:
                    stream.close()
                return False
            self._file = stream
            return True

    def release(self):
        with self._guard:
            stream, self._file = self._file, None
            if stream is None:
                return
            try:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            finally:
                stream.close()


class MicrophoneLease(ExclusiveFileLease):
    def __init__(self, path=None):
        selected = path if path is not None else os.environ.get('ESP32_COMPANION_MICROPHONE_LEASE')
        super().__init__(selected)
