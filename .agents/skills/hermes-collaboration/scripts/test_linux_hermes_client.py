import importlib.util
import json
import os
import socket
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from pathlib import Path
from unittest.mock import patch


CLIENT_PATH = Path(__file__).with_name("linux_hermes_client.py")
spec = importlib.util.spec_from_file_location("linux_hermes_client", CLIENT_PATH)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class Handler(BaseHTTPRequestHandler):
    seen = []
    accepted_by_key = {}
    operation_count = 0
    drop_after_accept = set()

    def log_message(self, *_):
        pass

    def _send_json(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        Handler.seen.append((self.path, self.headers.get("Authorization"), self.headers.get("Proxy-Authorization")))
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/should-not-follow")
            self.end_headers()
            return
        self._send_json(200, {"platform": "hermes-agent"})

    def do_POST(self):
        key = self.headers.get("Idempotency-Key")
        Handler.seen.append((self.path, self.headers.get("Authorization"), self.headers.get("Proxy-Authorization"), key))
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if key not in Handler.accepted_by_key:
            Handler.operation_count += 1
            Handler.accepted_by_key[key] = {"run_id": "stable-run", "status": "queued", "input": payload.get("input")}
        elif Handler.accepted_by_key[key].get("input") != payload.get("input"):
            self._send_json(409, {"error": "idempotency payload mismatch"})
            return
        if key in Handler.drop_after_accept:
            Handler.drop_after_accept.remove(key)
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
            return
        self._send_json(202, Handler.accepted_by_key[key])


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Handler.seen = []
        Handler.accepted_by_key = {}
        Handler.operation_count = 0
        Handler.drop_after_accept = set()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()

    def test_transport_refuses_redirect_and_ignores_proxy_environment(self):
        broken_proxy = "http://127.0.0.1:1"
        with patch.dict(os.environ, {"http_proxy": broken_proxy, "HTTP_PROXY": broken_proxy}):
            status, body = client.api_call(self.base, "test-key", "GET", "/ok")
        self.assertEqual(status, 200)
        self.assertEqual(body["platform"], "hermes-agent")
        self.assertEqual(Handler.seen[-1], ("/ok", "Bearer test-key", None))
        with self.assertRaises(client.ApiStatus) as caught:
            client.api_call(self.base, "test-key", "GET", "/redirect")
        self.assertEqual(caught.exception.status, 302)
        self.assertNotIn(("/should-not-follow", "Bearer test-key", None), Handler.seen)

    def test_ambiguous_first_submit_replays_same_identity_without_duplicate_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(client, "RUNS_DIR", root / "runs"):
                source = root / "task.txt"
                source.write_text("continue bounded read-only inventory", encoding="utf-8")
                output = StringIO()
                with redirect_stdout(output):
                    client.prepare(type("Args", (), {"input_file": str(source)})())
                request_id = json.loads(output.getvalue())["request_id"]
                folder, _ = client.read_request(request_id)
                Handler.drop_after_accept.add(request_id)
                args = type("Args", (), {"request_id": request_id})()
                with self.assertRaises(Exception):
                    client.submit(args, self.base, "test-key")
                self.assertTrue((folder / "request.json").is_file())
                self.assertFalse((folder / "run-response.json").exists())
                with redirect_stdout(StringIO()):
                    client.submit(args, self.base, "test-key")
                receipt = json.loads((folder / "run-response.json").read_text(encoding="utf-8"))
                self.assertEqual(receipt["response"]["run_id"], "stable-run")
                post_calls = [row for row in Handler.seen if row[0] == "/v1/runs" and row[3] == request_id]
                self.assertEqual(len(post_calls), 2)
                self.assertEqual(Handler.operation_count, 1)
                before = len(Handler.seen)
                with redirect_stdout(StringIO()):
                    client.submit(args, self.base, "test-key")
                self.assertEqual(len(Handler.seen), before)

    def test_ambiguous_request_cannot_be_replayed_with_another_endpoint_or_credential(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(client, "RUNS_DIR", root / "runs"):
                source = root / "task.txt"
                source.write_text("continue the same bounded task", encoding="utf-8")
                output = StringIO()
                with redirect_stdout(output):
                    client.prepare(type("Args", (), {"input_file": str(source)})())
                request_id = json.loads(output.getvalue())["request_id"]
                folder, _ = client.read_request(request_id)
                Handler.drop_after_accept.add(request_id)
                args = type("Args", (), {"request_id": request_id})()
                with self.assertRaises(Exception):
                    client.submit(args, self.base, "test-key")
                seen_after_ambiguous = len(Handler.seen)
                count_after_ambiguous = Handler.operation_count
                with self.assertRaisesRegex(RuntimeError, "bound to another"):
                    client.submit(args, self.base, "different-key")
                with self.assertRaisesRegex(RuntimeError, "bound to another"):
                    client.submit(args, self.base + "/other", "test-key")
                self.assertEqual(len(Handler.seen), seen_after_ambiguous)
                self.assertNotIn("test-key", (folder / "dispatch-identity.json").read_text(encoding="utf-8"))
                with redirect_stdout(StringIO()):
                    client.submit(args, self.base, "test-key")
                self.assertEqual(Handler.operation_count, count_after_ambiguous)

    def test_stop_uses_run_stop_endpoint_and_interrupted_is_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []
            def fake_call(base, key, method, route, payload=None, **kwargs):
                calls.append((method, route, payload))
                return 200, {"status": "stopping"}
            args = type("Args", (), {"run_id": "run-1"})()
            with patch.object(client, "RUNS_DIR", Path(tmp)), patch.object(client, "api_call", side_effect=fake_call), redirect_stdout(StringIO()):
                client.stop(args, "http://localhost", "test-key")
            self.assertEqual(calls, [("POST", "/v1/runs/run-1/stop", {})])
            self.assertIn("interrupted", client.TERMINAL_RUN_STATES)

            calls.clear()
            args = type("Args", (), {
                "run_id": "run-1", "expected_request_id": "req-1",
                "expected_command": "uname -sm", "expected_generation": "4",
            })()
            def interrupted_call(base, key, method, route, payload=None, **kwargs):
                calls.append((method, route, payload))
                return 200, {"status": "interrupted"}
            with patch.object(client, "api_call", side_effect=interrupted_call):
                with self.assertRaisesRegex(ValueError, "already terminal"):
                    client.approve(args, "http://localhost", "test-key")
            self.assertEqual(len(calls), 1)

    def test_event_name_comes_from_json_data(self):
        self.assertEqual(client.event_name("message", {"event": "tool.completed"}), "tool.completed")
        self.assertEqual(client.event_name("run.completed", {}), "run.completed")

    def test_health_readiness_fails_closed_for_malformed_or_starting_responses(self):
        self.assertTrue(client.health_readiness({"status": "healthy"}))
        self.assertFalse(client.health_readiness({"status": "starting"}))
        self.assertFalse(client.health_readiness({"status": "ok", "healthy": False}))
        self.assertIsNone(client.health_readiness({"message": "HTTP 200"}))
        with self.assertRaisesRegex(ValueError, "unexpected response shape"):
            client.health_readiness(["healthy"])

    def test_saved_request_identity_is_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(client, "RUNS_DIR", root / "runs"):
                input_file = root / "task.txt"
                input_file.write_text("read-only inventory", encoding="utf-8")
                args = type("Args", (), {"input_file": str(input_file)})()
                output = StringIO()
                with redirect_stdout(output):
                    client.prepare(args)
                request_id = json.loads(output.getvalue())["request_id"]
                folder, record = client.read_request(request_id)
                self.assertEqual(record["payload"]["input"], "read-only inventory")
                record["payload"]["input"] = "different task"
                (folder / "request.json").write_text(json.dumps(record), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "changed"):
                    client.read_request(request_id)

    def test_approval_rejects_changed_generation_and_terminal_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(client, "RUNS_DIR", Path(tmp)):
                calls = []
                current_status = {"status": "awaiting_approval", "approval": {
                    "request_id": "req-1", "command": "uname -sm", "execution_generation": 4,
                }}
                def fake_call(base, key, method, route, payload=None, **kwargs):
                    calls.append((method, route, payload))
                    return 200, current_status
                args = type("Args", (), {
                    "run_id": "run-1",
                    "expected_request_id": "req-1",
                    "expected_command": "uname -sm",
                    "expected_generation": "3",
                })()
                with patch.object(client, "api_call", side_effect=fake_call):
                    with self.assertRaisesRegex(ValueError, "generation changed"):
                        client.approve(args, "http://localhost", "test-key")
                    self.assertEqual(len(calls), 1)
                    current_status["status"] = "completed"
                    args.expected_generation = "4"
                    with self.assertRaisesRegex(ValueError, "terminal"):
                        client.approve(args, "http://localhost", "test-key")
                    self.assertEqual(len(calls), 2)

    def test_approval_success_is_once_and_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(client, "RUNS_DIR", Path(tmp)):
                calls = []
                def fake_call(base, key, method, route, payload=None, **kwargs):
                    calls.append((method, route, payload))
                    if method == "GET":
                        return 200, {"status": "awaiting_approval", "approval": {
                            "request_id": "req-1", "command": "uname -sm", "execution_generation": 4,
                        }}
                    return 200, {"approved": True}
                args = type("Args", (), {
                    "run_id": "run-1",
                    "expected_request_id": "req-1",
                    "expected_command": "uname -sm",
                    "expected_generation": "4",
                })()
                with patch.object(client, "api_call", side_effect=fake_call), redirect_stdout(StringIO()):
                    client.approve(args, "http://localhost", "test-key")
                self.assertEqual(calls[1][2], {
                    "request_id": "req-1", "choice": "once", "execution_generation": 4,
                })


if __name__ == "__main__":
    unittest.main()
