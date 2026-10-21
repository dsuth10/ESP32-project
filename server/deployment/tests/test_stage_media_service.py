import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "stage_media_service.py"
PROJECT_ROOT = SCRIPT.parents[3]
spec = importlib.util.spec_from_file_location("stage_media_service", SCRIPT)
stage_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage_module)


class StageMediaTests(unittest.TestCase):
    def test_preflight_is_read_only_and_reviewed_stage_is_no_overwrite(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as temp:
            destination = Path(temp) / "stage"
            report = stage_module.stage(destination, reviewed=False)
            self.assertFalse(destination.exists())
            self.assertFalse(report["host_changes_performed"])
            staged = stage_module.stage(destination, reviewed=True)
            self.assertTrue((destination / "STAGE-REVIEW.json").is_file())
            for relative in staged["files"]:
                self.assertTrue((destination / relative).is_file())
            with self.assertRaises(FileExistsError):
                stage_module.stage(destination, reviewed=True)


if __name__ == "__main__":
    unittest.main()
