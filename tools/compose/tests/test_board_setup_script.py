"""The portable Board setup creates a usable venv at its final path."""
import base64
import csv
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[3]
POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh")
pytestmark = pytest.mark.skipif(os.name != "nt" or not POWERSHELL, reason="Windows PowerShell is required")


def _stub_dependency_wheel(folder: Path) -> Path:
    """Make a tiny offline wheel containing import-only Board dependency stubs."""
    packages = ("PySide6", "PIL", "reportlab", "requests", "sounddevice", "numpy", "scipy", "faster_whisper")
    dist_info = "board_setup_test_deps-1.0.dist-info"
    files = {f"{name}/__init__.py": "__version__ = '1.0'\n" for name in packages}
    files[f"{dist_info}/METADATA"] = "Metadata-Version: 2.1\nName: board-setup-test-deps\nVersion: 1.0\n"
    files[f"{dist_info}/WHEEL"] = "Wheel-Version: 1.0\nGenerator: Board setup test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    rows = []
    for name, content in files.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(content.encode()).digest()).rstrip(b"=").decode()
        rows.append((name, "sha256=" + digest, str(len(content.encode()))))
    rows.append((f"{dist_info}/RECORD", "", ""))
    record = io.StringIO(newline="")
    csv.writer(record, lineterminator="\n").writerows(rows)
    files[f"{dist_info}/RECORD"] = record.getvalue()
    wheel = folder / "board_setup_test_deps-1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return wheel


def test_missing_environment_setup_installs_offline_and_keeps_final_venv_path(tmp_path):
    project = tmp_path / "school-checkout"
    compose = project / "tools" / "compose"
    compose.mkdir(parents=True)
    setup = compose / "setup_teaching_board_candidate.ps1"
    shutil.copyfile(ROOT / "tools/compose/setup_teaching_board_candidate.ps1", setup)
    wheels = tmp_path / "fixture wheels"
    wheels.mkdir()
    wheel = _stub_dependency_wheel(wheels)
    (compose / "requirements-board.txt").write_text(
        "board-setup-test-deps @ " + wheel.as_uri() + "\n", encoding="utf-8")
    base_python = subprocess.check_output(
        [sys.executable, "-c", "import sys; print(sys._base_executable)"], text=True).strip()
    writable_temp = tmp_path / "windows-temp"
    writable_temp.mkdir()
    process_environment = os.environ.copy()
    process_environment["TEMP"] = str(writable_temp)
    process_environment["TMP"] = str(writable_temp)

    result = subprocess.run(
        # The isolated test subprocess uses a process-only policy setting so
        # the temporary unsigned fixture can run; the shipped launcher never
        # changes the school's execution policy.
        [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(setup),
         "-PythonExecutable", base_python],
        capture_output=True, text=True, timeout=180, env=process_environment,
    )
    assert result.returncode == 0, f"interpreter={base_python}\n{result.stdout}\n{result.stderr}"
    environment = project / ".local" / "teaching-board-renderer-env"
    python = environment / "Scripts" / "python.exe"
    assert python.is_file()
    assert not (environment / ".setup-in-progress").exists()
    assert not (project / ".local" / ".teaching-board-renderer-env.setup-lock").exists()
    check = subprocess.run([str(python), "-c", "import PySide6, PIL, reportlab, requests, sounddevice, numpy, scipy, faster_whisper"],
                           capture_output=True, text=True, timeout=30)
    assert check.returncode == 0, check.stdout + "\n" + check.stderr
