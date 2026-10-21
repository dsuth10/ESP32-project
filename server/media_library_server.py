"""Private, single-host media library sync API.

The service is intentionally small and uses only the Python standard library.
Run it behind a private HTTPS endpoint (for example, Tailscale Serve) when
accessing it from another machine. It defaults to loopback and refuses to
start without an explicitly configured bearer token.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
import re
import sqlite3
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

MAX_BLOB_BYTES = 20 * 1024 * 1024
MAX_EVENT_BYTES = 128 * 1024
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}
SOURCE_FIELDS = {"url", "creator", "licence", "attribution", "provider", "model"}
VERSION_FIELDS = {
    "asset_id", "version_id", "title", "tags", "sha256", "mime", "width", "height",
    "byte_size", "parent_version_id", "source", "created_at", "origin",
}


class ApiError(Exception):
    def __init__(self, status: int, message: str, details: dict[str, Any] | None = None):
        self.status = status
        self.message = message
        self.details = details or {}
        super().__init__(message)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _valid_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(uuid.UUID(value)) == value.lower()
    except (ValueError, AttributeError):
        return False


def _validate_version(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != VERSION_FIELDS:
        raise ApiError(400, "Invalid version event schema")
    version = payload
    if not isinstance(version, dict) or set(version) - VERSION_FIELDS:
        raise ApiError(400, "Invalid version metadata fields")
    if not _valid_uuid(version.get("asset_id")) or not _valid_uuid(version.get("version_id")):
        raise ApiError(400, "Invalid asset or version identifier")
    if version.get("mime") not in ALLOWED_MIME or version.get("origin") not in {"import", "generated", "web", "derived"}:
        raise ApiError(400, "Unsupported image type or origin")
    if not isinstance(version.get("title"), str) or len(version["title"]) > 240:
        raise ApiError(400, "Invalid title")
    tags = version.get("tags")
    if not isinstance(tags, list) or len(tags) > 40 or any(not isinstance(t, str) or len(t) > 80 for t in tags):
        raise ApiError(400, "Invalid tags")
    for field in ("width", "height", "byte_size"):
        n = version.get(field)
        if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
            raise ApiError(400, f"Invalid {field}")
    if version["byte_size"] > MAX_BLOB_BYTES or not HASH_RE.fullmatch(str(version.get("sha256", ""))):
        raise ApiError(400, "Invalid blob reference")
    if version.get("parent_version_id") is not None and not _valid_uuid(version["parent_version_id"]):
        raise ApiError(400, "Invalid parent version")
    source = version.get("source", {})
    if not isinstance(source, dict) or set(source) - SOURCE_FIELDS or any(not isinstance(v, str) or len(v) > 2048 for v in source.values()):
        raise ApiError(400, "Invalid source metadata")
    source_url = source.get("url")
    if source_url:
        parsed_source = urlsplit(source_url)
        if (parsed_source.scheme not in {"http", "https"} or not parsed_source.hostname
                or parsed_source.username is not None or parsed_source.password is not None
                or parsed_source.query or parsed_source.fragment):
            raise ApiError(400, "Source URL must be a public page URL without credentials or query data")
    return payload


def _validate_canonical(payload: Any) -> dict[str, Any]:
    required = {"asset_id", "version_id", "expected_revision", "revision"}
    if not isinstance(payload, dict) or not required.issubset(payload) or set(payload) - (required | {"canonical_title"}):
        raise ApiError(400, "Invalid canonical event schema")
    if not _valid_uuid(payload.get("asset_id")) or not _valid_uuid(payload.get("version_id")):
        raise ApiError(400, "Invalid asset or version identifier")
    rev = payload.get("expected_revision")
    if isinstance(rev, bool) or not isinstance(rev, int) or rev < 0:
        raise ApiError(400, "Invalid expected revision")
    if isinstance(payload["revision"], bool) or not isinstance(payload["revision"], int) or payload["revision"] != rev + 1:
        raise ApiError(400, "Canonical revision must follow expected revision")
    if "canonical_title" in payload:
        title = payload["canonical_title"]
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            raise ApiError(400, "Invalid canonical title")
    return payload


class MediaLibrary:
    def __init__(self, data_dir: str | Path, token: str):
        if not token or not token.strip():
            raise ValueError("MEDIA_SERVER_TOKEN must be configured")
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.blob_dir = self.data_dir / "blobs"
        self.db_path = self.data_dir / "media-server.sqlite3"
        self.token = token.encode("utf-8")
        self.lock = threading.RLock()
        self.blob_dir.mkdir(parents=True, exist_ok=True)
        self._initialise()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA foreign_keys=ON")
            yield db
            if db.in_transaction:
                db.commit()
        except BaseException:
            if db.in_transaction:
                db.rollback()
            raise
        finally:
            db.close()

    def _initialise(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS events (
                    cursor INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    kind TEXT NOT NULL,
                    payload BLOB NOT NULL,
                    payload_hash TEXT NOT NULL,
                    asset_id TEXT,
                    asset_revision INTEGER,
                    received_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assets (
                    asset_id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL,
                    canonical_title TEXT,
                    canonical_version_id TEXT,
                    canonical_event_id TEXT
                );
                CREATE TABLE IF NOT EXISTS versions (
                    version_id TEXT PRIMARY KEY,
                    asset_id TEXT NOT NULL,
                    metadata BLOB NOT NULL,
                    FOREIGN KEY(asset_id) REFERENCES assets(asset_id)
                );
                CREATE TABLE IF NOT EXISTS budget_reservations (
                    operation_id TEXT PRIMARY KEY,
                    amount_cents INTEGER NOT NULL,
                    period TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('pending','committed','uncertain','released')),
                    actual_cents INTEGER,
                    updated_at TEXT NOT NULL
                );
            """)
            asset_columns = {row["name"] for row in db.execute("PRAGMA table_info(assets)")}
            if "canonical_title" not in asset_columns:
                db.execute("ALTER TABLE assets ADD COLUMN canonical_title TEXT")

    def _blob_path(self, digest: str) -> Path:
        return self.blob_dir / digest[:2] / digest

    def put_blob(self, digest: str, body: bytes, content_type: str) -> bool:
        if not HASH_RE.fullmatch(digest):
            raise ApiError(400, "Invalid SHA-256")
        if len(body) > MAX_BLOB_BYTES:
            raise ApiError(413, "Blob exceeds 20 MiB")
        if hashlib.sha256(body).hexdigest() != digest:
            raise ApiError(400, "Blob hash mismatch")
        detected = _image_info(body)
        if detected is None or detected[0] != content_type.split(";", 1)[0].lower():
            raise ApiError(415, "Unsupported or mismatched image MIME type")
        target = self._blob_path(digest)
        with self.lock:
            if target.exists():
                if target.stat().st_size != len(body) or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                    raise ApiError(500, "Stored blob integrity check failed")
                return False
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".upload-", dir=target.parent)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(body)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, target)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
        return True

    def get_blob(self, digest: str) -> tuple[bytes, str]:
        if not HASH_RE.fullmatch(digest):
            raise ApiError(400, "Invalid SHA-256")
        path = self._blob_path(digest)
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            raise ApiError(404, "Blob not found")
        if hashlib.sha256(body).hexdigest() != digest:
            raise ApiError(500, "Stored blob integrity check failed")
        info = _image_info(body)
        if info is None:
            raise ApiError(500, "Stored blob is not a supported image")
        return body, info[0]

    def accept_event(self, event: Any) -> dict[str, Any]:
        if not isinstance(event, dict) or set(event) != {"event_id", "kind", "payload"}:
            raise ApiError(400, "Invalid event envelope")
        event_id, kind, payload = event["event_id"], event["kind"], event["payload"]
        if not _valid_uuid(event_id):
            raise ApiError(400, "Invalid event id")
        if kind == "version":
            payload = _validate_version(payload)
            asset_id = payload["asset_id"]
        elif kind == "canonical":
            payload = _validate_canonical(payload)
            asset_id = payload["asset_id"]
        else:
            raise ApiError(400, "Unsupported event kind")
        encoded = _json_bytes(payload)
        digest = hashlib.sha256(encoded).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        with self.lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT cursor,payload_hash FROM events WHERE event_id=?", (event_id,)).fetchone()
            if prior:
                if prior["payload_hash"] != digest:
                    raise ApiError(409, "Event id already exists with different content")
                db.execute("COMMIT")
                return {"accepted": True, "duplicate": True, "cursor": prior["cursor"]}
            row = db.execute("SELECT revision,canonical_version_id FROM assets WHERE asset_id=?", (asset_id,)).fetchone()
            current_revision = row["revision"] if row else 0
            expected = payload["expected_revision"] if kind == "canonical" else current_revision
            if expected != current_revision:
                db.execute("ROLLBACK")
                raise ApiError(409, "Asset revision conflict", {
                    "asset_id": asset_id,
                    "server_revision": current_revision,
                    "server_canonical_version_id": row["canonical_version_id"] if row else None,
                })
            # Version metadata is immutable and does not consume a canonical
            # revision. This keeps the client CAS counter aligned with the
            # store's remote_revision field, which advances on canonical picks.
            new_revision = current_revision + 1 if kind == "canonical" else current_revision
            if kind == "version":
                version = payload
                blob = self._blob_path(version["sha256"])
                if not blob.exists():
                    db.execute("ROLLBACK")
                    raise ApiError(409, "Upload the version blob before its event")
                if blob.stat().st_size != version["byte_size"]:
                    db.execute("ROLLBACK")
                    raise ApiError(400, "Version byte size does not match blob")
                blob_body = blob.read_bytes()
                if hashlib.sha256(blob_body).hexdigest() != version["sha256"]:
                    db.execute("ROLLBACK")
                    raise ApiError(409, "Stored blob failed SHA-256 verification")
                info = _image_info(blob_body)
                if info is None or info[0] != version["mime"] or info[1] != (version["width"], version["height"]):
                    db.execute("ROLLBACK")
                    raise ApiError(400, "Version MIME or dimensions do not match blob")
                if db.execute("SELECT 1 FROM versions WHERE version_id=?", (version["version_id"],)).fetchone():
                    db.execute("ROLLBACK")
                    raise ApiError(409, "Version id already exists")
                if version.get("parent_version_id") and not db.execute("SELECT 1 FROM versions WHERE version_id=? AND asset_id=?", (version["parent_version_id"], asset_id)).fetchone():
                    db.execute("ROLLBACK")
                    raise ApiError(409, "Parent version is not present on this asset")
                if row is None:
                    db.execute("INSERT INTO assets(asset_id,revision) VALUES(?,?)", (asset_id, new_revision))
                db.execute("INSERT INTO versions(version_id,asset_id,metadata) VALUES(?,?,?)", (version["version_id"], asset_id, _json_bytes(version)))
            else:
                if row is None or not db.execute("SELECT 1 FROM versions WHERE version_id=? AND asset_id=?", (payload["version_id"], asset_id)).fetchone():
                    db.execute("ROLLBACK")
                    raise ApiError(409, "Canonical version is not present on this asset")
                db.execute("UPDATE assets SET revision=?,canonical_title=COALESCE(?,canonical_title),canonical_version_id=?,canonical_event_id=? WHERE asset_id=?", (new_revision, payload.get("canonical_title"), payload["version_id"], event_id, asset_id))
            db.execute("INSERT INTO events(event_id,kind,payload,payload_hash,asset_id,asset_revision,received_at) VALUES(?,?,?,?,?,?,?)", (event_id, kind, encoded, digest, asset_id, new_revision, now))
            cursor = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.execute("COMMIT")
            return {"accepted": True, "duplicate": False, "cursor": cursor, "revision": new_revision}

    def events_after(self, after: int, limit: int) -> dict[str, Any]:
        with self._connect() as db:
            rows = db.execute("SELECT cursor,event_id,kind,payload,asset_revision FROM events WHERE cursor>? ORDER BY cursor LIMIT ?", (after, limit)).fetchall()
            latest = db.execute("SELECT COALESCE(MAX(cursor),0) FROM events").fetchone()[0]
        events = [{"cursor": r["cursor"], "event_id": r["event_id"], "kind": r["kind"], "payload": json.loads(r["payload"]), "revision": r["asset_revision"]} for r in rows]
        return {"events": events, "next_cursor": events[-1]["cursor"] if events else after, "latest_cursor": latest}

    @staticmethod
    def month_period() -> str:
        now = datetime.now(timezone.utc)
        try:
            now = now.astimezone(ZoneInfo("Australia/Brisbane"))
        except ZoneInfoNotFoundError:
            pass  # UTC fallback is documented for minimal Python installations.
        return now.strftime("%Y-%m")

    def budget_snapshot(self, limit_cents: int) -> dict[str, Any]:
        period = self.month_period()
        with self._connect() as db:
            rows = db.execute("SELECT state,amount_cents,COALESCE(actual_cents,0) actual_cents FROM budget_reservations WHERE period=?", (period,)).fetchall()
        reserved = sum(r["amount_cents"] for r in rows if r["state"] in ("pending", "uncertain"))
        committed = sum(r["actual_cents"] for r in rows if r["state"] == "committed")
        uncertain = sum(r["amount_cents"] for r in rows if r["state"] == "uncertain")
        return {"period": period, "limit_cents": limit_cents, "reserved_cents": reserved,
                "spent_or_uncertain_cents": committed + uncertain,
                "available_cents": max(0, limit_cents - committed - reserved)}

    def reserve_budget(self, operation_id: str, amount: int, limit_cents: int) -> dict[str, Any]:
        if not EVENT_ID_RE.fullmatch(operation_id) or isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ApiError(400, "Invalid operation id or amount")
        period = self.month_period()
        now = datetime.now(timezone.utc).isoformat()
        with self.lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT amount_cents,period,state FROM budget_reservations WHERE operation_id=?", (operation_id,)).fetchone()
            if prior:
                if prior["amount_cents"] != amount or prior["period"] != period:
                    db.execute("ROLLBACK")
                    raise ApiError(409, "Operation id already reserved differently")
                db.execute("COMMIT")
                return {"operation_id": operation_id, "amount_cents": amount, "period": period, "state": prior["state"], "duplicate": True}
            snapshot = db.execute("SELECT COALESCE(SUM(CASE WHEN state IN ('pending','uncertain') THEN amount_cents WHEN state='committed' THEN COALESCE(actual_cents,amount_cents) ELSE 0 END),0) FROM budget_reservations WHERE period=?", (period,)).fetchone()[0]
            if snapshot + amount > limit_cents:
                db.execute("ROLLBACK")
                raise ApiError(409, "Monthly budget allowance exhausted")
            db.execute("INSERT INTO budget_reservations(operation_id,amount_cents,period,state,updated_at) VALUES(?,?,?,'pending',?)", (operation_id, amount, period, now))
            db.execute("COMMIT")
            return {"operation_id": operation_id, "amount_cents": amount, "period": period, "state": "pending", "duplicate": False}

    def update_reservation(self, operation_id: str, action: str, actual: Any = None) -> dict[str, Any]:
        if not EVENT_ID_RE.fullmatch(operation_id):
            raise ApiError(400, "Invalid operation id")
        if action == "commit" and actual is not None and (isinstance(actual, bool) or not isinstance(actual, int) or actual < 0):
            raise ApiError(400, "actual_cents must be a non-negative integer")
        with self.lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state,amount_cents,actual_cents FROM budget_reservations WHERE operation_id=?", (operation_id,)).fetchone()
            if row is None:
                db.execute("ROLLBACK")
                raise ApiError(404, "Reservation not found")
            current = row["state"]
            if action == "commit":
                if actual is not None and actual != row["amount_cents"]:
                    db.execute("ROLLBACK")
                    raise ApiError(409, "Successful operations consume their full reserved allocation")
                if current == "committed":
                    requested = row["amount_cents"] if actual is None else actual
                    if requested != row["actual_cents"]:
                        db.execute("ROLLBACK")
                        raise ApiError(409, "Committed estimate cannot be changed")
                    db.execute("COMMIT")
                    return {"operation_id": operation_id, "state": "committed", "duplicate": True}
                state = "committed"
                # This is the caller's conservative AUD allocation estimate,
                # not a provider invoice or currency-conversion receipt.
                allocation = row["amount_cents"]
                db.execute("UPDATE budget_reservations SET state=?,actual_cents=?,updated_at=? WHERE operation_id=?", (state, allocation, datetime.now(timezone.utc).isoformat(), operation_id))
            elif action == "uncertain":
                if current == "committed":
                    db.execute("ROLLBACK")
                    raise ApiError(409, "A committed reservation cannot become uncertain")
                if current == "uncertain":
                    db.execute("COMMIT")
                    return {"operation_id": operation_id, "state": "uncertain", "duplicate": True}
                state = "uncertain"
                db.execute("UPDATE budget_reservations SET state=?,updated_at=? WHERE operation_id=?", (state, datetime.now(timezone.utc).isoformat(), operation_id))
            elif action == "release":
                if current != "pending":
                    db.execute("ROLLBACK")
                    raise ApiError(409, "Only a known unsubmitted pending reservation can be released")
                state = "released"
                db.execute("UPDATE budget_reservations SET state=?,updated_at=? WHERE operation_id=?", (state, datetime.now(timezone.utc).isoformat(), operation_id))
            else:
                db.execute("ROLLBACK")
                raise ApiError(400, "Unsupported reservation action")
            db.execute("COMMIT")
            return {"operation_id": operation_id, "state": state}


def _image_info(body: bytes) -> tuple[str, tuple[int, int]] | None:
    try:
        from PIL import Image
        import io
        with Image.open(io.BytesIO(body)) as image:
            image_format, dimensions = image.format, image.size
            image.verify()
    except Exception:
        return None
    mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}.get(image_format)
    if mime not in ALLOWED_MIME or dimensions[0] <= 0 or dimensions[1] <= 0 or dimensions[0] * dimensions[1] > 16_000_000:
        return None
    return mime, dimensions


class MediaRequestHandler(BaseHTTPRequestHandler):
    server: "MediaHTTPServer"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Do not log request headers, bodies, event metadata, or bearer tokens.
        return

    def _send(self, status: int, body: bytes = b"", content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json(self, status: int, value: Any) -> None:
        self._send(status, _json_bytes(value))

    def _auth(self) -> bool:
        supplied = self.headers.get("Authorization", "")
        valid = supplied.startswith("Bearer ") and hmac.compare_digest(supplied[7:].encode("utf-8"), self.server.library.token)
        if not valid:
            self._json(401, {"error": "Authentication required"})
        return valid

    def _read_body(self, max_bytes: int) -> bytes:
        length = self.headers.get("Content-Length")
        try:
            n = int(length or "")
        except ValueError:
            raise ApiError(400, "Content-Length required")
        if n < 0 or n > max_bytes:
            raise ApiError(413, "Request body too large")
        return self.rfile.read(n)

    def _handle(self, method: str) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        if method == "GET" and path == "/health":
            return self._json(200, {"status": "ok"})
        if path == "/v1/capabilities" and method == "GET":
            if not self._auth(): return
            return self._json(200, {"service": "media-library", "version": 1, "max_blob_bytes": MAX_BLOB_BYTES, "event_kinds": ["version", "canonical"], "budget": True})
        if not self._auth(): return
        try:
            if method == "PUT" and path.startswith("/v1/blobs/"):
                digest = path.rsplit("/", 1)[-1]
                content_type = self.headers.get("Content-Type", "")
                body = self._read_body(MAX_BLOB_BYTES)
                created = self.server.library.put_blob(digest, body, content_type)
                return self._json(201 if created else 200, {"sha256": digest, "byte_size": len(body), "stored": True, "duplicate": not created})
            if method == "GET" and path.startswith("/v1/blobs/"):
                body, mime = self.server.library.get_blob(path.rsplit("/", 1)[-1])
                return self._send(200, body, mime)
            if method == "POST" and path == "/v1/events":
                raw = self._read_body(MAX_EVENT_BYTES)
                try: event = json.loads(raw)
                except (UnicodeDecodeError, json.JSONDecodeError): raise ApiError(400, "Invalid JSON")
                return self._json(200, self.server.library.accept_event(event))
            if method == "GET" and path == "/v1/events":
                q = parse_qs(parsed.query)
                after = int(q.get("after", ["0"])[0]); limit = int(q.get("limit", ["100"])[0])
                if after < 0 or not 1 <= limit <= 500: raise ApiError(400, "Invalid cursor or limit")
                return self._json(200, self.server.library.events_after(after, limit))
            if method == "GET" and path == "/v1/budget":
                return self._json(200, self.server.library.budget_snapshot(self.server.budget_limit_cents))
            if method == "POST" and path == "/v1/budget/reservations":
                try: value = json.loads(self._read_body(4096))
                except (UnicodeDecodeError, json.JSONDecodeError): raise ApiError(400, "Invalid JSON")
                if not isinstance(value, dict) or set(value) != {"operation_id", "amount_cents"}: raise ApiError(400, "Invalid reservation schema")
                return self._json(200, self.server.library.reserve_budget(value["operation_id"], value["amount_cents"], self.server.budget_limit_cents))
            if method == "POST" and path.startswith("/v1/budget/reservations/"):
                parts = path.strip("/").split("/")
                if len(parts) != 5: raise ApiError(404, "Not found")
                operation_id, action = parts[3], parts[4]
                try: value = json.loads(self._read_body(4096)) if self.headers.get("Content-Length", "0") != "0" else {}
                except (UnicodeDecodeError, json.JSONDecodeError): raise ApiError(400, "Invalid JSON")
                if not isinstance(value, dict) or set(value) - {"actual_cents"}: raise ApiError(400, "Invalid update schema")
                if (action == "commit" and set(value) not in (set(), {"actual_cents"})) or (action != "commit" and value):
                    raise ApiError(400, "Invalid reservation action schema")
                return self._json(200, self.server.library.update_reservation(operation_id, action, value.get("actual_cents")))
            raise ApiError(404, "Not found")
        except ApiError as exc:
            return self._json(exc.status, {"error": exc.message, **exc.details})
        except (ValueError, TypeError, OverflowError):
            return self._json(400, {"error": "Invalid request"})

    do_GET = lambda self: self._handle("GET")
    do_POST = lambda self: self._handle("POST")
    do_PUT = lambda self: self._handle("PUT")


class MediaHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], library: MediaLibrary, budget_limit_cents: int = 3000):
        self.library = library
        self.budget_limit_cents = budget_limit_cents
        super().__init__(address, MediaRequestHandler)


def create_server(host: str | None = None, port: int | None = None, token: str | None = None, data_dir: str | Path | None = None, budget_limit_cents: int | None = None) -> MediaHTTPServer:
    token = token if token is not None else os.environ.get("MEDIA_SERVER_TOKEN")
    data_dir = data_dir if data_dir is not None else os.environ.get("MEDIA_SERVER_DATA_DIR")
    if not token:
        raise ValueError("Set MEDIA_SERVER_TOKEN before starting the media server")
    if not data_dir:
        raise ValueError("Set MEDIA_SERVER_DATA_DIR before starting the media server")
    if budget_limit_cents is None:
        budget_limit_cents = int(os.environ.get("MEDIA_SERVER_BUDGET_LIMIT_CENTS", "3000"))
    if isinstance(budget_limit_cents, bool) or not isinstance(budget_limit_cents, int) or budget_limit_cents <= 0:
        raise ValueError("MEDIA_SERVER_BUDGET_LIMIT_CENTS must be a positive integer")
    host = host if host is not None else os.environ.get("MEDIA_SERVER_HOST", "127.0.0.1")
    port = port if port is not None else int(os.environ.get("MEDIA_SERVER_PORT", "8765"))
    return MediaHTTPServer((host, port), MediaLibrary(data_dir, token), budget_limit_cents)


def main() -> None:
    parser = argparse.ArgumentParser(description="Private media library sync API")
    parser.add_argument("--host", default=None, help="Defaults to MEDIA_SERVER_HOST or 127.0.0.1")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    server = create_server(args.host, args.port)
    print(f"Media library API listening on {server.server_address[0]}:{server.server_address[1]}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
