"""Focused local-only tests for the typed Board resource catalogue."""
import io
from pathlib import Path
import sys
import sqlite3
import uuid

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_resources import ResourceCatalogue
from media_store import MediaStore


def image_bytes(colour="steelblue"):
    stream = io.BytesIO()
    Image.new("RGB", (48, 32), colour).save(stream, "PNG")
    return stream.getvalue()


def test_image_catalogue_references_existing_media_version_without_copying(tmp_path):
    media = MediaStore(tmp_path / "media")
    image = media.import_bytes(image_bytes(), "Evaporation diagram", tags=["Science"])
    before = media.blob_path(image["sha256"]).read_bytes()
    catalogue = ResourceCatalogue(tmp_path / "board", media_store=media)
    saved = catalogue.save_resource("image", image["version_title"], image_ref={
        "asset_id": image["asset_id"], "version_id": image["version_id"], "sha256": image["sha256"]},
        aliases=["water cycle picture"], tags=["Year 5"], provenance={"basis": "teacher library"})
    assert saved["image_ref"] == {"asset_id": image["asset_id"], "version_id": image["version_id"], "sha256": image["sha256"]}
    assert saved["content_hash"] == image["sha256"]
    assert media.blob_path(image["sha256"]).read_bytes() == before
    assert list((tmp_path / "board").glob("*.png")) == []


def test_missing_or_mismatched_image_version_is_rejected(tmp_path):
    media = MediaStore(tmp_path / "media")
    image = media.import_bytes(image_bytes(), "Existing")
    catalogue = ResourceCatalogue(tmp_path / "board", media_store=media)
    with pytest.raises(ValueError, match="exact image version"):
        catalogue.save_resource("image", "Missing", media_ref={"asset_id": str(uuid.uuid4()),
            "version_id": image["version_id"], "sha256": image["sha256"]})
    with pytest.raises(ValueError, match="hash"):
        catalogue.save_resource("image", "Wrong hash", media_ref={"asset_id": image["asset_id"],
            "version_id": image["version_id"], "sha256": "0" * 64})


def test_typed_non_image_resources_are_immutable_and_relationships_pin_versions(tmp_path):
    catalogue = ResourceCatalogue(tmp_path / "board")
    dataset = catalogue.save_resource("dataset", "Monthly rainfall", metadata={"units": "mm", "rows": 4},
        content_hash="a" * 64, mime="text/csv", byte_size=120, provenance={"publisher": "BOM"}, state="approved")
    chart = catalogue.save_resource("chart", "Rainfall by month", metadata={"kind": "bar", "units": "mm"},
        state="draft", idempotency_key="chart-request-1")
    repeated = catalogue.save_resource("chart", "Rainfall by month", metadata={"kind": "bar", "units": "mm"},
        state="draft", idempotency_key="chart-request-1")
    link = catalogue.add_relationship(chart["version_id"], "derived_from", dataset["version_id"], {"transform": "monthly totals"})
    assert repeated["version_id"] == chart["version_id"]
    assert link["source_version_id"] == chart["version_id"]
    assert link["target_version_id"] == dataset["version_id"]
    revised = catalogue.save_resource("dataset", "Monthly rainfall revised", resource_id=dataset["resource_id"],
        metadata={"units": "mm", "rows": 5}, content_hash="b" * 64)
    assert revised["version_id"] != dataset["version_id"]
    assert catalogue.get_resource(dataset["resource_id"], dataset["version_id"])["metadata"]["rows"] == 4
    assert catalogue.relationships(chart["resource_id"])[0]["target_version_id"] == dataset["version_id"]
    with pytest.raises(ValueError, match="different resource payload"):
        catalogue.save_resource("chart", "Different later data", metadata={"kind": "line"},
            idempotency_key="chart-request-1")


def test_metadata_json_rejects_non_finite_values_and_missing_image_identities(tmp_path):
    catalogue = ResourceCatalogue(tmp_path / "board")
    with pytest.raises(ValueError, match="JSON-compatible"):
        catalogue.save_resource("dataset", "Invalid", metadata={"value": float("nan")})
    with pytest.raises(ValueError, match="exact asset_id"):
        catalogue.save_resource("image", "Missing identity", media_ref={"sha256": "a" * 64})


def test_catalogue_does_not_overwrite_a_newer_schema_version(tmp_path):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=2")
    with pytest.raises(ValueError, match="newer than this application supports"):
        ResourceCatalogue(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2


def test_image_availability_and_auto_selection_require_verified_local_bytes(tmp_path):
    media = MediaStore(tmp_path / "media")
    image = media.import_bytes(image_bytes(), "Verified image")
    catalogue = ResourceCatalogue(tmp_path / "board", media_store=media)
    ref = {key: image[key] for key in ("asset_id", "version_id", "sha256")}
    saved = catalogue.save_resource("image", "Verified image", media_ref=ref, state="approved")
    assert saved["availability"] == "offline"
    assert catalogue.auto_select("Verified image") is not None
    media.blob_path(image["sha256"]).unlink()
    missing_image = media.import_bytes(image_bytes("tomato"), "Missing bytes")
    media.blob_path(missing_image["sha256"]).unlink()
    unavailable = catalogue.save_resource("image", "Missing bytes", media_ref={
        key: missing_image[key] for key in ("asset_id", "version_id", "sha256")}, state="approved")
    assert unavailable["availability"] == "unavailable"
    assert catalogue.auto_select("Missing bytes") is None
    assert catalogue.auto_select("Verified image") is None


def test_relationship_version_filter_applies_to_both_endpoints(tmp_path):
    catalogue = ResourceCatalogue(tmp_path / "board")
    source_a = catalogue.save_resource("page", "Page A")
    source_b = catalogue.save_resource("page", "Page B")
    target_a = catalogue.save_resource("dataset", "Dataset A")
    target_b = catalogue.save_resource("dataset", "Dataset B")
    catalogue.add_relationship(source_a["version_id"], "uses", target_a["version_id"])
    catalogue.add_relationship(source_b["version_id"], "uses", target_b["version_id"])
    assert len(catalogue.relationships(source_a["resource_id"], source_a["version_id"])) == 1
    assert catalogue.relationships(source_a["resource_id"], source_b["version_id"]) == []


def test_search_is_local_deterministic_exact_alias_and_review_aware(tmp_path):
    catalogue = ResourceCatalogue(tmp_path / "board")
    media = MediaStore(tmp_path / "media")
    def save_image(title, state, aliases=(), description=""):
        image = media.import_bytes(image_bytes(), title)
        return catalogue.save_resource("image", title, description=description, aliases=aliases, state=state,
            media_ref={"asset_id": image["asset_id"], "version_id": image["version_id"], "sha256": image["sha256"]})
    draft = save_image("Water cycle sketch", "draft", ["our usual hydrological cycle"], "Unlabelled diagram")
    approved = catalogue.save_resource("chart", "Annual rainfall", description="Rainfall in millimetres", state="approved")
    rejected = save_image("Rejected water cycle", "rejected")
    assert catalogue.resolve("OUR USUAL HYDROLOGICAL CYCLE")["version_id"] == draft["version_id"]
    assert catalogue.auto_select("our usual hydrological cycle") is None
    assert catalogue.auto_select("Annual rainfall")["version_id"] == approved["version_id"]
    assert [item["version_id"] for item in catalogue.search("water cycle")] == [draft["version_id"]]
    assert all(item["version_id"] != rejected["version_id"] for item in catalogue.disambiguate("water cycle"))
    assert catalogue.resolve(rejected["version_id"]) is None
    assert catalogue.resolve(rejected["version_id"], include_excluded=True)["version_id"] == rejected["version_id"]
    assert catalogue.search("millimetres", resource_types=["image"]) == []
    assert {item["version_id"] for item in catalogue.search("water cycle", include_excluded=True)} == {draft["version_id"], rejected["version_id"]}


def test_ambiguous_alias_requires_disambiguation_and_exact_uuid_resolves(tmp_path):
    catalogue = ResourceCatalogue(tmp_path / "board")
    one = catalogue.save_resource("page", "Lesson A", aliases=["review sheet"])
    two = catalogue.save_resource("page", "Lesson B", aliases=["review sheet"])
    assert catalogue.resolve("review sheet") is None
    assert len(catalogue.disambiguate("review sheet")) == 2
    assert catalogue.resolve(one["version_id"])["version_id"] == one["version_id"]
    assert catalogue.get_resource(two["resource_id"])["version_id"] == two["version_id"]


def test_store_isolation_and_rebuildable_fts_index(tmp_path):
    one = ResourceCatalogue(tmp_path / "one")
    two = ResourceCatalogue(tmp_path / "two")
    item = one.save_resource("video", "Condensation explanation", description="Cloud formation segment", availability="metadata_only")
    assert one.search("condensation")
    assert two.search("condensation") == []
    assert one.rebuild_index() == 1
    assert one.search("cloud formation")[0]["version_id"] == item["version_id"]


@pytest.mark.parametrize("resource_type", ["image", "dataset", "chart", "page", "video"])
def test_supported_catalogue_types_accept_bounded_metadata(tmp_path, resource_type):
    catalogue = ResourceCatalogue(tmp_path / resource_type)
    image_ref = None
    if resource_type == "image":
        image_ref = {"asset_id": str(uuid.uuid4()), "version_id": str(uuid.uuid4()), "sha256": "c" * 64}
    item = catalogue.save_resource(resource_type, "Bounded resource", metadata={"units": "mm"}, media_ref=image_ref)
    assert item["resource_type"] == resource_type
