"""Portable, standard-library smoke tests for the private media API.

Run from any working directory with:
    python server/tests/test_media_server_portable.py

The tests bind only to loopback on an ephemeral port and use temporary data.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from server.media_library_server import create_server  # noqa: E402


TOKEN = "portable-test-token-not-for-deployment"
PIL_AVAILABLE = importlib.util.find_spec("PIL") is not None


def png_sample() -> tuple[bytes, int, int]:
    """Return a tiny deterministic image generated with Pillow."""
    from PIL import Image

    import io

    output = io.BytesIO()
    Image.new("RGB", (3, 2), (35, 95, 170)).save(output, format="PNG")
    return output.getvalue(), 3, 2


class MediaServerPortableTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="media-server-test-")
        self.server = create_server(
            host="127.0.0.1",
            port=0,
            token=TOKEN,
            data_dir=Path(self.temporary.name) / "data",
            budget_limit_cents=100,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address[:2]
        self.base_url = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temporary.cleanup()

    def request(self, method: str, path: str, *, body: bytes | None = None,
                token: str | None = TOKEN, content_type: str = "application/json"):
        headers = {"Content-Type": content_type, "Connection": "close"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            self.base_url + path, data=body, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            try:
                return error.code, error.headers, error.read()
            finally:
                error.close()

    def json_request(self, method: str, path: str, value=None, *, token: str | None = TOKEN):
        body = None if value is None else json.dumps(value).encode("utf-8")
        status, headers, payload = self.request(method, path, body=body, token=token)
        parsed = json.loads(payload) if payload else None
        return status, headers, parsed

    def test_authentication_health_and_capabilities(self) -> None:
        status, _, body = self.request("GET", "/health", token=None)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"status": "ok"})

        status, _, _ = self.request("GET", "/v1/capabilities", token=None)
        self.assertEqual(status, 401)
        status, _, capabilities = self.json_request("GET", "/v1/capabilities")
        self.assertEqual(status, 200)
        self.assertEqual(capabilities["service"], "media-library")
        self.assertEqual(set(capabilities["event_kinds"]), {"version", "canonical"})

    def test_database_connection_context_closes_connection(self) -> None:
        with self.server.library._connect() as connection:
            connection.execute("SELECT 1")
            closed_connection = connection
        with self.assertRaises(sqlite3.ProgrammingError):
            closed_connection.execute("SELECT 1")

    @unittest.skipUnless(PIL_AVAILABLE, "Pillow is unavailable; skipping image transfer case")
    def test_blob_version_canonical_idempotency_and_revision_conflict(self) -> None:
        image, width, height = png_sample()
        digest = hashlib.sha256(image).hexdigest()
        status, _, response = self.request(
            "PUT", f"/v1/blobs/{digest}", body=b"not the image",
            content_type="image/png",
        )
        self.assertEqual(status, 400)
        self.assertIn(b"hash mismatch", response)

        status, _, _ = self.request(
            "PUT", f"/v1/blobs/{digest}", body=image,
            content_type="image/jpeg",
        )
        self.assertEqual(status, 415)
        status, _, stored = self.request(
            "PUT", f"/v1/blobs/{digest}", body=image,
            content_type="image/png",
        )
        self.assertEqual(status, 201)
        self.assertEqual(json.loads(stored)["sha256"], digest)
        status, headers, downloaded = self.request("GET", f"/v1/blobs/{digest}")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get_content_type(), "image/png")
        self.assertEqual(downloaded, image)

        asset_id, version_id = str(uuid.uuid4()), str(uuid.uuid4())
        version_event = {
            "event_id": str(uuid.uuid4()),
            "kind": "version",
            "payload": {
                "asset_id": asset_id,
                "version_id": version_id,
                "title": "Portable test image",
                "tags": ["test"],
                "sha256": digest,
                "mime": "image/png",
                "width": width,
                "height": height,
                "byte_size": len(image),
                "parent_version_id": None,
                "source": {"creator": "Portable test"},
                "created_at": "2026-10-21T00:00:00+00:00",
                "origin": "import",
            },
        }
        status, _, accepted = self.json_request("POST", "/v1/events", version_event)
        self.assertEqual(status, 200)
        self.assertFalse(accepted["duplicate"])
        status, _, duplicate = self.json_request("POST", "/v1/events", version_event)
        self.assertEqual(status, 200)
        self.assertTrue(duplicate["duplicate"])

        changed = json.loads(json.dumps(version_event))
        changed["payload"]["title"] = "Changed payload under existing event id"
        status, _, _ = self.json_request("POST", "/v1/events", changed)
        self.assertEqual(status, 409)

        canonical_payload = {
            "asset_id": asset_id,
            "version_id": version_id,
            "expected_revision": 0,
            "revision": 1,
            "canonical_title": "Portable canonical image",
        }
        canonical_event = {
            "event_id": str(uuid.uuid4()), "kind": "canonical", "payload": canonical_payload
        }
        status, _, canonical_result = self.json_request("POST", "/v1/events", canonical_event)
        self.assertEqual(status, 200)
        self.assertEqual(canonical_result["revision"], 1)
        status, _, duplicate_canonical = self.json_request("POST", "/v1/events", canonical_event)
        self.assertEqual(status, 200)
        self.assertTrue(duplicate_canonical["duplicate"])

        stale_event = {
            "event_id": str(uuid.uuid4()),
            "kind": "canonical",
            "payload": canonical_payload,
        }
        status, _, conflict = self.json_request("POST", "/v1/events", stale_event)
        self.assertEqual(status, 409)
        self.assertEqual(conflict["server_revision"], 1)
        self.assertEqual(conflict["server_canonical_version_id"], version_id)

    def test_budget_duplicate_and_atomic_exhaustion(self) -> None:
        operation_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        barrier = threading.Barrier(2)

        def reserve(operation_id: str):
            barrier.wait(timeout=5)
            return self.json_request(
                "POST", "/v1/budget/reservations",
                {"operation_id": operation_id, "amount_cents": 70},
            )

        results: list[tuple[int, object, object]] = []
        worker = threading.Thread(target=lambda: results.append(reserve(operation_ids[0])))
        worker.start()
        second = reserve(operation_ids[1])
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        results.append(second)
        self.assertEqual(sorted(status for status, _, _ in results), [200, 409])

        accepted_status, _, accepted = next(item for item in results if item[0] == 200)
        self.assertEqual(accepted_status, 200)
        operation_id = accepted["operation_id"]
        duplicate_status, _, duplicate = self.json_request(
            "POST", "/v1/budget/reservations",
            {"operation_id": operation_id, "amount_cents": 70},
        )
        self.assertEqual(duplicate_status, 200)
        self.assertTrue(duplicate["duplicate"])

        release_status, _, released = self.json_request(
            "POST", f"/v1/budget/reservations/{operation_id}/release", {}
        )
        self.assertEqual(release_status, 200)
        self.assertEqual(released["state"], "released")
        replacement_id = str(uuid.uuid4())
        reserve_status, _, _ = self.json_request(
            "POST", "/v1/budget/reservations",
            {"operation_id": replacement_id, "amount_cents": 70},
        )
        self.assertEqual(reserve_status, 200)
        commit_status, _, committed = self.json_request(
            "POST", f"/v1/budget/reservations/{replacement_id}/commit", {}
        )
        self.assertEqual(commit_status, 200)
        self.assertEqual(committed["state"], "committed")

        exhausted_status, _, _ = self.json_request(
            "POST", "/v1/budget/reservations",
            {"operation_id": str(uuid.uuid4()), "amount_cents": 40},
        )
        self.assertEqual(exhausted_status, 409)


if __name__ == "__main__":
    unittest.main(verbosity=2)
