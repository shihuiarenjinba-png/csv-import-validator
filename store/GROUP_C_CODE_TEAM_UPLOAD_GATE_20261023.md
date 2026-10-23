# Group C / プライバシー・データ保護7製品 — コード担当へのMSIXビルド・Store下書きアップロード引き継ぎ

**記録日:** 2026-10-23　**現在の判断:** 全7製品「アップロード開始HOLD」。これは実機不合格判定ではなく、必要な実行証拠・公式Identity・MSIX実物の未確認を意味する。

## オーナーの方針 / 権限範囲

- 配布チャネルは **Microsoft Store用MSIX** のみ。署名サービス・証明書の購入、PFX生成、SignTool、独自コード署名、サイドロード販売は**不要／実施しない**。Storeが公開時にMSIXに署名する。
- まず製品ごとにビルド・検証証拠を揃える。**合格した製品についてのみ**コード担当にPartner Centerの該当既存製品のPackagesページへ**下書きアップロードと保存**を任せる。
- ただし、アップロード許可を出す時点で、オーナーの当該製品についての「アップロードに進む」判断とコード担当の権限を確認すること。**申請提出 (Submit for certification)、公開、価格・地域・年齢区分変更、新商品枠の作成は未承認**。勝手に操作しない。
- 現在これらの製品用に生成・SHA検証されたMSIX実物は**0件**。GitHub Actionsは7製品ともジョブのrunner未割当・steps=0で停止した記録がある。実行成功を意味しない。費用を伴うActions課金設定を無断変更しない。
- 他グループ、特にSTRATEGY MARKET US/JPのIdentity、Publisher、Store ID、Store version、MSIX SHAを**決して流用しない**。

## 対象リポジトリと作業優先順位

| 優先 | 製品 | GitHub repository | 専用作業branch | Store ID候補 |
| --- | --- | --- | --- | --- |
| P0 | Data Contract Auditor | `csv-import-validator` | `codex/store-p0-data-contract-20261023` | `9PDL4ZWSB45P` |
| P0 | Web Evidence Archiver | `web-evidence-archiver` | `codex/store-p0-web-evidence-20261023` | `9NNT1B142ZWV` |
| P1 | Folder Privacy Auditor | `-Folder-Privacy-Auditor` | `codex/store-p1-folder-privacy-20261023` | `9PKMCT98XQF5` |
| P1 | Excel / CSV Privacy Cleaner | `-Excel-CSV-Privacy-Cleaner` | `codex/store-p1-excel-csv-privacy-20261023` | `9P3Z36J7PSFC` |
| P1 | Image Privacy Cleaner | `-Screenshot-Image-Privacy-Cleaner` | `codex/store-p1-image-privacy-20261023` | `9PNSPFBKBBTQ` |
| P1 | AI Upload Guard | `-AI-Upload-Guard-AI-` | `codex/store-p1-ai-upload-guard-20261023` | `9PDJ1T5BQ4P1` |
| P1 | PDF Privacy Toolkit | `-PDF-Privacy-Toolkit` | `codex/store-p1-pdf-privacy-20261023` | `9PD1RXLFWPBC` |

**Store IDはユーザーによる数字の概ねの確認があっても、各Partner Centerのライブ照合が済んだとみなしてはならない。** 予約済み表示名とソース表示名が同じ保証もない。

## 製品ごとに必須の順番（混在・一括アップロード禁止）

1. **開始ゲート:** 対象repo、指定source branch、作業branch、remote HEAD、local HEAD、`git status --porcelain` を記録。dirtyならファイル変更・ビルドなしで停止。既存の変更を消さない。専用branch以外に書かない。
2. **Identityゲート:** 既存Partner Center製品の **Store ID → Package Identity Name → Publisher → PublisherDisplayName → reserved Store DisplayName → PFN → Package version** を同一製品枠に対して照合。各フィールドを根拠URL/画像、検証時刻、担当者と結び、未確認はnull/UNKNOWN/HOLDのまま。MSIX 4部バージョン末尾は`.0`。既定`1.0.0.0`は承認ではない。
3. **実行環境ゲート:** GitHub Actionsの実runner名・job ID・steps・終了コード・ログ・artifactを実際に確認。現時点のsteps=0は未実施。利用制限/支払い状態/runner availabilityは所有者が確認し、無断の有料切替は行わない。復旧までCI PASSを主張しない。
4. **アプリゲート:** Windows x64で既存の依存関係ビルドと回帰を実施。EXEのSHA-256、GUI起動と主機能、匿名の実データによる入力/出力、エラー動作、原本の非上書き、不要な情報送信がないかを記録。既存`build-windows-portable.ps1`等を壊さない。Web EvidenceではPlaywright/Chromium同梱・オフライン起動・許可ホスト外への通信遮断・権利表示を追加確認。
5. **MSIX候補ゲート:** 製品固有の正式Identity・承認ロゴ・承認されたバージョン/言語を用いて**未署名**MSIXを作成。生成成功、unpack、`AppxManifest.xml`のName/Publisher/PublisherDisplayName/2箇所のDisplayName/Version/x64/Resources/EXEパス、実ファイル・必要ランタイム・ライセンス、`SOURCE_GIT_COMMIT.txt`、MSIX/EXE SHA-256を比較。実在しない成果物には値を付けない。署名済みと偽らない。
6. **掲載ゲート:** 既存製品の表示名に一致する説明、実画面スクリーンショット、ロゴ、サポート連絡先、プライバシーポリシー、カテゴリ、年齢区分、提供市場、価格、第三者ライセンスを確認。存在しない機能や認証、完全プライバシー保証は広告しない。
7. **アップロード許可判断:** 項目1–6が揃った当該1製品についてのみ、`UPLOAD_DRAFT_ALLOWED`の承認を得たコード担当がPartner Centerの既存製品枠で該当Store IDを再確認し、Packagesへ一致する最新のMSIXをアップロード、検証完了まで確認。赤いハードエラーを解消した場合に限り**下書きを保存**。保存成功を実画面で確認し、記録する。**Submit for certification / 公開は行わない**。
8. **結果記録:** 出力を消さず、run/job ID・runner・steps・テスト数・MSIXパス/サイズ/SHA-256・Manifest値・Partner Centerメッセージ原文・Package draft save確認・未解決のrunFullTrust警告を製品別ログに残す。

## 現時点の製品別留意点

- **Data Contract**: `store/validate_store_config.py`, `store/build-msix.ps1 -PreflightOnly`, `store/verify_msix_candidate.py`。source名と予約名の相違は実際のPartner Center証拠で解決。Identity/version/ロゴはまだHOLD。今回追加したビルダーはWindows実行未確認。
- **Web Evidence**: `store/msix_preflight.py --strict`, `store/build-msix.ps1 -PreflightOnly`。Chromiumの配布と`store/browser_bundle_approval.json`が別ゲート。ブラウザー同梱MSIXビルダーはWindows実行未確認。
- **Folder Privacy**: 正本 `store/partner-center-identity.json` schema v2、`store/identity_manifest.py`、既存 `store/build-msix.ps1`。スクリーンショット由来のPublisher/PFN/SIDをライブ検証済みと扱わず、nullのIdentity Name/Package versionを勝手に埋めない。
- **Excel/CSV、Image、AI Upload Guard、PDF**: 既存のMSIXビルダーは外部Identity引数方式。新しい`store/unsigned_msix_submission_inputs.json`はHOLD/不明点の記録であり、ビルダーへ自動で承認値を供給する仕組みではない。独立した公式証拠が得られるまで引数を推測しない。
- **PDF Privacy**: 「PDF Privacy」という商品枠の名称と`PDF Privacy Toolkit`というrepo/製品表示名は一致するとは限らないため、厳密に同一製品を確認。
- **既存Python/PowerShellビルドスクリプト**を編集する前に担当範囲と既存の検証ルートを確かめ、今回作った補助コードだけに修正を閉じる。

## コード担当への実行プロンプト

> あなたはグループCのコード担当です。上記7製品を**P0から1製品ずつ**、指定repo/作業branchに限定して扱ってください。まずorigin/branchとHEAD/dirtyを確認し、各製品でMicrosoft Storeの正しい予約済み商品枠・Store ID・Package Identity Name/Publisher/PublisherDisplayName/予約名/Versionを独立に照合してください。署名/PFX購入/SignToolは不要で、Windows x64のEXE検証と未署名MSIX生成、pack-unpack/Manifest/SHA256/Store用ロゴ/実画面/プライバシー説明の検証まで行います。GitHub Actionsがrunnerなし・steps=0ならPASSにしないでください。各製品のログ・テスト結果・MSIX SHA256を提出し、**アップロード開始承認を得た製品だけ**Partner CenterのPackages下書きにアップロードして、エラー解消と下書き保存成功を確認してください。提出/公開/価格変更は行わず、実際の結果と未解決事項を正確に引き継いでください。

## 受領報告テンプレート（製品ごとに1レコード）

```text
Product / Repo / Store ID / branch:
Remote SHA / Local SHA / dirty:
Identity Source / verified field status / reserved DisplayName:
Store version A.B.C.0 / approval:
Windows runner / Actions run ID / job ID / executed steps:
Unit tests executed / pass / fail; GUI smoke evidence:
EXE path / SHA256:
MSIX path / size / SHA256:
Unpacked manifest Name/Publisher/PublisherDisplayName/VisualElements DisplayName/Version/x64:
Browser runtime/license approval (Web Evidence only):
Windows QA / limitation:
Partner Center Packages upload / hard errors / warnings / draft Save result:
Signature: UNSIGNED (Store submission only)
Submit for certification: NOT AUTHORIZED
Publish: NOT AUTHORIZED
Decision: HOLD or UPLOAD_DRAFT_ALLOWED (requires named approval)
Remaining blockers:
```

## 別グループのStoreアップロード経験から転用できる一般的な教訓

STRATEGY MARKETの受領ログで問題になったのはVersionの4番目が0でないこと、予約済みDisplayNameの不一致、`runFullTrust`警告と致命的エラーの混同、アップロード後のSave結果未確認である。**教訓だけ転用し、あちらの具体的なID/Name/Package SHA/Versionは転用しない。**

Microsoft MSIX Store署名説明: https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/package-version-numbering
