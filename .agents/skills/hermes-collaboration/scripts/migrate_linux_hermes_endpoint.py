"""Safely validate and switch the development client's private Hermes origin."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
LOCAL_DIR = PROJECT_ROOT / ".local"
CONFIG_PATH = LOCAL_DIR / "linux-hermes.json"
RUNS_DIR = LOCAL_DIR / "hermes-runs"
TIMEOUT_SECONDS = 12
MAX_RESPONSE_BYTES = 2_000_000
TERMINAL = {"completed", "failed", "cancelled", "canceled", "interrupted", "succeeded", "success", "finished", "done"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


def validate_origin(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("Enter an HTTPS origin only, without credentials, path, query or fragment.")
    try:
        _ = parsed.port
    except ValueError:
        raise ValueError("Endpoint port is invalid.") from None
    if not re.fullmatch(r"[A-Za-z0-9.-]+", parsed.hostname) or parsed.hostname.startswith(".") or parsed.hostname.endswith("."):
        raise ValueError("Endpoint host name is invalid.")
    return urllib.parse.urlunsplit(("https", parsed.netloc, "", "", "")).rstrip("/")


def readiness(payload):
    if not isinstance(payload, dict):
        return False
    if payload.get("healthy") is True:
        return True
    if payload.get("healthy") is False:
        return False
    status = payload.get("status")
    return isinstance(status, str) and status.casefold() in {"healthy", "ok", "ready"}


def authenticated_get(origin: str, key: str, route: str):
    request = urllib.request.Request(origin + route, headers={"Authorization": "Bearer " + key, "Accept": "application/json"}, method="GET")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("Authenticated readiness response exceeded the size limit.")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("Authenticated readiness response has an unexpected shape.")
    return data


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def unresolved_runs(runs_dir: Path):
    unresolved = []
    if not runs_dir.exists():
        return unresolved
    for folder in runs_dir.iterdir():
        if not folder.is_dir() or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", folder.name):
            continue
        if (folder / "dispatch.lock").exists():
            unresolved.append(folder.name)
            continue
        identity_path = folder / "dispatch-identity.json"
        if not identity_path.exists():
            continue
        identity = _read_json(identity_path)
        if not isinstance(identity, dict):
            unresolved.append(folder.name)
            continue
        receipt = _read_json(folder / "run-response.json")
        if not isinstance(receipt, dict):
            # Dispatch identity is persisted before sending; without a receipt the
            # outcome is ambiguous and must be reconciled against the old origin.
            unresolved.append(folder.name)
            continue
        response = receipt.get("response")
        run_id = response.get("run_id") if isinstance(response, dict) else None
        state = response.get("status") if isinstance(response, dict) else None
        observations = []
        evidence_folder = runs_dir / ("run-" + run_id) if isinstance(run_id, str) else folder
        for status_file in sorted(evidence_folder.glob("status-*.json"), key=lambda p: p.stat().st_mtime_ns):
            record = _read_json(status_file)
            data = record.get("response") if isinstance(record, dict) else None
            if isinstance(data, dict) and isinstance(data.get("status"), str):
                observations.append(data["status"])
        for event_file in sorted(evidence_folder.glob("events-*.json"), key=lambda p: p.stat().st_mtime_ns):
            record = _read_json(event_file)
            events = record.get("events", []) if isinstance(record, dict) else []
            for event in events if isinstance(events, list) else []:
                if isinstance(event, dict) and event.get("event") in {"run.completed", "run.failed", "run.cancelled", "run.interrupted"}:
                    observations.append("completed" if event["event"] == "run.completed" else event["event"].split(".", 1)[1])
        if not run_id or not isinstance(state, str):
            unresolved.append(folder.name)
            continue
        latest = observations[-1] if observations else state
        if latest.casefold() not in TERMINAL:
            unresolved.append(folder.name)
    return unresolved


def atomic_write(path: Path, data: bytes):
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def switch(origin: str, key: str, config_path: Path = CONFIG_PATH, runs_dir: Path = RUNS_DIR, backup_dir: Path | None = None):
    origin = validate_origin(origin)
    if not key:
        raise ValueError("No credential supplied on stdin.")
    initial_config_bytes = config_path.read_bytes()
    config = json.loads(initial_config_bytes.decode("utf-8"))
    old = config.get("base_url")
    if not isinstance(old, str):
        raise ValueError("Existing endpoint configuration is invalid.")
    old = old.rstrip("/")
    if old == origin:
        raise ValueError("The requested endpoint is already configured.")
    unresolved = unresolved_runs(runs_dir)
    if unresolved:
        raise RuntimeError("Unresolved Hermes run identities require reconciliation at the current endpoint before migration.")
    health = authenticated_get(origin, key, "/health")
    if not readiness(health):
        raise RuntimeError("Candidate endpoint did not report explicit healthy, ok or ready status.")
    capabilities = authenticated_get(origin, key, "/v1/capabilities")
    if capabilities.get("platform") != "hermes-agent" or not isinstance(capabilities.get("features"), dict):
        raise RuntimeError("Candidate endpoint returned no authenticated capabilities.")

    config["base_url"] = origin
    encoded = (json.dumps(config, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if backup_dir is None:
        backup_dir = config_path.parent / "hermes-endpoint-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_dir / f"linux-hermes-{stamp}-{uuid.uuid4().hex[:8]}.json"
    old_bytes = config_path.read_bytes()
    descriptor = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(old_bytes)
        stream.flush()
        os.fsync(stream.fileno())
    if hashlib.sha256(backup.read_bytes()).digest() != hashlib.sha256(old_bytes).digest():
        backup.unlink(missing_ok=True)
        raise RuntimeError("Private endpoint backup verification failed; configuration was not changed.")
    if config_path.read_bytes() != initial_config_bytes or unresolved_runs(runs_dir):
        backup.unlink(missing_ok=True)
        raise RuntimeError("Configuration or run state changed during readiness check; reconcile and retry.")
    atomic_write(config_path, encoded)
    return backup


def rollback(backup_path: Path, expected_current: str, config_path: Path = CONFIG_PATH, backup_dir: Path | None = None, runs_dir: Path = RUNS_DIR):
    expected_current = validate_origin(expected_current)
    original = json.loads(backup_path.read_text(encoding="utf-8"))
    old_origin = original.get("base_url") if isinstance(original, dict) else None
    if not isinstance(old_origin, str) or urllib.parse.urlsplit(old_origin).scheme not in {"http", "https"}:
        raise ValueError("Private backup does not contain a valid prior endpoint.")
    current = json.loads(config_path.read_text(encoding="utf-8"))
    if current.get("base_url", "").rstrip("/") != expected_current:
        raise RuntimeError("Current endpoint changed; refusing rollback over an unexpected configuration.")
    initial_config_bytes = config_path.read_bytes()
    if unresolved_runs(runs_dir):
        raise RuntimeError("Unresolved Hermes run identities require reconciliation before rollback.")
    backup_dir = backup_dir or config_path.parent / "hermes-endpoint-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    displaced = backup_dir / f"linux-hermes-before-rollback-{stamp}-{uuid.uuid4().hex[:8]}.json"
    current_bytes = config_path.read_bytes()
    descriptor = os.open(displaced, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(current_bytes)
        stream.flush()
        os.fsync(stream.fileno())
    if displaced.read_bytes() != current_bytes:
        displaced.unlink(missing_ok=True)
        raise RuntimeError("Current configuration backup verification failed; rollback was not applied.")
    if config_path.read_bytes() != initial_config_bytes or unresolved_runs(runs_dir):
        displaced.unlink(missing_ok=True)
        raise RuntimeError("Configuration or run state changed during rollback; reconcile and retry.")
    atomic_write(config_path, (json.dumps(original, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return displaced


def main():
    parser = argparse.ArgumentParser(description="Validate and safely migrate the configured Linux Hermes endpoint.")
    parser.add_argument("--endpoint", help="HTTPS origin only; no path or credentials")
    parser.add_argument("--rollback-backup", help="Restore a saved endpoint configuration backup")
    parser.add_argument("--expected-current", help="Required current endpoint guard for rollback")
    args = parser.parse_args()
    try:
        if args.rollback_backup:
            if not args.expected_current:
                raise ValueError("Rollback requires --expected-current.")
            displaced = rollback(Path(args.rollback_backup), args.expected_current)
            print(json.dumps({"rolled_back": True, "displaced_config_backup": str(displaced)}))
            return 0
        if not args.endpoint:
            raise ValueError("--endpoint is required for migration.")
        key = sys.stdin.readline().rstrip("\r\n")
        backup = switch(args.endpoint, key)
        print(json.dumps({"updated": True, "backup_file": str(backup)}))
        return 0
    except urllib.error.HTTPError as exc:
        print(json.dumps({"updated": False, "http_status": exc.code, "automatic_retry": False}), file=sys.stderr)
    except Exception as exc:
        print(json.dumps({"updated": False, "error_type": type(exc).__name__, "automatic_retry": False}), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
