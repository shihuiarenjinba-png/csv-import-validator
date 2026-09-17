from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from contract_auditor import audit_drift, save_audit


class DataContractAuditApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Data Contract & Schema Drift Auditor")
        self.geometry("1020x650")
        self.minsize(900, 560)

        self.baseline = tk.StringVar()
        self.current = tk.StringVar()
        self.contract_path = tk.StringVar()
        self.keys = tk.StringVar()
        self.output_dir = tk.StringVar(value=str(Path.cwd() / "data_contract_audit"))
        self.status = tk.StringVar(value="BaselineとCurrentを選択してください。固定Contractは任意です。")
        self.run_button: ttk.Button | None = None

        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="Data Contract & Schema Drift Auditor", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text=(
                "Contract違反（止めるべき仕様違反）とDrift（レビューすべき傾向変化）を分離して監査します。"
                "固定Contract未指定時はBaselineからレビュー用Contractを生成します。"
            ),
            wraplength=960,
        ).pack(anchor="w", pady=(4, 14))

        self._path_row(root, "Baseline", self.baseline, lambda: self._pick_data(self.baseline))
        self._path_row(root, "Current", self.current, lambda: self._pick_data(self.current))
        self._path_row(root, "Contract", self.contract_path, self._pick_contract)
        self._path_row(root, "出力先", self.output_dir, self._pick_output)

        row = ttk.Frame(root)
        row.pack(fill="x", pady=5)
        ttk.Label(row, text="Key列", width=10).pack(side="left")
        ttk.Entry(row, textvariable=self.keys).pack(side="left", fill="x", expand=True)
        ttk.Label(row, text=" 例: customer_id,date").pack(side="left")

        ttk.Label(
            root,
            text="Contract未指定: Baselineから雛形生成 / Contract指定: そのルールでCurrentを評価",
            wraplength=960,
        ).pack(anchor="w", pady=(4, 8))

        self.run_button = ttk.Button(root, text="Data Contract / Drift監査を実行", command=self.run_audit)
        self.run_button.pack(anchor="w", pady=(8, 8))
        ttk.Label(root, textvariable=self.status, wraplength=960).pack(anchor="w", pady=(0, 10))

        self.tree = ttk.Treeview(
            root,
            columns=("category", "severity", "code", "column", "message", "baseline", "current"),
            show="headings",
            height=16,
        )
        for key, title, width in [
            ("category", "区分", 85),
            ("severity", "重要度", 75),
            ("code", "種類", 195),
            ("column", "列", 125),
            ("message", "内容", 300),
            ("baseline", "基準", 100),
            ("current", "今回", 100),
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

    def _pick_data(self, variable):
        path = filedialog.askopenfilename(filetypes=[("CSV / Excel", "*.csv *.xlsx *.xlsm"), ("All", "*.*")])
        if path:
            variable.set(path)

    def _pick_contract(self):
        path = filedialog.askopenfilename(filetypes=[("JSON Contract", "*.json"), ("All", "*.*")])
        if path:
            self.contract_path.set(path)

    def _pick_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)

    def _load_contract(self) -> dict | None:
        value = self.contract_path.get().strip()
        if not value:
            return None
        path = Path(value).expanduser().resolve()
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "columns" not in data:
            raise ValueError("Contract JSONに columns がありません。")
        return data

    def run_audit(self):
        if not self.baseline.get() or not self.current.get():
            messagebox.showwarning("入力不足", "BaselineとCurrentを選択してください。")
            return
        if self.run_button:
            self.run_button.state(["disabled"])
        self.status.set("監査中…")
        threading.Thread(target=self._run_worker, daemon=True).start()

    def _run_worker(self):
        try:
            keys = [x.strip() for x in self.keys.get().split(",") if x.strip()]
            contract = self._load_contract()
            report = audit_drift(self.baseline.get(), self.current.get(), key_columns=keys, contract=contract)
            out = save_audit(report, self.output_dir.get())
            self.after(0, self._show_result, report, out)
        except Exception as exc:
            self.after(0, self._show_error, exc)

    def _show_result(self, report: dict, out: Path):
        if self.run_button:
            self.run_button.state(["!disabled"])
        for item in self.tree.get_children():
            self.tree.delete(item)
        for f in report["findings"][:1500]:
            self.tree.insert("", "end", values=(
                f.get("category", ""), f["severity"], f["code"], f["column"], f["message"],
                f.get("baseline", ""), f.get("current", ""),
            ))
        s = report["summary"]
        self.status.set(
            f"完了: Contract errors={s['contract_errors']} / Drift warnings={s['drift_warnings']} / "
            f"Info={s['info']} / gate={s['release_gate']} / {out}"
        )
        if s["contract_errors"]:
            messagebox.showwarning("Contract違反あり", f"{s['contract_errors']}件のContract errorがあります。\n\n{out}")
        else:
            messagebox.showinfo("監査完了", f"Contract errorはありません。Drift候補を確認してください。\n\n{out}")

    def _show_error(self, exc: Exception):
        if self.run_button:
            self.run_button.state(["!disabled"])
        self.status.set(f"失敗: {exc}")
        messagebox.showerror("監査失敗", str(exc))


if __name__ == "__main__":
    DataContractAuditApp().mainloop()
