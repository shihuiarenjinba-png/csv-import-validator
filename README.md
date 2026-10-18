# Data Contract & Schema Drift Auditor

CSV / Excel の「今回ファイル」を単独検査するだけでなく、**基準ファイルと比較してデータ構造や品質の変化を検出する**ローカル監査ツールです。

旧 `CSV Import Validator` の単体チェック機能は `validator.py` に残し、新たに `contract_auditor.py` で時系列のSchema Drift監査を追加しました。

> 現在はMVP開発版です。検出結果は要確認候補であり、業務システムへの投入可否を保証するものではありません。

## 使う場面

- SaaS / EC / 会計システムから毎日・毎月出すCSVの仕様が変わっていないか
- 取引先から届く定型ファイルの列や型が変わっていないか
- ETL前にNULL率や重複率の急増を検知したい
- APIやCSVエクスポートのバージョン変更を早く見つけたい

## Schema Drift監査

Baseline と Current を選ぶと、以下を比較します。

- 列の追加 / 削除
- 推定データ型の変化
- NULL率の増加
- Numeric列の平均値の大きなシフト
- Baseline範囲を超える新しい最小 / 最大値
- Categorical列の新しい値候補
- 指定Key列の重複率増加
- 行数 / 列数の変化

Baselineから `generated_contract.json` も作成します。現在はRequired列、推定型、許容NULL率を記録する簡易Data Contractです。

## 既存の単体Importチェック

`validator.py` には従来のCSV事前検査を残しています。

- 文字コード / 区切り
- 列数ずれ
- 重複ヘッダー
- 必須列
- キー空欄 / 重複
- 制御文字候補
- Excel数式として解釈され得る値の候補

## 実行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## 出力

```text
data_contract_audit/
  data_drift_audit.json
  data_drift_findings.csv
  generated_contract.json
```

## 次の強化

- Contractファイルを固定して継続監視
- 列順ルール
- 正規表現 / min-max / enum / unique制約
- PSI / KSなど分布変化指標の追加
- Excel複数Sheet比較
- 監査履歴の時系列表示
- Windows 10/11実機テスト、portable EXE、署名

## 2026-10-19 有料商品としての品質強化（開発中・HOLD）

`audit/paid-product-hardening-20261019` は、既存の商用準備ブランチとは別の監査ブランチです。
- 対象製品: **Data Contract & Schema Drift Auditor**
- 今回の強化: 試運転→確認→保存・SHA-256承認・CSV/XLSX重複ヘッダー拒否。これらに対応する異常系テストを追加しました。
- 価格の仮説: **¥2,980（買い切り・国内税込、未承認）**。成熟した他社製品の公式掲載価格との比較に基づく**テスト候補値**であり、自社商品の購入実績に裏付けられた価格ではありません。
- Store最終商品: **MSIXのみ**。検証用EXEは内部QA・パッケージ組立工程に限定し、Portable EXE/NSISを最終販売形式として採用しません。
- **未完了のブロッカー**: 監査ブランチのWindows実機テスト、GUI/日英/表示倍率/破損データ・容量不足試験、正規Identity MSIX実物、WACK PASS、商用LICENSE/NOTICE/素材権利の承認、Store認定。
- GitHub Actionsが0ステップで終了する場合はテスト**未実行**として記録し、ソース不合格や品質合格と扱わないでください。
- 全19商品の価格根拠と合格ゲート: [GitHub品質計画](https://github.com/shihuiarenjinba-png/document-site/blob/audit/store-19-product-readiness-20261019/quality/PAID_19_PRODUCT_QUALITY_AND_PRICING_20261019.md)

既存`main`とReleaseの変更・統合・販売公開は、独立QAを終えるまで行わないでください。
