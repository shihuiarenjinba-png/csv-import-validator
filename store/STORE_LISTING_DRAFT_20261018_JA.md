# Data Contract and Schema Drift Auditor — Microsoft Store商品ページ原稿（準備段階）

**状態：未登録/未確認の正式Identity・販売HOLD。Store未提出。**

## 商品名（候補）
Data Contract and Schema Drift Auditor

## 短い説明（原稿）
CSV・Excelの基準データと新しいデータを比較し、列・型・欠損の変化を把握

## 想定購入者
毎月の定型データを取り込む情報システム・分析担当者

## 具体的な活用例
毎週届く売上CSVの列や欠損率が先週から変わっていないか確認する。

## 主な機能（実機確認後に掲載可否を判断）
- 基準と最新ファイルの列追加・欠落を検出
- 推定データ型やNULL率の変化を一覧化
- 重複キーや分布変化の候補を表示
- 監査結果と簡易データ契約をローカル保存

## 制約・注意
型判定・分布変化は推定やしきい値に依存します。システム取込の安全性、データの正確性を保証しません。

## 未入力・確認待ち
- 正式Store Product Identity / Package Family Name：Partner Center確認後に記録
- 製品名のStore可用性・商標・カテゴリ：未確定
- 価格：未確定。Document Version Auditの既存980円下書きは変更しない。
- 配布地域と言語：所有者判断待ち
- サポートURL、プライバシーポリシーURL：製品に適合する公開ページを確認後入力
- MSIX：パッケージ候補生成/静的チェック/Store Draftアップロード未完了
- スクリーンショット・ロゴ：製品別の承認/実画面撮影待ち
- 公開認証：実機・ライセンス・品質ゲートを終えるまで行わない

## 操作順序（Partner Center）
1. Apps and gamesで既存同名商品を検索。既存枠があれば再利用し、重複作成しない。
2. 新規候補のみ、MSIX or PWA appとして名前の可用性を確認し、予約する。
3. Product identityの正式値を `store/partner_center_registration.json` へ反映（機密情報は記録しない）。
4. 画像の権利と4サイズのロゴを承認して `store/assets/` に配置。
5. Windows上で `store/build-msix.ps1` でパッケージ候補を生成し、`store/verify-upload-inputs.py --msix <実際のファイル>` を実行。
6. Product release → Start submissionで下書き開始。Packagesに指定MSIXをアップロードし、保存。
7. **Submit for certificationは押さない。** 最終実機試験と所有者承認後に判断する。

公式：https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/create-app-submission
公式：https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/upload-app-packages

> この原稿は正確性と非誇張を優先した内部ドラフトであり、実機確認前に機能全体の保証をしない。
