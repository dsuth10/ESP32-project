"""Compose test harness. Linux-only Windows/audio stubs; native skips stay skipped."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from linux_windows_stubs import INSTALLED, install_windows_stubs

install_windows_stubs()


def pytest_report_header(config):
    if not INSTALLED:
        return 'Windows/audio stubs: none (native modules present)'
    return 'Windows/audio stubs: ' + ', '.join(INSTALLED)
