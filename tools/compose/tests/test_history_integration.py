"""History must survive insertion failures without changing the paste contract."""
import logging
import queue
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compose_gui import ComposeApp
from history_store import HistoryStore


def app_with_history(tmp_path):
    app = ComposeApp.__new__(ComposeApp)
    app.history = HistoryStore(tmp_path / "companion.sqlite3")
    app.history_enabled = True
    app._stop_poller = False
    app._ui_events = queue.Queue()
    app.local_only = True
    app.log = Mock()
    app.set_status = Mock()
    app.speech_pipeline = Mock()
    app.speech_pipeline.transcribe.return_value = ("A synthetic request", "fixture", 0)
    app.llm_pipeline = Mock()
    app.llm_pipeline.generate.return_value = ("A synthetic response", "fixture", 0, 1)
    return app


def test_completed_response_is_persisted_before_delivery_is_scheduled(tmp_path):
    app = app_with_history(tmp_path)
    app._process_pipeline_worker("compose", b"fixture", {"hwnd": 4}, "")
    # Delivery is still waiting on the UI queue; the stored result already survives a restart.
    stored = HistoryStore(app.history.path).list_entries()
    assert [(row["request"], row["response"]) for row in stored] == [
        ("A synthetic request", "A synthetic response")]
    callbacks = [item[0] for item in app._ui_events.queue]
    assert app._deliver_result in callbacks


def test_history_off_does_not_prevent_delivery(tmp_path):
    app = app_with_history(tmp_path)
    app.history_enabled = False
    app._process_pipeline_worker("compose", b"fixture", None, "")
    assert app.history.list_entries() == []
    assert app._deliver_result in [item[0] for item in app._ui_events.queue]


def test_storage_failure_retains_output_for_paste(tmp_path):
    app = app_with_history(tmp_path)
    app.history = Mock()
    app.history.add_entry.side_effect = OSError("fixture storage unavailable")
    app._process_pipeline_worker("compose", b"fixture", None, "")
    deliveries = [args for callback, args in app._ui_events.queue if callback == app._deliver_result]
    assert deliveries == [("A synthetic response", None)]


def test_failed_generation_is_labelled_failed_and_never_delivered(tmp_path):
    app = app_with_history(tmp_path)
    app.llm_pipeline.generate.side_effect = RuntimeError("private provider exception")
    app._process_pipeline_worker("compose", b"fixture", None, "")
    assert app.history.list_entries()[0]["status"] == "failed"
    assert app._deliver_result not in [item[0] for item in app._ui_events.queue]
    assert "private provider exception" not in str(app.log.call_args_list)


def test_queue_from_library_never_pastes_into_companion(tmp_path):
    app = app_with_history(tmp_path)
    app._busy = False
    app.is_recording = False
    with patch("compose_gui.ClipboardManager.inject_paste") as inject:
        app._queue_library_text("Stored text")
    inject.assert_not_called()
    assert app.pending_ready_payload == "Stored text"


def test_status_excludes_config_content_and_does_not_claim_bluetooth_health(tmp_path):
    app = app_with_history(tmp_path)
    app.is_recording = False
    app._busy = False
    app.pending_ready_payload = "private classroom text"
    app.audio_capture = Mock(device_name="fixture microphone")
    app.receiver = Mock()
    app.receiver.is_listening.return_value = True
    app.config = {"GROQ_API_KEY": "private key"}
    status = app._assistant_status()
    assert status["receiver_port_open"] is True
    assert "private" not in str(status)
    assert "Not verified" in status["bluetooth"]


def test_sensitive_preview_is_not_written_to_operational_log(caplog):
    app = ComposeApp.__new__(ComposeApp)
    app._ui_events = queue.Queue()
    with caplog.at_level(logging.INFO):
        app.log("Synthetic private transcript", content=True)
        app.log("Finished processing")
    assert "Synthetic private transcript" not in caplog.text
    assert "Finished processing" in caplog.text
    assert "Synthetic private transcript" in str(list(app._ui_events.queue))
