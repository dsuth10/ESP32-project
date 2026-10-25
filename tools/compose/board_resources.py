"""Local typed, versioned catalogue for reusable Teaching Board resources.

This catalogue stores metadata and exact references. Image bytes remain in the
existing MediaStore content-addressed blob tree; other resource types are not
downloaded, parsed, rendered, or indexed outside their bounded local metadata.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Iterator, Sequence


RESOURCE_TYPES = frozenset({"image", "dataset", "chart", "page", "video", "audio", "document", "attachment"})
REVIEW_STATES = frozenset({"draft", "approved", "rejected", "excluded"})
AVAILABILITY_STATES = frozenset({"metadata_only", "cached", "preview_ready", "offline", "unavailable"})
RELATIONSHIPS = frozenset({"derived_from", "rendered_from", "thumbnail_of", "transcript_of", "segment_of", "uses", "part_of", "supersedes"})
MAX_TEXT = 4000
MAX_TITLE = 200
MAX_ITEMS = 100
MAX_QUERY = 500
MAX_LIMIT = 100
MAX_METADATA_BYTES = 65536
_HEX = re.compile(r"^[0-9a-f]{64}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _uuid(value: str | None, name: str) -> str:
    try:
        return str(uuid.uuid4()) if value is None else str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"{name} must be a UUID") from exc


def _clean_text(value: Any, name: str, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    result = value.strip()
    if len(result) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return result


def _strings(values: Sequence[str] | None, name: str) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a sequence of strings")
    result = []
    for value in values:
        cleaned = _clean_text(value, name, 200)
        if cleaned and cleaned.casefold() not in {item.casefold() for item in result}:
            result.append(cleaned)
    if len(result) > MAX_ITEMS:
        raise ValueError(f"{name} may contain at most {MAX_ITEMS} items")
    return result


def _json_object(value: dict[str, Any] | None, name: str) -> str:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError(f"{name} must contain JSON-compatible values") from exc
    if len(encoded.encode("utf-8")) > MAX_METADATA_BYTES:
        raise ValueError(f"{name} exceeds the 64 KiB metadata limit")
    return encoded


class ResourceCatalogue:
    """A per-store SQLite catalogue; it never modifies the image library."""

    def __init__(self, root_or_db_path: Path | str, media_root: Path | str | None = None, *, media_store: Any = None, resolver: Any = None) -> None:
        target = Path(root_or_db_path).expanduser()
        if target.suffix.casefold() in {".sqlite", ".sqlite3", ".db"}:
            target.parent.mkdir(parents=True, exist_ok=True)
            self.path = target
        else:
            target.mkdir(parents=True, exist_ok=True)
            self.path = target / "board_resources.sqlite3"
        if media_root is not None and media_store is not None:
            raise ValueError("provide media_root or media_store, not both")
        self.media_store = media_store
        self.resolver = resolver
        inferred_root = getattr(media_store, "root", None) if media_store is not None else media_root
        self.media_root = Path(inferred_root).expanduser().absolute() if inferred_root is not None else None
        self._initialise()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        try:
            yield db
        finally:
            db.close()

    def _initialise(self) -> None:
        with self._connect() as db:
            db.execute("PRAGMA foreign_keys=ON")
            schema_version = int(db.execute("PRAGMA user_version").fetchone()[0])
            if schema_version > 1:
                raise ValueError(f"board resource catalogue schema {schema_version} is newer than this application supports")
            if not db.execute("SELECT sqlite_compileoption_used('ENABLE_FTS5')").fetchone()[0]:
                # Some builds omit the compile option despite exposing FTS5. The
                # virtual-table creation below is the definitive capability check.
                pass
            db.executescript("""
                CREATE TABLE IF NOT EXISTS resource (
                    resource_id TEXT PRIMARY KEY,
                    resource_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(resource_id, resource_type)
                );
                CREATE TABLE IF NOT EXISTS resource_version (
                    version_id TEXT PRIMARY KEY,
                    resource_id TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    provenance_json TEXT NOT NULL DEFAULT '{}',
                    content_hash TEXT,
                    mime TEXT,
                    byte_size INTEGER,
                    availability TEXT NOT NULL,
                    review_state TEXT NOT NULL,
                    media_asset_id TEXT,
                    media_version_id TEXT,
                    created_at TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE,
                    FOREIGN KEY(resource_id, resource_type) REFERENCES resource(resource_id, resource_type),
                    UNIQUE(resource_id, version_id)
                );
                CREATE INDEX IF NOT EXISTS resource_version_latest ON resource_version(resource_id, created_at DESC, version_id DESC);
                CREATE INDEX IF NOT EXISTS resource_version_type_state ON resource_version(resource_type, review_state, availability);
                CREATE TABLE IF NOT EXISTS resource_alias (
                    alias_id INTEGER PRIMARY KEY,
                    resource_id TEXT NOT NULL REFERENCES resource(resource_id),
                    version_id TEXT,
                    alias TEXT NOT NULL,
                    normalised TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(resource_id, version_id) REFERENCES resource_version(resource_id, version_id),
                    UNIQUE(resource_id, version_id, normalised)
                );
                CREATE INDEX IF NOT EXISTS resource_alias_exact ON resource_alias(normalised, resource_id, version_id);
                CREATE TABLE IF NOT EXISTS resource_relationship (
                    relationship_id INTEGER PRIMARY KEY,
                    source_resource_id TEXT NOT NULL,
                    source_version_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    target_resource_id TEXT NOT NULL,
                    target_version_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(source_resource_id, source_version_id) REFERENCES resource_version(resource_id, version_id),
                    FOREIGN KEY(target_resource_id, target_version_id) REFERENCES resource_version(resource_id, version_id),
                    UNIQUE(source_resource_id, source_version_id, relation, target_resource_id, target_version_id)
                );
                CREATE TABLE IF NOT EXISTS review_override (
                    resource_id TEXT NOT NULL,
                    version_id TEXT NOT NULL,
                    review_state TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(resource_id, version_id),
                    FOREIGN KEY(resource_id, version_id) REFERENCES resource_version(resource_id, version_id)
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS resource_fts USING fts5(
                    version_id UNINDEXED, resource_id UNINDEXED, resource_type UNINDEXED,
                    title, aliases, description, tags, metadata,
                    tokenize='unicode61 remove_diacritics 2'
                );
            """)
            if schema_version == 0:
                db.execute("PRAGMA user_version=1")

    def _validate_media_ref(self, media_ref: dict[str, str] | None, content_hash: str | None) -> tuple[str | None, str | None, str | None, str | None, int | None]:
        if media_ref is None:
            return None, None, content_hash, None, None
        if not isinstance(media_ref, dict):
            raise ValueError("media_ref must be a mapping")
        if not media_ref.get("asset_id") or not media_ref.get("version_id"):
            raise ValueError("media_ref must provide exact asset_id and version_id values")
        asset_id = _uuid(media_ref.get("asset_id"), "media_ref.asset_id")
        version_id = _uuid(media_ref.get("version_id"), "media_ref.version_id")
        supplied_hash = media_ref.get("sha256")
        if supplied_hash is not None and not _HEX.fullmatch(str(supplied_hash)):
            raise ValueError("media_ref.sha256 must be a lowercase SHA-256 digest")
        if content_hash and supplied_hash and content_hash != supplied_hash:
            raise ValueError("media_ref.sha256 does not match content_hash")
        content_hash = content_hash or supplied_hash
        if self.resolver is not None:
            resolved = self.resolver(asset_id, version_id)
            if not resolved or resolved.get("asset_id") != asset_id or resolved.get("version_id") != version_id:
                raise ValueError("media_ref must identify an existing exact image version")
            digest = resolved.get("sha256")
            if content_hash and content_hash != digest:
                raise ValueError("media_ref hash does not match the resolved image version")
            return asset_id, version_id, digest, resolved.get("mime"), resolved.get("byte_size")
        if self.media_store is not None:
            resolved = self.media_store.get_version(version_id)
            if not resolved or resolved.get("asset_id") != asset_id:
                raise ValueError("media_ref must identify an existing exact image version")
            if content_hash and content_hash != resolved["sha256"]:
                raise ValueError("media_ref hash does not match the stored image version")
            return asset_id, version_id, resolved["sha256"], resolved.get("mime"), resolved.get("byte_size")
        if self.media_root is None and "root" not in media_ref:
            # Preserve a usable metadata-only API for callers that provide exact
            # IDs and a digest but deliberately have no connected image store.
            return asset_id, version_id, content_hash, None, None
        media_root = Path(media_ref.get("root", self.media_root or "")).expanduser().absolute()
        database = media_root / "media.sqlite3"
        if not database.is_file():
            raise ValueError("the referenced image library is unavailable")
        db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=3)
        try:
            db.execute("PRAGMA query_only=ON")
            row = db.execute("SELECT v.sha256,v.mime,v.byte_size,v.asset_id FROM asset_version v WHERE v.version_id=?", (version_id,)).fetchone()
        except sqlite3.DatabaseError as exc:
            raise ValueError("the referenced image library has an unsupported schema") from exc
        finally:
            db.close()
        if row is None or row[3] != asset_id:
            raise ValueError("media_ref must identify an existing exact image version")
        if content_hash and content_hash != row[0]:
            raise ValueError("content_hash does not match the referenced image version")
        return asset_id, version_id, row[0], row[1], int(row[2])

    def _media_blob_available(self, media_ref: dict[str, str] | None, digest: str | None,
                              expected_size: int | None = None) -> bool:
        if not media_ref or not digest or not _HEX.fullmatch(digest):
            return False
        root = getattr(self.media_store, "root", None) if self.media_store is not None else self.media_root
        if root is None and media_ref.get("root"):
            root = media_ref["root"]
        if root is None:
            return False
        root = Path(root).expanduser().absolute()
        blob = root / "blobs" / "sha256" / digest[:2] / digest[2:]
        try:
            if any(path.is_symlink() or path.is_junction() for path in (root, *root.parents, *blob.parents, blob)):
                return False
            resolved_root, resolved_blob = root.resolve(), blob.resolve()
            if resolved_root not in resolved_blob.parents or not resolved_blob.is_file():
                return False
            if resolved_blob.stat().st_size > 20 * 1024 * 1024:
                return False
            if expected_size is not None and resolved_blob.stat().st_size != expected_size:
                return False
            hasher = hashlib.sha256()
            with resolved_blob.open("rb") as stream:
                while chunk := stream.read(64 * 1024):
                    hasher.update(chunk)
            return hasher.hexdigest() == digest
        except (OSError, RuntimeError, ValueError):
            return False

    def save_resource(
        self,
        resource_type: str,
        title: str,
        *,
        metadata: dict[str, Any] | None = None,
        description: str = "",
        aliases: Sequence[str] | None = None,
        tags: Sequence[str] | None = None,
        provenance: dict[str, Any] | None = None,
        resource_id: str | None = None,
        version_id: str | None = None,
        content_hash: str | None = None,
        mime: str | None = None,
        byte_size: int | None = None,
        availability: str = "metadata_only",
        state: str = "draft",
        media_ref: dict[str, str] | None = None,
        image_ref: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Save an immutable version, returning the prior version for a repeated key."""
        if resource_type not in RESOURCE_TYPES:
            raise ValueError(f"resource_type must be one of {', '.join(sorted(RESOURCE_TYPES))}")
        title = _clean_text(title, "title", MAX_TITLE)
        if not title:
            raise ValueError("title is required")
        description = _clean_text(description, "description")
        if availability not in AVAILABILITY_STATES:
            raise ValueError("unsupported availability state")
        if state not in REVIEW_STATES:
            raise ValueError("unsupported review state")
        if image_ref is not None:
            if media_ref is not None:
                raise ValueError("provide image_ref or media_ref, not both")
            media_ref = image_ref
        if resource_type == "image" and media_ref is None:
            raise ValueError("image resources require an exact existing media_ref")
        if resource_type != "image" and media_ref is not None:
            raise ValueError("media_ref is only valid for image resources")
        if content_hash is not None and not _HEX.fullmatch(content_hash):
            raise ValueError("content_hash must be a lowercase SHA-256 digest")
        if byte_size is not None and (isinstance(byte_size, bool) or not isinstance(byte_size, int) or byte_size < 0):
            raise ValueError("byte_size must be a non-negative integer")
        if mime is not None and (not isinstance(mime, str) or len(mime) > 200):
            raise ValueError("mime must be text up to 200 characters")
        meta_json = _json_object(metadata, "metadata")
        provenance_json = _json_object(provenance, "provenance")
        alias_list = _strings(aliases, "aliases")
        tag_list = _strings(tags, "tags")
        alias_list = list(dict.fromkeys([title, *alias_list]))
        asset_id, media_version_id, content_hash, media_mime, media_size = self._validate_media_ref(media_ref, content_hash)
        if media_mime:
            mime, byte_size = media_mime, media_size
            availability = "offline" if self._media_blob_available(media_ref, content_hash, media_size) else (
                "unavailable" if (self.media_store is not None or self.media_root is not None or media_ref.get("root"))
                else "metadata_only")
        rid = _uuid(resource_id, "resource_id") if resource_id is not None else (asset_id or str(uuid.uuid4()))
        vid = _uuid(version_id, "version_id") if version_id is not None else (media_version_id or str(uuid.uuid4()))
        if idempotency_key is not None:
            idempotency_key = _clean_text(idempotency_key, "idempotency_key", 200)
            if not idempotency_key:
                raise ValueError("idempotency_key cannot be empty")
        created_at = _now()
        with self._connect() as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            try:
                if idempotency_key:
                    existing = db.execute("SELECT * FROM resource_version WHERE idempotency_key=?", (idempotency_key,)).fetchone()
                    if existing:
                        same = (
                            existing["resource_type"] == resource_type
                            and existing["title"] == title
                            and existing["description"] == description
                            and existing["tags_json"] == json.dumps(tag_list, ensure_ascii=False)
                            and existing["metadata_json"] == meta_json
                            and existing["provenance_json"] == provenance_json
                            and existing["content_hash"] == content_hash
                            and existing["mime"] == mime
                            and existing["byte_size"] == byte_size
                            and existing["availability"] == availability
                            and existing["review_state"] == state
                            and existing["media_asset_id"] == asset_id
                            and existing["media_version_id"] == media_version_id
                            and (resource_id is None or existing["resource_id"] == rid)
                            and (version_id is None or existing["version_id"] == vid)
                        )
                        existing_aliases = {row[0] for row in db.execute(
                            "SELECT normalised FROM resource_alias WHERE resource_id=? AND version_id=?",
                            (existing["resource_id"], existing["version_id"]))}
                        if not same or existing_aliases != {alias.casefold() for alias in alias_list}:
                            raise ValueError("idempotency_key is already bound to a different resource payload")
                        db.execute("COMMIT")
                        return self.get_resource_by_version(existing["version_id"])
                existing_resource = db.execute("SELECT resource_type FROM resource WHERE resource_id=?", (rid,)).fetchone()
                if existing_resource and existing_resource["resource_type"] != resource_type:
                    raise ValueError("resource_id already belongs to a different resource type")
                if not existing_resource:
                    db.execute("INSERT INTO resource VALUES (?,?,?)", (rid, resource_type, created_at))
                db.execute("""INSERT INTO resource_version
                    (version_id,resource_id,resource_type,title,description,tags_json,metadata_json,provenance_json,
                     content_hash,mime,byte_size,availability,review_state,media_asset_id,media_version_id,created_at,idempotency_key)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (vid,rid,resource_type,title,description,json.dumps(tag_list,ensure_ascii=False),meta_json,provenance_json,
                     content_hash,mime,byte_size,availability,state,asset_id,media_version_id,created_at,idempotency_key))
                for alias in alias_list:
                    db.execute("INSERT OR IGNORE INTO resource_alias(resource_id,version_id,alias,normalised,created_at) VALUES (?,?,?,?,?)",
                               (rid,vid,alias,alias.casefold(),created_at))
                self._refresh_fts(db, rid, vid)
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
        return self.get_resource_by_version(vid)

    @staticmethod
    def _row_record(db: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        override = db.execute("SELECT review_state,reason FROM review_override WHERE resource_id=? AND version_id=?",
                              (row["resource_id"], row["version_id"])).fetchone()
        aliases = [item[0] for item in db.execute("SELECT alias FROM resource_alias WHERE resource_id=? AND (version_id=? OR version_id IS NULL) ORDER BY normalised,alias",
                                                   (row["resource_id"], row["version_id"]))]
        return {"resource_id": row["resource_id"], "version_id": row["version_id"], "resource_type": row["resource_type"],
                "title": row["title"], "description": row["description"], "tags": json.loads(row["tags_json"]),
                "aliases": aliases, "metadata": json.loads(row["metadata_json"]), "provenance": json.loads(row["provenance_json"]),
                "content_hash": row["content_hash"], "mime": row["mime"], "byte_size": row["byte_size"],
                "availability": row["availability"], "review_state": override["review_state"] if override else row["review_state"],
                "review_reason": override["reason"] if override else "", "media_ref": ({"asset_id":row["media_asset_id"],"version_id":row["media_version_id"],"sha256":row["content_hash"]} if row["media_asset_id"] else None),
                "image_ref": ({"asset_id":row["media_asset_id"],"version_id":row["media_version_id"],"sha256":row["content_hash"]} if row["media_asset_id"] else None),
                "created_at": row["created_at"]}

    def get_resource_by_version(self, version_id: str) -> dict[str, Any] | None:
        vid = _uuid(version_id, "version_id")
        with self._connect() as db:
            row = db.execute("SELECT * FROM resource_version WHERE version_id=?", (vid,)).fetchone()
            return self._row_record(db, row) if row else None

    def get_resource(self, resource_id: str, version_id: str | None = None) -> dict[str, Any] | None:
        rid = _uuid(resource_id, "resource_id")
        with self._connect() as db:
            if version_id:
                row = db.execute("SELECT * FROM resource_version WHERE resource_id=? AND version_id=?", (rid, _uuid(version_id,"version_id"))).fetchone()
            else:
                row = db.execute("SELECT * FROM resource_version WHERE resource_id=? ORDER BY created_at DESC,version_id DESC LIMIT 1", (rid,)).fetchone()
            return self._row_record(db, row) if row else None

    def resolve(self, reference: str, *, include_excluded: bool = False) -> dict[str, Any] | None:
        """Resolve exact resource/version UUIDs or an exact teacher alias."""
        value = _clean_text(reference, "reference", 300)
        with self._connect() as db:
            try:
                parsed = str(uuid.UUID(value))
            except ValueError:
                parsed = None
            if parsed:
                row = db.execute("SELECT * FROM resource_version WHERE version_id=?", (parsed,)).fetchone()
                if row:
                    result = self._row_record(db, row)
                    return result if include_excluded or (result["review_state"] not in {"rejected", "excluded"} and result["availability"] != "unavailable") else None
                row = db.execute("SELECT * FROM resource_version WHERE resource_id=? ORDER BY created_at DESC,version_id DESC LIMIT 1", (parsed,)).fetchone()
                if not row:
                    return None
                result = self._row_record(db, row)
                return result if include_excluded or (result["review_state"] not in {"rejected", "excluded"} and result["availability"] != "unavailable") else None
            rows = db.execute("""SELECT v.* FROM resource_alias a JOIN resource_version v
                ON v.resource_id=a.resource_id AND (a.version_id=v.version_id OR a.version_id IS NULL)
                WHERE a.normalised=? ORDER BY a.version_id IS NULL, v.created_at DESC, v.version_id DESC""", (value.casefold(),)).fetchall()
            if not rows:
                return None
            # Ambiguous exact aliases do not silently select one resource.
            unique = {(row["resource_id"], row["version_id"]): row for row in rows}
            records = [self._row_record(db, row) for row in unique.values()]
            if not include_excluded:
                records = [record for record in records if record["review_state"] not in {"rejected", "excluded"} and record["availability"] != "unavailable"]
            return records[0] if len(records) == 1 else None

    @staticmethod
    def _refresh_fts(db: sqlite3.Connection, resource_id: str, version_id: str) -> None:
        row = db.execute("SELECT * FROM resource_version WHERE resource_id=? AND version_id=?", (resource_id,version_id)).fetchone()
        if row is None:
            return
        aliases = " ".join(alias[0] for alias in db.execute("SELECT alias FROM resource_alias WHERE resource_id=? AND (version_id=? OR version_id IS NULL)", (resource_id,version_id)))
        db.execute("DELETE FROM resource_fts WHERE version_id=?", (version_id,))
        db.execute("INSERT INTO resource_fts VALUES (?,?,?,?,?,?,?,?)", (version_id,resource_id,row["resource_type"],row["title"],aliases,row["description"]," ".join(json.loads(row["tags_json"])),row["metadata_json"]))

    @staticmethod
    def _query_terms(query: str) -> list[str]:
        terms = re.findall(r"[^\W_]+", query, flags=re.UNICODE)
        return terms[:32]

    def search(self, query: str = "", *, resource_types: Sequence[str] | None = None, include_excluded: bool = False, limit: int = 20) -> list[dict[str, Any]]:
        """Search local metadata deterministically; exact references/aliases rank first."""
        query = _clean_text(query, "query", MAX_QUERY)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_LIMIT}")
        types = _strings(resource_types, "resource_types") if resource_types is not None else []
        if any(value not in RESOURCE_TYPES for value in types):
            raise ValueError("resource_types contains an unsupported type")
        where, params = [], []
        if types:
            where.append("v.resource_type IN (" + ",".join("?" for _ in types) + ")")
            params.extend(types)
        if not include_excluded:
            where.append("COALESCE(o.review_state,v.review_state) NOT IN ('rejected','excluded')")
            where.append("v.availability!='unavailable'")
        filter_sql = (" WHERE " + " AND ".join(where)) if where else ""
        terms = self._query_terms(query)
        fts_query = " AND ".join('"' + term.replace('"', '""') + '"' for term in terms)
        with self._connect() as db:
            if not query:
                rows = db.execute(f"""SELECT v.*,o.review_state AS override_state,o.reason AS override_reason,0 AS rank
                    FROM resource_version v LEFT JOIN review_override o USING(resource_id,version_id){filter_sql}
                    ORDER BY v.created_at DESC,v.resource_id,v.version_id LIMIT ?""", (*params,limit)).fetchall()
            elif not terms:
                rows = []
            else:
                exact = None
                try:
                    value = str(uuid.UUID(query))
                except ValueError:
                    value = None
                if value:
                    exact = db.execute(f"""SELECT v.*,o.review_state AS override_state,o.reason AS override_reason,-1000000 AS rank
                        FROM resource_version v LEFT JOIN review_override o USING(resource_id,version_id)
                        WHERE (v.version_id=? OR v.resource_id=?)""" + (" AND "+" AND ".join(where) if where else "") + " ORDER BY v.version_id=? DESC,v.created_at DESC LIMIT ?", (value,value,*params,value,limit)).fetchall()
                exact_alias = db.execute(f"""SELECT v.*,o.review_state AS override_state,o.reason AS override_reason,-500000 AS rank
                    FROM resource_alias a JOIN resource_version v ON v.resource_id=a.resource_id AND (a.version_id=v.version_id OR a.version_id IS NULL)
                    LEFT JOIN review_override o USING(resource_id,version_id) WHERE a.normalised=?""" + (" AND "+" AND ".join(where) if where else "") + " ORDER BY a.version_id IS NULL,v.created_at DESC,v.version_id LIMIT ?", (query.casefold(),*params,limit)).fetchall()
                found = {(r["resource_id"],r["version_id"]):r for r in [*(exact or []),*exact_alias]}
                remaining = max(0, limit-len(found))
                ranked = []
                if remaining and fts_query:
                    ranked = db.execute(f"""SELECT v.*,o.review_state AS override_state,o.reason AS override_reason,bm25(resource_fts,0.0,0.0,0.0,8.0,6.0,2.0,3.0,0.5) AS rank
                        FROM resource_fts JOIN resource_version v ON v.version_id=resource_fts.version_id
                        LEFT JOIN review_override o USING(resource_id,version_id)
                        WHERE resource_fts MATCH ?""" + (" AND "+" AND ".join(where) if where else "") + " ORDER BY rank ASC,v.created_at DESC,v.resource_id,v.version_id LIMIT ?", (fts_query,*params,remaining)).fetchall()
                rows = list(found.values()) + [r for r in ranked if (r["resource_id"],r["version_id"]) not in found]
            result = []
            for row in rows:
                record = self._row_record(db,row)
                record["match_score"] = float(row["rank"])
                if record["review_state"] in {"rejected", "excluded"} and not include_excluded:
                    continue
                if record["availability"] == "unavailable" and not include_excluded:
                    continue
                result.append(record)
            return result[:limit]

    def disambiguate(self, query: str, *, resource_types: Sequence[str] | None = None, limit: int = 8) -> list[dict[str, Any]]:
        """Return a small explicit-choice list for teacher/UI review."""
        return self.search(query, resource_types=resource_types, include_excluded=False, limit=min(limit, 8))

    def auto_select(self, query: str, *, resource_types: Sequence[str] | None = None) -> dict[str, Any] | None:
        """Select only a single exact approved alias; lexical matches need a chooser."""
        result = self.resolve(query)
        if result is None or result["review_state"] != "approved" or result["availability"] == "unavailable":
            return None
        if resource_types and result["resource_type"] not in resource_types:
            return None
        if result["resource_type"] == "image":
            ref = result.get("media_ref")
            if result["availability"] != "offline" or not self._media_blob_available(ref, result.get("content_hash"), result.get("byte_size")):
                return None
        return result

    def add_alias(self, resource_id: str, alias: str, *, version_id: str | None = None) -> None:
        rid = _uuid(resource_id, "resource_id")
        alias = _clean_text(alias, "alias", 200)
        if not alias:
            raise ValueError("alias is required")
        vid = _uuid(version_id, "version_id") if version_id else None
        with self._connect() as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            try:
                if not db.execute("SELECT 1 FROM resource WHERE resource_id=?", (rid,)).fetchone():
                    raise ValueError("resource does not exist")
                db.execute("INSERT OR IGNORE INTO resource_alias(resource_id,version_id,alias,normalised,created_at) VALUES (?,?,?,?,?)", (rid,vid,alias,alias.casefold(),_now()))
                if vid:
                    self._refresh_fts(db,rid,vid)
                else:
                    for row in db.execute("SELECT version_id FROM resource_version WHERE resource_id=?", (rid,)).fetchall():
                        self._refresh_fts(db,rid,row[0])
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise

    def set_review_state(self, resource_id: str, version_id: str, state: str, reason: str = "") -> None:
        """Set mutable eligibility without altering the immutable saved version."""
        rid, vid = _uuid(resource_id,"resource_id"), _uuid(version_id,"version_id")
        if state not in REVIEW_STATES:
            raise ValueError("unsupported review state")
        reason = _clean_text(reason,"reason",1000)
        with self._connect() as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("INSERT INTO review_override VALUES (?,?,?,?,?) ON CONFLICT(resource_id,version_id) DO UPDATE SET review_state=excluded.review_state,reason=excluded.reason,updated_at=excluded.updated_at",
                        (rid,vid,state,reason,_now()))

    def add_relationship(self, source_ref: str, relation: str, target_ref: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """Link two exact versions; endpoints must resolve unambiguously."""
        if relation not in RELATIONSHIPS:
            raise ValueError("unsupported relationship type")
        source, target = self.resolve(source_ref), self.resolve(target_ref)
        if source is None or target is None:
            raise ValueError("relationship endpoints must be exact version IDs or unambiguous exact aliases")
        for supplied, resolved in ((source_ref, source), (target_ref, target)):
            try:
                parsed = str(uuid.UUID(supplied))
            except (ValueError, TypeError, AttributeError):
                parsed = None
            if parsed and parsed == resolved["resource_id"] and parsed != resolved["version_id"]:
                raise ValueError("relationships must pin exact version IDs, not a moving resource ID")
        encoded = _json_object(metadata,"relationship metadata")
        with self._connect() as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("INSERT OR IGNORE INTO resource_relationship(source_resource_id,source_version_id,relation,target_resource_id,target_version_id,metadata_json,created_at) VALUES (?,?,?,?,?,?,?)",
                        (source["resource_id"],source["version_id"],relation,target["resource_id"],target["version_id"],encoded,_now()))
            row = db.execute("SELECT * FROM resource_relationship WHERE source_resource_id=? AND source_version_id=? AND relation=? AND target_resource_id=? AND target_version_id=?",
                             (source["resource_id"],source["version_id"],relation,target["resource_id"],target["version_id"])).fetchone()
            return {"source_resource_id":row["source_resource_id"],"source_version_id":row["source_version_id"],"relation":row["relation"],
                    "target_resource_id":row["target_resource_id"],"target_version_id":row["target_version_id"],"metadata":json.loads(row["metadata_json"])}

    def relationships(self, resource_id: str, version_id: str | None = None) -> list[dict[str, Any]]:
        rid = _uuid(resource_id,"resource_id")
        sql = "SELECT * FROM resource_relationship WHERE source_resource_id=? OR target_resource_id=?"
        params: list[Any] = [rid,rid]
        if version_id:
            vid = _uuid(version_id,"version_id")
            sql = "SELECT * FROM resource_relationship WHERE (source_resource_id=? OR target_resource_id=?) AND (source_version_id=? OR target_version_id=?)"
            params.extend([vid,vid])
        sql += " ORDER BY relation,source_version_id,target_version_id"
        with self._connect() as db:
            return [{"source_resource_id":r["source_resource_id"],"source_version_id":r["source_version_id"],"relation":r["relation"],
                     "target_resource_id":r["target_resource_id"],"target_version_id":r["target_version_id"],"metadata":json.loads(r["metadata_json"])}
                    for r in db.execute(sql,params)]

    def rebuild_index(self) -> int:
        """Rebuild the local derived FTS table from authoritative catalogue rows."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute("DELETE FROM resource_fts")
                rows = db.execute("SELECT resource_id,version_id FROM resource_version ORDER BY resource_id,version_id").fetchall()
                for row in rows:
                    self._refresh_fts(db,row["resource_id"],row["version_id"])
                db.execute("COMMIT")
                return len(rows)
            except Exception:
                db.execute("ROLLBACK")
                raise


__all__ = ["ResourceCatalogue", "RESOURCE_TYPES", "REVIEW_STATES", "AVAILABILITY_STATES", "RELATIONSHIPS"]
