from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TIMEOUT_SECONDS = 12
EVENT_TIMEOUT_SECONDS = 8
MAX_RESPONSE_BYTES = 2_000_000
MAX_EVENT_BYTES = 1_000_000
MAX_TASK_BYTES = 200_000
MAX_CONTEXT_BYTES = 200_000
MAX_EVENTS = 1000
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,160}$")
_TERMINAL = {"completed", "failed", "cancelled", "canceled", "interrupted", "succeeded", "success", "finished", "done"}
_NONTERMINAL = {"prepared", "dispatching", "uncertain", "queued", "running", "awaiting_approval", "stopping", "unknown"}


class HermesServiceError(Exception):
    """Base class for safe-to-display service errors."""


class HermesHTTPError(HermesServiceError):
    def __init__(self, status: int):
        self.status = status
        super().__init__(f"Hermes returned HTTP {status}.")


class HermesTransportError(HermesServiceError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _clean_text(value: Any, limit: int = 20_000) -> str:
    if not isinstance(value, str):
        return ""
    return value[:limit]


def _config_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on", "enabled"}
    return False


def _json_write_exclusive(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _json_write_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


class HermesService:
    """Durable, bounded adapter for explicitly requested Hermes runs.

    Request records contain the selected task and optional selected context only.
    History is never read or appended by this service.
    """

    def __init__(self, config: dict, root: Path):
        self.root = Path(root)
        self.requests_dir = self.root / "hermes-runs"
        self.requests_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._closed = False
        self._capabilities: dict = {}
        self.config = self._validated_config(config)
        self._recover_dispatch_states()

    @staticmethod
    def _validated_config(config: dict) -> dict:
        if not isinstance(config, dict):
            raise ValueError("Hermes settings must be a mapping.")
        enabled = _config_bool(config.get("HERMES_ENABLED", False))
        local_only = _config_bool(config.get("LOCAL_ONLY", False))
        url = str(config.get("HERMES_URL", "")).strip().rstrip("/")
        token = str(config.get("HERMES_TOKEN", ""))
        if url:
            parsed = urllib.parse.urlsplit(url)
            loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
                raise ValueError("Hermes URL must use HTTPS; HTTP is allowed only for loopback fixtures.")
            if not parsed.netloc or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
                raise ValueError("Hermes URL must be an origin without credentials, path, query or fragment.")
            if parsed.port is not None and not (0 < parsed.port < 65536):
                raise ValueError("Hermes URL has an invalid port.")
        return {
            "HERMES_ENABLED": enabled,
            "HERMES_URL": url,
            "HERMES_TOKEN": token,
            "LOCAL_ONLY": local_only,
        }

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Hermes service is closed.")

    def _local_only(self) -> bool:
        return bool(self.config.get("LOCAL_ONLY"))

    def _enabled(self) -> bool:
        return bool(self.config.get("HERMES_ENABLED")) and not self._local_only()

    def _base(self) -> str:
        if not self._enabled():
            raise HermesServiceError("Hermes is disabled or local-only mode is active.")
        if not self.config["HERMES_URL"] or not self.config["HERMES_TOKEN"]:
            raise HermesServiceError("Hermes endpoint or credential is not configured.")
        return self.config["HERMES_URL"]

    def _opener(self):
        # Ignore ambient proxy and netrc configuration. Only explicit bearer auth is used.
        return urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPHandler(), urllib.request.HTTPSHandler(), _NoRedirect())

    def _api_call(self, method: str, route: str, payload: dict | None = None, *, idempotency_key: str | None = None, accept: str = "application/json", timeout: float = TIMEOUT_SECONDS, max_bytes: int = MAX_RESPONSE_BYTES) -> tuple[int, Any]:
        self._ensure_open()
        base = self._base()
        if not route.startswith("/") or route.startswith("//"):
            raise ValueError("Invalid Hermes API route.")
        headers = {"Authorization": "Bearer " + self.config["HERMES_TOKEN"], "Accept": accept}
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(base + route, data=body, headers=headers, method=method)
        try:
            with self._opener().open(request, timeout=timeout) as response:
                raw = self._read_sse_bounded(response, max_bytes, timeout) if accept == "text/event-stream" else self._read_bounded(response, max_bytes, timeout)
                if not raw:
                    return response.status, b"" if accept == "text/event-stream" else {}
                if accept == "text/event-stream":
                    return response.status, raw
                try:
                    return response.status, json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    raise HermesTransportError("Hermes returned an invalid response.") from None
        except urllib.error.HTTPError as exc:
            raise HermesHTTPError(exc.code) from None
        except HermesServiceError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            # Do not retain exception strings: they can include private endpoint details.
            reason = getattr(exc, "reason", None)
            if isinstance(exc, TimeoutError) or isinstance(reason, TimeoutError):
                raise HermesTransportError("Hermes request timed out.") from None
            if isinstance(reason, ssl.SSLError) or isinstance(exc, ssl.SSLError):
                raise HermesTransportError("Hermes TLS identity or handshake could not be verified.") from None
            if isinstance(reason, socket.gaierror):
                raise HermesTransportError("Hermes private endpoint name could not be resolved on this network.") from None
            raise HermesTransportError(f"Hermes could not be reached securely ({type(exc).__name__}).") from None

    @staticmethod
    def _read_bounded(response, max_bytes: int, timeout: float) -> bytes:
        deadline = time.monotonic() + timeout
        chunks: list[bytes] = []
        total = 0
        while True:
            if response.isclosed():
                return b"".join(chunks)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if chunks:
                    return b"".join(chunks)
                raise HermesTransportError("Hermes response timed out.")
            sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
            if sock is not None:
                sock.settimeout(remaining)
            response_remaining = getattr(response, "length", None)
            if response_remaining == 0:
                return b"".join(chunks)
            read_size = min(64 * 1024, max_bytes + 1 - total)
            if isinstance(response_remaining, int) and response_remaining > 0:
                read_size = min(read_size, response_remaining)
            chunk = response.read(read_size)
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise HermesTransportError("Hermes response exceeded the configured size limit.")

    @staticmethod
    def _read_sse_bounded(response, max_bytes: int, timeout: float) -> bytes:
        deadline = time.monotonic() + timeout
        chunks: list[bytes] = []
        complete_bytes = 0
        event = ""
        data_lines: list[str] = []
        total = 0
        terminal = {"run.completed", "run.failed", "run.cancelled", "run.interrupted"}
        while total < max_bytes:
            if response.isclosed():
                break
            sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if sock is not None:
                sock.settimeout(remaining)
            try:
                line = response.readline(min(64 * 1024, max_bytes - total))
            except (TimeoutError, socket.timeout):
                break
            if not line:
                break
            chunks.append(line)
            total += len(line)
            decoded = line.decode("utf-8", errors="replace").rstrip("\r\n")
            if decoded.startswith("event:"):
                event = decoded[6:].strip()[:200]
            elif decoded.startswith("data:"):
                data_lines.append(decoded[5:].strip())
            elif decoded == "" and data_lines:
                complete_bytes = total
                try:
                    data = json.loads("\n".join(data_lines))
                except json.JSONDecodeError:
                    data = {}
                name = data.get("event") if isinstance(data, dict) and isinstance(data.get("event"), str) else event
                status = _normal_status(data.get("status")) if isinstance(data, dict) else None
                if name in terminal or status in {"completed", "failed", "cancelled", "interrupted"}:
                    break
                event, data_lines = "", []
        # An incomplete frame cannot establish a terminal state.
        return b"".join(chunks)[:complete_bytes]

    @staticmethod
    def _readiness(data: Any) -> bool | None:
        if not isinstance(data, dict):
            return None
        if data.get("healthy") is True:
            return True
        if data.get("healthy") is False:
            return False
        status = data.get("status")
        if isinstance(status, str):
            return status.casefold() in {"ok", "healthy", "ready"}
        return None

    def test_connection(self) -> dict:
        if self._local_only():
            return {"ok": False, "status": "local_only", "message": "Remote Hermes calls are disabled in local-only mode.", "capabilities": {}}
        if not self.config["HERMES_ENABLED"]:
            return {"ok": False, "status": "disabled", "message": "Hermes integration is disabled.", "capabilities": {}}
        try:
            _, health = self._api_call("GET", "/health")
            ready = self._readiness(health)
        except HermesHTTPError as exc:
            status = "authentication_failed" if exc.status in (401, 403) else "unsupported_api" if exc.status in (404, 405, 501) else "http_error"
            return {"ok": False, "status": status, "message": f"Hermes health check returned HTTP {exc.status}.", "capabilities": {}}
        except HermesServiceError as exc:
            return {"ok": False, "status": _transport_status(exc), "message": str(exc), "capabilities": {}}
        if ready is not True:
            state = "degraded" if ready is False else "unknown_readiness"
            return {"ok": False, "status": state, "message": "Hermes responded, but readiness was not confirmed.", "capabilities": {}}
        try:
            _, capabilities = self._api_call("GET", "/v1/capabilities")
        except HermesHTTPError as exc:
            if exc.status in (404, 405, 501):
                return {"ok": False, "status": "unsupported_api", "message": "Hermes is ready, but its capabilities API is unsupported.", "capabilities": {}}
            if exc.status in (401, 403):
                return {"ok": False, "status": "authentication_failed", "message": f"Hermes capabilities check returned HTTP {exc.status}.", "capabilities": {}}
            return {"ok": False, "status": "http_error", "message": f"Hermes capabilities check returned HTTP {exc.status}.", "capabilities": {}}
        except HermesServiceError as exc:
            return {"ok": False, "status": _transport_status(exc), "message": str(exc), "capabilities": {}}
        if not isinstance(capabilities, dict):
            return {"ok": False, "status": "unsupported_api", "message": "Hermes returned an unsupported capabilities response.", "capabilities": {}}
        features = capabilities.get("features", {})
        if capabilities.get("platform") != "hermes-agent" or not isinstance(features, dict):
            return {"ok": False, "status": "unsupported_api", "message": "The authenticated endpoint did not identify a supported Hermes API.", "capabilities": self._safe_capabilities(capabilities)}
        has_submit = features.get("run_submission") is True or features.get("async_runs") is True
        has_status = features.get("run_status") is True or features.get("async_runs") is True
        if not has_submit or not has_status:
            return {"ok": False, "status": "unsupported_api", "message": "This Hermes API does not advertise the required run submission and status routes.", "capabilities": self._safe_capabilities(capabilities)}
        self._capabilities = dict(features)
        return {"ok": True, "status": "ready", "message": "Hermes is ready.", "capabilities": self._safe_capabilities(capabilities)}

    @staticmethod
    def _safe_capabilities(data: dict) -> dict:
        result = {}
        for key in ("platform", "version", "features", "models", "toolsets"):
            value = data.get(key)
            if isinstance(value, str):
                result[key] = value[:500]
            elif isinstance(value, list):
                result[key] = [_clean_text(item, 200) for item in value[:100] if isinstance(item, str)]
            elif isinstance(value, dict):
                result[key] = {str(k)[:100]: (v if isinstance(v, (bool, int, float)) else _clean_text(v, 200)) for k, v in list(value.items())[:100]}
        return result

    def _folder(self, request_id: str) -> Path:
        if not isinstance(request_id, str) or not _ID_RE.fullmatch(request_id):
            raise ValueError("Invalid Hermes request identity.")
        folder = self.requests_dir / request_id
        if not folder.is_dir():
            raise FileNotFoundError("Hermes request was not found.")
        return folder

    def _load(self, request_id: str) -> dict:
        folder = self._folder(request_id)
        try:
            data = json.loads((folder / "request.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise HermesServiceError("Saved Hermes request is unreadable.") from None
        if data.get("request_id") != request_id or not isinstance(data.get("payload"), dict):
            raise HermesServiceError("Saved Hermes request identity is invalid.")
        if hashlib.sha256(_canonical(data["payload"])).hexdigest() != data.get("payload_sha256"):
            raise HermesServiceError("Saved Hermes request was changed; refusing to dispatch.")
        if "task" in data or "context" in data:
            selection = {"task": data.get("task", ""), "context": data.get("context", "")}
            if hashlib.sha256(_canonical(selection)).hexdigest() != data.get("selection_sha256"):
                raise HermesServiceError("Saved Hermes task selection was changed; refusing to dispatch.")
        return data

    def _state(self, request_id: str) -> dict:
        folder = self._folder(request_id)
        try:
            return json.loads((folder / "state.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            request = self._load(request_id)
            return {"request_id": request_id, "status": "prepared", "message": "Prepared; awaiting explicit submission.", "created_utc": request["created_utc"], "updated_utc": request["created_utc"]}
        except (OSError, json.JSONDecodeError):
            return {"request_id": request_id, "status": "uncertain", "message": "Saved request state is unreadable; manual review is required."}

    def _save_state(self, request_id: str, status: str, message: str, **fields) -> dict:
        previous = self._state(request_id)
        # Stream history and transport failures cannot reopen an observed terminal
        # run or replace its retained result with a connection error.
        if previous.get("status") in _TERMINAL and status != previous["status"]:
            fields["observation_status"] = status
            fields.pop("text", None)
            status = previous["status"]
        view = {**previous, **fields, "request_id": request_id, "status": status, "message": message, "updated_utc": _now()}
        _json_write_atomic(self._folder(request_id) / "state.json", view)
        return view

    def _recover_dispatch_states(self) -> None:
        # A process restart after dispatch started but before a receipt is ambiguous.
        for folder in self.requests_dir.iterdir():
            if not folder.is_dir() or not _ID_RE.fullmatch(folder.name):
                continue
            try:
                state = json.loads((folder / "state.json").read_text(encoding="utf-8"))
            except (FileNotFoundError, OSError, json.JSONDecodeError):
                continue
            if state.get("status") == "dispatching" and not (folder / "run-response.json").exists():
                self._save_state(folder.name, "uncertain", "Dispatch outcome is uncertain after restart; a saved dispatch lock requires manual reconciliation before retry.")

    def prepare(self, task: str, context: str = "") -> dict:
        self._ensure_open()
        if not isinstance(task, str) or not task.strip():
            raise ValueError("Hermes task is empty.")
        if len(task.encode("utf-8")) > MAX_TASK_BYTES:
            raise ValueError("Hermes task exceeds the 200 kB limit.")
        if not isinstance(context, str):
            raise ValueError("Hermes context must be text.")
        if len(context.encode("utf-8")) > MAX_CONTEXT_BYTES:
            raise ValueError("Hermes context exceeds the 200 kB limit.")
        selected_task = task.strip()
        selected_context = context.strip()
        payload = {"input": selected_task + (("\n\nSelected context:\n" + selected_context) if selected_context else "")}
        request_id = str(uuid.uuid4())
        created = _now()
        selection = {"task": selected_task, "context": selected_context}
        record = {"request_id": request_id, **selection, "selection_sha256": hashlib.sha256(_canonical(selection)).hexdigest(), "payload": payload, "payload_sha256": hashlib.sha256(_canonical(payload)).hexdigest(), "created_utc": created}
        with self._lock:
            folder = self.requests_dir / request_id
            folder.mkdir(parents=True, exist_ok=False)
            _json_write_exclusive(folder / "request.json", record)
            view = {"request_id": request_id, "status": "prepared", "message": "Prepared; awaiting explicit submission.", "created_utc": created, "updated_utc": created}
            _json_write_exclusive(folder / "state.json", view)
        return view

    def preview(self, request_id: str) -> dict:
        """Read the immutable saved selection locally without making network calls."""
        self._ensure_open()
        state = self._state(request_id)
        try:
            record = self._load(request_id)
        except HermesServiceError:
            # A locally discarded request intentionally has a tombstone, not a payload.
            try:
                tombstone = json.loads((self._folder(request_id) / "request.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raise HermesServiceError("Saved Hermes request is unreadable.") from None
            if tombstone.get("status") == "cancelled" and state.get("status") == "cancelled":
                return {**state, "task": "", "context": "", "retry_allowed": False, "receipt_exists": False}
            raise
        folder = self._folder(request_id)
        receipt_exists = (folder / "run-response.json").exists()
        lock_exists = (folder / "dispatch.lock").exists()
        binding_path = folder / "dispatch-identity.json"
        same_binding = False
        if binding_path.exists():
            try:
                same_binding = json.loads(binding_path.read_text(encoding="utf-8")).get("fingerprint") == self._fingerprint()
            except (OSError, json.JSONDecodeError):
                same_binding = False
        status = str(state.get("status", "unknown")).casefold()
        retry_allowed = (
            status == "prepared" and not any((folder / name).exists() for name in ("dispatch-identity.json", "dispatch.lock", "run-response.json"))
        ) or (
            status in {"uncertain", "http_error"} and same_binding and not lock_exists and not receipt_exists
        )
        return {**state, "request_id": request_id, "task": record.get("task", record["payload"].get("input", "")), "context": record.get("context", ""), "retry_allowed": retry_allowed, "receipt_exists": receipt_exists}

    def discard(self, request_id: str) -> dict:
        """Discard only a prepared local request that has never entered dispatch."""
        self._ensure_open()
        folder = self._folder(request_id)
        state = self._state(request_id)
        if state.get("status") != "prepared":
            raise HermesServiceError("Only an undispatched prepared request can be discarded.")
        if any((folder / name).exists() for name in ("dispatch-identity.json", "dispatch.lock", "run-response.json")):
            raise HermesServiceError("This request has dispatch evidence and cannot be discarded locally.")
        record = self._load(request_id)
        tombstone = {"request_id": request_id, "status": "cancelled", "discarded_utc": _now()}
        _json_write_atomic(folder / "request.json", tombstone)
        return self._save_state(request_id, "cancelled", "Prepared request discarded locally before dispatch.", run_id=None, receipt_exists=False)

    def _fingerprint(self) -> str:
        return hashlib.sha256((self.config["HERMES_URL"] + "\0" + self.config["HERMES_TOKEN"]).encode("utf-8")).hexdigest()

    def _bind_identity(self, folder: Path) -> None:
        path = folder / "dispatch-identity.json"
        fingerprint = self._fingerprint()
        value = {"fingerprint": fingerprint, "runs_idempotency": self._capabilities.get("runs_idempotency") is True, "created_utc": _now()}
        try:
            _json_write_exclusive(path, value)
        except FileExistsError:
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raise HermesServiceError("Saved dispatch identity is unreadable; refusing another attempt.") from None
            if saved.get("fingerprint") != fingerprint:
                raise HermesServiceError("This request is bound to another endpoint or credential; refusing dispatch.")

    def submit(self, request_id: str) -> dict:
        self._ensure_open()
        if self._local_only():
            return {**self._state(request_id), "status": "local_only", "message": "Remote Hermes dispatch is disabled in local-only mode."}
        folder = self._folder(request_id)
        receipt = folder / "run-response.json"
        if receipt.exists():
            current = self._state(request_id)
            if current.get("run_id"):
                return current
            try:
                saved = json.loads(receipt.read_text(encoding="utf-8"))
                response = saved.get("response", {})
            except (OSError, json.JSONDecodeError):
                return self._save_state(request_id, "uncertain", "A dispatch receipt exists but is unreadable; refusing redispatch.")
            return self._save_state(request_id, _normal_status(response.get("status")) or "unknown", _message(response), text=_message(response), run_id=_valid_remote_id(response.get("run_id"), "run_id"), receipt_exists=True)
        current = self._state(request_id)
        if current.get("status") in _TERMINAL:
            return current
        try:
            self._load(request_id)
        except HermesServiceError as exc:
            self._record_error(request_id, "uncertain", str(exc))
            return self._state(request_id)
        if not self._capabilities:
            connection = self.test_connection()
            if not connection.get("ok"):
                return {**current, "status": connection["status"], "message": connection["message"]}
        if self._capabilities.get("runs_idempotency") is not True:
            return {**current, "status": "unsupported_api", "message": "Hermes does not advertise durable run idempotency; dispatch is disabled to prevent duplicate runs."}
        try:
            lock_fd = os.open(str(folder / "dispatch.lock"), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return self._save_state(request_id, "uncertain", "Dispatch is already in progress or needs manual recovery; do not create a new request identity.")
        os.close(lock_fd)
        try:
            if receipt.exists():
                return self._state(request_id)
            self._load(request_id)
            self._bind_identity(folder)
            self._save_state(request_id, "dispatching", "Sending the explicitly prepared request.")
            _, response = self._api_call("POST", "/v1/runs", self._load(request_id)["payload"], idempotency_key=request_id, timeout=TIMEOUT_SECONDS)
            if not isinstance(response, dict):
                raise HermesTransportError("Hermes returned an unsupported run response.")
            receipt_data = {"request_id": request_id, "response": response, "received_utc": _now()}
            _json_write_exclusive(receipt, receipt_data)
            run_id = _valid_remote_id(response.get("run_id"), "run_id")
            status = _normal_status(response.get("status")) or "unknown"
            return self._save_state(request_id, status, _message(response) or "Hermes accepted the request.", text=_message(response), run_id=run_id, receipt_exists=True)
        except HermesHTTPError as exc:
            self._record_error(request_id, "http_error", f"Hermes dispatch returned HTTP {exc.status}.")
            return self._state(request_id)
        except HermesServiceError as exc:
            # Any failure after dispatch begins is treated as uncertain, including malformed or oversized replies.
            self._record_error(request_id, "uncertain", str(exc))
            return self._state(request_id)
        finally:
            try:
                (folder / "dispatch.lock").unlink()
            except FileNotFoundError:
                pass

    def _record_error(self, request_id: str, status: str, message: str) -> None:
        folder = self._folder(request_id)
        name = f"error-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}.json"
        _json_write_exclusive(folder / name, {"request_id": request_id, "status": status, "message": message, "recorded_utc": _now()})
        self._save_state(request_id, status, message)

    def _request_for_run(self, request_id: str) -> tuple[dict, str]:
        self._load(request_id)
        folder = self._folder(request_id)
        try:
            receipt = json.loads((folder / "run-response.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise HermesServiceError("This request has no run receipt; it cannot be polled, stopped or queried for events.") from None
        except (OSError, json.JSONDecodeError):
            raise HermesServiceError("Saved Hermes run receipt is unreadable.") from None
        response = receipt.get("response")
        run_id = _valid_remote_id(response.get("run_id") if isinstance(response, dict) else None, "run_id")
        if not run_id:
            raise HermesServiceError("Saved Hermes run receipt has no valid run ID.")
        bound = json.loads((folder / "dispatch-identity.json").read_text(encoding="utf-8"))
        if bound.get("fingerprint") != self._fingerprint():
            raise HermesServiceError("This run is bound to another endpoint or credential; refusing remote access.")
        return response, run_id

    def poll(self, request_id: str) -> dict:
        self._ensure_open()
        state = self._state(request_id)
        if self._local_only():
            return {**state, "status": "local_only", "message": "Remote Hermes status checks are disabled in local-only mode."}
        try:
            _, data = self._api_call("GET", "/v1/runs/" + self._request_for_run(request_id)[1])
            if not isinstance(data, dict):
                raise HermesTransportError("Hermes returned an unsupported run status.")
            _json_write_exclusive(self._unique_path(self._folder(request_id), "status"), {"response": data, "received_utc": _now()})
            status = _normal_status(data.get("status")) or "unknown"
            approval = data.get("approval")
            pending_controls = data.get("pending_controls")
            approval_pending = isinstance(approval, dict) or bool(pending_controls)
            message = "Hermes run requires review of a pending approval." if approval_pending else _message(data)
            return self._save_state(request_id, status, message or "Hermes status updated.", text=_message(data), run_id=self._request_for_run(request_id)[1], approval_pending=approval_pending)
        except HermesHTTPError as exc:
            return self._record_and_return(request_id, "http_error", f"Hermes status check returned HTTP {exc.status}.")
        except HermesServiceError as exc:
            return self._record_and_return(request_id, "unavailable", str(exc))

    def events(self, request_id: str) -> dict:
        self._ensure_open()
        state = self._state(request_id)
        if self._local_only():
            return {**state, "status": "local_only", "message": "Remote Hermes event checks are disabled in local-only mode.", "events": []}
        try:
            run_id = self._request_for_run(request_id)[1]
            _, raw = self._api_call("GET", "/v1/runs/" + run_id + "/events", accept="text/event-stream", timeout=EVENT_TIMEOUT_SECONDS, max_bytes=MAX_EVENT_BYTES)
            parsed = _parse_sse(raw)
            _json_write_exclusive(self._unique_path(self._folder(request_id), "events"), {"run_id": run_id, "events": parsed, "received_utc": _now()})
            last_status = next((_normal_status(e.get("event", "").removeprefix("run.")) for e in reversed(parsed) if e.get("event", "").startswith("run.")), None)
            if last_status:
                event_text = next((_message(event.get("data")) for event in reversed(parsed) if _message(event.get("data"))), "")
                return self._save_state(request_id, last_status, event_text or "Hermes event stream updated.", text=event_text, run_id=run_id, event_count=len(parsed), events=parsed)
            return {**state, "events": parsed, "event_count": len(parsed), "message": "Hermes event stream updated."}
        except HermesHTTPError as exc:
            return self._record_and_return(request_id, "http_error", f"Hermes event stream returned HTTP {exc.status}.", events=[])
        except HermesServiceError as exc:
            return self._record_and_return(request_id, "unavailable", str(exc), events=[])

    def stop(self, request_id: str) -> dict:
        self._ensure_open()
        state = self._state(request_id)
        if self._local_only():
            return {**state, "status": "local_only", "message": "Remote Hermes cancellation is disabled in local-only mode."}
        try:
            run_id = self._request_for_run(request_id)[1]
            _, data = self._api_call("POST", "/v1/runs/" + run_id + "/stop", {})
            if not isinstance(data, dict):
                raise HermesTransportError("Hermes returned an unsupported cancellation response.")
            _json_write_exclusive(self._unique_path(self._folder(request_id), "stop"), {"run_id": run_id, "response": data, "received_utc": _now()})
            remote_status = _normal_status(data.get("status"))
            # A stop request is not proof of termination; only a terminal receipt may say stopped.
            status = remote_status if remote_status in _TERMINAL else "stopping"
            return self._save_state(request_id, status, _message(data) or ("Hermes confirmed the run stopped." if status in _TERMINAL else "Cancellation requested; waiting for a terminal receipt."), run_id=run_id)
        except HermesHTTPError as exc:
            return self._record_and_return(request_id, "http_error", f"Hermes cancellation returned HTTP {exc.status}.")
        except HermesServiceError as exc:
            return self._record_and_return(request_id, "uncertain", str(exc))

    def _record_and_return(self, request_id: str, status: str, message: str, **fields) -> dict:
        self._record_error(request_id, status, message)
        return {**self._state(request_id), **fields}

    @staticmethod
    def _unique_path(folder: Path, prefix: str) -> Path:
        return folder / f"{prefix}-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}.json"

    def list_requests(self) -> list[dict]:
        self._ensure_open()
        result = []
        for folder in self.requests_dir.iterdir():
            if not folder.is_dir() or not _ID_RE.fullmatch(folder.name):
                continue
            try:
                result.append(self._state(folder.name))
            except (ValueError, FileNotFoundError, HermesServiceError):
                continue
        result.sort(key=lambda item: item.get("created_utc", ""), reverse=True)
        return result

    def has_pending_requests(self) -> bool:
        return any(str(item.get("status", "unknown")).casefold() not in _TERMINAL for item in self.list_requests())

    def update_config(self, values: dict) -> dict:
        self._ensure_open()
        updated = self._validated_config({**self.config, **values})
        sensitive_changed = any(updated.get(key) != self.config.get(key) for key in ("HERMES_URL", "HERMES_TOKEN"))
        if sensitive_changed and self.has_pending_requests():
            raise HermesServiceError("Cannot change the Hermes endpoint or credential while requests are prepared, uncertain or nonterminal.")
        self.config = updated
        return {key: value for key, value in updated.items() if key != "HERMES_TOKEN"}

    def close(self) -> None:
        with self._lock:
            self._closed = True


def _valid_remote_id(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        return None
    return value


def _normal_status(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    status = value.casefold().replace("-", "_").replace(" ", "_")[:80]
    return status if re.fullmatch(r"[a-z0-9_]+", status) else None


def _message(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    for key in ("message", "text", "output", "result"):
        text = _extract_text(data.get(key))
        if text:
            return text
    return ""


def _extract_text(value: Any, depth: int = 0) -> str:
    if depth > 4:
        return ""
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, list):
        parts = [_extract_text(item, depth + 1) for item in value[:100]]
        return _clean_text("\n".join(part for part in parts if part))
    if isinstance(value, dict):
        for key in ("text", "output", "result", "content", "message"):
            text = _extract_text(value.get(key), depth + 1)
            if text:
                return text
    return ""


def _transport_status(error: HermesServiceError) -> str:
    message = str(error).casefold()
    if "tls" in message:
        return "tls_error"
    if "timed out" in message:
        return "timeout"
    if "name could not be resolved" in message:
        return "endpoint_unresolved"
    return "network_unavailable"


def _parse_sse(raw: bytes) -> list[dict]:
    records: list[dict] = []
    event = ""
    data_lines: list[str] = []
    total = 0
    for line in raw.splitlines():
        total += len(line) + 1
        if total > MAX_EVENT_BYTES or len(records) >= MAX_EVENTS:
            raise HermesTransportError("Hermes event stream exceeded its configured limits.")
        decoded = line.decode("utf-8", errors="replace")
        if decoded.startswith("event:"):
            event = decoded[6:].strip()[:200]
        elif decoded.startswith("data:"):
            data_lines.append(decoded[5:].strip())
        elif not decoded and data_lines:
            joined = "\n".join(data_lines)
            try:
                data = json.loads(joined)
            except json.JSONDecodeError:
                data = {"text": joined[:4000]}
            name = data.get("event") if isinstance(data, dict) and isinstance(data.get("event"), str) else event
            safe = data if isinstance(data, dict) else {"value": _clean_text(str(data), 4000)}
            records.append({"event": _clean_text(name, 200), "data": _limit_event_data(safe)})
            event, data_lines = "", []
    if data_lines and len(records) < MAX_EVENTS:
        joined = "\n".join(data_lines)
        try:
            data = json.loads(joined)
        except json.JSONDecodeError:
            data = {"text": joined[:4000]}
        name = data.get("event") if isinstance(data, dict) and isinstance(data.get("event"), str) else event
        safe = data if isinstance(data, dict) else {"value": _clean_text(str(data), 4000)}
        records.append({"event": _clean_text(name, 200), "data": _limit_event_data(safe)})
    return records


def _limit_event_data(data: dict) -> dict:
    # Keep useful event text/state only, avoiding arbitrary nested payloads or credentials.
    out = {}
    for key in ("event", "status", "message", "text", "output", "result", "run_id", "request_id", "tool", "name", "timestamp"):
        value = data.get(key)
        if isinstance(value, str):
            out[key] = value[:4000]
        elif isinstance(value, (int, float, bool)):
            out[key] = value
        elif isinstance(value, (dict, list)) and key in {"output", "result"}:
            text = _extract_text(value)
            if text:
                out[key] = text
    return out
