import csv
import json
import tempfile
import unittest
from pathlib import Path

from contract_runtime import check_contract, load_contract, save_contract_audit


class PaidContractRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.contract = {
            "version": 1,
            "columns": {
                "id": {"required": True, "kind": "numeric", "unique": True},
                "amount": {"required": True, "kind": "numeric", "max_null_rate": 0, "min": 0, "max": 200},
            },
        }

    def contract_file(self, obj):
        path = self.root / "contract.json"
        path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        return path

    def data(self, text):
        path = self.root / "current.csv"
        path.write_text(text, encoding="utf-8")
        return path

    def test_good_declared_columns(self):
        c = load_contract(self.contract_file(self.contract))
        result = check_contract(self.data("id,amount\n1,12\n2,90\n"), c)
        self.assertEqual(result["status"], "NO_VIOLATION_IN_DECLARED_FIELDS")
        self.assertEqual(result["unchecked_columns"], [])
        self.assertEqual(len(result["source_sha256"]), 64)

    def test_outside_contract_not_silent_pass(self):
        result = check_contract(self.data("id,amount,extra\n1,12,z\n"), self.contract)
        self.assertEqual(result["status"], "REVIEW_UNCHECKED_COLUMNS")
        self.assertIn("extra", result["unchecked_columns"])

    def test_missing_column_duplicate_key_and_limits(self):
        for data, code in [
            ("id\n1\n", "required_missing"),
            ("id,amount\n1,12\n1,22\n", "duplicate_unique_value"),
            ("id,amount\n1,-2\n", "below_min"),
            ("id,amount\n1,201\n", "above_max"),
            ("id,amount\n1,not-a-number\n", "kind_mismatch"),
            ("id,amount\n1,\n", "null_rate_limit"),
        ]:
            with self.subTest(code=code):
                result = check_contract(self.data(data), self.contract)
                self.assertEqual(result["status"], "CONTRACT_VIOLATION")
                self.assertIn(code, [x["code"] for x in result["findings"]])

    def test_duplicate_source_csv_header_detected_despite_pandas_renaming(self):
        result = check_contract(self.data("id,id,amount\n1,2,3\n"), self.contract)
        self.assertEqual(result["status"], "CONTRACT_VIOLATION")
        self.assertIn("duplicate_header", [x["code"] for x in result["findings"]])

    def test_reject_unknown_or_non_finite_contract_constraints(self):
        bad = [
            {"version": 2, "columns": {"id": {}}},
            {"version": 1, "columns": {"id": {"bogus": True}}},
            {"version": 1, "columns": {"id": {"unique": "yes"}}},
            {"version": 1, "columns": {"id": {"max_null_rate": 1.1}}},
            {"version": 1, "columns": {"id": {"min": 2, "max": 1}}},
            {"version": 1, "columns": {"id": {"min": float("nan")}}},
            {"version": 1, "columns": {"id": {"allowed_values": [float("inf")]}}},
        ]
        for obj in bad:
            with self.subTest(obj=obj):
                with self.assertRaises(ValueError):
                    load_contract(self.contract_file(obj))

    def test_non_overwriting_reports_and_spreadsheet_formula_protection(self):
        result = {
            "source_file": "a.csv",
            "findings": [{"severity": "=SUM(A1)", "code": "warning",
                          "column": "@X", "detail": "+risky"}],
        }
        first = save_contract_audit(result, self.root)
        second = save_contract_audit(result, self.root)
        self.assertNotEqual(first, second)
        self.assertTrue((first / "contract_result.json").exists())
        with (first / "contract_findings.csv").open(encoding="utf-8-sig", newline="") as handle:
            row = list(csv.reader(handle))[1]
        self.assertEqual(row[0], "'=SUM(A1)")
        self.assertEqual(row[2], "'@X")
        self.assertEqual(row[3], "'+risky")


if __name__ == "__main__":
    unittest.main()
