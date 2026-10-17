from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from contract_auditor import audit_drift, save_audit
from contract_runtime import check_contract, load_contract, save_contract_audit


class DataContractAuditApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Data Contract & Schema Drift Auditor")
        self.geometry("900x580")
        self.minsize(800, 500)

        self.baseline = tk.StringVar()
        self.current = tk.StringVar()
        self.keys = tk.StringVar()
        self.output_dir = tk.StringVar(value=str((Path.home() / "Documents" if (Path.home() / "Documents").is_dir() else Path.home()) / "DataContractAudits"))
        self.status = tk.StringVar(value="基準ファイルと今回ファイルを選択してください。")

        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="Data Contract & Schema Drift Auditor", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text="昨日と今日、旧エクスポートと新エクスポートなどを比較し、列・型・NULL率・分布・キー重複の変化を監査します。",
            wraplength=840,
        ).pack(anchor="w", pady=(4, 14))

        self._path_row(root, "Baseline", self.baseline, lambda: self._pick(self.baseline))
        self._path_row(root, "Current", self.current, lambda: self._pick(self.current))
        self._path_row(root, "出力先", self.output_dir, self._pick_output)

        row = ttk.Frame(root)
        row.pack(fill="x", pady=5)
        ttk.Label(row, text="Key列", width=10).pack(side="left")
        ttk.Entry(row, textvariable=self.keys).pack(side="left", fill="x", expand=True)
        ttk.Label(row, text=" 例: customer_id,date").pack(side="left")

        controls = ttk.Frame(root)
        controls.pack(anchor="w", pady=(12, 8))
        ttk.Button(controls, text="基準と今回を比較", command=self.run_audit).pack(side="left")
        ttk.Button(controls, text="保存済みContractで今回を検査", command=self.run_saved_contract).pack(side="left", padx=(10, 0))
        ttk.Label(root, textvariable=self.status, wraplength=840).pack(anchor="w", pady=(0, 10))

        self.tree = ttk.Treeview(root, columns=("severity", "code", "column", "message", "baseline", "current"), show="headings", height=15)
        for key, title, width in [
            ("severity", "重要度", 75), ("code", "種類", 190), ("column", "列", 140),
            ("message", "内容", 300), ("baseline", "基準", 90), ("current", "今回", 90),
        ]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True)

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
            messagebox.showwarning("入力不足", "BaselineとCurrentを選択してください。")
            return
        keys = [x.strip() for x in self.keys.get().split(",") if x.strip()]
        try:
            report = audit_drift(self.baseline.get(), self.current.get(), key_columns=keys)
            out = save_audit(report, self.output_dir.get())
            for item in self.tree.get_children():
                self.tree.delete(item)
            for f in report["findings"][:1000]:
                self.tree.insert("", "end", values=(
                    f["severity"], f["code"], f["column"], f["message"], f.get("baseline", ""), f.get("current", ""),
                ))
            s = report["summary"]
            self.status.set(f"完了: error={s['errors']} / warning={s['warnings']} / info={s['info']} / {out}")
        except Exception as exc:
            messagebox.showerror("監査失敗", str(exc))
            self.status.set(f"失敗: {exc}")


    def run_saved_contract(self):
        if not self.current.get():
            messagebox.showwarning("入力不足", "今回ファイルを先に選択してください。")
            return
        contract_file = filedialog.askopenfilename(
            title="以前保存したContract JSONを選択",
            filetypes=[("Data Contract JSON", "*.json"), ("All", "*.*")]
        )
        if not contract_file:
            return
        try:
            report = check_contract(self.current.get(), load_contract(contract_file))
            output = save_contract_audit(report, self.output_dir.get())
            for item in self.tree.get_children():
                self.tree.delete(item)
            for issue in report["findings"][:1000]:
                self.tree.insert("", "end", values=(
                    issue["severity"], issue["code"], issue["column"],
                    issue["detail"], "", ""
                ))
            self.status.set(
                f"{report['status']} / 検証対象 {len(report['checked_columns'])}列 / "
                f"対象外 {len(report['unchecked_columns'])}列 / {output}"
            )
        except Exception as exc:
            messagebox.showerror("Contract検証失敗", str(exc))
            self.status.set(f"失敗: {exc}")


if __name__ == "__main__":
    DataContractAuditApp().mainloop()
