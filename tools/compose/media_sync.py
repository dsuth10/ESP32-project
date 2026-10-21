"""Authenticated, retry-safe media sync client for MediaStore."""

from __future__ import annotations

import hashlib
import os
import json
import tempfile
import io
import threading
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import requests


class SyncError(RuntimeError):
    pass


class SyncConflict(SyncError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        self.details = details or {}
        super().__init__(message)


class SyncClient:
    """Synchronise one local MediaStore with a private media API.

    ``local_only`` disables all network activity. Remote access requires both
    explicit ``allow_private_sync=True`` and a non-empty token. A Session with
    environment proxy/netrc discovery disabled is used so bearer credentials
    are sent only to the configured endpoint. Redirects are always disabled.
    """

    def __init__(self, store: Any, base_url: str, token: str | None, *, local_only: bool = False,
                 allow_private_sync: bool = False, timeout: float = 15.0):
        self.store = store
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.local_only = bool(local_only)
        self.allow_private_sync = bool(allow_private_sync)
        self.timeout = timeout
        self._request_lock = threading.RLock()
        self.cancel_event = threading.Event()
        if not self.local_only:
            if not self.allow_private_sync:
                raise ValueError("Private sync requires allow_private_sync=True")
            parsed_url = urlsplit(self.base_url)
            local_hosts = {"127.0.0.1", "localhost", "::1"}
            local_http = parsed_url.scheme == "http" and parsed_url.hostname in local_hosts
            remote_https = parsed_url.scheme == "https" and parsed_url.hostname is not None
            if (not (local_http or remote_https) or parsed_url.username is not None or
                    parsed_url.password is not None or parsed_url.query or parsed_url.fragment):
                raise ValueError("Remote private sync requires HTTPS")
            if not token:
                raise ValueError("A media server bearer token is required")
        self.session = requests.Session()
        self.session.trust_env = False
        if not self.local_only:
            self.session.headers.update({"Authorization": f"Bearer {token}"})

    def _url(self, path: str) -> str:
        return self.base_url + path

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        if self.cancel_event.is_set():
            raise SyncError("Sync stopped")
        try:
            with self._request_lock:
                if self.cancel_event.is_set():
                    raise SyncError("Sync stopped")
                response = self.session.request(method, self._url(path), timeout=self.timeout,
                                               allow_redirects=False, **kwargs)
        except requests.RequestException as exc:
            raise SyncError(f"Media server unavailable: {exc.__class__.__name__}") from exc
        if 300 <= response.status_code < 400:
            raise SyncError("Media server redirected a request; credentials were not forwarded")
        return response

    @staticmethod
    def _json(response: requests.Response) -> dict[str, Any]:
        try:
            value = response.json()
        except (ValueError, requests.JSONDecodeError) as exc:
            raise SyncError(f"Media server returned invalid JSON (HTTP {response.status_code})") from exc
        if not isinstance(value, dict):
            raise SyncError("Media server returned an invalid response")
        return value

    def _raise_for(self, response: requests.Response) -> dict[str, Any]:
        value = self._json(response)
        if response.status_code >= 400:
            message = value.get("error", f"HTTP {response.status_code}")
            if response.status_code == 409:
                raise SyncConflict(str(message), value)
            raise SyncError(str(message))
        return value

    def _ensure_capabilities(self) -> dict[str, Any]:
        return self._raise_for(self._request("GET", "/v1/capabilities"))

    def _read_blob(self, digest: str) -> bytes:
        path = Path(self.store.blob_path(digest))
        body = path.read_bytes()
        if hashlib.sha256(body).hexdigest() != digest:
            raise SyncError(f"Local blob failed SHA-256 verification: {digest}")
        if len(body) > 20 * 1024 * 1024:
            raise SyncError("Local blob exceeds the 20 MiB sync limit")
        return body

    def _upload_event_blob(self, event: dict[str, Any]) -> None:
        payload = event.get("payload")
        if event.get("kind") != "version":
            return
        digest = payload["sha256"]
        body = self._read_blob(digest)
        response = self._request("PUT", f"/v1/blobs/{quote(digest)}", data=body,
                                 headers={"Content-Type": payload["mime"]})
        self._raise_for(response)

    def _download_blob(self, digest: str, expected_size: int, expected_mime: str,
                       expected_dimensions: tuple[int, int]) -> bool:
        # Existing valid local copies are sufficient; the store remains the
        # authority for placing/atomically committing a newly received blob.
        try:
            local = Path(self.store.blob_path(digest))
            body = local.read_bytes()
            if len(body) == expected_size and hashlib.sha256(body).hexdigest() == digest:
                return False
        except (OSError, AttributeError):
            pass
        with self._request_lock:
            response = self._request("GET", f"/v1/blobs/{quote(digest)}", stream=True)
            if response.status_code >= 400:
                self._raise_for(response)
            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                try:
                    if int(content_length) < 0 or int(content_length) > 20 * 1024 * 1024:
                        response.close()
                        raise SyncError("Downloaded blob exceeds the 20 MiB sync limit")
                except ValueError:
                    response.close()
                    raise SyncError("Media server returned an invalid blob length")
            chunks: list[bytes] = []
            total = 0
            try:
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if self.cancel_event.is_set():
                        raise SyncError("Sync stopped")
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > 20 * 1024 * 1024:
                        raise SyncError("Downloaded blob exceeds the 20 MiB sync limit")
                    chunks.append(chunk)
            finally:
                response.close()
        body = b"".join(chunks)
        if len(body) != expected_size or hashlib.sha256(body).hexdigest() != digest:
            raise SyncError(f"Downloaded blob failed integrity checks: {digest}")
        try:
            from PIL import Image
            with Image.open(io.BytesIO(body)) as image:
                image_format = image.format
                dimensions = image.size
                image.verify()
                detected_mime = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}.get(image_format)
        except Exception as exc:
            raise SyncError(f"Downloaded blob is not a valid supported image: {digest}") from exc
        if (detected_mime != response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                or detected_mime != expected_mime or dimensions != expected_dimensions):
            raise SyncError(f"Downloaded blob MIME type did not match its contents: {digest}")
        target = Path(self.store.blob_path(digest))
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".sync-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return True

    def _cursor(self) -> int:
        value = self.store.get_sync_cursor()
        if value in (None, ""):
            return 0
        try:
            cursor = int(value)
        except (TypeError, ValueError) as exc:
            raise SyncError("Local sync cursor is invalid") from exc
        if cursor < 0:
            raise SyncError("Local sync cursor is invalid")
        return cursor

    def sync_once(self) -> dict[str, Any]:
        if self.local_only:
            return {"uploaded_events": 0, "downloaded_events": 0, "uploaded_blobs": 0,
                    "downloaded_blobs": 0, "conflicts": [], "local_only": True}
        caps = self._ensure_capabilities()
        if caps.get("service") != "media-library" or caps.get("version") != 1:
            raise SyncError("Unsupported media library server contract")
        allowed_kinds = set(caps.get("event_kinds", []))
        pending = self.store.pending_events()
        result: dict[str, Any] = {"uploaded_events": 0, "downloaded_events": 0,
                                  "uploaded_blobs": 0, "downloaded_blobs": 0,
                                  "conflicts": [], "local_only": False}
        for event in pending:
            if event.get("kind") not in allowed_kinds:
                result["conflicts"].append({"event_id": event.get("event_id"), "reason": "unsupported_event_kind"})
                continue
            try:
                if event.get("kind") == "version":
                    self._upload_event_blob(event)
                    result["uploaded_blobs"] += 1
                response = self._request("POST", "/v1/events", json=event)
                body = self._raise_for(response)
                if body.get("accepted") is not True:
                    raise SyncError("Server did not acknowledge the event")
                self.store.mark_event_synced(event["event_id"])
                result["uploaded_events"] += 1
            except SyncConflict as exc:
                # Local outbox entry remains pending and its candidate remains
                # durable and blocked for the UI's explicit conflict workflow.
                record = getattr(self.store, "record_sync_conflict", None)
                if callable(record):
                    details = exc.details
                    record(event_id=event.get("event_id"),
                           server_revision=details.get("server_revision"),
                           server_canonical_version_id=details.get("server_canonical_version_id"),
                           reason=str(exc))
                result["conflicts"].append({"event_id": event.get("event_id"), "reason": str(exc), **exc.details})

        cursor = self._cursor()
        while True:
            page = self._raise_for(self._request("GET", f"/v1/events?after={cursor}&limit=200"))
            events = page.get("events")
            if (not isinstance(events, list) or len(events) > 200 or
                    not {"next_cursor", "latest_cursor"}.issubset(page)):
                raise SyncError("Server returned malformed event page")
            start_cursor = cursor
            for event in events:
                event_cursor = event.get("cursor") if isinstance(event, dict) else None
                if type(event_cursor) is not int or event_cursor <= cursor:
                    raise SyncError("Server returned malformed event")
                payload = event.get("payload")
                if event.get("kind") == "version":
                    if not isinstance(payload, dict):
                        raise SyncError("Server returned malformed version")
                    if self._download_blob(payload["sha256"], payload["byte_size"], payload["mime"],
                                           (payload["width"], payload["height"])):
                        result["downloaded_blobs"] += 1
                applied = self.store.apply_remote_event(event)
                # Store implementations may return False for an already
                # applied id; the cursor still advances after durable dedupe.
                if applied is False:
                    pass
                self.store.set_sync_cursor(str(event_cursor))
                cursor = event_cursor
                result["downloaded_events"] += 1
            next_cursor = page.get("next_cursor", cursor)
            latest_cursor = page.get("latest_cursor", cursor)
            if type(next_cursor) is not int or type(latest_cursor) is not int or latest_cursor < cursor:
                raise SyncError("Server returned an invalid event cursor")
            if events and next_cursor != cursor:
                raise SyncError("Server event page cursor does not match its last event")
            if not events and next_cursor != start_cursor:
                raise SyncError("Server advanced the event cursor without an event")
            if not events and cursor < latest_cursor:
                raise SyncError("Server omitted events before its latest cursor")
            if not events or cursor >= latest_cursor:
                break
            if cursor <= start_cursor:
                raise SyncError("Server event page did not advance the cursor")
        return result

    def budget_status(self) -> dict[str, Any]:
        if self.local_only:
            raise SyncError("Shared budget is unavailable in local-only mode")
        return self._raise_for(self._request("GET", "/v1/budget"))

    def reserve_budget(self, operation_id: str, amount_cents: int) -> dict[str, Any]:
        if self.local_only:
            raise SyncError("Shared budget is unavailable in local-only mode")
        response = self._request("POST", "/v1/budget/reservations",
                                  json={"operation_id": operation_id, "amount_cents": amount_cents})
        return self._raise_for(response)

    def commit_budget(self, operation_id: str, amount_cents: int | None = None) -> dict[str, Any]:
        if self.local_only:
            raise SyncError("Shared budget is unavailable in local-only mode")
        # This ledger records the conservative AUD estimate allocation, not a
        # provider invoice or currency conversion. By default, consume exactly
        # the amount previously reserved for this operation.
        body = {} if amount_cents is None else {"actual_cents": amount_cents}
        response = self._request("POST", f"/v1/budget/reservations/{quote(operation_id)}/commit",
                                  json=body)
        return self._raise_for(response)

    def release_budget(self, operation_id: str) -> dict[str, Any]:
        if self.local_only:
            raise SyncError("Shared budget is unavailable in local-only mode")
        response = self._request("POST", f"/v1/budget/reservations/{quote(operation_id)}/release", json={})
        return self._raise_for(response)

    def mark_budget_uncertain(self, operation_id: str) -> dict[str, Any]:
        if self.local_only:
            raise SyncError("Shared budget is unavailable in local-only mode")
        return self._raise_for(self._request("POST", f"/v1/budget/reservations/{quote(operation_id)}/uncertain", json={}))

    def close(self) -> None:
        """Release the underlying HTTP connection pool after sync stops."""
        with self._request_lock:
            self.session.close()
