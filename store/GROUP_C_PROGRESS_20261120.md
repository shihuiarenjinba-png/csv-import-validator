# Group C progress evidence — 2026-11-20

Product: **Data Contract Auditor**

## Validated source before this record
- Source HEAD: `e5b8c0a7299e6a11192e79ae9ac91b72909e9961`
- GitHub Actions run: `44685165081`
- Workflow: Data Contract Auditor Store MSIX candidate gate
- regression-preflight: **SUCCESS**
- qa-unsigned-structural-msix: **SUCCESS**
- real Store candidate job: **SKIPPED by approval gate**

## QA-only package evidence
- QA version: `1.0.61.0` — generated from workflow run number; **NOT an approved Store version**
- Package: `DataContractSchemaDrift_QA_UNSIGNED_1.0.61.0_x64.msix`
- EXE SHA-256: `ba67c643eacd95e76f1215ed41c3fce48a400f34a4e298ca6b50867cd10f52ab`
- MSIX SHA-256: `475e0a405e35cc76bb646eb551b08f4e042941f0f463deb9b47d7ec523bc4c71`
- Artifact: `data-contract-QA_UNSIGNED-validation-msix-44685165081-1`
- Artifact ID: `14606067221`
- Signature status: `QA_UNSIGNED`
- Sales release: `HOLD`

## Current blockers for a real Store candidate
- approved Store version is missing / not owner-approved
- owner-approved manifest language list is missing
- final approved Store artwork and `store/assets/approval.json` are missing
- commercial-license evidence remains uncertified
- real Windows human UI/DPI acceptance remains separate

Do not upload the QA_UNSIGNED package to Partner Center as a production candidate.
