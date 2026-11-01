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


def test_classroom_app_chords_edge_detect_like_onenote_and_stay_off_by_default():
    assert HotkeyState.CLASSROOM_MODES == (
        'onenote_display', 'word_display', 'chrome_display', 'board_display')
    idle = HotkeyState()
    assert 'word_display' not in idle.enabled_modes
    assert idle.update({0x82}.__contains__) == []
    assert idle.update({0x11, 0x10, 0x12, 0x74}.__contains__) == []
    assert idle.update({0x83}.__contains__) == []
    assert idle.update({0x11, 0x10, 0x12, 0x73}.__contains__) == []
    assert idle.update({0x84}.__contains__) == []
    assert idle.update({0x11, 0x10, 0x12, 0x72}.__contains__) == []
    enabled = HotkeyState(HotkeyState.CLASSROOM_MODES)
    for mode, extended, standard in (
            ('word_display', 0x82, 0x74),
            ('chrome_display', 0x83, 0x73),
            ('board_display', 0x84, 0x72)):
        state = HotkeyState((mode,))
        keys = {0x11, 0x10, 0x12, extended, standard}
        assert state.update(keys.__contains__) == [(mode, 'down')]
        keys.remove(extended)
        assert state.update(keys.__contains__) == []
        keys.clear()
        assert state.update(keys.__contains__) == [(mode, 'up')]
    both = HotkeyState(HotkeyState.DEFAULT_MODES + HotkeyState.CLASSROOM_MODES)
    assert both.update({0x11, 0x10, 0x12, 0x74}.__contains__) == [('word_display', 'down')]
    assert both.update({0x11, 0x10, 0x12, 0x78}.__contains__) == [('compose', 'down'), ('word_display', 'up')]


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


def test_word_chrome_and_board_hotkeys_do_not_start_recording_or_paste():
    app = ComposeApp.__new__(ComposeApp)
    app._settings_saving = lambda: False
    app.log = Mock()
    app.set_status = Mock()
    app.start_recording_flow = Mock()
    app.inject_paste_ui = Mock()
    app.is_recording = False
    app.open_classroom_app = Mock()
    app.open_onenote_on_classroom_display = Mock()
    ComposeApp._handle_hardware_event(app, 'word_display', 'down')
    ComposeApp._handle_hardware_event(app, 'chrome_display', 'down')
    ComposeApp._handle_hardware_event(app, 'board_display', 'down')
    assert app.open_classroom_app.call_args_list == [(('word',),), (('chrome',),), (('board',),)]
    app.open_onenote_on_classroom_display.assert_not_called()
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


def test_restore_focus_does_not_unmaximise_non_minimised_classroom_onenote():
    with patch('focus_tracker.win32gui.IsWindow', return_value=True), \
            patch('focus_tracker.win32gui.IsIconic', return_value=False), \
            patch('focus_tracker.win32gui.GetForegroundWindow', side_effect=[10, 10, 77]), \
            patch('focus_tracker.win32gui.GetWindowText', return_value='Notebook - OneNote'), \
            patch('focus_tracker.win32process.GetWindowThreadProcessId', side_effect=lambda h: (2, 10) if h == 10 else (1, 500)), \
            patch('focus_tracker.win32gui.ShowWindow') as show_window, \
            patch('focus_tracker.win32gui.SetForegroundWindow') as set_fg:
        assert FocusTracker.restore_focus({'hwnd': 77, 'pid': 500, 'title': 'Notebook - OneNote'})
        show_window.assert_not_called()
        set_fg.assert_called_once_with(77)


def test_restore_focus_restores_minimised_window():
    with patch('focus_tracker.win32gui.IsWindow', return_value=True), \
            patch('focus_tracker.win32gui.IsIconic', return_value=True), \
            patch('focus_tracker.win32gui.GetForegroundWindow', side_effect=[10, 10, 77]), \
            patch('focus_tracker.win32gui.GetWindowText', return_value='Notebook - OneNote'), \
            patch('focus_tracker.win32process.GetWindowThreadProcessId', side_effect=lambda h: (2, 10) if h == 10 else (1, 500)), \
            patch('focus_tracker.win32gui.ShowWindow') as show_window, \
            patch('focus_tracker.win32gui.SetForegroundWindow') as set_fg:
        assert FocusTracker.restore_focus({'hwnd': 77, 'pid': 500, 'title': 'Notebook - OneNote'})
        show_window.assert_called_once_with(77, 9)
        set_fg.assert_called_once_with(77)


def test_gui_stop_recording_restores_document_focus_after_button_click():
    app = ComposeApp.__new__(ComposeApp)
    app.root = Mock()
    app.audio_capture = Mock()
    app.audio_capture.stop_recording.return_value = (b'audio', 1.2, 200.0)
    app._ui_events = queue.Queue()
    app._stop_poller = False
    app._recording_timer = None
    app._busy = False
    app.is_recording = True
    app.recording_mode = 'compose'
    app.btn_compose = Mock()
    app.btn_dictate = Mock()
    app.log = Mock()
    app.set_status = Mock()
    app._target_focus_snap = {'hwnd': 77, 'pid': 555, 'title': 'OneNote', 'runtime_id': [1, 2]}
    app._target_selected_text = ''
    with patch('compose_gui.FocusTracker.snapshot_foreground_window', return_value={'hwnd': 1, 'pid': os.getpid()}), \
            patch('compose_gui.FocusTracker.restore_focus', return_value=True) as restore, \
            patch('compose_gui.FocusTracker.is_focus_matched', return_value=True), \
            patch('compose_gui.FocusTracker.get_focus_snapshot', return_value={'hwnd': 77, 'pid': 555, 'title': 'OneNote', 'runtime_id': [3, 4]}), \
            patch('compose_gui.threading.Thread') as thread:
        app.stop_recording_flow()
        restore.assert_called_once()
        passed_snap = thread.call_args.kwargs['args'][2]
        assert passed_snap['hwnd'] == 77
        assert passed_snap['runtime_id'] == [3, 4]


def test_remember_external_focus_ignores_windows_shell_chrome():
    app = ComposeApp.__new__(ComposeApp)
    app._stop_poller = False
    previous = {'hwnd': 77, 'pid': 555, 'title': 'Notebook - OneNote'}
    app._last_external_snap = previous
    app.root = Mock()
    with patch('compose_gui.FocusTracker.snapshot_foreground_window', return_value={'hwnd': 99, 'pid': 888, 'title': ''}), \
            patch('focus_tracker.win32gui.GetClassName', return_value='Shell_TrayWnd'):
        app._remember_external_focus()
    assert app._last_external_snap is previous


def test_is_onenote_canvas_ready_distinguishes_canvas_from_ribbon():
    with patch.object(FocusTracker, 'get_focused_child_hwnd', return_value=123), \
            patch('focus_tracker.win32gui.GetClassName', side_effect=lambda h: 'OneNote::DocumentCanvas' if h == 123 else 'Framework::CFrame'):
        assert FocusTracker.is_onenote_canvas_ready(50) is True

    with patch.object(FocusTracker, 'get_focused_child_hwnd', return_value=456), \
            patch('focus_tracker.win32gui.GetClassName', side_effect=lambda h: 'NetUIHWND' if h == 456 else 'Framework::CFrame'), \
            patch('focus_tracker.win32gui.GetWindowText', return_value='Notebook - OneNote'):
        assert FocusTracker.is_onenote_canvas_ready(50) is False

    with patch.object(FocusTracker, 'get_focused_child_hwnd', return_value=789), \
            patch('focus_tracker.win32gui.GetClassName', side_effect=lambda h: 'Edit' if h == 789 else 'Notepad'), \
            patch('focus_tracker.win32gui.GetWindowText', return_value='Untitled - Notepad'):
        assert FocusTracker.is_onenote_canvas_ready(50) is None


def test_deliver_result_restores_external_target_if_host_is_foreground():
    app = ComposeApp.__new__(ComposeApp)
    app.pending_ready_payload = None
    app.restore_delay = 0.01
    app.log = Mock()
    app.set_status = Mock()
    focus_snap = {'hwnd': 77, 'pid': 500, 'title': 'Notebook - OneNote'}

    with patch('compose_gui.FocusTracker.snapshot_foreground_window', return_value={'hwnd': 1, 'pid': os.getpid()}), \
            patch('compose_gui.FocusTracker.restore_focus', return_value=True) as restore, \
            patch('compose_gui.FocusTracker.is_focus_matched', return_value=True), \
            patch('compose_gui.FocusTracker.is_onenote_canvas_ready', return_value=True), \
            patch('compose_gui.ClipboardManager.inject_paste', return_value=True) as inject:
        app._deliver_result('Hello World', focus_snap)
        restore.assert_called_once_with({'hwnd': 77, 'pid': 500, 'title': 'Notebook - OneNote', 'runtime_id': None})
        inject.assert_called_once_with('Hello World', restore_delay=0.01)
        assert app.pending_ready_payload is None
        app.log.assert_called_with('Paste shortcut sent to the original document.')


def test_deliver_result_warns_if_onenote_canvas_is_not_focused():
    app = ComposeApp.__new__(ComposeApp)
    app.pending_ready_payload = None
    app.restore_delay = 0.01
    app.log = Mock()
    app.set_status = Mock()
    focus_snap = {'hwnd': 77, 'pid': 500, 'title': 'Notebook - OneNote'}

    with patch('compose_gui.FocusTracker.snapshot_foreground_window', return_value={'hwnd': 1, 'pid': os.getpid()}), \
            patch('compose_gui.FocusTracker.restore_focus', return_value=True), \
            patch('compose_gui.FocusTracker.is_focus_matched', return_value=True), \
            patch('compose_gui.FocusTracker.is_onenote_canvas_ready', return_value=False), \
            patch('compose_gui.ClipboardManager.inject_paste') as inject:
        app._deliver_result('Hello World', focus_snap)
        inject.assert_not_called()
        assert app.pending_ready_payload == 'Hello World'
        assert 'OneNote page canvas is not focused' in app.log.call_args[0][0]

