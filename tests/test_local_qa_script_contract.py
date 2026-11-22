from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PY = (ROOT / "scripts" / "local_real_device_qa.py").read_text(encoding="utf-8")
PS = (ROOT / "scripts" / "run_local_real_device_qa.ps1").read_text(encoding="utf-8")


class LocalQaScriptContractTests(unittest.TestCase):
    def test_qa_runner_covers_release_critical_cases(self):
        for token in (
            "core_csv_drift",
            "csv_xlsx_compare",
            "invalid_input_rejected",
            "outputs_reopen",
            "inputs_unchanged",
            "ui_language_and_scaling",
            "ui_compare_workflow",
            "ui_error_path",
            "close_relaunch",
        ):
            with self.subTest(token=token):
                self.assertIn(token, PY)

    def test_runner_adds_repository_root_to_python_path(self):
        self.assertIn("sys.path.insert(0, str(root))", PY)

    def test_wrapper_fail_closes_and_does_not_authorize_store_upload(self):
        self.assertIn("Working tree must be clean before QA", PS)
        self.assertIn("Local HEAD is not the current remote branch HEAD", PS)
        self.assertIn("STORE_UPLOAD_AUTHORIZED=FALSE", PS)
        self.assertIn("HUMAN_VISUAL_SPOT_CHECK=REMAINS", PS)


if __name__ == "__main__":
    unittest.main()
