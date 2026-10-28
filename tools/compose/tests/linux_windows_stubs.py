"""Minimal Windows/audio import stubs for Linux collection of compose tests.

Installed only when the real modules are missing. Native Windows skipif tests
still skip. Stubs do not open a microphone, send keystrokes, or inspect windows.
"""
from __future__ import annotations

import ctypes
import sys
import types


INSTALLED: list[str] = []


def _module(name: str, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    sys.modules[name] = module
    INSTALLED.append(name)
    return module


def _missing(name: str) -> bool:
    if name in sys.modules:
        return False
    try:
        __import__(name)
    except (ImportError, OSError, AttributeError):
        return True
    return False


def _install_win32() -> None:
    if sys.platform == 'win32':
        return

    if _missing('win32gui'):
        _module(
            'win32gui',
            GetForegroundWindow=lambda: 0,
            GetWindowText=lambda hwnd: '',
            IsWindow=lambda hwnd: False,
            ShowWindow=lambda hwnd, cmd=None: None,
            SetForegroundWindow=lambda hwnd: True,
            SetParent=lambda hwnd, parent: 0,
            GetWindowLong=lambda hwnd, index: 0,
            SetWindowLong=lambda hwnd, index, value: 0,
            SetWindowPos=lambda *args, **kwargs: None,
            GetAncestor=lambda hwnd, flags: hwnd,
            EnableWindow=lambda hwnd, enabled: True,
            GetParent=lambda hwnd: 0,
            GetClassName=lambda hwnd: '',
            GetWindow=lambda hwnd, cmd: 0,
        )
    if _missing('win32process'):
        _module('win32process', GetWindowThreadProcessId=lambda hwnd: (0, 0))
    if _missing('win32con'):
        _module(
            'win32con',
            GWL_STYLE=-16,
            GWL_EXSTYLE=-20,
            WS_CHILD=0x40000000,
            WS_OVERLAPPEDWINDOW=0x00CF0000,
            SW_SHOW=5,
            SWP_NOZORDER=0x0004,
            SWP_FRAMECHANGED=0x0020,
            CF_UNICODETEXT=13,
            CF_DIB=8,
            CF_BITMAP=2,
        )
    if _missing('win32clipboard'):
        _module(
            'win32clipboard',
            OpenClipboard=lambda hwnd=None: None,
            CloseClipboard=lambda: None,
            EmptyClipboard=lambda: None,
            IsClipboardFormatAvailable=lambda fmt: False,
            GetClipboardData=lambda fmt=None: '',
            SetClipboardData=lambda fmt, data: None,
            RegisterClipboardFormat=lambda name: 0xC000,
        )
    if _missing('pywintypes'):
        class error(OSError):
            pass
        _module('pywintypes', error=error)
    if _missing('win32com'):
        client = types.ModuleType('win32com.client')
        client.Dispatch = lambda *args, **kwargs: None
        package = _module('win32com', client=client)
        sys.modules['win32com.client'] = client
        package.client = client
        INSTALLED.append('win32com.client')
    if _missing('uiautomation'):
        class PatternId:
            TextPattern = 10014

        class UIAutomationInitializerInThread:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        _module(
            'uiautomation',
            PatternId=PatternId,
            UIAutomationInitializerInThread=UIAutomationInitializerInThread,
            GetFocusedControl=lambda: None,
        )


def _install_ctypes_windll() -> None:
    if getattr(ctypes, 'windll', None) is not None:
        return

    class _User32:
        def GetAsyncKeyState(self, _vk):
            return 0

        def keybd_event(self, *_args, **_kwargs):
            return None

        def SendInput(self, count, _events, _size):
            return count

        def GetGUIThreadInfo(self, _tid, _info):
            return 0

        def GetClipboardSequenceNumber(self):
            return 0

        def SendMessageTimeoutW(self, *_args, **_kwargs):
            return 0

        def GetForegroundWindow(self):
            return 0

        def GetAncestor(self, hwnd, _flags):
            return hwnd

        def GetFocus(self):
            return 0

        def AttachThreadInput(self, *_args, **_kwargs):
            return 1

        def SetForegroundWindow(self, _hwnd):
            return 1

    class _Kernel32:
        def GetCurrentThreadId(self):
            return 0

    ctypes.windll = types.SimpleNamespace(user32=_User32(), kernel32=_Kernel32())
    INSTALLED.append('ctypes.windll')


def _install_faster_whisper() -> None:
    if not _missing('faster_whisper'):
        return

    class WhisperModel:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError('faster_whisper stub: no local Whisper weights on this host.')

        def transcribe(self, *_args, **_kwargs):
            raise RuntimeError('faster_whisper stub: no local Whisper weights on this host.')

    _module('faster_whisper', WhisperModel=WhisperModel)


def _install_sounddevice() -> None:
    if sys.modules.get('sounddevice') is not None:
        return
    try:
        import sounddevice  # noqa: F401
        return
    except (ImportError, OSError):
        pass

    class PortAudioError(OSError):
        pass

    class InputStream:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError('PortAudio stub: WASAPI capture is unavailable on this host.')

        def start(self):
            raise RuntimeError('PortAudio stub: WASAPI capture is unavailable on this host.')

        def stop(self):
            return None

        def close(self):
            return None

    _module(
        'sounddevice',
        PortAudioError=PortAudioError,
        InputStream=InputStream,
        default=types.SimpleNamespace(device=[-1, -1]),
        query_hostapis=lambda: [],
        query_devices=lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError('PortAudio stub: no recording devices on this host.')),
    )


def install_windows_stubs() -> list[str]:
    """Inject missing Windows/audio imports. Returns names that were stubbed."""
    INSTALLED.clear()
    _install_win32()
    _install_ctypes_windll()
    _install_sounddevice()
    _install_faster_whisper()
    return list(INSTALLED)
