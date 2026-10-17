"""Repeatable, fail-closed Data Contract validation for a paid local data auditor.

A generated contract is a starting hypothesis, not certification of a dataset.
This module validates ONLY explicitly described constraints. No network or edits
to imported CSV/XLSX files are performed.
"""
from __future__ import annotations

import csv
import hashlib
import json
import tempfile
from pathlib import Path

import pandas as pd

from contract_auditor import load_table, _infer_kind


def load_contract(path: str | Path) -> dict:
    item = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(item, dict) or type(item.get("version")) is not int or item["version"] != 1:
        raise ValueError("Unsupported or missing contract version (required: 1)")
    if not isinstance(item.get("columns"), dict) or not item["columns"]:
        raise ValueError("Contract must contain at least one column")
    permitted = {"required", "kind", "max_null_rate", "unique", "min", "max", "allowed_values"}
    for name, rules in item["columns"].items():
        if not isinstance(name, str) or not name.strip() or not isinstance(rules, dict):
            raise ValueError("Invalid column definition")
        if set(rules) - permitted:
            raise ValueError(f"Unsupported constraints in {name}: {sorted(set(rules)-permitted)}")
        for flag in ("required", "unique"):
            if flag in rules and not isinstance(rules[flag], bool):
                raise ValueError(f"{name}.{flag} must be boolean")
        if "kind" in rules and rules["kind"] not in {
            "empty", "boolean", "numeric", "numeric_text",
            "datetime", "datetime_text", "categorical", "text"
        }:
            raise ValueError(f"Unknown expected kind in {name}")
        if "max_null_rate" in rules:
            rate = rules["max_null_rate"]
            if isinstance(rate, bool) or not isinstance(rate, (float, int)) or not 0 <= rate <= 1:
                raise ValueError(f"Invalid max_null_rate for {name}")
        if "allowed_values" in rules and (
            not isinstance(rules["allowed_values"], list) or
            len(rules["allowed_values"]) > 500 or
            any(not isinstance(x, (str, int, float, bool)) or pd.isna(x) for x in rules["allowed_values"])
        ):
            raise ValueError(f"Invalid allowed_values for {name}")
        for bound in ("min", "max"):
            if bound in rules and (isinstance(rules[bound], bool) or not isinstance(rules[bound], (int, float))):
                raise ValueError(f"Invalid {bound} for {name}")
        if rules.get("min", float("-inf")) > rules.get("max", float("inf")):
            raise ValueError(f"Impossible min/max for {name}")
    return item


def check_contract(current_path: str | Path, contract: dict) -> dict:
    file = Path(current_path).expanduser().resolve()
    data = load_table(file)
    checks: list[dict] = []
    def add(severity: str, code: str, column: str, detail: str):
        checks.append({"severity": severity, "code": code, "column": column, "detail": detail})
    columns = contract["columns"]
    if not data.columns.is_unique:
        add("error", "duplicate_header", "", "Duplicate column names cannot be proven safe.")
    for name, rules in columns.items():
        if name not in data.columns:
            if rules.get("required", False):
                add("error", "required_missing", name, "Required column was not found.")
            else:
                add("info", "optional_missing", name, "Optional column was not found.")
            continue
        series = data[name]
        if isinstance(series, pd.DataFrame):
            add("error", "ambiguous_header", name, "Column name appears more than once.")
            continue
        kind = _infer_kind(series)
        expected = rules.get("kind")
        compatible_numeric = {kind, expected} <= {"numeric", "numeric_text"} if expected else False
        if expected and kind != expected and not compatible_numeric:
            add("error", "kind_mismatch", name, f"Expected {expected}; observed {kind}.")
        null_rate = float(series.isna().mean()) if len(series) else 0.0
        if "max_null_rate" in rules and null_rate > rules["max_null_rate"]:
            add("error", "null_rate_limit", name, f"{null_rate:.1%} > {rules['max_null_rate']:.1%}")
        nonnull = series.dropna()
        if rules.get("unique", False) and bool(nonnull.duplicated().any()):
            add("error", "duplicate_unique_value", name, "The column has duplicate non-null values.")
        if "allowed_values" in rules:
            allowed = {str(x) for x in rules["allowed_values"]}
            outside = int((~nonnull.astype(str).isin(allowed)).sum())
            if outside:
                add("error", "outside_allowed_values", name, f"{outside} rows outside declared values.")
        if "min" in rules or "max" in rules:
            parsed = pd.to_numeric(nonnull.astype(str).str.replace(",", "", regex=False), errors="coerce")
            bad = int(parsed.isna().sum())
            if bad:
                add("error", "numeric_unverifiable", name, f"{bad} values are not verifiable numbers.")
            else:
                if "min" in rules and bool((parsed < rules["min"]).any()):
                    add("error", "below_min", name, "Some values fall below contract minimum.")
                if "max" in rules and bool((parsed > rules["max"]).any()):
                    add("error", "above_max", name, "Some values exceed contract maximum.")
    extras = sorted(map(str, set(data.columns) - set(columns)))
    if extras:
        add("warning", "extra_columns_unchecked", "", f"{len(extras)} columns not defined in the contract.")
    sha = hashlib.sha256()
    with file.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            sha.update(chunk)
    return {
        "contract_version": 1, "source_file": file.name, "source_sha256": sha.hexdigest(),
        "row_count": len(data), "checked_columns": list(columns),
        "unchecked_columns": extras, "findings": checks,
        "status": "CONTRACT_VIOLATION" if any(x["severity"] == "error" for x in checks)
                  else "NO_VIOLATION_IN_DECLARED_FIELDS",
        "limitation": "This is data structure/constraints validation, not accounting, legal, security or ingestion approval."
    }


def save_contract_audit(result: dict, output_parent: str | Path) -> Path:
    root = Path(output_parent).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix="contract-run-", dir=root))
    (out / "contract_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    def excel_safe(value) -> str:
        text = str(value)
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text
    with (out / "contract_findings.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["severity", "code", "column", "detail"])
        for item in result["findings"]:
            writer.writerow([excel_safe(item.get(x, "")) for x in ("severity","code","column","detail")])
    return out
