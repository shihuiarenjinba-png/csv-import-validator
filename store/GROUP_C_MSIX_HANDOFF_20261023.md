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