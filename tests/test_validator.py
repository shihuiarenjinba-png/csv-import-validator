import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from contract_auditor import audit_drift, save_audit
from validator import validate_csv


class CsvValidatorTests(unittest.TestCase):
    def test_detects_duplicate_key_and_formula_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "input.csv"
            source.write_text(
                "customer_id,name,amount\n1,A,100\n1,=SUM(A1:A2),200\n",
                encoding="utf-8",
            )
            schema = {
                "expected_columns": ["customer_id", "name", "amount"],
                "required_columns": ["customer_id", "name"],
                "key_columns": ["customer_id"],
                "allow_extra_columns": False,
            }

            result = validate_csv(source, root / "out", schema)
            report = json.loads((result / "report.json").read_text(encoding="utf-8"))
            codes = {issue["code"] for issue in report["issues"]}

            self.assertIn("duplicate_key", codes)
            self.assertIn("formula_prefix_candidate", codes)
            self.assertGreaterEqual(report["error_count"], 1)

    def test_detects_column_count_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "bad.csv"
            source.write_text("a,b\n1,2,3\n", encoding="utf-8")
            result = validate_csv(source, root / "out")
            report = json.loads((result / "report.json").read_text(encoding="utf-8"))
            self.assertTrue(any(i["code"] == "column_count_mismatch" for i in report["issues"]))

    def test_schema_drift_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline.csv"
            current = root / "current.csv"
            pd.DataFrame(
                {"id": [1, 2, 3, 4], "amount": [10, 20, 30, 40], "obsolete": ["a", "b", "c", "d"]}
            ).to_csv(baseline, index=False)
            pd.DataFrame(
                {
                    "id": [1, 1, 3, 4],
                    "amount": ["ten", None, "thirty", None],
                    "added": [True, False, True, False],
                }
            ).to_csv(current, index=False)

            report = audit_drift(baseline, current, key_columns=["id"])
            codes = {finding["code"] for finding in report["findings"]}
            self.assertIn("column_added", codes)
            self.assertIn("column_removed", codes)
            self.assertIn("type_changed", codes)
            self.assertIn("null_rate_increased", codes)
            self.assertIn("duplicate_key_rate_increased", codes)

            output = save_audit(report, root / "output 日本語 space")
            reopened = json.loads((output / "data_drift_audit.json").read_text(encoding="utf-8"))
            self.assertEqual(reopened["summary"], report["summary"])


if __name__ == "__main__":
    unittest.main()
