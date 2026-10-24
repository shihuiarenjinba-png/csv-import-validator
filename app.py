from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from contract_auditor import audit_drift, save_audit
from i18n import translate
from ui_desktop import bind_shortcuts, restore_window_state, save_window_state


class DataContractAuditApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Data Contract Auditor")
        self.geometry("900x580")
        self.minsize(800, 500)
        restore_window_state(self, "DataContractAuditor", min_width=800, min_height=500)

        self.baseline = tk.StringVar()
        self.current = tk.StringVar()
        self.keys = tk.StringVar()
        self.output_dir = tk.StringVar(value=str(Path.cwd() / "data_contract_audit"))
        self.status = tk.StringVar(value="基準ファイルと今回ファイルを選択してください。")
        self.severity_filter = tk.StringVar(value="ALL")
        self._findings: list[dict] = []
        self._events = queue.Queue()
        self._running = False

        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="Data Contract Auditor", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text="昨日と今日、旧エクスポートと新エクスポートなどを比較し、列・型・NULL率・分布・キー重複の変化を監査します。",
            wraplength=840,
        ).pack(anchor="w", pady=(4, 14))

        ttk.Label(
            root,
            text="① 基準と今回を選択  →  ② Key列は必要な場合だけ指定  →  ③ 比較結果を確認",
            font=("Segoe UI", 10, "bold"),
            wraplength=840,
        ).pack(anchor="w", pady=(0, 3))
        ttk.Label(
            root,
            text="元ファイルは変更しません。結果は指定した出力先へ保存します。",
            wraplength=840,
        ).pack(anchor="w", pady=(0, 10))
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
        ttk.Label(root, textvariable=self.status, wraplength=840).pack(anchor="w", pady=(0, 6))
        filter_row = ttk.Frame(root)
        filter_row.pack(fill="x", pady=(0, 6))
        ttk.Label(filter_row, text="Show results:").pack(side="left")
        severity = ttk.Combobox(filter_row, state="readonly", width=12,
                                textvariable=self.severity_filter,
                                values=("ALL", "ERROR", "WARNING", "INFO"))
        severity.pack(side="left", padx=(6, 0))
        severity.bind("<<ComboboxSelected>>", lambda _event: self._render_findings())

        self.tree = ttk.Treeview(root, columns=("severity", "code", "column", "message", "baseline", "current"), show="headings", height=15)
        self._tree_titles = {
            "severity": ("重要度", 75), "code": ("種類", 190), "column": ("列", 140),
            "message": ("内容", 300), "baseline": ("基準", 90), "current": ("今回", 90),
        }
        for key, (title, width) in self._tree_titles.items():
            self.tree.heading(key, text=translate(title))
            self.tree.column(key, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.after(150, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.baseline.trace_add("write", lambda *_: self._refresh_actions())
        self.current.trace_add("write", lambda *_: self._refresh_actions())
        bind_shortcuts(self, {
            "<Control-Return>": self.run_audit,
            "<F5>": self.run_audit,
            "<Control-Shift-S>": self._pick_output,
        })
        self._refresh_actions()

    def refresh_i18n(self):
        for key, (title, _width) in self._tree_titles.items():
            self.tree.heading(key, text=translate(title))

    def _render_findings(self):
        selected = self.severity_filter.get().lower()
        findings = self._findings if selected == "all" else [
            item for item in self._findings if str(item.get("severity", "")).lower() == selected
        ]
        for item in self.tree.get_children():
            self.tree.delete(item)
        for finding in findings[:1000]:
            self.tree.insert("", "end", values=(
                finding["severity"], finding["code"], finding["column"],
                finding["message"], finding.get("baseline", ""), finding.get("current", ""),
            ))

    def _refresh_actions(self):
        ready = bool(self.baseline.get().strip() and self.current.get().strip()) and not self._running
        self.run_button.state(["!disabled"] if ready else ["disabled"])

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
        self._refresh_actions()
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
                self._refresh_actions()
                if ok:
                    report = value
                    self._findings = list(report["findings"])
                    self._render_findings()
                    s = report["summary"]
                    self.status.set(
                        f"監査完了: error={s['errors']} / warning={s['warnings']} / "
                        f"info={s['info']}。保存先: {Path(out).name}"
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
        save_window_state(self, "DataContractAuditor")
        self.destroy()


if __name__ == "__main__":
    from i18n import install_bilingual_ui

    app = DataContractAuditApp()
    install_bilingual_ui(app)
    app.mainloop()
