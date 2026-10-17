"""Commercial acceptance for schema identity preservation and report safety."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from contract_auditor import load_table, save_audit


class SchemaCommercialSafetyTests(unittest.TestCase):
    def test_identifier_leading_zero_and_na_literal_survive_csv_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "顧客.csv"
            path.write_text("id,description\n00123,NA\n00002,\n", encoding="utf-8")
            frame = load_table(path)
            self.assertEqual(frame.iloc[0]["id"], "00123")
            self.assertEqual(frame.iloc[0]["description"], "NA")
            self.assertTrue(frame["description"].isna().iloc[1])

    def test_previous_report_is_preserved_and_dangerous_cell_is_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "audit"
            report = {
                "generated_contract": {"version": 1, "columns": {}},
                "findings": [{
                    "severity": "warning",
                    "code": "column_added",
                    "column": "=HYPERLINK(\"https://invalid\")",
                    "message": "+suspicious",
                    "baseline": "",
                    "current": "",
                }],
            }
            first = save_audit(report, output)
            first_json = (first / "data_drift_audit.json").read_bytes()
            second = save_audit(report, output)
            self.assertNotEqual(first, second)
            self.assertEqual((first / "data_drift_audit.json").read_bytes(), first_json)
            raw = json.loads((second / "data_drift_audit.json").read_text(encoding="utf-8"))
            self.assertEqual(raw["report_csv_formula_values_escaped"], 2)
            self.assertTrue(raw["findings"][0]["column"].startswith("="))
            with (second / "data_drift_findings.csv").open(encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertTrue(rows[0]["column"].startswith("'="))
            self.assertTrue(rows[0]["message"].startswith("'+"))


if __name__ == "__main__":
    unittest.main()
