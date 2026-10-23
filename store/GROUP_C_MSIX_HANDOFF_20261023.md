## 2026-10-23 owner decision: Microsoft Store only, unsigned MSIX, minimum viable submission

The owner explicitly does **not** want to buy a code-signing certificate, sign locally, or distribute outside Microsoft Store. For this product, **signing / PFX / HSM / SignTool / external sideload distribution is OUT OF SCOPE and MUST NOT block preparation**. Microsoft's Store MSIX publishing process supplies the Store certificate after certification. The existing unsigned candidate builder is the selected packaging route; keep all existing application/build scripts intact.

**Minimum path, in order:**
1. Confirm own product's Partner Center reserved listing, Store ID and exact package Identity Name, Publisher, PublisherDisplayName, reserved DisplayName and approved next `A.B.C.0` version. Do not invent values; existing user-confirmed Store IDs are not independently live-verified.
2. Confirm genuine product logos and required localization, correct architecture and EXE payload. Perform source regression, portable EXE Windows real-input/output smoke and UI check. Use only genuinely run logs, not 0-step Actions status.
3. Produce **unsigned x64 MSIX** with existing product-specific builder only when its hard configuration checks pass. Unpack and inspect manifest, embedded EXE/resources and SHA-256. Do not mark candidate ready if package cannot be generated or validated.
4. Prepare minimum truthful Store listing: app name, brief feature description/limitations, actual Windows screenshots, product logo, support contact, privacy policy URL, category, age rating, price/markets and dependency licenses/notices. Privacy claims must reflect tested actual behavior.
5. Have the code owner check the draft package on Partner Center **Packages** page: match identity/version to the intended product, fix hard validation errors, record draft upload result. Upload, submit, certification and publish are distinct; **no certification submission or publication in this work without explicit authorization**.

**Excluded:** purchasing a signing certificate, signing a package, publishing a sideload installer, pretending an unsigned MSIX was successfully installed on a normal machine, and demanding WACK as a substitute for actual Store validation. Windows installation/update/uninstall checks can be done after a Store-signed deliverable is available. Until then, use real EXE smoke, MSIX structure/manifest/contents and Partner Center's package validation as evidence, without claiming unperformed lifecycle tests passed.

Official reference: https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/app-package-requirements

---

# Group C P0: Data Contract Auditor — MSIX handoff, 2026-10-23

**Designated working branch:** `codex/store-p0-data-contract-20261023`. The work branch diverged only from source `audit/store-release-hardening-20261019`, starting at `a259daa804f214c5453aab7b971372cc543dac3b`.

**Owner-confirmed Store ID candidate:** `9PDL4ZWSB45P` — numbers confirmed by user, NOT live-verified in Partner Center. Never treat this candidate as proof of the package identity fields.

**Implemented:** Dedicated JSON readiness validator, source regression tests, `store/build-msix.ps1` unsigned candidate builder, MSIX unpacked-manifest verifier, separate GitHub Actions preflight/build jobs. Existing app sources and existing scripts were not replaced.

## Current HOLD
- `packageIdentityName`, `packageIdentityPublisher`, `publisherDisplayName`, `packageFamilyName` are null, not confirmed.
- Store-reserved display name, identity fields, and Store ID require explicit live Partner Center verification status. Owner-approved Store package version `A.B.C.0` and language list are unknown.
- Product-owned PNG logos at `store/assets/` and `store/assets/approval.json` have not been supplied/approved.
- Neither Windows installation QA nor Store/WACK validation nor certification is verified.
- Latest at review: [GitHub Actions run 39921159690](https://github.com/shihuiarenjinba-png/csv-import-validator/actions/runs/39921159690), runner not assigned; steps = 0. This is *not* a test PASS or test FAIL. Verify current run before relying on it.

## Safe next execution
1. Confirm repository, designated source/work branch, exact remote/local HEAD and clean status; stop immediately if dirty.
2. Use exact Partner Center information from this product's own reserved slot; write statuses with provenance. Never copy another product's identity.
3. Complete genuine logo approval and Store version/language approval. Do not infer defaults.
4. Run source tests, then `./store/build-msix.ps1 -PreflightOnly` on a GitHub Windows runner. Inspect `store-output/**/store-preflight.json`. Any blocker means no package.
5. Only when ready, the existing conditional Actions build job will run `store/build-msix.ps1` for unsigned MSIX. Verify its true job ID, runner, steps, exit codes, artifact, package manifest, package SHA256 and contained EXE hash.
6. Real Windows install, launch, GUI usability (editing/debug controls not exposed), input/output safety, update/removal, WACK and Partner Center package validation are separate tasks; leave sale HOLD until audited and expressly authorized.

**Submission/publication:** NOT AUTHORIZED. **Sales:** HOLD.