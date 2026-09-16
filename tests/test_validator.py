import json
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
