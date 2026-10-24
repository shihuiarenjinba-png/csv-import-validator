from __future__ import annotations

import json
import locale
import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

def _settings_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "PrivacyWindowsTools" / "language.json"
    return Path.home() / ".privacy-windows-tools" / "language.json"


def _saved_language() -> str | None:
    try:
        value = json.loads(_settings_path().read_text(encoding="utf-8")).get("language")
        return value if value in {"en", "ja"} else None
    except Exception:
        return None


_LANGUAGE = _saved_language() or ("ja" if any((x or "").lower().startswith("ja") for x in (locale.getlocale()[0], os.environ.get("LANG"))) else "en")
_CONTROLLERS = []
_PATCHED = False

TEXTS = {
    "比較を開始": ("Start comparison", "比較を開始"),
    "押すと2つのファイルを読み取り、変更点を下の一覧に表示します。元ファイルは変更しません。": ("Reads both files and shows the detected changes below. The original files are not modified.", "押すと2つのファイルを読み取り、変更点を下の一覧に表示します。元ファイルは変更しません。"),
    "Show results:": ("Show results:", "表示する結果:"),
    "重要度": ("Severity", "重要度"),
    "種類": ("Type", "種類"),
    "列": ("Column", "列"),
    "内容": ("Details", "内容"),
    "基準": ("Baseline", "基準"),
    "今回": ("Current", "今回"),
    "Data Contract Auditor": ("Data Contract Auditor", "データ契約監査"),
    "昨日と今日、旧エクスポートと新エクスポートなどを比較し、列・型・NULL率・分布・キー重複の変化を監査します。":
        ("Compare baseline and current CSV/Excel files to review column, type, NULL-rate, distribution and duplicate-key changes.",
         "昨日と今日、旧エクスポートと新エクスポートなどを比較し、列・型・NULL率・分布・キー重複の変化を監査します。"),
    "Baseline": ("Baseline", "基準ファイル"),
    "Current": ("Current", "今回ファイル"),
    "出力先": ("Output folder", "出力先"),
    "Key列": ("Key column(s)", "Key列"),
    " 例: customer_id,date": (" Example: customer_id,date", " 例: customer_id,date"),
    "Schema Drift監査を実行": ("Start comparison", "比較を開始"),
    "選択": ("Choose", "選択"),
    "重要度": ("Severity", "重要度"), "種類": ("Type", "種類"), "列": ("Column", "列"),
    "内容": ("Details", "内容"), "基準": ("Baseline", "基準"), "今回": ("Current", "今回"),
    "基準ファイルと今回ファイルを選択してください。": ("Choose the baseline and current files to begin.", "基準ファイルと今回ファイルを選択してください。"),
    "入力不足": ("Missing input", "入力不足"), "選択エラー": ("Selection error", "選択エラー"),
    "監査失敗": ("Comparison failed", "監査失敗"), "処理中": ("Working", "処理中"),
    "① 基準と今回を選択  →  ② Key列は必要な場合だけ指定  →  ③ 比較結果を確認":
        ("① Choose baseline/current  →  ② Add key columns only if needed  →  ③ Review findings",
         "① 基準と今回を選択  →  ② Key列は必要な場合だけ指定  →  ③ 比較結果を確認"),
    "元ファイルは変更しません。結果は指定した出力先へ保存します。":
        ("Original files are not modified. Results are saved to the selected output folder.",
         "元ファイルは変更しません。結果は指定した出力先へ保存します。"),
}

PHRASES = (
    ("監査完了:", "Comparison complete:"), ("保存先:", "Saved to:"),
    ("監査失敗:", "Comparison failed:"), ("BaselineとCurrentを選択してください。", "Choose both baseline and current files."),
    ("同じファイル同士の監査はできません。", "Baseline and current must be different files."),
    ("監査が完了するまではウィンドウを閉じないでください。", "Keep this window open until the comparison finishes."),
)

def get_language():
    return _LANGUAGE

def translate(text):
    if not isinstance(text, str):
        return text
    if text in TEXTS:
        en, ja = TEXTS[text]
        return ja if _LANGUAGE == "ja" else en
    if _LANGUAGE == "en":
        for ja, en in PHRASES:
            text = text.replace(ja, en)
    else:
        for ja, en in PHRASES:
            text = text.replace(en, ja)
    return text

def set_language(lang):
    global _LANGUAGE
    if lang not in {"en", "ja"}:
        raise ValueError("language must be 'en' or 'ja'")
    _LANGUAGE = lang
    try:
        path = _settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"language": lang}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    for controller in tuple(_CONTROLLERS):
        controller.refresh()

def _patch():
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True
    original_insert = tk.Listbox.insert
    tk.Listbox.insert = lambda self, index, *items: original_insert(self, index, *(translate(x) for x in items))
    for name in ("showinfo", "showwarning", "showerror", "askokcancel"):
        original = getattr(messagebox, name, None)
        if original is None:
            continue
        def make_wrapper(func):
            def wrapper(title, message, *args, **kwargs):
                return func(translate(title), translate(message), *args, **kwargs)
            return wrapper
        setattr(messagebox, name, make_wrapper(original))
    for name in ("askopenfilename", "asksaveasfilename", "askdirectory"):
        original = getattr(filedialog, name, None)
        if original is None:
            continue
        def make_dialog(func):
            def wrapper(*args, **kwargs):
                if "title" in kwargs:
                    kwargs["title"] = translate(kwargs["title"])
                return func(*args, **kwargs)
            return wrapper
        setattr(filedialog, name, make_dialog(original))

class LanguageController:
    def __init__(self, root):
        self.root = root
        self.original_title = root.title()
        existing = list(root.winfo_children())
        self._snapshot(root)
        self.frame = tk.Frame(root, padx=12, pady=5)
        if existing:
            self.frame.pack(fill="x", before=existing[0])
        else:
            self.frame.pack(fill="x")
        tk.Label(self.frame, text="Language / 言語").pack(side="right", padx=(0, 8))
        self.button = tk.Button(self.frame, width=10, command=self.toggle)
        self.button.pack(side="right")
        _CONTROLLERS.append(self)
        self.refresh()

    def _snapshot(self, widget):
        try:
            widget._i18n_original_text = widget.cget("text")
        except Exception:
            pass
        for child in widget.winfo_children():
            self._snapshot(child)

    def _refresh(self, widget):
        if widget is not self.button and hasattr(widget, "_i18n_original_text"):
            try:
                widget.configure(text=translate(widget._i18n_original_text))
            except Exception:
                pass
        for child in widget.winfo_children():
            self._refresh(child)

    def refresh(self):
        self.root.title(translate(self.original_title))
        self._refresh(self.root)
        refresh_hook = getattr(self.root, "refresh_i18n", None)
        if callable(refresh_hook):
            refresh_hook()
        status_var = getattr(self.root, "status", None)
        if status_var is not None and hasattr(status_var, "get") and hasattr(status_var, "set"):
            current = status_var.get()
            translated = translate(current)
            if translated != current:
                status_var.set(translated)
        self.button.configure(text="English" if _LANGUAGE == "ja" else "日本語")

    def toggle(self):
        set_language("en" if _LANGUAGE == "ja" else "ja")

def install_bilingual_ui(root):
    _patch()
    return LanguageController(root)
