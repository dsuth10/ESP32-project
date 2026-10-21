import hashlib
import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from server.deployment import install_media_service as installer


class InstallMediaServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.stage = self.root / "stage"
        for rel in installer.STAGE_REQUIRED_FILES:
            dest = self.stage / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("[Unit]\nDescription=test\n" if rel.suffix == ".service" else "fixture\n", encoding="utf-8")
        staged_hashes = {p.as_posix(): hashlib.sha256((self.stage / p).read_bytes()).hexdigest() for p in installer.STAGE_REQUIRED_FILES}
        (self.stage / installer.STAGE_MANIFEST).write_text(json.dumps({
            "files": [p.as_posix() for p in installer.STAGE_REQUIRED_FILES],
            "source_sha256": staged_hashes,
            "staged_sha256": staged_hashes,
        }), encoding="utf-8")
        self.layout = installer.Layout(
            app_root=self.root / "opt" / "companion-media",
            env_root=self.root / "etc" / "companion-media",
            state_root=self.root / "var" / "lib",
            receipt_root=self.root / "var" / "receipts",
            unit_path=self.root / "etc" / "systemd" / installer.UNIT_NAME,
        )
        self.layout.unit_path.parent.mkdir(parents=True)
        venv_python = self.layout.app_root / "venv" / "bin" / "python"
        venv_python.parent.mkdir(parents=True)
        venv_python.write_bytes(b"fixture python")
        venv_python.chmod(0o755)

    def tearDown(self):
        self.temp.cleanup()

    def successful_run(self, calls):
        def run(args, check=True):
            calls.append((args, check))
            class Result:
                returncode = 0
            return Result()
        return run

    def test_plan_has_review_hash_and_no_writes(self):
        plan = installer.preflight(self.stage, "desk", self.layout)
        self.assertEqual(plan["bind"], "127.0.0.1:8765")
        self.assertEqual(len(plan["package_sha256"]), 64)
        self.assertFalse(plan["writes_performed"])
        self.assertIn("Linux root", plan["host_checks_pending"])

    def test_missing_venv_is_refused_before_install_receipt_or_unit(self):
        missing_app = self.root / "absent-app"
        with self.assertRaisesRegex(FileNotFoundError, "Provision"):
            installer._safe_existing_app(missing_app)
        self.assertFalse(missing_app.exists())

    def test_venv_security_rejects_writable_interpreter(self):
        secure = SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o755)
        writable = SimpleNamespace(st_uid=0, st_mode=stat.S_IFREG | 0o775)
        with patch.object(Path, "stat", side_effect=[secure, secure, writable]):
            with self.assertRaisesRegex(PermissionError, "root-owned"):
                installer._check_venv_security(Path("/opt/companion-media"), Path("/opt/companion-media/venv"), Path("/opt/companion-media/venv/bin/python"))

    def test_readiness_requires_expected_contract_and_uses_auth_header(self):
        class Response:
            status = 200
            def __init__(self, url, payload):
                self.url = url
                self.payload = json.dumps(payload).encode()
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def geturl(self): return self.url
            def read(self, _limit): return self.payload
        responses = [
            Response("http://127.0.0.1:8765/health", {"status": "ok"}),
            Response("http://127.0.0.1:8765/v1/capabilities", {"service": "media-library", "version": 1,
                "event_kinds": ["version", "canonical"], "budget": True, "max_blob_bytes": 1000}),
        ]
        class Opener:
            def open(self, request, timeout):
                return urlopen(request, timeout)
        def urlopen(request, timeout):
            self.assertEqual(timeout, 5)
            if request.full_url.endswith("capabilities"):
                self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
            return responses.pop(0)
        with patch.object(installer.urllib.request, "build_opener", return_value=Opener()):
            installer._verify_readiness("test-secret")

    def test_install_requires_hash_and_is_ordered_verify_before_enable(self):
        calls = []
        run = self.successful_run(calls)
        def staged_run(args, check=True):
            if args[0] == "getent":
                return type("Result", (), {"returncode": 0})()
            if args[0].endswith("/python"):
                return type("Result", (), {"returncode": 0})()
            return run(args, check)
        digest = installer.package_hash(self.stage)[0]
        with patch.object(installer, "_is_root", return_value=True), patch.object(installer.sys, "platform", "linux"), patch.object(installer, "_run", side_effect=staged_run), patch.object(installer, "_check_venv_security"), patch.object(installer, "_verify_readiness") as ready:
            result = installer.apply_install(self.stage, "desk", digest, apply=True, layout=self.layout, run=run)
        ready.assert_called_once()
        commands = [args for args, _ in calls]
        self.assertLess(commands.index(["systemd-analyze", "verify", str(self.layout.unit_path)]), commands.index(["systemctl", "enable", "--now", "companion-media-library@desk.service"]))
        self.assertEqual(result["status"], "active")
        env = self.layout.env_path("desk")
        if os.name == "posix":
            self.assertEqual(env.stat().st_mode & 0o777, 0o600)
        self.assertIn(b"MEDIA_SERVER_TOKEN=", env.read_bytes())
        receipt = json.loads(self.layout.receipt_path("desk").read_text())
        self.assertNotIn("MEDIA_SERVER_TOKEN", json.dumps(receipt))
        self.assertFalse(any("token" in " ".join(args).lower() for args, _ in calls))

    def test_rejects_preexisting_unit_env_data_and_unrelated_app_files(self):
        targets = [
            (self.layout.unit_path, "unit"),
            (self.layout.env_path("desk"), "env"),
            (self.layout.data_path("desk"), "data"),
            (self.layout.app_root / "existing.txt", "app"),
        ]
        for path, label in targets:
            with self.subTest(label=label):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("owned elsewhere")
                with self.assertRaises(FileExistsError):
                    installer._reject_preexisting(self.layout, "desk")
                path.unlink()

    def test_failed_start_stops_and_disables_only_target_and_preserves_files(self):
        calls = []
        def run(args, check=True):
            calls.append(args)
            if args[:3] == ["systemctl", "enable", "--now"]:
                raise RuntimeError("start failure")
            return type("Result", (), {"returncode": 0})()
        def mocked_run(args, check=True):
            if args[0] == "getent" or args[0].endswith("/python"):
                return type("Result", (), {"returncode": 0})()
            return run(args, check)
        digest = installer.package_hash(self.stage)[0]
        with patch.object(installer, "_is_root", return_value=True), patch.object(installer.sys, "platform", "linux"), patch.object(installer, "_run", side_effect=mocked_run), patch.object(installer, "_check_venv_security"), patch.object(installer, "_verify_readiness"):
            with self.assertRaisesRegex(RuntimeError, "start failure"):
                installer.apply_install(self.stage, "desk", digest, apply=True, layout=self.layout, run=run)
        self.assertIn(["systemctl", "stop", "companion-media-library@desk.service"], calls)
        self.assertIn(["systemctl", "disable", "companion-media-library@desk.service"], calls)
        self.assertTrue(self.layout.env_path("desk").exists())
        self.assertTrue(self.layout.app_root.joinpath("server/media_library_server.py").exists())
        self.assertEqual(json.loads(self.layout.receipt_path("desk").read_text())["status"], "failed-preserved")

    def test_unit_validation_failure_does_not_touch_a_systemd_instance(self):
        calls = []
        def run(args, check=True):
            calls.append(args)
            if args[0] == "systemd-analyze":
                raise RuntimeError("invalid unit")
            return type("Result", (), {"returncode": 0})()
        def mocked_run(args, check=True):
            if args[0] == "getent" or args[0].endswith("/python"):
                return type("Result", (), {"returncode": 0})()
            return run(args, check)
        digest = installer.package_hash(self.stage)[0]
        with patch.object(installer, "_is_root", return_value=True), patch.object(installer.sys, "platform", "linux"), patch.object(installer, "_run", side_effect=mocked_run), patch.object(installer, "_check_venv_security"), patch.object(installer, "_verify_readiness"):
            with self.assertRaisesRegex(RuntimeError, "invalid unit"):
                installer.apply_install(self.stage, "desk", digest, apply=True, layout=self.layout, run=run)
        self.assertNotIn(["systemctl", "stop", "companion-media-library@desk.service"], calls)
        self.assertNotIn(["systemctl", "disable", "companion-media-library@desk.service"], calls)

    def test_stage_tamper_during_copy_fails_before_activation(self):
        calls = []
        run = self.successful_run(calls)
        real_copy = installer._copy_sources
        def tamper(stage, layout, expected):
            (stage / "server/media_library_server.py").write_text("changed", encoding="utf-8")
            return real_copy(stage, layout, expected)
        digest = installer.package_hash(self.stage)[0]
        def mocked_run(args, check=True):
            if args[0] == "getent":
                return type("Result", (), {"returncode": 0})()
            return run(args, check)
        with patch.object(installer, "_is_root", return_value=True), patch.object(installer.sys, "platform", "linux"), patch.object(installer, "_run", side_effect=mocked_run), patch.object(installer, "_check_venv_security"), patch.object(installer, "_copy_sources", side_effect=tamper):
            with self.assertRaisesRegex(ValueError, "changed after"):
                installer.apply_install(self.stage, "desk", digest, apply=True, layout=self.layout, run=run)
        self.assertFalse(any(args and args[0] == "systemctl" for args, _ in calls))

    def test_rollback_uses_only_receipt_owned_unit_and_preserves_data(self):
        unit_bytes = b"unit fixture"
        self.layout.unit_path.parent.mkdir(parents=True, exist_ok=True)
        self.layout.unit_path.write_bytes(unit_bytes)
        receipt_path = self.layout.receipt_path("desk")
        receipt_path.parent.mkdir(parents=True)
        receipt_path.write_text(json.dumps({
            "schema": 1,
            "instance": "desk",
            "unit_name": "companion-media-library@desk.service",
            "unit_path": str(self.layout.unit_path),
            "unit_sha256": hashlib.sha256(unit_bytes).hexdigest(),
            "created_unit": True,
            "status": "active",
        }))
        calls = []
        with patch.object(installer, "_is_root", return_value=True), patch.object(installer.sys, "platform", "linux"):
            result = installer.rollback(receipt_path, apply=True, layout=self.layout, run=self.successful_run(calls))
        self.assertTrue(result["writes_performed"])
        self.assertEqual([x[0] for x in calls], [
            ["systemctl", "stop", "companion-media-library@desk.service"],
            ["systemctl", "disable", "companion-media-library@desk.service"],
        ])
        self.assertTrue(self.layout.unit_path.exists())
        self.assertTrue(result["preserves_app_env_data_and_token"])

    def test_rollback_refuses_changed_unit(self):
        self.layout.unit_path.parent.mkdir(parents=True, exist_ok=True)
        self.layout.unit_path.write_text("changed")
        receipt = self.layout.receipt_path("desk")
        receipt.parent.mkdir(parents=True)
        receipt.write_text(json.dumps({
            "schema": 1, "instance": "desk", "unit_name": "companion-media-library@desk.service",
            "unit_path": str(self.layout.unit_path), "unit_sha256": "0" * 64, "created_unit": True,
        }))
        with self.assertRaisesRegex(ValueError, "changed"):
            installer.rollback(receipt, apply=True, layout=self.layout)


if __name__ == "__main__":
    unittest.main()
