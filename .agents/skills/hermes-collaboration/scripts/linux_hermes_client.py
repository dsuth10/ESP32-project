import argparse
import hashlib
import json
import os
import re
import sys
import time
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
MAX_EVENT_BYTES = 1_000_000
TERMINAL_RUN_STATES = {"completed", "failed", "cancelled", "canceled", "interrupted", "succeeded", "success", "finished", "done"}
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,160}$")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


def stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def exclusive_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(data)


def unique_json(directory, stem, value):
    name = f"{stem}-{stamp()}-{uuid.uuid4().hex[:8]}.json"
    path = directory / name
    exclusive_json(path, value)
    return path


def load_config():
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        base = config["base_url"].rstrip("/")
        parsed = urllib.parse.urlsplit(base)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError()
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError()
        return base
    except Exception:
        raise RuntimeError("Missing or invalid .local/linux-hermes.json configuration.") from None


def get_key():
    key = sys.stdin.readline().rstrip("\r\n")
    if not key:
        raise RuntimeError("No credential supplied on stdin.")
    return key


def opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def api_call(base, key, method, route, payload=None, idempotency_key=None, timeout=TIMEOUT_SECONDS, max_bytes=MAX_RESPONSE_BYTES):
    if not route.startswith("/") or route.startswith("//"):
        raise ValueError("Invalid API route.")
    headers = {"Authorization": "Bearer " + key, "Accept": "application/json"}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(base + route, data=body, headers=headers, method=method)
    try:
        with opener().open(request, timeout=timeout) as response:
            raw = response.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise RuntimeError("API response exceeded the configured size limit.")
            if not raw:
                return response.status, {}
            return response.status, json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Do not retain or print the body: it is untrusted and may contain secrets.
        raise ApiStatus(exc.code) from None


class ApiStatus(Exception):
    def __init__(self, status):
        self.status = status


def request_dir(request_id):
    if not RUN_ID_RE.fullmatch(request_id):
        raise ValueError("Invalid request identity.")
    return RUNS_DIR / request_id


def prepare(args):
    text = Path(args.input_file).read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("Request input is empty.")
    if len(text.encode("utf-8")) > 200_000:
        raise ValueError("Request input exceeds the 200 kB limit.")
    identity = str(uuid.uuid4())
    folder = request_dir(identity)
    folder.mkdir(parents=True, exist_ok=False)
    payload = {"input": text}
    record = {
        "request_id": identity,
        "payload": payload,
        "payload_sha256": hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    exclusive_json(folder / "request.json", record)
    print(json.dumps({"request_id": identity, "request_file": str(folder / "request.json")}, ensure_ascii=False))


def read_request(request_id):
    folder = request_dir(request_id)
    record = json.loads((folder / "request.json").read_text(encoding="utf-8"))
    if record.get("request_id") != request_id or not isinstance(record.get("payload"), dict):
        raise ValueError("Saved request identity does not match.")
    digest = hashlib.sha256(json.dumps(record["payload"], ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    if digest != record.get("payload_sha256"):
        raise ValueError("Saved request was changed; refusing dispatch.")
    return folder, record


def bind_dispatch_identity(folder, base, key):
    """Persist the first endpoint/credential pairing before any dispatch attempt."""
    fingerprint = hashlib.sha256((base + "\0" + key).encode("utf-8")).hexdigest()
    path = folder / "dispatch-identity.json"
    if path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            raise RuntimeError("Saved dispatch identity is unreadable; refusing another attempt.") from None
        if saved.get("fingerprint") != fingerprint:
            raise RuntimeError("This request identity is bound to another configured endpoint or credential; refusing dispatch.")
        return
    try:
        exclusive_json(path, {"fingerprint": fingerprint, "created_utc": datetime.now(timezone.utc).isoformat()})
    except FileExistsError:
        # A concurrent submit may have created it. Re-read and enforce the same binding.
        bind_dispatch_identity(folder, base, key)


def submit(args, base, key):
    folder, record = read_request(args.request_id)
    response_path = folder / "run-response.json"
    if response_path.exists():
        print(json.dumps({"request_id": args.request_id, "already_submitted": True, "response_file": str(response_path)}))
        return
    lock = folder / "dispatch.lock"
    try:
        descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise RuntimeError("A dispatch is already in progress or needs manual recovery; do not start a new request identity.") from None
    os.close(descriptor)
    try:
        if response_path.exists():
            print(json.dumps({"request_id": args.request_id, "already_submitted": True, "response_file": str(response_path)}))
            return
        bind_dispatch_identity(folder, base, key)
        status, data = api_call(
            base, key, "POST", "/v1/runs", record["payload"],
            idempotency_key=args.request_id, timeout=TIMEOUT_SECONDS,
        )
        if not isinstance(data, dict):
            raise RuntimeError("API returned an unexpected response shape.")
        receipt = {"http_status": status, "request_id": args.request_id, "response": data, "received_utc": datetime.now(timezone.utc).isoformat()}
        exclusive_json(response_path, receipt)
        print(json.dumps({"http_status": status, "request_id": args.request_id, "run_id": data.get("run_id"), "status": data.get("status")}))
    except ApiStatus as exc:
        unique_json(folder, "dispatch-http-error", {"request_id": args.request_id, "http_status": exc.status, "retry_identity": args.request_id})
        raise
    except Exception as exc:
        unique_json(folder, "dispatch-error", {"request_id": args.request_id, "error_type": type(exc).__name__, "retry_identity": args.request_id})
        raise
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def check_run_id(run_id):
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError("Invalid run ID.")
    return run_id


def poll(args, base, key):
    run_id = check_run_id(args.run_id)
    status, data = api_call(base, key, "GET", "/v1/runs/" + run_id)
    folder = RUNS_DIR / ("run-" + run_id)
    path = unique_json(folder, "status", {"http_status": status, "run_id": run_id, "response": data, "received_utc": datetime.now(timezone.utc).isoformat()})
    approval = data.get("approval") if isinstance(data, dict) else None
    view = {"http_status": status, "run_id": run_id, "status": data.get("status"), "receipt": str(path)}
    if approval:
        view["approval"] = approval
    print(json.dumps(view, ensure_ascii=False))


def event_name(event, data):
    if isinstance(data, dict) and isinstance(data.get("event"), str):
        return data["event"]
    return event


def events(args, base, key):
    run_id = check_run_id(args.run_id)
    route = "/v1/runs/" + run_id + "/events"
    request = urllib.request.Request(base + route, headers={"Authorization": "Bearer " + key, "Accept": "text/event-stream"})
    records = []
    event = ""
    data_lines = []
    total = 0
    deadline = time.monotonic() + args.max_seconds
    terminal = {"run.completed", "run.failed", "run.cancelled", "run.interrupted"}
    try:
        with opener().open(request, timeout=min(TIMEOUT_SECONDS, 8)) as response:
            while time.monotonic() < deadline:
                line = response.readline()
                if not line:
                    break
                total += len(line)
                if total > MAX_EVENT_BYTES:
                    raise RuntimeError("Event stream exceeded the configured size limit.")
                decoded = line.decode("utf-8", errors="replace").rstrip("\r\n")
                if decoded.startswith("event:"):
                    event = decoded[6:].strip()
                elif decoded.startswith("data:"):
                    data_lines.append(decoded[5:].strip())
                elif decoded == "":
                    if data_lines:
                        raw = "\n".join(data_lines)
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            data = {"raw_data": raw}
                        name = event_name(event, data)
                        records.append({"event": name, "data": data})
                        if name in terminal:
                            break
                    event, data_lines = "", []
    except urllib.error.HTTPError as exc:
        raise ApiStatus(exc.code) from None
    folder = RUNS_DIR / ("run-" + run_id)
    path = unique_json(folder, "events", {"run_id": run_id, "events": records, "received_utc": datetime.now(timezone.utc).isoformat()})
    print(json.dumps({"run_id": run_id, "event_count": len(records), "terminal_seen": bool(records and records[-1]["event"] in terminal), "receipt": str(path)}))


def stop(args, base, key):
    run_id = check_run_id(args.run_id)
    status, data = api_call(base, key, "POST", "/v1/runs/" + run_id + "/stop", {})
    path = unique_json(RUNS_DIR / ("run-" + run_id), "stop", {"http_status": status, "run_id": run_id, "response": data, "received_utc": datetime.now(timezone.utc).isoformat()})
    print(json.dumps({"http_status": status, "run_id": run_id, "status": data.get("status") if isinstance(data, dict) else None, "receipt": str(path)}))


def approve(args, base, key):
    run_id = check_run_id(args.run_id)
    status, current = api_call(base, key, "GET", "/v1/runs/" + run_id)
    if not isinstance(current, dict) or not isinstance(current.get("status"), str):
        raise ValueError("Current run state is unavailable; refusing approval.")
    if current["status"].casefold() in TERMINAL_RUN_STATES:
        raise ValueError("Run is already terminal; refusing approval.")
    pending = current.get("approval") if isinstance(current, dict) else None
    if not isinstance(pending, dict):
        raise ValueError("There is no current pending approval.")
    if pending.get("request_id") != args.expected_request_id:
        raise ValueError("Approval request identity changed; refusing.")
    if pending.get("command") != args.expected_command:
        raise ValueError("Approval command changed; refusing.")
    generation = pending.get("execution_generation")
    actual_generation = None if generation is None else str(generation)
    if actual_generation != args.expected_generation:
        raise ValueError("Approval execution generation changed; refusing.")
    payload = {"request_id": args.expected_request_id, "choice": "once"}
    if generation is not None:
        payload["execution_generation"] = generation
    status, result = api_call(base, key, "POST", "/v1/runs/" + run_id + "/approval", payload)
    path = unique_json(RUNS_DIR / ("run-" + run_id), "approval-once", {
        "http_status": status,
        "run_id": run_id,
        "request_id": args.expected_request_id,
        "command_sha256": hashlib.sha256(args.expected_command.encode("utf-8")).hexdigest(),
        "execution_generation": generation,
        "choice": "once",
        "response": result,
        "received_utc": datetime.now(timezone.utc).isoformat(),
    })
    print(json.dumps({"http_status": status, "run_id": run_id, "approval_request_id": args.expected_request_id, "choice": "once", "receipt": str(path)}))


def health_readiness(data):
    if not isinstance(data, dict):
        raise ValueError("Health endpoint returned an unexpected response shape.")
    if data.get("healthy") is False:
        return False
    if data.get("healthy") is True:
        return True
    status = data.get("status")
    if not isinstance(status, str):
        return None
    return status.casefold() in {"ok", "healthy", "ready"}

def main():
    parser = argparse.ArgumentParser(description="Bounded client for a configured Linux Hermes API.")
    subs = parser.add_subparsers(dest="mode", required=True)
    p = subs.add_parser("prepare")
    p.add_argument("--input-file", required=True)
    p.set_defaults(func=prepare)
    p = subs.add_parser("capabilities")
    p.set_defaults(func=None)
    subs.add_parser("health").set_defaults(func=None)
    p = subs.add_parser("submit")
    p.add_argument("--request-id", required=True)
    p.set_defaults(func=submit)
    p = subs.add_parser("poll")
    p.add_argument("--run-id", required=True)
    p.set_defaults(func=poll)
    p = subs.add_parser("events")
    p.add_argument("--run-id", required=True)
    p.add_argument("--max-seconds", type=int, default=45, choices=range(1, 91))
    p.set_defaults(func=events)
    p = subs.add_parser("stop")
    p.add_argument("--run-id", required=True)
    p.set_defaults(func=stop)
    p = subs.add_parser("approve")
    p.add_argument("--run-id", required=True)
    p.add_argument("--expected-request-id", required=True)
    p.add_argument("--expected-command", required=True)
    p.add_argument("--expected-generation")
    p.set_defaults(func=approve)

    args = parser.parse_args()
    try:
        if args.mode == "prepare":
            args.func(args)
            return 0
        base = load_config()
        key = get_key()
        if args.mode in ("health", "capabilities"):
            route = "/health" if args.mode == "health" else "/v1/capabilities"
            status, data = api_call(base, key, "GET", route)
            if args.mode == "health":
                ready = health_readiness(data)
                print(json.dumps({"http_status": status, "ready": ready is True, "readiness_known": ready is not None, "health_status": data.get("status") if isinstance(data, dict) else None}, ensure_ascii=False))
                return 0 if ready is True else 2
            summary = {"http_status": status, "platform": data.get("platform")}
            summary["feature_names"] = sorted((data.get("features") or {}).keys())
            print(json.dumps(summary, ensure_ascii=False))
            return 0
        args.func(args, base, key)
        return 0
    except ApiStatus as exc:
        print(json.dumps({"http_status": exc.status, "operation": args.mode, "automatic_retry": False}), file=sys.stderr)
    except Exception as exc:
        print(json.dumps({"error_type": type(exc).__name__, "operation": args.mode, "automatic_retry": False}), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
