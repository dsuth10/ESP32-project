from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
from hermes_service import HermesService, HermesHTTPError, HermesServiceError

TEST_TEMP_ROOT = Path(__file__).parents[2] / ".local-hermes-test-tmp"
TEST_TEMP_ROOT.mkdir(exist_ok=True)


class FixtureState:
    calls = []
    accepted = {}
    health = {"status": "healthy"}
    capabilities = {"platform": "hermes-agent", "features": {"run_submission": True, "run_status": True, "runs_idempotency": True}}
    run_status = {"status": "running", "message": "Working"}
    stop_response = {"status": "stopping"}
    event_body = b'event: run.completed\ndata: {"event":"run.completed","status":"completed","text":"Finished"}\n\n'
    drop_keys = set()
    operation_count = 0
    stream_stall = False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

    def _send(self, status, data, content_type="application/json"):
        raw = data if isinstance(data, bytes) else json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        FixtureState.calls.append(("GET", self.path, self.headers.get("Authorization"), self.headers.get("Proxy-Authorization")))
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/should-not-follow")
            self.end_headers()
        elif self.path == "/health":
            self._send(200, FixtureState.health)
        elif self.path == "/v1/capabilities":
            self._send(200, FixtureState.capabilities)
        elif self.path == "/v1/runs/stable-run":
            self._send(200, FixtureState.run_status)
        elif self.path == "/v1/runs/stable-run/events":
            if FixtureState.stream_stall:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                self.wfile.write(b'event: tool.progress\ndata: {"event":"tool.progress","message":"Working"}\n\n')
                self.wfile.flush()
                time.sleep(0.25)
            else:
                self._send(200, FixtureState.event_body, "text/event-stream")
        else:
            self._send(404, {"error": "missing"})

    def do_POST(self):
        payload = self._read_json()
        key = self.headers.get("Idempotency-Key")
        FixtureState.calls.append(("POST", self.path, self.headers.get("Authorization"), self.headers.get("Proxy-Authorization"), key, payload))
        if self.path == "/v1/runs":
            if key not in FixtureState.accepted:
                FixtureState.operation_count += 1
                FixtureState.accepted[key] = {"run_id": "stable-run", "status": "started", "input": payload.get("input")}
            elif FixtureState.accepted[key]["input"] != payload.get("input"):
                self._send(409, {"error": "payload mismatch"})
                return
            if key in FixtureState.drop_keys:
                FixtureState.drop_keys.remove(key)
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            self._send(202, FixtureState.accepted[key])
        elif self.path == "/v1/runs/stable-run/stop":
            self._send(200, FixtureState.stop_response)
        else:
            self._send(404, {"error": "missing"})


class HermesServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()

    def setUp(self):
        FixtureState.calls = []
        FixtureState.accepted = {}
        FixtureState.health = {"status": "healthy"}
        FixtureState.capabilities = {"platform": "hermes-agent", "features": {"run_submission": True, "run_status": True, "runs_idempotency": True}}
        FixtureState.run_status = {"status": "running", "message": "Working"}
        FixtureState.stop_response = {"status": "stopping"}
        FixtureState.event_body = b'event: run.completed\ndata: {"event":"run.completed","status":"completed","text":"Finished"}\n\n'
        FixtureState.drop_keys = set()
        FixtureState.operation_count = 0
        FixtureState.stream_stall = False
        self.tmp = TemporaryDirectory(dir=TEST_TEMP_ROOT)
        self.root = Path(self.tmp.name)
        self.config = {"HERMES_ENABLED": True, "HERMES_URL": self.base, "HERMES_TOKEN": "fixture-secret", "LOCAL_ONLY": False}
        self.service = HermesService(self.config, self.root)

    def tearDown(self):
        self.service.close()
        self.tmp.cleanup()

    def test_finished_run_survives_old_stream_events_and_unsupported_event_route(self):
        request_id = self.service.prepare("Selected work")["request_id"]
        self.service.submit(request_id)
        FixtureState.run_status = {"status": "completed", "output": "Retained final result"}
        self.assertEqual(self.service.poll(request_id)["status"], "completed")
        FixtureState.event_body = b'event: run.started\ndata: {"status":"started"}\n\n'
        self.assertEqual(self.service.events(request_id)["status"], "completed")
        with patch.object(self.service, "_api_call", side_effect=HermesHTTPError(404)):
            observed = self.service.events(request_id)
        self.assertEqual(observed["status"], "completed")
        self.assertEqual(observed["text"], "Retained final result")
        self.assertFalse(self.service.has_pending_requests())
        self.assertEqual(self.service.submit(request_id)["status"], "completed")

    def test_partial_terminal_event_does_not_finish_run(self):
        request_id = self.service.prepare("Selected work")["request_id"]
        self.service.submit(request_id)
        FixtureState.event_body = b'event: run.completed\ndata: {"output":"incomplete'
        observed = self.service.events(request_id)
        self.assertEqual(observed["events"], [])
        self.assertNotEqual(observed["status"], "completed")

    def test_health_requires_readiness_and_capabilities(self):
        FixtureState.health = {"status": "starting"}
        result = self.service.test_connection()
        self.assertEqual(result["status"], "degraded")
        self.assertFalse(result["ok"])
        self.assertEqual(len(FixtureState.calls), 1)
        FixtureState.health = {"status": "healthy"}
        result = self.service.test_connection()
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["capabilities"]["platform"], "hermes-agent")

    def test_capabilities_require_hermes_identity_and_run_routes(self):
        for capabilities in (
            {},
            {"platform": "other-service", "features": {"run_submission": True, "run_status": True, "runs_idempotency": True}},
            {"platform": "hermes-agent", "features": {"chat_completions": True}},
        ):
            FixtureState.capabilities = capabilities
            self.assertEqual(self.service.test_connection()["status"], "unsupported_api")

    def test_authentication_failure_has_specific_safe_status(self):
        with patch.object(self.service, "_api_call", side_effect=HermesHTTPError(401)):
            result = self.service.test_connection()
        self.assertEqual(result["status"], "authentication_failed")

    def test_capabilities_404_is_distinct_unsupported_api(self):
        class NoCapabilities(Handler):
            def do_GET(self):
                if self.path == "/health":
                    self._send(200, {"status": "ready"})
                else:
                    FixtureState.calls.append(("GET", self.path, self.headers.get("Authorization"), None))
                    self._send(404, {"error": "not installed"})
        # Exercise the HTTP mapping directly without relying on global server mutation.
        with patch.object(self.service, "_api_call", side_effect=[(200, {"status": "ready"}), HermesHTTPError(404)]):
            result = self.service.test_connection()
        self.assertEqual(result["status"], "unsupported_api")

    def test_prepare_persists_selected_task_and_context_only_then_submit_receipt_prevents_replay(self):
        prepared = self.service.prepare("Summarise this selected task", "Only this selected context")
        folder = self.root / "hermes-runs" / prepared["request_id"]
        saved = json.loads((folder / "request.json").read_text(encoding="utf-8"))
        self.assertIn("selected context", saved["payload"]["input"])
        self.assertNotIn("history", saved["payload"]["input"].lower())
        self.assertEqual(prepared["status"], "prepared")
        self.assertEqual(len(FixtureState.calls), 0)
        submitted = self.service.submit(prepared["request_id"])
        self.assertEqual(submitted["run_id"], "stable-run")
        self.assertEqual(submitted["status"], "started")
        dispatch = next(call for call in FixtureState.calls if call[0] == "POST" and call[1] == "/v1/runs")
        self.assertEqual(dispatch[4], prepared["request_id"])
        before = len(FixtureState.calls)
        again = self.service.submit(prepared["request_id"])
        self.assertEqual(again["run_id"], "stable-run")
        self.assertEqual(len(FixtureState.calls), before)
        self.assertEqual(FixtureState.operation_count, 1)
        FixtureState.run_status = {"status": "completed", "output": "The saved final answer."}
        completed = self.service.poll(prepared["request_id"])
        self.assertEqual(completed["text"], "The saved final answer.")
        repeated = self.service.submit(prepared["request_id"])
        self.assertEqual(repeated["status"], "completed")
        self.assertEqual(repeated["text"], "The saved final answer.")
        self.assertEqual(len(FixtureState.calls), before + 1)

    def test_ambiguous_dispatch_retries_same_identity_with_same_pair_in_live_process(self):
        prepared = self.service.prepare("Read-only bounded task")
        request_id = prepared["request_id"]
        FixtureState.drop_keys.add(request_id)
        first = self.service.submit(request_id)
        self.assertEqual(first["status"], "uncertain")
        self.assertFalse((self.root / "hermes-runs" / request_id / "run-response.json").exists())
        second = self.service.submit(request_id)
        self.assertEqual(second["run_id"], "stable-run")
        self.assertEqual(FixtureState.operation_count, 1)

    def test_restart_keeps_existing_dispatch_lock_and_refuses_replay(self):
        prepared = self.service.prepare("May have been dispatched")
        request_id = prepared["request_id"]
        folder = self.root / "hermes-runs" / request_id
        self.service._save_state(request_id, "dispatching", "Simulated process interruption.")
        (folder / "dispatch.lock").write_text("owner process", encoding="utf-8")
        self.service.close()
        restarted = HermesService(self.config, self.root)
        before_posts = len([call for call in FixtureState.calls if call[0] == "POST" and call[1] == "/v1/runs"])
        result = restarted.submit(request_id)
        self.assertEqual(result["status"], "uncertain")
        self.assertTrue((folder / "dispatch.lock").exists())
        self.assertEqual(len([call for call in FixtureState.calls if call[0] == "POST" and call[1] == "/v1/runs"]), before_posts)
        restarted.close()

    def test_preview_and_discard_only_apply_to_undispatched_local_request(self):
        prepared = self.service.prepare("Selected ask", "Selected context")
        preview = self.service.preview(prepared["request_id"])
        self.assertEqual((preview["task"], preview["context"]), ("Selected ask", "Selected context"))
        discarded = self.service.discard(prepared["request_id"])
        self.assertEqual(discarded["status"], "cancelled")
        record = json.loads((self.root / "hermes-runs" / prepared["request_id"] / "request.json").read_text(encoding="utf-8"))
        self.assertNotIn("payload", record)
        self.assertEqual(self.service.preview(prepared["request_id"])["task"], "")
        self.assertEqual(self.service.submit(prepared["request_id"])["status"], "cancelled")
        self.assertEqual(FixtureState.calls, [])

        dispatched = self.service.prepare("Already submitted")
        self.service.submit(dispatched["request_id"])
        with self.assertRaisesRegex(HermesServiceError, "Only an undispatched"):
            self.service.discard(dispatched["request_id"])

    def test_ambiguous_dispatch_cannot_change_endpoint_or_credential(self):
        prepared = self.service.prepare("Same identity only")
        request_id = prepared["request_id"]
        FixtureState.drop_keys.add(request_id)
        self.assertEqual(self.service.submit(request_id)["status"], "uncertain")
        before_posts = len([call for call in FixtureState.calls if call[0] == "POST" and call[1] == "/v1/runs"])
        with self.assertRaisesRegex(HermesServiceError, "while requests are prepared"):
            self.service.update_config({"HERMES_TOKEN": "replacement-secret"})
        restarted = HermesService({**self.config, "HERMES_TOKEN": "replacement-secret"}, self.root)
        rejected = restarted.submit(request_id)
        self.assertIn("bound to another", rejected["message"])
        restarted.close()
        self.assertEqual(len([call for call in FixtureState.calls if call[0] == "POST" and call[1] == "/v1/runs"]), before_posts)

    def test_config_changes_block_for_prepared_and_nonterminal_requests(self):
        prepared = self.service.prepare("Not submitted yet")
        with self.assertRaisesRegex(HermesServiceError, "while requests are prepared"):
            self.service.update_config({"HERMES_URL": "https://hermes.example.test"})
        self.service.submit(prepared["request_id"])
        self.assertTrue(self.service.has_pending_requests())
        with self.assertRaises(HermesServiceError):
            self.service.update_config({"HERMES_TOKEN": "new-secret"})
        FixtureState.run_status = {"status": "completed", "text": "Done"}
        self.service.poll(prepared["request_id"])
        self.assertFalse(self.service.has_pending_requests())
        result = self.service.update_config({"HERMES_ENABLED": False})
        self.assertFalse(result["HERMES_ENABLED"])
        self.assertNotIn("HERMES_TOKEN", result)

    def test_poll_events_and_stop_do_not_claim_stopped_without_terminal_receipt(self):
        prepared = self.service.prepare("Bounded work")
        self.service.submit(prepared["request_id"])
        polled = self.service.poll(prepared["request_id"])
        self.assertEqual(polled["status"], "running")
        self.assertEqual(polled["message"], "Working")
        FixtureState.event_body = b'event: run.progress\ndata: {"text":"Working"}\n\n'
        events = self.service.events(prepared["request_id"])
        self.assertEqual(events["events"][0]["event"], "run.progress")
        stopped = self.service.stop(prepared["request_id"])
        self.assertEqual(stopped["status"], "stopping")
        FixtureState.stop_response = {"status": "interrupted", "message": "Stopped"}
        stopped = self.service.stop(prepared["request_id"])
        self.assertEqual(stopped["status"], "interrupted")

    def test_persistent_sse_timeout_preserves_complete_events(self):
        prepared = self.service.prepare("Bounded work")
        self.service.submit(prepared["request_id"])
        FixtureState.stream_stall = True
        with patch("hermes_service.EVENT_TIMEOUT_SECONDS", 0.05):
            result = self.service.events(prepared["request_id"])
        self.assertEqual(result["event_count"], 1)
        self.assertEqual(result["events"][0]["event"], "tool.progress")
        self.assertEqual(result["events"][0]["data"]["message"], "Working")

    def test_pending_approval_is_reported_as_review_and_not_approved(self):
        prepared = self.service.prepare("Bounded task")
        self.service.submit(prepared["request_id"])
        FixtureState.run_status = {"status": "awaiting_approval", "approval": {"request_id": "approval-1", "command": "opaque"}}
        result = self.service.poll(prepared["request_id"])
        self.assertTrue(result["approval_pending"])
        self.assertIn("review", result["message"])
        self.assertFalse(any(call[0] == "POST" and call[1].endswith("/approval") for call in FixtureState.calls))

    def test_local_only_blocks_all_remote_operations(self):
        self.service.update_config({"LOCAL_ONLY": True})
        prepared = self.service.prepare("Local task")
        self.assertEqual(self.service.test_connection()["status"], "local_only")
        self.assertEqual(self.service.submit(prepared["request_id"])["status"], "local_only")
        self.assertEqual(self.service.poll(prepared["request_id"])["status"], "local_only")
        self.assertEqual(self.service.events(prepared["request_id"])["status"], "local_only")
        self.assertEqual(self.service.stop(prepared["request_id"])["status"], "local_only")
        self.assertEqual(FixtureState.calls, [])

    def test_transport_refuses_redirects_and_ambient_proxies_without_leaking_auth(self):
        with patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:1", "http_proxy": "http://127.0.0.1:1"}):
            status, body = self.service._api_call("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "healthy")
        seen = FixtureState.calls[-1]
        self.assertEqual(seen[2], "Bearer fixture-secret")
        self.assertIsNone(seen[3])
        with self.assertRaises(HermesHTTPError) as caught:
            self.service._api_call("GET", "/redirect")
        self.assertEqual(caught.exception.status, 302)
        self.assertNotIn("fixture-secret", str(caught.exception))

    def test_url_validation_and_request_payload_tamper_detection(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            HermesService({**self.config, "HERMES_URL": "http://example.test"}, self.root / "bad")
        prepared = self.service.prepare("Immutable payload")
        path = self.root / "hermes-runs" / prepared["request_id"] / "request.json"
        saved = json.loads(path.read_text(encoding="utf-8"))
        saved["payload"]["input"] = "changed"
        path.write_text(json.dumps(saved), encoding="utf-8")
        result = self.service.submit(prepared["request_id"])
        self.assertEqual(result["status"], "uncertain")
        self.assertIn("changed", result["message"])
        self.assertEqual(FixtureState.calls, [])

    def test_string_config_booleans_parse_zero_as_false(self):
        service = HermesService({"HERMES_ENABLED": "0", "HERMES_URL": self.base, "HERMES_TOKEN": "fixture-secret", "LOCAL_ONLY": "0"}, self.root / "string-config")
        self.assertEqual(service.test_connection()["status"], "disabled")
        self.assertEqual(FixtureState.calls, [])
        service.close()

    def test_list_requests_newest_first_and_interrupted_is_terminal(self):
        first = self.service.prepare("First")
        second = self.service.prepare("Second")
        states = self.service.list_requests()
        self.assertEqual([item["request_id"] for item in states], [second["request_id"], first["request_id"]])
        self.assertTrue(self.service.has_pending_requests())
        self.service._save_state(second["request_id"], "cancelled", "Test fixture terminal state.")
        # Confirm interrupted is considered terminal when received from the API.
        self.service.submit(first["request_id"])
        FixtureState.run_status = {"status": "interrupted"}
        self.service.poll(first["request_id"])
        self.assertFalse(self.service.has_pending_requests())


if __name__ == "__main__":
    unittest.main()
