# PRD: travel-expense-auto（出張旅費ROI可視化）
> 規模: M ／ 最終更新: 2026-02-27 ／ ステータス: In Progress（Phase 0 完了）

## 1. 課題定義（Problem Statement）
- 部署ごとに出張が増加しているが、その出張費が受注増に繋がっているかを月次で判定できていない
- 旅費データが複数ソース（EXカード・MF経費・Racco）に散在し、手作業での集計が必要
- 旅費と受注実績を突き合わせるROI分析の仕組みがない

## 2. ソリューション概要（Solution Overview）
各ソースから旅費データを自動取得し、部署マスタと紐付けて個人・部署別に集計。
受注データと突き合わせて部署別の出張ROI（受注額 / 旅費）を月次で可視化する。

- **スコープ内**: 旅費自動取得、部署別集計、受注データ連携、ROI算出、スプレッドシート出力
- **スコープ外**: 旅費の承認ワークフロー、経費精算、予算管理

## 3. ユーザーストーリー（User Stories）
- US-1: 経理担当者として、月初に前月の部署別旅費を自動集計したい。手作業を減らすため。
  - 受け入れ基準: 全3ソース（EXカード・MF経費・Racco）のデータが自動取得・集計される
- US-2: 部署マネージャーとして、自部署の出張ROI（旅費 vs 受注額）を月次で確認したい。出張投資の判断材料にするため。
  - 受け入れ基準: スプレッドシート上で部署別ROIが閲覧できる
- US-3: 経理担当者として、個人別の旅費内訳も確認したい。異常値の検出のため。
  - 受け入れ基準: 個人別の旅費一覧が部署でグルーピングされて表示される

## 4. 機能要件（Functional Requirements）
| ID | 機能 | 優先度 | 説明 |
|----|------|--------|------|
| F-1 | EXカードデータ取得 | Must | Playwrightで法人管理画面からCSV自動DL（公開APIなし） |
| F-2 | MF経費データ取得 | Must | 公式REST API（OAuth 2.0）で経費明細を自動取得 |
| F-3 | Raccoデータ取得 | Must | Playwrightで管理画面からCSV自動DL（公開APIなし） |
| F-4 | 部署マスタ連携 | Must | スプレッドシートの部署マスタから個人→部署マッピング |
| F-5 | 受注データ連携 | Must | スプレッドシートの受注実績を部署別に取得 |
| F-6 | 個人別・部署別集計 | Must | 旅費を個人別→部署別に集計 |
| F-7 | ROI算出 | Must | 部署別ROI = 受注額 / 旅費 を月次で算出 |
| F-8 | スプレッドシート出力 | Must | 集計結果を指定スプレッドシートに書き込み |

## 5. 非機能要件（Non-Functional Requirements）
- **更新頻度**: 月次（月初に前月分を処理）
- **セキュリティ**: 経費・受注データは社内限定、認証情報は.envで管理
- **運用**: エラー時に担当者へ通知（方法は未定）

## 6. 技術仕様（Technical Specification）
- **実行形態**: CLI（Python スクリプト、月次バッチ実行）
- **技術スタック**: Python（requests / Playwright / gspread）
- **データソース**:
  | ソース | 取得方法 | 技術 | 備考 |
  |--------|---------|------|------|
  | EXカード | Playwrightスクレイピング | 法人管理画面→CSV自動DL | 公開APIなし。規約注意、月1回最小限 |
  | MF経費 | 公式REST API | OAuth 2.0 + requests | エンドポイント: `expense.moneyforward.com/api/external/v1/` |
  | Racco | Playwrightスクレイピング | 管理画面→CSV自動DL | 公開APIなし。規約注意、月1回最小限 |
  | Google Sheets（部署マスタ） | gspread | ID: `1gL6ShZUta6vM_TOcx0VB10_sjb_lZ7ZX6o9V-5LL3yc` | 要閲覧権限申請 |
  | Google Sheets（受注実績） | gspread | ソース未確認 | |
  | Google Sheets（出力先） | gspread | 参考: `1YWyDrpyHPq2MHoHeBHwQ2W-ouDg8Kqn7aW5vPLyMfzQ` | |
- **認証情報管理**: `.env`ファイル（MF経費のOAuth、EXカード・Raccoのログイン情報、GCPサービスアカウント）

## 7. 制約事項（Constraints）
- 部署マスタのスプレッドシートは閲覧権限がまだない（要申請）
- EXカード・Raccoはスクレイピングのため、画面変更で壊れるリスクあり
- EXカード・Raccoのスクレイピングは利用規約上グレー（月1回・最小限のアクセスに留める）
- 締切: 2026年3月末

## 8. マイルストーン（Milestones）
- [x] Phase 0: API調査（EXカード・MF経費・Raccoの取得方法確定）
- [ ] Phase 1a: MF経費API接続（OAuth 2.0認証 + 経費明細取得）
- [ ] Phase 1b: EXカード Playwrightスクレイパー
- [ ] Phase 1c: Racco Playwrightスクレイパー
- [ ] Phase 2: 部署マスタ連携 + 個人別・部署別集計 + ROI算出
- [ ] Phase 3: スプレッドシート出力 + 月次自動実行

## 9. 未決事項（Open Questions）
- [x] Q1: EXカード → 公開APIなし。法人管理画面からCSV DL可能。Playwrightで自動化
- [x] Q2: MF経費 → 公式REST API あり（OAuth 2.0）。経費明細・従業員・部門取得可能
- [x] Q3: Racco → 公開APIなし。管理画面からCSV DL可能。Playwrightで自動化
- [ ] Q4: 部署マスタの閲覧権限はいつ取得できるか？
- [ ] Q5: 受注データのソース・フォーマットの詳細は？
- [x] Q6: 実行形態 → CLI（Pythonスクリプト、月次バッチ）
- [ ] Q7: MF経費のAPI連携設定画面にアクセスできるか？（Client ID/Secret取得のため）
- [ ] Q8: EXカード法人管理画面のURL・ログイン情報は？
- [ ] Q9: Racco管理画面のURL・ログイン情報は？

## Changelog
- **2026-02-27 v0.2（Phase 0 完了）**
  - API調査完了。結果:
    - MF経費: 公式REST API あり（OAuth 2.0）→ Python API直叩き
    - EXカード: 公開APIなし、管理画面CSVのみ → Playwright自動DL
    - Racco: 公開APIなし、管理画面CSVのみ → Playwright自動DL
  - 技術スタック確定: Python（requests / Playwright / gspread）
  - Yoom（導入済みiPaaS）も検討したが、EXカード・Racco非対応のため不採用
  - Yoom vs Playwright vs API直叩きの3方式を比較し、ハイブリッド（API + Playwright）に決定
  - 実行形態: CLI（月次バッチ）に決定
- **2026-02-27 v0.1（初版）**
  - 当初の課題: 旅費交通費（EXカード・MF経費・Racco）の手動集計を自動化したい
  - ヒアリング中に目的が拡張: 単なる集計ではなく **出張旅費のROI判定** が本質と判明
  - Return = 部署ごとの受注実績（スプレッドシート管理）
  - Cost = 部署ごとの出張旅費（3ソース統合）
  - 月初に前月の部署別ROIを確認する運用を想定
  - 規模判定: M（外部連携4-5、画面数未定）
  - 最大リスク: 各データソース（EXカード・MF経費・Racco）のAPI存在が未確認
