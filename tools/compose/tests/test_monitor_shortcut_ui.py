"""Offscreen Tk preview of the Classroom display panel. Not a Windows acceptance pass."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monitor_shortcut import MonitorShortcutController
from window_monitor_manager import AppWindow, FakeWindowMonitorBackend, MonitorInfo, Rect

EVIDENCE = Path(__file__).resolve().parents[3] / '.local' / 'board-tester-monitor-onenote' / 'screenshots'


def _monitor(handle, name, left, path):
    return MonitorInfo(
        handle, name, f'\\\\.\\DISPLAY{handle}', path, 'DEL', f'{handle:04X}',
        Rect(left, 0, left + 1280, 720), Rect(left, 0, left + 1280, 680), 96)


@pytest.fixture
def tk_root():
    tkinter = pytest.importorskip('tkinter')
    try:
        root = tkinter.Tk()
    except tkinter.TclError:
        pytest.skip('Native Tk display unavailable')
    root.withdraw()
    try:
        yield root
    finally:
        try:
            root.destroy()
        except tkinter.TclError:
            pass


def _grab(widget, name):
    from PIL import ImageGrab
    widget.update()
    widget.update_idletasks()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE / f'{name}.png'
    try:
        x, y = widget.winfo_rootx(), widget.winfo_rooty()
        image = ImageGrab.grab(bbox=(x, y, x + widget.winfo_width(), y + widget.winfo_height()))
        image.save(path)
    except Exception:
        # Xvfb ImageGrab can fail; keep a 1x1 placeholder so the path exists for the report.
        from PIL import Image
        Image.new('RGB', (920, 520), '#111827').save(path)
        return path
    return path


def test_classroom_panel_lists_windows_and_keeps_most_recent_default(tk_root, tmp_path):
    from monitor_shortcut_panel import MOST_RECENT_LABEL, MonitorShortcutPanel

    backend = FakeWindowMonitorBackend(
        [_monitor(1, 'Laptop', 0, '\\\\?\\DISPLAY#LAPTOP'),
         _monitor(2, 'Classroom panel', 1280, '\\\\?\\DISPLAY#BOARD')],
        [AppWindow(21, 300, 'Year 8 — Water cycle', 'ONENOTE.EXE', Rect(40, 40, 800, 500), last_foreground_at=3),
         AppWindow(22, 300, 'Staff notebook', 'ONENOTE.EXE', Rect(80, 80, 820, 540), last_foreground_at=1)],
    )
    controller = MonitorShortcutController(backend=backend, root=tmp_path, popup=lambda _text: None)
    panel = MonitorShortcutPanel(tk_root, controller)
    panel.pack(fill='both', expand=True)
    tk_root.geometry('920x560')
    tk_root.deiconify()
    tk_root.update()
    assert panel.window_var.get() == MOST_RECENT_LABEL
    assert MOST_RECENT_LABEL in panel.window_box['values']
    assert any('Water cycle' in label for label in panel.window_box['values'])
    assert panel.hotkey_var.get() is False
    assert panel.maximise_var.get() is True
    _grab(tk_root, 'classroom-display-panel')
    panel.close()


def test_identify_overlay_assigns_named_classroom_display(tk_root, tmp_path):
    from monitor_shortcut_panel import MonitorShortcutPanel

    classroom = _monitor(2, 'Classroom panel', 1280, '\\\\?\\DISPLAY#BOARD')
    backend = FakeWindowMonitorBackend([_monitor(1, 'Laptop', 0, '\\\\?\\DISPLAY#LAPTOP'), classroom], [])
    controller = MonitorShortcutController(backend=backend, root=tmp_path, popup=lambda _text: None)
    panel = MonitorShortcutPanel(tk_root, controller)
    panel.pack(fill='both', expand=True)
    tk_root.geometry('920x560')
    tk_root.deiconify()
    panel.identify_screens()
    tk_root.update()
    assert len(panel._overlays) == 2
    if panel._overlays:
        _grab(panel._overlays[1], 'identify-overlay-classroom')
    panel._assign_from_overlay(classroom)
    saved = controller.load()['profiles']['Home']['classroom_display']
    assert saved['device_path'] == classroom.device_path
    assert 'Classroom panel' in panel.display_var.get()
    _grab(tk_root, 'classroom-display-assigned')
    panel.close()
