"""Open or focus classroom apps on a teacher-named classroom display.

Desktop-only: no firmware, no Office COM navigation, no typing injection.
A successful placement is not a Paste Ready or insert-permission grant.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import json
import logging
from pathlib import Path
import time

from companion_settings import data_directory
from window_monitor_manager import (
    ALLOWLISTED_LAUNCH_URI,
    APP_BOARD,
    APP_CHROME,
    APP_ONENOTE,
    APP_WORD,
    BOARD_PUPIL_TITLE,
    MISSING_DISPLAY_MESSAGE,
    ONENOTE_EXECUTABLE,
    AppWindow,
    ClassroomApp,
    MonitorInfo,
    Rect,
    WindowMonitorBackend,
    classroom_app,
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
KIND_BOARD_UNAVAILABLE = 'board_unavailable'
DISPLAY_SET_CHANGED_MESSAGE = (
    'The connected displays have changed. Confirm the classroom display before moving OneNote.')
UNASSIGNED_MESSAGE = 'Choose the classroom display first using Identify screens.'
AMBIGUOUS_WINDOWS_MESSAGE = (
    'Several OneNote windows are open. Choose one in Classroom display, or bring the intended notebook to the front once.')
CHOSEN_GONE_AMBIGUOUS_MESSAGE = (
    'The chosen OneNote window is no longer open. Several OneNote windows are open — choose one in Classroom display.')
BOARD_UNAVAILABLE_MESSAGE = 'Open the Teaching Board first.'
BOARD_PRESENCE_NAME = 'board-pupil-presence.json'
BOARD_REQUEST_NAME = 'classroom-board-request.json'
BOARD_RECEIPT_NAME = 'classroom-board-receipt.json'
CLASSROOM_APP_IDS = (APP_ONENOTE, APP_WORD, APP_CHROME)


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
    app_id: str = APP_ONENOTE

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
            'app_id': self.app_id,
        }


def default_app_settings(app_id: str) -> dict:
    spec = classroom_app(app_id)
    return {
        'window_choice': WINDOW_MOST_RECENT,
        'chosen_window': None,
        'maximise': True,
        'launch': spec.default_launch,
    }


def default_profile() -> dict:
    return {
        'classroom_display': None,
        'last_seen_identities': [],
        'onenote_window_choice': WINDOW_MOST_RECENT,
        'chosen_window': None,
        'maximise': True,
        'onenote_launch': ALLOWLISTED_LAUNCH_URI,
        'apps': {app_id: default_app_settings(app_id) for app_id in CLASSROOM_APP_IDS},
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
                merged['onenote_launch'] = launch if is_allowlisted_launch(str(launch), APP_ONENOTE) else ALLOWLISTED_LAUNCH_URI
                incoming_apps = incoming.get('apps')
                merged['apps'] = _merge_app_settings(incoming_apps if isinstance(incoming_apps, dict) else {}, merged)
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
            if current['onenote_launch'] and not is_allowlisted_launch(str(current['onenote_launch']), APP_ONENOTE):
                current['onenote_launch'] = ALLOWLISTED_LAUNCH_URI
            current['apps'] = _merge_app_settings(current.get('apps') if isinstance(current.get('apps'), dict) else {}, current)
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


def _merge_app_settings(incoming: dict, profile: dict) -> dict:
    merged = {app_id: default_app_settings(app_id) for app_id in CLASSROOM_APP_IDS}
    for app_id in CLASSROOM_APP_IDS:
        source = incoming.get(app_id)
        if isinstance(source, dict):
            current = merged[app_id]
            if source.get('window_choice') in {WINDOW_MOST_RECENT, 'chosen'}:
                current['window_choice'] = source['window_choice']
            if source.get('chosen_window') is None or isinstance(source.get('chosen_window'), dict):
                current['chosen_window'] = source.get('chosen_window')
            current['maximise'] = bool(source.get('maximise', True))
            launch = source.get('launch') or current['launch']
            current['launch'] = launch if is_allowlisted_launch(str(launch), app_id) else classroom_app(app_id).default_launch
            merged[app_id] = current
    # Keep the existing OneNote keys as the source of truth for that app.
    merged[APP_ONENOTE]['window_choice'] = profile.get('onenote_window_choice') or WINDOW_MOST_RECENT
    merged[APP_ONENOTE]['chosen_window'] = profile.get('chosen_window')
    merged[APP_ONENOTE]['maximise'] = bool(profile.get('maximise', True))
    launch = profile.get('onenote_launch') or ALLOWLISTED_LAUNCH_URI
    merged[APP_ONENOTE]['launch'] = launch if is_allowlisted_launch(str(launch), APP_ONENOTE) else ALLOWLISTED_LAUNCH_URI
    return merged


def app_settings(profile: dict, app_id: str) -> dict:
    apps = profile.get('apps') if isinstance(profile.get('apps'), dict) else {}
    current = default_app_settings(app_id)
    incoming = apps.get(app_id)
    if isinstance(incoming, dict):
        current.update({key: incoming.get(key, current[key]) for key in current})
    if app_id == APP_ONENOTE:
        if profile.get('onenote_window_choice') in {WINDOW_MOST_RECENT, 'chosen'}:
            current['window_choice'] = profile['onenote_window_choice']
        if 'chosen_window' in profile:
            current['chosen_window'] = profile.get('chosen_window')
        if 'maximise' in profile:
            current['maximise'] = bool(profile.get('maximise', True))
        if profile.get('onenote_launch'):
            launch = profile['onenote_launch']
            current['launch'] = launch if is_allowlisted_launch(str(launch), APP_ONENOTE) else ALLOWLISTED_LAUNCH_URI
    if current.get('launch') and not is_allowlisted_launch(str(current['launch']), app_id):
        current['launch'] = classroom_app(app_id).default_launch
    return current


def set_app_settings(profile: dict, app_id: str, updates: dict) -> None:
    apps = profile.setdefault('apps', {item: default_app_settings(item) for item in CLASSROOM_APP_IDS})
    current = app_settings(profile, app_id)
    current.update(updates)
    if current.get('launch') and not is_allowlisted_launch(str(current['launch']), app_id):
        current['launch'] = classroom_app(app_id).default_launch
    apps[app_id] = current
    if app_id == APP_ONENOTE:
        profile['onenote_window_choice'] = current.get('window_choice') or WINDOW_MOST_RECENT
        profile['chosen_window'] = current.get('chosen_window')
        profile['maximise'] = bool(current.get('maximise', True))
        profile['onenote_launch'] = current.get('launch') or ALLOWLISTED_LAUNCH_URI


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


def _app_choice_messages(app: ClassroomApp) -> dict:
    if app.app_id == APP_ONENOTE:
        return {
            'ambiguous': AMBIGUOUS_WINDOWS_MESSAGE,
            'chosen_gone': 'The chosen OneNote window is no longer open.',
            'chosen_gone_one': 'The chosen OneNote window is no longer open. Using the remaining window: {title}.',
            'chosen_gone_ambiguous': CHOSEN_GONE_AMBIGUOUS_MESSAGE,
            'untitled': 'OneNote',
        }
    label = app.label
    return {
        'ambiguous': (
            f'Several {label} windows are open. Choose one in Classroom display, '
            f'or bring the intended window to the front once.'),
        'chosen_gone': f'The chosen {label} window is no longer open.',
        'chosen_gone_one': (
            f'The chosen {label} window is no longer open. Using the remaining window: {{title}}.'),
        'chosen_gone_ambiguous': (
            f'The chosen {label} window is no longer open. Several {label} windows are open — '
            f'choose one in Classroom display.'),
        'untitled': label,
    }


def resolve_app_window(app_id: str, profile: dict, windows: list[AppWindow],
                       foreground_hwnd: int = 0) -> tuple[str, AppWindow | None, str]:
    app = classroom_app(app_id)
    settings = app_settings(profile, app_id)
    live = [window for window in windows if window.alive and window.executable.upper() == app.executable]
    choice = settings.get('window_choice') or WINDOW_MOST_RECENT
    chosen = settings.get('chosen_window') if choice == 'chosen' else None
    texts = _app_choice_messages(app)

    if chosen:
        match = _chosen_still_present(chosen, live, app.executable)
        if match is not None:
            return KIND_OK, match, ''
        if not live:
            return KIND_OK, None, texts['chosen_gone']
        if len(live) == 1:
            title = live[0].title or texts['untitled']
            return KIND_OK, live[0], texts['chosen_gone_one'].format(title=title)
        return KIND_AMBIGUOUS, None, texts['chosen_gone_ambiguous']

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
    return KIND_AMBIGUOUS, None, texts['ambiguous']


def resolve_onenote_window(profile: dict, windows: list[AppWindow],
                           foreground_hwnd: int = 0) -> tuple[str, AppWindow | None, str]:
    return resolve_app_window(APP_ONENOTE, profile, windows, foreground_hwnd)


def _chosen_still_present(chosen: dict, live: list[AppWindow],
                          default_executable: str = ONENOTE_EXECUTABLE) -> AppWindow | None:
    hwnd = int(chosen.get('hwnd') or 0)
    pid = int(chosen.get('pid') or 0)
    executable = str(chosen.get('executable') or default_executable).upper()
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


class FakeBoardPupilTarget:
    """In-process Board stand-in for Linux tests. Never navigates, freezes or resumes."""

    def __init__(self, *, available: bool = True, visible: bool = True,
                 snapshot: dict | None = None):
        self._available = available
        self.visible = visible
        self.show_checked = visible
        self.place_calls: list[tuple[tuple[int, int, int, int], str]] = []
        self.raise_calls = 0
        self.navigate_calls = 0
        self.freeze_calls = 0
        self.resume_calls = 0
        self.snapshot = snapshot or {
            'frozen': False, 'page_id': 'page-1', 'revision': 1, 'token': 'tok',
            'document': {'title': 'Lesson'},
        }

    def is_available(self) -> bool:
        return self._available

    def pupil_snapshot(self) -> dict:
        return copy.deepcopy(self.snapshot)

    def show_pupil(self) -> None:
        self.visible = True
        self.show_checked = True

    def place_pupil(self, work_area: Rect, monitor: MonitorInfo) -> bool:
        self.place_calls.append((work_area.as_tuple(), monitor.durable_key()))
        return True

    def raise_pupil(self) -> bool:
        self.raise_calls += 1
        return True


class FileBoardPupilBridge:
    """Ask the separate Teaching Board process to place the existing pupil window."""

    def __init__(self, root: Path, timeout_s: float = 2.0):
        self.root = Path(root)
        self.timeout_s = timeout_s

    def is_available(self) -> bool:
        path = self.root / BOARD_PRESENCE_NAME
        if not path.is_file():
            return False
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False
        return bool(isinstance(data, dict) and data.get('running'))

    def bring_forward(self, monitor: MonitorInfo) -> dict:
        request_id = f'{time.time():.6f}'
        request_path = self.root / BOARD_REQUEST_NAME
        receipt_path = self.root / BOARD_RECEIPT_NAME
        try:
            if receipt_path.exists():
                receipt_path.unlink()
        except OSError:
            pass
        payload = {
            'id': request_id,
            'work_area': list(monitor.work_area.as_tuple()),
            'durable_key': monitor.durable_key(),
            'friendly_name': monitor.friendly_name,
        }
        request_path.parent.mkdir(parents=True, exist_ok=True)
        request_path.write_text(json.dumps(payload), encoding='utf-8')
        deadline = time.time() + max(0.05, self.timeout_s)
        while time.time() < deadline:
            if receipt_path.is_file():
                try:
                    data = json.loads(receipt_path.read_text(encoding='utf-8'))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    data = None
                if isinstance(data, dict) and data.get('id') == request_id:
                    return data
            time.sleep(0.05)
        return {'ok': False, 'message': BOARD_UNAVAILABLE_MESSAGE}


class MonitorShortcutController:
    def __init__(self, backend: WindowMonitorBackend | None = None, root: Path | None = None,
                 popup=None, wait_timeout_s: float = 8.0, board_target=None):
        self.backend = backend or create_backend()
        self.root = Path(root) if root is not None else data_directory()
        self.popup = popup
        self.wait_timeout_s = wait_timeout_s
        self.board_target = board_target

    def load(self) -> dict:
        return load_shortcut_settings(self.root)

    def save(self, settings: dict) -> dict:
        return save_shortcut_settings(settings, self.root)

    def list_monitors(self) -> list[MonitorInfo]:
        return self.backend.list_monitors()

    def list_onenote_windows(self) -> list[AppWindow]:
        return self.list_app_windows(APP_ONENOTE)

    def list_app_windows(self, app_id: str) -> list[AppWindow]:
        return self.backend.list_app_windows(classroom_app(app_id).executable)

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

    def _resolve_classroom_monitor(self, settings: dict) -> tuple[str, MonitorInfo | None, str, str]:
        profile_name = active_profile_name(settings)
        profile = active_profile(settings)
        monitors = self.list_monitors()
        status, monitor, message = match_classroom_monitor(
            profile.get('classroom_display'), monitors, profile.get('last_seen_identities'))
        return status, monitor, message, profile_name

    def _missing_or_unresolved_receipt(self, status: str, message: str, profile_name: str,
                                       app_id: str) -> ActionReceipt:
        if status == KIND_MISSING_DISPLAY:
            receipt = ActionReceipt(kind=KIND_MISSING_DISPLAY, message=MISSING_DISPLAY_MESSAGE,
                                    profile=profile_name, app_id=app_id)
            write_receipt(receipt, self.root)
            self._warn_missing_display()
            return receipt
        receipt = ActionReceipt(kind=status, message=message, profile=profile_name, app_id=app_id)
        write_receipt(receipt, self.root)
        return receipt

    def open_onenote_on_classroom_display(self) -> ActionReceipt:
        return self.open_app_on_classroom_display(APP_ONENOTE)

    def open_app_on_classroom_display(self, app_id: str) -> ActionReceipt:
        app = classroom_app(app_id)
        settings = self.load()
        profile = active_profile(settings)
        status, monitor, message, profile_name = self._resolve_classroom_monitor(settings)
        if status == KIND_MISSING_DISPLAY or status != KIND_OK or monitor is None:
            return self._missing_or_unresolved_receipt(status, message, profile_name, app_id)

        windows = self.list_app_windows(app_id)
        window_status, window, warning = resolve_app_window(
            app_id, profile, windows, self.backend.foreground_hwnd())
        if window_status == KIND_AMBIGUOUS:
            receipt = ActionReceipt(kind=KIND_AMBIGUOUS, message=warning, profile=profile_name,
                                    monitor_key=monitor.durable_key(), warning=warning,
                                    app_id=app_id)
            write_receipt(receipt, self.root)
            return receipt

        launched = False
        settings_for_app = app_settings(profile, app_id)
        if window is None:
            launch = settings_for_app.get('launch') or app.default_launch
            if not is_allowlisted_launch(str(launch), app_id):
                receipt = ActionReceipt(
                    kind=KIND_LAUNCH_FAILED,
                    message=f'{app.label} could not be started. Launch command is not allowlisted.',
                    profile=profile_name, monitor_key=monitor.durable_key(), warning=warning,
                    app_id=app_id)
                write_receipt(receipt, self.root)
                return receipt
            try:
                self.backend.launch_application(launch)
            except Exception as error:
                receipt = ActionReceipt(
                    kind=KIND_LAUNCH_FAILED,
                    message=f'{app.label} could not be started. {error}',
                    profile=profile_name, monitor_key=monitor.durable_key(), warning=warning,
                    app_id=app_id)
                write_receipt(receipt, self.root)
                return receipt
            launched = True
            window = self.backend.wait_for_app_window(app.executable, self.wait_timeout_s)
            if window is None:
                receipt = ActionReceipt(
                    kind=KIND_LAUNCH_FAILED,
                    message=f'{app.label} did not open in time. Open it once, then try again.',
                    launched=True, profile=profile_name, monitor_key=monitor.durable_key(),
                    warning=warning, app_id=app_id)
                write_receipt(receipt, self.root)
                return receipt

        if not self.backend.is_window_alive(window.hwnd):
            receipt = ActionReceipt(
                kind=KIND_WINDOW_GONE,
                message=f'The {app.label} window closed before it could be moved.',
                hwnd=window.hwnd, launched=launched, profile=profile_name,
                monitor_key=monitor.durable_key(), warning=warning, app_id=app_id)
            write_receipt(receipt, self.root)
            return receipt

        maximise = bool(settings_for_app.get('maximise', True))
        placed = self.backend.place_window(window.hwnd, monitor.work_area, maximise)
        if not placed or not self.backend.is_window_alive(window.hwnd):
            gone = not self.backend.is_window_alive(window.hwnd)
            receipt = ActionReceipt(
                kind=KIND_WINDOW_GONE if gone else KIND_PLACEMENT_FAILED,
                message=(f'The {app.label} window closed before it could be moved.'
                         if gone else f'{app.label} could not be moved onto the classroom display.'),
                hwnd=window.hwnd, launched=launched, profile=profile_name,
                monitor_key=monitor.durable_key(), work_area=monitor.work_area.as_tuple(),
                warning=warning, window_title=window.title, app_id=app_id)
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
                message=f'{app.label} was not on the classroom display after moving it.',
                hwnd=window.hwnd, launched=launched, placed=False, foreground=False,
                profile=profile_name, monitor_key=monitor.durable_key(),
                work_area=monitor.work_area.as_tuple(), warning=warning,
                window_title=window.title, app_id=app_id)
            write_receipt(receipt, self.root)
            return receipt

        if not foreground_ok:
            receipt = ActionReceipt(
                kind=KIND_FOREGROUND_FAILED,
                message=(f'{app.label} is on the classroom display, but Windows kept another window in front. '
                         f'Click the {app.label} window once.'),
                hwnd=window.hwnd, launched=launched, placed=True, foreground=False,
                profile=profile_name, monitor_key=monitor.durable_key(),
                work_area=monitor.work_area.as_tuple(), warning=warning,
                window_title=window.title, app_id=app_id)
            write_receipt(receipt, self.root)
            return receipt

        used = f'Started {app.label}' if launched else f'Found the desktop {app.label} window'
        where = monitor.friendly_name or 'classroom display'
        receipt = ActionReceipt(
            kind=KIND_OK,
            message=f'{used} and placed it on {where}.',
            hwnd=window.hwnd, launched=launched, placed=True, foreground=True,
            profile=profile_name, monitor_key=monitor.durable_key(),
            work_area=monitor.work_area.as_tuple(), warning=warning,
            window_title=window.title, app_id=app_id)
        write_receipt(receipt, self.root)
        return receipt

    def bring_board_to_classroom_display(self) -> ActionReceipt:
        settings = self.load()
        status, monitor, message, profile_name = self._resolve_classroom_monitor(settings)
        if status == KIND_MISSING_DISPLAY or status != KIND_OK or monitor is None:
            return self._missing_or_unresolved_receipt(status, message, profile_name, APP_BOARD)

        target = self.board_target
        if target is not None and target.is_available():
            before = target.pupil_snapshot()
            target.show_pupil()
            placed = bool(target.place_pupil(monitor.work_area, monitor))
            raised = bool(target.raise_pupil())
            after = target.pupil_snapshot()
            if before != after:
                logging.warning('Board pupil snapshot changed during bring-forward; content should stay pinned.')
            if not placed:
                receipt = ActionReceipt(
                    kind=KIND_PLACEMENT_FAILED,
                    message='The Teaching Board pupil window could not be moved onto the classroom display.',
                    profile=profile_name, monitor_key=monitor.durable_key(),
                    work_area=monitor.work_area.as_tuple(), app_id=APP_BOARD)
                write_receipt(receipt, self.root)
                return receipt
            receipt = ActionReceipt(
                kind=KIND_OK if raised else KIND_FOREGROUND_FAILED,
                message=(
                    f'The Teaching Board pupil window is on {monitor.friendly_name or "the classroom display"}.'
                    if raised else
                    'The Teaching Board pupil window is on the classroom display, but another window stayed in front.'),
                placed=True, foreground=raised, profile=profile_name,
                monitor_key=monitor.durable_key(), work_area=monitor.work_area.as_tuple(),
                window_title=BOARD_PUPIL_TITLE, app_id=APP_BOARD)
            write_receipt(receipt, self.root)
            return receipt

        bridge = FileBoardPupilBridge(self.root, timeout_s=min(2.0, max(0.1, self.wait_timeout_s)))
        if bridge.is_available():
            result = bridge.bring_forward(monitor)
            if result.get('ok'):
                receipt = ActionReceipt(
                    kind=KIND_OK,
                    message=f'The Teaching Board pupil window is on {monitor.friendly_name or "the classroom display"}.',
                    placed=True, foreground=True, profile=profile_name,
                    monitor_key=monitor.durable_key(), work_area=monitor.work_area.as_tuple(),
                    window_title=BOARD_PUPIL_TITLE, app_id=APP_BOARD)
                write_receipt(receipt, self.root)
                return receipt

        windows = self.backend.list_board_pupil_windows(include_hidden=True)
        if windows:
            window = windows[0]
            self.backend.show_window(window.hwnd)
            placed = self.backend.place_window(window.hwnd, monitor.work_area, False)
            if not placed or not self.backend.is_window_alive(window.hwnd):
                receipt = ActionReceipt(
                    kind=KIND_PLACEMENT_FAILED,
                    message='The Teaching Board pupil window could not be moved onto the classroom display.',
                    hwnd=window.hwnd, profile=profile_name, monitor_key=monitor.durable_key(),
                    work_area=monitor.work_area.as_tuple(), app_id=APP_BOARD)
                write_receipt(receipt, self.root)
                return receipt
            raised = self.backend.request_foreground(
                window.hwnd, window.pid, window.title, allow_internal=True)
            receipt = ActionReceipt(
                kind=KIND_OK if raised else KIND_FOREGROUND_FAILED,
                message=(
                    f'The Teaching Board pupil window is on {monitor.friendly_name or "the classroom display"}.'
                    if raised else
                    'The Teaching Board pupil window is on the classroom display, but another window stayed in front.'),
                hwnd=window.hwnd, placed=True, foreground=bool(raised), profile=profile_name,
                monitor_key=monitor.durable_key(), work_area=monitor.work_area.as_tuple(),
                window_title=BOARD_PUPIL_TITLE, app_id=APP_BOARD)
            write_receipt(receipt, self.root)
            return receipt

        receipt = ActionReceipt(
            kind=KIND_BOARD_UNAVAILABLE, message=BOARD_UNAVAILABLE_MESSAGE,
            profile=profile_name, monitor_key=monitor.durable_key(), app_id=APP_BOARD)
        write_receipt(receipt, self.root)
        return receipt

    def test_placement(self) -> ActionReceipt:
        return self.open_onenote_on_classroom_display()


def classroom_hotkey_enabled(root: Path | None = None) -> bool:
    return bool(load_shortcut_settings(root).get('hotkey_enabled'))
