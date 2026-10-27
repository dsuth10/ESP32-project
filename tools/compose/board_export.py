"""Portable, bounded Teaching Board packages and vector PDF export.

Packages contain validated lesson state/history, exact image version records,
and content-addressed image bytes. No provider jobs, profile, credentials, or
source-library paths are exported.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
from urllib.parse import urlsplit, urlunsplit
import uuid
import zipfile
from typing import Any, Callable

from board_model import BoardModel, BoardValidationError, canonical_json
from board_store import BoardStore, BoardStoreError
from media_store import MediaStore


FORMAT = "teaching-board-portable"
SCHEMA = 1
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_UNPACKED_BYTES = 256 * 1024 * 1024
MAX_ENTRIES = 2048
MAX_IMAGE_BYTES = 32 * 1024 * 1024
MAX_VERSIONS = 1000
MAX_CATALOGUE_DEPENDENCIES = 256
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_JSON_FILE_BYTES = 20 * 1024 * 1024
_VERSION_FIELDS = {"asset_id", "version_id", "title", "tags", "sha256", "mime", "width", "height",
                   "byte_size", "parent_version_id", "source", "origin", "created_at"}
_PRIVATE_KEYS = {"path", "root", "prompt", "transcript", "credential", "password", "token", "job", "history", "profile", "secret", "api_key", "session"}


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Portable lesson JSON cannot contain duplicate fields.")
        result[key] = value
    return result


def _nonfinite(_value: str) -> None:
    raise ValueError("Portable lesson JSON numbers must be finite.")


def _load_json(data: bytes) -> Any:
    return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_nonfinite)


def _as_model(value: Any) -> BoardModel:
    if isinstance(value, BoardModel):
        return BoardModel.from_state(value.export_state())
    if isinstance(value, dict):
        return BoardModel.from_state(copy.deepcopy(value))
    raise BoardValidationError("Export a validated BoardModel or exported Board session state.")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_member(name: str) -> str:
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise ValueError("Package contains an unsafe member path.")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts) or ":" in path.parts[0]:
        raise ValueError("Package contains an unsafe member path.")
    if path.as_posix() != name:
        raise ValueError("Package paths must use canonical relative POSIX form.")
    return name


def _reject_linked_path(path: Path) -> None:
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("Portable lesson paths must not redirect through links or junctions.")


def _version_record(media_store: MediaStore, version_id: str) -> dict[str, Any]:
    record = media_store.get_version(version_id)
    if record is None:
        raise ValueError("A lesson image version is missing from the selected media store.")
    result = {key: record[key] for key in _VERSION_FIELDS}
    result["title"] = record["version_title"]
    result["tags"] = record["version_tags"]
    result["source"] = _portable_source(result["source"])
    licence = result["source"].get("licence", "").casefold()
    if "cc by" in licence and not (result["source"].get("attribution") or result["source"].get("creator")):
        raise ValueError("A CC BY image is missing required creator or attribution details.")
    data = media_store.blob_path(record["sha256"]).read_bytes()
    if len(data) > MAX_IMAGE_BYTES or len(data) != record["byte_size"] or _sha(data) != record["sha256"]:
        raise ValueError("A lesson image is damaged or exceeds the package size limit.")
    mime, width, height = MediaStore._inspect(data)
    if (mime, width, height) != (record["mime"], record["width"], record["height"]):
        raise ValueError("A lesson image does not match its immutable version metadata.")
    return result


def _portable_source(source: Any) -> dict[str, str]:
    """Retain recognised provenance while excluding local file paths."""
    if not isinstance(source, dict):
        return {}
    allowed = {"url", "creator", "licence", "attribution", "provider", "model"}
    result = {key: str(source[key])[:2000] for key in allowed if key in source and source[key] is not None}
    url = result.get("url")
    if url:
        parsed = urlsplit(url)
        if parsed.scheme.casefold() not in {"http", "https"} or parsed.username or parsed.password:
            result.pop("url", None)
        else:
            # Strip query and fragment so signed/private URLs are never portable.
            result["url"] = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return result


def _image_refs(state: dict[str, Any]) -> dict[str, dict[str, str]]:
    refs: dict[str, dict[str, str]] = {}
    documents = [state["document"], *state["undo"], *state["redo"]]
    for document in documents:
        for page in document["pages"]:
            for obj in page["objects"]:
                if obj["type"] != "image":
                    continue
                ref = obj["image_ref"]
                prior = refs.get(ref["version_id"])
                if prior and prior != ref:
                    raise ValueError("A lesson reuses an image version ID with different hashes.")
                refs[ref["version_id"]] = copy.deepcopy(ref)
    return refs


def _private_safe(value: Any, depth: int = 0) -> Any:
    if depth > 16:
        raise ValueError("Catalogue dependency metadata is too deeply nested.")
    if isinstance(value, dict):
        safe = {}
        for key, item in value.items():
            normalized = str(key).casefold()
            if (normalized in _PRIVATE_KEYS or normalized.endswith("_path") or "credential" in normalized
                    or "password" in normalized or "token" in normalized or "secret" in normalized
                    or "prompt" in normalized or "history" in normalized or "profile" in normalized
                    or "job_id" in normalized or "session" in normalized):
                continue
            if normalized.endswith("url") and isinstance(item, str):
                parsed = urlsplit(item)
                if parsed.scheme.casefold() not in {"http", "https"} or parsed.username or parsed.password:
                    continue
                item = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
            safe[str(key)] = _private_safe(item, depth + 1)
        return safe
    if isinstance(value, list):
        if len(value) > 1000:
            raise ValueError("Catalogue dependency lists exceed the package bound.")
        return [_private_safe(item, depth + 1) for item in value]
    if isinstance(value, str):
        if len(value) > 20000:
            raise ValueError("Catalogue dependency text exceeds the package bound.")
        lowered = value.casefold()
        if lowered.startswith("file:") or re.match(r"^[a-z]:[\\/]|^\\\\", value, flags=re.IGNORECASE):
            return "[local path omitted]"
        return value
    if value is None or type(value) in {bool, int, float}:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Catalogue dependency numbers must be finite.")
        return value
    raise ValueError("Catalogue dependency metadata must be JSON-compatible.")


def _catalogue_closure(catalogue: Any, refs: tuple[str, ...] | list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if catalogue is None:
        return [], []
    queue = list(refs)
    resources: dict[tuple[str, str], dict[str, Any]] = {}
    edges: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    while queue and len(resources) < MAX_CATALOGUE_DEPENDENCIES:
        reference = queue.pop(0)
        item = catalogue.resolve(reference, include_excluded=True)
        if not item:
            continue
        key = (item["resource_id"], item["version_id"])
        if key in resources:
            continue
        metadata = _private_safe(item["metadata"])
        if item["content_hash"] is not None and metadata != item["metadata"]:
            raise ValueError("Immutable catalogue metadata contains private fields and cannot be exported without changing its content hash.")
        provenance = item["provenance"]
        if item["resource_type"] == "page" and isinstance(provenance, dict):
            # This is a local request receipt, not portable lesson provenance.
            provenance = {name: value for name, value in provenance.items() if name != "request_id"}
        resources[key] = {"resource_id": item["resource_id"], "version_id": item["version_id"],
                          "resource_type": item["resource_type"], "title": item.get("source_title", item["title"]),
                          "description": item.get("source_description", item["description"]),
                          "tags": item.get("source_tags", item["tags"]),
                          "aliases": item["aliases"],
                          "metadata": metadata, "provenance": _private_safe(provenance),
                          "content_hash": item["content_hash"], "mime": item["mime"], "byte_size": item["byte_size"],
                          "availability": item["availability"], "review_state": item["review_state"]}
        teacher_metadata = {name: item[name] for name in ("title", "description", "tags", "topics", "year_levels")
                            if name in item}
        if (item.get("has_teacher_metadata")
                or any(item.get("source_" + name, item[name]) != item[name] for name in ("title", "description", "tags"))
                or item.get("topics") or item.get("year_levels")):
            if _private_safe(teacher_metadata) != teacher_metadata:
                raise ValueError("Teacher resource metadata contains private fields and cannot be exported unchanged.")
            resources[key]["teacher_metadata"] = teacher_metadata
        for edge in catalogue.relationships(item["resource_id"], item["version_id"]):
            # Follow dependencies only from this resource to its targets.
            # Incoming consumers (such as unrelated saved pages using a
            # shared image) are outside this lesson's dependency closure.
            if (edge["source_resource_id"], edge["source_version_id"]) != key:
                continue
            edges[(edge["source_resource_id"], edge["source_version_id"], edge["relation"],
                   edge["target_resource_id"], edge["target_version_id"])] = _private_safe(edge)
            queue.append(edge["target_version_id"])
    if queue:
        raise ValueError("Catalogue dependency closure exceeds 256 resources.")
    return list(resources.values()), list(edges.values())


def export_lesson(model_or_state: Any, destination: Path | str, *, media_store: MediaStore,
                  catalogue: Any = None, catalogue_refs: tuple[str, ...] | list[str] = ()) -> Path:
    """Write a portable .tboard ZIP without changing its source lesson or media store."""
    model = _as_model(model_or_state)
    state = model.export_state()
    refs = _image_refs(state)
    versions: dict[str, dict[str, Any]] = {}
    pending = list(refs)
    while pending:
        if len(versions) >= MAX_VERSIONS:
            raise ValueError("Image lineage exceeds the package version limit.")
        version_id = pending.pop(0)
        if version_id in versions:
            continue
        record = _version_record(media_store, version_id)
        ref = refs.get(version_id)
        if ref and (record["asset_id"] != ref["asset_id"] or record["sha256"] != ref["sha256"]):
            raise ValueError("A lesson image reference does not match its pinned media version.")
        versions[version_id] = record
        if record["parent_version_id"]:
            pending.append(record["parent_version_id"])
    # Exact image versions used anywhere in the editable document's undo/redo
    # snapshots are natural roots for typed dependencies such as chart specs
    # and datasets. Explicit roots remain supported for callers exporting
    # resources not represented by Board image objects.
    roots = list(dict.fromkeys([*refs.keys(), *catalogue_refs]))
    catalogue_resources, catalogue_relationships = _catalogue_closure(catalogue, roots)
    # Image dependencies in catalogue relationships are also packaged by exact
    # version and hash. Other typed resources retain their bounded JSON metadata.
    pending = [item["version_id"] for item in catalogue_resources if item["resource_type"] == "image"]
    while pending:
        if len(versions) >= MAX_VERSIONS:
            raise ValueError("Catalogue image lineage exceeds the package version limit.")
        version_id = pending.pop(0)
        if version_id in versions:
            continue
        record = _version_record(media_store, version_id)
        if (record["asset_id"], record["sha256"]) != next(
                (item["resource_id"], item["content_hash"]) for item in catalogue_resources if item["version_id"] == version_id):
            raise ValueError("Catalogue image dependency does not match the selected media version.")
        versions[version_id] = record
        if record["parent_version_id"]:
            pending.append(record["parent_version_id"])
    # Prove all ancestry terminates, stays within its asset, and is acyclic.
    for version_id, record in versions.items():
        seen = {version_id}
        parent_id = record["parent_version_id"]
        depth = 0
        while parent_id:
            depth += 1
            if depth >= 100 or parent_id in seen or parent_id not in versions:
                raise ValueError("Image lineage is invalid or incomplete.")
            seen.add(parent_id)
            parent = versions[parent_id]
            if parent["asset_id"] != record["asset_id"]:
                raise ValueError("Image lineage crosses asset identities.")
            parent_id = parent["parent_version_id"]

    files: dict[str, bytes] = {"state.json": canonical_json(state)}
    version_manifest = []
    for version_id in sorted(versions):
        record = versions[version_id]
        data = media_store.blob_path(record["sha256"]).read_bytes()
        blob_path = f"blobs/sha256/{record['sha256'][:2]}/{record['sha256'][2:]}"
        files.setdefault(blob_path, data)
        version_manifest.append({**record, "blob_path": blob_path})
    if catalogue is not None and (catalogue_resources or catalogue_relationships):
        if len(catalogue_relationships) > 4096:
            raise ValueError("Catalogue dependency relationships exceed the package limit.")
        files["catalogue.json"] = json.dumps({"resources": catalogue_resources, "relationships": catalogue_relationships},
                                             ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(files) + 1 > MAX_ENTRIES:
        raise ValueError("Portable lesson has too many files.")
    if sum(map(len, files.values())) > MAX_UNPACKED_BYTES:
        raise ValueError("Portable lesson exceeds the total size limit.")
    manifest = {"format": FORMAT, "schema": SCHEMA,
                "files": {name: {"sha256": _sha(data), "size": len(data)} for name, data in sorted(files.items())},
                "media_versions": version_manifest,
                "catalogue": {"resource_count": len(catalogue_resources), "relationship_count": len(catalogue_relationships)}}
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise ValueError("Portable lesson manifest exceeds the size limit.")
    destination = Path(destination).expanduser().absolute()
    _reject_linked_path(destination)
    if destination.suffix.casefold() != ".tboard":
        raise ValueError("Portable lesson files must use the .tboard extension.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr("manifest.json", manifest_bytes)
            for name, data in sorted(files.items()):
                archive.writestr(name, data)
        if temporary.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ValueError("Portable lesson archive exceeds the package size limit.")
        os.replace(temporary, destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)


def _read_package(path: Path) -> tuple[BoardModel, dict[str, dict[str, Any]], dict[str, bytes], dict[str, Any] | None]:
    _reject_linked_path(path)
    if not path.is_file() or path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Choose a regular portable lesson file within the archive size limit.")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            if not 2 <= len(infos) <= MAX_ENTRIES:
                raise ValueError("Portable lesson has an invalid file count.")
            names: set[str] = set()
            folded_names: set[str] = set()
            total = 0
            for info in infos:
                name = _safe_member(info.filename)
                if name in names or info.is_dir():
                    raise ValueError("Portable lesson has duplicate or directory entries.")
                if name.casefold() in folded_names:
                    raise ValueError("Portable lesson has case-colliding member paths.")
                names.add(name)
                folded_names.add(name.casefold())
                mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode) or stat.S_ISDIR(mode):
                    raise ValueError("Portable lesson cannot contain symlinks or special files.")
                if info.file_size < 0 or info.file_size > MAX_JSON_FILE_BYTES and not name.startswith("blobs/"):
                    raise ValueError("Portable lesson member exceeds its type-specific limit.")
                if name.startswith("blobs/") and info.file_size > MAX_IMAGE_BYTES:
                    raise ValueError("Portable lesson image exceeds the image size limit.")
                if info.compress_size and info.file_size > max(1024 * 1024, info.compress_size * 1000):
                    raise ValueError("Portable lesson member has a suspicious compression ratio.")
                total += info.file_size
                if total > MAX_UNPACKED_BYTES:
                    raise ValueError("Portable lesson exceeds the total uncompressed size limit.")
            if "manifest.json" not in names:
                raise ValueError("Portable lesson manifest is missing.")
            manifest_bytes = archive.read("manifest.json")
            if len(manifest_bytes) > MAX_MANIFEST_BYTES:
                raise ValueError("Portable lesson manifest exceeds the size limit.")
            manifest = _load_json(manifest_bytes)
            if (not isinstance(manifest, dict) or set(manifest) != {"format", "schema", "files", "media_versions", "catalogue"}
                    or manifest["format"] != FORMAT or type(manifest["schema"]) is not int or manifest["schema"] != SCHEMA):
                raise ValueError("Unsupported portable lesson format.")
            expected_files = manifest["files"]
            if not isinstance(expected_files, dict) or set(expected_files) != names - {"manifest.json"}:
                raise ValueError("Portable lesson manifest file list does not match its archive.")
            files: dict[str, bytes] = {}
            for name, expected in expected_files.items():
                _safe_member(name)
                if (not isinstance(expected, dict) or set(expected) != {"sha256", "size"}
                        or type(expected["size"]) is not int or expected["size"] < 0 or not _is_sha(expected["sha256"])):
                    raise ValueError("Portable lesson file metadata is invalid.")
                with archive.open(name, "r") as stream:
                    data = stream.read(int(expected["size"]) + 1)
                if len(data) != expected["size"] or _sha(data) != expected["sha256"]:
                    raise ValueError("Portable lesson file hash or size check failed.")
                files[name] = data
    except (zipfile.BadZipFile, OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError, OverflowError) as exc:
        raise ValueError("Portable lesson is invalid or damaged.") from exc

    if "state.json" not in files:
        raise ValueError("Portable lesson state is missing.")
    state = _load_json(files["state.json"])
    model = BoardModel.from_state(state)
    refs = _image_refs(state)
    versions_list = manifest["media_versions"]
    if not isinstance(versions_list, list) or len(versions_list) > MAX_VERSIONS:
        raise ValueError("Portable lesson media version list is invalid.")
    versions: dict[str, dict[str, Any]] = {}
    blobs: dict[str, bytes] = {}
    for entry in versions_list:
        if not isinstance(entry, dict) or set(entry) != _VERSION_FIELDS | {"blob_path"}:
            raise ValueError("Portable lesson media version metadata is invalid.")
        version_id, asset_id, digest = entry["version_id"], entry["asset_id"], entry["sha256"]
        if version_id in versions or not _is_uuid(version_id) or not _is_uuid(asset_id) or not _is_sha(digest):
            raise ValueError("Portable lesson media identities are invalid or duplicated.")
        if (not isinstance(entry["title"], str) or not entry["title"].strip() or len(entry["title"]) > 200
                or not isinstance(entry["tags"], list) or len(entry["tags"]) > 100
                or any(not isinstance(tag, str) or len(tag) > 200 for tag in entry["tags"])
                or entry["mime"] not in {"image/png", "image/jpeg", "image/webp"}
                or type(entry["width"]) is not int or type(entry["height"]) is not int
                or type(entry["byte_size"]) is not int or entry["byte_size"] <= 0
                or not isinstance(entry["created_at"], str)
                or entry["origin"] not in {"import", "generated", "web"}
                or not isinstance(entry["source"], dict) or _portable_source(entry["source"]) != entry["source"]
                or (entry["parent_version_id"] is not None and not _is_uuid(entry["parent_version_id"]))):
            raise ValueError("Portable lesson media version fields are invalid.")
        blob_path = _safe_member(entry["blob_path"])
        if blob_path != f"blobs/sha256/{digest[:2]}/{digest[2:]}":
            raise ValueError("Portable lesson blob path does not match its content hash.")
        data = files.get(blob_path)
        if data is None or len(data) != entry["byte_size"] or _sha(data) != digest:
            raise ValueError("Portable lesson image bytes do not match their version metadata.")
        mime, width, height = MediaStore._inspect(data)
        if (mime, width, height) != (entry["mime"], entry["width"], entry["height"]):
            raise ValueError("Portable lesson image metadata does not match decoded bytes.")
        versions[version_id] = entry
        blobs[digest] = data
    for version_id, ref in refs.items():
        record = versions.get(version_id)
        if not record or (record["asset_id"], record["sha256"]) != (ref["asset_id"], ref["sha256"]):
            raise ValueError("Portable lesson is missing an exact referenced image version.")
    for version_id, record in versions.items():
        parent = record["parent_version_id"]
        if parent and (parent not in versions or versions[parent]["asset_id"] != record["asset_id"]):
            raise ValueError("Portable lesson image lineage is incomplete.")
        if record["origin"] not in {"import", "generated", "web"} or not isinstance(record["source"], dict):
            raise ValueError("Portable lesson provenance is invalid.")
    if set(files) - {"state.json", "catalogue.json"} - {entry["blob_path"] for entry in versions.values()}:
        raise ValueError("Portable lesson contains undeclared content.")
    catalogue_data = None
    if "catalogue.json" in files:
        catalogue_data = _load_json(files["catalogue.json"])
        if not isinstance(catalogue_data, dict) or set(catalogue_data) != {"resources", "relationships"}:
            raise ValueError("Portable lesson catalogue metadata is invalid.")
        if (not isinstance(catalogue_data["resources"], list) or len(catalogue_data["resources"]) > MAX_CATALOGUE_DEPENDENCIES
                or not isinstance(catalogue_data["relationships"], list) or len(catalogue_data["relationships"]) > 4096):
            raise ValueError("Portable lesson catalogue dependency count is invalid.")
    counts = manifest["catalogue"]
    if (not isinstance(counts, dict) or set(counts) != {"resource_count", "relationship_count"}
            or type(counts["resource_count"]) is not int or type(counts["relationship_count"]) is not int
            or counts["resource_count"] != len(catalogue_data["resources"] if catalogue_data else [])
            or counts["relationship_count"] != len(catalogue_data["relationships"] if catalogue_data else [])):
        raise ValueError("Portable lesson catalogue counts do not match its dependencies.")
    if catalogue_data:
        resource_versions: set[tuple[str, str]] = set()
        resource_ids: dict[str, str] = {}
        for resource in catalogue_data["resources"]:
            required = {"resource_id", "version_id", "resource_type", "title", "description", "tags", "aliases",
                        "metadata", "provenance", "content_hash", "mime", "byte_size", "availability", "review_state"}
            if not isinstance(resource, dict) or set(resource) - {"teacher_metadata"} != required:
                raise ValueError("Portable lesson catalogue resource fields are invalid.")
            if "teacher_metadata" in resource:
                correction = resource["teacher_metadata"]
                if (not isinstance(correction, dict)
                        or set(correction) != {"title", "description", "tags", "topics", "year_levels"}
                        or not isinstance(correction["title"], str) or not correction["title"].strip()
                        or len(correction["title"]) > 200
                        or not isinstance(correction["description"], str) or len(correction["description"]) > 4000
                        or any(not isinstance(correction[name], list) or len(correction[name]) > 100
                               or any(not isinstance(value, str) or len(value) > 200 for value in correction[name])
                               for name in ("tags", "topics", "year_levels"))):
                    raise ValueError("Portable lesson teacher metadata is invalid.")
            if (not _is_uuid(resource["resource_id"]) or not _is_uuid(resource["version_id"])
                    or resource["resource_type"] not in {"image", "dataset", "chart", "page", "video", "audio", "document", "attachment"}
                    or not isinstance(resource["title"], str) or not resource["title"].strip() or len(resource["title"]) > 200
                    or not isinstance(resource["description"], str) or len(resource["description"]) > 4000
                    or not isinstance(resource["tags"], list) or not isinstance(resource["aliases"], list)
                    or len(resource["tags"]) > 100 or len(resource["aliases"]) > 100
                    or any(not isinstance(value, str) or len(value) > 200 for value in resource["tags"] + resource["aliases"])
                    or not isinstance(resource["metadata"], dict) or not isinstance(resource["provenance"], dict)
                    or len(canonical_json(resource["metadata"])) > 65536 or len(canonical_json(resource["provenance"])) > 65536
                    or _private_safe(resource) != resource
                    or resource["availability"] not in {"metadata_only", "cached", "preview_ready", "offline", "unavailable"}
                    or resource["review_state"] not in {"draft", "approved", "rejected", "excluded"}
                    or (resource["content_hash"] is not None and not _is_sha(resource["content_hash"]))
                    or (resource["byte_size"] is not None and (type(resource["byte_size"]) is not int or resource["byte_size"] < 0))):
                raise ValueError("Portable lesson catalogue resource metadata is invalid.")
            key = (resource["resource_id"], resource["version_id"])
            if key in resource_versions or (resource["resource_id"] in resource_ids and resource_ids[resource["resource_id"]] != resource["resource_type"]):
                raise ValueError("Portable lesson catalogue identities conflict.")
            resource_versions.add(key); resource_ids[resource["resource_id"]] = resource["resource_type"]
            if resource["resource_type"] == "image":
                version = versions.get(resource["version_id"])
                if not version or (version["asset_id"], version["sha256"]) != (resource["resource_id"], resource["content_hash"]):
                    raise ValueError("Portable lesson catalogue image dependency is missing or mismatched.")
        for edge in catalogue_data["relationships"]:
            required = {"source_resource_id", "source_version_id", "relation", "target_resource_id", "target_version_id", "metadata"}
            if (not isinstance(edge, dict) or set(edge) != required
                    or (edge["source_resource_id"], edge["source_version_id"]) not in resource_versions
                    or (edge["target_resource_id"], edge["target_version_id"]) not in resource_versions
                    or edge["relation"] not in {"derived_from", "rendered_from", "thumbnail_of", "transcript_of", "segment_of", "uses", "part_of", "supersedes"}
                    or not isinstance(edge["metadata"], dict) or len(canonical_json(edge["metadata"])) > 65536
                    or _private_safe(edge) != edge):
                raise ValueError("Portable lesson catalogue relationship is invalid or has missing endpoints.")
    allowed_versions = set(refs)
    if catalogue_data:
        allowed_versions.update(item["version_id"] for item in catalogue_data["resources"] if item["resource_type"] == "image")
    pending_versions = list(allowed_versions)
    while pending_versions:
        version = versions.get(pending_versions.pop())
        if version and version["parent_version_id"] and version["parent_version_id"] not in allowed_versions:
            allowed_versions.add(version["parent_version_id"]); pending_versions.append(version["parent_version_id"])
    if set(versions) != allowed_versions:
        raise ValueError("Portable lesson contains image versions outside its exact dependency closure.")
    # Cross-check ancestry closure and ensure no cycles/deep chains.
    for version_id, record in versions.items():
        seen, parent, depth = {version_id}, record["parent_version_id"], 0
        while parent:
            depth += 1
            if parent in seen or depth > 100 or parent not in versions:
                raise ValueError("Portable lesson image lineage is cyclic or excessive.")
            seen.add(parent)
            parent = versions[parent]["parent_version_id"]
    return model, versions, blobs, catalogue_data


def _is_uuid(value: Any) -> bool:
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value
    except ValueError:
        return False


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def import_lesson(package_path: Path | str, destination: Path | str) -> BoardStore:
    """Validate a complete package, then atomically create a fresh local lesson folder."""
    model, versions, blobs, catalogue_data = _read_package(Path(package_path).expanduser().absolute())
    destination = Path(destination).expanduser().absolute()
    _reject_linked_path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Import destination must be a new local folder.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.import-", dir=destination.parent))
    try:
        media = MediaStore(staging / "media")
        for digest, data in blobs.items():
            blob = media.blob_path(digest)
            blob.parent.mkdir(parents=True, exist_ok=True)
            blob.write_bytes(data)
        pending = dict(versions)
        while pending:
            progressed = False
            for version_id, record in list(pending.items()):
                if record["parent_version_id"] and record["parent_version_id"] in pending:
                    continue
                payload = {key: record[key] for key in _VERSION_FIELDS}
                payload["tags"] = payload.pop("tags")
                media.apply_remote_event({"event_id": str(uuid.uuid4()), "kind": "version", "payload": payload})
                del pending[version_id]
                progressed = True
            if not progressed:
                raise ValueError("Portable lesson image lineage cannot be imported.")
        if catalogue_data and catalogue_data["resources"]:
            from board_resources import ResourceCatalogue
            catalogue = ResourceCatalogue(staging / "catalogue", media_store=media)
            for item in catalogue_data["resources"]:
                fields = {key: item[key] for key in ("resource_type", "title", "metadata", "description", "aliases", "tags", "provenance", "resource_id", "version_id", "content_hash", "mime", "byte_size", "availability") if key in item}
                fields["state"] = item.get("review_state", "draft")
                if fields.get("resource_type") == "image":
                    fields["image_ref"] = {"asset_id": item["resource_id"], "version_id": item["version_id"], "sha256": item["content_hash"]}
                catalogue.save_resource(**fields)
                if item.get("teacher_metadata"):
                    catalogue.update_metadata(item["version_id"], **item["teacher_metadata"])
            for edge in catalogue_data["relationships"]:
                catalogue.add_relationship(edge["source_version_id"], edge["relation"], edge["target_version_id"], edge.get("metadata"))
        store = BoardStore(staging)
        store.save(model)
        os.replace(staging, destination)
        return BoardStore(destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    from reportlab.pdfbase.pdfmetrics import stringWidth
    words = str(text).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and stringWidth(candidate, font, size) > width:
            lines.append(current)
            current = word
            if stringWidth(current, font, size) > width:
                piece = ""
                for character in current:
                    if piece and stringWidth(piece + character, font, size) > width:
                        lines.append(piece)
                        piece = character
                    else:
                        piece += character
                current = piece
        else:
            current = candidate
    if current:
        lines.append(current)
    if any(stringWidth(line, font, size) > width for line in lines):
        raise ValueError("PDF text cannot fit the available width at its current font size.")
    return lines or [""]


def _image_credit(record: dict[str, Any]) -> str:
    source = record.get("source") or {}
    parts = [record.get("title", "Image")]
    for key, label in (("creator", "creator"), ("licence", "licence"), ("attribution", "credit"), ("url", "source")):
        value = source.get(key)
        if value and str(value) not in parts:
            parts.append(f"{label}: {value}")
    if len(parts) == 1:
        parts.append("source details not recorded")
    return " | ".join(parts)


def _media_provenance(media_store: MediaStore, version_id: str) -> dict[str, Any] | None:
    lineage = []
    seen = set()
    current = version_id
    while current:
        if current in seen or len(seen) >= 100:
            raise ValueError("PDF image lineage is cyclic or excessive.")
        seen.add(current)
        record = media_store.get_version(current)
        if record is None:
            raise ValueError("PDF image version is missing from the local media library.")
        lineage.append(record)
        current = record["parent_version_id"]
    merged_source: dict[str, str] = {}
    for record in reversed(lineage):
        merged_source.update(_portable_source(record.get("source", {})))
    licence = merged_source.get("licence", "").casefold()
    if "cc by" in licence and not (merged_source.get("attribution") or merged_source.get("creator")):
        raise ValueError("A CC BY image is missing required creator or attribution details.")
    selected = lineage[0]
    return {"title": selected.get("version_title") or selected.get("title") or "Image", "source": merged_source}


def export_pdf(model_or_state: Any, destination: Path | str, *, image_resolver: Callable[[dict[str, str]], bytes],
               media_store: MediaStore | None = None, catalogue: Any = None) -> Path:
    """Create a vector PDF rendering of the validated Board model and local images."""
    model = _as_model(model_or_state)
    state = model.export_state()
    if not callable(image_resolver):
        raise ValueError("Provide a local image resolver for Board image references.")
    try:
        import reportlab
        from reportlab.lib.colors import HexColor
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError("ReportLab is required for local Board PDF export.") from exc
    destination = Path(destination).expanduser().absolute()
    _reject_linked_path(destination)
    if destination.suffix.casefold() != ".pdf":
        raise ValueError("PDF export destination must use the .pdf extension.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    scale = 0.5  # Board logical units map to half-point PDF units.
    try:
        regular_font, bold_font = "Helvetica", "Helvetica-Bold"
        font_candidates = ((Path("C:/Windows/Fonts/arial.ttf"), "BoardArial"),
                           (Path("C:/Windows/Fonts/segoeui.ttf"), "BoardSegoe"),
                           (Path(reportlab.__file__).parent / "fonts" / "Vera.ttf", "BoardVera"))
        for font_path, font_name in font_candidates:
            if font_path.is_file():
                bold_path = font_path.with_name(font_path.stem + "bd" + font_path.suffix)
                if font_name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
                bold_name = font_name + "Bold"
                if bold_path.is_file() and bold_name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(bold_name, str(bold_path)))
                regular_font = font_name
                bold_font = bold_name if bold_path.is_file() else font_name
                break
        pdf = canvas.Canvas(str(temporary), pageCompression=1)
        pdf.setTitle(state["document"]["title"])
        total_pages = len(state["document"]["pages"])
        for page_number, page in enumerate(state["document"]["pages"], start=1):
            image_records: dict[str, dict[str, Any]] = {}
            for obj in page["objects"]:
                if obj["type"] != "image":
                    continue
                ref = obj["image_ref"]
                data = image_resolver(copy.deepcopy(ref))
                if not isinstance(data, bytes) or not 1 <= len(data) <= MAX_IMAGE_BYTES or _sha(data) != ref["sha256"]:
                    raise ValueError("A PDF image is unavailable, damaged, or exceeds 32 MiB.")
                MediaStore._inspect(data)
                record = _media_provenance(media_store, ref["version_id"]) if media_store else None
                if record is None and catalogue is not None:
                    record = catalogue.resolve(ref["version_id"], include_excluded=True)
                    if record:
                        record = {"title": record["title"], "source": record.get("provenance", {})}
                if record is None:
                    record = {"title": "Image", "source": {}}
                record = copy.deepcopy(record)
                record["source"] = _portable_source(record.get("source", {}))
                record["_data"] = data
                image_records[ref["version_id"]] = record
            credits = [_image_credit(record) for record in image_records.values()]
            credit_lines = []
            for credit in credits:
                credit_lines.extend(_wrap(credit, regular_font, 8, page["width"] * scale - 24))
            footer_height = max(25, 12 + len(credit_lines) * 10)
            header_height = 30
            page_width, page_height = page["width"] * scale, page["height"] * scale + header_height + footer_height
            pdf.setPageSize((page_width, page_height))
            body_bottom = footer_height
            body_top = footer_height + page["height"] * scale
            pdf.setFillColor(HexColor("#F8FAFC")); pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)
            pdf.setFillColor(HexColor("#0F172A")); pdf.setFont(bold_font, 14)
            pdf.drawString(12, body_top + 11, page["title"] or state["document"]["title"])
            pdf.setFillColor(HexColor("#475569")); pdf.setFont(regular_font, 8)
            pdf.drawRightString(page_width - 12, body_top + 15, f"Page {page_number} of {total_pages}")
            pdf.setStrokeColor(HexColor("#CBD5E1")); pdf.setLineWidth(0.7)
            pdf.rect(0, body_bottom, page_width, page["height"] * scale, fill=0, stroke=1)
            for obj in page["objects"]:
                x, y, w, h = obj["x"] * scale, obj["y"] * scale, obj["width"] * scale, obj["height"] * scale
                cx, cy = x + w / 2, body_top - y - h / 2
                pdf.saveState(); pdf.translate(cx, cy); pdf.rotate(-obj["rotation"])
                if obj["type"] == "text":
                    pdf.setFillColor(HexColor(obj["colour"]))
                    font = regular_font
                    font_size = max(2, obj["font_size"] * scale)
                    align = obj["align"]
                    lines = _wrap(obj["text"], font, font_size, max(2, w - 8))
                    line_y = h / 2 - font_size
                    pdf.setFont(font, font_size)
                    line_limit = int(max(0, h - font_size) / max(1, font_size * 1.2)) + 1
                    if len(lines) > line_limit:
                        raise ValueError("PDF export cannot fit all text in a Board object. Enlarge the text box or reduce its font size.")
                    for line in lines:
                        line_width = pdf.stringWidth(line, font, font_size)
                        tx = -w / 2 + 4 if align == "left" else (w / 2 - line_width - 4 if align == "right" else -line_width / 2)
                        pdf.drawString(tx, line_y, line); line_y -= font_size * 1.2
                elif obj["type"] == "image":
                    ref = obj["image_ref"]; data = image_records[ref["version_id"]]["_data"]
                    pdf.drawImage(ImageReader(io.BytesIO(data)), -w/2, -h/2, width=w, height=h, preserveAspectRatio=False, mask="auto")
                elif obj["type"] == "shape":
                    pdf.setFillColor(HexColor(obj["fill"])); pdf.setStrokeColor(HexColor(obj["stroke"])); pdf.setLineWidth(obj["stroke_width"] * scale)
                    if obj["shape"] == "ellipse": pdf.ellipse(-w/2, -h/2, w/2, h/2, fill=1, stroke=1)
                    else: pdf.rect(-w/2, -h/2, w, h, fill=1, stroke=1)
                elif obj["type"] == "arrow":
                    pdf.setStrokeColor(HexColor(obj["colour"])); pdf.setFillColor(HexColor(obj["colour"])); pdf.setLineWidth(obj["stroke_width"] * scale)
                    sx, sy = (obj["start"][0]-obj["width"]/2)*scale, (obj["height"]/2-obj["start"][1])*scale
                    ex, ey = (obj["end"][0]-obj["width"]/2)*scale, (obj["height"]/2-obj["end"][1])*scale
                    pdf.line(sx, sy, ex, ey)
                    angle = math.atan2(ey-sy, ex-sx); head = max(5, obj["stroke_width"]*2)*scale
                    left = (ex-head*math.cos(angle-0.5), ey-head*math.sin(angle-0.5))
                    right = (ex-head*math.cos(angle+0.5), ey-head*math.sin(angle+0.5))
                    pdf.line(ex, ey, *left); pdf.line(ex, ey, *right)
                elif obj["type"] == "ink":
                    pdf.setStrokeColor(HexColor(obj["colour"])); pdf.setLineWidth(obj["stroke_width"] * scale); pdf.setLineCap(1); pdf.setLineJoin(1)
                    points = obj["points"]
                    if len(points) == 1:
                        px, py = (points[0][0]-obj["width"]/2)*scale, (obj["height"]/2-points[0][1])*scale
                        pdf.circle(px, py, max(1, obj["stroke_width"]*scale/2), fill=1, stroke=0)
                    else:
                        path = pdf.beginPath(); path.moveTo((points[0][0]-obj["width"]/2)*scale, (obj["height"]/2-points[0][1])*scale)
                        for px, py in points[1:]: path.lineTo((px-obj["width"]/2)*scale,(obj["height"]/2-py)*scale)
                        pdf.drawPath(path, stroke=1, fill=0)
                pdf.restoreState()
            pdf.setFillColor(HexColor("#334155")); pdf.setFont(bold_font, 8)
            pdf.drawString(12, footer_height-10, "Credits and provenance")
            pdf.setFont(regular_font, 8)
            for index, line in enumerate(credit_lines):
                pdf.drawString(12, footer_height - 21 - index*10, line)
            pdf.showPage()
        pdf.save()
        if temporary.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ValueError("PDF exceeds the local export size limit.")
        os.replace(temporary, destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)


__all__ = ["export_lesson", "import_lesson", "export_pdf"]
