"""Render Classroom display UI on a private X display for evidence screenshots."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from monitor_shortcut import MonitorShortcutController
from monitor_shortcut_panel import MonitorShortcutPanel
from window_monitor_manager import AppWindow, FakeWindowMonitorBackend, MonitorInfo, Rect


def monitor(handle, name, left, path):
    return MonitorInfo(
        handle, name, f'\\\\.\\DISPLAY{handle}', path, 'DEL', f'{handle:04X}',
        Rect(left, 0, left + 960, 540), Rect(left, 0, left + 960, 500), 96)


def grab(root, path: Path):
    root.update()
    root.update_idletasks()
    path.parent.mkdir(parents=True, exist_ok=True)
    image = ImageGrab.grab(bbox=(0, 0, 920, 580))
    image.save(path)
    print(path)


def main(destination: Path):
    import tkinter as tk

    backend = FakeWindowMonitorBackend(
        [monitor(1, 'Laptop', 0, '\\\\?\\DISPLAY#LAPTOP'),
         monitor(2, 'Classroom panel', 960, '\\\\?\\DISPLAY#BOARD')],
        [AppWindow(21, 300, 'Year 8 — Water cycle', 'ONENOTE.EXE', Rect(40, 40, 800, 500), last_foreground_at=3),
         AppWindow(22, 300, 'Staff notebook', 'ONENOTE.EXE', Rect(80, 80, 820, 540), last_foreground_at=1)],
    )
    controller = MonitorShortcutController(backend=backend, root=destination / 'settings', popup=lambda _t: None)
    root = tk.Tk()
    root.title('Classroom display')
    root.geometry('920x580+0+0')
    panel = MonitorShortcutPanel(root, controller)
    panel.pack(fill='both', expand=True)
    root.lift()
    grab(root, destination / 'classroom-display-panel.png')

    panel.identify_screens()
    root.update()
    if len(panel._overlays) >= 2:
        panel._overlays[0].withdraw()
        overlay = panel._overlays[1]
        overlay.geometry('920x580+0+0')
        overlay.update()
        grab(overlay, destination / 'identify-overlay-classroom.png')
    panel._assign_from_overlay(backend.monitors[1])
    root.geometry('920x580+0+0')
    grab(root, destination / 'classroom-display-assigned.png')
    panel.close()
    root.destroy()


if __name__ == '__main__':
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/tmp/monitor-onenote-ui')
    main(out)
