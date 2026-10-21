"""Privacy and lifecycle checks for changing a running companion's settings."""
import sys
import threading
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compose_gui import ComposeApp
from assistant_panel import AssistantPanel
from media_panel import MediaPanel


def app_fixture():
    app = ComposeApp.__new__(ComposeApp)
    app.config = {"LOCAL_ONLY": "0"}
    app.local_only = False
    app._busy = app.is_recording = False
    app._sync_stop = threading.Event()
    app._sync_thread = Mock()
    app._sync_thread.is_alive.side_effect = [True, False]
    app.hermes_service = Mock()
    app.receiver = Mock(owns_process=True)
    app.voice_bridge = Mock()
    app._post_ui = Mock()
    return app


def test_local_only_settings_wait_for_sync_and_stop_only_owned_receiver():
    app = app_fixture()
    bridge = app.voice_bridge
    rollback = app._validate_settings_before_save({"LOCAL_ONLY": "1"})
    assert callable(rollback)
    assert app._sync_stop.is_set()
    app._sync_thread.join.assert_called_once_with(timeout=18.0)
    app.receiver.stop.assert_called_once()
    bridge.close.assert_called_once()
    assert app.voice_bridge is None
    # Applying/persisting occurs later; preflight alone never claims the mode.
    assert not app.local_only


def test_local_only_preserves_external_receiver():
    app = app_fixture()
    app.receiver.owns_process = False
    app._validate_settings_before_save({"LOCAL_ONLY": "1"})
    app.receiver.stop.assert_not_called()


def test_unfinished_network_request_prevents_settings_commit():
    app = app_fixture()
    app._sync_thread.is_alive.side_effect = None
    app._sync_thread.is_alive.return_value = True
    with pytest.raises(ValueError, match="still finishing"):
        app._validate_settings_before_save({"LOCAL_ONLY": "1"})
    assert len(app.hermes_service.update_config.call_args_list) == 2
    assert app.hermes_service.update_config.call_args_list[-1].args[0]["LOCAL_ONLY"] is False
    app.receiver.stop.assert_not_called()


def test_running_ask_request_prevents_settings_transition():
    app = app_fixture()
    app.assistant_panel = Mock(_busy=True)
    with pytest.raises(ValueError, match="Finish recording"):
        app._validate_settings_before_save({"LOCAL_ONLY": "1"})
    app.hermes_service.update_config.assert_not_called()


def test_settings_transition_blocks_new_hardware_and_recording():
    app = ComposeApp.__new__(ComposeApp)
    app.settings_panel = Mock(_saving=True)
    app.is_recording = app._busy = False
    app.audio_capture = Mock()
    app.start_recording_flow()
    app.audio_capture.start_recording.assert_not_called()
    with patch.object(app, "inject_paste_ui") as paste:
        app._handle_hardware_event("paste", "up")
        paste.assert_not_called()


def test_settings_transition_blocks_new_assistant_and_media_work():
    assistant = AssistantPanel.__new__(AssistantPanel)
    assistant.settings_saving = lambda: True
    assistant.notice = Mock()
    assistant.send()
    assistant.notice.configure.assert_called_once()
    media = MediaPanel.__new__(MediaPanel)
    media.settings_saving = lambda: True
    media.tell = Mock()
    operation = Mock()
    media.run(operation, Mock())
    operation.assert_not_called()
    media.tell.assert_called_once()


def test_close_waits_for_an_explicit_settings_save():
    app = ComposeApp.__new__(ComposeApp)
    app.settings_panel = Mock(_saving=True)
    app.root = Mock()
    app.close()
    app.root.destroy.assert_not_called()
    app.settings_panel.set_status.assert_called_once()
