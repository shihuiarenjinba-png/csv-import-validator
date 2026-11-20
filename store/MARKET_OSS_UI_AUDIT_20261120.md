# Market / OSS reference audit — 2026-11-20

Product: **Data Contract Auditor**

## References reviewed
- Great Expectations (GX): schema expectations for column existence, type, column count/order/set, and validation history.
  - https://docs.greatexpectations.io/docs/reference/learn/data_quality_use_cases/schema/
- Soda Core: data-contract engine with human-readable contracts and explicit quality checks.
  - https://github.com/sodadata/soda-core
- Frictionless Framework: tabular validation with structured, user-readable error details.
  - https://framework.frictionlessdata.io/docs/guides/validating-data

## Decisions for this product
- Keep the current local desktop workflow; do not add cloud/service dependencies merely to imitate larger platforms.
- Preserve explicit severity/status grouping and make the reason for each finding visible.
- Keep schema checks and data-quality checks distinguishable; a structurally valid file is not automatically semantically correct.
- Continue to expose summary counts plus actionable row/column-level detail where available.
- Fail closed on unreadable/ambiguous input, but never overwrite source files.
- Treat this document as design evidence only; no third-party code was copied.

## Remaining release evidence
- Real Windows 11 x64 UI/functional run at 100/125/150% DPI.
- Successful and invalid-input scenarios with non-personal fixtures.
- Exact Store version, final assets, QA_UNSIGNED MSIX, unpacked manifest and hashes.
