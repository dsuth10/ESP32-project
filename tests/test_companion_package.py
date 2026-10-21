import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("companion_package", ROOT/"tools/companion_package.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


def archive(path, text="version-one", extra=None):
    files = {"start_companion_feature.bat": text.encode(), "tools/compose/example.py": b"pass"}
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    with zipfile.ZipFile(path, "w") as output:
        for name, data in files.items():
            output.writestr(name, data)
        output.writestr("preview-manifest.json", json.dumps({"format": "source-preview", "files": manifest}))
        if extra:
            output.writestr(*extra)
    return path


def test_install_update_rollback_uninstall_preserves_data_and_extra_files(tmp_path):
    destination = tmp_path/"installed"
    first = package.install(archive(tmp_path/"first.zip"), destination)
    old = destination/"releases"/first["current"]
    # Local dependencies and user-created files must survive removal.
    (old/"my-notes.txt").write_text("preserve")
    data = tmp_path/"independent-data"
    data.mkdir()
    (data/"history.txt").write_text("preserve history")
    second = package.install(archive(tmp_path/"second.zip", "version-two"), destination)
    assert second["previous"] == first["current"]
    assert package.rollback(destination)["current"] == first["current"]
    result = package.uninstall(destination)
    assert result["data_preserved"]
    assert (old/"my-notes.txt").read_text() == "preserve"
    assert (data/"history.txt").read_text() == "preserve history"
    assert not (destination/"Start Companion Feature.cmd").exists()


def test_changed_installed_sources_block_update_and_uninstall(tmp_path):
    destination = tmp_path/"installed"
    first = package.install(archive(tmp_path/"first.zip"), destination)
    source = destination/"releases"/first["current"]/"start_companion_feature.bat"
    source.write_text("user edits")
    with pytest.raises(ValueError, match="changed"):
        package.install(archive(tmp_path/"second.zip", "version-two"), destination)
    with pytest.raises(ValueError, match="changed"):
        package.uninstall(destination)
    assert source.read_text() == "user edits"


@pytest.mark.parametrize("name", ["../escape.py", "/absolute.py", "a\\escape.py", "C:/escape.py",
                                  "bad./escape.py", "tools/COM1", "tools/compose/EXAMPLE.py"])
def test_unsafe_or_unexpected_package_writes_nothing(tmp_path, name):
    destination = tmp_path/"installed"
    bad = archive(tmp_path/"bad.zip", extra=(name, b"unexpected"))
    with pytest.raises(ValueError):
        package.install(bad, destination)
    assert not destination.exists()


def test_hash_mismatch_rejected_before_install(tmp_path):
    bad = tmp_path/"bad.zip"
    with zipfile.ZipFile(bad, "w") as output:
        output.writestr("start_companion_feature.bat", b"tampered")
        output.writestr("preview-manifest.json", json.dumps({
            "format": "source-preview", "files": {"start_companion_feature.bat": "0"*64}}))
    with pytest.raises(ValueError, match="integrity"):
        package.install(bad, tmp_path/"installed")
    assert not (tmp_path/"installed").exists()


def test_unmanaged_destination_preserved(tmp_path):
    destination = tmp_path/"unmanaged"
    destination.mkdir()
    (destination/"important.txt").write_text("preserve")
    with pytest.raises(ValueError, match="empty folder"):
        package.install(archive(tmp_path/"first.zip"), destination)
    assert (destination/"important.txt").read_text() == "preserve"


def test_symlink_in_installed_release_refused(tmp_path):
    destination = tmp_path/"installed"
    first = package.install(archive(tmp_path/"first.zip"), destination)
    path = destination/"releases"/first["current"]/"tools/compose/example.py"
    outside = tmp_path/"outside.py"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    try:
        path.symlink_to(outside)
    except OSError:
        pytest.skip("Symlink creation unavailable on this Windows installation")
    with pytest.raises(ValueError):
        package.uninstall(destination)
    assert outside.exists()

@pytest.mark.parametrize("name", ["tools/COM1.py", "tools/NUL", "tools/a/./b.py",
                                  "tools//b.py", "tools/trailing./b.py"])
def test_unsafe_names_are_refused_even_when_manifest_lists_them(tmp_path, name):
    output = tmp_path/"listed-unsafe.zip"
    files = {"start_companion_feature.bat": b"start", name: b"unsafe"}
    with zipfile.ZipFile(output, "w") as archive:
        for path, data in files.items():
            archive.writestr(path, data)
        archive.writestr("preview-manifest.json", json.dumps({"format": "source-preview", "files": {
            path: hashlib.sha256(data).hexdigest() for path, data in files.items()}}))
    with pytest.raises(ValueError, match="unsafe"):
        package.install(output, tmp_path/"installed")
    assert not (tmp_path/"installed").exists()


def directory_link(link, target):
    import os
    import subprocess
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                                capture_output=True)
        if result.returncode:
            pytest.skip("Directory junction creation unavailable")
    else:
        link.symlink_to(target, target_is_directory=True)


def test_ancestor_link_cannot_redirect_uninstall_to_external_file(tmp_path):
    import shutil
    destination = tmp_path/"installed"
    first = package.install(archive(tmp_path/"first.zip"), destination)
    release = destination/"releases"/first["current"]
    outside = tmp_path/"external-tools"
    shutil.copytree(release/"tools", outside)
    (release/"tools").rename(release/"original-tools")
    directory_link(release/"tools", outside)
    with pytest.raises(ValueError, match="changed"):
        package.uninstall(destination)
    assert (outside/"compose/example.py").read_bytes() == b"pass"


def test_releases_junction_cannot_redirect_update(tmp_path):
    import shutil
    destination = tmp_path/"installed"
    package.install(archive(tmp_path/"first.zip"), destination)
    outside = tmp_path/"external-releases"
    shutil.copytree(destination/"releases", outside)
    (destination/"releases").rename(destination/"original-releases")
    directory_link(destination/"releases", outside)
    before = sorted(p.relative_to(outside).as_posix() for p in outside.rglob("*"))
    with pytest.raises(ValueError, match="Linked"):
        package.install(archive(tmp_path/"next.zip", "version-two"), destination)
    assert sorted(p.relative_to(outside).as_posix() for p in outside.rglob("*")) == before
