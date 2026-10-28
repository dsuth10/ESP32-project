"""Microphone arbitration is tested with files and processes, never real audio."""
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audio_lease import MicrophoneLease


def test_without_unified_lease_configuration_keeps_standalone_capture_independent(monkeypatch):
    monkeypatch.delenv('ESP32_COMPANION_MICROPHONE_LEASE', raising=False)
    first, second = MicrophoneLease(), MicrophoneLease()
    assert first.acquire()
    assert second.acquire()
    first.release(); second.release()


def test_only_one_capture_can_own_the_shared_microphone_path(tmp_path):
    first = MicrophoneLease(tmp_path / 'microphone.lock')
    second = MicrophoneLease(tmp_path / 'microphone.lock')
    try:
        assert first.acquire()
        assert not second.acquire()
        first.release()
        assert second.acquire()
    finally:
        first.release(); second.release()


def test_board_transcription_worker_can_release_a_ui_thread_capture(tmp_path):
    """Board stops capture from its transcription worker, not its Qt UI thread."""
    first = MicrophoneLease(tmp_path / 'microphone.lock')
    second = MicrophoneLease(tmp_path / 'microphone.lock')
    assert first.acquire()
    errors = []
    def stop_from_worker():
        try:
            first.release()
        except Exception as error:
            errors.append(error)
    worker = threading.Thread(target=stop_from_worker)
    worker.start(); worker.join(timeout=5)
    try:
        assert not worker.is_alive()
        assert errors == []
        assert second.acquire()
    finally:
        first.release(); second.release()


def test_environment_path_arbitrates_the_two_applications(tmp_path, monkeypatch):
    monkeypatch.setenv('ESP32_COMPANION_MICROPHONE_LEASE', str(tmp_path / 'microphone.lock'))
    first, second = MicrophoneLease(), MicrophoneLease()
    try:
        assert first.acquire()
        assert not second.acquire()
    finally:
        first.release(); second.release()


def test_child_crash_releases_microphone_ownership(tmp_path):
    """A dead embedded companion must not permanently block Board recording."""
    path = tmp_path / 'microphone.lock'
    script = (
        'import sys,time; sys.path.insert(0,sys.argv[1]); '
        'from audio_lease import MicrophoneLease; '
        'lease=MicrophoneLease(sys.argv[2]); '
        'print("acquired" if lease.acquire() else "blocked",flush=True); '
        'time.sleep(60)'
    )
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    child = subprocess.Popen([sys.executable, '-u', '-c', script,
                              str(Path(__file__).resolve().parents[1]), str(path)],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             creationflags=flags)
    competing = MicrophoneLease(path)
    try:
        assert child.stdout.readline().strip() == 'acquired'
        assert not competing.acquire()
        child.terminate(); child.wait(timeout=10)
        # Windows may finish closing file handles just after its process wait
        # becomes signalled. Require prompt recovery, allowing that OS cleanup.
        deadline = time.monotonic() + 2
        while not competing.acquire() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert competing.acquire()
    finally:
        competing.release()
        if child.poll() is None:
            child.terminate(); child.wait(timeout=10)
        child.stdout.close(); child.stderr.close()


def test_release_is_safe_when_capture_never_started(tmp_path):
    lease = MicrophoneLease(tmp_path / 'microphone.lock')
    lease.release(); lease.release()
    assert lease.acquire()
    lease.release(); lease.release()


def test_audio_capture_never_opens_second_stream_while_other_workspace_records(tmp_path, monkeypatch):
    capture = pytest.importorskip('audio_capture')
    monkeypatch.setenv('ESP32_COMPANION_MICROPHONE_LEASE', str(tmp_path / 'microphone.lock'))
    monkeypatch.setattr(capture, 'find_default_wasapi_input_device', lambda: (None, 16000))
    opened = []
    class Stream:
        def __init__(self, **kwargs):
            opened.append(self)
        def start(self): pass
        def stop(self): pass
        def close(self): pass
    monkeypatch.setattr(capture.sd, 'InputStream', Stream)
    first, second = capture.AudioCapture(), capture.AudioCapture()
    try:
        assert first.start_recording()
        assert not second.start_recording()
        assert len(opened) == 1
        assert 'other workspace' in second.last_error
        first.stop_recording()
        assert second.start_recording()
        assert len(opened) == 2
    finally:
        first.stop_recording(); second.stop_recording()


def test_failed_audio_open_releases_ownership_for_the_other_workspace(tmp_path, monkeypatch):
    capture = pytest.importorskip('audio_capture')
    path = tmp_path / 'microphone.lock'
    monkeypatch.setenv('ESP32_COMPANION_MICROPHONE_LEASE', str(path))
    monkeypatch.setattr(capture, 'find_default_wasapi_input_device', lambda: (None, 16000))
    def cannot_open(**kwargs):
        raise OSError('Synthetic microphone unavailable')
    monkeypatch.setattr(capture.sd, 'InputStream', cannot_open)
    audio = capture.AudioCapture()
    assert not audio.start_recording()
    assert not audio.is_recording
    other = MicrophoneLease(path)
    try:
        assert other.acquire()
    finally:
        other.release(); audio.stop_recording()
