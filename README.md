# Data Contract & Schema Drift Auditor

**定型CSV / Excelの「仕様が壊れた」と「データの傾向が変わった」を分けて監査するローカルツール**です。

単なるCSV Validatorではなく、**Data Contract違反**と**Statistical Drift**を別カテゴリとして出力し、業務を止めるべき問題とレビュー候補を混同しないことを専門機能にしています。

> Release Candidate。自動生成Contractは本番強制ルールではなく、レビュー用の雛形です。販売開始前に `RELEASE_CHECKLIST.md` のDesktop-only項目を実機確認してください。

## 1. Contract Violations
明示ContractまたはBaselineから生成したContractに対し、Currentデータを検査します。

- required column missing
- kind violation
- NULL率上限超過
- unexpected column（Contractで禁止した場合）

Contract errorがある場合は `release_gate = fail` として出します。

## 2. Schema / Data Drift
過去BaselineとCurrentを比較し、レビュー候補を出します。

- 列追加 / 削除
- 推定型変化
- NULL率増加
- Numeric平均の大幅なシフト
- 新しい最小 / 最大値
- 新しいカテゴリ値候補
- Key重複率の増加
- 行数 / 列数の変化

Driftは異常断定ではありません。Contract違反とは分離し `review signal` として扱います。

## 3. Generated Data Contract
Baselineから以下を含む雛形を作成します。

- required
- inferred kind
- max_null_rate
- allow_extra_columns

生成後に人がレビューして固定Contractとして使うことを想定しています。

## 4. CSV Import Preflight
従来の単体CSV検査も残しています。

- 文字コード / delimiter
- 列数不一致
- 空 / 重複ヘッダー
- 必須列
- Key空欄 / 重複
- 制御文字候補
- Excel Formula Injection候補

## 出力

```text
data_contract_audit_YYYYMMDD_HHMMSS/
  data_contract_audit.json
  generated_contract.json
  contract_violations.csv
  drift_findings.csv
```

Baseline / Currentはファイル名とSHA256で識別し、共有レポートにローカル絶対パスを残しません。

## 想定用途

- SaaS / EC / 会計システムの定期CSV
- 取引先から届く定型ファイル
- ETL / BI投入前の品質ゲート
- API export仕様変更の早期検知
- 月次データ品質の監査

## Privacy / Safety

- ローカル処理
- 元ファイル非変更
- 外部送信なし
- Driftを自動エラー断定しない
- ContractとDriftを分離して出力

## 起動

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## Test / Build

```powershell
python -m unittest discover -s tests -v
```

Windows CI / PyInstaller定義は `.github/workflows/windows-ci.yml` にあります。

## 重要な制約

- 型推定はheuristicです。ゼロ埋めIDやコード列等は固定Contractで明示する方が安全です。
- Numeric driftは意味的重要性を判定しません。
- Categorical profileは代表値ベースのレビュー信号です。
- 大容量データの販売前性能確認は実機で必要です。

販売判定は [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) を基準にしてください。
