# Changelog

## 0.9.0-rc1 — 2026-09-17

- Expanded from CSV preflight validation to Data Contract & Schema Drift Auditor.
- Separated hard Contract violations from statistical Drift review signals.
- Added generated Contract templates, fixed Contract loading, and release-gate status.
- Added null/type/schema/numeric/category/key-duplicate monitoring.
- Hardened CSV preflight against absolute-path leakage and spreadsheet formula injection.
- Added spreadsheet-safe Contract/Drift CSV reports.
- Added non-blocking GUI with Contract/Drift category display.
- Corrected runtime dependencies for pandas/openpyxl.
- Added Windows CI/PyInstaller release-candidate workflow and release gates.
