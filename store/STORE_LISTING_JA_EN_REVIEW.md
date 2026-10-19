# Microsoft Store掲載文｜Data Contract & Schema Drift Auditor｜レビュー準備稿
対象ブランチ: `ui/simple-schema-key-picker-20261019`
状態: **文案完成 / 公開未承認 / Store ID・価格の実入力未済**
価格の仮設定: **¥2,980（仮）**。正式価格・対応市場は権限のある販売者が承認し、Partner Centerで指定する。

## ja-JP
**製品名（候補）:** Data Contract & Schema Drift Auditor

**短い説明:**
以前と今回のCSV・Excelを比較して、列・データ型・欠損率・数値傾向・重複キーの変化を報告します。

**詳細説明（そのまま編集欄へ転記可能）:**
データ取り込み前に、基準データから列構成や値の特徴が変化していないかを確認するWindowsツールです。基準と今回のCSV・XLSXを選び、共通するKey列を一覧から指定し、保存なしで試運転した後に差分レポートを出力できます。

・基準CSV/Excelと今回CSV/Excelを比較
・共通するKey列を候補から選択
・差分・欠損・型変化・重複のレポート作成

**対応範囲と重要な注意事項:**
検出結果は統計上・構造上の要確認候補であり、業務データの正しさを証明しません。固定Contractによる自動継続監視はこの版では未完成です。

**What's new:** 初回提出時は空欄。製品更新の場合のみ新旧の違いを事実確認して記載。

## en-US
**Suggested title:** Data Contract & Schema Drift Auditor

**Short description:**
Compare baseline and current CSV/Excel data for schema, type, null-rate and duplicate-key changes.

**Full description:**
Check changes in incoming datasets before using them. Choose baseline and current CSV or XLSX files, select common key columns from a list, run a read-only preview, and save a new report describing schema and data-pattern differences.

• Compare baseline and current CSV/XLSX files
• Pick common key columns from the UI
• Review schema-drift findings before saving reports

**Important limitations:**
Findings identify potential structural or statistical changes, not proof that data is accurate or fit for business use. Automated monitoring against a persistent fixed contract is not yet complete.

**What's new:** Leave blank for the initial submission.

## Partner Center 編集チェック
- 描写の対象は各製品の現行ブランチで**実装が確認できる機能のみ**。未知の機能や完全安全保証を足さない。
- 正式名の重複確認、年齢区分質問票、価格、カテゴリ、地域、検索キーワード、機能欄は提出画面で設定する。価格は購入実績の裏付けがない仮説。
- スクリーンショットは実機撮影5枚。本文に外部URL、HTML、未確認の商標や第三者との提携表現を入れない。
- 最終チェック: ユーザー向けの日本語/英語を実画面と照合。英語UIが未合格なら対応言語を無理に追加しない。
- ソースWindows QA、MSIX、Store Identity、プライバシー・サポート情報、ライセンス承認が揃うまで掲載しない。

公式: https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/add-and-edit-store-listing-info
