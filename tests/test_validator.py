import csv
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
            self.assertEqual(report["source_file"]["name"], "input.csv")
            self.assertNotIn(str(root), json.dumps(report))

            with (result / "issues.csv").open("r", encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
            formula_row = next(r for r in rows if r["code"] == "formula_prefix_candidate")
            self.assertTrue(formula_row["value_preview"].startswith("'="))

    def test_signed_numeric_values_are_not_formula_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "numbers.csv"
            source.write_text("id,amount\n1,-100\n2,+25.5\n", encoding="utf-8")
            result = validate_csv(source, root / "out")
            report = json.loads((result / "report.json").read_text(encoding="utf-8"))
            self.assertFalse(any(i["code"] == "formula_prefix_candidate" for i in report["issues"]))

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
