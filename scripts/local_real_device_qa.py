"""Reproducible DCA GUI/data smoke using synthetic files only.

Run from an interactive Windows desktop with the project requirements installed:
    python scripts/local_real_device_qa.py --evidence-dir <new-empty-folder>

The driver exercises the actual Tk UI workflow and analyzer. It does not install
or certify an MSIX and must not be used as installed-package evidence.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import subprocess
import tempfile
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _walk_text(widget) -> list[str]:
    values = []
    try:
        text = widget.cget("text")
        if text:
            values.append(str(text))
    except Exception:
        pass
    for child in widget.winfo_children():
        values.extend(_walk_text(child))
    return values


def _wait(app, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while app._running and time.monotonic() < deadline:
        app.update()
        time.sleep(0.05)
    app.update_idletasks()
    if app._running:
        raise TimeoutError("DCA comparison did not finish within 60 seconds")


def _csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        csv.writer(stream).writerows(rows)


def _source_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
            capture_output=True, text=True, timeout=10,
        )
        value = result.stdout.strip()
        return value if len(value) == 40 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _source_worktree_clean() -> bool | None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT,
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None
        return not bool(result.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return None


def run(evidence_dir: Path | None = None) -> dict:
    if platform.system() != "Windows":
        raise RuntimeError("The interactive DCA GUI smoke is supported on Windows only")

    from openpyxl import Workbook

    supplied_evidence = evidence_dir is not None
    if evidence_dir is None:
        evidence_dir = Path(tempfile.mkdtemp(prefix="dca-gui-qa-evidence-"))
    evidence_dir = evidence_dir.expanduser().resolve()
    evidence_dir.mkdir(parents=True, exist_ok=False if supplied_evidence else True)

    previous_local_app_data = os.environ.get("LOCALAPPDATA")
    local_app_data = evidence_dir / "profile" / "LocalAppData"
    local_app_data.mkdir(parents=True, exist_ok=True)
    os.environ["LOCALAPPDATA"] = str(local_app_data)

    # Import after LOCALAPPDATA is redirected so UI preferences and the default
    # result path stay inside this disposable evidence directory.
    import app as app_module
    import i18n
    from app import DataContractAuditApp
    from i18n import install_bilingual_ui
    from app_paths import default_results_directory

    fixtures = evidence_dir / "fixtures"
    fixtures.mkdir()
    baseline_csv = fixtures / "baseline.csv"
    current_csv = fixtures / "current.csv"
    invalid_csv = fixtures / "invalid_duplicate_headers.csv"
    current_xlsx = fixtures / "current.xlsx"
    _csv(baseline_csv, [["id", "amount", "status"], ["1", "10", "active"], ["2", "20", "active"]])
    _csv(current_csv, [["id", "amount", "status", "region"], ["1", "12", "active", "JP"], ["2", "", "inactive", "US"], ["3", "30", "active", "JP"]])
    _csv(invalid_csv, [["id", "id"], ["1", "2"]])
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["id", "amount", "status", "region"])
    sheet.append([1, 12, "active", "JP"])
    sheet.append([2, None, "inactive", "US"])
    sheet.append([3, 30, "active", "JP"])
    workbook.save(current_xlsx)

    original_hashes = {p.name: _sha256(p) for p in (baseline_csv, current_csv, invalid_csv, current_xlsx)}
    default_output = default_results_directory()
    expected_output = local_app_data / "DataContractAuditor" / "Results"
    if default_output != expected_output:
        raise AssertionError(f"default output path escaped per-user app data: {default_output}")
    if str(default_output).lower().startswith(str(Path.cwd()).lower()):
        raise AssertionError("default results path still depends on the repository/process working directory")

    checks = []
    errors: list[tuple[str, str]] = []
    original_showerror = app_module.messagebox.showerror
    app = DataContractAuditApp()
    controller = install_bilingual_ui(app)
    try:
        i18n.set_language("en")
        app.update()
        compare_button = app.command_bar.button("compare")
        if (app.title() != "Data Contract Auditor" or compare_button is None
                or not compare_button.winfo_exists()):
            raise AssertionError("DCA launch did not initialize the expected title and primary Compare control")
        checks.append({"id": "launch_and_render", "status": "PASS",
                       "primary_control": "Compare",
                       "evidence_scope": "Tk widget tree initialized; visual rendering/DPI is not asserted"})
        controller.toggle()
        app.update_idletasks()
        japanese = "\n".join(_walk_text(app))
        if "データ契約監査" not in app.title() or "言語" not in japanese:
            raise AssertionError("Japanese UI language toggle did not render")
        checks.append({"id": "language_toggle_ja", "status": "PASS"})
        controller.toggle()
        app.update_idletasks()
        english = "\n".join(_walk_text(app))
        if app.title() != "Data Contract Auditor" or "Language / 言語" not in english:
            raise AssertionError("English UI language toggle did not render")
        checks.append({"id": "language_toggle_en", "status": "PASS"})

        if Path(app.output_dir.get()) != expected_output:
            raise AssertionError("GUI default output field did not use LOCALAPPDATA")
        checks.append({"id": "writable_default_output_path", "status": "PASS", "path": str(expected_output)})

        app.baseline.set(str(baseline_csv))
        app.current.set(str(current_csv))
        app.keys.set("id")
        app.run_audit()
        _wait(app)
        if app.status.get().startswith("監査失敗"):
            raise AssertionError(f"CSV GUI audit failed: {app.status.get()}")
        csv_findings = list(app._findings)
        codes = {item.get("code") for item in csv_findings}
        if not {"column_added", "null_rate_increased"}.issubset(codes):
            raise AssertionError(f"CSV compare missed expected drift findings: {sorted(codes)}")
        # The visible status contains the folder basename; find the latest run
        # under the configured user-writable result folder instead of trusting it.
        csv_outputs = sorted(expected_output.glob("drift_audit_*"), key=lambda p: p.stat().st_mtime)
        csv_folder = csv_outputs[-1]
        csv_json = json.loads((csv_folder / "data_drift_audit.json").read_text(encoding="utf-8"))
        findings_rows = list(csv.DictReader((csv_folder / "data_drift_findings.csv").open(encoding="utf-8-sig", newline="")))
        json.loads((csv_folder / "generated_contract.json").read_text(encoding="utf-8"))
        if len(csv_json["findings"]) != len(csv_findings) or len(findings_rows) != len(csv_findings):
            raise AssertionError("CSV output files do not match the visible finding count")
        checks.append({"id": "csv_compare_and_output_reopen", "status": "PASS", "finding_count": len(csv_findings), "output": str(csv_folder)})

        app.current.set(str(current_xlsx))
        app.run_audit()
        _wait(app)
        if app.status.get().startswith("監査失敗"):
            raise AssertionError(f"XLSX GUI audit failed: {app.status.get()}")
        xlsx_findings = list(app._findings)
        if not xlsx_findings:
            raise AssertionError("XLSX comparison returned no findings")
        xlsx_outputs = sorted(expected_output.glob("drift_audit_*"), key=lambda p: p.stat().st_mtime)
        xlsx_folder = xlsx_outputs[-1]
        xlsx_json = json.loads((xlsx_folder / "data_drift_audit.json").read_text(encoding="utf-8"))
        if len(xlsx_json["findings"]) != len(xlsx_findings):
            raise AssertionError("XLSX report does not match the visible finding count")
        checks.append({"id": "xlsx_compare_and_output_reopen", "status": "PASS", "finding_count": len(xlsx_findings), "output": str(xlsx_folder)})

        app_module.messagebox.showerror = lambda title, message, *a, **kw: errors.append((str(title), str(message)))
        app.current.set(str(invalid_csv))
        app.run_audit()
        _wait(app)
        if not errors or "duplicate or ambiguous column names" not in errors[-1][1]:
            raise AssertionError("Duplicate-header CSV did not produce the expected visible error")
        checks.append({"id": "duplicate_header_visible_error", "status": "PASS", "message": errors[-1][1]})

        observed_hashes = {p.name: _sha256(p) for p in (baseline_csv, current_csv, invalid_csv, current_xlsx)}
        if observed_hashes != original_hashes:
            raise AssertionError("DCA modified one or more synthetic input files")
        checks.append({"id": "input_files_unchanged", "status": "PASS", "sha256": observed_hashes})
    finally:
        app_module.messagebox.showerror = original_showerror
        app._close()

    relaunched = DataContractAuditApp()
    try:
        relaunched.update_idletasks()
        if relaunched.title() != "Data Contract Auditor":
            raise AssertionError("Second GUI launch did not render the expected title")
        checks.append({"id": "normal_exit_and_relaunch", "status": "PASS"})
    finally:
        relaunched._close()
        if previous_local_app_data is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = previous_local_app_data

    receipt = {
        "schema_version": "data-contract-auditor-gui-smoke/1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "product": "Data Contract Auditor",
        "source_sha": _source_sha(),
        "source_worktree_clean": _source_worktree_clean(),
        "source_revision_scope": ("COMMIT_EXACT" if _source_worktree_clean() is True
                                  else "HEAD_WITH_UNCOMMITTED_SOURCE_CHANGES"),
        "execution_type": "SOURCE_GUI_DRIVER_SYNTHETIC_DATA",
        "environment_lane": "WINDOWS_SERVER_AUTOMATION" if os.environ.get("GITHUB_ACTIONS") == "true" else "LOCAL_WINDOWS_GUI",
        "platform": platform.platform(),
        "status": "PASS",
        "checks": checks,
        "installed_msix_tested": False,
        "visual_dpi_tested": False,
        "certification_executed": False,
        "publish_executed": False,
    }
    output = evidence_dir / "DCA_GUI_QA_RECEIPT.json"
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite QA receipt: {output}")
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()
    try:
        result = run(args.evidence_dir)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": result["status"], "checks": len(result["checks"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

