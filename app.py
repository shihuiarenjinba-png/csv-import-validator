from __future__ import annotations

import os
import sys
import tkinter as tk
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from contract_auditor import audit_drift, save_audit


DIAGNOSTIC_DIR = Path(os.getenv("LOCALAPPDATA", Path.home())) / "Data Contract Auditor" / "Logs"
FINDING_LABELS = {
    "column_removed": "列の削除",
    "column_added": "列の追加",
    "type_changed": "データ型の変更",
    "null_rate_increased": "空欄率の増加",
    "distribution_changed": "値分布の変化",
    "new_numeric_low": "数値範囲（下限）の変化",
    "new_numeric_high": "数値範囲（上限）の変化",
    "duplicate_key_rate_increased": "キー重複率の増加",
}


def record_failure(operation: str, exc: Exception) -> str:
    diagnostic_id = uuid.uuid4().hex[:12].upper()
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    with (DIAGNOSTIC_DIR / "diagnostics.log").open("a", encoding="utf-8") as handle:
        handle.write(
            f"\n[{datetime.now(timezone.utc).isoformat()}] "
            f"Diagnostic ID={diagnostic_id} operation={operation}\n"
        )
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=handle)
    return diagnostic_id


class DataContractAuditApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Data Contract & Schema Drift Auditor")
        self.geometry("940x720")
        self.minsize(820, 620)

        self.baseline = tk.StringVar()
        self.current = tk.StringVar()
        self.keys = tk.StringVar()
        self.output_dir = tk.StringVar(
            value=str(Path.home() / "Documents" / "Data Contract Auditor" / "Output")
        )
        self.status = tk.StringVar(value="基準ファイルと今回ファイルを選択してください。")
        self.summary = tk.StringVar()
        self.last_output: Path | None = None

        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="Data Contract & Schema Drift Auditor", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text="昨日と今日、旧エクスポートと新エクスポートなどを比較し、列・型・NULL率・分布・キー重複の変化を監査します。",
            wraplength=840,
        ).pack(anchor="w", pady=(4, 14))

        ttk.Label(root, text="Step 1 — 前回データと今回データを選択", font=("Segoe UI", 11, "bold")).pack(
            anchor="w"
        )
        self._path_row(root, "前回データ", self.baseline, lambda: self._pick(self.baseline))
        self._path_row(root, "今回データ", self.current, lambda: self._pick(self.current))
        ttk.Label(root, text="Step 2 — キー列と出力先を設定", font=("Segoe UI", 11, "bold")).pack(
            anchor="w", pady=(8, 0)
        )
        self._path_row(root, "出力先", self.output_dir, self._pick_output)

        ttk.Label(
            root,
            text="入力: CSV / XLSX / XLSM。出力: JSON監査、CSV所見、基準から生成したData Contract。元ファイルは変更しません。",
            wraplength=840,
        ).pack(anchor="w", pady=(2, 8))

        row = ttk.Frame(root)
        row.pack(fill="x", pady=5)
        ttk.Label(row, text="Key列", width=10).pack(side="left")
        ttk.Entry(row, textvariable=self.keys).pack(side="left", fill="x", expand=True)
        ttk.Label(row, text=" 例: customer_id,date").pack(side="left")

        ttk.Label(root, text="Step 3 — 実行前確認", font=("Segoe UI", 11, "bold")).pack(
            anchor="w", pady=(8, 0)
        )
        ttk.Label(root, textvariable=self.summary, wraplength=840).pack(anchor="w", pady=(2, 4))
        ttk.Button(root, text="データ構造と品質の監査を開始", command=self.run_audit).pack(
            anchor="w", pady=(6, 8)
        )
        ttk.Label(root, text="Step 4 — 結果を確認", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(root, textvariable=self.status, wraplength=840).pack(anchor="w", pady=(2, 6))
        self.open_output_button = ttk.Button(
            root, text="出力フォルダを開く", command=self._open_last_output, state="disabled"
        )
        self.open_output_button.pack(anchor="w", pady=(0, 8))

        self.tree = ttk.Treeview(root, columns=("severity", "code", "column", "message", "baseline", "current"), show="headings", height=15)
        for key, title, width in [
            ("severity", "重要度", 75), ("code", "種類", 190), ("column", "列", 140),
            ("message", "内容", 300), ("baseline", "基準", 90), ("current", "今回", 90),
        ]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True)
        for variable in (self.baseline, self.current, self.output_dir, self.keys):
            variable.trace_add("write", self._update_summary)
        self._update_summary()

    def _update_summary(self, *_args) -> None:
        baseline = self.baseline.get().strip() or "未指定"
        current = self.current.get().strip() or "未指定"
        output = self.output_dir.get().strip() or "未指定"
        self.summary.set(
            f"入力: 前回={baseline} / 今回={current}\n出力先: {output}\n処理: 列・型・空欄率・分布・キー重複を比較 / 元ファイル上書き: なし / ネットワーク: なし"
        )

    def _path_row(self, parent, label, variable, command):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=5)
        ttk.Label(row, text=label, width=10).pack(side="left")
        ttk.Entry(row, textvariable=variable).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(row, text="選択", command=command).pack(side="left")

    def _pick(self, variable):
        path = filedialog.askopenfilename(filetypes=[("CSV / Excel", "*.csv *.xlsx *.xlsm"), ("All", "*.*")])
        if path:
            variable.set(path)

    def _pick_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)

    def run_audit(self):
        if not self.baseline.get() or not self.current.get():
            messagebox.showwarning("入力不足", "前回データと今回データを選択してください。")
            return
        keys = [x.strip() for x in self.keys.get().split(",") if x.strip()]
        try:
            report = audit_drift(self.baseline.get(), self.current.get(), key_columns=keys)
            out = save_audit(report, self.output_dir.get())
            for item in self.tree.get_children():
                self.tree.delete(item)
            for f in report["findings"][:1000]:
                self.tree.insert("", "end", values=(
                    f["severity"], FINDING_LABELS.get(f["code"], f["code"]), f["column"], f["message"], f.get("baseline", ""), f.get("current", ""),
                ))
            s = report["summary"]
            self.status.set(f"完了: error={s['errors']} / warning={s['warnings']} / info={s['info']} / {out}")
            self.last_output = Path(out)
            self.open_output_button.configure(state="normal")
            messagebox.showinfo(
                "完了",
                f"監査が完了しました。\nエラー: {s['errors']}件 / 警告: {s['warnings']}件 / 情報: {s['info']}件\n出力フォルダ: {out}",
            )
        except Exception as exc:
            diagnostic_id = record_failure("audit-drift", exc)
            messagebox.showerror(
                "監査失敗",
                f"データの監査に失敗しました。入力ファイル、キー列、出力先を確認してください。\nDiagnostic ID: {diagnostic_id}",
            )
            self.status.set("監査に失敗しました。入力ファイル、キー列、出力先を確認してください。")

    def _open_last_output(self) -> None:
        if self.last_output is None:
            return
        target = self.last_output if self.last_output.is_dir() else self.last_output.parent
        target.mkdir(parents=True, exist_ok=True)
        os.startfile(target)


if __name__ == "__main__":
    if len(sys.argv) >= 5 and sys.argv[1] == "--acceptance-audit":
        keys = [value for value in sys.argv[5].split(",") if value] if len(sys.argv) > 5 else []
        save_audit(audit_drift(sys.argv[2], sys.argv[3], key_columns=keys), sys.argv[4])
    else:
        DataContractAuditApp().mainloop()
