"""Read-only Windows launcher checks; never start an app or install packages."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = ROOT / 'tools/compose/run_unified_desktop.ps1'
BOARD_PYTHON = ROOT / '.local/teaching-board-renderer-env/Scripts/python.exe'
POWERSHELL = shutil.which('powershell.exe')
pytestmark = pytest.mark.skipif(os.name != 'nt' or not POWERSHELL,
                                reason='Windows PowerShell launcher checks')


def run_check(*arguments):
    return subprocess.run([POWERSHELL, '-NoProfile', '-File', str(LAUNCHER),
                           '-CheckOnly', *map(str, arguments)],
                          cwd=ROOT, capture_output=True, text=True, timeout=120,
                          creationflags=subprocess.CREATE_NO_WINDOW)


def test_missing_explicit_board_python_reports_setup_without_creating_data(tmp_path):
    lesson, profile = tmp_path / 'lesson', tmp_path / 'voice'
    result = run_check('-PythonExecutable', tmp_path / 'missing-python.exe',
                       '-DataRoot', lesson, '-CompanionDataRoot', profile)
    assert result.returncode != 0
    assert 'setup_unified_desktop.ps1' in result.stderr
    assert 'Normal launch does not install packages or download models' in result.stderr
    assert not lesson.exists() and not profile.exists()


def test_missing_explicit_companion_python_has_clear_failure_without_installing(tmp_path):
    result = run_check('-PythonExecutable', sys.executable,
                       '-CompanionPythonExecutable', tmp_path / 'missing-python.exe')
    assert result.returncode != 0
    assert 'selected voice companion Python executable is missing' in result.stderr
    assert 'Traceback' not in result.stderr


def test_windows_powershell_can_skip_board_env_missing_voice_and_find_existing_runtime(tmp_path):
    if not BOARD_PYTHON.is_file():
        pytest.skip('Existing isolated Board interpreter is unavailable')
    probe = subprocess.run([str(BOARD_PYTHON), '-c', 'import win32gui'],
                           capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    if probe.returncode == 0:
        pytest.skip('The Board interpreter already has voice dependencies; fallback is unnecessary')
    lesson, profile = tmp_path / 'lesson', tmp_path / 'voice'
    result = run_check('-PythonExecutable', BOARD_PYTHON,
                       '-DataRoot', lesson, '-CompanionDataRoot', profile)
    if 'Voice dependencies are missing' in result.stderr:
        pytest.skip('No installed companion interpreter is available on this computer')
    assert result.returncode == 0, result.stderr
    assert 'Teaching Board dependencies ready' in result.stdout
    assert 'Voice companion dependencies ready' in result.stdout
    assert 'No application or listeners started' in result.stdout
    assert 'Traceback' not in result.stderr
    assert 'NativeCommandError' not in result.stderr
    assert not lesson.exists() and not profile.exists()
