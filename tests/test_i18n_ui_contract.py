from pathlib import Path
import unittest

import i18n

ROOT = Path(__file__).resolve().parents[1]
UI_FILE = ROOT / "app.py"
SOURCE = "① 基準と今回を選択  →  ② Key列は必要な場合だけ指定  →  ③ 比較結果を確認"
ENGLISH = "① Choose baseline/current  →  ② Add key columns only if needed  →  ③ Review findings"
JAPANESE = "① 基準と今回を選択  →  ② Key列は必要な場合だけ指定  →  ③ 比較結果を確認"
COMPARE_SOURCE = "上の Compare を押すと2つのファイルを読み取り、変更点を下の一覧に表示します。元ファイルは変更しません。"
COMPARE_ENGLISH = "Press Compare above to read both files and show detected changes below. The original files are not modified."


class I18nUiContractTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("en")

    def test_guide_switches_both_languages(self):
        i18n.set_language("en")
        self.assertEqual(i18n.translate(SOURCE), ENGLISH)
        i18n.set_language("ja")
        self.assertEqual(i18n.translate(SOURCE), JAPANESE)

    def test_compare_guide_switches_to_english(self):
        i18n.set_language("en")
        self.assertEqual(i18n.translate(COMPARE_SOURCE), COMPARE_ENGLISH)
        i18n.set_language("ja")
        self.assertEqual(i18n.translate(COMPARE_SOURCE), COMPARE_SOURCE)

    def test_ui_installs_visible_language_switch(self):
        ui = UI_FILE.read_text(encoding="utf-8")
        helper = (ROOT / "i18n.py").read_text(encoding="utf-8")
        self.assertIn("install_bilingual_ui", ui)
        self.assertIn("Language / 言語", helper)

    def test_command_bar_icon_label_switches_language(self):
        i18n.set_language("en")
        self.assertEqual(i18n.translate("▶\nCompare"), "▶\nCompare")
        i18n.set_language("ja")
        self.assertEqual(i18n.translate("▶\nCompare"), "▶\n比較")


if __name__ == "__main__":
    unittest.main()
