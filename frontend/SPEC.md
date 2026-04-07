# 旅費自動仕訳 フロントエンド仕様書

## 概要
月次の旅費交通費を集計・仕訳生成・ROI分析するWebアプリ。

## 技術スタック
- Next.js 16 + React 19 + TypeScript
- Tailwind CSS 4
- Recharts（チャート）
- バックエンド: FastAPI（`http://localhost:8000`）

## 画面構成（4タブ）

### 1. 旅費集計（AggregateTab）
月次の旅費交通費を各ソースから集計し、個人別に表示。

**入力**:
- 年/月
- ソース選択（MF経費 / EXカード / Racco / じゃらん / タイムズカー）
- dry-runチェック

**出力**:
- スコープ切替（全体 / スタメン単体 / スタジアム単体）
- サマリー指標（合計 / 新幹線 / 宿泊 / 在来線 / その他 / 人数）
- 個人別テーブル（社員番号・名前・部署・新幹線・宿泊・在来線・その他・合計）
- 未マッチレコード警告
- 実行ログ

**API**: `POST /api/aggregate`

### 2. 仕訳生成（JournalTab）
MF会計Plusインポート用の仕訳CSVを生成・ダウンロード。

**入力**: 年/月
**出力**: CSV生成 → ブラウザダウンロード（`journal_YYYY_MM.csv`）

**API**: `POST /api/journal-csv`

### 3. ROI分析（ROITab）
セグメント別の旅費ROIを分析。

**入力**: 年/月、デモデータ切替
**出力**:
- 指標カード（旅費合計 / 売上合計 / 全体ROI）
- セグメント別テーブル（セグメント・旅費・売上・ROI）
- 棒グラフ（旅費 vs 売上）
- スプレッドシート書き出しボタン

**API**: `POST /api/roi`, `POST /api/roi/write`

### 4. 部門別ROI（DeptROITab）
法人セグメントごとの旅費ROIを詳細分析。

**入力**: 年/月
**出力**:
- 指標カード（旅費合計 / 売上合計 / 全体ROI）
- 詳細テーブル（セグメント・人数・新幹線・在来線・車・飛行機・宿泊・旅費合計・売上・ROI）
- 棒グラフ
- スプレッドシート書き出しボタン

**API**: `POST /api/dept-roi`, `POST /api/dept-roi/write`

## API型定義

```typescript
// 集計結果
interface SummaryRow {
  emp_no: string; name: string; department: string;
  shinkansen: number; hotel: number; train: number; other: number; total: number;
  shinkansen_ad: number; shinkansen_welfare: number; shinkansen_recruit: number; shinkansen_subsidiary: number;
  hotel_ad: number; hotel_recruit: number;
  train_ad: number; train_recruit: number;
  other_ad: number; other_recruit: number;
}

// ROI
interface ROIRow { セグメント: string; 旅費交通費: number; 売上: number; ROI: number; }

// 部門別ROI
interface DeptROIRow {
  department: string; headcount: number;
  shinkansen: number; train: number; car: number; airplane: number; hotel: number;
  total: number; sales: number; roi: number;
}
```

## デザインシステム
| トークン | 値 | 用途 |
|---|---|---|
| --primary | #2563eb | ボタン・アクティブタブ |
| --success | #10b981 | ROI高評価（50x以上） |
| --warning | #f59e0b | チャート旅費バー・警告 |
| --danger | #ef4444 | エラー |
| --background | #f5f7fa | ページ背景 |
| --card | #ffffff | カード背景 |

## デプロイ
- 現状: localhost:3003（開発サーバー）
- 予定: Vercel
