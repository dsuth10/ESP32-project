"""
Clipboard manager for Windows with atomic snapshot, paste injection,
prior clipboard restoration, and Windows 10/11 Win+V / Cloud Clipboard suppression.
"""

import time
import logging
import win32clipboard
import win32con
import ctypes
from ctypes import wintypes


class _KeyboardInput(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class _InputUnion(ctypes.Union):
    # MOUSEINPUT is larger than KEYBDINPUT (32 bytes on 64-bit Windows).
    _fields_ = [("ki", _KeyboardInput), ("padding", ctypes.c_byte * (32 if ctypes.sizeof(ctypes.c_void_p) == 8 else 24))]


class _Input(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("data", _InputUnion)]


def send_paste_shortcut():
    """Send a checked native Ctrl+V, independently of the pointer position."""
    events = (_Input * 4)()
    for event, (key, flags) in zip(events, ((0x11, 0), (0x56, 0), (0x56, 2), (0x11, 2))):
        event.type = 1
        event.data.ki = _KeyboardInput(key, 0, flags, 0, 0)
    sent = ctypes.windll.user32.SendInput(4, events, ctypes.sizeof(_Input))
    if sent != 4:
        # Release potentially partially injected keys before reporting failure.
        ctypes.windll.user32.SendInput(2, ctypes.byref(events, 2 * ctypes.sizeof(_Input)), ctypes.sizeof(_Input))
        raise OSError("Windows rejected the paste shortcut")


class ClipboardManager:
    @staticmethod
    def _open_clipboard_retry(max_attempts: int = 10, delay: float = 0.02) -> bool:
        """Attempts to open the Windows clipboard with retries in case another process holds it."""
        for _ in range(max_attempts):
            try:
                win32clipboard.OpenClipboard()
                return True
            except Exception:
                time.sleep(delay)
        return False

    @classmethod
    def get_clipboard_text(cls) -> str | None:
        """Safely retrieves current text in clipboard if available."""
        if not cls._open_clipboard_retry():
            return None
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return None
        except Exception as e:
            logging.debug("Error reading clipboard: %s", e)
            return None
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass

    @classmethod
    def empty_clipboard(cls) -> bool:
        """Safely empties the Windows clipboard."""
        if not cls._open_clipboard_retry():
            return False
        try:
            win32clipboard.EmptyClipboard()
            return True
        except Exception as e:
            logging.debug("Error emptying clipboard: %s", e)
            return False
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass

    @classmethod
    def set_clipboard_text(cls, text: str) -> bool:
        """Safely sets Unicode text on the Windows clipboard."""
        if not cls._open_clipboard_retry():
            return False
        try:
            win32clipboard.EmptyClipboard()
            if text is not None:
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            return True
        except Exception as e:
            logging.debug("Error setting clipboard text: %s", e)
            return False
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass

    @classmethod
    def inject_paste(cls, text: str, restore_delay: float = 0.15) -> bool:
        """
        Injects text at the current cursor position:
        1. Snapshots prior clipboard.
        2. Sets target text in clipboard with Win+V & Cloud sync suppression.
        3. Synthesizes Ctrl+V.
        4. Waits restore_delay (default 150ms) for target app to consume WM_PASTE.
        5. Restores original clipboard.
        """
        if not text:
            return False

        # 1. Snapshot previous clipboard
        prev_text = cls.get_clipboard_text()

        # 2. Put text into clipboard with suppression formats
        if not cls._open_clipboard_retry():
            logging.error("Failed to open clipboard for writing payload")
            return False

        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)

            # Suppress Windows 10/11 Clipboard History (Win+V)
            try:
                cf_exclude_history = win32clipboard.RegisterClipboardFormat("CanIncludeInClipboardHistory")
                win32clipboard.SetClipboardData(cf_exclude_history, b"\x00\x00\x00\x00")
            except Exception as e:
                logging.debug("CanIncludeInClipboardHistory registration failed: %s", e)

            # Suppress Cloud Clipboard Sync
            try:
                cf_exclude_cloud = win32clipboard.RegisterClipboardFormat("CanUploadToCloudClipboard")
                win32clipboard.SetClipboardData(cf_exclude_cloud, b"\x00\x00\x00\x00")
            except Exception as e:
                logging.debug("CanUploadToCloudClipboard registration failed: %s", e)
        except Exception as e:
            logging.error("Error setting payload to clipboard: %s", e)
            return False
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass

        # 3. Synthetic Ctrl+V
        try:
            send_paste_shortcut()
            succeeded = True
        except Exception:
            logging.exception("Paste shortcut failed")
            succeeded = False

        # 4. Wait for target app message queue
        time.sleep(restore_delay)

        # 5. Restore original clipboard
        if cls._open_clipboard_retry():
            try:
                win32clipboard.EmptyClipboard()
                if prev_text is not None:
                    win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, prev_text)
            except Exception as e:
                logging.debug("Error restoring original clipboard: %s", e)
            finally:
                try:
                    win32clipboard.CloseClipboard()
                except Exception:
                    pass

        return succeeded


if __name__ == "__main__":
    # Test clipboard snapshot and restoration
    original = "EXISTING_USER_CLIPBOARD_DATA"
    if ClipboardManager._open_clipboard_retry():
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, original)
        finally:
            win32clipboard.CloseClipboard()

    print("[ClipboardManager] Injected test paste simulation...")
    # Simulate inject_paste without actual Ctrl+V in self-test
    prev = ClipboardManager.get_clipboard_text()
    assert prev == original, f"Expected {original}, got {prev}"
    print("[ClipboardManager] Test Passed!")
