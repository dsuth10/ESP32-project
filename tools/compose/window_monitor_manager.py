"""Monitor and window operations for the classroom OneNote action.

Windows calls live in the Win32 backend and run only when os.name == 'nt'.
Linux tests use FakeWindowMonitorBackend. This module does not grant Paste Ready
permission, inject typing, or talk to Office COM.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import time
from typing import Protocol


ONENOTE_EXECUTABLE = 'ONENOTE.EXE'
ALLOWLISTED_LAUNCH_URI = 'onenote:'
MISSING_DISPLAY_MESSAGE = 'No classroom display detected.'


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def centre(self) -> tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.right, self.bottom)

    def contains_point(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom

    def intersects(self, other: 'Rect') -> bool:
        return not (self.right <= other.left or other.right <= self.left
                    or self.bottom <= other.top or other.bottom <= self.top)


@dataclass(frozen=True)
class MonitorInfo:
    handle: int
    friendly_name: str
    device_name: str
    device_path: str
    edid_manufacturer: str
    edid_product: str
    bounds: Rect
    work_area: Rect
    dpi: int
    is_primary: bool = False

    def durable_key(self) -> str:
        if self.device_path:
            return f'path:{self.device_path}'
        if self.edid_manufacturer or self.edid_product:
            return f'edid:{self.edid_manufacturer}:{self.edid_product}'
        return self.fallback_fingerprint()

    def fallback_fingerprint(self) -> str:
        left, top, right, bottom = self.bounds.as_tuple()
        return f'bounds:{left},{top},{right},{bottom}@{self.dpi}'

    def identity_record(self) -> dict:
        return {
            'friendly_name': self.friendly_name,
            'device_name': self.device_name,
            'device_path': self.device_path,
            'edid_manufacturer': self.edid_manufacturer,
            'edid_product': self.edid_product,
            'bounds': list(self.bounds.as_tuple()),
            'work_area': list(self.work_area.as_tuple()),
            'dpi': self.dpi,
            'durable_key': self.durable_key(),
            'fallback_fingerprint': self.fallback_fingerprint(),
        }


@dataclass
class AppWindow:
    hwnd: int
    pid: int
    title: str
    executable: str
    bounds: Rect
    class_name: str = ''
    last_foreground_at: float | None = None
    show_state: str = 'normal'
    alive: bool = True


@dataclass
class PlacementOutcome:
    placed: bool
    foreground: bool
    message: str
    hwnd: int = 0
    launched: bool = False
    work_area: tuple[int, int, int, int] | None = None


class WindowMonitorBackend(Protocol):
    def list_monitors(self) -> list[MonitorInfo]: ...
    def list_app_windows(self, executable: str) -> list[AppWindow]: ...
    def foreground_hwnd(self) -> int: ...
    def is_window_alive(self, hwnd: int) -> bool: ...
    def launch_application(self, command: str) -> None: ...
    def wait_for_app_window(self, executable: str, timeout_s: float = 8.0) -> AppWindow | None: ...
    def place_window(self, hwnd: int, work_area: Rect, maximise: bool) -> bool: ...
    def request_foreground(self, hwnd: int, pid: int = 0, title: str = '') -> bool: ...
    def window_bounds(self, hwnd: int) -> Rect | None: ...
    def note_foreground(self, hwnd: int, when: float | None = None) -> None: ...


def is_allowlisted_launch(command: str) -> bool:
    text = (command or '').strip()
    if not text:
        return False
    if text.lower() == ALLOWLISTED_LAUNCH_URI:
        return True
    name = text.replace('\\', '/').split('/')[-1].upper()
    return name == ONENOTE_EXECUTABLE


def verify_placement(bounds: Rect | None, work_area: Rect) -> bool:
    if bounds is None:
        return False
    x, y = bounds.centre
    if work_area.contains_point(x, y):
        return True
    return bounds.intersects(work_area)


class FakeWindowMonitorBackend:
    """In-memory backend for Linux unit tests and headless UI previews."""

    def __init__(self, monitors: list[MonitorInfo] | None = None,
                 windows: list[AppWindow] | None = None):
        self.monitors = list(monitors or [])
        self.windows = list(windows or [])
        self._foreground = 0
        self.launch_calls: list[str] = []
        self.place_calls: list[tuple[int, tuple[int, int, int, int], bool]] = []
        self.foreground_requests: list[int] = []
        self.dead_hwnds: set[int] = set()
        self.launch_window: AppWindow | None = None
        self.fail_place = False
        self.fail_foreground = False
        self.die_during_place = False
        self.launch_delay_windows: list[AppWindow] = []

    def list_monitors(self) -> list[MonitorInfo]:
        return list(self.monitors)

    def list_app_windows(self, executable: str) -> list[AppWindow]:
        wanted = executable.upper()
        live = []
        for window in self.windows:
            if window.hwnd in self.dead_hwnds:
                window.alive = False
                continue
            if window.executable.upper() == wanted and window.alive:
                live.append(window)
        return live

    def foreground_hwnd(self) -> int:
        return self._foreground

    def set_foreground(self, hwnd: int) -> None:
        self._foreground = hwnd
        self.note_foreground(hwnd)

    def is_window_alive(self, hwnd: int) -> bool:
        if hwnd in self.dead_hwnds:
            return False
        return any(window.hwnd == hwnd and window.alive for window in self.windows)

    def kill_window(self, hwnd: int) -> None:
        self.dead_hwnds.add(hwnd)
        for window in self.windows:
            if window.hwnd == hwnd:
                window.alive = False

    def launch_application(self, command: str) -> None:
        if not is_allowlisted_launch(command):
            raise ValueError('OneNote launch command is not allowlisted.')
        self.launch_calls.append(command)
        created = self.launch_window or (self.launch_delay_windows[0] if self.launch_delay_windows else None)
        if created is not None:
            if created not in self.windows:
                self.windows.append(created)
            created.alive = True
            self.dead_hwnds.discard(created.hwnd)

    def wait_for_app_window(self, executable: str, timeout_s: float = 8.0) -> AppWindow | None:
        found = self.list_app_windows(executable)
        if found:
            return found[0]
        if self.launch_delay_windows:
            delayed = self.launch_delay_windows.pop(0)
            if delayed not in self.windows:
                self.windows.append(delayed)
            delayed.alive = True
            return delayed
        return None

    def place_window(self, hwnd: int, work_area: Rect, maximise: bool) -> bool:
        self.place_calls.append((hwnd, work_area.as_tuple(), maximise))
        if self.die_during_place:
            self.kill_window(hwnd)
            return False
        if not self.is_window_alive(hwnd) or self.fail_place:
            return False
        for window in self.windows:
            if window.hwnd == hwnd:
                window.bounds = work_area
                window.show_state = 'maximised' if maximise else 'normal'
                return True
        return False

    def request_foreground(self, hwnd: int, pid: int = 0, title: str = '') -> bool:
        self.foreground_requests.append(hwnd)
        if self.fail_foreground or not self.is_window_alive(hwnd):
            return False
        self.set_foreground(hwnd)
        return True

    def window_bounds(self, hwnd: int) -> Rect | None:
        if not self.is_window_alive(hwnd):
            return None
        for window in self.windows:
            if window.hwnd == hwnd:
                return window.bounds
        return None

    def note_foreground(self, hwnd: int, when: float | None = None) -> None:
        stamp = time.time() if when is None else when
        for window in self.windows:
            if window.hwnd == hwnd:
                window.last_foreground_at = stamp


class Win32WindowMonitorBackend:
    """ctypes Win32 implementation. Instantiated only on Windows hosts."""

    def __init__(self):
        if os.name != 'nt':
            raise RuntimeError('The Win32 monitor backend is only available on Windows.')
        self._last_foreground: dict[int, float] = {}

    def list_monitors(self) -> list[MonitorInfo]:
        from ctypes import wintypes
        import ctypes

        user32 = ctypes.WinDLL('user32', use_last_error=True)
        extras = _query_ccd_targets()

        class RECT(ctypes.Structure):
            _fields_ = [('left', wintypes.LONG), ('top', wintypes.LONG),
                        ('right', wintypes.LONG), ('bottom', wintypes.LONG)]

        class MONITORINFOEXW(ctypes.Structure):
            _fields_ = [
                ('cbSize', wintypes.DWORD),
                ('rcMonitor', RECT),
                ('rcWork', RECT),
                ('dwFlags', wintypes.DWORD),
                ('szDevice', wintypes.WCHAR * 32),
            ]

        monitors: list[MonitorInfo] = []

        def _callback(handle, _hdc, _rect, _data):
            info = MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(MONITORINFOEXW)
            if not user32.GetMonitorInfoW(handle, ctypes.byref(info)):
                return True
            device_name = info.szDevice
            path, adapter_name = _gdi_device_identity(device_name)
            extra = _match_ccd_extra(extras, path, device_name)
            bounds = Rect(info.rcMonitor.left, info.rcMonitor.top,
                          info.rcMonitor.right, info.rcMonitor.bottom)
            work = Rect(info.rcWork.left, info.rcWork.top,
                        info.rcWork.right, info.rcWork.bottom)
            friendly = (extra.get('friendly_name') or adapter_name or device_name
                        or 'Display')
            monitors.append(MonitorInfo(
                handle=int(handle),
                friendly_name=friendly,
                device_name=device_name,
                device_path=extra.get('device_path') or path,
                edid_manufacturer=extra.get('edid_manufacturer', ''),
                edid_product=extra.get('edid_product', ''),
                bounds=bounds,
                work_area=work,
                dpi=_monitor_dpi(handle),
                is_primary=bool(info.dwFlags & 1),
            ))
            return True

        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
        user32.EnumDisplayMonitors(0, 0, MONITORENUMPROC(_callback), 0)
        return monitors

    def list_app_windows(self, executable: str) -> list[AppWindow]:
        from ctypes import wintypes
        import ctypes

        user32 = ctypes.WinDLL('user32', use_last_error=True)
        wanted = executable.upper()
        found: list[AppWindow] = []
        GWL_EXSTYLE = -20
        WS_EX_TOOLWINDOW = 0x00000080

        def _callback(hwnd, _data):
            if not user32.IsWindowVisible(hwnd):
                return True
            if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            image = _process_image_name(pid.value)
            if os.path.basename(image).upper() != wanted:
                return True
            title = _window_text(hwnd)
            class_name = _class_name(hwnd)
            bounds = self.window_bounds(int(hwnd))
            if bounds is None:
                return True
            show_state = 'minimised' if user32.IsIconic(hwnd) else (
                'maximised' if user32.IsZoomed(hwnd) else 'normal')
            found.append(AppWindow(
                hwnd=int(hwnd),
                pid=int(pid.value),
                title=title,
                executable=os.path.basename(image).upper(),
                bounds=bounds,
                class_name=class_name,
                last_foreground_at=self._last_foreground.get(int(hwnd)),
                show_state=show_state,
            ))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(_callback), 0)
        current = self.foreground_hwnd()
        if current:
            self.note_foreground(current)
            for window in found:
                if window.hwnd == current:
                    window.last_foreground_at = self._last_foreground.get(current)
        return found

    def foreground_hwnd(self) -> int:
        import ctypes
        return int(ctypes.WinDLL('user32', use_last_error=True).GetForegroundWindow() or 0)

    def is_window_alive(self, hwnd: int) -> bool:
        import ctypes
        return bool(hwnd and ctypes.WinDLL('user32', use_last_error=True).IsWindow(hwnd))

    def launch_application(self, command: str) -> None:
        if not is_allowlisted_launch(command):
            raise ValueError('OneNote launch command is not allowlisted.')
        text = command.strip()
        if text.lower() == ALLOWLISTED_LAUNCH_URI:
            os.startfile(ALLOWLISTED_LAUNCH_URI)  # noqa: S606 — allowlisted URI only
            return
        if not os.path.isfile(text):
            raise FileNotFoundError('The configured OneNote program was not found.')
        import subprocess
        subprocess.Popen([text], close_fds=True)

    def wait_for_app_window(self, executable: str, timeout_s: float = 8.0) -> AppWindow | None:
        deadline = time.time() + max(0.2, timeout_s)
        while time.time() < deadline:
            windows = self.list_app_windows(executable)
            if windows:
                return windows[0]
            time.sleep(0.2)
        return None

    def place_window(self, hwnd: int, work_area: Rect, maximise: bool) -> bool:
        import ctypes
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        if not self.is_window_alive(hwnd):
            return False
        if (not user32.IsIconic(hwnd)
                and verify_placement(self.window_bounds(hwnd), work_area)
                and bool(user32.IsZoomed(hwnd)) == bool(maximise)):
            return True
        SW_RESTORE = 9
        SW_SHOWMAXIMIZED = 3
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        SWP_FRAMECHANGED = 0x0020
        user32.ShowWindow(hwnd, SW_RESTORE)
        if not self.is_window_alive(hwnd):
            return False
        ok = user32.SetWindowPos(
            hwnd, 0, work_area.left, work_area.top, work_area.width, work_area.height,
            SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED)
        if not ok:
            return False
        if maximise:
            if not self.is_window_alive(hwnd):
                return False
            user32.ShowWindow(hwnd, SW_SHOWMAXIMIZED)
        return self.is_window_alive(hwnd)

    def request_foreground(self, hwnd: int, pid: int = 0, title: str = '') -> bool:
        from focus_tracker import FocusTracker
        if not self.is_window_alive(hwnd):
            return False
        if pid and FocusTracker.is_internal_process(pid):
            return False
        if FocusTracker.is_internal_window(hwnd):
            return False
        return FocusTracker.request_foreground(hwnd, restore=False)

    def window_bounds(self, hwnd: int) -> Rect | None:
        from ctypes import wintypes
        import ctypes
        if not self.is_window_alive(hwnd):
            return None
        rect = wintypes.RECT()
        if not ctypes.WinDLL('user32', use_last_error=True).GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        return Rect(rect.left, rect.top, rect.right, rect.bottom)

    def note_foreground(self, hwnd: int, when: float | None = None) -> None:
        if hwnd:
            self._last_foreground[int(hwnd)] = time.time() if when is None else when


def create_backend() -> WindowMonitorBackend:
    if os.name == 'nt':
        return Win32WindowMonitorBackend()
    return FakeWindowMonitorBackend()


def _window_text(hwnd: int) -> str:
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 2)
    user32.GetWindowTextW(hwnd, buffer, length + 2)
    return buffer.value


def _class_name(hwnd: int) -> str:
    import ctypes
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def _process_image_name(pid: int) -> str:
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return ''
    try:
        text = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(32768)
        kernel.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        if not kernel.QueryFullProcessImageNameW(handle, 0, text, ctypes.byref(length)):
            return ''
        return text.value
    finally:
        kernel.CloseHandle(handle)


def _gdi_device_identity(device_name: str) -> tuple[str, str]:
    import ctypes
    from ctypes import wintypes

    class DISPLAY_DEVICEW(ctypes.Structure):
        _fields_ = [
            ('cb', wintypes.DWORD),
            ('DeviceName', wintypes.WCHAR * 32),
            ('DeviceString', wintypes.WCHAR * 128),
            ('StateFlags', wintypes.DWORD),
            ('DeviceID', wintypes.WCHAR * 128),
            ('DeviceKey', wintypes.WCHAR * 128),
        ]

    user32 = ctypes.WinDLL('user32', use_last_error=True)
    device = DISPLAY_DEVICEW()
    device.cb = ctypes.sizeof(DISPLAY_DEVICEW)
    if not user32.EnumDisplayDevicesW(device_name, 0, ctypes.byref(device), 0):
        return '', ''
    return device.DeviceID, device.DeviceString


def _monitor_dpi(handle: int) -> int:
    try:
        import ctypes
        from ctypes import wintypes
        shcore = ctypes.WinDLL('shcore', use_last_error=True)
        dpi_x = wintypes.UINT()
        dpi_y = wintypes.UINT()
        if shcore.GetDpiForMonitor(handle, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y)) == 0:
            return int(dpi_x.value or 96)
    except Exception:
        pass
    return 96


def _query_ccd_targets() -> list[dict]:
    """Best-effort CCD names/EDID. Fields may be missing or duplicated."""
    if os.name != 'nt':
        return []
    try:
        import ctypes
        from ctypes import wintypes

        class LUID(ctypes.Structure):
            _fields_ = [('LowPart', wintypes.DWORD), ('HighPart', wintypes.LONG)]

        class HEADER(ctypes.Structure):
            _fields_ = [('type', wintypes.UINT), ('size', wintypes.UINT),
                        ('adapterId', LUID), ('id', wintypes.UINT)]

        class TARGET_NAME(ctypes.Structure):
            _fields_ = [
                ('header', HEADER),
                ('flags', wintypes.UINT),
                ('outputTechnology', wintypes.UINT),
                ('edidManufactureId', wintypes.USHORT),
                ('edidProductCodeId', wintypes.USHORT),
                ('connectorInstance', wintypes.UINT),
                ('monitorFriendlyDeviceName', wintypes.WCHAR * 64),
                ('monitorDevicePath', wintypes.WCHAR * 128),
            ]

        class PATH_SOURCE(ctypes.Structure):
            _fields_ = [('adapterId', LUID), ('id', wintypes.UINT),
                        ('modeInfoIdx', wintypes.UINT), ('statusFlags', wintypes.UINT)]

        class PATH_TARGET(ctypes.Structure):
            _fields_ = [
                ('adapterId', LUID), ('id', wintypes.UINT), ('modeInfoIdx', wintypes.UINT),
                ('outputTechnology', wintypes.UINT), ('rotation', wintypes.UINT),
                ('scaling', wintypes.UINT), ('refreshRate_num', wintypes.UINT),
                ('refreshRate_den', wintypes.UINT), ('scanLineOrdering', wintypes.UINT),
                ('targetAvailable', wintypes.BOOL), ('statusFlags', wintypes.UINT),
            ]

        class PATH_INFO(ctypes.Structure):
            _fields_ = [('sourceInfo', PATH_SOURCE), ('targetInfo', PATH_TARGET),
                        ('flags', wintypes.UINT)]

        user32 = ctypes.WinDLL('user32', use_last_error=True)
        path_count = wintypes.UINT()
        mode_count = wintypes.UINT()
        QDC_ONLY_ACTIVE_PATHS = 2
        if user32.GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(path_count),
                                              ctypes.byref(mode_count)) != 0:
            return []
        paths = (PATH_INFO * path_count.value)()
        # Mode buffer is required by the API; contents are unused here.
        modes = (ctypes.c_byte * max(1, mode_count.value * 64))()
        if user32.QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS, ctypes.byref(path_count), paths,
                                     ctypes.byref(mode_count), modes, None) != 0:
            return []
        extras = []
        for index in range(path_count.value):
            name = TARGET_NAME()
            name.header.type = 2  # DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME
            name.header.size = ctypes.sizeof(TARGET_NAME)
            name.header.adapterId = paths[index].targetInfo.adapterId
            name.header.id = paths[index].targetInfo.id
            if user32.DisplayConfigGetDeviceInfo(ctypes.byref(name)) != 0:
                continue
            extras.append({
                'friendly_name': name.monitorFriendlyDeviceName,
                'device_path': name.monitorDevicePath,
                'edid_manufacturer': f'{name.edidManufactureId:04X}' if name.edidManufactureId else '',
                'edid_product': f'{name.edidProductCodeId:04X}' if name.edidProductCodeId else '',
            })
        return extras
    except Exception:
        return []


def _match_ccd_extra(extras: list[dict], device_path: str, device_name: str) -> dict:
    for extra in extras:
        path = extra.get('device_path') or ''
        if device_path and path and (device_path.lower() in path.lower() or path.lower() in device_path.lower()):
            return extra
    if len(extras) == 1:
        return extras[0]
    return {}
