from __future__ import annotations

import hashlib
import io
import json
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import uuid

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from history_store import HistoryStore
from media_store import MediaStore


def image_bytes(colour: tuple[int, int, int] = (20, 80, 160), fmt: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 6), colour).save(buffer, format=fmt)
    return buffer.getvalue()


def test_import_builds_immutable_versions_and_content_deduplicated_blob(tmp_path):
    store = MediaStore(tmp_path)
    first = store.import_bytes(image_bytes(), "Water cycle", [" Science ", "water", "water"], prompt="private seed")
    second = store.import_bytes(image_bytes(), "Water cycle revision", ["science"], asset_id=first["asset_id"],
                                parent_version_id=first["version_id"], prompt="private refinement")

    assert first["sha256"] == hashlib.sha256(image_bytes()).hexdigest()
    assert first["mime"] == "image/png"
    assert (first["width"], first["height"]) == (8, 6)
    assert first["version_id"] != second["version_id"]
    assert second["parent_version_id"] == first["version_id"]
    assert store.blob_path(first["sha256"]) == store.blob_path(second["sha256"])
    assert store.blob_path(first["sha256"]).read_bytes() == image_bytes()
    assert [v["version_id"] for v in store.list_versions(first["asset_id"])] == [first["version_id"], second["version_id"]]
    assert store.get_version(first["version_id"])["sha256"] == first["sha256"]


def test_concurrent_identical_imports_share_one_blob_safely(tmp_path):
    store = MediaStore(tmp_path)
    data = image_bytes()
    with ThreadPoolExecutor(max_workers=6) as pool:
        records = list(pool.map(lambda n: store.import_bytes(data, f"Asset {n}"), range(6)))
    assert len({record["asset_id"] for record in records}) == 6
    assert len({record["sha256"] for record in records}) == 1
    assert len({store.blob_path(record["sha256"]) for record in records}) == 1
    assert store.blob_path(records[0]["sha256"]).read_bytes() == data


@pytest.mark.parametrize("data", [b"not an image", image_bytes(fmt="GIF"), b"x" * (20 * 1024 * 1024 + 1)],
                         ids=["invalid", "unsupported-format", "oversized"])
def test_rejects_bad_unsupported_and_oversized_images(tmp_path, data):
    with pytest.raises(ValueError):
        MediaStore(tmp_path).import_bytes(data, "invalid")


def test_rejects_image_over_pixel_limit_before_decode(tmp_path):
    # A valid PNG header with excessive dimensions is enough to trigger the size guard.
    data = bytearray(image_bytes())
    data[16:24] = (5001).to_bytes(4, "big") + (5000).to_bytes(4, "big")
    with pytest.raises(ValueError):
        MediaStore(tmp_path).import_bytes(bytes(data), "too large")


def test_search_is_unicode_casefolded_and_literal(tmp_path):
    store = MediaStore(tmp_path)
    store.import_bytes(image_bytes(), "Über den Wolken 100%", ["BÜCHER", "class_5"])

    assert len(store.list_assets("über")) == 1
    assert len(store.list_assets("bücher")) == 1
    assert store.list_assets("100%")
    assert store.list_assets("class_5")
    assert store.list_assets("classX5") == []


def test_canonical_selection_uses_optimistic_local_revision_and_keeps_versions(tmp_path):
    store = MediaStore(tmp_path)
    a = store.import_bytes(image_bytes(), "Poster")
    b = store.import_bytes(image_bytes((200, 20, 40)), "Poster edit", asset_id=a["asset_id"], parent_version_id=a["version_id"])

    selected = store.set_canonical(a["asset_id"], a["version_id"], expected_revision=0)
    assert selected["canonical_version_id"] == a["version_id"]
    with pytest.raises(ValueError, match="revision conflict"):
        store.set_canonical(a["asset_id"], b["version_id"], expected_revision=0)
    assert len(store.list_versions(a["asset_id"])) == 2
    assert store.get_asset(a["asset_id"])["canonical_version_id"] == a["version_id"]
    assert store.get_version(a["version_id"])["version_title"] == "Poster"


def test_canonical_title_is_shared_only_with_successful_compare_and_set(tmp_path):
    store = MediaStore(tmp_path)
    version = store.import_bytes(image_bytes(), "Draft")
    result = store.set_canonical(version["asset_id"], version["version_id"], expected_revision=0,
                                 canonical_title="Our water cycle")
    assert result["title"] == "Our water cycle"
    assert result["version_title"] == "Draft"
    canonical_event = store.pending_events()[-1]
    assert canonical_event["payload"]["canonical_title"] == "Our water cycle"


def test_queued_canonical_events_chain_server_revisions_in_order(tmp_path):
    store = MediaStore(tmp_path)
    first = store.import_bytes(image_bytes(), "Poster")
    second = store.import_bytes(image_bytes((1, 2, 3)), "Poster edit", asset_id=first["asset_id"], parent_version_id=first["version_id"])
    store.set_canonical(first["asset_id"], first["version_id"], expected_revision=0)
    store.set_canonical(first["asset_id"], second["version_id"], expected_revision=1)
    canonical_events = [event for event in store.pending_events() if event["kind"] == "canonical"]
    assert [(event["payload"]["expected_revision"], event["payload"]["revision"]) for event in canonical_events] == [(0, 1), (1, 2)]


def test_server_conflict_blocks_retry_and_resolution_rebases_explicit_choice(tmp_path):
    store = MediaStore(tmp_path)
    first = store.import_bytes(image_bytes(), "Poster")
    second = store.import_bytes(image_bytes((90, 30, 120)), "Poster edit", asset_id=first["asset_id"], parent_version_id=first["version_id"])
    store.set_canonical(first["asset_id"], first["version_id"], expected_revision=0)
    store.set_canonical(first["asset_id"], second["version_id"], expected_revision=1)
    second_choice = [event for event in store.pending_events() if event["kind"] == "canonical"][-1]

    conflict = store.record_sync_conflict(second_choice["event_id"], server_revision=5,
        server_canonical_version_id=first["version_id"], reason="revision_conflict")
    assert conflict["server_revision"] == 5
    assert second_choice["event_id"] not in {event["event_id"] for event in store.pending_events()}
    resolved = store.resolve_conflict(first["asset_id"], second["version_id"], canonical_title="Our poster")
    assert resolved["canonical_version_id"] == second["version_id"]
    assert resolved["title"] == "Our poster"
    assert resolved["version_title"] == "Poster edit"  # version snapshot remains immutable
    assert store.get_asset(first["asset_id"])["title"] == "Our poster"
    assert store.list_conflicts() == []
    canonical_events = [event for event in store.pending_events() if event["kind"] == "canonical"]
    assert len(canonical_events) == 1
    assert canonical_events[0]["payload"] == {"asset_id": first["asset_id"], "version_id": second["version_id"],
        "expected_revision": 5, "revision": 6, "canonical_title": "Our poster"}
    assert len(store.list_versions(first["asset_id"])) == 2


def test_outbox_excludes_prompt_and_source_is_allowlisted(tmp_path):
    store = MediaStore(tmp_path)
    result = store.add_generated(image_bytes(), "Generated poster", prompt="never sync this secret",
        source={"provider": "example", "model": "image-v1", "prompt": "also private", "api_key": "secret"})
    events = store.pending_events()
    assert len(events) == 1 and events[0]["kind"] == "version"
    serialised = json.dumps(events)
    assert "never sync" not in serialised and "also private" not in serialised and "secret" not in serialised
    assert events[0]["payload"]["source"] == {"model": "image-v1", "provider": "example"}
    assert store.get_version(result["version_id"])["origin"] == "generated"
    assert store.mark_event_synced(events[0]["event_id"])
    assert store.pending_events() == []


def test_remote_events_are_idempotent_and_canonical_conflicts_are_preserved(tmp_path):
    store = MediaStore(tmp_path)
    first = store.import_bytes(image_bytes(), "Poster")
    second = store.import_bytes(image_bytes((10, 200, 30)), "Poster edit", asset_id=first["asset_id"], parent_version_id=first["version_id"])
    store.mark_event_synced(store.pending_events()[0]["event_id"])

    remote_choice = {"event_id": "6e84df2d-e2b3-4092-9705-8e5ff25a968a", "kind": "canonical",
                     "payload": {"asset_id": first["asset_id"], "version_id": first["version_id"], "expected_revision": 0, "revision": 1}}
    assert store.apply_remote_event(remote_choice) is True
    assert store.apply_remote_event(remote_choice) is False
    conflict = {"event_id": "e30b3c6c-f010-4ec5-8ff7-4a9db55de295", "kind": "canonical",
                "payload": {"asset_id": first["asset_id"], "version_id": second["version_id"], "expected_revision": 0, "revision": 1}}
    assert store.apply_remote_event(conflict) is True
    assert store.get_asset(first["asset_id"])["canonical_version_id"] == first["version_id"]
    with store._connect() as db:
        assert db.execute("SELECT COUNT(*) FROM sync_conflict").fetchone()[0] == 1


def test_remote_immutable_version_id_rejects_changed_content_metadata(tmp_path):
    sender = MediaStore(tmp_path / "sender")
    receiver = MediaStore(tmp_path / "receiver")
    sender.import_bytes(image_bytes(), "Poster")
    event = sender.pending_events()[0]
    assert receiver.apply_remote_event(event)
    conflicting = {"event_id": str(uuid.uuid4()), "kind": "version", "payload": dict(event["payload"])}
    conflicting["payload"]["sha256"] = "f" * 64
    with pytest.raises(ValueError, match="immutable version ID"):
        receiver.apply_remote_event(conflicting)


def test_acknowledged_events_are_idempotent_when_pulled_back_and_restart_recovers_jobs(tmp_path):
    store = MediaStore(tmp_path)
    version = store.import_bytes(image_bytes(), "Poster")
    event = store.pending_events()[0]
    assert store.mark_event_synced(event["event_id"])
    assert store.apply_remote_event(event) is False
    job = store.create_job("generate", {"brief": "local only"})
    store.update_job(job["job_id"], "acquiring", provider_job_id="private-operation")
    reopened = MediaStore(tmp_path)
    assert reopened.recover_interrupted_jobs() == 1
    recovered = reopened.get_job(job["job_id"])
    assert recovered["phase"] == "needs_recovery"
    assert recovered["provider_job_id"] == "private-operation"
    assert reopened.get_version(version["version_id"]) is not None


def test_history_database_is_untouched_and_media_recovers_after_restart(tmp_path):
    history = HistoryStore(tmp_path / "companion.sqlite3")
    entry_id = history.add_entry("Ask", "local question", "local answer")
    with history._connect() as db:
        history_schema = db.execute("PRAGMA user_version").fetchone()[0]
        history_tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]

    store = MediaStore(tmp_path)
    image = store.import_bytes(image_bytes(), "Retained asset", prompt="local-only prompt")
    job = store.create_job("import", {"source_path": "local file path", "prompt": "local request"})
    reopened = MediaStore(tmp_path)

    assert reopened.get_version(image["version_id"])["sha256"] == image["sha256"]
    assert reopened.blob_path(image["sha256"]).exists()
    assert reopened.get_job(job["job_id"])["request"]["prompt"] == "local request"
    with history._connect() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == history_schema == 1
        assert [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")] == history_tables
    assert history.get_entry(entry_id)["request"] == "local question"


def test_local_backup_restores_database_blobs_jobs_and_prompts_without_overwrite(tmp_path):
    store = MediaStore(tmp_path / "source")
    version = store.add_generated(image_bytes(), "Local draft", prompt="private local prompt")
    job = store.create_job("generate", {"brief": "local only"})
    backup = store.export_backup(tmp_path / "backup")
    with pytest.raises(FileExistsError):
        store.export_backup(backup)

    restored = MediaStore.restore_backup(backup, tmp_path / "restored")
    assert restored.get_version(version["version_id"])["sha256"] == version["sha256"]
    assert restored.blob_path(version["sha256"]).read_bytes() == image_bytes()
    assert restored.get_job(job["job_id"])["request"] == {"brief": "local only"}
    with restored._connect() as db:
        assert db.execute("SELECT prompt FROM local_prompt WHERE version_id=?", (version["version_id"],)).fetchone()[0] == "private local prompt"
    with pytest.raises(FileExistsError):
        MediaStore.restore_backup(backup, tmp_path / "restored")
