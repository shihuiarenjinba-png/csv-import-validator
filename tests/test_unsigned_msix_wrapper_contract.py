"""Static safety assertions for the new Data Contract unsigned MSIX wrapper.

Does not demonstrate Windows PowerShell execution, EXE/MSIX output, or Store review.
"""
from __future__ import annotations
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "store" / "build-msix.ps1"
WORKFLOW = ROOT / ".github" / "workflows" / "store-msix-candidate.yml"


class BuilderSourceSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_single_candidate_builder(self):
        self.assertEqual(self.script.count("[CmdletBinding()]"), 1)
        self.assertEqual(self.script.count("QA_UNSIGNED_MSIX_CREATED"), 1)
        self.assertEqual(self.script.count("SIGNATURE_STATUS=QA_UNSIGNED"), 1)

    def test_origin_branch_commit_and_clean_worktree_before_outputs(self):
        text = self.script
        repo_check = text.index("if ($RemoteUrl -notmatch")
        branch_check = text.index("if ($Branch -notin $AllowedBranches)")
        sha_check = text.index("if ($SourceSha -notmatch")
        dirty_check = text.index("if (-not [string]::IsNullOrWhiteSpace($DirtyState))")
        first_write = text.index("New-Item -ItemType Directory")
        self.assertLess(repo_check, branch_check)
        self.assertLess(branch_check, sha_check)
        self.assertLess(sha_check, dirty_check)
        self.assertLess(dirty_check, first_write)
        self.assertIn("origin/", text)
        self.assertIn("ExpectedRemoteBranch", text)
        self.assertIn('"codex/dca-userdata-output-20261128"', text)
        self.assertIn("shihuiarenjinba-png/csv-import-validator", text)

    def test_version_identity_and_manifest_guards_present(self):
        text = self.script
        self.assertIn("validate_store_config.py", text)
        self.assertIn("verify_msix_candidate.py", text)
        self.assertIn("Unpacked MSIX", text)
        self.assertIn("Get-FileHash", text)
        self.assertIn("MSIX_BUILD_BLOCKED", text)
        self.assertIn("QA_UNSIGNED", text)
        self.assertNotIn("SignTool.exe", text)
        self.assertNotIn("New-SelfSignedCertificate", text)

    def test_workflow_never_builds_when_gate_reports_hold(self):
        self.assertIn("ready == 'true'", self.workflow)
        self.assertIn("store/build-msix.ps1", self.workflow)

    def test_workflow_runs_product_gui_data_driver_and_isolated_install_lane(self):
        self.assertIn("scripts/local_real_device_qa.py", self.workflow)
        self.assertIn("store/qa_test_sign_install.ps1", self.workflow)
        self.assertIn("WINDOWS_10_11_VISUAL_DPI=NOT_RUN", self.workflow)
        self.assertIn("FIXED_1_0_0_0_PACKAGE_UNCHANGED=TRUE", self.workflow)

    def test_test_sign_script_is_github_hosted_only_and_binds_original_payload(self):
        script = (ROOT / "store" / "qa_test_sign_install.ps1").read_text(encoding="utf-8")
        guard = script.index("$env:GITHUB_ACTIONS -ne 'true'")
        signing = script.index("New-SelfSignedCertificate")
        install = script.index("Add-AppxPackage")
        cleanup = script.rindex("finally {")
        self.assertLess(guard, signing)
        self.assertLess(signing, install)
        self.assertLess(install, cleanup)
        self.assertIn("Get-ZipHashes", script)
        self.assertIn("AppxSignature.p7x", script)
        self.assertIn("original_unsigned_package_unchanged", script)
        self.assertIn("Remove-AppxPackage", script)


if __name__ == "__main__":
    unittest.main()

