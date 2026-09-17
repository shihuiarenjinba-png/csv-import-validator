import tempfile
import unittest
from pathlib import Path

import pandas as pd

from contract_auditor import audit_drift, evaluate_contract, profile_dataframe


class ContractAuditorTests(unittest.TestCase):
    def test_contract_violations_are_separate_from_drift(self):
        baseline = pd.DataFrame({"id": [1, 2, 3], "amount": [10, 20, 30]})
        current = pd.DataFrame({"id": [1, 2, 3], "amount": [10, None, None]})
        contract = {
            "version": 1,
            "allow_extra_columns": True,
            "columns": {
                "id": {"required": True, "kind": "numeric", "max_null_rate": 0.0},
                "amount": {"required": True, "kind": "numeric", "max_null_rate": 0.10},
            },
        }
        findings = evaluate_contract(profile_dataframe(current), contract)
        codes = {f.code for f in findings}
        self.assertIn("null_rate_violation", codes)
        self.assertTrue(all(f.category == "contract" for f in findings))

    def test_missing_required_column_fails_release_gate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            baseline = root / "baseline.csv"
            current = root / "current.csv"
            baseline.write_text("id,amount\n1,10\n2,20\n", encoding="utf-8")
            current.write_text("id\n1\n2\n", encoding="utf-8")
            contract = {
                "version": 1,
                "allow_extra_columns": True,
                "columns": {
                    "id": {"required": True, "kind": "numeric", "max_null_rate": 0.0},
                    "amount": {"required": True, "kind": "numeric", "max_null_rate": 0.0},
                },
            }
            report = audit_drift(baseline, current, contract=contract)
            self.assertEqual(report["summary"]["release_gate"], "fail")
            self.assertTrue(any(f["code"] == "required_column_missing" for f in report["contract_findings"]))
            self.assertNotIn("/", report["baseline_file"]["name"])

    def test_numeric_shift_remains_review_signal(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            baseline = root / "baseline.csv"
            current = root / "current.csv"
            baseline.write_text("id,amount\n1,10\n2,11\n3,12\n4,13\n", encoding="utf-8")
            current.write_text("id,amount\n1,100\n2,110\n3,120\n4,130\n", encoding="utf-8")
            report = audit_drift(baseline, current)
            self.assertTrue(any(f["code"] == "numeric_mean_shift" for f in report["drift_findings"]))
            self.assertEqual(report["summary"]["release_gate"], "review")


if __name__ == "__main__":
    unittest.main()
