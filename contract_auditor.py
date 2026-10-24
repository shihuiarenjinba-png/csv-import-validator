from __future__ import annotations

import json
import csv
import math
import os
import shutil
import tempfile
import uuid
from datetime import datetime
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class Finding:
    severity: str
    code: str
    column: str
    message: str
    baseline: str = ""
    current: str = ""


MAX_INPUT_BYTES = 50_000_000


def _validate_csv_header(path: Path, encoding: str) -> None:
    # pandas auto-renames duplicate headers (a,a -> a,a.1). That would
    # hide schema corruption and produce misleading drift comparisons.
    with path.open("r", encoding=encoding, newline="") as stream:
        headers = next(csv.reader(stream), None)
    if not headers or any(not h.strip() for h in headers):
        raise ValueError("CSV must contain non-empty column names")
    normalized = [name.strip() for name in headers]
    if len(normalized) != len(set(normalized)):
        raise ValueError("CSV contains duplicate or ambiguous column names")


def load_table(path: str | Path, sheet_name: str | int = 0) -> pd.DataFrame:
    p = Path(path).expanduser().resolve()
    suffix = p.suffix.lower()
    if not p.is_file() or p.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("Input must be an existing regular file no larger than 50 MB")
    if suffix == ".csv":
        last_error = None
        for enc in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
            try:
                _validate_csv_header(p, enc)
                return pd.read_csv(p, encoding=enc, dtype=str, keep_default_na=False, na_values=[""])
            except UnicodeDecodeError as exc:
                last_error = exc
        raise last_error or ValueError("CSV encoding could not be detected")
    if suffix in {".xlsx", ".xlsm"}:
        return pd.read_excel(p, sheet_name=sheet_name)
    raise ValueError(f"Unsupported file type: {suffix}")


def _infer_kind(series: pd.Series) -> str:
    nonnull = series.dropna()
    if nonnull.empty:
        return "empty"
    if pd.api.types.is_bool_dtype(nonnull):
        return "boolean"
    if pd.api.types.is_numeric_dtype(nonnull):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(nonnull):
        return "datetime"
    text = nonnull.astype(str).str.strip()
    numeric = pd.to_numeric(text.str.replace(",", "", regex=False), errors="coerce")
    if numeric.notna().mean() >= 0.98:
        return "numeric_text"
    dt = pd.to_datetime(text, errors="coerce")
    if dt.notna().mean() >= 0.98:
        return "datetime_text"
    unique_ratio = text.nunique(dropna=True) / max(len(text), 1)
    return "categorical" if unique_ratio <= 0.25 or text.nunique() <= 50 else "text"


def profile_dataframe(df: pd.DataFrame) -> dict:
    columns = {}
    row_count = len(df)
    for col in df.columns:
        s = df[col]
        kind = _infer_kind(s)
        nonnull = s.dropna()
        item = {
            "kind": kind,
            "null_rate": float(s.isna().mean()) if row_count else 0.0,
            "unique_count": int(nonnull.nunique(dropna=True)),
            "unique_ratio": float(nonnull.nunique(dropna=True) / max(len(nonnull), 1)),
        }
        if kind in {"numeric", "numeric_text"}:
            num = pd.to_numeric(nonnull.astype(str).str.replace(",", "", regex=False), errors="coerce").dropna()
            if not num.empty:
                item.update({
                    "mean": float(num.mean()),
                    "std": float(num.std(ddof=0)) if len(num) > 1 else 0.0,
                    "min": float(num.min()),
                    "max": float(num.max()),
                    "q05": float(num.quantile(0.05)),
                    "q50": float(num.quantile(0.50)),
                    "q95": float(num.quantile(0.95)),
                })
        if kind == "categorical":
            counts = nonnull.astype(str).value_counts(normalize=True).head(20)
            item["top_values"] = {str(k): float(v) for k, v in counts.items()}
        columns[str(col)] = item
    return {
        "row_count": row_count,
        "column_count": len(df.columns),
        "columns": columns,
    }


def _numeric_shift(base: dict, cur: dict) -> float | None:
    if "mean" not in base or "mean" not in cur:
        return None
    scale = abs(float(base.get("std", 0.0)))
    if scale < 1e-12:
        scale = max(abs(float(base.get("mean", 0.0))) * 0.05, 1e-9)
    return abs(float(cur["mean"]) - float(base["mean"])) / scale


def compare_profiles(
    baseline: dict,
    current: dict,
    *,
    null_rate_increase_warn: float = 0.10,
    numeric_shift_warn: float = 1.0,
) -> list[Finding]:
    findings: list[Finding] = []
    bcols = baseline["columns"]
    ccols = current["columns"]

    for col in sorted(set(bcols) - set(ccols)):
        findings.append(Finding("error", "column_removed", col, "Baseline column is missing in current data."))
    for col in sorted(set(ccols) - set(bcols)):
        findings.append(Finding("warning", "column_added", col, "New column appeared in current data."))

    for col in sorted(set(bcols) & set(ccols)):
        b, c = bcols[col], ccols[col]
        if b["kind"] != c["kind"]:
            findings.append(Finding(
                "warning", "type_changed", col, "Inferred data type changed.", b["kind"], c["kind"]
            ))
        null_delta = float(c["null_rate"]) - float(b["null_rate"])
        if null_delta >= null_rate_increase_warn:
            findings.append(Finding(
                "warning", "null_rate_increased", col,
                f"Null rate increased by {null_delta:.1%}.", f"{b['null_rate']:.1%}", f"{c['null_rate']:.1%}",
            ))
        if b["kind"] in {"numeric", "numeric_text"} and c["kind"] in {"numeric", "numeric_text"}:
            shift = _numeric_shift(b, c)
            if shift is not None and shift >= numeric_shift_warn:
                findings.append(Finding(
                    "warning", "numeric_mean_shift", col,
                    f"Mean shifted by {shift:.2f} baseline standard deviations.",
                    str(b.get("mean", "")), str(c.get("mean", "")),
                ))
            bmin, bmax = b.get("min"), b.get("max")
            cmin, cmax = c.get("min"), c.get("max")
            if bmin is not None and cmin is not None and cmin < bmin:
                findings.append(Finding("info", "new_numeric_low", col, "Current minimum is below baseline minimum.", str(bmin), str(cmin)))
            if bmax is not None and cmax is not None and cmax > bmax:
                findings.append(Finding("info", "new_numeric_high", col, "Current maximum is above baseline maximum.", str(bmax), str(cmax)))
        if b["kind"] == "categorical" and c["kind"] == "categorical":
            bset = set((b.get("top_values") or {}).keys())
            cset = set((c.get("top_values") or {}).keys())
            new_values = cset - bset
            if new_values:
                findings.append(Finding(
                    "info", "new_category_values", col,
                    f"New category values appeared among top values: {len(new_values)}",
                    str(len(bset)), str(len(cset)),
                ))
    return findings


def duplicate_key_rate(df: pd.DataFrame, key_columns: list[str]) -> float | None:
    if not key_columns:
        return None
    missing = [c for c in key_columns if c not in df.columns]
    if missing:
        raise ValueError(f"Missing key columns: {missing}")
    if len(df) == 0:
        return 0.0
    return float(df.duplicated(subset=key_columns, keep=False).mean())


def build_contract(profile: dict) -> dict:
    columns = {}
    for name, item in profile["columns"].items():
        columns[name] = {
            "required": True,
            "kind": item["kind"],
            "max_null_rate": min(1.0, max(0.0, float(item["null_rate"]) + 0.05)),
        }
    return {"version": 1, "columns": columns}


def audit_drift(
    baseline_path: str | Path,
    current_path: str | Path,
    *,
    key_columns: list[str] | None = None,
) -> dict:
    key_columns = key_columns or []
    baseline_df = load_table(baseline_path)
    current_df = load_table(current_path)
    baseline = profile_dataframe(baseline_df)
    current = profile_dataframe(current_df)
    findings = compare_profiles(baseline, current)

    bdup = duplicate_key_rate(baseline_df, key_columns)
    cdup = duplicate_key_rate(current_df, key_columns)
    if bdup is not None and cdup is not None and cdup > bdup + 0.01:
        findings.append(Finding(
            "warning", "duplicate_key_rate_increased", ",".join(key_columns),
            "Duplicate-key rate increased.", f"{bdup:.2%}", f"{cdup:.2%}",
        ))

    return {
        "baseline_file": str(Path(baseline_path).resolve()),
        "current_file": str(Path(current_path).resolve()),
        "key_columns": key_columns,
        "baseline_profile": baseline,
        "current_profile": current,
        "generated_contract": build_contract(baseline),
        "summary": {
            "errors": sum(f.severity == "error" for f in findings),
            "warnings": sum(f.severity == "warning" for f in findings),
            "info": sum(f.severity == "info" for f in findings),
            "baseline_rows": baseline["row_count"],
            "current_rows": current["row_count"],
        },
        "findings": [asdict(f) for f in findings],
    }


def _safe_csv_value(value):
    """Prevent report-cell formulas while keeping the JSON evidence unchanged."""
    if isinstance(value, str) and (
        value.lstrip().startswith(("=", "+", "-", "@")) or value[:1] in ("\t", "\r", "\n")
    ):
        return "'" + value
    return value


def save_audit(report: dict, output_dir: str | Path) -> Path:
    """Publish the full JSON/CSV/contract set, never a partial report."""
    base = Path(output_dir).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = base / f"drift_audit_{stamp}_{uuid.uuid4().hex[:12]}"
    temporary = Path(tempfile.mkdtemp(dir=base, prefix='.pending_drift_'))
    try:
        expected_cols = ["severity", "code", "column", "message", "baseline", "current"]
        findings = pd.DataFrame(report["findings"], columns=expected_cols)
        safe_findings = findings.apply(lambda column: column.map(_safe_csv_value))
        escape_count = sum(
            _safe_csv_value(value) != value
            for finding in report["findings"] for value in finding.values()
        )
        output_report = {**report, "report_csv_formula_values_escaped": escape_count}
        with (temporary / "data_drift_audit.json").open("x", encoding="utf-8") as file:
            json.dump(output_report, file, ensure_ascii=False, indent=2)
        with (temporary / "generated_contract.json").open("x", encoding="utf-8") as file:
            json.dump(report["generated_contract"], file, ensure_ascii=False, indent=2)
        safe_findings.to_csv(temporary / "data_drift_findings.csv", index=False,
                             encoding="utf-8-sig", mode="x")
        for name in ("data_drift_audit.json", "generated_contract.json", "data_drift_findings.csv"):
            file = temporary / name
            if not file.is_file() or file.stat().st_size == 0:
                raise ValueError(f"Incomplete audit output: {name}")

        # Re-open every published format before the atomic rename. A report that
        # cannot be parsed again is not a successful audit output.
        with (temporary / "data_drift_audit.json").open("r", encoding="utf-8") as file:
            reread_report = json.load(file)
        with (temporary / "generated_contract.json").open("r", encoding="utf-8") as file:
            reread_contract = json.load(file)
        reread_findings = pd.read_csv(temporary / "data_drift_findings.csv", encoding="utf-8-sig")
        if reread_report.get("summary") != output_report.get("summary"):
            raise ValueError("Audit JSON verification failed: summary changed after write.")
        if reread_contract != report["generated_contract"]:
            raise ValueError("Generated contract verification failed after write.")
        if list(reread_findings.columns) != expected_cols or len(reread_findings) != len(findings):
            raise ValueError("Audit CSV verification failed after write.")
        os.rename(temporary, out)
        return out
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
