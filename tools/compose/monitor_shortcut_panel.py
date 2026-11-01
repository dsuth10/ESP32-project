"""Teacher setup for the classroom display and classroom-app window choice."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from monitor_shortcut import (
    APP_CHROME,
    APP_ONENOTE,
    APP_WORD,
    CLASSROOM_APP_IDS,
    DEFAULT_PROFILES,
    PROFILE_HOME,
    WINDOW_MOST_RECENT,
    ActionReceipt,
    MonitorShortcutController,
    active_profile,
    active_profile_name,
    app_settings,
    set_app_settings,
)
from window_monitor_manager import MISSING_DISPLAY_MESSAGE, MonitorInfo, classroom_app


MOST_RECENT_LABEL = 'Most recent'
APP_TAB_ORDER = (APP_ONENOTE, APP_WORD, APP_CHROME)


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
            text='Open or focus OneNote, Word, Chrome or the Teaching Board pupil window on the named '
                 'classroom display. This does not insert text or images and does not grant Paste Ready.',
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

        self.app_tabs = ttk.Notebook(self)
        self.app_tabs.grid(row=3, column=0, columnspan=3, sticky='ew', pady=(8, 4))
        self._app_widgets: dict[str, dict] = {}
        for app_id in APP_TAB_ORDER:
            self._build_app_tab(app_id)
        # Existing tests and OneNote helpers keep using these OneNote widgets.
        onenote = self._app_widgets[APP_ONENOTE]
        self.window_var = onenote['window_var']
        self.window_box = onenote['window_box']
        self.maximise_var = onenote['maximise_var']

        self.hotkey_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self,
            text='Enable classroom app shortcuts (off by default)',
            variable=self.hotkey_var, command=self._hotkey_changed,
        ).grid(row=4, column=0, columnspan=3, sticky='w', pady=(6, 0))
        ttk.Label(
            self,
            text='When enabled: F18 OneNote, F19 Word, F20 Chrome, F21 Board, '
                 'or Ctrl+Alt+Shift+F6 / F5 / F4 / F3. No handheld buttons in this slice.',
            wraplength=820,
        ).grid(row=5, column=0, columnspan=3, sticky='w', pady=(0, 6))

        buttons = ttk.Frame(self)
        buttons.grid(row=6, column=0, columnspan=3, sticky='w', pady=12)
        ttk.Button(buttons, text='Test classroom display', command=self.test_action).pack(side='left', padx=(0, 8))
        ttk.Button(
            buttons, text='Open OneNote on classroom display', command=self.open_action,
        ).pack(side='left', padx=(0, 8))
        ttk.Button(buttons, text='Open Word', command=lambda: self.open_app_action(APP_WORD)).pack(
            side='left', padx=(0, 8))
        ttk.Button(buttons, text='Open Chrome', command=lambda: self.open_app_action(APP_CHROME)).pack(
            side='left', padx=(0, 8))
        ttk.Button(buttons, text='Bring Board forward', command=self.board_action).pack(side='left')

        self.status = ttk.Label(self, text='Classroom display is not assigned yet.', wraplength=820, justify='left')
        self.status.grid(row=7, column=0, columnspan=3, sticky='ew', pady=(8, 0))

        self._windows: list = []
        self._windows_by_app: dict[str, list] = {app_id: [] for app_id in CLASSROOM_APP_IDS}
        self.reload()

    def _build_app_tab(self, app_id: str) -> None:
        app = classroom_app(app_id)
        frame = ttk.Frame(self.app_tabs, padding=8)
        self.app_tabs.add(frame, text=app.label)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text=f'{app.label} window').grid(row=0, column=0, sticky='w', padx=(0, 8), pady=4)
        window_var = tk.StringVar(value=MOST_RECENT_LABEL)
        window_box = ttk.Combobox(frame, textvariable=window_var, state='readonly', width=56)
        window_box.grid(row=0, column=1, sticky='ew', pady=4)
        window_box.bind('<<ComboboxSelected>>', lambda _event=None, item=app_id: self._window_changed(item))
        ttk.Button(
            frame, text='Refresh windows', command=lambda item=app_id: self.refresh_windows(app_id=item),
        ).grid(row=0, column=2, sticky='e', padx=4)
        maximise_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame, text=f'Maximise {app.label} on the classroom display',
            variable=maximise_var, command=lambda item=app_id: self._maximise_changed(item),
        ).grid(row=1, column=0, columnspan=3, sticky='w', pady=6)
        self._app_widgets[app_id] = {
            'window_var': window_var,
            'window_box': window_box,
            'maximise_var': maximise_var,
        }

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
        self.hotkey_var.set(bool(settings.get('hotkey_enabled', False)))
        for app_id in CLASSROOM_APP_IDS:
            self._app_widgets[app_id]['maximise_var'].set(bool(app_settings(profile, app_id).get('maximise', True)))
        self.refresh_windows(select_saved=True)

    def _profile_changed(self, _event=None) -> None:
        settings = self.controller.load()
        name = self.profile_var.get()
        if name in DEFAULT_PROFILES:
            settings['active_profile'] = name
            self.controller.save(settings)
        self.reload()

    def _maximise_changed(self, app_id: str | None = None) -> None:
        settings = self.controller.load()
        profile = active_profile(settings)
        target = app_id or APP_ONENOTE
        set_app_settings(profile, target, {'maximise': bool(self._app_widgets[target]['maximise_var'].get())})
        self.controller.save(settings)

    def _hotkey_changed(self) -> None:
        settings = self.controller.load()
        settings['hotkey_enabled'] = bool(self.hotkey_var.get())
        self.controller.save(settings)
        if self.on_hotkey_changed:
            self.on_hotkey_changed(bool(self.hotkey_var.get()))

    def refresh_windows(self, select_saved: bool = False, app_id: str | None = None) -> None:
        targets = [app_id] if app_id else list(CLASSROOM_APP_IDS)
        for target in targets:
            windows = self.controller.list_app_windows(target)
            self._windows_by_app[target] = windows
            if target == APP_ONENOTE:
                self._windows = windows
            labels = [MOST_RECENT_LABEL]
            for window in windows:
                labels.append(self._window_label(target, window))
            widgets = self._app_widgets[target]
            widgets['window_box']['values'] = labels
            if select_saved:
                settings = self.controller.load()
                chosen_settings = app_settings(active_profile(settings), target)
                if chosen_settings.get('window_choice') == 'chosen' and chosen_settings.get('chosen_window'):
                    chosen = chosen_settings['chosen_window']
                    for window in windows:
                        if window.hwnd == int(chosen.get('hwnd') or 0):
                            widgets['window_var'].set(self._window_label(target, window))
                            break
                    else:
                        widgets['window_var'].set(MOST_RECENT_LABEL)
                else:
                    widgets['window_var'].set(MOST_RECENT_LABEL)
            elif widgets['window_var'].get() not in labels:
                widgets['window_var'].set(MOST_RECENT_LABEL)

    def _window_label(self, app_id: str, window) -> str:
        label = classroom_app(app_id).label
        title = window.title.strip() if window.title else f'{label} (untitled)'
        return f'{title}  [hwnd {window.hwnd}]'

    def _window_changed(self, app_id: str | None = None, _event=None) -> None:
        target = app_id or APP_ONENOTE
        settings = self.controller.load()
        profile = active_profile(settings)
        label = self._app_widgets[target]['window_var'].get()
        if label == MOST_RECENT_LABEL:
            set_app_settings(profile, target, {'window_choice': WINDOW_MOST_RECENT, 'chosen_window': None})
        else:
            for window in self._windows_by_app.get(target, []):
                if self._window_label(target, window) == label:
                    set_app_settings(profile, target, {
                        'window_choice': 'chosen',
                        'chosen_window': {
                            'hwnd': window.hwnd,
                            'pid': window.pid,
                            'title': window.title,
                            'executable': window.executable,
                        },
                    })
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

    def open_app_action(self, app_id: str) -> None:
        self._show_receipt(self.controller.open_app_on_classroom_display(app_id))

    def board_action(self) -> None:
        self._show_receipt(self.controller.bring_board_to_classroom_display())

    def _show_receipt(self, receipt: ActionReceipt) -> None:
        colour = '#10B981' if receipt.kind == 'ok' else '#F59E0B'
        if receipt.kind in {'placement_failed', 'launch_failed', 'window_gone', 'board_unavailable'}:
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
