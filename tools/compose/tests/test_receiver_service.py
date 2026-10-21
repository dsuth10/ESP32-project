"""The companion starts the voice receiver without duplicating one that is already up."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from receiver_service import VoiceReceiver


def _service(tmp_path: Path) -> VoiceReceiver:
    server = tmp_path / "server"
    server.mkdir()
    (server / "hermes_voice_receiver.py").write_text("# receiver\n", encoding="utf-8")
    return VoiceReceiver(tmp_path)


def test_start_leaves_an_existing_receiver_alone(tmp_path):
    service = _service(tmp_path)
    with patch.object(service, "is_listening", return_value=True), \
         patch("receiver_service.subprocess.Popen") as popen:
        message = service.start()
    popen.assert_not_called()
    assert service.process is None
    assert "already running" in message


def test_start_launches_the_receiver_script(tmp_path):
    service = _service(tmp_path)
    fake = Mock()
    fake.poll.return_value = None
    with patch.object(service, "is_listening", return_value=False), \
         patch.object(service, "python_executable", return_value=Path("python")), \
         patch("receiver_service.subprocess.Popen", return_value=fake) as popen:
        message = service.start()
    command = popen.call_args.args[0]
    assert command[-1].endswith("hermes_voice_receiver.py")
    assert popen.call_args.kwargs["cwd"].endswith("server")
    assert "Starting voice receiver" in message
    assert service.owns_process
    service.stop()


def test_stop_terminates_only_a_receiver_this_window_started(tmp_path):
    service = _service(tmp_path)
    fake = Mock()
    fake.poll.return_value = None
    with patch.object(service, "is_listening", return_value=False), \
         patch.object(service, "python_executable", return_value=Path("python")), \
         patch("receiver_service.subprocess.Popen", return_value=fake):
        service.start()
    service.stop()
    fake.terminate.assert_called_once()
    assert service.process is None


def test_stop_does_nothing_when_the_receiver_was_already_running(tmp_path):
    service = _service(tmp_path)
    with patch.object(service, "is_listening", return_value=True):
        service.start()
    service.stop()
    assert service.process is None
