"""Local, versioned image library for the classroom companion.

Media has its own SQLite database and immutable content-addressed blobs. The
existing text-only History database is deliberately not migrated or opened.
Prompts are stored in a local-only table and are never included in sync events.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import threading
import unicodedata
import uuid
import warnings
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from PIL import Image, UnidentifiedImageError


_SCHEMA_VERSION = 2
_MAX_IMAGE_BYTES = 20 * 1024 * 1024
_MAX_IMAGE_PIXELS = 25_000_000
_MAX_TITLE_LENGTH = 200
_MAX_TAGS = 100
_MAX_LIST_LIMIT = 500
_MIME_BY_FORMAT = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
_SOURCE_KEYS = {"url", "creator", "licence", "attribution", "provider", "model"}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_BLOB_WRITE_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _uuid(value: str | None, name: str) -> str:
    result = str(uuid.uuid4()) if value is None else str(value)
    try:
        return str(uuid.UUID(result))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"{name} must be a UUID") from exc


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _source(value: dict[str, Any] | None) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("source must be a mapping")
    # Prompts, transcripts, and unrecognised fields are deliberately excluded.
    return {key: str(value[key]) for key in sorted(_SOURCE_KEYS) if key in value and value[key] is not None}


class MediaStore:
    """Store imported images, immutable versions, jobs, and sync metadata locally."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "media.sqlite3"
        self.blobs = self.root / "blobs" / "sha256"
        self.blobs.mkdir(parents=True, exist_ok=True)
        self._initialise()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        try:
            yield connection
        finally:
            connection.close()

    def _initialise(self) -> None:
        with self._connect() as db:
            version = int(db.execute("PRAGMA user_version").fetchone()[0])
            if version > _SCHEMA_VERSION:
                raise RuntimeError(f"Media database schema {version} is newer than supported {_SCHEMA_VERSION}")
            if version == _SCHEMA_VERSION:
                return
            db.execute("BEGIN IMMEDIATE")
            try:
                schema = """
                    CREATE TABLE IF NOT EXISTS asset (
                        asset_id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        tags_json TEXT NOT NULL DEFAULT '[]',
                        canonical_version_id TEXT,
                        revision INTEGER NOT NULL DEFAULT 0,
                        remote_revision INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS asset_version (
                        version_id TEXT PRIMARY KEY,
                        asset_id TEXT NOT NULL REFERENCES asset(asset_id),
                        version_title TEXT NOT NULL,
                        version_tags_json TEXT NOT NULL,
                        sha256 TEXT NOT NULL,
                        mime TEXT NOT NULL,
                        width INTEGER NOT NULL,
                        height INTEGER NOT NULL,
                        byte_size INTEGER NOT NULL,
                        parent_version_id TEXT,
                        source_json TEXT NOT NULL DEFAULT '{}',
                        origin TEXT NOT NULL CHECK (origin IN ('import','generated','web')),
                        created_at TEXT NOT NULL,
                        UNIQUE(asset_id, version_id)
                    );
                    CREATE INDEX IF NOT EXISTS asset_version_asset_created
                        ON asset_version(asset_id, created_at, version_id);
                    CREATE INDEX IF NOT EXISTS asset_version_sha256 ON asset_version(sha256);
                    CREATE TABLE IF NOT EXISTS local_prompt (
                        version_id TEXT PRIMARY KEY REFERENCES asset_version(version_id),
                        prompt TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS operation (
                        operation_id TEXT PRIMARY KEY,
                        version_id TEXT NOT NULL REFERENCES asset_version(version_id)
                    );
                    CREATE TABLE IF NOT EXISTS media_job (
                        job_id TEXT PRIMARY KEY,
                        kind TEXT NOT NULL,
                        request_json TEXT NOT NULL,
                        phase TEXT NOT NULL DEFAULT 'queued',
                        fields_json TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS sync_outbox (
                        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id TEXT UNIQUE NOT NULL,
                        kind TEXT NOT NULL CHECK (kind IN ('version','canonical')),
                        payload_json TEXT NOT NULL,
                        synced INTEGER NOT NULL DEFAULT 0 CHECK (synced IN (0,1)),
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS applied_event (
                        event_id TEXT PRIMARY KEY,
                        kind TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS sync_conflict (
                        event_id TEXT PRIMARY KEY,
                        asset_id TEXT NOT NULL,
                        local_version_id TEXT,
                        remote_version_id TEXT,
                        expected_revision INTEGER NOT NULL,
                        received_revision INTEGER NOT NULL,
                        server_revision INTEGER,
                        server_canonical_version_id TEXT,
                        reason TEXT NOT NULL DEFAULT 'canonical_revision_conflict',
                        resolved_at TEXT,
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS sync_cursor (
                        name TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                """
                for statement in schema.split(";"):
                    if statement.strip():
                        db.execute(statement)
                # Add fields introduced in schema v2 without touching text History.
                def add_columns(table: str, definitions: dict[str, str]) -> None:
                    present = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
                    for name, declaration in definitions.items():
                        if name not in present:
                            db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")

                add_columns("asset_version", {"version_title": "TEXT NOT NULL DEFAULT ''",
                                               "version_tags_json": "TEXT NOT NULL DEFAULT '[]'"})
                add_columns("sync_outbox", {"sequence": "INTEGER"})
                add_columns("sync_conflict", {"server_revision": "INTEGER",
                                               "server_canonical_version_id": "TEXT",
                                               "reason": "TEXT NOT NULL DEFAULT 'canonical_revision_conflict'",
                                               "resolved_at": "TEXT"})
                db.execute("UPDATE asset_version SET version_title=(SELECT title FROM asset WHERE asset.asset_id=asset_version.asset_id) WHERE version_title='' ")
                db.execute("UPDATE asset_version SET version_tags_json=(SELECT tags_json FROM asset WHERE asset.asset_id=asset_version.asset_id) WHERE version_tags_json='[]'")
                db.execute("UPDATE sync_outbox SET sequence=rowid WHERE sequence IS NULL")
                db.execute("CREATE UNIQUE INDEX IF NOT EXISTS sync_outbox_sequence ON sync_outbox(sequence)")
                db.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise

    @staticmethod
    def _tags(tags: list[str] | tuple[str, ...] | None) -> list[str]:
        if tags is None:
            return []
        if isinstance(tags, (str, bytes)):
            raise ValueError("tags must be a sequence of strings")
        result: list[str] = []
        for tag in tags:
            cleaned = str(tag).strip()
            if cleaned and cleaned not in result:
                result.append(cleaned)
        if len(result) > _MAX_TAGS:
            raise ValueError(f"at most {_MAX_TAGS} tags are allowed")
        return result

    @staticmethod
    def _inspect(data: bytes) -> tuple[str, int, int]:
        if not data:
            raise ValueError("image data is empty")
        if len(data) > _MAX_IMAGE_BYTES:
            raise ValueError("image exceeds the 20 MiB limit")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                import io
                with Image.open(io.BytesIO(data)) as image:
                    image_format = image.format
                    width, height = image.size
                    if image_format not in _MIME_BY_FORMAT:
                        raise ValueError("only PNG, JPEG, and WebP images are supported")
                    if width <= 0 or height <= 0 or width * height > _MAX_IMAGE_PIXELS:
                        raise ValueError("image exceeds the 25 megapixel limit")
                    image.verify()
                # verify() checks structure; load() also catches truncated/corrupt payloads.
                with Image.open(io.BytesIO(data)) as image:
                    if image.format != image_format or image.size != (width, height):
                        raise ValueError("image metadata changed while validating")
                    image.load()
            return _MIME_BY_FORMAT[image_format], width, height
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
                Image.DecompressionBombWarning) as exc:
            raise ValueError("file is not a safe, complete PNG, JPEG, or WebP image") from exc

    def import_image(
        self,
        path: Path,
        title: str,
        tags: list[str] | tuple[str, ...] | None = None,
        asset_id: str | None = None,
        parent_version_id: str | None = None,
        source: dict[str, Any] | None = None,
        prompt: str = "",
        operation_id: str | None = None,
    ) -> dict[str, Any]:
        image_path = Path(path).expanduser()
        if image_path.stat().st_size > _MAX_IMAGE_BYTES:
            raise ValueError("image exceeds the 20 MiB limit")
        data = image_path.read_bytes()
        return self.import_bytes(data, title, tags, asset_id, parent_version_id, source, prompt, operation_id)

    def import_bytes(
        self,
        data: bytes,
        title: str,
        tags: list[str] | tuple[str, ...] | None = None,
        asset_id: str | None = None,
        parent_version_id: str | None = None,
        source: dict[str, Any] | None = None,
        prompt: str = "",
        operation_id: str | None = None,
        origin: str = "import",
    ) -> dict[str, Any]:
        if origin not in {"import", "generated", "web"}:
            raise ValueError("origin must be import, generated, or web")
        title = str(title).strip()
        if not title:
            raise ValueError("title is required")
        title = title[:_MAX_TITLE_LENGTH]
        tags_value = self._tags(tags)
        source_value = _source(source)
        mime, width, height = self._inspect(data)
        sha256 = hashlib.sha256(data).hexdigest()
        if operation_id is not None:
            operation_id = _uuid(operation_id, "operation_id")
        proposed_asset_id = _uuid(asset_id, "asset_id") if asset_id is not None else None
        version_id = str(uuid.uuid4())
        asset_id_value = proposed_asset_id or str(uuid.uuid4())
        created_at = _now()
        blob = self.blob_path(sha256)
        with _BLOB_WRITE_LOCK:
            blob.parent.mkdir(parents=True, exist_ok=True)
            if not blob.exists():
                fd, temp_name = tempfile.mkstemp(prefix=".incoming-", dir=blob.parent)
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                    if hashlib.sha256(Path(temp_name).read_bytes()).hexdigest() != sha256:
                        raise OSError("image hash changed while writing the managed blob")
                    os.replace(temp_name, blob)
                finally:
                    if os.path.exists(temp_name):
                        os.unlink(temp_name)
            elif hashlib.sha256(blob.read_bytes()).hexdigest() != sha256:
                raise OSError("managed blob does not match its content address")

        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if operation_id:
                    prior = db.execute("SELECT version_id FROM operation WHERE operation_id=?", (operation_id,)).fetchone()
                    if prior:
                        db.execute("COMMIT")
                        existing = self.get_version(prior["version_id"])
                        assert existing is not None
                        return existing
                asset = db.execute("SELECT * FROM asset WHERE asset_id=?", (asset_id_value,)).fetchone()
                if asset is None:
                    db.execute("INSERT INTO asset VALUES (?, ?, ?, NULL, 0, 0, ?, ?)",
                               (asset_id_value, title, _json(tags_value), created_at, created_at))
                elif proposed_asset_id is None:
                    raise RuntimeError("generated asset UUID unexpectedly exists")
                else:
                    if asset["canonical_version_id"] is None:
                        db.execute("UPDATE asset SET title=?, tags_json=?, updated_at=? WHERE asset_id=?",
                                   (title, _json(tags_value), created_at, asset_id_value))
                if parent_version_id:
                    parent = db.execute("SELECT asset_id FROM asset_version WHERE version_id=?", (parent_version_id,)).fetchone()
                    if not parent or parent["asset_id"] != asset_id_value:
                        raise ValueError("parent_version_id must name a version of this asset")
                db.execute("""INSERT INTO asset_version
                    (version_id,asset_id,version_title,version_tags_json,sha256,mime,width,height,byte_size,parent_version_id,source_json,origin,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (version_id, asset_id_value, title, _json(tags_value), sha256, mime, width, height, len(data), parent_version_id,
                     _json(source_value), origin, created_at))
                db.execute("INSERT INTO local_prompt(version_id,prompt) VALUES (?,?)", (version_id, str(prompt)))
                if operation_id:
                    db.execute("INSERT INTO operation VALUES (?,?)", (operation_id, version_id))
                record = self._version_record(db, version_id)
                event_id = str(uuid.uuid4())
                payload = self._version_payload(record)
                sequence = int(db.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM sync_outbox").fetchone()[0])
                db.execute("INSERT INTO sync_outbox (sequence,event_id,kind,payload_json,synced,created_at) VALUES (?,?,?,?,0,?)",
                           (sequence, event_id, "version", _json(payload), created_at))
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
        return record

    def add_generated(self, data: bytes, title: str, asset_id: str | None = None,
                      parent_version_id: str | None = None, prompt: str = "",
                      source: dict[str, Any] | None = None, operation_id: str | None = None) -> dict[str, Any]:
        return self.import_bytes(data, title, asset_id=asset_id, parent_version_id=parent_version_id,
                                 prompt=prompt, source=source, operation_id=operation_id, origin="generated")

    def blob_path(self, sha256: str) -> Path:
        if not _SHA256_RE.fullmatch(str(sha256)):
            raise ValueError("sha256 must be a lowercase hexadecimal SHA-256 digest")
        return self.blobs / sha256[:2] / sha256[2:]

    @staticmethod
    def _version_payload(record: dict[str, Any]) -> dict[str, Any]:
        # This allowlist is the sync privacy boundary: no prompt, job request, or transcript.
        keys = ("asset_id", "version_id", "version_title", "version_tags", "sha256", "mime", "width", "height",
                "byte_size", "parent_version_id", "source", "created_at", "origin")
        payload = {key: record[key] for key in keys}
        payload["title"] = payload.pop("version_title")
        payload["tags"] = payload.pop("version_tags")
        return payload

    @staticmethod
    def _version_record(db: sqlite3.Connection, version_id: str) -> dict[str, Any] | None:
        row = db.execute("""SELECT v.*,a.title AS asset_title,a.tags_json AS asset_tags_json,a.canonical_version_id,a.revision
            FROM asset_version v JOIN asset a USING(asset_id) WHERE v.version_id=?""", (version_id,)).fetchone()
        if row is None:
            return None
        return {"asset_id": row["asset_id"], "version_id": row["version_id"], "title": row["asset_title"],
                "tags": json.loads(row["asset_tags_json"]), "version_title": row["version_title"],
                "version_tags": json.loads(row["version_tags_json"]), "sha256": row["sha256"], "mime": row["mime"],
                "width": row["width"], "height": row["height"], "byte_size": row["byte_size"],
                "parent_version_id": row["parent_version_id"], "source": json.loads(row["source_json"]),
                "canonical_version_id": row["canonical_version_id"], "revision": row["revision"],
                "created_at": row["created_at"], "origin": row["origin"]}

    def get_version(self, version_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            return self._version_record(db, version_id)

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM asset WHERE asset_id=?", (asset_id,)).fetchone()
            if row is None:
                return None
            record = dict(row)
            record["tags"] = json.loads(record.pop("tags_json"))
            return record

    def list_assets(self, query: str = "", limit: int = 100) -> list[dict[str, Any]]:
        limit = min(_MAX_LIST_LIMIT, max(0, int(limit)))
        if not limit:
            return []
        with self._connect() as db:
            rows = db.execute("""SELECT a.*,v.version_id,v.sha256,v.mime,v.width,v.height,v.byte_size,
                v.parent_version_id,v.source_json,v.origin,v.created_at AS version_created_at
                FROM asset a LEFT JOIN asset_version v ON v.version_id=COALESCE(a.canonical_version_id,
                  (SELECT version_id FROM asset_version vv WHERE vv.asset_id=a.asset_id
                   ORDER BY vv.created_at DESC,vv.version_id DESC LIMIT 1))
                ORDER BY a.updated_at DESC,a.asset_id""").fetchall()
        needle = unicodedata.normalize("NFKC", str(query)).casefold()
        result = []
        for row in rows:
            tags = json.loads(row["tags_json"])
            if needle and needle not in unicodedata.normalize("NFKC", row["title"] + " " + " ".join(tags)).casefold():
                continue
            result.append({"asset_id": row["asset_id"], "version_id": row["version_id"], "title": row["title"],
                "tags": tags, "sha256": row["sha256"], "mime": row["mime"], "width": row["width"],
                "height": row["height"], "byte_size": row["byte_size"], "parent_version_id": row["parent_version_id"],
                "source": json.loads(row["source_json"] or "{}"), "canonical_version_id": row["canonical_version_id"],
                "revision": row["revision"], "created_at": row["version_created_at"], "origin": row["origin"]})
            if len(result) >= limit:
                break
        return result

    def list_versions(self, asset_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT version_id FROM asset_version WHERE asset_id=? ORDER BY created_at,version_id", (asset_id,)).fetchall()
            return [self._version_record(db, row["version_id"]) for row in rows]  # type: ignore[misc]

    def set_canonical(self, asset_id: str, version_id: str, expected_revision: int | None = None,
                      canonical_title: str | None = None) -> dict[str, Any]:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                asset = db.execute("SELECT * FROM asset WHERE asset_id=?", (asset_id,)).fetchone()
                version = db.execute("SELECT asset_id FROM asset_version WHERE version_id=?", (version_id,)).fetchone()
                if asset is None or version is None or version["asset_id"] != asset_id:
                    raise ValueError("asset and version must identify an existing version of the same asset")
                if expected_revision is not None and int(asset["revision"]) != int(expected_revision):
                    raise ValueError(f"canonical revision conflict: expected {expected_revision}, found {asset['revision']}")
                if canonical_title is not None:
                    canonical_title = str(canonical_title).strip()
                    if not canonical_title:
                        raise ValueError("canonical_title cannot be blank")
                    canonical_title = canonical_title[:_MAX_TITLE_LENGTH]
                revision = int(asset["revision"]) + 1
                db.execute("UPDATE asset SET canonical_version_id=?,title=COALESCE(?,title),revision=?,updated_at=? WHERE asset_id=?",
                           (version_id, canonical_title, revision, _now(), asset_id))
                event_id = str(uuid.uuid4())
                expected_remote_revision = int(asset["remote_revision"])
                pending_canonical = db.execute(
                    "SELECT payload_json FROM sync_outbox WHERE kind='canonical' AND synced=0 ORDER BY sequence DESC"
                ).fetchall()
                for pending in pending_canonical:
                    queued = json.loads(pending["payload_json"])
                    if queued["asset_id"] == asset_id:
                        expected_remote_revision = int(queued["revision"])
                        break
                payload = {"asset_id": asset_id, "version_id": version_id,
                           "expected_revision": expected_remote_revision,
                           "revision": expected_remote_revision + 1}
                if canonical_title is not None:
                    payload["canonical_title"] = canonical_title
                sequence = int(db.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM sync_outbox").fetchone()[0])
                db.execute("INSERT INTO sync_outbox (sequence,event_id,kind,payload_json,synced,created_at) VALUES (?,?,?,?,0,?)",
                           (sequence, event_id, "canonical", _json(payload), _now()))
                result = self._version_record(db, version_id)
                db.execute("COMMIT")
                assert result is not None
                return result
            except Exception:
                db.execute("ROLLBACK")
                raise

    def create_job(self, kind: str, request: Any, job_id: str | None = None) -> dict[str, Any]:
        job_id = _uuid(job_id, "job_id")
        timestamp = _now()
        request_json = _json(request)
        with self._connect() as db:
            existing = db.execute("SELECT * FROM media_job WHERE job_id=?", (job_id,)).fetchone()
            if existing:
                if existing["kind"] != str(kind) or existing["request_json"] != request_json:
                    raise ValueError("job_id already belongs to a different request")
                return self._job(existing)
            db.execute("INSERT INTO media_job VALUES (?,?,?,'queued','{}',?,?)",
                       (job_id, str(kind), request_json, timestamp, timestamp))
            return self.get_job(job_id)  # type: ignore[return-value]

    @staticmethod
    def _job(row: sqlite3.Row) -> dict[str, Any]:
        fields = json.loads(row["fields_json"])
        return {"job_id": row["job_id"], "kind": row["kind"], "request": json.loads(row["request_json"]),
                "phase": row["phase"], "fields": fields, **fields,
                "created_at": row["created_at"], "updated_at": row["updated_at"]}

    def update_job(self, job_id: str, phase: str, **fields: Any) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM media_job WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            current = json.loads(row["fields_json"])
            current.update(fields)
            db.execute("UPDATE media_job SET phase=?,fields_json=?,updated_at=? WHERE job_id=?",
                       (str(phase), _json(current), _now(), job_id))
        return self.get_job(job_id)  # type: ignore[return-value]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM media_job WHERE job_id=?", (job_id,)).fetchone()
            return self._job(row) if row else None

    def claim_job(self, job_id: str, expected_phase: str, phase: str, **fields: Any) -> bool:
        """Claim a durable attempt across processes without replacing another owner."""
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT phase,fields_json FROM media_job WHERE job_id=?', (job_id,)).fetchone()
            if row is None or row['phase'] != expected_phase:
                db.execute('ROLLBACK')
                return False
            current = json.loads(row['fields_json'])
            current.update(fields)
            db.execute('UPDATE media_job SET phase=?,fields_json=?,updated_at=? WHERE job_id=?',
                       (phase, _json(current), _now(), job_id))
            db.execute('COMMIT')
            return True

    def list_jobs(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = min(_MAX_LIST_LIMIT, max(0, int(limit)))
        with self._connect() as db:
            rows = db.execute("SELECT * FROM media_job ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [self._job(row) for row in rows]

    def generation_job_for_version(self, version_id: str) -> dict[str, Any] | None:
        """Local receipt lookup through the existing operation identity, never synced."""
        with self._connect() as db:
            row = db.execute('SELECT media_job.* FROM media_job JOIN operation '
                             'ON operation.operation_id=media_job.job_id WHERE operation.version_id=?',
                             (version_id,)).fetchone()
            return self._job(row) if row else None

    def recover_interrupted_jobs(self) -> int:
        """Mark jobs interrupted mid-operation so restart recovery stays explicit."""
        recoverable = {"reserving", "acquiring", "inserting"}
        count = 0
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                rows = db.execute("SELECT job_id,phase,fields_json FROM media_job").fetchall()
                for row in rows:
                    if row["phase"] not in recoverable:
                        continue
                    fields = json.loads(row["fields_json"])
                    fields["recovery_reason"] = "process_restarted_during_operation"
                    db.execute("UPDATE media_job SET phase='needs_recovery',fields_json=?,updated_at=? WHERE job_id=?",
                               (_json(fields), _now(), row["job_id"]))
                    count += 1
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
        return count

    def pending_events(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("""SELECT o.* FROM sync_outbox o WHERE o.synced=0
                AND NOT EXISTS (SELECT 1 FROM sync_conflict c WHERE c.event_id=o.event_id AND c.resolved_at IS NULL)
                ORDER BY o.sequence""").fetchall()
            return [{"event_id": row["event_id"], "kind": row["kind"], "payload": json.loads(row["payload_json"])} for row in rows]

    def record_sync_conflict(self, event_id: str, server_revision: int | None = None,
                             server_canonical_version_id: str | None = None,
                             reason: str = "server_conflict") -> dict[str, Any]:
        """Persist a server rejection and stop retrying it until explicit resolution."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT kind,payload_json FROM sync_outbox WHERE event_id=?", (event_id,)).fetchone()
                if row is None:
                    raise KeyError(event_id)
                conflict_reason = str(reason)
                if row["kind"] == "canonical" and not conflict_reason.startswith("canonical"):
                    conflict_reason = f"canonical:{conflict_reason}"
                payload = json.loads(row["payload_json"])
                asset_id = payload.get("asset_id")
                local_version_id = payload.get("version_id")
                expected = int(payload.get("expected_revision", 0))
                received = int(payload.get("revision", expected))
                db.execute("""INSERT INTO sync_conflict
                    (event_id,asset_id,local_version_id,remote_version_id,expected_revision,received_revision,
                     server_revision,server_canonical_version_id,reason,resolved_at,created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,NULL,?)
                    ON CONFLICT(event_id) DO UPDATE SET server_revision=excluded.server_revision,
                      server_canonical_version_id=excluded.server_canonical_version_id,reason=excluded.reason""",
                    (event_id, asset_id, local_version_id, server_canonical_version_id, expected, received,
                     server_revision, server_canonical_version_id, conflict_reason, _now()))
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
        return next(conflict for conflict in self.list_conflicts() if conflict["event_id"] == event_id)

    def list_conflicts(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM sync_conflict WHERE resolved_at IS NULL ORDER BY created_at,event_id").fetchall()
            return [dict(row) for row in rows]

    def resolve_conflict(self, asset_id: str, version_id: str,
                         canonical_title: str | None = None) -> dict[str, Any]:
        """Rebase an explicit canonical choice on the latest known server revision."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                asset = db.execute("SELECT * FROM asset WHERE asset_id=?", (asset_id,)).fetchone()
                version = db.execute("SELECT asset_id FROM asset_version WHERE version_id=?", (version_id,)).fetchone()
                conflicts = db.execute("SELECT c.*,o.kind AS event_kind FROM sync_conflict c LEFT JOIN sync_outbox o USING(event_id) WHERE c.asset_id=? AND c.resolved_at IS NULL ORDER BY c.created_at DESC",
                                       (asset_id,)).fetchall()
                if asset is None or version is None or version["asset_id"] != asset_id or not conflicts:
                    raise ValueError("an unresolved conflict and a version of the asset are required")
                canonical_conflicts = [c for c in conflicts if c["event_kind"] == "canonical" or str(c["reason"]).startswith("canonical")]
                if not canonical_conflicts:
                    raise ValueError("this conflict is not a canonical-choice conflict")
                if canonical_title is not None:
                    canonical_title = str(canonical_title).strip()
                    if not canonical_title:
                        raise ValueError("canonical_title cannot be blank")
                    canonical_title = canonical_title[:_MAX_TITLE_LENGTH]
                latest_server_revision = max(
                    [int(asset["remote_revision"])] + [
                        int(c["server_revision"] if c["server_revision"] is not None else asset["remote_revision"])
                        for c in canonical_conflicts])
                queued = db.execute("SELECT event_id,payload_json FROM sync_outbox WHERE kind='canonical' AND synced=0").fetchall()
                superseded = [row["event_id"] for row in queued
                              if json.loads(row["payload_json"])["asset_id"] == asset_id]
                if superseded:
                    db.executemany("UPDATE sync_outbox SET synced=1 WHERE event_id=?", ((event,) for event in superseded))
                resolved_at = _now()
                db.execute("UPDATE sync_conflict SET resolved_at=? WHERE asset_id=? AND resolved_at IS NULL AND reason LIKE 'canonical%'", (resolved_at, asset_id))
                revision = int(asset["revision"]) + 1
                db.execute("UPDATE asset SET canonical_version_id=?,title=COALESCE(?,title),revision=?,remote_revision=?,updated_at=? WHERE asset_id=?",
                           (version_id, canonical_title, revision, latest_server_revision, resolved_at, asset_id))
                event_id = str(uuid.uuid4())
                payload = {"asset_id": asset_id, "version_id": version_id,
                           "expected_revision": latest_server_revision, "revision": latest_server_revision + 1}
                if canonical_title is not None:
                    payload["canonical_title"] = canonical_title
                sequence = int(db.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM sync_outbox").fetchone()[0])
                db.execute("INSERT INTO sync_outbox (sequence,event_id,kind,payload_json,synced,created_at) VALUES (?,?,'canonical',?,0,?)",
                           (sequence, event_id, _json(payload), resolved_at))
                result = self._version_record(db, version_id)
                db.execute("COMMIT")
                assert result is not None
                return result
            except Exception:
                db.execute("ROLLBACK")
                raise

    def mark_event_synced(self, event_id: str) -> bool:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT kind,payload_json,synced FROM sync_outbox WHERE event_id=?", (event_id,)).fetchone()
                if row is None or row["synced"]:
                    db.execute("COMMIT")
                    return False
                payload = json.loads(row["payload_json"])
                if row["kind"] == "canonical":
                    db.execute("UPDATE asset SET remote_revision=MAX(remote_revision,?) WHERE asset_id=?",
                               (int(payload["revision"]), payload["asset_id"]))
                db.execute("UPDATE sync_outbox SET synced=1 WHERE event_id=?", (event_id,))
                # Our later pull can echo this event; the local change is already committed.
                db.execute("INSERT OR IGNORE INTO applied_event VALUES (?,?)", (event_id, row["kind"]))
                db.execute("COMMIT")
                return True
            except Exception:
                db.execute("ROLLBACK")
                raise

    def apply_remote_event(self, event: dict[str, Any]) -> bool:
        """Apply one metadata event once; divergent canonical writes become conflicts."""
        event_id = _uuid(event.get("event_id"), "event_id")
        kind, payload = event.get("kind"), event.get("payload")
        if kind not in {"version", "canonical"} or not isinstance(payload, dict):
            raise ValueError("event must contain a supported kind and payload mapping")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if db.execute("SELECT 1 FROM applied_event WHERE event_id=?", (event_id,)).fetchone():
                    db.execute("COMMIT")
                    return False
                if kind == "version":
                    required = {"asset_id", "version_id", "title", "tags", "sha256", "mime", "width", "height", "byte_size", "parent_version_id", "source", "created_at", "origin"}
                    if set(payload) != required:
                        raise ValueError("remote version payload has unexpected or missing fields")
                    if (payload["mime"] not in _MIME_BY_FORMAT.values() or not _SHA256_RE.fullmatch(payload["sha256"])
                            or payload["origin"] not in {"import", "generated", "web"}):
                        raise ValueError("remote version has invalid media metadata")
                    if (int(payload["width"]) <= 0 or int(payload["height"]) <= 0
                            or int(payload["width"]) * int(payload["height"]) > _MAX_IMAGE_PIXELS
                            or int(payload["byte_size"]) <= 0 or int(payload["byte_size"]) > _MAX_IMAGE_BYTES):
                        raise ValueError("remote version dimensions are invalid")
                    asset_id = _uuid(payload["asset_id"], "asset_id")
                    version_id = _uuid(payload["version_id"], "version_id")
                    prior = db.execute("SELECT * FROM asset_version WHERE version_id=?", (version_id,)).fetchone()
                    if prior:
                        remote_source = _json(_source(payload["source"]))
                        immutable = (prior["asset_id"], prior["version_title"], prior["version_tags_json"], prior["sha256"],
                                     prior["mime"], prior["width"], prior["height"], prior["byte_size"],
                                     prior["parent_version_id"], prior["source_json"], prior["origin"], prior["created_at"])
                        candidate = (asset_id, str(payload["title"])[:_MAX_TITLE_LENGTH], _json(self._tags(payload["tags"])),
                                     payload["sha256"], payload["mime"], int(payload["width"]), int(payload["height"]),
                                     int(payload["byte_size"]), payload["parent_version_id"], remote_source, payload["origin"], payload["created_at"])
                        if immutable != candidate:
                            raise ValueError("immutable version ID conflicts with existing content")
                    else:
                        asset = db.execute("SELECT asset_id FROM asset WHERE asset_id=?", (asset_id,)).fetchone()
                        if asset is None:
                            db.execute("INSERT INTO asset VALUES (?, ?, ?, NULL, 0, 0, ?, ?)",
                                       (asset_id, str(payload["title"])[:_MAX_TITLE_LENGTH], _json(self._tags(payload["tags"])), _now(), _now()))
                        parent = payload["parent_version_id"]
                        if parent:
                            parent_row = db.execute("SELECT asset_id FROM asset_version WHERE version_id=?", (parent,)).fetchone()
                            if not parent_row or parent_row["asset_id"] != asset_id:
                                raise ValueError("remote version parent is unavailable or belongs to another asset")
                        db.execute("""INSERT INTO asset_version
                            (version_id,asset_id,version_title,version_tags_json,sha256,mime,width,height,byte_size,parent_version_id,source_json,origin,created_at)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (version_id, asset_id, str(payload["title"])[:_MAX_TITLE_LENGTH], _json(self._tags(payload["tags"])),
                             payload["sha256"], payload["mime"], int(payload["width"]), int(payload["height"]),
                             int(payload["byte_size"]), parent, _json(_source(payload["source"])), payload["origin"], payload["created_at"]))
                        db.execute("UPDATE asset SET title=?,tags_json=?,updated_at=? WHERE asset_id=? AND canonical_version_id IS NULL",
                                   (str(payload["title"])[:_MAX_TITLE_LENGTH], _json(self._tags(payload["tags"])), _now(), asset_id))
                else:
                    asset_id = _uuid(payload.get("asset_id"), "asset_id")
                    version_id = _uuid(payload.get("version_id"), "version_id")
                    allowed = {"asset_id", "version_id", "expected_revision", "revision", "canonical_title"}
                    required = allowed - {"canonical_title"}
                    if frozenset(payload) not in {frozenset(required), frozenset(allowed)}:
                        raise ValueError("remote canonical payload has unexpected or missing fields")
                    expected = int(payload.get("expected_revision", -1))
                    received = int(payload.get("revision", -1))
                    asset = db.execute("SELECT * FROM asset WHERE asset_id=?", (asset_id,)).fetchone()
                    version = db.execute("SELECT asset_id FROM asset_version WHERE version_id=?", (version_id,)).fetchone()
                    if (asset is None or version is None or version["asset_id"] != asset_id
                            or expected < 0 or received != expected + 1):
                        raise ValueError("remote canonical choice refers to an unknown asset/version")
                    if expected != int(asset["remote_revision"]):
                        db.execute("""INSERT INTO sync_conflict
                            (event_id,asset_id,local_version_id,remote_version_id,expected_revision,received_revision,
                             server_revision,server_canonical_version_id,reason,resolved_at,created_at)
                            VALUES (?,?,?,?,?,?,?,?,?,NULL,?)""",
                            (event_id, asset_id, asset["canonical_version_id"], version_id, expected, received,
                             int(asset["remote_revision"]), asset["canonical_version_id"], "canonical_revision_conflict", _now()))
                    else:
                        canonical_title = payload.get("canonical_title")
                        if canonical_title is not None:
                            canonical_title = str(canonical_title).strip()
                            if not canonical_title:
                                raise ValueError("remote canonical title cannot be blank")
                            canonical_title = canonical_title[:_MAX_TITLE_LENGTH]
                        db.execute("UPDATE asset SET canonical_version_id=?,title=COALESCE(?,title),revision=revision+1,remote_revision=?,updated_at=? WHERE asset_id=?",
                                   (version_id, canonical_title, received, _now(), asset_id))
                db.execute("INSERT INTO applied_event VALUES (?,?)", (event_id, kind))
                db.execute("COMMIT")
                return True
            except Exception:
                db.execute("ROLLBACK")
                raise

    def get_sync_cursor(self, name: str = "default") -> str | None:
        with self._connect() as db:
            row = db.execute("SELECT value FROM sync_cursor WHERE name=?", (name,)).fetchone()
            return row["value"] if row else None

    def set_sync_cursor(self, value: str, name: str = "default") -> None:
        with self._connect() as db:
            db.execute("INSERT INTO sync_cursor VALUES (?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value", (name, str(value)))

    def export_backup(self, destination: Path) -> Path:
        """Create a verified, self-contained local backup without overwriting a prior one."""
        destination = Path(destination).expanduser()
        if destination.exists():
            raise FileExistsError(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.backup-", dir=destination.parent))
        try:
            with self._connect() as source:
                backup_db = sqlite3.connect(staging / "media.sqlite3")
                try:
                    source.backup(backup_db)
                finally:
                    backup_db.close()
            shutil.copytree(self.root / "blobs", staging / "blobs")
            self._verify_backup(staging)
            os.replace(staging, destination)
            return destination
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            raise

    @classmethod
    def restore_backup(cls, backup_root: Path, destination: Path) -> "MediaStore":
        """Restore a verified backup into a new data directory, preserving any existing root."""
        backup_root = Path(backup_root).expanduser()
        destination = Path(destination).expanduser()
        if destination.exists():
            raise FileExistsError(destination)
        cls._verify_backup(backup_root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.restore-", dir=destination.parent))
        try:
            shutil.copy2(backup_root / "media.sqlite3", staging / "media.sqlite3")
            shutil.copytree(backup_root / "blobs", staging / "blobs")
            cls._verify_backup(staging)
            os.replace(staging, destination)
            return cls(destination)
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            raise

    @classmethod
    def _verify_backup(cls, root: Path) -> None:
        database = root / "media.sqlite3"
        if not database.is_file() or not (root / "blobs").is_dir():
            raise ValueError("backup must contain media.sqlite3 and blobs/")
        connection = sqlite3.connect(database)
        try:
            digests = [row[0] for row in connection.execute("SELECT DISTINCT sha256 FROM asset_version")]
        except sqlite3.DatabaseError as exc:
            raise ValueError("backup media database is invalid") from exc
        finally:
            connection.close()
        blob_root = root / "blobs" / "sha256"
        for digest in digests:
            blob = blob_root / digest[:2] / digest[2:]
            if not blob.is_file() or hashlib.sha256(blob.read_bytes()).hexdigest() != digest:
                raise ValueError(f"backup is missing or has a corrupt blob: {digest}")
