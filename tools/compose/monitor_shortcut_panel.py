"""Teacher setup for the classroom display and OneNote window choice."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from monitor_shortcut import (
    DEFAULT_PROFILES,
    KIND_MISSING_DISPLAY,
    PROFILE_HOME,
    WINDOW_MOST_RECENT,
    ActionReceipt,
    MonitorShortcutController,
    active_profile,
    active_profile_name,
)
from window_monitor_manager import MISSING_DISPLAY_MESSAGE, MonitorInfo


MOST_RECENT_LABEL = 'Most recent'


class MonitorShortcutPanel(ttk.Frame):
    def __init__(self, parent, controller: MonitorShortcutController, on_status=None,
                 on_hotkey_changed=None):
        super().__init__(parent, padding=14)
        self.controller = controller
        self.on_status = on_status or (lambda text, colour=None: None)
        self.on_hotkey_changed = on_hotkey_changed
        self._overlays: list[tk.Toplevel] = []
        self.columnconfigure(1, weight=1)
        try:
            import tkinter.font as tkfont
            for name in ('TkDefaultFont', 'TkTextFont', 'TkHeadingFont'):
                tkfont.nametofont(name).configure(size=10)
        except Exception:
            pass

        ttk.Label(
            self,
            text='Open or focus desktop OneNote on the named classroom display. '
                 'This does not insert text or images and does not grant Paste Ready.',
            wraplength=820,
        ).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 10))

        ttk.Label(self, text='Location profile').grid(row=1, column=0, sticky='w', padx=(0, 8), pady=4)
        self.profile_var = tk.StringVar(value=PROFILE_HOME)
        self.profile_box = ttk.Combobox(
            self, textvariable=self.profile_var, values=list(DEFAULT_PROFILES), state='readonly', width=24)
        self.profile_box.grid(row=1, column=1, sticky='w', pady=4)
        self.profile_box.bind('<<ComboboxSelected>>', self._profile_changed)

        ttk.Label(self, text='Classroom display').grid(row=2, column=0, sticky='w', padx=(0, 8), pady=4)
        self.display_var = tk.StringVar(value='Not assigned')
        ttk.Label(self, textvariable=self.display_var, wraplength=520).grid(row=2, column=1, sticky='w', pady=4)
        ttk.Button(self, text='Identify screens', command=self.identify_screens).grid(
            row=2, column=2, sticky='e', padx=4)

        ttk.Label(self, text='OneNote window').grid(row=3, column=0, sticky='w', padx=(0, 8), pady=4)
        self.window_var = tk.StringVar(value=MOST_RECENT_LABEL)
        self.window_box = ttk.Combobox(self, textvariable=self.window_var, state='readonly', width=56)
        self.window_box.grid(row=3, column=1, sticky='ew', pady=4)
        self.window_box.bind('<<ComboboxSelected>>', self._window_changed)
        ttk.Button(self, text='Refresh windows', command=self.refresh_windows).grid(
            row=3, column=2, sticky='e', padx=4)

        self.maximise_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            self, text='Maximise OneNote on the classroom display',
            variable=self.maximise_var, command=self._maximise_changed,
        ).grid(row=4, column=0, columnspan=3, sticky='w', pady=6)

        self.hotkey_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self,
            text='Optional keyboard chord (off by default): F18 or Ctrl+Alt+Shift+F6. '
                 'No handheld button in this slice.',
            variable=self.hotkey_var, command=self._hotkey_changed,
        ).grid(row=5, column=0, columnspan=3, sticky='w', pady=4)

        buttons = ttk.Frame(self)
        buttons.grid(row=6, column=0, columnspan=3, sticky='w', pady=12)
        ttk.Button(buttons, text='Test classroom display', command=self.test_action).pack(side='left', padx=(0, 8))
        ttk.Button(
            buttons, text='Open OneNote on classroom display', command=self.open_action,
        ).pack(side='left')

        self.status = ttk.Label(self, text='Classroom display is not assigned yet.', wraplength=820, justify='left')
        self.status.grid(row=7, column=0, columnspan=3, sticky='ew', pady=(8, 0))

        self._windows: list = []
        self.reload()

    def reload(self) -> None:
        settings = self.controller.load()
        self.profile_var.set(active_profile_name(settings))
        profile = active_profile(settings)
        assigned = profile.get('classroom_display') or {}
        if assigned:
            name = assigned.get('friendly_name') or assigned.get('device_name') or 'Classroom display'
            self.display_var.set(name)
        else:
            self.display_var.set('Not assigned')
        self.maximise_var.set(bool(profile.get('maximise', True)))
        self.hotkey_var.set(bool(settings.get('hotkey_enabled', False)))
        self.refresh_windows(select_saved=True)

    def _profile_changed(self, _event=None) -> None:
        settings = self.controller.load()
        name = self.profile_var.get()
        if name in DEFAULT_PROFILES:
            settings['active_profile'] = name
            self.controller.save(settings)
        self.reload()

    def _maximise_changed(self) -> None:
        settings = self.controller.load()
        active_profile(settings)['maximise'] = bool(self.maximise_var.get())
        self.controller.save(settings)

    def _hotkey_changed(self) -> None:
        settings = self.controller.load()
        settings['hotkey_enabled'] = bool(self.hotkey_var.get())
        self.controller.save(settings)
        if self.on_hotkey_changed:
            self.on_hotkey_changed(bool(self.hotkey_var.get()))

    def refresh_windows(self, select_saved: bool = False) -> None:
        self._windows = self.controller.list_onenote_windows()
        labels = [MOST_RECENT_LABEL]
        for window in self._windows:
            labels.append(self._window_label(window))
        self.window_box['values'] = labels
        if select_saved:
            settings = self.controller.load()
            profile = active_profile(settings)
            if profile.get('onenote_window_choice') == 'chosen' and profile.get('chosen_window'):
                chosen = profile['chosen_window']
                for window in self._windows:
                    if window.hwnd == int(chosen.get('hwnd') or 0):
                        self.window_var.set(self._window_label(window))
                        return
                self.window_var.set(MOST_RECENT_LABEL)
                return
            self.window_var.set(MOST_RECENT_LABEL)
            return
        if self.window_var.get() not in labels:
            self.window_var.set(MOST_RECENT_LABEL)

    def _window_label(self, window) -> str:
        title = window.title.strip() if window.title else 'OneNote (untitled)'
        return f'{title}  [hwnd {window.hwnd}]'

    def _window_changed(self, _event=None) -> None:
        settings = self.controller.load()
        profile = active_profile(settings)
        label = self.window_var.get()
        if label == MOST_RECENT_LABEL:
            profile['onenote_window_choice'] = WINDOW_MOST_RECENT
            profile['chosen_window'] = None
        else:
            for window in self._windows:
                if self._window_label(window) == label:
                    profile['onenote_window_choice'] = 'chosen'
                    profile['chosen_window'] = {
                        'hwnd': window.hwnd,
                        'pid': window.pid,
                        'title': window.title,
                        'executable': window.executable,
                    }
                    break
        self.controller.save(settings)

    def identify_screens(self) -> None:
        self.close_overlays()
        monitors = self.controller.list_monitors()
        if not monitors:
            self._set_status(MISSING_DISPLAY_MESSAGE, '#F59E0B')
            return
        for index, monitor in enumerate(monitors, start=1):
            overlay = tk.Toplevel(self)
            overlay.title(f'Screen {index}')
            overlay.configure(bg='#111827')
            geometry = (
                f'{max(320, monitor.bounds.width)}x{max(200, monitor.bounds.height)}'
                f'+{monitor.bounds.left}+{monitor.bounds.top}')
            try:
                overlay.geometry(geometry)
            except tk.TclError:
                overlay.geometry('480x240')
            try:
                overlay.attributes('-topmost', True)
            except tk.TclError:
                pass
            name = monitor.friendly_name or f'Display {index}'
            tk.Label(
                overlay, text=f'{index}', font=('Segoe UI', 48, 'bold'),
                fg='#F8FAFC', bg='#111827',
            ).pack(pady=(40, 8))
            tk.Label(
                overlay, text=name, font=('Segoe UI', 16), fg='#E5E7EB', bg='#111827',
                wraplength=600,
            ).pack()
            ttk.Button(
                overlay, text='Use as Classroom display',
                command=lambda item=monitor: self._assign_from_overlay(item),
            ).pack(pady=16)
            ttk.Button(overlay, text='Close', command=self.close_overlays).pack()
            self._overlays.append(overlay)

    def _assign_from_overlay(self, monitor: MonitorInfo) -> None:
        self.controller.assign_monitor(monitor)
        self.close_overlays()
        self.reload()
        self._set_status(f'Classroom display is now {monitor.friendly_name or "this screen"}.', '#10B981')

    def close_overlays(self) -> None:
        for overlay in self._overlays:
            try:
                overlay.destroy()
            except tk.TclError:
                pass
        self._overlays.clear()

    def test_action(self) -> None:
        self._show_receipt(self.controller.test_placement())

    def open_action(self) -> None:
        self._show_receipt(self.controller.open_onenote_on_classroom_display())

    def _show_receipt(self, receipt: ActionReceipt) -> None:
        colour = '#10B981' if receipt.kind == 'ok' else '#F59E0B'
        if receipt.kind in {'placement_failed', 'launch_failed', 'window_gone'}:
            colour = '#EF4444'
        text = receipt.message
        if receipt.warning:
            text = f'{receipt.warning} {receipt.message}'.strip()
        self._set_status(text, colour)

    def _set_status(self, text: str, colour: str | None = None) -> None:
        self.status.configure(text=text)
        self.on_status(text, colour)

    def close(self) -> None:
        self.close_overlays()
