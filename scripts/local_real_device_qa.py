from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_text(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def wait_until(app, predicate, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.update()
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("Timed out waiting for UI operation")


def collect_texts(widget) -> list[str]:
    values: list[str] = []
    try:
        text = widget.cget("text")
        if text:
            values.append(str(text))
    except Exception:
        pass
    for child in widget.winfo_children():
        values.extend(collect_texts(child))
    return values


def geometry_probe(app, scale: float) -> dict:
    app.tk.call("tk", "scaling", scale)
    app.geometry("900x580")
    app.update_idletasks()
    app.update()

    width = int(app.winfo_width())
    height = int(app.winfo_height())
    entries = []
    tree = None
    for child in app.winfo_children():
        stack = [child]
        while stack:
            node = stack.pop()
            cls = str(node.winfo_class())
            if cls in {"TEntry", "Entry"} and bool(node.winfo_ismapped()):
                entries.append(node)
            if cls == "Treeview":
                tree = node
            stack.extend(node.winfo_children())

    if len(entries) < 2:
        raise AssertionError(f"Expected at least 2 visible primary entries, got {len(entries)}")
    if any(str(e.cget("state")) in {"readonly", "disabled"} for e in entries[:2]):
        raise AssertionError("A primary file path entry is unexpectedly read-only or disabled")
    if min(int(e.winfo_width()) for e in entries[:2]) < 200:
        raise AssertionError("Primary file path entry is too narrow")
    if int(app.compare_button.winfo_width()) < 80:
        raise AssertionError("Primary compare button is too narrow")
    if tree is None or int(tree.winfo_width()) < 400 or int(tree.winfo_height()) < 70:
        raise AssertionError("Findings table is not usable at this scaling")

    if app.advanced_frame.winfo_manager():
        raise AssertionError("Advanced settings must start collapsed")
    app._toggle_advanced()
    app.update_idletasks()
    app.update()
    visible_after_toggle = []
    for child in app.winfo_children():
        stack = [child]
        while stack:
            node = stack.pop()
            if str(node.winfo_class()) in {"TEntry", "Entry"} and bool(node.winfo_ismapped()):
                visible_after_toggle.append(node)
            stack.extend(node.winfo_children())
    if len(visible_after_toggle) < 4:
        raise AssertionError("Advanced settings did not expose their editable fields")
    app._toggle_advanced()
    app.update_idletasks()

    return {
        "tk_scaling": scale,
        "window": [width, height],
        "primary_entry_min_width": min(int(e.winfo_width()) for e in entries[:2]),
        "compare_button_width": int(app.compare_button.winfo_width()),
        "tree_size": [int(tree.winfo_width()), int(tree.winfo_height())],
        "advanced_settings_collapsed_by_default": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    # Running a file from scripts/ makes scripts/ sys.path[0]. Add the
    # repository root explicitly so app.py / contract_auditor.py resolve
    # the same way they do when launched from the repository root.
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    evidence_dir = Path(args.evidence_dir).expanduser().resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    source_sha = git_text(root, "rev-parse", "HEAD")
    source_branch = git_text(root, "branch", "--show-current")

    checks: list[dict] = []

    def passed(name: str, detail=None) -> None:
        checks.append({"name": name, "status": "PASS", "detail": detail})

    with tempfile.TemporaryDirectory(prefix="dca-local-qa-") as td:
        work = Path(td)
        # Keep language/UI-state writes away from the user's real profile.
        os.environ["LOCALAPPDATA"] = str(work / "localappdata")

        import pandas as pd
        from contract_auditor import audit_drift, save_audit

        baseline = work / "baseline.csv"
        current = work / "current.csv"
        invalid = work / "invalid.csv"
        current_xlsx = work / "current.xlsx"
        output = work / "output"

        baseline.write_text(
            "id,amount,status,comment\n"
            "1,10.0,active,ok\n"
            "2,20.0,active,ok\n"
            "3,30.0,inactive,\n"
            "4,40.0,active,ok\n",
            encoding="utf-8",
        )
        current.write_text(
            "id,amount,status,new_flag,comment\n"
            "1,10.0,active,Y,ok\n"
            "2,200.5,pending,Y,\n"
            "2,200.5,pending,N,duplicate\n"
            "4,,active,N,ok\n"
            "5,999.9,new,Y,ok\n",
            encoding="utf-8",
        )
        invalid.write_text("id,id\n1,2\n", encoding="utf-8")
        pd.read_csv(current).to_excel(current_xlsx, index=False)

        before = {"baseline": sha256(baseline), "current": sha256(current)}

        report = audit_drift(baseline, current, key_columns=["id"])
        codes = {item["code"] for item in report["findings"]}
        required_codes = {"column_added", "duplicate_key_rate_increased"}
        missing = required_codes - codes
        if missing:
            raise AssertionError(f"Expected drift codes missing: {sorted(missing)}")
        passed("core_csv_drift", {"finding_codes": sorted(codes), "summary": report["summary"]})

        xlsx_report = audit_drift(baseline, current_xlsx, key_columns=["id"])
        if not xlsx_report["findings"]:
            raise AssertionError("CSV/XLSX comparison returned no findings")
        passed("csv_xlsx_compare", {"summary": xlsx_report["summary"]})

        try:
            audit_drift(baseline, invalid, key_columns=["id"])
        except Exception as exc:
            passed("invalid_input_rejected", {"error": str(exc)})
        else:
            raise AssertionError("Invalid duplicate-header CSV was accepted")

        published = save_audit(report, output)
        expected = {
            "data_drift_audit.json",
            "data_drift_findings.csv",
            "generated_contract.json",
        }
        actual = {p.name for p in published.iterdir() if p.is_file()}
        if not expected.issubset(actual):
            raise AssertionError(f"Published output incomplete: {sorted(actual)}")
        json.loads((published / "data_drift_audit.json").read_text(encoding="utf-8"))
        json.loads((published / "generated_contract.json").read_text(encoding="utf-8"))
        pd.read_csv(published / "data_drift_findings.csv", encoding="utf-8-sig")
        passed("outputs_reopen", {"folder": str(published), "files": sorted(actual)})

        after = {"baseline": sha256(baseline), "current": sha256(current)}
        if before != after:
            raise AssertionError("Input files changed during audit")
        passed("inputs_unchanged", before)

        # UI contract and workflow smoke on the real Windows desktop Python/Tk stack.
        from tkinter import messagebox
        from app import DataContractAuditApp
        from i18n import install_bilingual_ui, set_language

        layout = []
        for scale in (96 / 72, 120 / 72, 144 / 72):
            app = DataContractAuditApp()
            controller = install_bilingual_ui(app)
            layout.append(geometry_probe(app, scale))

            set_language("en")
            controller.refresh()
            app.update_idletasks()
            en_text = "\n".join(collect_texts(app))
            if "Baseline file (previous / normal)" not in en_text:
                raise AssertionError("English first-run guidance did not render")

            set_language("ja")
            controller.refresh()
            app.update_idletasks()
            ja_text = "\n".join(collect_texts(app))
            if "基準ファイル（前回・正常）" not in ja_text:
                raise AssertionError("Japanese first-run guidance did not render")

            app.destroy()
        passed("ui_language_and_scaling", layout)

        app = DataContractAuditApp()
        controller = install_bilingual_ui(app)
        errors: list[tuple[str, str]] = []
        messagebox.showerror = lambda title, message, *a, **k: errors.append((str(title), str(message)))
        messagebox.showwarning = lambda title, message, *a, **k: errors.append((str(title), str(message)))

        if str(app.compare_button.cget("state")) != "disabled":
            raise AssertionError("Compare should start disabled")
        app.baseline.set(str(baseline))
        app.current.set(str(current))
        app.keys.set("id")
        app.output_dir.set(str(work / "ui-output"))
        app.update()
        if str(app.compare_button.cget("state")) != "normal":
            raise AssertionError("Compare did not enable after two inputs")

        app.run_audit()
        wait_until(app, lambda: not app._running)
        if not app._findings:
            raise AssertionError("UI comparison produced no findings")
        passed("ui_compare_workflow", {"findings": len(app._findings), "status": app.status.get()})

        app.current.set(str(invalid))
        app.run_audit()
        wait_until(app, lambda: not app._running)
        if not errors:
            raise AssertionError("UI invalid-input path did not surface an error")
        passed("ui_error_path", {"last_error": errors[-1]})

        app._close()
        if app.winfo_exists():
            raise AssertionError("UI did not close cleanly")

        app2 = DataContractAuditApp()
        install_bilingual_ui(app2)
        app2.update_idletasks()
        app2.destroy()
        passed("close_relaunch", {"status": "second instance created and destroyed"})

    evidence = {
        "schema_version": "data-contract-local-real-device-qa/1",
        "product": "Data Contract Auditor",
        "source_branch": source_branch,
        "source_sha": source_sha,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "status": "PASS",
        "checks": checks,
        "human_visual_spot_check_required": True,
        "store_upload_authorized": False,
    }
    path = evidence_dir / "LOCAL_REAL_DEVICE_QA.json"
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print("LOCAL_REAL_DEVICE_QA=PASS")
    print(f"SOURCE_SHA={source_sha}")
    print(f"EVIDENCE={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
