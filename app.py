from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from contract_auditor import audit_drift, save_audit


class DataContractAuditApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Data Contract & Schema Drift Auditor")
        self.geometry("900x580")
        self.minsize(800, 500)

        self.baseline = tk.StringVar()
        self.current = tk.StringVar()
        self.keys = tk.StringVar()
        self.output_dir = tk.StringVar(value=str(Path.cwd() / "data_contract_audit"))
        self.status = tk.StringVar(value="基準ファイルと今回ファイルを選択してください。")
        self._events = queue.Queue()
        self._running = False

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

        self.run_button = ttk.Button(root, text="Schema Drift監査を実行", command=self.run_audit)
        self.run_button.pack(anchor="w", pady=(12, 8))
        self.progress = ttk.Progressbar(root, mode="indeterminate")
        self.progress.pack(fill="x", pady=4)
        ttk.Label(root, textvariable=self.status, wraplength=840).pack(anchor="w", pady=(0, 10))

        self.tree = ttk.Treeview(root, columns=("severity", "code", "column", "message", "baseline", "current"), show="headings", height=15)
        for key, title, width in [
            ("severity", "重要度", 75), ("code", "種類", 190), ("column", "列", 140),
            ("message", "内容", 300), ("baseline", "基準", 90), ("current", "今回", 90),
        ]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.after(150, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)

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
        if self._running:
            return
        if not self.baseline.get() or not self.current.get():
            messagebox.showwarning("入力不足", "BaselineとCurrentを選択してください。")
            return
        baseline = self.baseline.get()
        current = self.current.get()
        if Path(baseline).resolve() == Path(current).resolve():
            messagebox.showwarning("選択エラー", "同じファイル同士の監査はできません。")
            return
        keys = [x.strip() for x in self.keys.get().split(",") if x.strip()]
        output_dir = self.output_dir.get()
        self._running = True
        self.run_button.state(["disabled"])
        self.progress.start(15)
        self.status.set("解析中です。元データは変更しません。")

        def worker():
            try:
                report = audit_drift(baseline, current, key_columns=keys)
                out = save_audit(report, output_dir)
                self._events.put((True, report, str(out)))
            except Exception as exc:
                self._events.put((False, str(exc), ""))
        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            while True:
                ok, value, out = self._events.get_nowait()
                self._running = False
                self.progress.stop()
                self.run_button.state(["!disabled"])
                if ok:
                    report = value
                    for item in self.tree.get_children():
                        self.tree.delete(item)
                    for finding in report["findings"][:1000]:
                        self.tree.insert("", "end", values=(
                            finding["severity"], finding["code"], finding["column"],
                            finding["message"], finding.get("baseline", ""),
                            finding.get("current", ""),
                        ))
                    s = report["summary"]
                    self.status.set(
                        f"監査完了: error={s['errors']} / warning={s['warnings']} / "
                        f"info={s['info']}。新しい保存フォルダ: {out}"
                    )
                else:
                    self.status.set(f"監査失敗: {value}")
                    messagebox.showerror("監査失敗", value)
        except queue.Empty:
            pass
        self.after(150, self._poll)

    def _close(self):
        if self._running:
            messagebox.showwarning("処理中", "監査が完了するまではウィンドウを閉じないでください。")
            return
        self.destroy()


if __name__ == "__main__":
    DataContractAuditApp().mainloop()
