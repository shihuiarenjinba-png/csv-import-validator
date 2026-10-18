"""Paid GUI regression: Key picker, CSV/Excel ID stability and read-only discovery."""
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from contract_auditor import load_table
from gui_schema_columns import common_key_candidates, read_header


class SchemaPickerQualityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.baseline = self.root / "baseline.csv"
        self.current = self.root / "current.csv"
        self.baseline.write_text("id,status,amount\n00123,NA,\n", encoding="utf-8")
        self.current.write_text("id,status,quantity\n00123,NA,12\n", encoding="utf-8")

    def test_picker_uses_common_column_names_without_writing(self):
        before = {p: p.read_bytes() for p in (self.baseline, self.current)}
        self.assertEqual(common_key_candidates(str(self.baseline), str(self.current)),
                         ["id", "status"])
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_picker_refuses_ambiguous_headers(self):
        self.baseline.write_text("id,id\n00123,00234\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "同じ列名"):
            common_key_candidates(str(self.baseline), str(self.current))

    def test_excel_text_identifier_na_literal_and_blank_are_preserved(self):
        path = self.root / "prior.xlsx"
        book = Workbook()
        sheet = book.active
        sheet.append(["id", "status", "empty"])
        sheet.append(["00123", "NA", None])
        book.save(path)
        book.close()
        frame = load_table(path)
        self.assertEqual(frame.iloc[0]["id"], "00123")
        self.assertEqual(frame.iloc[0]["status"], "NA")
        self.assertTrue(frame["empty"].isna().iloc[0])

    def test_excel_key_picker_uses_real_first_sheet_header(self):
        path = self.root / "prior.xlsx"
        book = Workbook()
        sheet = book.active
        sheet.append(["id", "status"])
        sheet.append(["00123", "NA"])
        book.save(path)
        book.close()
        self.assertEqual(read_header(str(path)), ["id", "status"])
        self.assertEqual(common_key_candidates(str(path), str(self.current)),
                         ["id", "status"])


if __name__ == "__main__":
    unittest.main()
