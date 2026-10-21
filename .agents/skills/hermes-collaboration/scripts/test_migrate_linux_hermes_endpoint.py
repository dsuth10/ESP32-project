import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("migrate_linux_hermes_endpoint.py")
PROJECT_ROOT = SCRIPT.parents[4]
spec = importlib.util.spec_from_file_location("endpoint_migration", SCRIPT)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class MigrationTests(unittest.TestCase):
    def test_https_origin_validation(self):
        self.assertEqual(migration.validate_origin("https://example.ts.net:8443/"), "https://example.ts.net:8443")
        for value in ("http://example.ts.net", "https://u:p@example.ts.net", "https://example.ts.net/a", "https://example.ts.net/?x=1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                migration.validate_origin(value)

    def test_refuses_ambiguous_dispatch_identity(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            root = Path(temp)
            runs = root / "runs"
            folder = runs / "request-1"
            folder.mkdir(parents=True)
            (folder / "dispatch-identity.json").write_text("{}", encoding="utf-8")
            (root / "config.json").write_text('{"base_url":"http://old.local"}\n', encoding="utf-8")
            with patch.object(migration, "authenticated_get") as probe:
                with self.assertRaisesRegex(RuntimeError, "Unresolved"):
                    migration.switch("https://new.ts.net", "secret-token", root / "config.json", runs, root / "backups")
                probe.assert_not_called()
            self.assertEqual(json.loads((root / "config.json").read_text())["base_url"], "http://old.local")

    def test_malformed_dispatch_identity_fails_closed(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            runs = Path(temp) / "runs"
            folder = runs / "request-2"
            folder.mkdir(parents=True)
            (folder / "dispatch-identity.json").write_text("not-json", encoding="utf-8")
            self.assertEqual(migration.unresolved_runs(runs), ["request-2"])

    def test_authenticated_preflight_then_atomic_switch_and_guarded_rollback(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            root = Path(temp)
            config = root / "config.json"
            config.write_text('{"base_url":"http://old.local","other":"kept"}\n', encoding="utf-8")
            with patch.object(migration, "authenticated_get", side_effect=[{"status": "ready"}, {"platform": "hermes-agent", "features": {}}]) as probe:
                backup = migration.switch("https://new.ts.net", "secret-token", config, root / "runs", root / "backups")
            self.assertEqual([call.args[2] for call in probe.call_args_list], ["/health", "/v1/capabilities"])
            self.assertNotIn("secret-token", backup.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(config.read_text())["base_url"], "https://new.ts.net")
            with self.assertRaisesRegex(RuntimeError, "changed"):
                migration.rollback(backup, "https://other.ts.net", config, root / "backups", root / "runs")
            migration.rollback(backup, "https://new.ts.net", config, root / "backups", root / "runs")
            self.assertEqual(json.loads(config.read_text())["base_url"], "http://old.local")
            self.assertEqual(json.loads(config.read_text())["other"], "kept")

    def test_rollback_refuses_unresolved_runs(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            root = Path(temp)
            config = root / "config.json"
            config.write_text(json.dumps({"base_url": "https://new.ts.net"}), encoding="utf-8")
            backup = root / "old.json"
            backup.write_text(json.dumps({"base_url": "https://old.ts.net"}), encoding="utf-8")
            folder = root / "runs" / "request-1"
            folder.mkdir(parents=True)
            (folder / "dispatch-identity.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "Unresolved"):
                migration.rollback(backup, "https://new.ts.net", config, root / "backups", root / "runs")
            self.assertEqual(json.loads(config.read_text())["base_url"], "https://new.ts.net")

    def test_unready_candidate_never_changes_config(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            root = Path(temp)
            config = root / "config.json"
            initial = '{"base_url":"http://old.local"}\n'
            config.write_text(initial, encoding="utf-8")
            with patch.object(migration, "authenticated_get", return_value={"status": "starting"}):
                with self.assertRaisesRegex(RuntimeError, "explicit"):
                    migration.switch("https://new.ts.net", "secret-token", config, root / "runs", root / "backups")
            self.assertEqual(config.read_text(encoding="utf-8"), initial)
            self.assertFalse((root / "backups").exists())

    def test_inflight_run_status_receipts_are_followed_in_client_run_folder(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            root = Path(temp)
            runs = root / "runs"
            request = runs / "request-1"
            request.mkdir(parents=True)
            (request / "dispatch-identity.json").write_text("{}", encoding="utf-8")
            (request / "run-response.json").write_text(json.dumps({"response": {"run_id": "run-1", "status": "queued"}}), encoding="utf-8")
            status_dir = runs / "run-run-1"
            status_dir.mkdir()
            (status_dir / "status-20261021T000000Z.json").write_text(json.dumps({"response": {"status": "running"}}), encoding="utf-8")
            self.assertEqual(migration.unresolved_runs(runs), ["request-1"])
            (status_dir / "status-20261021T000001Z.json").write_text(json.dumps({"response": {"status": "completed"}}), encoding="utf-8")
            self.assertEqual(migration.unresolved_runs(runs), [])


if __name__ == "__main__":
    unittest.main()
