"""Verified, per-user source-preview install, update, rollback and removal.

No elevation, registry edits, dependencies, network calls or firmware operations.
Python and the documented setup step are still required to run the preview.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import time
import zipfile

MAX_PACKAGE_BYTES = 64 * 1024 * 1024
MAX_FILES = 1000
MANIFEST = "preview-manifest.json"


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _safe_name(name):
    reserved = {"CON", "PRN", "AUX", "NUL"} | {
        prefix + str(number) for prefix in ("COM", "LPT") for number in range(1, 10)}
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError("Package contains an unsafe path.")
    for part in name.split("/"):
        if (part in {"", ".", ".."} or part.endswith((" ", ".")) or
                any(character in '<>:"|?*' or ord(character) < 32 for character in part) or
                part.split(".")[0].upper() in reserved):
            raise ValueError("Package contains an unsafe Windows path.")


def _check_inside(path, boundary):
    path, boundary = Path(path).absolute(), Path(boundary).absolute()
    current = path
    while True:
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise ValueError("Linked installation paths are refused.")
        if current == boundary:
            break
        if current.parent == current:
            raise ValueError("Installation path escapes its directory.")
        current = current.parent
    if not path.resolve().is_relative_to(boundary.resolve()):
        raise ValueError("Installation path escapes its directory.")
    return path


def inspect_package(package):
    """Validate the entire archive before writing any executable source."""
    with zipfile.ZipFile(package) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if len(names) > MAX_FILES or len(names) != len(set(names)):
            raise ValueError("Package contains duplicate or too many entries.")
        if sum(item.file_size for item in infos) > MAX_PACKAGE_BYTES:
            raise ValueError("Package exceeds the source-preview size limit.")
        for item in infos:
            _safe_name(item.filename)
            path = PurePosixPath(item.filename)
            mode = item.external_attr >> 16
            if (path.is_absolute() or not path.parts or
                    any(part in {".", ".."} or ":" in part or
                        part.endswith((" ", ".")) for part in path.parts) or
                    "\\" in item.filename or item.is_dir() or stat.S_ISLNK(mode)):
                raise ValueError("Package contains an unsafe path.")
        manifest = json.loads(archive.read(MANIFEST))
        if manifest.get("format") != "source-preview" or not isinstance(manifest.get("files"), dict):
            raise ValueError("Unsupported package manifest.")
        files = manifest["files"]
        if set(names) != set(files) | {MANIFEST} or "start_companion_feature.bat" not in files:
            raise ValueError("Package contents differ from its manifest.")
        if len({name.casefold() for name in names}) != len(names):
            raise ValueError("Package paths collide on Windows.")
        blobs = {}
        for name, digest in files.items():
            data = archive.read(name)
            if _hash(data) != digest:
                raise ValueError("Package integrity verification failed.")
            blobs[name] = data
        identity = _hash(json.dumps(files, sort_keys=True).encode())
        return identity, files, blobs


def _atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".package-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _state(root):
    path = _check_inside(root / "installation.json", root)
    if not path.exists():
        return {"current": None, "previous": None}
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_release(root, identity):
    if not isinstance(identity, str) or len(identity) != 64 or any(c not in "0123456789abcdef" for c in identity):
        raise ValueError("Invalid installed release identity.")
    release = _check_inside(root / "releases" / identity, root)
    _check_inside(release / MANIFEST, root)
    manifest = json.loads((release / MANIFEST).read_text(encoding="utf-8"))
    files = manifest["files"]
    if _hash(json.dumps(files, sort_keys=True).encode()) != identity:
        raise ValueError("Installed manifest identity changed.")
    for name, digest in files.items():
        _safe_name(name)
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
            raise ValueError("Installed manifest contains an unsafe path.")
        target = _check_inside(release / name, root)
        if target.is_symlink() or not target.is_file() or _hash(target.read_bytes()) != digest:
            raise ValueError("Installed source was changed; preserve it before switching releases.")
    return release, files


def _activate(root, current, previous):
    _release, files = _verify_release(root, current)
    launcher = root / "Start Companion Feature.cmd"
    entry = 'start_companion.bat' if 'start_companion.bat' in files else 'start_companion_feature.bat'
    text = _launcher_text(current, entry)
    # Save the recoverable pointer before the launcher. A launch failure never
    # removes the old release; rerunning rollback recreates both files.
    _atomic(root / "installation.json", json.dumps(
        {"format": 1, "current": current, "previous": previous}, indent=2).encode())
    _atomic(launcher, text.encode("utf-8"))


def _launcher_text(identity, entry):
    return '@echo off\r\ncall "%~dp0releases\\' + identity + '\\' + entry + '"\r\n'


def _publish_release(staging, release):
    """Allow a short-lived Windows scanner handle to settle before publication.

    This retries only an unchanged atomic directory move. It never deletes a
    destination, bypasses permissions or activates partially published files.
    """
    for attempt in range(5):
        try:
            os.replace(staging, release)
            return
        except PermissionError as error:
            if (os.name != 'nt' or getattr(error, 'winerror', None) not in {5, 32, 33}
                    or attempt == 4 or release.exists()):
                raise
            time.sleep(.05 * (2 ** attempt))


def install(package, destination):
    root = Path(destination).absolute()
    _check_inside(root, root)
    identity, files, blobs = inspect_package(package)
    state = _state(root)
    if state["current"]:
        _verify_release(root, state["current"])
    elif root.exists() and any(root.iterdir()):
        raise ValueError("Choose an empty folder or an existing managed installation.")
    root.mkdir(parents=True, exist_ok=True)
    release = _check_inside(root / "releases" / identity, root)
    if release.exists():
        _verify_release(root, identity)
    else:
        staging = Path(tempfile.mkdtemp(prefix=".install-", dir=root))
        try:
            for name, data in blobs.items():
                path = staging / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            (staging / MANIFEST).write_text(json.dumps(
                {"format": "source-preview", "files": files}, indent=2), encoding="utf-8")
            release.parent.mkdir(exist_ok=True)
            _publish_release(staging, release)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    previous = state["current"] if state["current"] != identity else state["previous"]
    _activate(root, identity, previous)
    return {"current": identity, "previous": previous, "source_verified": True}


def rollback(destination):
    root = Path(destination).absolute()
    _check_inside(root, root)
    state = _state(root)
    if not state["previous"]:
        raise ValueError("No previous installed release is available.")
    _activate(root, state["previous"], state["current"])
    return {"current": state["previous"], "source_verified": True}


def uninstall(destination):
    """Remove unchanged managed sources; retain modified, extra files and data."""
    root = Path(destination).absolute()
    _check_inside(root, root)
    state = _state(root)
    if not state["current"]:
        raise ValueError("No managed installation was found.")
    # Verify identities and paths before deleting any managed file.
    releases = []
    for identity in {state["current"], state["previous"]} - {None}:
        try:
            releases.append(_verify_release(root, identity))
        except ValueError:
            # A modified managed release requires deliberate preservation.
            raise ValueError("An installed release was changed; uninstall stopped before removing files.") from None
    for release, files in releases:
        for name in files:
            (release / name).unlink()
        (release / MANIFEST).unlink()
        for folder in sorted((p for p in release.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            if not any(folder.iterdir()):
                folder.rmdir()
        if not any(release.iterdir()):
            release.rmdir()
    launcher = root / "Start Companion Feature.cmd"
    if launcher.exists():
        expected = {_launcher_text(state['current'], entry).encode()
                    for entry in ('start_companion.bat', 'start_companion_feature.bat')}
        if launcher.read_bytes() in expected:
            launcher.unlink()
    (root / "installation.json").unlink()
    return {"removed_managed_sources": True, "data_preserved": True,
            "remaining_files": sum(p.is_file() for p in root.rglob("*"))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "rollback", "uninstall"])
    parser.add_argument("--package", type=Path)
    parser.add_argument("--destination", type=Path, default=Path(
        os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ESP32CompanionFeature")
    args = parser.parse_args()
    if args.action == "install" and not args.package:
        parser.error("install requires --package")
    functions = {"install": lambda: install(args.package, args.destination),
                 "rollback": lambda: rollback(args.destination),
                 "uninstall": lambda: uninstall(args.destination)}
    print(json.dumps(functions[args.action]()))


if __name__ == "__main__":
    main()
