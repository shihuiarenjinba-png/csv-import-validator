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
        self.status = tk.StringVar(value="まず2つのファイルを選んでください。")
        self.severity_filter = tk.StringVar(value="ALL")
        self._findings: list[dict] = []
        self._events = queue.Queue()
        self._running = False

        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text="Data Contract Auditor", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text="前回のCSV / Excelと今回のCSV / Excelを比べて、列・型・欠損・重複・値の変化を見つけます。",
            wraplength=840,
        ).pack(anchor="w", pady=(4, 2))
        ttk.Label(
            root,
            text="元ファイルは変更しません。通常は下の2つを選んで「比較を開始」を押すだけです。",
            wraplength=840,
        ).pack(anchor="w", pady=(0, 12))

        self._file_row(
            root,
            "① 基準ファイル（前回・正常）",
            "以前の正常なCSV / Excel。比較の基準になります。",
            self.baseline,
            lambda: self._pick(self.baseline),
        )
        self._file_row(
            root,
            "② 今回ファイル（新しい方）",
            "今回確認したいCSV / Excel。基準との差を検出します。",
            self.current,
            lambda: self._pick(self.current),
        )

        self.advanced_toggle = ttk.Button(root, text="詳細設定", command=self._toggle_advanced)
        self.advanced_toggle.pack(anchor="w", pady=(2, 4))

        self.advanced_frame = ttk.LabelFrame(root, text="詳細設定（通常は変更不要）", padding=(10, 7))
        self._advanced_path_row(self.advanced_frame, "結果の保存先", self.output_dir, self._pick_output)

        key_row = ttk.Frame(self.advanced_frame)
        key_row.pack(fill="x", pady=3)
        ttk.Label(key_row, text="重複チェック用の列", width=18).pack(side="left")
        ttk.Entry(key_row, textvariable=self.keys).pack(side="left", fill="x", expand=True)
        ttk.Label(key_row, text="任意。例: id / customer_id,date").pack(side="left", padx=(6, 0))

        self.compare_button = ttk.Button(root, text="③ 比較を開始", command=self.run_audit, state="disabled")
        self.compare_button.pack(anchor="w", pady=(2, 8))

        self.progress = ttk.Progressbar(root, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 4))
        ttk.Label(root, textvariable=self.status, wraplength=840).pack(anchor="w", pady=(0, 6))

        result_header = ttk.Frame(root)
        result_header.pack(fill="x", pady=(2, 5))
        ttk.Label(result_header, text="検出された変更", font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Label(result_header, text="表示:").pack(side="left", padx=(18, 4))
        severity = ttk.Combobox(
            result_header,
            state="readonly",
            width=12,
            textvariable=self.severity_filter,
            values=("ALL", "ERROR", "WARNING", "INFO"),
        )
        severity.pack(side="left")
        severity.bind("<<ComboboxSelected>>", lambda _event: self._render_findings())

        self.tree = ttk.Treeview(
            root,
            columns=("severity", "code", "column", "message", "baseline", "current"),
            show="headings",
            height=12,
        )
        self._tree_titles = {
            "severity": ("重要度", 75),
            "code": ("種類", 190),
            "column": ("列", 140),
            "message": ("内容", 300),
            "baseline": ("基準", 90),
            "current": ("今回", 90),
        }
        for key, (title, width) in self._tree_titles.items():
            self.tree.heading(key, text=translate(title))
            self.tree.column(key, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True)

        self._poll_after_id = self.after(150, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.baseline.trace_add("write", lambda *_: self._refresh_actions())
        self.current.trace_add("write", lambda *_: self._refresh_actions())
        bind_shortcuts(
            self,
            {
                "<Control-Return>": self.run_audit,
                "<F5>": self.run_audit,
                "<Control-Shift-S>": self._pick_output,
            },
        )
        self._refresh_actions()

    def refresh_i18n(self):
        for key, (title, _width) in self._tree_titles.items():
            self.tree.heading(key, text=translate(title))

    def _file_row(self, parent, label, help_text, variable, browse_command):
        block = ttk.Frame(parent)
        block.pack(fill="x", pady=(2, 8))
        ttk.Label(block, text=label, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        ttk.Label(block, text=help_text).pack(anchor="w", pady=(1, 3))
        row = ttk.Frame(block)
        row.pack(fill="x")
        entry = ttk.Entry(row, textvariable=variable)
        entry.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="選択", command=browse_command, width=8).pack(side="left", padx=(6, 0))

    def _toggle_advanced(self):
        if self.advanced_frame.winfo_manager():
            self.advanced_frame.pack_forget()
        else:
            self.advanced_frame.pack(fill="x", pady=(0, 8), before=self.compare_button)

    def _advanced_path_row(self, parent, label, variable, browse_command):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=3)
        ttk.Label(row, text=label, width=18).pack(side="left")
        entry = ttk.Entry(row, textvariable=variable)
        entry.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="選択", command=browse_command, width=8).pack(side="left", padx=(6, 0))

    def _render_findings(self):
        selected = self.severity_filter.get().lower()
        findings = self._findings if selected == "all" else [
            item for item in self._findings if str(item.get("severity", "")).lower() == selected
        ]
        for item in self.tree.get_children():
            self.tree.delete(item)
        for finding in findings[:1000]:
            self.tree.insert(
                "",
                "end",
                values=(
                    finding["severity"],
                    finding["code"],
                    finding["column"],
                    finding["message"],
                    finding.get("baseline", ""),
                    finding.get("current", ""),
                ),
            )

    def _refresh_actions(self):
        ready = bool(self.baseline.get().strip() and self.current.get().strip()) and not self._running
        self.compare_button.configure(state="normal" if ready else "disabled")

    def _pick(self, variable):
        path = filedialog.askopenfilename(
            filetypes=[("CSV / Excel", "*.csv *.xlsx *.xlsm"), ("All", "*.*")]
        )
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

        baseline = self.baseline.get().strip().strip('"')
        current = self.current.get().strip().strip('"')
        self.baseline.set(baseline)
        self.current.set(current)

        if Path(baseline).resolve() == Path(current).resolve():
            messagebox.showwarning("選択エラー", "同じファイル同士の監査はできません。")
            return

        keys = [x.strip() for x in self.keys.get().split(",") if x.strip()]
        output_dir = self.output_dir.get().strip().strip('"')
        self.output_dir.set(output_dir)

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
        try:
            if self.winfo_exists():
                self._poll_after_id = self.after(150, self._poll)
        except tk.TclError:
            self._poll_after_id = None

    def _close(self):
        if self._running:
            messagebox.showwarning("処理中", "監査が完了するまではウィンドウを閉じないでください。")
            return
        save_window_state(self, "DataContractAuditor")
        after_id = getattr(self, "_poll_after_id", None)
        if after_id:
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass
            self._poll_after_id = None
        self.destroy()


if __name__ == "__main__":
    from i18n import install_bilingual_ui

    app = DataContractAuditApp()
    install_bilingual_ui(app)
    app.mainloop()
