"""Product acceptance: preview permission is tied to exact file bytes."""
import os
import tempfile
import unittest
from pathlib import Path

from audit_review_gate import input_revision
from contract_auditor import load_table


class PaidPreviewGateTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.a = Path(self.folder.name) / "baseline.csv"
        self.b = Path(self.folder.name) / "current.csv"
        self.a.write_text("id,value\n001,10\n", encoding="utf-8")
        self.b.write_text("id,value\n001,11\n", encoding="utf-8")

    def test_same_inputs_approve_without_writing(self):
        first = input_revision(str(self.a), str(self.b), ["id"])
        self.assertEqual(first, input_revision(str(self.a), str(self.b), ["id"]))
        self.assertEqual(list(Path(self.folder.name).iterdir()), [self.a, self.b])

    def test_mutation_with_same_file_size_invalidates_approval(self):
        first = input_revision(str(self.a), str(self.b), ["id"])
        self.b.write_text("id,value\n001,12\n", encoding="utf-8")
        self.assertNotEqual(first, input_revision(str(self.a), str(self.b), ["id"]))

    def test_unsafe_input_or_duplicate_key_is_refused(self):
        for baseline, current, keys in (
            (str(self.a), str(self.a), ["id"]),
            (str(self.a), str(self.b), ["id", "id"]),
            (str(self.a), str(self.b), [] if False else ["id", "id"]),
        ):
            with self.subTest(base=baseline, keys=keys), self.assertRaises(ValueError):
                input_revision(baseline, current, keys)
        missing = Path(self.folder.name) / "missing.csv"
        with self.assertRaises(ValueError):
            input_revision(str(missing), str(self.b), ["id"])

    def test_csv_duplicate_headers_fail_closed(self):
        self.a.write_text("id,id\n001,10\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate headers"):
            load_table(self.a)
        self.assertEqual(self.a.read_text(encoding="utf-8"), "id,id\n001,10\n")

    def test_csv_empty_header_fails_closed(self):
        self.a.write_text("id,\n001,10\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "nonempty"):
            load_table(self.a)

    def test_oversized_input_is_refused_before_parsing(self):
        with self.a.open("wb") as target:
            target.truncate(100 * 1024 * 1024 + 1)
        with self.assertRaisesRegex(ValueError, "100 MiB"):
            input_revision(str(self.a), str(self.b), ["id"])
        with self.assertRaisesRegex(ValueError, "100 MiB"):
            load_table(self.a)


if __name__ == "__main__":
    unittest.main()
