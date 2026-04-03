"""FastAPI バックエンド — 既存Pythonロジックのラッパー"""

from __future__ import annotations

import sys
from pathlib import Path

# プロジェクトルートをパスに追加（src モジュール読み込み用）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="旅費自動仕訳・ROI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3003"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── リクエスト / レスポンス ──


class AggregateRequest(BaseModel):
    year: int
    month: int
    use_mf: bool = True
    use_ex: bool = True
    use_racco: bool = True
    use_jalan: bool = True
    use_times: bool = True
    dry_run: bool = True


class ROIRequest(BaseModel):
    year: int
    month: int
    demo: bool = False


class ROIWriteRequest(BaseModel):
    year: int
    month: int


class DeptROIRequest(BaseModel):
    year: int
    month: int
    write_sheet: bool = False


class FetchCSVRequest(BaseModel):
    source: str  # "ex" | "racco" | "jalan" | "times"
    year: int
    month: int


# ── エンドポイント ──


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/aggregate")
def aggregate(req: AggregateRequest):
    """旅費集計を実行"""
    from src.config import EX_DATA_DIR, MF_OFFICE_IDS
    from src.sheets_client import SheetsClient
    from src.aggregator import ExpenseAggregator

    log = []

    sheets = SheetsClient()
    dept_master = sheets.read_department_master(req.year, req.month)
    log.append(f"部署マスタ: {len(dept_master)}名")

    ex_card_master, ex_card_exclude_ids, ex_card_category_map = sheets.read_ex_card_master()
    log.append(f"EXカードマスタ: {len(ex_card_master)}件（除外: {len(ex_card_exclude_ids)}件）")

    ringi_lookup = sheets.read_ringi_lookup()
    log.append(f"稟議ルックアップ: {len(ringi_lookup)}件（広告費/採用費）")

    agg = ExpenseAggregator(
        dept_master,
        ex_card_master=ex_card_master,
        ex_card_exclude_ids=ex_card_exclude_ids,
        ex_card_category_map=ex_card_category_map,
        ringi_lookup=ringi_lookup,
    )

    data_dir = EX_DATA_DIR

    if req.use_ex:
        ex_csv = data_dir / f"ex_{req.year}_{req.month:02d}.csv"
        if ex_csv.exists():
            from src.ex_card import EXCardClient
            ex_records = EXCardClient.parse_csv(ex_csv)
            agg.add_ex_card(ex_records)
            log.append(f"EXカード: {len(ex_records)}件")
        else:
            log.append(f"EXカード: CSVなし ({ex_csv.name})")

    if req.use_times:
        times_csv = data_dir / f"times_{req.year}_{req.month:02d}.csv"
        if times_csv.exists():
            from src.times_car import TimesCarClient
            times_records = TimesCarClient.parse_csv(times_csv)
            agg.add_times_car(times_records)
            log.append(f"タイムズカー: {len(times_records)}件")
        else:
            log.append(f"タイムズカー: CSVなし ({times_csv.name})")

    if req.use_racco:
        racco_csv = data_dir / f"racco_{req.year}_{req.month:02d}.csv"
        if racco_csv.exists():
            from src.racco import RaccoClient
            racco_records = RaccoClient.parse_csv(racco_csv)
            agg.add_racco(racco_records)
            log.append(f"Racco: {len(racco_records)}件")
        else:
            log.append(f"Racco: CSVなし ({racco_csv.name})")

    if req.use_jalan:
        jalan_csv = data_dir / f"jalan_{req.year}_{req.month:02d}.csv"
        if jalan_csv.exists():
            from src.jalan import JalanClient
            jalan_records = JalanClient.parse_csv(jalan_csv)
            agg.add_jalan(jalan_records)
            log.append(f"じゃらん: {len(jalan_records)}件")
        else:
            log.append(f"じゃらん: CSVなし ({jalan_csv.name})")

    if req.use_mf:
        from src.mf_expense import MFExpenseClient
        mf = MFExpenseClient()
        mf.ensure_token()
        from_date = f"{req.year}-{req.month:02d}-01"
        if req.month == 12:
            to_date = f"{req.year + 1}-01-01"
        else:
            to_date = f"{req.year}-{req.month + 1:02d}-01"
        mf_records = []
        for label, office_id in MF_OFFICE_IDS.items():
            records = mf.get_travel_expenses(office_id, from_date, to_date)
            mf_records.extend(records)
            log.append(f"MF経費({label}): {len(records)}件")
        agg.add_mf_expense(mf_records)

    summary = agg.summarize()
    unmatched = agg.get_unmatched()
    log.append(f"集計結果: {len(summary)}名")
    if unmatched:
        log.append(f"未マッチ: {len(unmatched)}件")

    if not req.dry_run and summary:
        sheets.write_expense_summary(summary, req.year, req.month)
        log.append("スプレッドシート書き込み完了")

    return {"summary": summary, "unmatched": unmatched, "log": log}


@app.post("/api/journal-csv")
def journal_csv(req: AggregateRequest):
    """仕訳CSV生成（集計実行 → CSV文字列を返す）"""
    result = aggregate(req)
    summary = result["summary"]
    if not summary:
        raise HTTPException(status_code=400, detail="集計結果がありません")

    import csv
    from io import StringIO
    from datetime import date

    output = StringIO()
    writer = csv.writer(output)

    headers = [
        "取引No", "取引日",
        "借方勘定科目", "借方補助科目", "借方部門", "借方税区分", "借方金額(税込)", "借方金額(税抜)", "借方消費税額",
        "貸方勘定科目", "貸方補助科目", "貸方部門", "貸方税区分", "貸方金額(税込)", "貸方金額(税抜)", "貸方消費税額",
        "摘要", "仕訳メモ", "タグ",
    ]
    writer.writerow(headers)

    txn_no = 1
    today = date.today().strftime("%Y/%m/%d")

    categories = [
        ("shinkansen", "旅費交通費", "新幹線代"),
        ("shinkansen_ad", "広告宣伝費", "新幹線代（展示会等）"),
        ("shinkansen_welfare", "福利厚生費", "新幹線代（社内イベント）"),
        ("shinkansen_recruit", "採用費", "新幹線代（採用関連）"),
        ("shinkansen_subsidiary", "旅費交通費", "新幹線代（子会社）"),
        ("hotel", "旅費交通費", "出張宿泊費"),
        ("hotel_ad", "広告宣伝費", "出張宿泊費（展示会等）"),
        ("hotel_recruit", "採用費", "出張宿泊費（採用関連）"),
        ("train", "旅費交通費", "電車代"),
        ("train_ad", "広告宣伝費", "電車代（展示会等）"),
        ("train_recruit", "採用費", "電車代（採用関連）"),
        ("other", "旅費交通費", "その他交通費"),
        ("other_ad", "広告宣伝費", "その他交通費（展示会等）"),
        ("other_recruit", "採用費", "その他交通費（採用関連）"),
    ]

    for row in summary:
        if row["total"] == 0:
            continue
        for cat_key, account, sub_account in categories:
            amount = row.get(cat_key, 0)
            if amount == 0:
                continue
            tax_inclusive = round(amount * 1.1)
            tax_amount = tax_inclusive - amount
            writer.writerow([
                txn_no, today,
                account, sub_account, row["department"], "課対仕入10%", tax_inclusive, amount, tax_amount,
                "未払金", "", "", "対象外", tax_inclusive, tax_inclusive, 0,
                f"{row['name']} {sub_account}", "", "",
            ])
            txn_no += 1

    return {"csv": output.getvalue(), "log": result["log"]}


@app.post("/api/roi")
def roi(req: ROIRequest):
    """ROIデータ取得"""
    if req.demo:
        return _demo_roi_data()

    from src.sheets_client import SheetsClient
    sheets = SheetsClient()

    roi_master = sheets.read_roi_master(req.year, req.month)
    sales = sheets.read_sales_data()
    expenses = sheets.read_expense_summary(req.year, req.month)

    return _build_roi_response(roi_master, expenses, sales, req.month - 1)


@app.post("/api/roi/write")
def roi_write(req: ROIWriteRequest):
    """ROI結果をスプレッドシートに書き出し"""
    # まずデータ取得
    from src.sheets_client import SheetsClient
    import pandas as pd

    sheets = SheetsClient()
    roi_master = sheets.read_roi_master(req.year, req.month)
    sales = sheets.read_sales_data()
    expenses = sheets.read_expense_summary(req.year, req.month)

    roi_result = _build_roi_response(roi_master, expenses, sales, req.month - 1)
    roi_df = pd.DataFrame(roi_result["rows"])

    overall_roi = roi_result["overall_roi"]
    sheets.write_roi_summary(roi_df, req.year, req.month, overall_roi)

    return {"message": f"ROI_{req.year}年{req.month:02d}月 書き出し完了"}


@app.post("/api/fetch-csv")
def fetch_csv(req: FetchCSVRequest):
    """Playwrightで各ソースからCSVを取得"""
    if req.source == "ex":
        from src.ex_card import EXCardClient
        with EXCardClient() as client:
            client.login()
            csv_path = client.download_csv(req.year, req.month)
            records = client.parse_csv(csv_path)
        return {"message": f"EXカード: {len(records)}件取得"}
    elif req.source == "racco":
        from src.racco import RaccoClient
        with RaccoClient() as client:
            client.login()
            csv_path = client.download_csv(req.year, req.month)
            records = client.parse_csv(csv_path)
        return {"message": f"Racco: {len(records)}件取得"}
    elif req.source == "jalan":
        from src.jalan import JalanClient
        with JalanClient() as client:
            client.login()
            csv_path = client.download_csv(req.year, req.month)
            records = client.parse_csv(csv_path)
        return {"message": f"じゃらん: {len(records)}件取得"}
    elif req.source == "times":
        from src.times_car import TimesCarClient
        with TimesCarClient() as client:
            client.login()
            csv_path = client.download_csv(req.year, req.month)
            records = client.parse_csv(csv_path)
        return {"message": f"タイムズカー: {len(records)}件取得"}
    else:
        raise HTTPException(status_code=400, detail=f"未知のソース: {req.source}")


@app.post("/api/dept-roi")
def dept_roi(req: DeptROIRequest):
    """部門別ROI集計"""
    from src.config import EX_DATA_DIR
    from src.sheets_client import SheetsClient
    from src.aggregator import ExpenseAggregator

    log = []

    sheets = SheetsClient()
    dept_master = sheets.read_department_master(req.year, req.month)
    log.append(f"部署マスタ: {len(dept_master)}名")

    ex_card_master, ex_card_exclude_ids, ex_card_category_map = sheets.read_ex_card_master()
    log.append(f"EXカードマスタ: {len(ex_card_master)}件")

    ringi_lookup = sheets.read_ringi_lookup()
    log.append(f"稟議ルックアップ: {len(ringi_lookup)}件")

    agg = ExpenseAggregator(
        dept_master,
        ex_card_master=ex_card_master,
        ex_card_exclude_ids=ex_card_exclude_ids,
        ex_card_category_map=ex_card_category_map,
        ringi_lookup=ringi_lookup,
    )

    data_dir = EX_DATA_DIR

    # EXカード
    ex_csv = data_dir / f"ex_{req.year}_{req.month:02d}.csv"
    if ex_csv.exists():
        from src.ex_card import EXCardClient
        ex_records = EXCardClient.parse_csv(ex_csv)
        agg.add_ex_card(ex_records)
        log.append(f"EXカード: {len(ex_records)}件")

    # タイムズカー
    times_csv = data_dir / f"times_{req.year}_{req.month:02d}.csv"
    if times_csv.exists():
        from src.times_car import TimesCarClient
        times_records = TimesCarClient.parse_csv(times_csv)
        agg.add_times_car(times_records)
        log.append(f"タイムズカー: {len(times_records)}件")

    # Racco
    racco_csv = data_dir / f"racco_{req.year}_{req.month:02d}.csv"
    if racco_csv.exists():
        from src.racco import RaccoClient
        racco_records = RaccoClient.parse_csv(racco_csv)
        agg.add_racco(racco_records)
        log.append(f"Racco: {len(racco_records)}件")

    # じゃらん
    jalan_csv = data_dir / f"jalan_{req.year}_{req.month:02d}.csv"
    if jalan_csv.exists():
        from src.jalan import JalanClient
        jalan_records = JalanClient.parse_csv(jalan_csv)
        agg.add_jalan(jalan_records)
        log.append(f"じゃらん: {len(jalan_records)}件")

    # ROIマスタ読み込み
    roi_master = sheets.read_roi_master(req.year, req.month)
    log.append(f"ROIマスタ: {len(roi_master)}名")

    # セグメント別集計（SDR/BDR/ALLI/UNI/CCS/事業開発/COM/その他）
    seg_summary = agg.summarize_by_segment(roi_master)
    log.append(f"セグメント別集計: {len(seg_summary)}セグメント")

    # セグメント別売上（予実シートから取得）
    segment_sales = sheets.read_segment_sales(req.month)

    # 売上・ROIを付与
    result_rows = []
    for row in seg_summary:
        seg = row["segment"]
        revenue = segment_sales.get(seg, 0)
        roi = revenue / row["total"] if row["total"] > 0 else 0
        result_rows.append({
            "department": seg,  # フロントとの互換性のためdepartmentキーを維持
            "headcount": row["headcount"],
            "shinkansen": row["shinkansen"],
            "train": row["train"],
            "car": row["car"],
            "airplane": row["airplane"],
            "hotel": row["hotel"],
            "total": row["total"],
            "sales": revenue,
            "roi": round(roi, 1),
        })

    total_expense = sum(r["total"] for r in result_rows)
    total_sales = sum(r["sales"] for r in result_rows)
    overall_roi = round(total_sales / total_expense, 1) if total_expense > 0 else 0

    # スプシ書き込み
    if req.write_sheet and seg_summary:
        sheets.write_segment_roi(result_rows, req.year, req.month)
        log.append("セグメント別ROIタブ書き込み完了")

    return {
        "departments": result_rows,
        "totals": {
            "total_expense": total_expense,
            "total_sales": total_sales,
            "overall_roi": overall_roi,
        },
        "log": log,
    }


@app.post("/api/dept-roi/write")
def dept_roi_write(req: ROIWriteRequest):
    """部門別ROIをスプレッドシートに書き出し"""
    result = dept_roi(DeptROIRequest(year=req.year, month=req.month, write_sheet=True))
    return {"message": f"部門別ROI {req.year}年{req.month}月 書き出し完了"}


# ── ヘルパー ──


def _build_roi_response(roi_master: dict, expenses: list[dict], sales: dict, month_index: int) -> dict:
    """ROIテーブルを構築してレスポンス形式で返す"""
    from src.sheets_client import normalize_name

    SEGMENT_SALES_MAP = {
        "SDR": "SDR_月次新規獲得売上",
        "BDR": "BDR_月次新規獲得売上",
        "ALLI": "ALLI_月次新規獲得売上",
        "UNION": "UNI_月次新規獲得売上",
        "法人": "法人_月次新規獲得売上",
    }

    cat_expenses = {}
    for row in expenses:
        name = normalize_name(row["name"])
        roi_cat = roi_master.get(name, "未分類")
        cat_expenses[roi_cat] = cat_expenses.get(roi_cat, 0) + row["total"]

    segment_expenses = {}
    for roi_cat, amount in cat_expenses.items():
        matched = False
        for seg_key in SEGMENT_SALES_MAP:
            if seg_key in roi_cat:
                segment_expenses[seg_key] = segment_expenses.get(seg_key, 0) + amount
                matched = True
                break
        if not matched:
            segment_expenses["その他"] = segment_expenses.get("その他", 0) + amount

    rows = []
    total_expense = 0
    total_revenue = 0
    for seg_key, sales_row_label in SEGMENT_SALES_MAP.items():
        expense = segment_expenses.get(seg_key, 0)
        sales_values = sales["data"].get(sales_row_label, [])
        revenue = int(sales_values[month_index]) * 1000 if month_index < len(sales_values) else 0
        roi = revenue / expense if expense > 0 else 0
        total_expense += expense
        total_revenue += revenue
        rows.append({
            "セグメント": seg_key,
            "旅費交通費": expense,
            "売上": revenue,
            "ROI": round(roi, 1),
        })

    other_expense = segment_expenses.get("その他", 0)
    if other_expense > 0:
        total_expense += other_expense
        rows.append({
            "セグメント": "その他",
            "旅費交通費": other_expense,
            "売上": 0,
            "ROI": 0,
        })

    overall_roi = total_revenue / total_expense if total_expense > 0 else 0

    return {
        "rows": rows,
        "total_expense": total_expense,
        "total_revenue": total_revenue,
        "overall_roi": round(overall_roi, 1),
    }


def _demo_roi_data() -> dict:
    """デモ用ROIデータ"""
    rows = [
        {"セグメント": "SDR", "旅費交通費": 132192, "売上": 12800000, "ROI": 96.8},
        {"セグメント": "BDR", "旅費交通費": 56078, "売上": 6300000, "ROI": 112.3},
        {"セグメント": "ALLI", "旅費交通費": 45518, "売上": 4500000, "ROI": 98.9},
        {"セグメント": "UNION", "旅費交通費": 104679, "売上": 3900000, "ROI": 37.3},
        {"セグメント": "法人", "旅費交通費": 146888, "売上": 22000000, "ROI": 149.8},
        {"セグメント": "その他", "旅費交通費": 32745, "売上": 0, "ROI": 0},
    ]
    return {
        "rows": rows,
        "total_expense": 518100,
        "total_revenue": 49500000,
        "overall_roi": 95.5,
    }
