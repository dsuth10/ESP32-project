"""Embedded controls preserve document targeting and vetoable two-phase close."""
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from companion_embedded import EmbeddedLifecycle, close_block_reason, validate_parent, _detach
from focus_tracker import FocusTracker
from compose_gui import ComposeApp


@pytest.fixture(autouse=True)
def internal_pids():
    previous = set(FocusTracker._internal_processes)
    yield
    FocusTracker._internal_processes = previous


def idle_app():
    return SimpleNamespace(_busy=False, is_recording=False, pending_ready_payload=None,
                           settings_panel=SimpleNamespace(_saving=False),
                           assistant_panel=SimpleNamespace(_busy=False),
                           media_panel=SimpleNamespace(_busy=False),
                           hermes_panel=SimpleNamespace(_busy=False), close=Mock())


@pytest.mark.parametrize('owner', ['own', 'teacher'])
def test_internal_windows_are_rejected_before_selection_inspection(owner):
    pid = os.getpid() if owner == 'own' else 912345
    FocusTracker.register_internal_process(912345)
    with patch('focus_tracker.win32gui.GetForegroundWindow', return_value=71), \
         patch('focus_tracker.win32process.GetWindowThreadProcessId', return_value=(1, pid)), \
         patch('focus_tracker.auto.GetFocusedControl') as inspect, \
         patch.object(FocusTracker, '_capture_via_wm_copy') as copy, \
         patch.object(FocusTracker, '_capture_via_chord_ctrl_c') as chord:
        assert FocusTracker.capture_selected_text(71) == ''
    inspect.assert_not_called()
    copy.assert_not_called()
    chord.assert_not_called()


def test_stale_document_snapshot_cannot_capture_new_teacher_field():
    with patch('focus_tracker.win32gui.GetForegroundWindow', return_value=72), \
         patch('focus_tracker.auto.GetFocusedControl') as inspect:
        assert FocusTracker.capture_selected_text(71) == ''
    inspect.assert_not_called()


def test_parent_teacher_and_pupil_cannot_be_restored_or_match_automatic_paste():
    FocusTracker.register_internal_process(912345)
    snapshot = {'hwnd': 71, 'pid': 912345, 'title': 'Private teacher field'}
    with patch('focus_tracker.win32gui.SetForegroundWindow') as restore:
        assert not FocusTracker.restore_focus(snapshot)
        assert not FocusTracker.is_focus_matched(snapshot)
    restore.assert_not_called()


def test_external_word_target_still_matches_without_reading_teacher_data():
    snapshot = {'hwnd': 71, 'pid': 912346, 'title': 'Word fixture'}
    with patch('focus_tracker.win32gui.GetForegroundWindow', return_value=71), \
         patch('focus_tracker.win32gui.GetWindowText', return_value='Word fixture'), \
         patch('focus_tracker.win32process.GetWindowThreadProcessId', return_value=(1, 912346)):
        assert FocusTracker.is_focus_matched(snapshot)


def test_remembered_document_is_not_replaced_by_teacher_or_pupil_window():
    FocusTracker.register_internal_process(912345)
    app = ComposeApp.__new__(ComposeApp)
    app._stop_poller = False
    previous = {'hwnd': 71, 'pid': 912346}
    app._last_external_snap = previous
    app.root = Mock()
    with patch.object(FocusTracker, 'snapshot_foreground_window', return_value={'hwnd': 72, 'pid': 912345}):
        app._remember_external_focus()
    assert app._last_external_snap is previous


@pytest.mark.parametrize('field', ['is_recording', '_busy', 'settings_panel', 'assistant_panel', 'media_panel', 'hermes_panel'])
def test_close_preflight_refuses_active_work(field):
    app = idle_app()
    if field.endswith('_panel'):
        setattr(app, field, SimpleNamespace(**({'_saving': True} if field == 'settings_panel' else {'_busy': True})))
    else:
        setattr(app, field, True)
    events = []
    lifecycle = EmbeddedLifecycle(app, events.append)
    lifecycle.handle({'type': 'prepare_close', 'request_id': 'test-close'})
    assert events[-1]['type'] == 'close_blocked'
    app.close.assert_not_called()
    assert lifecycle.prepared is None


def test_board_veto_cancels_prepared_close_without_losing_queued_text():
    app = idle_app()
    app.pending_ready_payload = 'Private queued result'
    events, enabled = [], []
    lifecycle = EmbeddedLifecycle(app, events.append, enabled.append)
    lifecycle.handle({'type': 'prepare_close', 'request_id': 'test-close'})
    assert events[-1]['code'] == 'pending_text'
    lifecycle.handle({'type': 'prepare_close', 'request_id': 'test-close', 'discard_queued_text': True})
    assert events[-1]['type'] == 'close_ready'
    assert app.pending_ready_payload == 'Private queued result'
    assert app._shutdown_prepared
    lifecycle.handle({'type': 'cancel_close', 'request_id': 'test-close'})
    assert app.pending_ready_payload == 'Private queued result'
    assert not app._shutdown_prepared
    assert enabled == [False, True]
    app.close.assert_not_called()


def test_discard_consent_cannot_bypass_busy_work_and_only_commits_after_correct_identity():
    app = idle_app()
    app.pending_ready_payload = 'Queued text'
    app.media_panel._busy = True
    events = []
    lifecycle = EmbeddedLifecycle(app, events.append)
    lifecycle.handle({'type': 'prepare_close', 'request_id': 'test-close', 'discard_queued_text': True})
    assert events[-1]['type'] == 'close_blocked'
    assert app.pending_ready_payload == 'Queued text'
    app.media_panel._busy = False
    lifecycle.handle({'type': 'prepare_close', 'request_id': 'test-close', 'discard_queued_text': True})
    lifecycle.handle({'type': 'commit_close', 'request_id': 'unrelated'})
    app.close.assert_not_called()
    assert app.pending_ready_payload == 'Queued text'
    lifecycle.handle({'type': 'commit_close', 'request_id': 'test-close'})
    app.close.assert_called_once()
    assert app.pending_ready_payload is None
    assert events[-1] == {'type': 'closed', 'request_id': 'test-close'}


def test_close_prepared_blocks_hardware_paste_and_new_recording():
    app = ComposeApp.__new__(ComposeApp)
    app._shutdown_prepared = True
    app.settings_panel = SimpleNamespace(_saving=False)
    app._busy = app.is_recording = False
    app.audio_capture = Mock()
    app.inject_paste_ui()
    app.start_recording_flow()
    app._handle_hardware_event('paste', 'up')
    app.audio_capture.start_recording.assert_not_called()


def test_invalid_parent_is_rejected_before_opening_data_or_starting_workers():
    with pytest.raises(ValueError, match='actual parent'):
        validate_parent(os.getppid() + 1, 1)


def test_detached_companion_still_excludes_surviving_private_teacher_shell(monkeypatch):
    import win32gui
    FocusTracker.register_internal_process(912345)
    for name in ('SetParent', 'SetWindowLong', 'ShowWindow', 'SetWindowPos'):
        monkeypatch.setattr(win32gui, name, Mock())
    monkeypatch.setattr(win32gui, 'GetWindowLong', Mock(return_value=0))
    _detach(Mock(), 71, 912345)
    assert FocusTracker.is_internal_process(912345)


def test_lifecycle_events_contain_no_queued_text():
    app = idle_app()
    app.pending_ready_payload = 'Private pupil document secret'
    events = []
    EmbeddedLifecycle(app, events.append).handle({'type': 'prepare_close', 'request_id': 'x'})
    assert 'Private pupil' not in str(events)
