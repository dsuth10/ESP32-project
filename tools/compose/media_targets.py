"""Windows image insertion with explicit target and selection checks.

Office/clipboard imports are lazy so library and server tests run without Office.
"""
from __future__ import annotations

import ctypes
import io
import os
from pathlib import Path

from PIL import Image


def foreground_target() -> dict:
    import win32gui, win32process
    hwnd = win32gui.GetForegroundWindow()
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    try:
        text, length = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
        if not handle or not kernel.QueryFullProcessImageNameW(handle, 0, text, ctypes.byref(length)):
            raise RuntimeError("The foreground application's identity could not be checked.")
        executable = Path(text.value).name.upper()
    finally:
        if handle:
            kernel.CloseHandle(handle)
    if pid == os.getpid():
        raise ValueError("Focus your Word or OneNote document, then press Paste Ready.")
    return {"hwnd": hwnd, "pid": pid, "executable": executable}


def target_matches(expected: dict, current: dict) -> bool:
    return bool(expected and all(expected.get(k) == current.get(k) for k in ("hwnd", "pid", "executable")))


def _word():
    import win32com.client
    return win32com.client.GetActiveObject("Word.Application")


def capture_target(*, allow_onenote_keyboard_paste: bool = False) -> dict:
    target = foreground_target()
    if target["executable"] == "WINWORD.EXE":
        app = _word()
        if int(app.ActiveWindow.Hwnd) != target["hwnd"]:
            raise ValueError("Word's active document does not match the foreground window.")
        selection = app.Selection.Range
        if selection.Start != selection.End:
            raise ValueError("Collapse the Word selection to a caret before inserting an image.")
        target.update(document=str(app.ActiveDocument.FullName), start=int(selection.Start), end=int(selection.End))
    elif target["executable"] == "ONENOTE.EXE":
        selection = _onenote_selection_collapsed()
        target["selection_checked"] = selection is True
        if selection is False:
            raise ValueError("Collapse the OneNote selection to a caret before inserting an image.")
        if selection is None and allow_onenote_keyboard_paste:
            # The user explicitly permits normal Ctrl+V semantics at the current
            # canvas when this edition cannot expose its selection through UIA.
            target["keyboard_context"] = _onenote_keyboard_context(target["hwnd"])
            target["explicit_keyboard_paste"] = True
        elif selection is not True:
            raise ValueError("OneNote selection could not be verified. Use Copy image and paste manually.")
    else:
        raise ValueError("Image insertion currently supports Word and OneNote desktop only.")
    return target


def _onenote_selection_collapsed() -> bool | None:
    """True = caret, False = selected content, None = inspection unavailable."""
    try:
        import uiautomation as auto
        with auto.UIAutomationInitializerInThread():
            control = auto.GetFocusedControl()
            for _ in range(3):
                if not control:
                    break
                pattern = control.GetPattern(auto.PatternId.TextPattern)
                if pattern:
                    ranges = pattern.GetSelection()
                    return all(r.CompareEndpoints(0, r, 1) == 0 for r in ranges) if ranges else None
                control = control.GetParentControl()
    except Exception:
        return None
    return None


def _onenote_keyboard_context(hwnd: int) -> dict:
    """Bind explicit keyboard delivery to the focused OneNote document canvas."""
    import win32gui, win32process
    from focus_tracker import GUITHREADINFO

    if win32gui.GetForegroundWindow() != hwnd:
        raise ValueError("OneNote target changed. Image retained in READY.")
    thread_id, _ = win32process.GetWindowThreadProcessId(hwnd)
    info = GUITHREADINFO()
    info.cbSize = ctypes.sizeof(GUITHREADINFO)
    if not ctypes.windll.user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
        raise ValueError("Focus a OneNote page before pressing Paste Ready.")
    focused = info.hwndFocus
    if (not focused or win32gui.GetClassName(focused) != "OneNote::DocumentCanvas"
            or win32gui.GetAncestor(focused, 2) != hwnd):
        raise ValueError("Focus the OneNote page body before pressing Paste Ready.")
    title = win32gui.GetWindowText(hwnd)
    if not title:
        raise ValueError("OneNote page identity is unavailable. Image retained in READY.")
    return {"focus_hwnd": int(focused), "window_title": title}


def copy_image(path: Path) -> None:
    import win32clipboard, win32con
    # Bitmap clipboard fallback is deliberately opaque: PNG also preserves alpha.
    with Image.open(path) as source:
        rgba = source.convert("RGBA")
        white = Image.new("RGB", rgba.size, "white")
        white.paste(rgba, mask=rgba.getchannel("A"))
        bitmap, png = io.BytesIO(), io.BytesIO()
        white.save(bitmap, "BMP")
        rgba.save(png, "PNG")
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB, bitmap.getvalue()[14:])
        win32clipboard.SetClipboardData(win32clipboard.RegisterClipboardFormat("PNG"), png.getvalue())
        for name in ("CanIncludeInClipboardHistory", "CanUploadToCloudClipboard"):
            win32clipboard.SetClipboardData(win32clipboard.RegisterClipboardFormat(name), b"\x00" * 4)
    finally:
        win32clipboard.CloseClipboard()


def insert_image(path: Path, target: dict) -> dict:
    if not target_matches(target, foreground_target()):
        raise ValueError("Target changed. Image remains queued; select the destination again.")
    if target["executable"] == "WINWORD.EXE":
        app = _word()
        selected = app.Selection.Range
        if (int(app.ActiveWindow.Hwnd) != target["hwnd"] or str(app.ActiveDocument.FullName) != target.get("document")
                or int(selected.Start) != target.get("start") or int(selected.End) != target.get("end")
                or selected.Start != selected.End):
            raise ValueError("Word document, caret or selection changed. Image remains queued.")
        if not target_matches(target, foreground_target()):
            raise ValueError("Target changed before insertion.")
        picture = app.ActiveDocument.InlineShapes.AddPicture(FileName=str(path.resolve()), LinkToFile=False,
                                                            SaveWithDocument=True, Range=selected.Duplicate)
        return {"transport": "word_com", "verification": "office_object_returned", "position": int(picture.Range.Start),
                "message": "Word returned an embedded picture. Check placement and save the document."}
    if target["executable"] == "ONENOTE.EXE":
        selection = _onenote_selection_collapsed()
        explicit = target.get("explicit_keyboard_paste") is True
        if selection is False:
            raise ValueError("Collapse the OneNote selection to a caret before inserting an image.")
        if selection is not True and not explicit:
            raise ValueError("Target selection could not be verified. Use Copy image and paste manually.")
        if explicit and target.get("keyboard_context") != _onenote_keyboard_context(target["hwnd"]):
            raise ValueError("OneNote page or focus changed. Image was not pasted.")
        copy_image(path)
        if not target_matches(target, foreground_target()):
            raise ValueError("Target changed. Image was copied but no paste was sent.")
        if explicit:
            if target.get("keyboard_context") != _onenote_keyboard_context(target["hwnd"]):
                raise ValueError("OneNote page or focus changed. Image was copied but no paste was sent.")
        elif _onenote_selection_collapsed() is not True:
            raise ValueError("OneNote selection changed. Image was copied but no paste was sent.")
        from clipboard_manager import send_paste_shortcut
        send_paste_shortcut()
        return {"transport": "onenote_clipboard", "verification": "paste_requested",
                "explicit_keyboard_paste": explicit,
                "selection_verification": "collapsed" if selection is True else "unavailable",
                "message": "OneNote paste shortcut sent. Check placement and save/reopen; insertion is not independently verified."}
    raise ValueError("Target selection could not be verified. Use Copy image and paste manually.")
