"""Host the existing Tk companion inside the Qt teacher window on Windows.

Only window lifecycle, microphone availability and redacted state cross this
interface. Content, credentials and existing companion work remain in its own
process. A broken host connection releases a recoverable standalone window.
"""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import uuid

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


MAX_MESSAGE_BYTES = 4096


def direct_python_executable(selected, environment):
    """Bypass Windows' venv redirector while retaining its Python environment.

    The redirector creates another process, breaking the exact parent/child
    ownership checks used for native embedding. CPython recognises this same
    launcher variable to retain the selected venv's prefix and dependencies.
    """
    selected = Path(selected).resolve()
    configuration = selected.parent.parent / 'pyvenv.cfg'
    if sys.platform == 'win32' and configuration.is_file():
        values = {}
        for line in configuration.read_text(encoding='utf-8').splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                values[key.strip().lower()] = value.strip()
        base = Path(values.get('executable') or str(Path(values.get('home', '')) / 'python.exe'))
        if not base.is_file():
            raise ValueError('The selected Python environment has no available base interpreter.')
        environment['__PYVENV_LAUNCHER__'] = str(selected)
        return str(base)
    environment.pop('__PYVENV_LAUNCHER__', None)
    return str(selected)


def native_window_owned_by(hwnd: int, pid: int) -> bool:
    """Never adopt an arbitrary window identity from a child message."""
    if sys.platform != 'win32' or type(hwnd) is not int or type(pid) is not int or hwnd <= 0 or pid <= 0:
        return False
    from ctypes import wintypes
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    owner = wintypes.DWORD()
    return bool(user32.IsWindow(hwnd) and user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner)) and owner.value == pid)


class CompanionHost(QWidget):
    """One native companion pane, with an explicit two-phase shutdown."""
    ready = Signal()
    busyChanged = Signal(bool)
    recordingChanged = Signal(bool)
    closePrepared = Signal(bool, str)
    closeBlockedCode = Signal(str)
    closeRequested = Signal()
    closed = Signal()
    showRequested = Signal()
    failed = Signal(str)
    stateChanged = Signal(str)

    def __init__(self, companion_data_root, *, python_executable=None, parent=None):
        super().__init__(parent)
        self.data_root = Path(companion_data_root)
        self.python_executable = str(python_executable or sys.executable)
        self.process = None
        self._events = queue.Queue(maxsize=100)
        self._foreign = self._container = None
        self._ready = False
        self._released = False
        self._hwnd = None
        self._recording = self._busy = False
        self._peer_microphone = False
        self._close_request = None
        self._close_deadline = None
        self._commit_deadline = None
        self._start_deadline = None
        self._exit_reported = False
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.notice = QLabel('The voice companion is starting. Its existing tools remain separate from the Teaching Board.')
        self.notice.setWordWrap(True)
        self._layout.addWidget(self.notice)
        self.retry = QPushButton('Start voice companion')
        self.retry.clicked.connect(self.start)
        self._layout.addWidget(self.retry)
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._poll)
        # Popen is intentional: destroying a QProcess kills its child, which
        # could interrupt a paid request or hide undurable queued writing.
        from PySide6.QtWidgets import QApplication
        QApplication.instance().aboutToQuit.connect(self._release_on_host_exit)

    @property
    def is_running(self):
        return not self._released and self.process is not None and self.process.poll() is None

    @property
    def is_ready(self):
        return self._ready and self.is_running

    def start(self):
        if self.process is not None and self.process.poll() is None:
            if self._released:
                self._set_notice('The recovered companion is still open in its own window. Close that window before restarting it here.')
            return
        self._clear_container()
        self._ready = self._exit_reported = False
        self._released = False
        self._hwnd = None
        self._close_request = self._close_deadline = None
        if sys.platform != 'win32':
            self._failure('The combined native voice pane currently requires Windows. The Teaching Board remains available.')
            return
        self.retry.setEnabled(False)
        self.notice.show()
        self._set_notice('Starting the existing voice companion…')
        environment = os.environ.copy()
        environment['ESP32_COMPANION_DATA_DIR'] = str(self.data_root.resolve())
        environment['PYTHONIOENCODING'] = 'utf-8'
        environment.setdefault('ESP32_RECEIVER_PORT', '8788')
        environment.setdefault('ESP32_DISCOVERY_UDP_PORT', '8789')
        entry = Path(__file__).with_name('companion_embedded.py')
        try:
            executable = direct_python_executable(self.python_executable, environment)
            arguments = [executable, '-u', str(entry), '--parent-pid', str(os.getpid()),
                         '--parent-hwnd', str(int(self.window().winId()))]
            process = subprocess.Popen(arguments, cwd=str(entry.parent), env=environment,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW)
        except (OSError, ValueError):
            self._failure('The voice companion could not start. Check its Python dependencies and retry. Existing data was preserved.')
            return
        self.process = process
        self._start_deadline = time.monotonic() + 30
        threading.Thread(target=self._read_messages, args=(process,), daemon=True).start()
        threading.Thread(target=self._discard_diagnostics, args=(process,), daemon=True).start()
        self._timer.start()

    def _read_messages(self, process):
        while True:
            line = process.stdout.readline(MAX_MESSAGE_BYTES + 1)
            if not line:
                return
            if len(line) > MAX_MESSAGE_BYTES or not line.endswith(b'\n'):
                self._enqueue(process, {'type': 'protocol_error'})
                return
            try:
                value = json.loads(line.decode('utf-8'))
            except (ValueError, UnicodeError):
                self._enqueue(process, {'type': 'protocol_error'})
                return
            if not isinstance(value, dict):
                self._enqueue(process, {'type': 'protocol_error'})
                return
            self._enqueue(process, value)

    def _enqueue(self, process, value):
        try:
            self._events.put((process, value), timeout=1)
        except queue.Full:
            # Closing stdin triggers the child's visible recovery path.
            self._release_process_channel(process)

    @staticmethod
    def _discard_diagnostics(process):
        # Drain stderr to avoid blocking, without exposing private diagnostics
        # as product content or allowing an unbounded in-memory log.
        while process.stderr.read(4096):
            pass

    def _send(self, value):
        if not self.is_running:
            return False
        try:
            self.process.stdin.write((json.dumps(value, separators=(',', ':')) + '\n').encode('utf-8'))
            self.process.stdin.flush()
            return True
        except (OSError, ValueError):
            return False

    def _poll(self):
        for _ in range(100):
            try:
                process, value = self._events.get_nowait()
            except queue.Empty:
                break
            if process is self.process:
                self._receive(value)
        now = time.monotonic()
        if self._start_deadline and not self._ready and now > self._start_deadline:
            self._start_deadline = None
            self._failure('The voice companion did not finish starting. It has been released to its own window if still running; no work was forcibly stopped.')
            self._release_on_host_exit()
        if self._close_deadline and now > self._close_deadline:
            self._close_deadline = None
            self.cancel_close()
            self.closePrepared.emit(False, 'The voice companion did not confirm it was ready to close. Keep the app open and try again.')
        if self._commit_deadline and now > self._commit_deadline and self.is_running:
            self._commit_deadline = None
            self.cancel_close()
            self.closePrepared.emit(False, 'The voice companion is still finishing shutdown. Teaching Board work remains open; wait before closing again.')
        if self.process and self.process.poll() is not None and not self._exit_reported:
            self._exit_reported = True
            self._ready = False
            self._set_activity(False, False)
            if self._close_request:
                self.closed.emit()
            else:
                self._failure('The voice companion stopped. Teaching Board work remains open; retry the companion when ready.')
            self._commit_deadline = None
            self.retry.setEnabled(True)

    def _receive(self, value):
        kind = value.get('type')
        if kind == 'ready' and not self._ready:
            hwnd, pid = value.get('hwnd'), value.get('pid')
            if pid != self.process.pid or not native_window_owned_by(hwnd, pid):
                self._failure('The companion window identity could not be checked. It was not attached.')
                self._release_on_host_exit()
                return
            try:
                # QTabWidget does not create native handles for a hidden page.
                # Materialise this parent before Qt adopts the foreign window,
                # so its initial native ancestry is the teacher window too.
                self.winId()
                self._foreign = QWindow.fromWinId(hwnd)
                self._hwnd = hwnd
                if self._foreign is None:
                    raise RuntimeError('Foreign window unavailable')
                self._container = QWidget.createWindowContainer(self._foreign, self)
                self._container.setMinimumSize(720, 640)
                self._layout.addWidget(self._container, 1)
                self._container.winId()
                self._container.show()
                self._ready = True
                self._start_deadline = None
                self.notice.hide()
                self.retry.hide()
                self._refresh_visible_child()
                self.set_peer_microphone(self._peer_microphone)
                self.ready.emit()
                self.stateChanged.emit('Voice companion ready')
            except Exception:
                self._failure('The voice companion could not attach to this window. It was released to its own window; no work was forcibly stopped.')
                self._release_on_host_exit()
        elif kind == 'status':
            self._set_activity(value.get('recording') is True, value.get('busy') is True)
        elif kind == 'show_companion':
            self.showRequested.emit()
        elif kind in {'close_ready', 'close_blocked'} and value.get('request_id') == self._close_request:
            self._close_deadline = None
            approved = kind == 'close_ready'
            reason = str(value.get('reason') or '')[:500]
            code = str(value.get('code') or '')[:60]
            if not approved and code == 'pending_text':
                self.closeBlockedCode.emit(code)
            else:
                self.closePrepared.emit(approved, reason)
        elif kind == 'closed' and value.get('request_id') == self._close_request:
            # Wait for process exit before allowing Qt to destroy its window.
            self._set_notice('Closing the voice companion…')
        elif kind == 'protocol_error':
            self._failure('The companion connection could not be read safely. It was released to its own window; no work was forcibly stopped.')
            self._release_on_host_exit()
        elif kind == 'request_close':
            self.closeRequested.emit()
        elif kind == 'error':
            self._failure(str(value.get('message') or 'The voice companion could not start.')[:500])

    def _set_activity(self, recording, busy):
        if recording != self._recording:
            self._recording = recording
            self.recordingChanged.emit(recording)
        if busy != self._busy:
            self._busy = busy
            self.busyChanged.emit(busy)

    def showEvent(self, event):
        super().showEvent(event)
        # A hidden Qt tab parks its foreign window outside the visible native
        # ancestry. Let Qt restore that ancestry before asking Tk to remap its
        # controls; remapping while hidden can preserve an obsolete geometry.
        QTimer.singleShot(0, self._refresh_visible_child)

    def _refresh_visible_child(self):
        if self.is_ready and self.isVisible() and self._container:
            self._layout.activate()
            self._container.show()
            self._send({'type': 'attached'})

    def set_peer_microphone(self, active):
        self._peer_microphone = bool(active)
        if self.is_ready:
            self._send({'type': 'peer_microphone', 'active': self._peer_microphone})

    def prepare_close(self, discard_queued_text=False):
        if not self.is_running:
            self.closePrepared.emit(True, '')
            return
        if not self.is_ready:
            self.closePrepared.emit(False, 'Wait for the voice companion to finish starting before closing.')
            return
        self._close_request = uuid.uuid4().hex
        self._close_deadline = time.monotonic() + 5
        if not self._send({'type': 'prepare_close', 'request_id': self._close_request,
                           'discard_queued_text': bool(discard_queued_text)}):
            self._close_deadline = None
            self.closePrepared.emit(False, 'The voice companion could not confirm it was ready to close.')

    def cancel_close(self):
        if self._close_request:
            self._send({'type': 'cancel_close', 'request_id': self._close_request})
        self._close_request = self._close_deadline = None
        self._commit_deadline = None

    def commit_close(self):
        if not self.is_running:
            self.closed.emit()
        elif self._close_request:
            if self._send({'type': 'commit_close', 'request_id': self._close_request}):
                self._commit_deadline = time.monotonic() + 10
            else:
                self.closePrepared.emit(False, 'The voice companion could not finish the close handshake. Teaching Board work remains open.')

    def _set_notice(self, message):
        self.notice.setText(message)
        self.stateChanged.emit(message)

    def _failure(self, message):
        self.notice.show()
        self.retry.show()
        self.retry.setEnabled(self.process is None or self.process.poll() is not None)
        self._set_notice(message)
        self.failed.emit(message)

    def _clear_container(self):
        if self._container:
            self._layout.removeWidget(self._container)
            self._container.deleteLater()
            self._container = self._foreign = None

    @staticmethod
    def _release_process_channel(process):
        if process and process.stdin:
            try:
                process.stdin.close()
            except (OSError, ValueError):
                pass

    def _release_on_host_exit(self, *_args):
        if self._hwnd and self.process and self.process.poll() is None:
            # Preserve the native window before Qt destroys its container. The
            # child's EOF handler restores full standalone decoration/controls.
            try:
                from ctypes import wintypes
                user32 = ctypes.WinDLL('user32', use_last_error=True)
                user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
                user32.SetParent(self._hwnd, None)
            except (OSError, ValueError):
                pass
        self._release_process_channel(self.process)
        self._released = True
        self._ready = False
