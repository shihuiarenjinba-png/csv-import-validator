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

既定では、現在の作業ディレクトリではなくユーザーのローカルアプリデータ配下に保存します。画面で出力先を指定した場合はその指定先を使用します。MSIXのインストール場所やWindowsAppsへの書き込みを前提にしません。

```text
%LOCALAPPDATA%/OkinawaDesktopTools/DataContractAuditor/data_contract_audit/
  data_drift_audit.json
  data_drift_findings.csv
  generated_contract.json
```

## Store候補と実行QAの状態

- 現在の承認済み製品バージョンは `1.0.0.0` のままです。
- 手動workflow dispatchで作成する `1.0.1.0` は暫定・未承認の候補です。製品登録情報のバージョンやSHAは変更しません。
- `QA_UNSIGNED` はテスト署名・実行QA用で、正式提出パッケージではありません。
- MSIXの実行試験は元のMSIXを変更せず、別コピーに短期テスト証明書で署名します。署名由来の差分を除く内容一致を確認し、元パッケージのSHAは維持します。
- GitHub Windows runnerでのインストール/AUMID起動は、Windows 10/11のユーザー環境における画面表示・DPI確認の代替ではありません。ローカルGUI QAとは別の証跡として記録します。
- Partner Center upload、Packages Save、Certification、Publishはこの候補ビルドworkflowから実行しません。

## 次の強化

- Contractファイルを固定して継続監視
- 列順ルール
- 正規表現 / min-max / enum / unique制約
- PSI / KSなど分布変化指標の追加
- Excel複数Sheet比較
- 監査履歴の時系列表示
- Windows 10/11実機テスト、portable EXE、署名
