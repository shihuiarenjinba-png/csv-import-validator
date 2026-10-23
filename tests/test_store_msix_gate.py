"""Regression tests for Store candidate gating and manifest verification."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from store.validate_store_config import LOGOS, validate_config  # noqa: E402
from store.verify_msix_candidate import verify_msix  # noqa: E402


def png_header(width: int, height: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + width.to_bytes(4, "big") + height.to_bytes(4, "big")


class StoreGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = self.root / "store"
        assets = self.store / "assets"
        assets.mkdir(parents=True)
        (self.root / "app.py").write_text("# fixture", encoding="utf-8")
        self.product = {
            "displayName": "Data Contract and Schema Drift Auditor",
            "exeName": "DataContractSchemaDrift",
            "appId": "DataContractSchemaDrift",
            "entryPoint": "app.py",
            "commercialLicense": "NOT_CERTIFIED",
            "storeStatus": "HOLD_OFFICIAL_PARTNER_IDENTITY_REQUIRED",
        }
        self.registration = {
            "repository": "csv-import-validator",
            "displayName": "Data Contract and Schema Drift Auditor",
            "partnerCenterState": "EXISTING_CONFIRMED",
            "certificationSubmission": "NOT_AUTHORIZED",
            "salesRelease": "HOLD",
            "storeIdVerificationStatus": "PARTNER_CENTER_VERIFIED",
            "identityFieldVerification": {
                "storeId": "PARTNER_CENTER_VERIFIED",
                "packageIdentityName": "PARTNER_CENTER_VERIFIED",
                "packageIdentityPublisher": "PARTNER_CENTER_VERIFIED",
                "publisherDisplayName": "PARTNER_CENTER_VERIFIED",
                "packageFamilyName": "PARTNER_CENTER_VERIFIED",
            },
            "displayNameVerificationStatus": "PARTNER_CENTER_VERIFIED",
            "approvedStoreVersion": "1.0.0.0",
            "approvedStoreVersionStatus": "OWNER_APPROVED",
            "manifestResources": ["en-US", "ja-JP"],
            "manifestResourcesVerificationStatus": "OWNER_APPROVED",
            "storeIdentity": {
                "storeId": "9PDL4ZWSB45P",
                "packageIdentityName": "OkinawaDesktopTools.DataContractAuditor",
                "packageIdentityPublisher": "CN=TEST-ONLY",
                "publisherDisplayName": "Test Publisher",
                "packageFamilyName": "OkinawaDesktopTools.DataContractAuditor_test",
            },
        }
        for filename, dims in LOGOS.items():
            (assets / filename).write_bytes(png_header(*dims))
        (assets / "approval.json").write_text(json.dumps({
            "status": "OWNER_APPROVED", "product_key": "data-contract-auditor",
            "approval_ref": "TEST-FIXTURE-ONLY", "approved_by": "TEST-FIXTURE-ONLY",
            "approval_date": "2026-10-23",
        }), encoding="utf-8")
        self._write_config()

    def _write_config(self):
        (self.store / "product.json").write_text(json.dumps(self.product), encoding="utf-8")
        (self.store / "partner_center_registration.json").write_text(json.dumps(self.registration), encoding="utf-8")

    def test_complete_fixture_passes_preflight(self):
        self._write_config()
        result = validate_config(self.root, "1.0.0.0")
        self.assertTrue(result["ready"], result["blockers"])

    def test_user_confirmation_alone_never_authorizes_candidate(self):
        self.registration["storeIdVerificationStatus"] = "USER_CONFIRMED_NOT_LIVE_VERIFIED"
        self.registration["identityFieldVerification"]["storeId"] = "USER_CONFIRMED_NOT_LIVE_VERIFIED"
        self._write_config()
        result = validate_config(self.root)
        self.assertFalse(result["ready"])
        self.assertTrue(any("not independently verified" in x for x in result["blockers"]))

    def test_unverified_identity_and_display_name_block_even_with_values(self):
        self.registration["identityFieldVerification"]["packageIdentityName"] = "UNKNOWN"
        self.registration["displayNameVerificationStatus"] = "UNKNOWN"
        self._write_config()
        result = validate_config(self.root)
        self.assertFalse(result["ready"])
        self.assertTrue(any("not live-verified: packageIdentityName" in x for x in result["blockers"]))
        self.assertTrue(any("reserved DisplayName" in x for x in result["blockers"]))

    def test_unapproved_version_and_languages_block_even_if_well_formed(self):
        self.registration["approvedStoreVersionStatus"] = "UNKNOWN"
        self.registration["manifestResourcesVerificationStatus"] = "UNKNOWN"
        self._write_config()
        result = validate_config(self.root)
        self.assertFalse(result["ready"])
        self.assertTrue(any("owner approval" in x for x in result["blockers"]))
        self.assertTrue(any("owner-approved" in x for x in result["blockers"]))

    def test_missing_identity_and_unconfirmed_state_fail_closed(self):
        self.registration["storeIdentity"]["packageIdentityName"] = None
        self.registration["partnerCenterState"] = "CONDITIONAL_CANDIDATE_NEEDS_WINDOWS_QA"
        self._write_config()
        result = validate_config(self.root, "1.0.0.0")
        self.assertFalse(result["ready"])
        self.assertTrue(any("packageIdentityName" in x for x in result["blockers"]))
        self.assertTrue(any("state is not confirmed" in x for x in result["blockers"]))

    def test_version_must_match_approved_four_part_revision_zero_value(self):
        self._write_config()
        for bad in ("1.0.0.15", "1.0.0", "2.0.0.0"):
            with self.subTest(version=bad):
                result = validate_config(self.root, bad)
                self.assertFalse(result["ready"])

    def test_artwork_requires_owner_approval(self):
        (self.store / "assets" / "approval.json").unlink()
        self._write_config()
        result = validate_config(self.root, "1.0.0.0")
        self.assertFalse(result["ready"])
        self.assertTrue(any("approval record" in x for x in result["blockers"]))

    def _make_msix(self, path: Path, display_name: str = "Data Contract and Schema Drift Auditor"):
        manifest = f'''<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10" xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10">
<Identity Name="OkinawaDesktopTools.DataContractAuditor" Publisher="CN=TEST-ONLY" Version="1.0.0.0" ProcessorArchitecture="x64"/>
<Properties><DisplayName>{display_name}</DisplayName><PublisherDisplayName>Test Publisher</PublisherDisplayName></Properties>
<Resources><Resource Language="en-US"/><Resource Language="ja-JP"/></Resources>
<Applications><Application Id="DataContractSchemaDrift" Executable="App\\DataContractSchemaDrift.exe"><uap:VisualElements DisplayName="{display_name}" Description="Test" BackgroundColor="transparent" Square150x150Logo="Assets/Square150x150Logo.png" Square44x44Logo="Assets/Square44x44Logo.png"/></Application></Applications>
</Package>'''
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("AppxManifest.xml", manifest)
            archive.writestr("App/DataContractSchemaDrift.exe", b"fixture")
            for filename in LOGOS:
                archive.writestr("Assets/" + filename, b"fixture-png")

    def test_synthetic_msix_manifest_contract_passes(self):
        self._write_config()
        package = self.root / "fixture.msix"
        self._make_msix(package)
        result = verify_msix(self.root, package)
        self.assertTrue(result["valid"], result["blockers"])

    def test_msix_wrong_display_name_is_rejected(self):
        self._write_config()
        package = self.root / "fixture.msix"
        self._make_msix(package, "Wrong Name")
        result = verify_msix(self.root, package)
        self.assertFalse(result["valid"])
        self.assertTrue(any("DisplayName" in x for x in result["blockers"]))


if __name__ == "__main__":
    unittest.main()
