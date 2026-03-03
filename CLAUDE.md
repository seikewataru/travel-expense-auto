# travel-expense-auto プロジェクトルール

## 概要
出張旅費のROI（受注額 / 旅費）を部署別に月次で可視化するツール。

## 要件定義
詳細は [PRD.md](./PRD.md) を参照。

## 技術スタック
- **言語**: Python 3.11+
- **MF経費**: requests（公式REST API、OAuth 2.0）
- **EXカード・Racco**: Playwright（管理画面スクレイピング→CSV自動DL）
- **Google Sheets**: gspread（部署マスタ・受注実績・出力先）
- **認証情報**: `.env`ファイル（dotenv）
- **GCP認証**: サービスアカウント `~/.config/gcp/service-account.json`（ir-db-automationと共有）

## ファイル構成
```
travel-expense-auto/
├── CLAUDE.md           # このファイル
├── PRD.md              # 要件定義書
├── .env                # 認証情報（git管理外）
├── .gitignore
├── requirements.txt
├── src/
│   ├── mf_expense.py   # MF経費API取得
│   ├── ex_card.py      # EXカード Playwrightスクレイパー
│   ├── racco.py        # Racco Playwrightスクレイパー
│   ├── sheets_client.py # Google Sheets読み書き
│   ├── aggregator.py   # 集計・ROI算出
│   └── main.py         # メインスクリプト
└── data/               # DL済みCSV一時保存（git管理外）
```

## データソース
| ソース | 種別 | 取得方法 | 状況 |
|--------|------|---------|------|
| MF経費 | 在来線・新幹線 | 公式REST API（OAuth 2.0） | Phase 1a で実装 |
| EXカード | 新幹線代 | Playwright（管理画面CSV DL） | Phase 1b で実装 |
| Racco | 宿泊費 | Playwright（管理画面CSV DL） | Phase 1c で実装 |
| Google Sheets | 部署マスタ | gspread | 要権限申請 |
| Google Sheets | 受注実績 | gspread | ソース未確認 |
| Google Sheets | 出力先 | gspread | 確認済 |

## スクレイピングルール（EXカード・Racco共通）
- アクセス頻度は月1回・最小限に留める
- エラー検知とアラート（画面変更時の通知）を必ず入れる
- ログイン情報は `.env` で管理、ハードコード禁止

## 運用
- 更新頻度: 月次（月初に前月分を処理）
- 利用者: 経理担当 + 部署マネージャー
- 実行形態: CLIスクリプト（将来的にlaunchd等で自動実行検討）

## ペンディング事項（未解決・次回セッションで必ず確認）

### ~~EXカード「スタジアム」部門貸出用3枚~~ → 解決済み
- `4859841980`（百五十部）→ 森川 智仁（COO）に加算
- `6859069977`（営業一部）, `9731504005`（営業二部）→ 「株式会社スタジアム」部門として集計
- EX_CARD_OVERRIDES で実装済み

### じゃらん未登録者2名
- 立川 拓真（5件）、高草木 りさ（2件）: 部署マスタに未登録。スタジアム社員？
- 現状: unmatchログに出るだけで集計に含まれない

### MF経費「承認用」アカウント
- stamen事業者で「承認用」名義の経費申請: ¥210（在来線）1件
- 不正利用の可能性あり → ユーザーが確認中
- 現状: unmatchログに出るだけで集計に含まれない

### 半期総会（全社集合）の旅費除外ルール
- 半年に1回、本社に集まる機会があり、その際の旅費は集計から除外したい
- 除外方法（移動日起点で除外するルール等）は正式ルール未定
- 実装タイミング: 別途検討

### 株式会社スタジアム（子会社）の除外オプション
- EXカード `6859069977`（営業一部）, `9731504005`（営業二部）は子会社利用
- 現状: 部門「株式会社スタジアム」として集計に含まれている
- 要件: スタメン単体の集計時は除外したい（`--exclude-stadium`等のフラグ）
- 実装タイミング: 別途検討
