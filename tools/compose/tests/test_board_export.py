"""Portable lesson archive safety and PDF rendering checks."""
import io
import hashlib
import json
from pathlib import Path
import shutil
import stat
import sys
import uuid
import zipfile

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_export import export_lesson, export_pdf, import_lesson
from board_model import BoardModel, new_object
from board_resources import ResourceCatalogue
from board_store import BoardStore
from board_library import BoardResourceLibrary
from board_resource_policy import render_chart
from media_store import MediaStore


def image_bytes(size=(160, 90), colour="royalblue"):
    stream = io.BytesIO()
    Image.new("RGB", size, colour).save(stream, "PNG")
    return stream.getvalue()


def build_lesson(root):
    media = MediaStore(root / "source-media")
    source = {"creator": "A Teacher", "licence": "CC BY 4.0", "attribution": "A Teacher, classroom diagram",
              "url": "https://example.org/diagram?token=secret"}
    original = media.import_bytes(image_bytes(), "Water cycle", source=source)
    refined = media.add_generated(image_bytes(colour="darkcyan"), "Water cycle labelled", asset_id=original["asset_id"],
                                  parent_version_id=original["version_id"], prompt="private prompt to exclude")
    image_ref = {"asset_id": refined["asset_id"], "version_id": refined["version_id"], "sha256": refined["sha256"]}
    model = BoardModel()
    page_id = model.snapshot()["pages"][0]["id"]
    model.apply([{"op": "add_object", "page_id": page_id,
                  "object": new_object("text", x=40, y=40, width=400, height=100, text="Water moves through the cycle", font_size=30)}], expected_revision=0)
    model.apply([{"op": "add_object", "page_id": page_id,
                  "object": new_object("image", x=180, y=180, width=320, height=180, image_ref=image_ref)},
                 {"op": "add_object", "page_id": page_id,
                  "object": new_object("shape", x=600, y=180, width=100, height=80, shape="ellipse", fill="#DDEEFF")},
                 {"op": "add_object", "page_id": page_id,
                  "object": new_object("arrow", x=500, y=200, width=100, height=100)},
                 {"op": "add_object", "page_id": page_id,
                  "object": new_object("ink", x=750, y=180, width=100, height=100, points=[[0,0],[50,50],[100,0]])}], expected_revision=1)
    model.undo(expected_revision=2)
    return media, model, original, refined


def unzip_entries(path):
    with zipfile.ZipFile(path) as archive:
        return {info.filename: archive.read(info.filename) for info in archive.infolist()}


def write_package(path, entries):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def test_roundtrip_is_self_contained_and_preserves_history_and_provenance(tmp_path):
    media, model, original, refined = build_lesson(tmp_path)
    package = export_lesson(model, tmp_path / "water-cycle.tboard", media_store=media)
    entries = unzip_entries(package)
    assert "manifest.json" in entries and "state.json" in entries
    assert b"private prompt" not in b"".join(entries.values())
    manifest = json.loads(entries["manifest.json"])
    assert {item["version_id"] for item in manifest["media_versions"]} == {original["version_id"], refined["version_id"]}
    assert "token=secret" not in b"".join(entries.values()).decode("utf-8", "ignore")
    destination = tmp_path / "imported"
    store = import_lesson(package, destination)
    restored = store.load()
    state = restored.export_state()
    assert state == model.export_state()
    assert len(state["redo"]) == 1
    assert MediaStore(destination / "media").blob_path(refined["sha256"]).read_bytes() == media.blob_path(refined["sha256"]).read_bytes()
    copied = MediaStore(destination / "media").get_version(original["version_id"])
    assert copied["source"]["attribution"] == "A Teacher, classroom diagram"
    assert copied["source"]["url"] == "https://example.org/diagram"
    assert MediaStore(destination / "media").get_version(refined["version_id"])["version_title"] == "Water cycle labelled"
    assert MediaStore(destination / "media").list_jobs() == []


def test_catalogue_dataset_chart_dependency_closure_preserves_exact_ids_and_specs(tmp_path):
    media, model, *_ = build_lesson(tmp_path)
    catalogue = ResourceCatalogue(tmp_path / "source-catalogue", media_store=media)
    dataset_metadata = {"units": "mm", "rows": [{"month": "Jan", "value": 31.2}]}
    dataset_bytes = json.dumps(dataset_metadata, sort_keys=True, separators=(",", ":")).encode()
    dataset = catalogue.save_resource("dataset", "Monthly rainfall", metadata=dataset_metadata,
        content_hash=hashlib.sha256(dataset_bytes).hexdigest(), mime="application/json", byte_size=len(dataset_bytes),
        provenance={"publisher": "Example climate authority"}, state="approved")
    chart = catalogue.save_resource("chart", "Rainfall chart", metadata={"kind": "bar", "x": "month", "y": "value", "units": "mm"},
        state="approved")
    catalogue.add_relationship(chart["version_id"], "derived_from", dataset["version_id"], {"operation": "monthly totals"})
    package = export_lesson(model, tmp_path / "with-data.tboard", media_store=media, catalogue=catalogue,
                            catalogue_refs=[chart["version_id"]])
    assert b"C:\\private\\dataset.csv" not in b"".join(unzip_entries(package).values())
    imported = tmp_path / "imported-with-data"
    import_lesson(package, imported)
    restored_catalogue = ResourceCatalogue(imported / "catalogue", media_store=MediaStore(imported / "media"))
    restored_dataset = restored_catalogue.get_resource(dataset["resource_id"], dataset["version_id"])
    restored_chart = restored_catalogue.get_resource(chart["resource_id"], chart["version_id"])
    assert restored_dataset["metadata"] == {"units": "mm", "rows": [{"month": "Jan", "value": 31.2}]}
    assert restored_chart["metadata"] == chart["metadata"]
    assert restored_catalogue.relationships(chart["resource_id"], chart["version_id"])[0]["target_version_id"] == dataset["version_id"]

    private_metadata = {"units": "mm", "source_path": "C:\\private\\must-not-be-rewritten.csv"}
    private = catalogue.save_resource("dataset", "Private source", metadata=private_metadata,
        content_hash="b" * 64, state="approved")
    with pytest.raises(ValueError, match="cannot be exported without changing its content hash"):
        export_lesson(model, tmp_path / "private-source.tboard", media_store=media, catalogue=catalogue,
                      catalogue_refs=[private["version_id"]])


def test_real_local_chart_artifact_and_dependency_closure_reopen_offline(tmp_path):
    library = BoardResourceLibrary(tmp_path / "source-library")
    dataset = {"schema": 1, "title": "Monthly rainfall", "x": {"label": "Month", "unit": "month"},
        "y": {"label": "Rainfall", "unit": "mm"},
        "points": [{"label": "January", "value": 80}, {"label": "February", "value": None},
                   {"label": "March", "value": 120}],
        "provenance": {"kind": "published", "publisher": "Australian Example Bureau",
            "source_url": "https://example.org/rain", "date": "2026-10-25", "licence": "CC BY 4.0",
            "coverage": "Monthly, 2025"}, "illustrative": False}
    artifact = render_chart(dataset, {"kind": "bar", "title": "Rainfall by month"})
    catalogue = library.catalogue
    source_dataset_record = catalogue.save_resource("dataset", dataset["title"], metadata=artifact.dataset,
        content_hash=artifact.dataset_sha256, state="approved", availability="offline",
        idempotency_key="dataset:" + artifact.dataset_sha256)
    source_chart_record = catalogue.save_resource("chart", artifact.spec["title"], metadata=artifact.spec,
        content_hash=artifact.spec_sha256, state="approved", availability="offline",
        idempotency_key="chart:" + artifact.spec_sha256 + ":" + artifact.dataset_sha256)
    catalogue.add_relationship(source_chart_record["version_id"], "derived_from", source_dataset_record["version_id"])
    version = library.media.import_bytes(artifact.image_bytes, artifact.spec["title"],
        operation_id=str(uuid.uuid5(uuid.NAMESPACE_URL, "test-chart:" + artifact.dataset_sha256 + ":" + artifact.spec_sha256)))
    source_image_record = library._index(version, library.media.root, approved=True,
        source_metadata={"visual_kind": "chart", "dataset_sha256": artifact.dataset_sha256,
                         "chart_spec_sha256": artifact.spec_sha256})
    catalogue.add_relationship(source_image_record["version_id"], "rendered_from", source_chart_record["version_id"])
    reference = source_image_record["image_ref"]
    # An unrelated saved lesson consumes the same image and also owns a unique
    # image. Exporting the shared image must not pull that incoming consumer in.
    private_version = library.media.import_bytes(image_bytes(colour="darkorange"), "Unrelated private image",
        operation_id=str(uuid.uuid4()))
    private_image = library._index(private_version, library.media.root, approved=True)
    private_page_metadata = {"schema": 1, "page_text": "UNRELATED_PRIVATE_LESSON_SENTINEL"}
    private_page_record = catalogue.save_resource("page", "Unrelated private lesson",
        metadata=private_page_metadata,
        content_hash=hashlib.sha256(json.dumps(private_page_metadata, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        provenance={"kind": "teaching_board", "request_id": "local-job-receipt-should-not-export"},
        state="approved", availability="offline")
    catalogue.add_relationship(private_page_record["version_id"], "uses", source_image_record["version_id"])
    catalogue.add_relationship(private_page_record["version_id"], "uses", private_image["version_id"])
    lesson_media = library.media
    model = BoardModel()
    page_id = model.snapshot()["pages"][0]["id"]
    model.apply([{"op": "add_object", "page_id": page_id,
                  "object": new_object("image", x=40, y=40, width=600, height=360, image_ref=reference)}],
                expected_revision=0)
    # Match the UI call: the exporter receives the lesson and catalogue only,
    # and derives exact dependency roots from image references in the lesson.
    package = export_lesson(model, tmp_path / "monthly-rainfall.tboard", media_store=lesson_media,
        catalogue=library.catalogue)
    with zipfile.ZipFile(package) as archive:
        package_catalogue = json.loads(archive.read("catalogue.json"))
        packaged_versions = {item["version_id"] for item in package_catalogue["resources"]}
        assert private_page_record["version_id"] not in packaged_versions
        assert private_image["version_id"] not in packaged_versions
        assert b"UNRELATED_PRIVATE_LESSON_SENTINEL" not in archive.read("catalogue.json")
        assert b"local-job-receipt-should-not-export" not in archive.read("catalogue.json")
        assert source_chart_record["version_id"] in packaged_versions
        assert source_dataset_record["version_id"] in packaged_versions

    # An explicitly requested saved page is a valid export root, but its local
    # request receipt is still not portable provenance.
    explicit_page_package = export_lesson(model, tmp_path / "with-explicit-page.tboard",
        media_store=lesson_media, catalogue=catalogue,
        catalogue_refs=[private_page_record["version_id"]])
    with zipfile.ZipFile(explicit_page_package) as archive:
        explicit_catalogue = json.loads(archive.read("catalogue.json"))
        packaged_page = next(item for item in explicit_catalogue["resources"]
                             if item["version_id"] == private_page_record["version_id"])
        assert packaged_page["provenance"] == {"kind": "teaching_board"}
    imported_root = tmp_path / "reopened-chart"
    imported_store = import_lesson(package, imported_root)
    restored_model = imported_store.load()
    restored_ref = next(obj["image_ref"] for page in restored_model.snapshot()["pages"]
                        for obj in page["objects"] if obj["type"] == "image")
    assert restored_ref == reference

    # Reopen the isolated imported library and verify the exact image bytes
    # resolve from its managed local blob store without a provider or source path.
    restored_library = BoardResourceLibrary(imported_root)
    restored_media = MediaStore(imported_root / "media")
    image_record = restored_library.catalogue.get_resource_by_version(reference["version_id"])
    restored_image = restored_media.get_version(reference["version_id"])
    restored_bytes = restored_media.blob_path(reference["sha256"]).read_bytes()
    assert restored_image["sha256"] == reference["sha256"]
    assert hashlib.sha256(restored_bytes).hexdigest() == reference["sha256"]
    assert image_record["provenance"]["dataset_sha256"] == hashlib.sha256(
        json.dumps(dataset, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()

    image_relations = restored_library.catalogue.relationships(image_record["resource_id"], image_record["version_id"])
    chart_edge = next(edge for edge in image_relations if edge["relation"] == "rendered_from")
    chart_record = restored_library.catalogue.get_resource_by_version(chart_edge["target_version_id"])
    dataset_edge = next(edge for edge in restored_library.catalogue.relationships(chart_record["resource_id"], chart_record["version_id"])
                        if edge["relation"] == "derived_from")
    dataset_record = restored_library.catalogue.get_resource_by_version(dataset_edge["target_version_id"])
    assert (chart_record["resource_id"], chart_record["version_id"]) == (source_chart_record["resource_id"], source_chart_record["version_id"])
    assert (dataset_record["resource_id"], dataset_record["version_id"]) == (source_dataset_record["resource_id"], source_dataset_record["version_id"])
    assert dataset_record["metadata"]["y"]["unit"] == "mm"
    assert dataset_record["metadata"]["points"] == dataset["points"]
    assert dataset_record["metadata"]["provenance"]["publisher"] == "Australian Example Bureau"
    assert chart_record["metadata"]["kind"] == "bar"
    dataset_hash = hashlib.sha256(json.dumps(dataset_record["metadata"], ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    chart_hash = hashlib.sha256(json.dumps(chart_record["metadata"], ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    assert dataset_record["content_hash"] == dataset_hash == source_dataset_record["content_hash"]
    assert chart_record["content_hash"] == chart_hash == source_chart_record["content_hash"]
    assert restored_media.get_version(reference["version_id"])["sha256"] == reference["sha256"]


def test_import_requires_fresh_destination_and_export_never_overwrites(tmp_path):
    media, model, *_ = build_lesson(tmp_path)
    package = export_lesson(model, tmp_path / "lesson.tboard", media_store=media)
    with pytest.raises(FileExistsError):
        export_lesson(model, package, media_store=media)
    with pytest.raises(FileExistsError):
        import_lesson(package, tmp_path)


@pytest.mark.parametrize("bad_member", ["../outside", "C:/outside", "/absolute", "blobs\\..\\outside"])
def test_unsafe_paths_are_rejected_before_destination_publication(tmp_path, bad_member):
    media, model, *_ = build_lesson(tmp_path)
    valid = export_lesson(model, tmp_path / "valid.tboard", media_store=media)
    entries = unzip_entries(valid)
    entries[bad_member] = b"bad"
    package = tmp_path / "bad.tboard"
    write_package(package, entries)
    destination = tmp_path / "must-not-exist"
    with pytest.raises(ValueError):
        import_lesson(package, destination)
    assert not destination.exists()


def test_duplicate_entries_symlinks_and_compression_bombs_are_rejected(tmp_path):
    media, model, *_ = build_lesson(tmp_path)
    valid = export_lesson(model, tmp_path / "valid.tboard", media_store=media)
    entries = unzip_entries(valid)
    duplicate = tmp_path / "duplicate.tboard"
    with pytest.warns(UserWarning, match="Duplicate name"):
        with zipfile.ZipFile(duplicate, "w") as archive:
            archive.writestr("manifest.json", entries["manifest.json"])
            archive.writestr("state.json", entries["state.json"])
            archive.writestr("state.json", entries["state.json"])
    with pytest.raises(ValueError):
        import_lesson(duplicate, tmp_path / "duplicate-dest")

    symlink = tmp_path / "symlink.tboard"
    with zipfile.ZipFile(symlink, "w") as archive:
        archive.writestr("manifest.json", entries["manifest.json"])
        info = zipfile.ZipInfo("link")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "../../outside")
    with pytest.raises(ValueError):
        import_lesson(symlink, tmp_path / "symlink-dest")

    bomb = tmp_path / "bomb.tboard"
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("manifest.json", entries["manifest.json"])
        archive.writestr("state.json", entries["state.json"])
        archive.writestr("bloat", b"0" * (2 * 1024 * 1024))
    with pytest.raises(ValueError):
        import_lesson(bomb, tmp_path / "bomb-dest")


def test_duplicate_json_fields_are_rejected_before_publication(tmp_path):
    package = tmp_path / "duplicate-fields.tboard"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", b'{"format":"bad","format":"teaching-board-portable"}')
        archive.writestr("state.json", b"{}")
    destination = tmp_path / "duplicate-fields-dest"
    with pytest.raises(ValueError, match="duplicate fields"):
        import_lesson(package, destination)
    assert not destination.exists()


def test_missing_or_tampered_exact_image_dependency_is_rejected_atomically(tmp_path):
    media, model, *_ = build_lesson(tmp_path)
    valid = export_lesson(model, tmp_path / "valid.tboard", media_store=media)
    entries = unzip_entries(valid)
    manifest = json.loads(entries["manifest.json"])
    manifest["media_versions"] = []
    entries["manifest.json"] = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    missing = tmp_path / "missing.tboard"; write_package(missing, entries)
    missing_dest = tmp_path / "missing-dest"
    with pytest.raises(ValueError, match="missing an exact"):
        import_lesson(missing, missing_dest)
    assert not missing_dest.exists()

    entries = unzip_entries(valid)
    entries["state.json"] += b" "
    tampered = tmp_path / "tampered.tboard"; write_package(tampered, entries)
    tampered_dest = tmp_path / "tampered-dest"
    with pytest.raises(ValueError, match="hash or size"):
        import_lesson(tampered, tampered_dest)
    assert not tampered_dest.exists()


def test_pdf_export_contains_text_credits_and_all_board_primitives(tmp_path):
    media, model, *_ = build_lesson(tmp_path)
    model.redo(expected_revision=model.revision)
    page_id = model.snapshot()["pages"][0]["id"]
    model.apply([{"op": "add_object", "page_id": page_id,
                  "object": new_object("text", x=40, y=700, width=300, height=60, text="Māori", font_size=24)}],
                expected_revision=model.revision)
    def resolver(ref):
        record = media.get_version(ref["version_id"])
        return media.blob_path(record["sha256"]).read_bytes()
    target = export_pdf(model, tmp_path / "lesson.pdf", image_resolver=resolver, media_store=media)
    assert target.is_file() and target.stat().st_size > 1000
    try:
        import pdfplumber
    except ImportError:
        pytest.skip("pdfplumber unavailable in this runtime")
    with pdfplumber.open(target) as pdf:
        assert len(pdf.pages) == 1
        text = " ".join((pdf.pages[0].extract_text() or "").split())
        assert "Water cycle" in text
        assert "Credits and provenance" in text
        assert "A Teacher" in text
        assert "Māori" in text


def test_pdf_export_fails_clearly_on_unavailable_image_and_overflowing_text(tmp_path):
    media, model, *_ = build_lesson(tmp_path)
    model.redo(expected_revision=model.revision)
    with pytest.raises(ValueError, match="image is unavailable"):
        export_pdf(model, tmp_path / "missing.pdf", image_resolver=lambda _ref: b"bad")

    no_image = BoardModel()
    page = no_image.snapshot()["pages"][0]
    no_image.apply([{"op": "add_object", "page_id": page["id"],
                     "object": new_object("text", x=0, y=0, width=10, height=10, text="Text does not fit", font_size=500)}], expected_revision=0)
    with pytest.raises(ValueError, match="cannot fit"):
        export_pdf(no_image, tmp_path / "overflow.pdf", image_resolver=lambda _ref: b"")
