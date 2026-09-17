# Release Gate — Data Contract & Schema Drift Auditor

## Code / Safety — repositoryで完了可能

- [x] 従来CSV構造検査を残す
- [x] Baseline / Currentのプロファイル比較を行う
- [x] Contract違反と統計Driftを別カテゴリとして出力する
- [x] 必須列欠落 / 型 / NULL上限 / unexpected columnをContract errorとして扱う
- [x] 数値平均シフト / 新カテゴリ / 重複率増加をDrift候補として扱う
- [x] BaselineからContract雛形を生成する
- [x] 元ファイルを変更しない
- [x] 絶対パスを監査レポートへ残さない
- [x] SHA256を記録する
- [x] Contract violations / Drift findingsを別CSVへ出力する
- [x] 回帰テストを配置する
- [x] Windows CI / PyInstaller build定義を配置する

## Desktop-only validation

- [ ] Windows 10/11でEXE起動・GUI一巡
- [ ] UTF-8 BOM / CP932 / Shift-JISの業務CSVを確認
- [ ] 大容量CSV / XLSXのメモリ・速度確認
- [ ] 日付・ID・ゼロ埋めコード等の型推定誤判定を代表データで確認
- [ ] SmartScreen / Defender / AV確認
- [ ] 配布ZIP SHA256確認

## Release rule

自動生成Contractはそのまま本番強制に使う前提にしない。利用者がレビューできる雛形として提供し、Driftは異常断定ではなくレビュー信号として表示する。
