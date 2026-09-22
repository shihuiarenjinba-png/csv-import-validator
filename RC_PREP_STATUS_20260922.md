# Windows direct-delivery RC preparation — 2026-09-22

## State

**RC preparation only — NOT SALES-READY.**

The customer delivery model is a direct Windows executable plus optional separate
documentation/example files. A customer-facing ZIP is not required.

## Automated gates configured

- source unit tests
- credential-marker scan
- Python 3.12 x64 environment
- PyInstaller one-file/windowed executable build
- packaged GUI startup smoke test
- SHA-256 generation
- dependency snapshot

## Credential handling

OAuth client JSON, service-account JSON, refresh tokens, API keys, and other
credentials must stay outside the repository and delivery files. Future
credential-backed integration tests must inject them only at test runtime.

## Remaining blockers

- successful Windows-hosted RC build evidence
- manual Windows 10/11 and display-scale acceptance
- formal product LICENSE and third-party NOTICE
- SBOM
- Authenticode (deferred)

The default branch is unchanged.


## GitHub Actions execution note

Push-triggered workflow runs were created, but the jobs failed before any runner
steps started. The job records contain no step list and no job log URL, so these
runs do not provide evidence of a source-test, PyInstaller, or runtime failure.
Automatic push triggering is paused on this branch; the workflow remains
available for manual dispatch when the Windows runner environment is available.


## Local Windows RC evidence — 2026-09-22

- Data Contract & Schema Drift Auditor 1.0.0: source tests, Python compile/build path, one-file EXE build, and automated startup smoke passed locally on Windows 11 with Python 3.12.10.
- SHA-256: a5ef5b7b6f78e58ba62f8a97bba7554487848206faba80f23fda4f27354a3ea9
- Release dependency lock, CycloneDX SBOM candidate, and installed-metadata third-party notice candidate were generated with the build.
- Customer artifact credential filename scan: PASS.
- Authenticode: DEFERRED until Microsoft approval (current signature state: NotSigned).
- **READY-FOR-HUMAN-ACCEPTANCE:** Packaged EXE detected added/removed columns, type/null drift, and duplicate-key increase from generated CSV files.
- Remaining human check: Windows 10/11 GUI appearance, 100/125/150% DPI, usability, and formal product LICENSE decision.
