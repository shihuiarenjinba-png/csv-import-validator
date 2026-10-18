from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from contract_auditor import audit_drift, save_audit
from audit_review_gate import input_revision
from gui_schema_columns import common_key_candidates


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
        self._column_events = queue.Queue()
        self._running = False
        self._preview_signature = None

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
        self.key_pick_btn = ttk.Button(row, text="列名から選ぶ", command=self._pick_keys)
        self.key_pick_btn.pack(side="left", padx=(8, 0))
        ttk.Label(root, text="Key列は任意です。列名から選ぶか、カンマ区切りで入力できます。"
                  "Key列を指定しない場合、重複キーの比較は行いません。",
                  wraplength=840).pack(anchor="w")

        actions = ttk.Frame(root)
        actions.pack(anchor="w", pady=(12, 8))
        self.preview_button = ttk.Button(actions, text="1  試運転（保存なし）",
                                         command=lambda: self.run_audit(preview=True))
        self.preview_button.pack(side="left", padx=(0, 8))
        self.run_button = ttk.Button(actions, text="2  確認してレポート保存",
                                     command=lambda: self.run_audit(preview=False))
        self.run_button.pack(side="left")
        ttk.Label(root, text="試運転後、同じ入力ファイル・同じKey列の場合だけ保存できます。"
                  "入力内容を変更した場合はもう一度試運転してください。",
                  wraplength=840).pack(anchor="w")
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

    def _pick_keys(self):
        """Load headers in a background thread; never freeze the UI for Excel."""
        if self._running:
            return
        baseline = self.baseline.get().strip()
        current = self.current.get().strip()
        if not baseline or not current:
            messagebox.showinfo("列の選択", "先に基準ファイルと今回ファイルを選んでください。")
            return
        self.key_pick_btn.state(["disabled"])
        self.status.set("両方のファイルの列名を読み込んでいます...")

        def work():
            try:
                names = common_key_candidates(baseline, current)
                self._column_events.put((True, names))
            except Exception as exc:
                self._column_events.put((False, str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def _show_key_picker(self, names):
        dialog = tk.Toplevel(self)
        dialog.title("比較に使うKey列を選ぶ")
        dialog.geometry("520x430")
        dialog.transient(self)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="両方のファイルに共通する列から選択してください。"
                  "CtrlまたはShiftで複数選べます。").pack(anchor="w", pady=(0, 8))
        listbox = tk.Listbox(frame, selectmode=tk.EXTENDED, exportselection=False)
        listbox.pack(fill="both", expand=True)
        current = {x.strip() for x in self.keys.get().split(",") if x.strip()}
        for index, name in enumerate(names):
            listbox.insert("end", name)
            if name in current:
                listbox.selection_set(index)
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(12, 0))
        def accept():
            chosen = [names[int(i)] for i in listbox.curselection()]
            self.keys.set(",".join(chosen))
            self._preview_signature = None
            self.status.set(f"Key列を{len(chosen)}件選択しました。次に試運転をしてください。")
            dialog.destroy()
        ttk.Button(buttons, text="この列を使う", command=accept).pack(side="left")
        ttk.Button(buttons, text="キャンセル", command=dialog.destroy).pack(
            side="left", padx=(10, 0))

    def run_audit(self, *, preview: bool = False):
        if self._running:
            return
        baseline = self.baseline.get().strip()
        current = self.current.get().strip()
        keys = [x.strip() for x in self.keys.get().split(",") if x.strip()]
        output_dir = self.output_dir.get().strip()
        try:
            signature = input_revision(baseline, current, keys)
            if not preview and not output_dir:
                raise ValueError("レポートの保存先を選択してください。")
        except (ValueError, OSError) as exc:
            messagebox.showwarning("入力の確認", str(exc))
            self.status.set(f"入力を確認してください: {exc}")
            return
        if not preview:
            if signature != self._preview_signature:
                messagebox.showwarning("再試運転が必要",
                                       "入力ファイルまたはKey列が変わりました。先に試運転してください。")
                return
            if not messagebox.askyesno(
                "レポート作成の確認",
                "試運転した入力を分析して新しい監査フォルダーを作成します。"
                "元のCSV/Excelは上書きしません。続行しますか？",
            ):
                return
        self._running = True
        self.run_button.state(["disabled"])
        self.preview_button.state(["disabled"])
        self.progress.start(15)
        self.status.set("保存なしで確認中..." if preview else "検査とレポート保存中...")

        def worker():
            try:
                if input_revision(baseline, current, keys) != signature:
                    raise ValueError("入力が処理開始前に変更されました。")
                report = audit_drift(baseline, current, key_columns=keys)
                if input_revision(baseline, current, keys) != signature:
                    raise ValueError("解析中に入力が変更されました。保存を中止しました。")
                out = "" if preview else str(save_audit(report, output_dir))
                self._events.put((True, report, out, preview, signature))
            except Exception as exc:
                self._events.put((False, str(exc), "", preview, None))
        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            while True:
                ok, result = self._column_events.get_nowait()
                self.key_pick_btn.state(["!disabled"])
                if ok:
                    self._show_key_picker(result)
                else:
                    self.status.set("列を読み込めませんでした。入力形式・権限を確認してください。")
                    messagebox.showwarning("列の取得に失敗", str(result))
        except queue.Empty:
            pass
        try:
            while True:
                ok, value, out, preview, signature = self._events.get_nowait()
                self._running = False
                self.progress.stop()
                self.run_button.state(["!disabled"])
                self.preview_button.state(["!disabled"])
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
                    if preview:
                        self._preview_signature = signature
                        self.status.set(
                            f"試運転完了（ファイル保存なし）: errors={s['errors']}, "
                            f"warnings={s['warnings']}, info={s['info']}。"
                            "内容を確認して「確認してレポート保存」を押してください。"
                        )
                    else:
                        self._preview_signature = None
                        self.status.set(
                            f"監査完了: errors={s['errors']}, warnings={s['warnings']}, "
                            f"info={s['info']}。新しい保存先: {out}"
                        )
                else:
                    self._preview_signature = None
                    self.status.set(f"監査失敗: {value}。ファイル形式・権限・容量を確認してください。")
                    messagebox.showerror("監査失敗", str(value) + "\n\n"
                                         "入力形式、ファイル破損、Key列、保存先の権限・容量を確認してください。")
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
