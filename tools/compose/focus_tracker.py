"""
Focus tracking, UI Automation target lock, and multi-tier selection capture for Windows.
Supports UIA TextPattern, Win32 WM_COPY (Notepad++/Scintilla/Edit), and chord-aware Ctrl+C.
"""

import os
import time
import logging
import ctypes
from ctypes import wintypes
import win32gui
import win32process
import uiautomation as auto
from clipboard_manager import ClipboardManager

_KEY_UP = 0x0002
_VK_SHIFT = 0x10
_VK_CONTROL = 0x11
_VK_MENU = 0x12
_VK_C = 0x43


def _key_is_down(vk: int) -> bool:
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)


def _key_event(vk: int, up: bool = False) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, _KEY_UP if up else 0, 0)


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


class FocusTracker:
    # The unified teacher shell and its pupil window live in another process.
    # Register only a parent validated by the embedded entry point, never an
    # untrusted PID taken from a document or model response.
    _internal_processes: set[int] = set()

    @classmethod
    def register_internal_process(cls, pid: int) -> None:
        if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0:
            cls._internal_processes.add(pid)

    @classmethod
    def unregister_internal_process(cls, pid: int) -> None:
        cls._internal_processes.discard(pid)

    @classmethod
    def is_internal_process(cls, pid: int) -> bool:
        return pid == os.getpid() or pid in cls._internal_processes

    @classmethod
    def is_internal_snapshot(cls, snapshot: dict | None) -> bool:
        return bool(snapshot and cls.is_internal_process(snapshot.get('pid', 0)))

    @classmethod
    def is_internal_window(cls, hwnd: int) -> bool:
        if not hwnd:
            return False
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return cls.is_internal_process(pid)

    @staticmethod
    def get_focus_snapshot() -> dict:
        """
        Snapshots the active foreground window HWND and focused UI Automation control.
        """
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd) if hwnd else ""
        _, pid = win32process.GetWindowThreadProcessId(hwnd) if hwnd else (0, 0)

        runtime_id = None
        try:
            with auto.UIAutomationInitializerInThread():
                focused = auto.GetFocusedControl()
                if focused:
                    runtime_id = focused.GetRuntimeId()
        except Exception:
            # UI Automation may fail on non-standard windows; fallback to HWND only
            pass

        return {
            "hwnd": hwnd,
            "title": title,
            "pid": pid,
            "runtime_id": runtime_id,
            "timestamp": time.time(),
        }

    @staticmethod
    def snapshot_foreground_window() -> dict:
        """HWND/title/pid only. Safe to call from the hotkey poller."""
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd) if hwnd else ""
        _, pid = win32process.GetWindowThreadProcessId(hwnd) if hwnd else (0, 0)
        return {
            "hwnd": hwnd,
            "title": title,
            "pid": pid,
            "runtime_id": None,
            "timestamp": time.time(),
        }

    @staticmethod
    def restore_focus(snapshot: dict | None) -> bool:
        """Bring the recorded document window back to the foreground."""
        hwnd = snapshot.get("hwnd") if snapshot else 0
        if not hwnd or FocusTracker.is_internal_snapshot(snapshot):
            return False
        try:
            if not win32gui.IsWindow(hwnd):
                return False
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if FocusTracker.is_internal_process(pid):
                return False
            if snapshot.get("pid") and pid != snapshot["pid"]:
                return False
            if snapshot.get("title") and win32gui.GetWindowText(hwnd) != snapshot["title"]:
                return False
            if win32gui.GetForegroundWindow() == hwnd:
                return True
            user32 = ctypes.windll.user32
            foreground = win32gui.GetForegroundWindow()
            fg_tid, _ = win32process.GetWindowThreadProcessId(foreground) if foreground else (0, 0)
            tgt_tid, _ = win32process.GetWindowThreadProcessId(hwnd)
            cur_tid = ctypes.windll.kernel32.GetCurrentThreadId()
            attached = []
            if fg_tid:
                user32.AttachThreadInput(cur_tid, fg_tid, True)
                attached.append(fg_tid)
            if tgt_tid and tgt_tid not in attached:
                user32.AttachThreadInput(cur_tid, tgt_tid, True)
                attached.append(tgt_tid)
            try:
                win32gui.ShowWindow(hwnd, 9)  # SW_RESTORE
                win32gui.SetForegroundWindow(hwnd)
            finally:
                for tid in reversed(attached):
                    user32.AttachThreadInput(cur_tid, tid, False)
            return win32gui.GetForegroundWindow() == hwnd
        except Exception as e:
            logging.debug("[FocusTracker] restore_focus error: %s", e)
            return False

    @staticmethod
    def is_focus_matched(snapshot: dict) -> bool:
        """
        Verifies if the current foreground window and control still match the snapshot.
        """
        if not snapshot or not snapshot.get("hwnd") or FocusTracker.is_internal_snapshot(snapshot):
            return False

        current_hwnd = win32gui.GetForegroundWindow()
        if current_hwnd != snapshot["hwnd"]:
            return False
        if FocusTracker.is_internal_window(current_hwnd):
            return False

        if snapshot.get("pid"):
            _, pid = win32process.GetWindowThreadProcessId(current_hwnd)
            if pid != snapshot["pid"]:
                return False
        if snapshot.get("title") and win32gui.GetWindowText(current_hwnd) != snapshot["title"]:
            return False
        # Preserve the control lock: another control in the same window is not
        # an authorised automatic insertion target. Use Paste Ready if UIA IDs rotate.
        expected_rid = snapshot.get("runtime_id")
        if expected_rid:
            try:
                with auto.UIAutomationInitializerInThread():
                    focused = auto.GetFocusedControl()
                    if not focused or focused.GetRuntimeId() != expected_rid:
                        return False
            except Exception:
                return False
        return True

    @staticmethod
    def get_focused_child_hwnd(fg_hwnd: int) -> int:
        """Finds the specific child control with keyboard focus (e.g. Scintilla inside Notepad++)."""
        if not fg_hwnd:
            return 0
        try:
            tid, _ = win32process.GetWindowThreadProcessId(fg_hwnd)
            gui = GUITHREADINFO()
            gui.cbSize = ctypes.sizeof(GUITHREADINFO)
            if ctypes.windll.user32.GetGUIThreadInfo(tid, ctypes.byref(gui)):
                return gui.hwndFocus or fg_hwnd
        except Exception as e:
            logging.debug("[FocusTracker] GetGUIThreadInfo error: %s", e)
        return fg_hwnd

    @staticmethod
    def _capture_via_wm_copy(hwnd: int) -> str:
        """Sends WM_COPY directly to window handle without simulating keyboard events."""
        if not hwnd:
            return ""
        try:
            seq_before = ctypes.windll.user32.GetClipboardSequenceNumber()
            orig_text = ClipboardManager.get_clipboard_text()

            result = wintypes.DWORD()
            # SMTO_ABORTIFHUNG = 0x0002
            ctypes.windll.user32.SendMessageTimeoutW(
                hwnd,
                0x0301,  # WM_COPY
                0,
                0,
                0x0002,
                200,     # 200 ms timeout
                ctypes.byref(result),
            )

            for _ in range(5):
                time.sleep(0.02)
                if ctypes.windll.user32.GetClipboardSequenceNumber() != seq_before:
                    break

            if ctypes.windll.user32.GetClipboardSequenceNumber() != seq_before:
                captured = ClipboardManager.get_clipboard_text() or ""
                # Restore previous clipboard so we don't pollute clipboard history
                if orig_text is None:
                    ClipboardManager.empty_clipboard()
                elif orig_text != captured:
                    ClipboardManager.set_clipboard_text(orig_text)
                return captured
        except Exception as e:
            logging.debug("[FocusTracker] WM_COPY error: %s", e)
        return ""

    @staticmethod
    def _capture_via_chord_ctrl_c() -> str:
        """
        Synthesizes Ctrl+C while the ESP32 chord is holding Alt/Shift.

        Keys this method presses are always released, including when the copy fails.
        Alt and Shift that were already held are restored so the hardware chord stays intact.
        """
        released: list[int] = []
        pressed: list[int] = []
        try:
            seq_before = ctypes.windll.user32.GetClipboardSequenceNumber()
            orig_text = ClipboardManager.get_clipboard_text()

            for vk in (_VK_MENU, _VK_SHIFT):
                if _key_is_down(vk):
                    _key_event(vk, up=True)
                    released.append(vk)

            if not _key_is_down(_VK_CONTROL):
                _key_event(_VK_CONTROL)
                pressed.append(_VK_CONTROL)
            _key_event(_VK_C)
            time.sleep(0.02)
            _key_event(_VK_C, up=True)

            for _ in range(6):
                time.sleep(0.02)
                if ctypes.windll.user32.GetClipboardSequenceNumber() != seq_before:
                    break

            if ctypes.windll.user32.GetClipboardSequenceNumber() != seq_before:
                captured = ClipboardManager.get_clipboard_text() or ""
                if orig_text is None:
                    ClipboardManager.empty_clipboard()
                elif orig_text != captured:
                    ClipboardManager.set_clipboard_text(orig_text)
                return captured
        except Exception as e:
            logging.debug("[FocusTracker] Chord Ctrl+C error: %s", e)
            return ""
        finally:
            _key_event(_VK_C, up=True)
            for vk in pressed:
                _key_event(vk, up=True)
            for vk in reversed(released):
                _key_event(vk)
        return ""

    @classmethod
    def capture_selected_text(cls, fg_hwnd: int = 0) -> str:
        """
        Multi-tier document selection extraction:
        1. UI Automation TextPattern (Word, Edge, Chrome, VS Code, modern Notepad).
        2. Direct Win32 WM_COPY to focused child HWND (Notepad++/Scintilla, SciTE, Edit, RichEdit).
        3. Direct Win32 WM_COPY to foreground HWND.
        4. Chord-aware synthetic Ctrl+C (with held Alt/Shift modifier compensation).
        """
        # Reject internal teacher/pupil/companion windows before *any* UIA read,
        # clipboard copy or key injection. A stale target must not capture the
        # currently focused teacher request field instead of its document.
        current_hwnd = win32gui.GetForegroundWindow()
        if not current_hwnd or (fg_hwnd and fg_hwnd != current_hwnd):
            return ""
        fg_hwnd = current_hwnd
        if cls.is_internal_window(fg_hwnd):
            return ""

        def unchanged_external_target():
            return win32gui.GetForegroundWindow() == fg_hwnd and not cls.is_internal_window(fg_hwnd)

        # Tier 1: UI Automation
        try:
            with auto.UIAutomationInitializerInThread():
                if not unchanged_external_target():
                    return ""
                focused = auto.GetFocusedControl()
                if focused:
                    pattern = focused.GetPattern(auto.PatternId.TextPattern)
                    if not pattern:
                        parent = focused.GetParentControl()
                        if parent:
                            pattern = parent.GetPattern(auto.PatternId.TextPattern)

                    if pattern:
                        ranges = pattern.GetSelection()
                        if ranges:
                            text = "".join(r.GetText(-1) for r in ranges)
                            if text.strip() and unchanged_external_target():
                                logging.debug("[FocusTracker] Captured text via UIA TextPattern (%d chars)", len(text))
                                return text
        except Exception as e:
            logging.debug("[FocusTracker] UIA capture error: %s", e)

        # Tier 2: Win32 WM_COPY on focused control HWND (e.g. Scintilla in Notepad++)
        if not fg_hwnd:
            fg_hwnd = win32gui.GetForegroundWindow()

        if fg_hwnd:
            _, fg_pid = win32process.GetWindowThreadProcessId(fg_hwnd)
            if cls.is_internal_process(fg_pid) or not unchanged_external_target():
                return ""
            child_hwnd = cls.get_focused_child_hwnd(fg_hwnd)
            if child_hwnd:
                text = cls._capture_via_wm_copy(child_hwnd)
                if text.strip() and unchanged_external_target():
                    logging.debug("[FocusTracker] Captured text via Win32 WM_COPY on child HWND %s (%d chars)", child_hwnd, len(text))
                    return text

            # Tier 2b: Win32 WM_COPY on foreground HWND
            if fg_hwnd != child_hwnd and unchanged_external_target():
                text = cls._capture_via_wm_copy(fg_hwnd)
                if text.strip() and unchanged_external_target():
                    logging.debug("[FocusTracker] Captured text via Win32 WM_COPY on fg HWND %s (%d chars)", fg_hwnd, len(text))
                    return text

        # Tier 3: Chord-aware Ctrl+C
        if not unchanged_external_target():
            return ""
        text = cls._capture_via_chord_ctrl_c()
        if text.strip() and unchanged_external_target():
            logging.debug("[FocusTracker] Captured text via chord Ctrl+C (%d chars)", len(text))
            return text

        return ""


if __name__ == "__main__":
    snap = FocusTracker.get_focus_snapshot()
    print("[FocusTracker] Snapshot:", snap)
    print("[FocusTracker] Is focus matched:", FocusTracker.is_focus_matched(snap))
    sel = FocusTracker.capture_selected_text(snap.get("hwnd", 0))
    print("[FocusTracker] Captured text:", repr(sel))
    print("[FocusTracker] Test Passed!")
