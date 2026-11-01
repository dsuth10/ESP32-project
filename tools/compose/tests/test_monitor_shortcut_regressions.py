"""Existing hotkey, focus and Paste Ready behaviour must stay unchanged."""
from __future__ import annotations

import os
import queue
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compose_gui import ComposeApp
from focus_tracker import FocusTracker
from hotkey_state import HotkeyState
from monitor_shortcut import MonitorShortcutController
from window_monitor_manager import FakeWindowMonitorBackend, MonitorInfo, Rect


def test_default_hotkey_state_still_has_the_five_firmware_modes_only():
    state = HotkeyState()
    assert tuple(state.enabled_modes) == HotkeyState.DEFAULT_MODES
    assert state.update({0x81}.__contains__) == []
    assert state.update({0x11, 0x10, 0x12, 0x75}.__contains__) == []


def test_existing_compose_chord_still_coalesces():
    state = HotkeyState()
    keys = {0x11, 0x10, 0x12, 0x78, 0x7C}
    assert state.update(keys.__contains__) == [('compose', 'down')]
    keys.remove(0x7C)
    assert state.update(keys.__contains__) == []
    keys.clear()
    assert state.update(keys.__contains__) == [('compose', 'up')]


def test_optional_onenote_chord_coalesces_only_when_enabled():
    state = HotkeyState(('onenote_display',))
    keys = {0x11, 0x10, 0x12, 0x81, 0x75}
    assert state.update(keys.__contains__) == [('onenote_display', 'down')]
    keys.remove(0x81)
    assert state.update(keys.__contains__) == []
    keys.clear()
    assert state.update(keys.__contains__) == [('onenote_display', 'up')]


def test_onenote_hotkey_does_not_start_recording_or_paste(tmp_path):
    app = ComposeApp.__new__(ComposeApp)
    app._settings_saving = lambda: False
    app.log = Mock()
    app.set_status = Mock()
    app.start_recording_flow = Mock()
    app.inject_paste_ui = Mock()
    app.is_recording = False
    popups = []
    backend = FakeWindowMonitorBackend([
        MonitorInfo(1, 'Board', '\\\\.\\DISPLAY2', '\\\\?\\DISPLAY#ABC', 'PRM', '0001',
                    Rect(1920, 0, 3840, 1080), Rect(1920, 0, 3840, 1080), 96)
    ], [])
    app.monitor_shortcut = MonitorShortcutController(
        backend=backend, root=tmp_path, popup=popups.append, wait_timeout_s=0.01)
    settings = app.monitor_shortcut.load()
    settings['profiles']['Home']['classroom_display'] = backend.monitors[0].identity_record()
    settings['profiles']['Home']['last_seen_identities'] = [backend.monitors[0].durable_key()]
    app.monitor_shortcut.save(settings)
    backend.launch_window = None
    app.open_onenote_on_classroom_display = Mock()
    ComposeApp._handle_hardware_event(app, 'onenote_display', 'down')
    app.open_onenote_on_classroom_display.assert_called_once()
    app.start_recording_flow.assert_not_called()
    app.inject_paste_ui.assert_not_called()


def test_library_and_paste_hotkeys_are_unchanged():
    app = ComposeApp.__new__(ComposeApp)
    app._settings_saving = lambda: False
    app.log = Mock()
    app.is_recording = False
    app.start_recording_flow = Mock()
    app.inject_paste_ui = Mock()
    app.media_tab = object()
    app.tabs = Mock()
    app.root = Mock()
    app.media_panel = Mock()
    app.open_onenote_on_classroom_display = Mock()
    ComposeApp._handle_hardware_event(app, 'library', 'down')
    app.media_panel.refresh.assert_called_once()
    ComposeApp._handle_hardware_event(app, 'paste', 'up')
    app.inject_paste_ui.assert_called_once()
    app.open_onenote_on_classroom_display.assert_not_called()
    app.start_recording_flow.assert_not_called()


def test_classroom_action_does_not_touch_paste_ready_or_media_targets(tmp_path):
    app = ComposeApp.__new__(ComposeApp)
    app._settings_saving = lambda: False
    app.log = Mock()
    app.set_status = Mock()
    app.pending_ready_payload = 'Queued writing'
    app.pending_media = {'version_id': 'keep-me'}
    classroom = MonitorInfo(1, 'Board', '\\\\.\\DISPLAY2', '\\\\?\\DISPLAY#ABC', 'PRM', '0001',
                            Rect(1920, 0, 3840, 1080), Rect(1920, 0, 3840, 1080), 96)
    from window_monitor_manager import AppWindow
    backend = FakeWindowMonitorBackend([classroom], [
        AppWindow(8, 11, 'Notebook', 'ONENOTE.EXE', Rect(0, 0, 400, 300), last_foreground_at=1)
    ])
    app.monitor_shortcut = MonitorShortcutController(backend=backend, root=tmp_path, popup=Mock())
    settings = app.monitor_shortcut.load()
    settings['profiles']['Home']['classroom_display'] = classroom.identity_record()
    settings['profiles']['Home']['last_seen_identities'] = [classroom.durable_key()]
    app.monitor_shortcut.save(settings)
    with patch('media_targets.capture_target') as capture, patch('media_targets.insert_image') as insert:
        ComposeApp.open_onenote_on_classroom_display(app)
    capture.assert_not_called()
    insert.assert_not_called()
    assert app.pending_ready_payload == 'Queued writing'
    assert app.pending_media == {'version_id': 'keep-me'}


def test_restore_focus_still_refuses_internal_snapshots():
    previous = set(FocusTracker._internal_processes)
    try:
        FocusTracker.register_internal_process(912345)
        snapshot = {'hwnd': 71, 'pid': 912345, 'title': 'Teacher'}
        assert not FocusTracker.restore_focus(snapshot)
        assert not FocusTracker.request_foreground(71, restore=False)
    finally:
        FocusTracker._internal_processes = previous


def test_explicit_onenote_keyboard_paste_still_requires_the_flag():
    import media_targets
    target = {'hwnd': 100, 'pid': 200, 'executable': 'ONENOTE.EXE'}
    with patch.object(media_targets, 'foreground_target', return_value=target), \
            patch.object(media_targets, '_onenote_selection_collapsed', return_value=None):
        with __import__('pytest').raises(ValueError, match='selection could not be verified'):
            media_targets.capture_target()
