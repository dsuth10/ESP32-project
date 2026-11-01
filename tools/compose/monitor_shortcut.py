"""Open or focus desktop OneNote on a teacher-named classroom display.

Desktop-only: no firmware, no Office COM navigation, no typing injection.
A successful placement is not a Paste Ready or insert-permission grant.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import time

from companion_settings import data_directory
from window_monitor_manager import (
    ALLOWLISTED_LAUNCH_URI,
    MISSING_DISPLAY_MESSAGE,
    ONENOTE_EXECUTABLE,
    AppWindow,
    MonitorInfo,
    WindowMonitorBackend,
    create_backend,
    is_allowlisted_launch,
    verify_placement,
)


SETTINGS_NAME = 'monitor_shortcut.json'
SETTINGS_VERSION = 1
ROLE_CLASSROOM = 'classroom_display'
PROFILE_HOME = 'Home'
PROFILE_WORK = 'Work'
DEFAULT_PROFILES = (PROFILE_HOME, PROFILE_WORK)
WINDOW_MOST_RECENT = 'most_recent'
KIND_OK = 'ok'
KIND_MISSING_DISPLAY = 'missing_display'
KIND_NEEDS_CONFIRM = 'needs_confirm'
KIND_UNASSIGNED = 'unassigned'
KIND_AMBIGUOUS = 'ambiguous'
KIND_LAUNCH_FAILED = 'launch_failed'
KIND_WINDOW_GONE = 'window_gone'
KIND_PLACEMENT_FAILED = 'placement_failed'
KIND_FOREGROUND_FAILED = 'foreground_failed'
DISPLAY_SET_CHANGED_MESSAGE = (
    'The connected displays have changed. Confirm the classroom display before moving OneNote.')
UNASSIGNED_MESSAGE = 'Choose the classroom display first using Identify screens.'
AMBIGUOUS_WINDOWS_MESSAGE = (
    'Several OneNote windows are open. Choose one in Classroom display, or bring the intended notebook to the front once.')
CHOSEN_GONE_AMBIGUOUS_MESSAGE = (
    'The chosen OneNote window is no longer open. Several OneNote windows are open — choose one in Classroom display.')


@dataclass
class ActionReceipt:
    kind: str
    message: str
    hwnd: int = 0
    launched: bool = False
    placed: bool = False
    foreground: bool = False
    monitor_role: str = ROLE_CLASSROOM
    monitor_key: str = ''
    profile: str = PROFILE_HOME
    work_area: tuple[int, int, int, int] | None = None
    warning: str = ''
    window_title: str = ''
    granted_paste_permission: bool = False
    paste_ready_target: bool = False

    def as_dict(self) -> dict:
        return {
            'kind': self.kind,
            'message': self.message,
            'hwnd': self.hwnd,
            'launched': self.launched,
            'placed': self.placed,
            'foreground': self.foreground,
            'monitor_role': self.monitor_role,
            'monitor_key': self.monitor_key,
            'profile': self.profile,
            'work_area': list(self.work_area) if self.work_area else None,
            'warning': self.warning,
            'window_title': self.window_title,
            'granted_paste_permission': False,
            'paste_ready_target': False,
        }


def default_profile() -> dict:
    return {
        'classroom_display': None,
        'last_seen_identities': [],
        'onenote_window_choice': WINDOW_MOST_RECENT,
        'chosen_window': None,
        'maximise': True,
        'onenote_launch': ALLOWLISTED_LAUNCH_URI,
    }


def default_settings() -> dict:
    return {
        'version': SETTINGS_VERSION,
        'active_profile': PROFILE_HOME,
        'hotkey_enabled': False,
        'profiles': {name: default_profile() for name in DEFAULT_PROFILES},
    }


def settings_path(root: Path | None = None) -> Path:
    return Path(root or data_directory()) / SETTINGS_NAME


def load_shortcut_settings(root: Path | None = None) -> dict:
    path = settings_path(root)
    settings = default_settings()
    if not path.exists():
        return settings
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        logging.warning('Classroom display settings could not be read; using defaults.')
        return settings
    if not isinstance(raw, dict):
        return settings
    if raw.get('active_profile') in DEFAULT_PROFILES:
        settings['active_profile'] = raw['active_profile']
    settings['hotkey_enabled'] = bool(raw.get('hotkey_enabled', False))
    profiles = raw.get('profiles')
    if isinstance(profiles, dict):
        for name in DEFAULT_PROFILES:
            incoming = profiles.get(name)
            if isinstance(incoming, dict):
                merged = default_profile()
                if incoming.get('classroom_display') is None or isinstance(incoming.get('classroom_display'), dict):
                    merged['classroom_display'] = incoming.get('classroom_display')
                seen = incoming.get('last_seen_identities')
                if isinstance(seen, list) and all(isinstance(item, str) for item in seen):
                    merged['last_seen_identities'] = list(seen)
                if incoming.get('onenote_window_choice') in {WINDOW_MOST_RECENT, 'chosen'}:
                    merged['onenote_window_choice'] = incoming['onenote_window_choice']
                if incoming.get('chosen_window') is None or isinstance(incoming.get('chosen_window'), dict):
                    merged['chosen_window'] = incoming.get('chosen_window')
                merged['maximise'] = bool(incoming.get('maximise', True))
                launch = incoming.get('onenote_launch') or ALLOWLISTED_LAUNCH_URI
                merged['onenote_launch'] = launch if is_allowlisted_launch(str(launch)) else ALLOWLISTED_LAUNCH_URI
                settings['profiles'][name] = merged
    return settings


def save_shortcut_settings(settings: dict, root: Path | None = None) -> dict:
    normalised = load_shortcut_settings(root)
    if settings.get('active_profile') in DEFAULT_PROFILES:
        normalised['active_profile'] = settings['active_profile']
    normalised['hotkey_enabled'] = bool(settings.get('hotkey_enabled', False))
    incoming_profiles = settings.get('profiles') or {}
    for name in DEFAULT_PROFILES:
        if isinstance(incoming_profiles.get(name), dict):
            current = default_profile()
            current.update({key: incoming_profiles[name].get(key, current[key]) for key in current})
            if current['onenote_launch'] and not is_allowlisted_launch(str(current['onenote_launch'])):
                current['onenote_launch'] = ALLOWLISTED_LAUNCH_URI
            normalised['profiles'][name] = current
    path = settings_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalised, indent=2), encoding='utf-8')
    return normalised


def active_profile_name(settings: dict) -> str:
    name = settings.get('active_profile', PROFILE_HOME)
    return name if name in DEFAULT_PROFILES else PROFILE_HOME


def active_profile(settings: dict) -> dict:
    return settings['profiles'][active_profile_name(settings)]


def connected_identity_set(monitors: list[MonitorInfo]) -> list[str]:
    return sorted(monitor.durable_key() for monitor in monitors)


def match_classroom_monitor(saved: dict | None, monitors: list[MonitorInfo],
                            last_seen: list[str] | None = None) -> tuple[str, MonitorInfo | None, str]:
    """Return (status, monitor, message). Never silently remaps after a set change."""
    if not saved:
        return KIND_UNASSIGNED, None, UNASSIGNED_MESSAGE
    if not monitors:
        return KIND_MISSING_DISPLAY, None, MISSING_DISPLAY_MESSAGE

    path = (saved.get('device_path') or '').strip()
    edid = ((saved.get('edid_manufacturer') or ''), (saved.get('edid_product') or ''))
    durable = saved.get('durable_key') or ''
    fallback = saved.get('fallback_fingerprint') or ''

    path_matches = [monitor for monitor in monitors if path and monitor.device_path == path]
    if len(path_matches) == 1:
        return KIND_OK, path_matches[0], ''
    if len(path_matches) > 1:
        return KIND_NEEDS_CONFIRM, None, DISPLAY_SET_CHANGED_MESSAGE

    durable_is_fallback = durable.startswith('bounds:') or not (path or edid[0] or edid[1])
    if durable and not durable_is_fallback:
        key_matches = [monitor for monitor in monitors if monitor.durable_key() == durable]
        if len(key_matches) == 1:
            return KIND_OK, key_matches[0], ''
        if len(key_matches) > 1:
            return KIND_NEEDS_CONFIRM, None, DISPLAY_SET_CHANGED_MESSAGE

    # EDID manufacturer/product can be shared by identical models. Only use it
    # when the saved mapping had no device path; a vanished path is "unplugged".
    if (edid[0] or edid[1]) and not path:
        edid_matches = [monitor for monitor in monitors
                        if monitor.edid_manufacturer == edid[0] and monitor.edid_product == edid[1]
                        and (monitor.edid_manufacturer or monitor.edid_product)]
        if len(edid_matches) == 1:
            return KIND_OK, edid_matches[0], ''
        if len(edid_matches) > 1:
            return KIND_NEEDS_CONFIRM, None, DISPLAY_SET_CHANGED_MESSAGE

    fallback_matches = [monitor for monitor in monitors if fallback and monitor.fallback_fingerprint() == fallback]
    current_set = connected_identity_set(monitors)
    previous_set = list(last_seen or saved.get('last_seen_identities') or [])
    set_changed = bool(previous_set) and current_set != sorted(previous_set)
    if len(fallback_matches) == 1 and not set_changed:
        return KIND_OK, fallback_matches[0], ''
    if len(fallback_matches) == 1 and set_changed:
        return KIND_NEEDS_CONFIRM, fallback_matches[0], DISPLAY_SET_CHANGED_MESSAGE
    if fallback_matches:
        return KIND_NEEDS_CONFIRM, None, DISPLAY_SET_CHANGED_MESSAGE
    return KIND_MISSING_DISPLAY, None, MISSING_DISPLAY_MESSAGE


def resolve_onenote_window(profile: dict, windows: list[AppWindow],
                           foreground_hwnd: int = 0) -> tuple[str, AppWindow | None, str]:
    live = [window for window in windows if window.alive and window.executable.upper() == ONENOTE_EXECUTABLE]
    choice = profile.get('onenote_window_choice') or WINDOW_MOST_RECENT
    chosen = profile.get('chosen_window') if choice == 'chosen' else None

    if chosen:
        match = _chosen_still_present(chosen, live)
        if match is not None:
            return KIND_OK, match, ''
        if not live:
            return KIND_OK, None, 'The chosen OneNote window is no longer open.'
        if len(live) == 1:
            return KIND_OK, live[0], (
                f'The chosen OneNote window is no longer open. Using the remaining window: {live[0].title or "OneNote"}.')
        return KIND_AMBIGUOUS, None, CHOSEN_GONE_AMBIGUOUS_MESSAGE

    if not live:
        return KIND_OK, None, ''
    if len(live) == 1:
        return KIND_OK, live[0], ''
    for window in live:
        if foreground_hwnd and window.hwnd == foreground_hwnd:
            return KIND_OK, window, ''
    timed = [window for window in live if window.last_foreground_at]
    if timed:
        newest = max(timed, key=lambda window: window.last_foreground_at or 0)
        return KIND_OK, newest, ''
    return KIND_AMBIGUOUS, None, AMBIGUOUS_WINDOWS_MESSAGE


def _chosen_still_present(chosen: dict, live: list[AppWindow]) -> AppWindow | None:
    hwnd = int(chosen.get('hwnd') or 0)
    pid = int(chosen.get('pid') or 0)
    executable = str(chosen.get('executable') or ONENOTE_EXECUTABLE).upper()
    for window in live:
        if window.hwnd == hwnd and window.executable.upper() == executable:
            if pid and window.pid != pid:
                continue
            return window
    return None


def write_receipt(receipt: ActionReceipt, root: Path | None = None) -> None:
    path = Path(root or data_directory()) / 'monitor-shortcut-receipts.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps({'timestamp': time.time(), **receipt.as_dict()}) + '\n')


class MonitorShortcutController:
    def __init__(self, backend: WindowMonitorBackend | None = None, root: Path | None = None,
                 popup=None, wait_timeout_s: float = 8.0):
        self.backend = backend or create_backend()
        self.root = Path(root) if root is not None else data_directory()
        self.popup = popup
        self.wait_timeout_s = wait_timeout_s

    def load(self) -> dict:
        return load_shortcut_settings(self.root)

    def save(self, settings: dict) -> dict:
        return save_shortcut_settings(settings, self.root)

    def list_monitors(self) -> list[MonitorInfo]:
        return self.backend.list_monitors()

    def list_onenote_windows(self) -> list[AppWindow]:
        return self.backend.list_app_windows(ONENOTE_EXECUTABLE)

    def hotkey_enabled(self) -> bool:
        return bool(self.load().get('hotkey_enabled'))

    def assign_monitor(self, monitor: MonitorInfo) -> dict:
        settings = self.load()
        profile = active_profile(settings)
        profile['classroom_display'] = monitor.identity_record()
        profile['last_seen_identities'] = connected_identity_set(self.list_monitors())
        return self.save(settings)

    def confirm_remap(self, monitor: MonitorInfo) -> dict:
        return self.assign_monitor(monitor)

    def _warn_missing_display(self) -> None:
        if self.popup is not None:
            self.popup(MISSING_DISPLAY_MESSAGE)
            return
        try:
            from tkinter import messagebox
            messagebox.showwarning('Classroom display', MISSING_DISPLAY_MESSAGE)
        except Exception:
            logging.warning(MISSING_DISPLAY_MESSAGE)

    def open_onenote_on_classroom_display(self) -> ActionReceipt:
        settings = self.load()
        profile_name = active_profile_name(settings)
        profile = active_profile(settings)
        monitors = self.list_monitors()
        status, monitor, message = match_classroom_monitor(
            profile.get('classroom_display'), monitors, profile.get('last_seen_identities'))
        if status == KIND_MISSING_DISPLAY:
            receipt = ActionReceipt(kind=KIND_MISSING_DISPLAY, message=MISSING_DISPLAY_MESSAGE,
                                    profile=profile_name)
            write_receipt(receipt, self.root)
            self._warn_missing_display()
            return receipt
        if status != KIND_OK or monitor is None:
            receipt = ActionReceipt(kind=status, message=message, profile=profile_name)
            write_receipt(receipt, self.root)
            return receipt

        windows = self.list_onenote_windows()
        window_status, window, warning = resolve_onenote_window(
            profile, windows, self.backend.foreground_hwnd())
        if window_status == KIND_AMBIGUOUS:
            receipt = ActionReceipt(kind=KIND_AMBIGUOUS, message=warning, profile=profile_name,
                                    monitor_key=monitor.durable_key(), warning=warning)
            write_receipt(receipt, self.root)
            return receipt

        launched = False
        if window is None:
            launch = profile.get('onenote_launch') or ALLOWLISTED_LAUNCH_URI
            try:
                self.backend.launch_application(launch)
            except Exception as error:
                receipt = ActionReceipt(
                    kind=KIND_LAUNCH_FAILED,
                    message=f'OneNote could not be started. {error}',
                    profile=profile_name, monitor_key=monitor.durable_key(), warning=warning)
                write_receipt(receipt, self.root)
                return receipt
            launched = True
            window = self.backend.wait_for_app_window(ONENOTE_EXECUTABLE, self.wait_timeout_s)
            if window is None:
                receipt = ActionReceipt(
                    kind=KIND_LAUNCH_FAILED,
                    message='OneNote did not open in time. Open it once, then try again.',
                    launched=True, profile=profile_name, monitor_key=monitor.durable_key(),
                    warning=warning)
                write_receipt(receipt, self.root)
                return receipt

        if not self.backend.is_window_alive(window.hwnd):
            receipt = ActionReceipt(
                kind=KIND_WINDOW_GONE,
                message='The OneNote window closed before it could be moved.',
                hwnd=window.hwnd, launched=launched, profile=profile_name,
                monitor_key=monitor.durable_key(), warning=warning)
            write_receipt(receipt, self.root)
            return receipt

        maximise = bool(profile.get('maximise', True))
        placed = self.backend.place_window(window.hwnd, monitor.work_area, maximise)
        if not placed or not self.backend.is_window_alive(window.hwnd):
            receipt = ActionReceipt(
                kind=KIND_WINDOW_GONE if not self.backend.is_window_alive(window.hwnd) else KIND_PLACEMENT_FAILED,
                message=('The OneNote window closed before it could be moved.'
                         if not self.backend.is_window_alive(window.hwnd)
                         else 'OneNote could not be moved onto the classroom display.'),
                hwnd=window.hwnd, launched=launched, profile=profile_name,
                monitor_key=monitor.durable_key(), work_area=monitor.work_area.as_tuple(),
                warning=warning, window_title=window.title)
            write_receipt(receipt, self.root)
            return receipt

        placement_ok = verify_placement(self.backend.window_bounds(window.hwnd), monitor.work_area)
        foreground_ok = self.backend.request_foreground(window.hwnd, window.pid, window.title)
        if placement_ok and self.backend.is_window_alive(window.hwnd):
            # Verify independently of the request; a refused focus request is not a placement failure.
            live_foreground = False
            try:
                live_foreground = self.backend.foreground_hwnd() == window.hwnd
            except Exception:
                live_foreground = False
            foreground_ok = bool(foreground_ok and live_foreground)
        else:
            receipt = ActionReceipt(
                kind=KIND_PLACEMENT_FAILED,
                message='OneNote was not on the classroom display after moving it.',
                hwnd=window.hwnd, launched=launched, placed=False, foreground=False,
                profile=profile_name, monitor_key=monitor.durable_key(),
                work_area=monitor.work_area.as_tuple(), warning=warning,
                window_title=window.title)
            write_receipt(receipt, self.root)
            return receipt

        if not foreground_ok:
            receipt = ActionReceipt(
                kind=KIND_FOREGROUND_FAILED,
                message='OneNote is on the classroom display, but Windows kept another window in front. Click the OneNote window once.',
                hwnd=window.hwnd, launched=launched, placed=True, foreground=False,
                profile=profile_name, monitor_key=monitor.durable_key(),
                work_area=monitor.work_area.as_tuple(), warning=warning,
                window_title=window.title)
            write_receipt(receipt, self.root)
            return receipt

        used = 'Started OneNote' if launched else 'Found the desktop OneNote window'
        where = monitor.friendly_name or 'classroom display'
        receipt = ActionReceipt(
            kind=KIND_OK,
            message=f'{used} and placed it on {where}.',
            hwnd=window.hwnd, launched=launched, placed=True, foreground=True,
            profile=profile_name, monitor_key=monitor.durable_key(),
            work_area=monitor.work_area.as_tuple(), warning=warning,
            window_title=window.title)
        write_receipt(receipt, self.root)
        return receipt

    def test_placement(self) -> ActionReceipt:
        return self.open_onenote_on_classroom_display()


def classroom_hotkey_enabled(root: Path | None = None) -> bool:
    return bool(load_shortcut_settings(root).get('hotkey_enabled'))
