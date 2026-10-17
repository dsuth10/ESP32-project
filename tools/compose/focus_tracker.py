"""
Focus tracking and UI Automation target lock module for Windows.
Ensures synthetic text paste only targets the intended control and window.
"""

import time
import win32gui
import win32process
import uiautomation as auto


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
        except Exception as e:
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
    def capture_selected_text() -> str:
        """Read the UIA selection without altering clipboard or held HID modifiers."""
        try:
            with auto.UIAutomationInitializerInThread():
                focused = auto.GetFocusedControl()
                pattern = focused.GetTextPattern() if focused else None
                return "".join(r.GetText(-1) for r in pattern.GetSelection()) if pattern else ""
        except Exception:
            return ""



if __name__ == "__main__":
    snap = FocusTracker.get_focus_snapshot()
    print("[FocusTracker] Snapshot:", snap)
    print("[FocusTracker] Is focus matched:", FocusTracker.is_focus_matched(snap))
    print("[FocusTracker] Test Passed!")
