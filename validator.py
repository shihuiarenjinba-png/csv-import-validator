from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

ENCODINGS = ("utf-8-sig", "utf-8", "cp932", "utf-16")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
NUMERIC_LITERAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_text(path: Path) -> tuple[str, str]:
    for encoding in ENCODINGS:
        try:
            return path.read_text(encoding=encoding), encoding
        except UnicodeError:
            continue
    raise ValueError("対応文字コードとして読み込めませんでした。")


def _dialect(text: str):
    try:
        return csv.Sniffer().sniff(text[:8192], delimiters=",\t;")
    except csv.Error:
        return csv.excel


def _formula_candidate(value: str) -> bool:
    stripped = value.lstrip()
    if not stripped:
        return False
    if stripped[0] in "=@":
        return True
    if stripped[0] in "+-":
        # 普通の符号付き数値はFormula Injection候補にしない。
        return not bool(NUMERIC_LITERAL_RE.fullmatch(stripped.replace(",", "")))
    return False


def _safe_csv(value: object) -> object:
    if not isinstance(value, str):
        return value
    if _formula_candidate(value):
        return "'" + value
    return value


def _issue(severity: str, code: str, message: str, row=None, column=None, value=None) -> dict:
    return {
        "severity": severity,
        "code": code,
        "row": row,
        "column": column,
        "message": message,
        "value_preview": "" if value is None else str(value)[:120],
    }


def validate_csv(
    input_path: str | Path,
    output_parent: str | Path,
    schema: dict | None = None,
) -> Path:
    source = Path(input_path).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".csv":
        raise ValueError("CSVファイルを指定してください。")

    schema = schema or {}
    text, encoding = _read_text(source)
    dialect = _dialect(text)
    reader = csv.reader(text.splitlines(), dialect)

    issues: list[dict] = []
    try:
        raw_headers = next(reader)
    except StopIteration:
        raw_headers = []

    headers = [str(h).strip() for h in raw_headers]
    if not headers:
        issues.append(_issue("error", "empty_file", "ヘッダーがありません。", row=1))
    else:
        for index, header in enumerate(headers, start=1):
            if not header:
                issues.append(_issue("error", "blank_header", "空の列名があります。", row=1, column=index))
        for name, count in Counter(headers).items():
            if name and count > 1:
                issues.append(_issue("error", "duplicate_header", f"列名 '{name}' が{count}回あります。", row=1, column=name))

    expected = list(schema.get("expected_columns", []))
    required = list(schema.get("required_columns", []))
    key_columns = list(schema.get("key_columns", []))
    allow_extra = bool(schema.get("allow_extra_columns", True))

    if expected:
        missing = [c for c in expected if c not in headers]
        extra = [c for c in headers if c not in expected]
        for column in missing:
            issues.append(_issue("error", "missing_expected_column", f"期待列 '{column}' がありません。", column=column))
        if not allow_extra:
            for column in extra:
                issues.append(_issue("warning", "extra_column", f"想定外の列 '{column}' があります。", column=column))

    for column in required:
        if column not in headers:
            issues.append(_issue("error", "missing_required_column", f"必須列 '{column}' がありません。", column=column))
    for column in key_columns:
        if column not in headers:
            issues.append(_issue("error", "missing_key_column", f"キー列 '{column}' がありません。", column=column))

    key_indexes = [headers.index(c) for c in key_columns if c in headers]
    seen_keys: dict[tuple[str, ...], int] = {}
    data_rows = 0

    for row_number, values in enumerate(reader, start=2):
        if not any(str(v).strip() for v in values):
            continue
        data_rows += 1
        if len(values) != len(headers):
            issues.append(_issue("error", "column_count_mismatch", f"列数がヘッダーと一致しません ({len(values)} != {len(headers)})。", row=row_number))
            continue

        for index, value in enumerate(values):
            column = headers[index] if index < len(headers) else str(index + 1)
            if CONTROL_RE.search(value):
                issues.append(_issue("warning", "control_character", "制御文字候補があります。", row_number, column, value))
            if _formula_candidate(value):
                issues.append(_issue("warning", "formula_prefix_candidate", "表計算ソフトで数式として解釈され得る値です。", row_number, column, value))

        for column in required:
            if column in headers and not values[headers.index(column)].strip():
                issues.append(_issue("error", "required_blank", f"必須列 '{column}' が空です。", row_number, column))

        if key_indexes:
            key = tuple(values[i].strip() for i in key_indexes)
            if any(not part for part in key):
                issues.append(_issue("error", "blank_key", "キー列に空欄があります。", row_number, ",".join(key_columns)))
            elif key in seen_keys:
                issues.append(_issue(
                    "error", "duplicate_key", f"キーが重複しています。最初の出現行: {seen_keys[key]}",
                    row_number, ",".join(key_columns), " | ".join(key),
                ))
            else:
                seen_keys[key] = row_number

    parent = Path(output_parent).expanduser().resolve()
    parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = parent / f"csv_validation_{stamp}"
    suffix = 1
    while run_dir.exists():
        run_dir = parent / f"csv_validation_{stamp}_{suffix}"
        suffix += 1
    run_dir.mkdir()

    summary = {
        "source_file": {"name": source.name, "sha256": sha256_file(source)},
        "encoding": encoding,
        "delimiter": getattr(dialect, "delimiter", ","),
        "headers": headers,
        "data_rows": data_rows,
        "error_count": sum(i["severity"] == "error" for i in issues),
        "warning_count": sum(i["severity"] == "warning" for i in issues),
        "issues": issues,
        "schema": schema,
        "limitations": [
            "Formula-prefix findings identify spreadsheet-execution candidates; they do not prove malicious content.",
            "CSV encoding detection is limited to the supported encoding list.",
        ],
    }
    (run_dir / "report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with (run_dir / "issues.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        fieldnames = ["severity", "code", "row", "column", "message", "value_preview"]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for issue in issues:
            writer.writerow({key: _safe_csv(issue.get(key, "")) for key in fieldnames})

    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="CSV Import Validator")
    parser.add_argument("input")
    parser.add_argument("--schema")
    parser.add_argument("--output", default="reports")
    args = parser.parse_args()
    schema = json.loads(Path(args.schema).read_text(encoding="utf-8")) if args.schema else None
    print(validate_csv(args.input, args.output, schema))


if __name__ == "__main__":
    main()
