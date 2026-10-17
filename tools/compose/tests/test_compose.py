"""Regression checks without recording, network requests or desktop keystrokes."""
import ctypes
import queue
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hotkey_state import HotkeyState
from compose_gui import ComposeApp
from clipboard_manager import ClipboardManager, _Input
from prompt_engine import verify_dictate_overlap
from speech_pipeline import SpeechPipeline


def test_firmware_dual_keys_produce_one_press_and_one_release():
    state = HotkeyState()
    keys = {0x11, 0x10, 0x12, 0x78, 0x7C}
    assert state.update(keys.__contains__) == [("compose", "down")]
    assert state.update(keys.__contains__) == []
    keys.remove(0x7C)
    assert state.update(keys.__contains__) == []
    keys.clear()
    assert state.update(keys.__contains__) == [("compose", "up")]


def test_cached_descriptor_standard_chord_survives_modifier_release():
    state = HotkeyState()
    assert state.update({0x11, 0x10, 0x12, 0x79}.__contains__) == [("dictate", "down")]
    assert state.update({0x79}.__contains__) == []
    assert state.update(set().__contains__) == [("dictate", "up")]


def test_unmodified_function_keys_do_not_record():
    assert HotkeyState().update({0x78}.__contains__) == []


def make_app():
    app = ComposeApp.__new__(ComposeApp)
    app.root = Mock()
    app.audio_capture = Mock()
    app.audio_capture.start_recording.return_value = True
    app.audio_capture.stop_recording.return_value = (b"test audio", 1.0, 100)
    app._ui_events = queue.Queue()
    app._stop_poller = False
    app._recording_timer = None
    app._busy = False
    app.is_recording = False
    app.btn_compose = Mock()
    app.btn_dictate = Mock()
    app.log = Mock()
    app.set_status = Mock()
    app.pending_ready_payload = None
    app.restore_delay = 0
    return app


def test_hardware_release_stops_recording_instead_of_waiting_for_another_down():
    app = make_app()
    with patch('compose_gui.FocusTracker.get_focus_snapshot', return_value=None), patch('compose_gui.threading.Thread') as thread:
        app._handle_hardware_event('dictate', 'down')
        assert app.is_recording
        app._handle_hardware_event('dictate', 'up')
        assert not app.is_recording
        app.audio_capture.stop_recording.assert_called_once()
        thread.return_value.start.assert_called_once()


def test_microphone_failure_does_not_claim_to_record():
    app = make_app()
    app.audio_capture.start_recording.return_value = False
    app.start_recording_flow('compose')
    assert not app.is_recording
    app.root.after.assert_not_called()


def test_busy_pipeline_rejects_new_recording():
    app = make_app()
    app._busy = True
    app.start_recording_flow()
    app.audio_capture.start_recording.assert_not_called()


def test_paste_runs_on_release_after_hid_modifiers_are_up():
    app = make_app()
    app.inject_paste_ui = Mock()
    app._handle_hardware_event('paste', 'down')
    app.inject_paste_ui.assert_not_called()
    app._handle_hardware_event('paste', 'up')
    app.inject_paste_ui.assert_called_once()


def test_changed_focus_keeps_result_ready_without_paste():
    app = make_app()
    with patch('compose_gui.FocusTracker.is_focus_matched', return_value=False), patch('compose_gui.ClipboardManager.inject_paste') as paste:
        app._deliver_result('Keep this text', {'hwnd': 42})
        paste.assert_not_called()
    assert app.pending_ready_payload == 'Keep this text'


def test_failed_paste_keeps_payload_for_retry():
    app = make_app()
    with patch('compose_gui.FocusTracker.is_focus_matched', return_value=True), patch('compose_gui.ClipboardManager.inject_paste', return_value=False):
        app._deliver_result('Keep this text', {'hwnd': 42})
    assert app.pending_ready_payload == 'Keep this text'


def test_successful_paste_clears_pending_payload():
    app = make_app()
    with patch('compose_gui.FocusTracker.is_focus_matched', return_value=True), patch('compose_gui.ClipboardManager.inject_paste', return_value=True):
        app._deliver_result('Final text', {'hwnd': 42})
    assert app.pending_ready_payload is None


def test_rejected_cleanup_is_not_treated_as_truthy_boolean():
    app = make_app()
    transcript = 'write an essay on biology'
    app.speech_pipeline = Mock()
    app.speech_pipeline.transcribe.return_value = (transcript, 'fixture', 0)
    app.llm_pipeline = Mock()
    app.llm_pipeline.generate.return_value = ('Biology is the scientific study of living organisms.', 'fixture', 0, 1)
    app._process_pipeline_worker('dictate', b'audio', None, '')
    callback, args = app._ui_events.get_nowait()
    assert callback == app._deliver_result
    assert args[0] == transcript


def test_dictation_survives_unavailable_cleanup_provider():
    app = make_app()
    app.speech_pipeline = Mock()
    app.speech_pipeline.transcribe.return_value = ('Hello there', 'fixture', 0)
    app.llm_pipeline = Mock()
    app.llm_pipeline.generate.side_effect = ConnectionError('offline')
    app._process_pipeline_worker('dictate', b'audio', None, '')
    _, args = app._ui_events.get_nowait()
    assert args[0] == 'Hello there'


def test_native_input_struct_matches_windows_abi():
    assert ctypes.sizeof(_Input) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)


def test_paste_failure_restores_previous_clipboard():
    with patch.object(ClipboardManager, 'get_clipboard_text', return_value='previous'), patch.object(ClipboardManager, '_open_clipboard_retry', return_value=True), patch('clipboard_manager.win32clipboard') as clipboard, patch('clipboard_manager.send_paste_shortcut', side_effect=OSError('blocked')):
        assert not ClipboardManager.inject_paste('new text', restore_delay=0)
        assert clipboard.SetClipboardData.call_args.args[1] == 'previous'


def test_dictate_guard_accepts_punctuation():
    assert verify_dictate_overlap('hello there', 'Hello there.') == 'Hello there.'


def test_auto_whisper_retries_lazy_cuda_failure_on_cpu():
    pipeline = SpeechPipeline(local_only=True)
    pipeline._resolved_device = 'cuda'
    def broken_segments():
        raise RuntimeError('cublas64_12.dll missing')
        yield
    gpu = Mock()
    gpu.transcribe.return_value = (broken_segments(), None)
    cpu = Mock()
    cpu.transcribe.return_value = ([Mock(text='Hello there')], None)
    pipeline._local_model = gpu
    with patch('faster_whisper.WhisperModel', return_value=cpu) as model:
        assert pipeline._transcribe_local(b'fixture') == 'Hello there'
        model.assert_called_once_with('base', device='cpu', compute_type='int8')
    assert pipeline._resolved_device == 'cpu'


def test_explicit_cuda_configuration_does_not_silently_switch_device():
    import pytest
    pipeline = SpeechPipeline(local_only=True, local_device='cuda')
    pipeline._resolved_device = 'cuda'
    pipeline._local_model = Mock()
    pipeline._local_model.transcribe.side_effect = RuntimeError('missing library')
    with pytest.raises(RuntimeError):
        pipeline._transcribe_local(b'fixture')
