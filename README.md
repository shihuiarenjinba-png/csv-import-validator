# CSV Import Validator

CSVを業務システムへアップロードする前に、文字コード・列構造・空欄・重複・危険な先頭文字などをローカルで検査するMVPです。

## できること

- UTF-8 / UTF-8 BOM / CP932 / UTF-16 の読込判定
- カンマ / タブ / セミコロンの区切り判定
- 空・重複ヘッダー検出
- 行ごとの列数ズレ検出
- 必須列 / 期待列 / 余分な列の検査
- キー列の空欄・重複検出
- Excel等で数式として解釈され得る `= + - @` 始まりのセルを候補警告
- 制御文字候補の検出
- JSONレポートとissues CSVを出力
- 元CSVは変更しない

## セットアップ

Python標準ライブラリのみで動作します。

```bash
python app.py
```

CLI:

```bash
python validator.py input.csv --schema schema.example.json --output reports
```

## スキーマ例

```json
{
  "expected_columns": ["customer_id", "name", "amount"],
  "required_columns": ["customer_id", "name"],
  "key_columns": ["customer_id"],
  "allow_extra_columns": false
}
```

## 注意

本ツールはアップロード成功やセキュリティを保証するものではありません。対象システム固有の仕様は、スキーマ設定として明示してください。

## テスト

```bash
python -m unittest discover -s tests -v
```

> 現在はMVP開発版です。販売用リリースではありません。
