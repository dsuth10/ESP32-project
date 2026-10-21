from __future__ import annotations

import hashlib
import io
import json
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "compose"))
sys.path.insert(0, str(ROOT / "server"))

from media_library_server import MAX_BLOB_BYTES, create_server  # noqa: E402
from media_store import MediaStore  # noqa: E402
from media_sync import SyncClient, SyncConflict  # noqa: E402


TOKEN = "test-private-media-token"


def png_bytes(colour: tuple[int, int, int] = (20, 90, 180)) -> bytes:
    image = Image.new("RGB", (8, 6), colour)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


@pytest.fixture
def api(tmp_path):
    server = create_server(host="127.0.0.1", port=0, token=TOKEN, data_dir=tmp_path / "server")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield base
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def auth_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers["Authorization"] = f"Bearer {TOKEN}"
    return session


def version_payload(asset_id: str, version_id: str, blob: bytes, title: str = "Water cycle") -> dict:
    return {
        "asset_id": asset_id,
        "version_id": version_id,
        "title": title,
        "tags": ["water", "diagram"],
        "sha256": hashlib.sha256(blob).hexdigest(),
        "mime": "image/png",
        "width": 8,
        "height": 6,
        "byte_size": len(blob),
        "parent_version_id": None,
        "source": {"creator": "Teacher"},
        "created_at": "2026-10-21T00:00:00+00:00",
        "origin": "import",
    }


def test_api_auth_blob_validation_and_idempotent_event(api, tmp_path):
    assert requests.get(api + "/health", timeout=2).json() == {"status": "ok"}
    assert requests.get(api + "/v1/capabilities", timeout=2).status_code == 401
    session = auth_session()
    image = png_bytes()
    digest = hashlib.sha256(image).hexdigest()
    assert session.put(api + f"/v1/blobs/{digest}", data=b"wrong bytes", headers={"Content-Type": "image/png"}, timeout=2).status_code == 400
    assert session.put(api + f"/v1/blobs/{digest}", data=image, headers={"Content-Type": "image/jpeg"}, timeout=2).status_code == 415
    assert session.put(api + f"/v1/blobs/{digest}", data=image, headers={"Content-Type": "image/png"}, timeout=2).status_code == 201
    got = session.get(api + f"/v1/blobs/{digest}", timeout=2)
    assert got.content == image
    assert got.headers["Content-Type"] == "image/png"

    event = {"event_id": str(uuid.uuid4()), "kind": "version",
             "payload": version_payload(str(uuid.uuid4()), str(uuid.uuid4()), image)}
    first = session.post(api + "/v1/events", json=event, timeout=2)
    second = session.post(api + "/v1/events", json=event, timeout=2)
    assert first.status_code == 200 and first.json()["duplicate"] is False
    assert second.status_code == 200 and second.json()["duplicate"] is True
    changed = json.loads(json.dumps(event))
    changed["payload"]["title"] = "Different bytes under the same id"
    assert session.post(api + "/v1/events", json=changed, timeout=2).status_code == 409
    private = json.loads(json.dumps(event))
    private["payload"]["prompt"] = "private prompt must never sync"
    assert session.post(api + "/v1/events", json=private, timeout=2).status_code == 400
    local_path = json.loads(json.dumps(event))
    local_path["event_id"] = str(uuid.uuid4())
    local_path["payload"]["source"]["url"] = "file:///C:/private/lesson.png"
    assert session.post(api + "/v1/events", json=local_path, timeout=2).status_code == 400


def test_canonical_compare_and_swap_preserves_conflicting_candidate(api):
    session = auth_session()
    image = png_bytes()
    digest = hashlib.sha256(image).hexdigest()
    session.put(api + f"/v1/blobs/{digest}", data=image, headers={"Content-Type": "image/png"}, timeout=2).raise_for_status()
    asset_id, version_id = str(uuid.uuid4()), str(uuid.uuid4())
    event = {"event_id": str(uuid.uuid4()), "kind": "version", "payload": version_payload(asset_id, version_id, image)}
    assert session.post(api + "/v1/events", json=event, timeout=2).status_code == 200
    canonical = {"asset_id": asset_id, "version_id": version_id, "expected_revision": 0, "revision": 1,
                 "canonical_title": "Water cycle"}
    accepted = {"event_id": str(uuid.uuid4()), "kind": "canonical", "payload": canonical}
    assert session.post(api + "/v1/events", json=accepted, timeout=2).status_code == 200
    stale = {"event_id": str(uuid.uuid4()), "kind": "canonical", "payload": canonical}
    rejected = session.post(api + "/v1/events", json=stale, timeout=2)
    assert rejected.status_code == 409
    assert rejected.json()["server_revision"] == 1
    assert rejected.json()["server_canonical_version_id"] == version_id
    events = session.get(api + "/v1/events?after=0&limit=50", timeout=2).json()["events"]
    assert [item["event_id"] for item in events] == [event["event_id"], accepted["event_id"]]


def test_budget_reservations_are_atomic_idempotent_and_uncertain(api):
    session = auth_session()
    assert session.post(api + "/v1/budget/reservations",
                        json={"operation_id": str(uuid.uuid4()), "amount_cents": True}, timeout=2).status_code == 400
    ids = [str(uuid.uuid4()), str(uuid.uuid4())]

    def reserve(operation_id: str):
        return session.post(api + "/v1/budget/reservations",
                            json={"operation_id": operation_id, "amount_cents": 2000}, timeout=4)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(reserve, ids))
    assert sorted(r.status_code for r in responses) == [200, 409]
    winner = next(r for r in responses if r.status_code == 200).json()
    duplicate = reserve(winner["operation_id"])
    assert duplicate.status_code == 200 and duplicate.json()["duplicate"] is True
    uncertain = session.post(api + f"/v1/budget/reservations/{winner['operation_id']}/uncertain", json={}, timeout=2)
    assert uncertain.status_code == 200 and uncertain.json()["state"] == "uncertain"
    assert session.post(api + f"/v1/budget/reservations/{winner['operation_id']}/release", json={}, timeout=2).status_code == 409
    committed = session.post(api + f"/v1/budget/reservations/{winner['operation_id']}/commit", json={}, timeout=2)
    assert committed.status_code == 200 and committed.json()["state"] == "committed"
    assert session.get(api + "/v1/budget", timeout=2).json()["spent_or_uncertain_cents"] == 2000


def test_two_store_transfer_retry_and_canonical_conflict(api, tmp_path):
    left = MediaStore(tmp_path / "left")
    right = MediaStore(tmp_path / "right")
    client_a = SyncClient(left, api, TOKEN, allow_private_sync=True)
    client_b = SyncClient(right, api, TOKEN, allow_private_sync=True)
    first_bytes = png_bytes((30, 90, 150))
    record = left.import_bytes(first_bytes, "Water cycle")
    left.set_canonical(record["asset_id"], record["version_id"], canonical_title="Water cycle approved")
    uploaded = client_a.sync_once()
    assert uploaded["uploaded_events"] == 2
    received = client_b.sync_once()
    assert received["downloaded_events"] == 2
    assert right.blob_path(record["sha256"]).read_bytes() == first_bytes
    assert right.get_version(record["version_id"])["sha256"] == record["sha256"]
    assert right.get_asset(record["asset_id"])["title"] == "Water cycle approved"

    # Both devices start from the same canonical revision, then choose
    # different versions while offline. The server accepts one CAS and retains
    # the stale outbox candidate locally after rejecting the other.
    second = right.import_bytes(png_bytes((90, 40, 20)), "Water cycle alternate", asset_id=record["asset_id"])
    right.set_canonical(record["asset_id"], second["version_id"])
    third = left.import_bytes(png_bytes((20, 140, 50)), "Water cycle revision", asset_id=record["asset_id"])
    left.set_canonical(record["asset_id"], third["version_id"])
    assert client_b.sync_once()["uploaded_events"] == 2
    conflict_result = client_a.sync_once()
    assert conflict_result["conflicts"]
    conflicts = left.list_conflicts()
    assert conflicts
    canonical_conflict = next(item for item in conflicts if item["local_version_id"] == third["version_id"])
    assert canonical_conflict["server_revision"] == 2
    assert canonical_conflict["server_canonical_version_id"] == second["version_id"]
    assert not any(event["event_id"] == canonical_conflict["event_id"] for event in left.pending_events())
    assert left.get_asset(record["asset_id"])["canonical_version_id"] == second["version_id"]

    # The blocked stale event does not loop on later automatic sync runs.
    assert client_a.sync_once()["conflicts"] == []
    page = auth_session().get(api + "/v1/events?after=0&limit=500", timeout=2).json()
    ids = [event["event_id"] for event in page["events"]]
    assert len(ids) == len(set(ids))


def test_sync_requires_explicit_private_policy_and_token(tmp_path):
    store = MediaStore(tmp_path / "store")
    with pytest.raises(ValueError, match="allow_private_sync"):
        SyncClient(store, "https://example.invalid", TOKEN)
    with pytest.raises(ValueError, match="bearer token"):
        SyncClient(store, "https://example.invalid", None, allow_private_sync=True)
    local = SyncClient(store, "https://example.invalid", None, local_only=True)
    assert local.sync_once()["local_only"] is True
