import hashlib
import importlib.util
import os
import json
import sqlite3
import sys
import threading
import tempfile
import unittest
import urllib.request
import uuid
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "media_backup.py"
PROJECT_ROOT = SCRIPT.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from server.media_library_server import create_server
spec = importlib.util.spec_from_file_location("media_backup", SCRIPT)
media_backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(media_backup)


def make_data(root: Path):
    root.mkdir()
    db = sqlite3.connect(root / media_backup.DB_NAME)
    db.execute("CREATE TABLE sample (value TEXT)")
    db.execute("INSERT INTO sample VALUES ('metadata remains private')")
    db.commit()
    db.close()
    blob = b"fixture-image-bytes"
    digest = hashlib.sha256(blob).hexdigest()
    path = root / "blobs" / digest[:2] / digest
    path.parent.mkdir(parents=True)
    path.write_bytes(blob)
    return digest


class MediaBackupTests(unittest.TestCase):
    def test_project_root_is_the_repository_not_the_filesystem_root(self):
        self.assertTrue((PROJECT_ROOT / "server" / "deployment" / "media_backup.py").is_file())
        self.assertNotEqual(PROJECT_ROOT.resolve(), Path("/").resolve())
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            self.assertTrue(Path(temp).resolve().is_relative_to(PROJECT_ROOT.resolve()))

    def test_requires_quiesced_service_and_never_overwrites_backup_or_restore(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            root = Path(temp)
            data = root / "data"
            make_data(data)
            backup = root / "backup"
            with self.assertRaisesRegex(ValueError, "Stop the media service"):
                media_backup.backup(data, backup, False)
            media_backup.backup(data, backup, True)
            self.assertTrue(media_backup.verify(backup)["verified"])
            restored = root / "restored"
            media_backup.restore(backup, restored)
            self.assertEqual(media_backup.verify(restored)["blob_count"], 1)
            with self.assertRaises(FileExistsError):
                media_backup.restore(backup, restored)
            with self.assertRaises(FileExistsError):
                media_backup.backup(data, backup, True)

    def test_verification_detects_blob_mutation(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            root = Path(temp)
            data = root / "data"
            digest = make_data(data)
            backup = root / "backup"
            media_backup.backup(data, backup, True)
            (backup / "blobs" / digest[:2] / digest).write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "name and content hash"):
                media_backup.verify(backup)

    @unittest.skipIf(os.name == "nt", "Creating symlinks may require developer mode or elevation on Windows")
    def test_backup_refuses_database_symlink(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            root = Path(temp)
            data = root / "data"
            make_data(data)
            db = data / media_backup.DB_NAME
            original = root / "original.sqlite3"
            db.rename(original)
            db.symlink_to(original)
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                media_backup.backup(data, root / "backup", True)

    @unittest.skipIf(os.name == "nt", "Creating symlinks may require developer mode or elevation on Windows")
    def test_restore_refuses_dangling_destination_symlink(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            root = Path(temp)
            data = root / "data"
            make_data(data)
            backup = root / "backup"
            media_backup.backup(data, backup, True)
            destination = root / "dangling-destination"
            destination.symlink_to(root / "missing-target", target_is_directory=True)
            with self.assertRaises(FileExistsError):
                media_backup.restore(backup, destination)
            self.assertTrue(destination.is_symlink())

    @unittest.skipUnless(importlib.util.find_spec("PIL"), "Pillow unavailable")
    def test_stopped_service_backup_restore_start_and_retrieve(self):
        from PIL import Image
        import io

        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            root = Path(temp)
            source_data = root / "source-data"
            token = "restore-fixture-token"
            original = create_server(host="127.0.0.1", port=0, token=token, data_dir=source_data)
            original_thread = threading.Thread(target=original.serve_forever, daemon=True)
            original_thread.start()
            try:
                output = io.BytesIO()
                Image.new("RGB", (2, 1), (25, 90, 180)).save(output, format="PNG")
                image = output.getvalue()
                digest = hashlib.sha256(image).hexdigest()
                base = f"http://127.0.0.1:{original.server_address[1]}"
                req = urllib.request.Request(base + f"/v1/blobs/{digest}", data=image, method="PUT", headers={"Authorization": f"Bearer {token}", "Content-Type": "image/png"})
                with urllib.request.urlopen(req, timeout=5) as response:
                    self.assertEqual(response.status, 201)
                asset_id, version_id = str(uuid.uuid4()), str(uuid.uuid4())
                version = {
                    "asset_id": asset_id, "version_id": version_id, "title": "Restored lesson image",
                    "tags": ["restore"], "sha256": digest, "mime": "image/png", "width": 2,
                    "height": 1, "byte_size": len(image), "parent_version_id": None,
                    "source": {"creator": "fixture"}, "created_at": "2026-10-21T00:00:00+00:00",
                    "origin": "import",
                }
                event = {"event_id": str(uuid.uuid4()), "kind": "version", "payload": version}
                request = urllib.request.Request(base + "/v1/events", data=json.dumps(event).encode(), method="POST", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
                with urllib.request.urlopen(request, timeout=5) as response:
                    self.assertEqual(response.status, 200)
            finally:
                original.shutdown()
                original.server_close()
                original_thread.join(timeout=3)
            self.assertFalse(original_thread.is_alive(), "Writer must stop before snapshot and blob copy")

            backup = root / "verified-backup"
            media_backup.backup(source_data, backup, service_stopped=True)
            restored_data = root / "restored-data"
            media_backup.restore(backup, restored_data)
            restored = create_server(host="127.0.0.1", port=0, token=token, data_dir=restored_data)
            restored_thread = threading.Thread(target=restored.serve_forever, daemon=True)
            restored_thread.start()
            try:
                restored_base = f"http://127.0.0.1:{restored.server_address[1]}"
                request = urllib.request.Request(restored_base + "/v1/events?after=0", headers={"Authorization": f"Bearer {token}"})
                with urllib.request.urlopen(request, timeout=5) as response:
                    events = json.loads(response.read())
                self.assertEqual(events["events"][0]["payload"]["title"], "Restored lesson image")
                request = urllib.request.Request(restored_base + f"/v1/blobs/{digest}", headers={"Authorization": f"Bearer {token}"})
                with urllib.request.urlopen(request, timeout=5) as response:
                    self.assertEqual(response.read(), image)
            finally:
                restored.shutdown()
                restored.server_close()
                restored_thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
