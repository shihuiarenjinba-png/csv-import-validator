from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from validator import validate_csv


class CsvValidatorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("CSV Import Validator")
        self.geometry("760x390")
        self.minsize(680, 350)
        self.input_var = tk.StringVar()
        self.schema_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(Path.home() / "Documents"))
        self.status_var = tk.StringVar(value="CSVを選択してください。")
        self._build()

    def _build(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)

        self._row(root, 0, "CSV", self.input_var, self._pick_csv)
        self._row(root, 1, "スキーマ(JSON・任意)", self.schema_var, self._pick_schema)
        self._row(root, 2, "出力先", self.output_var, self._pick_output)

        ttk.Label(root, text="スキーマなしでも文字コード・列数・数式候補などを検査できます。", wraplength=690).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(12, 0)
        )
        ttk.Label(root, textvariable=self.status_var, wraplength=690).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(14, 0)
        )
        ttk.Button(root, text="検査を実行", command=self._run).grid(row=5, column=0, columnspan=3, pady=18)

    def _row(self, parent, row, label, variable, command) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=7)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=7)
        ttk.Button(parent, text="選択", command=command).grid(row=row, column=2, padx=(8, 0), pady=7)

    def _pick_csv(self) -> None:
        value = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if value:
            self.input_var.set(value)

    def _pick_schema(self) -> None:
        value = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if value:
            self.schema_var.set(value)

    def _pick_output(self) -> None:
        value = filedialog.askdirectory()
        if value:
            self.output_var.set(value)

    def _run(self) -> None:
        try:
            schema = None
            if self.schema_var.get().strip():
                schema = json.loads(Path(self.schema_var.get()).read_text(encoding="utf-8"))
            result = validate_csv(self.input_var.get(), self.output_var.get(), schema)
            report = json.loads((result / "report.json").read_text(encoding="utf-8"))
        except Exception as exc:
            self.status_var.set(f"エラー: {exc}")
            messagebox.showerror("検査エラー", str(exc))
            return

        self.status_var.set(
            f"完了: エラー {report['error_count']} / 警告 {report['warning_count']} / {result}"
        )
        messagebox.showinfo("完了", self.status_var.get())


if __name__ == "__main__":
    CsvValidatorApp().mainloop()
