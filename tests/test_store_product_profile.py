"""Store-name preparation must not claim a release or fake Microsoft identity."""
import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StoreProfileTests(unittest.TestCase):
    def test_product_profile_matches_recorded_formal_candidate_and_live_readonly_gate(self):
        cfg = json.loads((ROOT / "store" / "product.json").read_text(encoding="utf-8"))
        gate = json.loads(
            (ROOT / "store" / "FORMAL_CANDIDATE_GATE_20261122.json").read_text(encoding="utf-8")
        )
        self.assertEqual(cfg["entryPoint"], "app.py")
        self.assertEqual(cfg["displayName"], "Data Contract Auditor")

        # The profile is now post-build: it records the next allowed step as
        # read-only Partner Center re-verification, not a pre-build state.
        self.assertEqual(cfg["storeStatus"], "READY_FOR_PARTNER_CENTER_READONLY")
        self.assertEqual(cfg["storeStatus"], gate["status"])
        self.assertEqual(cfg["msixPackageStatus"], "FORMAL_UNSIGNED_MSIX_CREATED_AND_VERIFIED")
        self.assertEqual(cfg["windowsRealDeviceQaStatus"], "WINDOWS_REAL_DEVICE_QA_PASS")
        self.assertEqual(cfg["finalArtworkApprovalStatus"], "OWNER_APPROVED_GENERATOR")
        self.assertEqual(cfg["commercialLicense"], "NOT_CERTIFIED")
        self.assertEqual(cfg["partnerCenterRegistration"], "PARTNER_CENTER_SCREENSHOT_VERIFIED")

        formal = cfg["formalPackage"]
        self.assertEqual(formal["sourceSha"], gate["formal_source_sha"])
        self.assertEqual(formal["msixSha256"], gate["formal_msix_sha256"])
        self.assertEqual(formal["msixFilename"], gate["formal_msix_filename"])
        self.assertEqual(formal["version"], gate["approved_store_version"])
        self.assertEqual(formal["signatureStatus"], "UNSIGNED_STORE_CANDIDATE")
        self.assertEqual(formal["unpackVerification"], "PASS")

        self.assertEqual(gate["qa_baseline_source_sha"], "107e59f2cbcde9c6ca88cf1aaf3d52262004e6e0")
        self.assertEqual(gate["formal_source_sha"], "5a09d81955e25664761ea25ecfb4ebf8d24cea6d")
        self.assertEqual(gate["next_allowed_action"], "PARTNER_CENTER_READONLY_REVERIFY_EXACT_DRAFT_AND_IDENTITY")
        self.assertFalse(gate["certification_submit_authorized"])
        self.assertFalse(gate["publish_authorized"])

        tree = ast.parse((ROOT / cfg["entryPoint"]).read_text(encoding="utf-8"))
        self.assertTrue(
            any(isinstance(item, ast.ClassDef) and item.name == "DataContractAuditApp" for item in tree.body)
        )


if __name__ == "__main__":
    unittest.main()
