from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

_NUMERIC_LITERAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


@dataclass
class Finding:
    severity: str
    category: str
    code: str
    column: str
    message: str
    baseline: str = ""
    current: str = ""


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_csv_cell(value: object) -> object:
    if not isinstance(value, str):
        return value
    stripped = value.lstrip()
    if not stripped or stripped[0] not in "=+-@":
        return value
    if _NUMERIC_LITERAL_RE.fullmatch(stripped.replace(",", "")):
        return value
    return "'" + value


def _write_findings_csv(path: Path, findings: list[dict]) -> None:
    fieldnames = ["severity", "category", "code", "column", "message", "baseline", "current"]
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for item in findings:
            writer.writerow({name: _safe_csv_cell(item.get(name, "")) for name in fieldnames})


def load_table(path: str | Path, sheet_name: str | int = 0) -> pd.DataFrame:
    p = Path(path).expanduser().resolve()
    suffix = p.suffix.lower()
    if suffix == ".csv":
        last_error: Exception | None = None
        for enc in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
            try:
                return pd.read_csv(p, encoding=enc)
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
    columns: dict[str, dict] = {}
    row_count = len(df)
    for raw_col in df.columns:
        col = str(raw_col)
        s = df[raw_col]
        kind = _infer_kind(s)
        nonnull = s.dropna()
        item: dict = {
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
            counts = nonnull.astype(str).value_counts(normalize=True).head(50)
            item["top_values"] = {str(k): float(v) for k, v in counts.items()}
        columns[col] = item
    return {"row_count": row_count, "column_count": len(df.columns), "columns": columns}


def _numeric_shift(base: dict, cur: dict) -> float | None:
    if "mean" not in base or "mean" not in cur:
        return None
    scale = abs(float(base.get("std", 0.0)))
    if scale < 1e-12:
        scale = max(abs(float(base.get("mean", 0.0))) * 0.05, 1e-9)
    return abs(float(cur["mean"]) - float(base["mean"])) / scale


def compare_profiles(baseline: dict, current: dict, *, null_rate_increase_warn: float = 0.10, numeric_shift_warn: float = 1.0) -> list[Finding]:
    findings: list[Finding] = []
    bcols = baseline["columns"]
    ccols = current["columns"]
    for col in sorted(set(bcols) - set(ccols)):
        findings.append(Finding("warning", "drift", "column_removed", col, "Baseline column is missing in current data."))
    for col in sorted(set(ccols) - set(bcols)):
        findings.append(Finding("info", "drift", "column_added", col, "New column appeared in current data."))
    for col in sorted(set(bcols) & set(ccols)):
        b, c = bcols[col], ccols[col]
        if b["kind"] != c["kind"]:
            findings.append(Finding("warning", "drift", "type_changed", col, "Inferred data type changed.", b["kind"], c["kind"]))
        null_delta = float(c["null_rate"]) - float(b["null_rate"])
        if null_delta >= null_rate_increase_warn:
            findings.append(Finding("warning", "drift", "null_rate_increased", col, f"Null rate increased by {null_delta:.1%}.", f"{b['null_rate']:.1%}", f"{c['null_rate']:.1%}"))
        if b["kind"] in {"numeric", "numeric_text"} and c["kind"] in {"numeric", "numeric_text"}:
            shift = _numeric_shift(b, c)
            if shift is not None and shift >= numeric_shift_warn:
                findings.append(Finding("warning", "drift", "numeric_mean_shift", col, f"Mean shifted by {shift:.2f} baseline standard deviations.", str(b.get("mean", "")), str(c.get("mean", ""))))
            bmin, bmax, cmin, cmax = b.get("min"), b.get("max"), c.get("min"), c.get("max")
            if bmin is not None and cmin is not None and cmin < bmin:
                findings.append(Finding("info", "drift", "new_numeric_low", col, "Current minimum is below baseline minimum.", str(bmin), str(cmin)))
            if bmax is not None and cmax is not None and cmax > bmax:
                findings.append(Finding("info", "drift", "new_numeric_high", col, "Current maximum is above baseline maximum.", str(bmax), str(cmax)))
        if b["kind"] == "categorical" and c["kind"] == "categorical":
            bset = set((b.get("top_values") or {}).keys())
            cset = set((c.get("top_values") or {}).keys())
            new_values = sorted(cset - bset)
            if new_values:
                findings.append(Finding("info", "drift", "new_category_values", col, f"New category values appeared among profiled values: {', '.join(new_values[:10])}", str(len(bset)), str(len(cset))))
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
    return {
        "version": 1,
        "allow_extra_columns": True,
        "columns": {
            name: {"required": True, "kind": item["kind"], "max_null_rate": min(1.0, max(0.0, float(item["null_rate"]) + 0.05))}
            for name, item in profile["columns"].items()
        },
    }


def evaluate_contract(current: dict, contract: dict) -> list[Finding]:
    findings: list[Finding] = []
    specs = contract.get("columns", {})
    ccols = current["columns"]
    allow_extra = bool(contract.get("allow_extra_columns", True))
    for col, spec in specs.items():
        if col not in ccols:
            if spec.get("required", False):
                findings.append(Finding("error", "contract", "required_column_missing", col, "Required contract column is missing."))
            continue
        cur = ccols[col]
        expected_kind = spec.get("kind")
        if expected_kind and cur.get("kind") != expected_kind:
            findings.append(Finding("error", "contract", "kind_violation", col, "Column kind violates contract.", str(expected_kind), str(cur.get("kind"))))
        if "max_null_rate" in spec and float(cur.get("null_rate", 0.0)) > float(spec["max_null_rate"]):
            findings.append(Finding("error", "contract", "null_rate_violation", col, "Null rate exceeds contract maximum.", f"<= {float(spec['max_null_rate']):.1%}", f"{float(cur.get('null_rate', 0.0)):.1%}"))
    if not allow_extra:
        for col in sorted(set(ccols) - set(specs)):
            findings.append(Finding("error", "contract", "unexpected_column", col, "Column is not allowed by contract."))
    return findings


def audit_drift(baseline_path: str | Path, current_path: str | Path, *, key_columns: list[str] | None = None, contract: dict | None = None) -> dict:
    key_columns = key_columns or []
    baseline_p = Path(baseline_path).expanduser().resolve()
    current_p = Path(current_path).expanduser().resolve()
    baseline_df = load_table(baseline_p)
    current_df = load_table(current_p)
    baseline = profile_dataframe(baseline_df)
    current = profile_dataframe(current_df)
    generated_contract = build_contract(baseline)
    active_contract = contract or generated_contract
    contract_findings = evaluate_contract(current, active_contract)
    drift_findings = compare_profiles(baseline, current)
    bdup = duplicate_key_rate(baseline_df, key_columns)
    cdup = duplicate_key_rate(current_df, key_columns)
    if bdup is not None and cdup is not None and cdup > bdup + 0.01:
        drift_findings.append(Finding("warning", "drift", "duplicate_key_rate_increased", ",".join(key_columns), "Duplicate-key rate increased.", f"{bdup:.2%}", f"{cdup:.2%}"))
    findings = contract_findings + drift_findings
    contract_errors = sum(f.category == "contract" and f.severity == "error" for f in findings)
    drift_warnings = sum(f.category == "drift" and f.severity == "warning" for f in findings)
    release_gate = "fail" if contract_errors else ("review" if drift_warnings else "pass")
    return {
        "baseline_file": {"name": baseline_p.name, "sha256": sha256_file(baseline_p)},
        "current_file": {"name": current_p.name, "sha256": sha256_file(current_p)},
        "key_columns": key_columns,
        "baseline_profile": baseline,
        "current_profile": current,
        "generated_contract": generated_contract,
        "active_contract": active_contract,
        "summary": {
            "contract_errors": contract_errors,
            "drift_warnings": drift_warnings,
            "info": sum(f.severity == "info" for f in findings),
            "baseline_rows": baseline["row_count"],
            "current_rows": current["row_count"],
            "release_gate": release_gate,
        },
        "contract_findings": [asdict(f) for f in contract_findings],
        "drift_findings": [asdict(f) for f in drift_findings],
        "findings": [asdict(f) for f in findings],
        "limitations": [
            "Drift findings are review signals, not proof of bad data.",
            "The generated contract is intentionally conservative and should be reviewed before operational enforcement.",
            "Type inference is heuristic; domain-specific identifiers may require an explicit contract override.",
        ],
    }


def _unique_output_dir(parent: Path) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = parent / f"data_contract_audit_{stamp}"
    n = 1
    while candidate.exists():
        candidate = parent / f"data_contract_audit_{stamp}_{n}"
        n += 1
    candidate.mkdir()
    return candidate


def save_audit(report: dict, output_dir: str | Path) -> Path:
    out = _unique_output_dir(Path(output_dir).expanduser().resolve())
    (out / "data_contract_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "generated_contract.json").write_text(json.dumps(report["generated_contract"], ensure_ascii=False, indent=2), encoding="utf-8")
    _write_findings_csv(out / "contract_violations.csv", report["contract_findings"])
    _write_findings_csv(out / "drift_findings.csv", report["drift_findings"])
    return out
