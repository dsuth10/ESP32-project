"""Verified, no-overwrite backup and restore for the media service data directory.

The operator must stop the service before backup so SQLite metadata and immutable
blob files represent the same point in time. Restore always targets a new path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

DB_NAME = "media-server.sqlite3"
BLOB_DIR = "blobs"
MANIFEST = "manifest.json"


def _digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def _secure(path: Path, directory=False):
    try:
        path.chmod(0o700 if directory else 0o600)
    except OSError:
        pass


def _assert_no_symlinks(root: Path):
    components = (root, *root.parents)
    for component in components:
        if component.is_symlink() or (hasattr(component, "is_junction") and component.is_junction()):
            raise ValueError("Data path contains a symbolic link or junction; refusing backup or verification.")
    if root.is_symlink():
        raise ValueError("Data set contains a symbolic link; refusing backup or verification.")
    for current, directories, files in os.walk(root, followlinks=False):
        base = Path(current)
        for name in directories + files:
            if (base / name).is_symlink():
                raise ValueError("Data set contains a symbolic link; refusing backup or verification.")


def _blob_hashes(root: Path):
    hashes = {}
    for path in sorted((root / BLOB_DIR).rglob("*")):
        if path.is_symlink():
            raise ValueError("Blob store contains a symbolic link; refusing backup.")
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            digest = _digest(path)
            if len(path.name) != 64 or digest != path.name:
                raise ValueError("Blob name and content hash do not match; refusing backup.")
            hashes[relative] = digest
    return hashes


def backup(data_dir: Path, destination: Path, service_stopped: bool):
    if not service_stopped:
        raise ValueError("Stop the media service and pass --service-stopped before taking a consistent backup.")
    data_dir = data_dir.absolute()
    _assert_no_symlinks(data_dir)
    data_dir = data_dir.resolve(strict=True)
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Backup destination already exists; refusing to overwrite it.")
    source_db = data_dir / DB_NAME
    source_blobs = data_dir / BLOB_DIR
    if not source_db.is_file() or not source_blobs.is_dir():
        raise ValueError("Data directory does not contain the expected SQLite database and blobs/ directory.")
    _assert_no_symlinks(data_dir)
    stage = destination.with_name(destination.name + ".staging")
    if stage.exists() or stage.is_symlink():
        raise FileExistsError("Backup staging path already exists; refusing to overwrite it.")
    stage.mkdir(parents=True)
    _secure(stage, True)
    try:
        source = sqlite3.connect(f"file:{source_db.as_posix()}?mode=ro", uri=True)
        target = sqlite3.connect(stage / DB_NAME)
        try:
            source.backup(target)
            check = target.execute("PRAGMA integrity_check").fetchone()[0]
            if check != "ok":
                raise ValueError("SQLite integrity check failed; backup was not published.")
        finally:
            target.close()
            source.close()
        shutil.copytree(source_blobs, stage / BLOB_DIR, copy_function=shutil.copy2)
        _secure(stage / DB_NAME)
        for path in (stage / BLOB_DIR).rglob("*"):
            if path.is_file(): _secure(path)
            elif path.is_dir(): _secure(path, True)
        manifest = {
            "format": 1,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "database_sha256": _digest(stage / DB_NAME),
            "blob_sha256": _blob_hashes(stage),
        }
        manifest_path = stage / MANIFEST
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _secure(manifest_path)
        verify(stage)
        os.replace(stage, destination)
        return destination
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def verify(backup_dir: Path):
    if backup_dir.is_symlink() or not backup_dir.is_dir():
        raise ValueError("Backup path must be a real directory.")
    database = backup_dir / DB_NAME
    if (backup_dir / MANIFEST).is_symlink() or database.is_symlink() or (backup_dir / BLOB_DIR).is_symlink():
        raise ValueError("Backup contains a symbolic link; refusing verification.")
    _assert_no_symlinks(backup_dir)
    manifest = json.loads((backup_dir / MANIFEST).read_text(encoding="utf-8"))
    if manifest.get("format") != 1 or not isinstance(manifest.get("blob_sha256"), dict):
        raise ValueError("Backup manifest format is invalid.")
    if not database.is_file() or _digest(database) != manifest.get("database_sha256"):
        raise ValueError("Backup SQLite digest does not match its manifest.")
    connection = sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True)
    try:
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Backup SQLite integrity check failed.")
    finally:
        connection.close()
    actual = _blob_hashes(backup_dir)
    if actual != manifest["blob_sha256"]:
        raise ValueError("Backup blob inventory or digest does not match its manifest.")
    return {"verified": True, "blob_count": len(actual), "database_sha256": manifest["database_sha256"]}


def restore(backup_dir: Path, destination: Path):
    verify(backup_dir)
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Restore destination already exists; restore never overwrites data.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=destination.name + ".restore-", dir=destination.parent))
    _secure(stage, True)
    try:
        shutil.copy2(backup_dir / DB_NAME, stage / DB_NAME)
        shutil.copytree(backup_dir / BLOB_DIR, stage / BLOB_DIR, copy_function=shutil.copy2)
        _secure(stage / DB_NAME)
        for path in (stage / BLOB_DIR).rglob("*"):
            if path.is_file(): _secure(path)
            elif path.is_dir(): _secure(path, True)
        expected = json.loads((backup_dir / MANIFEST).read_text(encoding="utf-8"))
        (stage / MANIFEST).write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _secure(stage / MANIFEST)
        verify(stage)
        os.replace(stage, destination)
        return destination
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main():
    parser = argparse.ArgumentParser(description="Create or verify a private media data backup; restore only to a new directory.")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("backup")
    command.add_argument("--data-dir", type=Path, required=True)
    command.add_argument("--destination", type=Path, required=True)
    command.add_argument("--service-stopped", action="store_true", help="Confirm service is stopped")
    command = sub.add_parser("verify")
    command.add_argument("--backup", type=Path, required=True)
    command = sub.add_parser("restore")
    command.add_argument("--backup", type=Path, required=True)
    command.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "backup": result = {"backup": str(backup(args.data_dir, args.destination, args.service_stopped))}
        elif args.command == "verify": result = verify(args.backup)
        else: result = {"restored_to": str(restore(args.backup, args.destination))}
        print(json.dumps(result))
        return 0
    except Exception as exc:
        print(json.dumps({"error_type": type(exc).__name__, "operation": args.command}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
