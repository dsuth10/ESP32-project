"""The shared desktop ships complete sources and keeps legacy rollback usable."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile
import os
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_companion_preview import build
from companion_package import inspect_package, install, rollback, uninstall
import companion_package


def test_unified_source_preview_contains_both_workspaces_and_no_local_data(tmp_path):
    package = tmp_path / 'shared-desktop.zip'
    manifest = build(package)
    required = {
        'start_companion.bat', 'start_classroom_companion.bat', 'start_companion_feature.bat',
        'tools/compose/unified_desktop.py', 'tools/compose/companion_host.py',
        'tools/compose/companion_embedded.py', 'tools/compose/audio_lease.py',
        'tools/compose/desktop_instance.py', 'tools/compose/compose_gui.py',
        'tools/compose/board_candidate.py', 'tools/compose/run_unified_desktop.ps1',
        'tools/compose/setup_unified_desktop.ps1', 'tools/compose/requirements.txt',
        'tools/compose/requirements-board.txt', 'docs/2026-10-28-unified-desktop-plan.md',
        'docs/2026-10-28-unified-desktop-guide.md',
        'docs/2026-10-28-unified-desktop-settings-repair.md',
        'tools/compose/board_resource_policy.py', 'tools/compose/settings_panel.py',
    }
    assert required <= set(manifest)
    assert all(not name.startswith('.local/') and not name.endswith(('.dpapi', '.sqlite3', '.log', '.env'))
               for name in manifest)
    _identity, verified, _blobs = inspect_package(package)
    assert verified == manifest
    result = install(package, tmp_path / 'installed')
    launcher = tmp_path / 'installed/Start Companion Feature.cmd'
    assert b'\\start_companion.bat' in launcher.read_bytes()
    assert result['source_verified']
    assert uninstall(tmp_path / 'installed')['data_preserved']
    assert not launcher.exists()


def _archive(path, files):
    files = {name: content.encode() for name, content in files.items()}
    manifest = {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}
    with zipfile.ZipFile(path, 'w') as archive:
        for name, content in files.items():
            archive.writestr(name, content)
        archive.writestr('preview-manifest.json', json.dumps({'format': 'source-preview', 'files': manifest}))
    return path


def test_rollback_restores_the_correct_shared_or_legacy_entry(tmp_path):
    legacy = _archive(tmp_path / 'legacy.zip', {'start_companion_feature.bat': 'legacy voice entry'})
    shared = _archive(tmp_path / 'shared.zip', {'start_companion_feature.bat': 'recovery voice entry',
                                              'start_companion.bat': 'shared teacher entry'})
    root = tmp_path / 'installed'
    install(legacy, root)
    launcher = root / 'Start Companion Feature.cmd'
    assert b'\\start_companion_feature.bat' in launcher.read_bytes()
    install(shared, root)
    assert b'\\start_companion.bat' in launcher.read_bytes()
    rollback(root)
    assert b'\\start_companion_feature.bat' in launcher.read_bytes()
    rollback(root)
    assert b'\\start_companion.bat' in launcher.read_bytes()
    uninstall(root)
    assert not launcher.exists()


@pytest.mark.skipif(os.name != 'nt', reason='Windows directory handle behaviour')
def test_transient_windows_publish_denial_retries_without_partial_activation(tmp_path, monkeypatch):
    source = _archive(tmp_path / 'shared.zip', {'start_companion_feature.bat': 'voice',
                                             'start_companion.bat': 'shared'})
    real_replace = companion_package.os.replace
    attempts = []
    def transient(staging, destination):
        if Path(staging).name.startswith('.install-'):
            attempts.append(destination)
            if len(attempts) < 3:
                error = PermissionError('Synthetic temporary Windows sharing denial')
                error.winerror = 5
                raise error
        return real_replace(staging, destination)
    monkeypatch.setattr(companion_package.os, 'replace', transient)
    monkeypatch.setattr(companion_package.time, 'sleep', lambda _delay: None)
    root = tmp_path / 'installed'
    result = install(source, root)
    assert len(attempts) == 3
    assert result['source_verified']
    assert b'\\start_companion.bat' in (root / 'Start Companion Feature.cmd').read_bytes()


@pytest.mark.skipif(os.name != 'nt', reason='Windows directory handle behaviour')
def test_persistent_publish_denial_preserves_previous_release_and_launcher(tmp_path, monkeypatch):
    root = tmp_path / 'installed'
    old = _archive(tmp_path / 'old.zip', {'start_companion_feature.bat': 'old'})
    new = _archive(tmp_path / 'new.zip', {'start_companion_feature.bat': 'new',
                                       'start_companion.bat': 'shared'})
    install(old, root)
    before = (root / 'installation.json').read_bytes(), (root / 'Start Companion Feature.cmd').read_bytes()
    real_replace = companion_package.os.replace
    attempts = []
    def denied(staging, destination):
        if Path(staging).name.startswith('.install-'):
            attempts.append(destination)
            error = PermissionError('Synthetic persistent Windows sharing denial')
            error.winerror = 32
            raise error
        return real_replace(staging, destination)
    monkeypatch.setattr(companion_package.os, 'replace', denied)
    monkeypatch.setattr(companion_package.time, 'sleep', lambda _delay: None)
    with pytest.raises(PermissionError):
        install(new, root)
    assert len(attempts) == 5
    assert before == ((root / 'installation.json').read_bytes(), (root / 'Start Companion Feature.cmd').read_bytes())
    assert not list(root.glob('.install-*'))
