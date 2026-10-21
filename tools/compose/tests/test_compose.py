"""Regression checks without recording, network requests or desktop keystrokes."""
import ctypes
import os
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
    app._target_focus_snap = None
    app._last_external_snap = None
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
    with patch('compose_gui.FocusTracker.restore_focus', return_value=False), patch('compose_gui.FocusTracker.is_focus_matched', return_value=False), patch('compose_gui.ClipboardManager.inject_paste') as paste:
        app._deliver_result('Keep this text', {'hwnd': 42})
        paste.assert_not_called()
    assert app.pending_ready_payload == 'Keep this text'


def test_failed_paste_keeps_payload_for_retry():
    app = make_app()
    with patch('compose_gui.FocusTracker.restore_focus', return_value=True), patch('compose_gui.FocusTracker.is_focus_matched', return_value=True), patch('compose_gui.ClipboardManager.inject_paste', return_value=False):
        app._deliver_result('Keep this text', {'hwnd': 42})
    assert app.pending_ready_payload == 'Keep this text'


def test_successful_paste_clears_pending_payload():
    app = make_app()
    with patch('compose_gui.FocusTracker.restore_focus', return_value=True), patch('compose_gui.FocusTracker.is_focus_matched', return_value=True), patch('compose_gui.ClipboardManager.inject_paste', return_value=True):
        app._deliver_result('Final text', {'hwnd': 42})
    assert app.pending_ready_payload is None


def test_same_window_still_matches_when_uia_runtime_id_changes():
    from focus_tracker import FocusTracker
    snap = {'hwnd': 99, 'runtime_id': [1, 2, 3]}
    with patch('focus_tracker.win32gui.GetForegroundWindow', return_value=99):
        assert FocusTracker.is_focus_matched(snap) is True


def test_gui_compose_uses_last_document_when_companion_has_focus():
    app = make_app()
    app._last_external_snap = {'hwnd': 77, 'pid': 555, 'title': 'OneNote'}
    with patch('compose_gui.FocusTracker.get_focus_snapshot', return_value={'hwnd': 1, 'pid': os.getpid(), 'title': 'Companion'}), \
         patch('compose_gui.FocusTracker.capture_selected_text', return_value=''), \
         patch('os.getpid', return_value=os.getpid()):
        app.start_recording_flow('compose')
    assert app._target_focus_snap['hwnd'] == 77


def test_env_loader_reuses_hermes_groq_key_when_compose_env_is_empty(tmp_path, monkeypatch):
    from config_loader import load_env_config
    hermes = tmp_path / 'hermes.env'
    hermes.write_text('GROQ_API_KEY=gsk_home_speed_key\n', encoding='utf-8')
    compose = tmp_path / 'compose.env'
    compose.write_text('GROQ_API_KEY=\nLOCAL_ONLY=0\n', encoding='utf-8')
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    # Point fallbacks at our temp files by writing hermes/.env where loader expects it
    hermes_dir = tmp_path / 'hermes'
    hermes_dir.mkdir()
    (hermes_dir / '.env').write_text('GROQ_API_KEY=gsk_home_speed_key\n', encoding='utf-8')
    cfg = load_env_config(tmp_path)
    assert cfg.get('GROQ_API_KEY') == 'gsk_home_speed_key'
    assert cfg.get('LOCAL_ONLY') == '0'


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


def test_auto_device_uses_cpu_when_cublas_missing():
    pipeline = SpeechPipeline(local_only=True)
    with patch('speech_pipeline.cuda_runtime_usable', return_value=False):
        assert pipeline._choose_device() == 'cpu'


def test_cuda_child_crash_retries_cpu_without_loading_gpu_in_gui():
    pipeline = SpeechPipeline(local_only=True)
    cpu = Mock()
    cpu.transcribe.return_value = ([Mock(text='Hello there')], None)
    with patch('speech_pipeline.cuda_runtime_usable', return_value=True), \
         patch.object(pipeline, '_transcribe_subprocess', return_value=(None, 'exit -1073740791')) as isolated, \
         patch('faster_whisper.WhisperModel', return_value=cpu) as model:
        assert pipeline._transcribe_local(b'fixture') == 'Hello there'
        isolated.assert_called_once_with(b'fixture', 'cuda')
        model.assert_called_once_with('base', device='cpu', compute_type='int8')
    assert pipeline._cuda_unusable is True
    assert pipeline._resolved_device == 'cpu'


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


def test_capture_selected_text_extracts_via_text_pattern():
    from focus_tracker import FocusTracker
    import uiautomation as auto

    mock_range = Mock()
    mock_range.GetText.return_value = "Selected essay text"

    mock_pattern = Mock()
    mock_pattern.GetSelection.return_value = [mock_range]

    mock_control = Mock()
    mock_control.GetPattern.side_effect = lambda pat_id: mock_pattern if pat_id == auto.PatternId.TextPattern else None

    with patch("uiautomation.GetFocusedControl", return_value=mock_control):
        assert FocusTracker.capture_selected_text() == "Selected essay text"


def test_capture_selected_text_falls_back_to_parent():
    from focus_tracker import FocusTracker
    import uiautomation as auto

    mock_range = Mock()
    mock_range.GetText.return_value = "Parent essay text"

    mock_pattern = Mock()
    mock_pattern.GetSelection.return_value = [mock_range]

    mock_parent = Mock()
    mock_parent.GetPattern.side_effect = lambda pat_id: mock_pattern if pat_id == auto.PatternId.TextPattern else None

    mock_control = Mock()
    mock_control.GetPattern.return_value = None
    mock_control.GetParentControl.return_value = mock_parent

    with patch("uiautomation.GetFocusedControl", return_value=mock_control):
        assert FocusTracker.capture_selected_text() == "Parent essay text"


def test_capture_selected_text_falls_back_to_wm_copy_for_scintilla():
    from focus_tracker import FocusTracker

    with patch("uiautomation.GetFocusedControl", return_value=None), \
         patch.object(FocusTracker, "get_focused_child_hwnd", return_value=12345), \
         patch.object(FocusTracker, "_capture_via_wm_copy", return_value="Notepad++ essay text") as mock_copy:
        result = FocusTracker.capture_selected_text(fg_hwnd=999)
        assert result == "Notepad++ essay text"
        mock_copy.assert_called_with(12345)


def test_capture_selected_text_falls_back_to_chord_ctrl_c():
    from focus_tracker import FocusTracker

    with patch("uiautomation.GetFocusedControl", return_value=None), \
         patch.object(FocusTracker, "_capture_via_wm_copy", return_value=""), \
         patch.object(FocusTracker, "_capture_via_chord_ctrl_c", return_value="Chord captured text") as mock_ctrl_c:
        result = FocusTracker.capture_selected_text(fg_hwnd=999)
        assert result == "Chord captured text"
        mock_ctrl_c.assert_called_once()


def test_chord_ctrl_c_releases_keys_it_presses_and_restores_alt():
    from focus_tracker import FocusTracker

    events = []

    def event(vk, up=False):
        events.append((vk, up))

    seq = {"n": 0}

    def sequence():
        seq["n"] += 1
        return 1 if seq["n"] == 1 else 2

    with patch("focus_tracker._key_event", side_effect=event), \
         patch("focus_tracker._key_is_down", side_effect=lambda vk: vk == 0x12), \
         patch("focus_tracker.time.sleep"), \
         patch("focus_tracker.ctypes.windll.user32.GetClipboardSequenceNumber", side_effect=sequence), \
         patch("focus_tracker.ClipboardManager.get_clipboard_text", side_effect=["old", "copied"]), \
         patch("focus_tracker.ClipboardManager.set_clipboard_text") as restore:
        assert FocusTracker._capture_via_chord_ctrl_c() == "copied"

    assert (0x12, True) in events
    assert events[-1] == (0x12, False)
    assert [e for e in events if e[0] == 0x11] == [(0x11, False), (0x11, True)]
    restore.assert_called_once_with("old")


def test_chord_ctrl_c_releases_ctrl_when_injection_fails():
    from focus_tracker import FocusTracker

    events = []

    def event(vk, up=False):
        events.append((vk, up))
        if vk == 0x43 and not up:
            raise OSError("injected")

    with patch("focus_tracker._key_event", side_effect=event), \
         patch("focus_tracker._key_is_down", return_value=False), \
         patch("focus_tracker.time.sleep"), \
         patch("focus_tracker.ctypes.windll.user32.GetClipboardSequenceNumber", return_value=1), \
         patch("focus_tracker.ClipboardManager.get_clipboard_text", return_value="old"):
        assert FocusTracker._capture_via_chord_ctrl_c() == ""

    assert (0x11, True) in events


def test_capture_selected_text_ignores_this_process():
    import os
    from focus_tracker import FocusTracker

    with patch("uiautomation.GetFocusedControl", return_value=None), \
         patch("focus_tracker.win32process.GetWindowThreadProcessId", return_value=(1, os.getpid())), \
         patch.object(FocusTracker, "_capture_via_wm_copy") as copy, \
         patch.object(FocusTracker, "_capture_via_chord_ctrl_c") as chord:
        assert FocusTracker.capture_selected_text(fg_hwnd=999) == ""
    copy.assert_not_called()
    chord.assert_not_called()


def test_groq_stt_network_failure_stays_on_local_whisper():
    import requests
    pipeline = SpeechPipeline(groq_api_key="gsk-test")
    groq_calls = {"n": 0}

    def groq(_wav):
        groq_calls["n"] += 1
        raise requests.ConnectionError("blocked")

    with patch.object(pipeline, "_transcribe_groq", side_effect=groq), \
         patch.object(pipeline, "_transcribe_local", return_value="hello"):
        text, provider, _ = pipeline.transcribe(b"x" * 120)
        assert (text, provider) == ("hello", "local_whisper")
        assert pipeline.cloud_down is True
        pipeline.transcribe(b"y" * 120)
    assert groq_calls["n"] == 1


def test_groq_timeout_latches_local_ollama():
    import requests
    from llm_pipeline import LlmPipeline

    pipeline = LlmPipeline(groq_api_key="gsk-test", local_only=False)
    groq_calls = {"n": 0}

    def groq(*_args, **_kwargs):
        groq_calls["n"] += 1
        raise requests.Timeout("blocked")

    with patch.object(pipeline, "_call_groq", side_effect=groq), \
         patch.object(pipeline, "_call_ollama", return_value=("ok", "stop")):
        text, provider, _, _ = pipeline.generate([{"role": "user", "content": "hi"}])
        assert (text, provider, pipeline.local_only) == ("ok", "ollama", True)
        pipeline.generate([{"role": "user", "content": "again"}])
    assert groq_calls["n"] == 1


def test_ollama_uses_installed_model_when_configured_model_is_missing():
    from llm_pipeline import LlmPipeline

    pipeline = LlmPipeline(local_only=True, ollama_model="llama3.2:latest")
    missing = Mock(status_code=404, text="model not found")
    ok = Mock(status_code=200)
    ok.json.return_value = {"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}]}
    tags = Mock(status_code=200)
    tags.json.return_value = {"models": [{"name": "qwen3.5:latest"}]}
    with patch("llm_pipeline.requests.post", side_effect=[missing, ok]) as post, \
         patch("llm_pipeline.requests.get", return_value=tags):
        text, provider, _, _ = pipeline.generate([{"role": "user", "content": "hi"}])
    assert (text, provider, pipeline.ollama_model) == ("hi", "ollama", "qwen3.5:latest")
    assert post.call_args_list[1].kwargs["json"]["model"] == "qwen3.5:latest"

