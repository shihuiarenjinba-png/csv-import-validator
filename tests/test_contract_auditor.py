import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from contract_auditor import audit_drift, load_table, save_audit


class ContractAuditorTests(unittest.TestCase):
    def test_csv_drift_findings_outputs_and_source_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "基準.csv"
            current = root / "今回.csv"
            output = root / "監査出力"
            baseline.write_text(
                "id,amount,region,retired\n"
                "1,10,east,x\n"
                "2,12,east,y\n"
                "3,14,west,z\n"
                "4,16,west,w\n",
                encoding="utf-8-sig",
            )
            current.write_text(
                "id,amount,region,added\n"
                "1,100,east,a\n"
                "1,100,,b\n"
                "3,100,north,c\n"
                "4,100,,d\n",
                encoding="utf-8-sig",
            )
            before = hashlib.sha256(baseline.read_bytes()).hexdigest()

            report = audit_drift(baseline, current, key_columns=["id"])
            codes = {item["code"] for item in report["findings"]}
            self.assertTrue(
                {
                    "column_removed",
                    "column_added",
                    "null_rate_increased",
                    "numeric_mean_shift",
                    "new_numeric_high",
                    "new_category_values",
                    "duplicate_key_rate_increased",
                }.issubset(codes)
            )
            saved = save_audit(report, output)
            self.assertEqual(saved, output.resolve())
            self.assertTrue((output / "data_drift_audit.json").is_file())
            self.assertTrue((output / "generated_contract.json").is_file())
            self.assertTrue((output / "data_drift_findings.csv").is_file())
            stored = json.loads((output / "data_drift_audit.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["summary"]["baseline_rows"], 4)
            self.assertEqual(stored["summary"]["current_rows"], 4)
            self.assertEqual(hashlib.sha256(baseline.read_bytes()).hexdigest(), before)

    def test_cp932_csv_is_loaded_without_rewriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "日本語.csv"
            original = "地域,件数\n沖縄,2\n".encode("cp932")
            source.write_bytes(original)

            frame = load_table(source)

            self.assertEqual(frame.iloc[0]["地域"], "沖縄")
            self.assertEqual(frame.iloc[0]["件数"], 2)
            self.assertEqual(source.read_bytes(), original)

    def test_xlsx_first_sheet_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "入力.xlsx"
            pd.DataFrame({"id": [1, 2], "name": ["沖縄", "東京"]}).to_excel(
                source, index=False
            )

            frame = load_table(source)

            self.assertEqual(list(frame.columns), ["id", "name"])
            self.assertEqual(frame["name"].tolist(), ["沖縄", "東京"])

    def test_missing_key_column_is_an_explicit_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            baseline = Path(tmp) / "baseline.csv"
            current = Path(tmp) / "current.csv"
            baseline.write_text("id,value\n1,a\n", encoding="utf-8")
            current.write_text("id,value\n1,a\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Missing key columns"):
                audit_drift(baseline, current, key_columns=["not_a_column"])


if __name__ == "__main__":
    unittest.main()
