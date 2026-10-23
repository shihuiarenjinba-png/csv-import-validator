"""Store-name preparation must not claim a release or fake Microsoft identity."""
import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class StoreProfileTests(unittest.TestCase):
    def test_product_profile_matches_live_entrypoint_and_stays_hold(self):
        cfg = json.loads((ROOT / "store" / "product.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["entryPoint"], "app.py")
        self.assertEqual(cfg["displayName"], "Data Contract Auditor")
        self.assertEqual(cfg["storeStatus"], "HOLD_STORE_VERSION_ARTWORK_WINDOWS_QA_REQUIRED")
        self.assertEqual(cfg["commercialLicense"], "NOT_CERTIFIED")
        self.assertEqual(cfg["partnerCenterRegistration"], "PARTNER_CENTER_SCREENSHOT_VERIFIED")
        self.assertEqual(cfg["msixPackageStatus"], "NOT_BUILT")
        tree = ast.parse((ROOT / cfg["entryPoint"]).read_text(encoding="utf-8"))
        self.assertTrue(any(isinstance(item, ast.ClassDef) and
                            item.name == "DataContractAuditApp" for item in tree.body))

if __name__ == "__main__":
    unittest.main()
