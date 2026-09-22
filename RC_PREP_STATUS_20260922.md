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
- SHA-256: $sha
- Release dependency lock, CycloneDX SBOM candidate, and installed-metadata third-party notice candidate were generated with the build.
- Customer artifact credential filename scan: PASS.
- Authenticode: DEFERRED until Microsoft approval (current signature state: NotSigned).
- **Not UPLOAD-READY:** product LICENSE approval and Windows 10/11 manual UI/DPI acceptance remain open. For API products, a customer-authorized live endpoint/OAuth test is also not represented by this automated result.
