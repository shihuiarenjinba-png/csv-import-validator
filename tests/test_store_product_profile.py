"""Store-name preparation must not claim a release or fake Microsoft identity."""
import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class StoreProfileTests(unittest.TestCase):
    def test_product_profile_matches_live_entrypoint_and_formal_build_gate(self):
        cfg = json.loads((ROOT / "store" / "product.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["entryPoint"], "app.py")
        self.assertEqual(cfg["displayName"], "Data Contract Auditor")
        self.assertEqual(cfg["storeStatus"], "READY_FOR_FORMAL_MSIX_BUILD")
        self.assertEqual(cfg["windowsRealDeviceQaStatus"], "WINDOWS_REAL_DEVICE_QA_PASS")
        self.assertEqual(cfg["finalArtworkApprovalStatus"], "OWNER_APPROVED_GENERATOR")
        self.assertEqual(cfg["commercialLicense"], "NOT_CERTIFIED")
        self.assertEqual(cfg["partnerCenterRegistration"], "PARTNER_CENTER_SCREENSHOT_VERIFIED")
        self.assertEqual(cfg["msixPackageStatus"], "FORMAL_READY_TO_BUILD")
        tree = ast.parse((ROOT / cfg["entryPoint"]).read_text(encoding="utf-8"))
        self.assertTrue(any(isinstance(item, ast.ClassDef) and
                            item.name == "DataContractAuditApp" for item in tree.body))

if __name__ == "__main__":
    unittest.main()
