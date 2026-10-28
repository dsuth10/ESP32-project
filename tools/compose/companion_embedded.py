"""Private stdio lifecycle for the existing companion inside the teacher shell.

Only bounded control/state messages cross this interface. Requests, results,
credentials and document text remain in the existing companion process.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import logging
import os
from pathlib import Path
import queue
import sys
import threading

MAX_MESSAGE = 2048
PENDING_TEXT_REASON = 'Text is still waiting in Paste Ready. Paste it before closing, or explicitly discard this queued copy.'


def claim_instance_mutex(data_root: Path):
    """Use the same profile-scoped instance identity for both entry points."""
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    name = 'Local\\ESP32ComposeGui'
    if os.environ.get('ESP32_COMPANION_DATA_DIR'):
        name += '-' + hashlib.sha256(str(data_root.resolve()).casefold().encode()).hexdigest()[:12]
    handle = kernel.CreateMutexW(None, False, name)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle(handle)
        return None
    return handle


def validate_parent(parent_pid: int, parent_hwnd: int):
    if os.name != 'nt' or parent_pid != os.getppid() or parent_pid <= 0 or parent_hwnd <= 0:
        raise ValueError('Embedding requires the actual parent process and its native window.')
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.IsWindow.argtypes = [wintypes.HWND]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    owner = wintypes.DWORD()
    if not user.IsWindow(parent_hwnd):
        raise ValueError('The teacher window is unavailable.')
    user.GetWindowThreadProcessId(parent_hwnd, ctypes.byref(owner))
    if owner.value != parent_pid:
        raise ValueError('The teacher window does not belong to the parent process.')


def close_block_reason(app, *, allow_queued_text=False):
    if getattr(getattr(app, 'settings_panel', None), '_saving', False):
        return 'Settings are still being protected. Wait for saving to finish.'
    if getattr(app, 'is_recording', False):
        return 'Finish the companion microphone recording before closing.'
    if getattr(app, '_busy', False):
        return 'Wait for the current transcription or writing task to finish.'
    for name in ('assistant_panel', 'media_panel', 'hermes_panel'):
        if getattr(getattr(app, name, None), '_busy', False):
            return 'Wait for the current companion request to finish before closing.'
    if getattr(app, 'pending_ready_payload', None) and not allow_queued_text:
        return PENDING_TEXT_REASON
    return ''


class EmbeddedLifecycle:
    """Tk-thread control handler; an idle preflight locks new operations."""
    def __init__(self, app, emit, enable_window=lambda enabled: None):
        self.app, self.emit, self.enable_window = app, emit, enable_window
        self.prepared = None

    def handle(self, message):
        if not isinstance(message, dict):
            return
        kind = message.get('type')
        request_id = message.get('request_id')
        if kind in {'prepare_close', 'cancel_close', 'commit_close'}:
            if not isinstance(request_id, str) or not 1 <= len(request_id) <= 80:
                return
        if kind == 'prepare_close':
            reason = close_block_reason(self.app, allow_queued_text=message.get('discard_queued_text') is True)
            pending_text = bool(getattr(self.app, 'pending_ready_payload', None))
            if reason:
                self.emit({'type': 'close_blocked', 'request_id': request_id, 'reason': reason,
                           'code': 'pending_text' if reason == PENDING_TEXT_REASON else 'busy'})
                return
            if self.prepared not in {None, request_id}:
                self.emit({'type': 'close_blocked', 'request_id': request_id,
                           'reason': 'Another close request is already being prepared.'})
                return
            self.prepared = request_id
            self.discard_queued_text = pending_text and message.get('discard_queued_text') is True
            self.app._shutdown_prepared = True
            self.enable_window(False)
            self.emit({'type': 'close_ready', 'request_id': request_id})
        elif kind == 'cancel_close' and self.prepared == request_id:
            self.cancel()
        elif kind == 'commit_close' and self.prepared == request_id:
            # The only path that releases the gate without returning to normal
            # event processing is the synchronous final close itself.
            self.app._shutdown_prepared = False
            if getattr(self, 'discard_queued_text', False):
                self.app.pending_ready_payload = None
            self.app.close()
            self.emit({'type': 'closed', 'request_id': request_id})

    def cancel(self):
        self.prepared = None
        self.app._shutdown_prepared = False
        self.enable_window(True)


def _detach(root, hwnd, parent_pid):
    """An unexpectedly lost shell must leave recoverable, visible controls."""
    import win32con
    import win32gui
    # The teacher shell can still be alive after a protocol/embedding failure.
    # Keep its private teacher/pupil controls excluded for this child lifetime.
    win32gui.SetParent(hwnd, 0)
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE,
                          (style & ~win32con.WS_CHILD) | win32con.WS_OVERLAPPEDWINDOW)
    root.deiconify()
    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
    win32gui.SetWindowPos(hwnd, 0, 80, 80, 1000, 800,
                         win32con.SWP_NOZORDER | win32con.SWP_FRAMECHANGED)
    root.lift()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-pid', type=int, required=True)
    parser.add_argument('--parent-hwnd', type=int, required=True)
    args = parser.parse_args(argv)
    protocol_output = sys.stdout
    # Library diagnostics must never be parsed as control messages, including
    # print() calls made later by worker threads.
    sys.stdout = sys.stderr
    output_lock = threading.Lock()

    def emit(message):
        try:
            with output_lock:
                protocol_output.write(json.dumps(message, separators=(',', ':')) + '\n')
                protocol_output.flush()
        except (OSError, ValueError):
            pass

    try:
        validate_parent(args.parent_pid, args.parent_hwnd)
        from companion_settings import data_directory
        instance_mutex = claim_instance_mutex(data_directory())
        if not instance_mutex:
            emit({'type': 'error', 'message': 'This companion profile is already open. Close its existing window first.'})
            return 2
        import tkinter as tk
        from focus_tracker import FocusTracker
        FocusTracker.register_internal_process(args.parent_pid)
        from compose_gui import ComposeApp
        logging.basicConfig(filename=Path(__file__).with_name('companion.log'),
                            level=logging.INFO, encoding='utf-8',
                            format='%(asctime)s %(levelname)s %(message)s')
        root = tk.Tk()
        root.withdraw()
        app = ComposeApp(root, embedded=True)
        root.overrideredirect(True)
        root.update_idletasks()
        import win32gui
        hwnd = win32gui.GetAncestor(root.winfo_id(), 2)
        lifecycle = EmbeddedLifecycle(app, emit, lambda enabled: win32gui.EnableWindow(hwnd, enabled))
        app.show_embedded_workspace = lambda: emit({'type': 'show_companion'})
        # A window-manager close also follows the parent-owned preflight.
        root.protocol('WM_DELETE_WINDOW', lambda: emit({'type': 'request_close'}))
        commands = queue.Queue(maxsize=128)
        disconnected = threading.Event()

        def read_commands():
            try:
                while True:
                    line = sys.stdin.readline(MAX_MESSAGE + 1)
                    if not line:
                        break
                    if len(line) > MAX_MESSAGE or not line.endswith('\n'):
                        break
                    try:
                        message = json.loads(line)
                    except ValueError:
                        continue
                    try:
                        commands.put_nowait(message)
                    except queue.Full:
                        break
            except (OSError, ValueError):
                pass
            finally:
                disconnected.set()

        def recover_controls():
            lifecycle.cancel()
            app.embedded = False
            app.show_embedded_workspace = None
            root.protocol('WM_DELETE_WINDOW', app.close)
            _detach(root, hwnd, args.parent_pid)
            app.set_status('Teacher window disconnected. Companion controls were recovered in this window.', '#F59E0B')

        def drain():
            if app._stop_poller:
                return
            if disconnected.is_set():
                recover_controls()
                return
            for _ in range(32):
                try:
                    message = commands.get_nowait()
                except queue.Empty:
                    break
                if isinstance(message, dict) and message.get('type') == 'attached':
                    root.withdraw()
                    root.deiconify()
                    root.update_idletasks()
                elif isinstance(message, dict) and message.get('type') == 'detach':
                    recover_controls()
                    return
                else:
                    lifecycle.handle(message)
                if app._stop_poller:
                    return
            emit({'type': 'status', 'recording': bool(app.is_recording),
                  'busy': bool(app._busy or any(getattr(getattr(app, name, None), '_busy', False)
                                              for name in ('assistant_panel', 'media_panel', 'hermes_panel')))})
            root.after(150, drain)

        threading.Thread(target=read_commands, daemon=True, name='teacher-control-reader').start()
        root.after(50, drain)
        emit({'type': 'ready', 'hwnd': hwnd, 'pid': os.getpid()})
        root.mainloop()
        return 0
    except Exception:
        logging.exception('Embedded companion could not start')
        emit({'type': 'error', 'message': 'The companion could not start. Check its local dependencies and data-folder access.'})
        return 1


if __name__ == '__main__':
    sys.exit(main())
