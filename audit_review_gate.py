"""Read-only input approval and mutation guard for schema drift audits.

The preview approval is pinned to exact input bytes, filenames and key mapping.
All decisions are made before any report directory is created.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

MAX_FILE_BYTES = 100 * 1024 * 1024
SUPPORTED = {".csv", ".xlsx", ".xlsm"}


def input_revision(baseline: str, current: str, keys: list[str]) -> tuple:
    """Return stable input identities; raise actionable errors on unsafe inputs."""
    if len(set(keys)) != len(keys):
        raise ValueError("Key列が重複しています。各Key列は一度だけ指定してください。")
    if not baseline.strip() or not current.strip():
        raise ValueError("BaselineとCurrentの両方を選択してください。")
    paths = (Path(baseline).expanduser(), Path(current).expanduser())
    resolved = []
    for label, path in zip(("Baseline", "Current"), paths):
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"{label}は存在する通常ファイルを選択してください。")
        if path.suffix.lower() not in SUPPORTED:
            raise ValueError(f"{label}の形式はCSV、XLSX、XLSMに限ります。")
        stat = path.stat()
        if stat.st_size <= 0 or stat.st_size > MAX_FILE_BYTES:
            raise ValueError(f"{label}は1バイト以上、100MiB以下にしてください。")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if path.stat().st_size != stat.st_size or path.stat().st_mtime_ns != stat.st_mtime_ns:
            raise ValueError(f"{label}が検査中に変更されました。もう一度試運転してください。")
        resolved.append((str(path.resolve()), stat.st_size, digest.hexdigest()))
    if resolved[0][0] == resolved[1][0]:
        raise ValueError("同じファイルをBaselineとCurrentの両方に指定できません。")
    return (tuple(resolved), tuple(keys))
