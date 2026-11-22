"""Static Store-facing UI contract.

This test protects the reviewed Store-facing title/layout/path-privacy decisions.
It does not replace real Windows 11 DPI or interaction QA.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "app.py").read_text(encoding="utf-8")
CHECKS = [["Data Contract Auditor","reserved Store name"],["self.geometry(\"900x580\")","default geometry"],["self.minsize(800, 500)","minimum geometry"],["Path(out).name","output path privacy"],["① 基準ファイル（前回・正常）","clear baseline step"],["② 今回ファイル（新しい方）","clear current step"],["詳細設定","advanced settings toggle"],["self.advanced_frame","advanced settings panel"],["pack_forget()","advanced settings collapsed"],["③ 比較を開始","single primary action"],["entry = ttk.Entry(row, textvariable=variable)","editable path entry"],["ttk.Button(row, text=\"選択\"","browse button"]]

class StoreUiContractTests(unittest.TestCase):
    def test_reviewed_ui_contract_is_present(self):
        for token, purpose in CHECKS:
            with self.subTest(purpose=purpose):
                self.assertIn(token, UI)

if __name__ == "__main__":
    unittest.main()
