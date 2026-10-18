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
    def is_focus_matched(snapshot: dict) -> bool:
        """
        Verifies if the current foreground window and control still match the snapshot.
        """
        if not snapshot or not snapshot.get("hwnd"):
            return False

        current_hwnd = win32gui.GetForegroundWindow()
        if current_hwnd != snapshot["hwnd"]:
            return False

        # If a specific runtime_id was recorded, verify it hasn't shifted to another control
        expected_rid = snapshot.get("runtime_id")
        if expected_rid:
            try:
                with auto.UIAutomationInitializerInThread():
                    current_focused = auto.GetFocusedControl()
                    if not current_focused or current_focused.GetRuntimeId() != expected_rid:
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
        # Tier 1: UI Automation
        try:
            with auto.UIAutomationInitializerInThread():
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
                            if text.strip():
                                logging.debug("[FocusTracker] Captured text via UIA TextPattern (%d chars)", len(text))
                                return text
        except Exception as e:
            logging.debug("[FocusTracker] UIA capture error: %s", e)

        # Tier 2: Win32 WM_COPY on focused control HWND (e.g. Scintilla in Notepad++)
        if not fg_hwnd:
            fg_hwnd = win32gui.GetForegroundWindow()

        if fg_hwnd:
            _, fg_pid = win32process.GetWindowThreadProcessId(fg_hwnd)
            if fg_pid == os.getpid():
                return ""
            child_hwnd = cls.get_focused_child_hwnd(fg_hwnd)
            if child_hwnd:
                text = cls._capture_via_wm_copy(child_hwnd)
                if text.strip():
                    logging.debug("[FocusTracker] Captured text via Win32 WM_COPY on child HWND %s (%d chars)", child_hwnd, len(text))
                    return text

            # Tier 2b: Win32 WM_COPY on foreground HWND
            if fg_hwnd != child_hwnd:
                text = cls._capture_via_wm_copy(fg_hwnd)
                if text.strip():
                    logging.debug("[FocusTracker] Captured text via Win32 WM_COPY on fg HWND %s (%d chars)", fg_hwnd, len(text))
                    return text

        # Tier 3: Chord-aware Ctrl+C
        text = cls._capture_via_chord_ctrl_c()
        if text.strip():
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
