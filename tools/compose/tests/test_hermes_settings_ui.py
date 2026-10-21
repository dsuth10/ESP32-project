from pathlib import Path
import sys
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import settings_panel
from compose_gui import ComposeApp
import compose_gui
from hermes_panel import HermesPanel


def save_panel(before_save, after_save=None):
    panel = settings_panel.SettingsPanel.__new__(settings_panel.SettingsPanel)
    panel.before_save = before_save
    panel.after_save = after_save or Mock()
    panel.post_ui = lambda callback, *args: callback(*args)
    panel._closed = False
    panel._saving = True
    panel.status = Mock()
    panel.grab_release = Mock()
    panel.grab_set = Mock()
    return panel


def test_settings_preflight_precedes_protected_persistence_and_apply():
    events = []
    panel = save_panel(lambda values: events.append("preflight"),
                       lambda values: events.append("apply"))
    with patch.object(settings_panel, "save_settings", side_effect=lambda values: events.append("persist")):
        panel._save_worker({"HERMES_URL": "https://fixture.invalid"})
    assert events == ["preflight", "persist", "apply"]
    panel.grab_release.assert_called_once()


def test_hermes_refusal_leaves_saved_settings_untouched():
    def refuse(_values):
        raise ValueError("A prepared Hermes request is still unresolved.")
    panel = save_panel(refuse)
    with patch.object(settings_panel, "save_settings") as persist:
        panel._save_worker({"HERMES_URL": "https://new.invalid"})
    persist.assert_not_called()
    panel.status.configure.assert_called_once_with(text="A prepared Hermes request is still unresolved.")
    panel.grab_release.assert_called_once()


def test_protected_storage_failure_rolls_back_service_config_before_ui_apply():
    rollback = Mock()
    after_save = Mock()
    panel = save_panel(lambda values: rollback, after_save)
    with patch.object(settings_panel, "save_settings", side_effect=OSError("fixture write failure")):
        panel._save_worker({"HERMES_URL": "https://new.invalid"})
    rollback.assert_called_once()
    after_save.assert_not_called()


def test_local_only_never_constructs_media_sync_client():
    app = ComposeApp.__new__(ComposeApp)
    app._sync_stop = __import__("threading").Event()
    app.local_only = True
    app.media_service = Mock(sync=object())
    app.settings_panel = Mock()
    with patch("compose_gui.SyncClient") as client:
        app._configure_media_sync()
    client.assert_not_called()
    assert app.media_service.sync is None
    app.settings_panel.set_status.assert_called_once()


def test_hermes_service_refuses_settings_change_while_run_is_unresolved():
    app = ComposeApp.__new__(ComposeApp)
    app._busy = False
    app.is_recording = False
    app.config = {"HERMES_ENABLED": "1", "HERMES_URL": "https://old.invalid",
                  "HERMES_TOKEN": "old-secret", "LOCAL_ONLY": "0"}
    app.hermes_panel = Mock(_busy=False)
    app.hermes_service = Mock()
    app.hermes_service.update_config.side_effect = ValueError(
        "Cannot change the Hermes endpoint while a request is unresolved.")
    with pytest.raises(ValueError, match="unresolved"):
        ComposeApp._validate_settings_before_save(app, {
            "HERMES_ENABLED": "1", "HERMES_URL": "https://new.invalid",
            "HERMES_TOKEN": "new-secret", "LOCAL_ONLY": "0"})
    app.hermes_service.update_config.assert_called_once_with({
        "HERMES_ENABLED": True, "HERMES_URL": "https://new.invalid",
        "HERMES_TOKEN": "new-secret", "LOCAL_ONLY": False})
    assert app.config["HERMES_URL"] == "https://old.invalid"


def test_hermes_token_is_loaded_only_from_protected_settings(tmp_path):
    (tmp_path / "compose.env").write_text(
        "HERMES_TOKEN=plaintext-env-file-secret\nHERMES_URL=https://env-file.invalid\n",
        encoding="utf-8")
    fake_module = tmp_path / "compose_gui.py"
    with patch.object(compose_gui, "__file__", str(fake_module)), \
         patch.object(compose_gui, "load_settings", return_value={}), \
         patch.dict("os.environ", {"HERMES_TOKEN": "plaintext-process-secret",
                                    "HERMES_URL": "https://process.invalid"}, clear=False):
        config = compose_gui.load_env_config()
    assert "HERMES_TOKEN" not in config
    assert config["HERMES_URL"] == "https://process.invalid"


def test_inflight_operation_restores_its_selected_request():
    panel = HermesPanel.__new__(HermesPanel)
    panel._restoring_selection = False
    panel._busy = True
    panel._operation_request = "request-a"
    panel._active_request = "request-a"
    panel.runs = Mock()
    panel.runs.selection.return_value = ("request-b",)
    panel.runs.exists.return_value = True
    HermesPanel._selected(panel)
    panel.runs.selection_set.assert_called_once_with("request-a")
    assert panel._active_request == "request-a"


def test_stale_worker_result_is_discarded_when_request_changes():
    panel = HermesPanel.__new__(HermesPanel)
    panel._closed = False
    panel._operation_generation = 3
    panel._busy = True
    panel._operation_request = "request-a"
    panel._active_request = "request-b"
    panel._sync_controls = Mock()
    callback = Mock()
    HermesPanel._finished(panel, callback, {"text": "old result"}, None, "request-a", 3)
    callback.assert_not_called()
    panel._sync_controls.assert_called_once()


def test_newly_prepared_request_clears_previous_run_and_result():
    panel = HermesPanel.__new__(HermesPanel)
    panel._active_request = "old-request"
    panel._active_run_id = "old-run"
    panel._result_text = "Old result"
    panel._result_request_id = "old-request"
    panel._prepared_task = "New task"
    panel._prepared_context = ""
    panel.status_line = Mock()
    panel.set_notice = Mock()
    panel._append_details = Mock()
    panel.refresh_runs = Mock()
    HermesPanel._prepared(panel, {"request_id": "new-request", "status": "prepared", "message": "Saved locally."})
    assert panel._active_request == "new-request"
    assert panel._active_run_id is None
    assert panel._result_text == ""
    assert panel._result_request_id is None


def test_busy_submit_keeps_same_request_retry_handle():
    panel = HermesPanel.__new__(HermesPanel)
    panel.service = object()
    panel.local_only = lambda: False
    panel.settings_saving = lambda: False
    panel._closed = False
    panel._prepared_request = "request-a"
    panel._blocked = lambda: False
    panel._start = Mock(return_value=False)
    HermesPanel.submit(panel)
    assert panel._prepared_request == "request-a"


def test_paste_ready_cannot_queue_result_from_another_run():
    panel = HermesPanel.__new__(HermesPanel)
    panel._result_text = "Old run result"
    panel._result_request_id = "request-a"
    panel._active_request = "request-b"
    panel._selected_status = "completed"
    panel.queue_text = Mock()
    panel.set_notice = Mock()
    HermesPanel.queue_result(panel)
    panel.queue_text.assert_not_called()
    panel.set_notice.assert_called_once()
    panel._active_request = "request-a"
    panel.set_notice.reset_mock()
    HermesPanel.queue_result(panel)
    panel.queue_text.assert_called_once_with("Old run result")
