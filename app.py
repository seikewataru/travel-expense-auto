"""旅費自動仕訳・ROI — Streamlit Webアプリ"""

import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="旅費自動仕訳・ROI",
    page_icon="🧾",
    layout="wide",
)


# --- バックエンド関数（UI より先に定義） ---


def fetch_csv_source(source: str, year: int, month: int) -> str:
    """Playwrightで各ソースからCSVを取得する"""
    if source == "ex":
        from src.ex_card import EXCardClient
        with EXCardClient() as client:
            client.login()
            csv_path = client.download_csv(year, month)
            records = client.parse_csv(csv_path)
        return f"EXカード: {len(records)}件取得 → {csv_path.name}"

    elif source == "racco":
        from src.racco import RaccoClient
        with RaccoClient() as client:
            client.login()
            csv_path = client.download_csv(year, month)
            records = client.parse_csv(csv_path)
        return f"Racco: {len(records)}件取得 → {csv_path.name}"

    elif source == "jalan":
        from src.jalan import JalanClient
        with JalanClient() as client:
            client.login()
            csv_path = client.download_csv(year, month)
            records = client.parse_csv(csv_path)
        return f"じゃらん: {len(records)}件取得 → {csv_path.name}"

    elif source == "times":
        from src.times_car import TimesCarClient
        with TimesCarClient() as client:
            client.login()
            csv_path = client.download_csv(year, month)
            records = client.parse_csv(csv_path)
        return f"タイムズカー: {len(records)}件取得 → {csv_path.name}"

    else:
        raise ValueError(f"未知のソース: {source}")


def run_aggregate(year: int, month: int, use_mf: bool, use_ex: bool, use_racco: bool, use_jalan: bool, use_times: bool, dry_run: bool) -> dict:
    """既存の集計エンジンを呼び出す"""
    from src.config import EX_DATA_DIR, MF_OFFICE_IDS
    from src.sheets_client import SheetsClient
    from src.aggregator import ExpenseAggregator

    log = []

    # マスタ読み込み
    sheets = SheetsClient()
    dept_master = sheets.read_department_master(year, month)
    log.append(f"部署マスタ: {len(dept_master)}名")

    ex_card_master, ex_card_exclude_ids, ex_card_category_map = sheets.read_ex_card_master()
    log.append(f"EXカードマスタ: {len(ex_card_master)}件（除外: {len(ex_card_exclude_ids)}件）")

    agg = ExpenseAggregator(dept_master, ex_card_master=ex_card_master, ex_card_exclude_ids=ex_card_exclude_ids, ex_card_category_map=ex_card_category_map)

    data_dir = EX_DATA_DIR

    # EXカード（既存CSV）
    if use_ex:
        ex_csv = data_dir / f"ex_{year}_{month:02d}.csv"
        if ex_csv.exists():
            from src.ex_card import EXCardClient
            ex_records = EXCardClient.parse_csv(ex_csv)
            agg.add_ex_card(ex_records)
            log.append(f"EXカード: {len(ex_records)}件")
        else:
            log.append(f"EXカード: CSVなし ({ex_csv.name})")

    # タイムズカー（既存CSV）
    if use_times:
        times_csv = data_dir / f"times_{year}_{month:02d}.csv"
        if times_csv.exists():
            from src.times_car import TimesCarClient
            times_records = TimesCarClient.parse_csv(times_csv)
            agg.add_times_car(times_records)
            log.append(f"タイムズカー: {len(times_records)}件")
        else:
            log.append(f"タイムズカー: CSVなし ({times_csv.name})")

    # Racco（既存CSV）
    if use_racco:
        racco_csv = data_dir / f"racco_{year}_{month:02d}.csv"
        if racco_csv.exists():
            from src.racco import RaccoClient
            racco_records = RaccoClient.parse_csv(racco_csv)
            agg.add_racco(racco_records)
            log.append(f"Racco: {len(racco_records)}件")
        else:
            log.append(f"Racco: CSVなし ({racco_csv.name})")

    # じゃらん（既存CSV）
    if use_jalan:
        jalan_csv = data_dir / f"jalan_{year}_{month:02d}.csv"
        if jalan_csv.exists():
            from src.jalan import JalanClient
            jalan_records = JalanClient.parse_csv(jalan_csv)
            agg.add_jalan(jalan_records)
            log.append(f"じゃらん: {len(jalan_records)}件")
        else:
            log.append(f"じゃらん: CSVなし ({jalan_csv.name})")

    # MF経費API
    if use_mf:
        from src.mf_expense import MFExpenseClient
        mf = MFExpenseClient()
        mf.ensure_token()
        from_date = f"{year}-{month:02d}-01"
        if month == 12:
            to_date = f"{year + 1}-01-01"
        else:
            to_date = f"{year}-{month + 1:02d}-01"
        mf_records = []
        for label, office_id in MF_OFFICE_IDS.items():
            records = mf.get_travel_expenses(office_id, from_date, to_date)
            mf_records.extend(records)
            log.append(f"MF経費({label}): {len(records)}件")
        agg.add_mf_expense(mf_records)

    # 集計
    summary = agg.summarize()
    unmatched = agg.get_unmatched()
    log.append(f"集計結果: {len(summary)}名")
    if unmatched:
        log.append(f"未マッチ: {len(unmatched)}件")

    # シート書き込み
    if not dry_run and summary:
        sheets.write_expense_summary(summary, year, month)
        log.append("スプレッドシート書き込み完了")

    return {"summary": summary, "unmatched": unmatched, "log": log}


def load_roi_data(year: int, month: int) -> dict:
    """ROIダッシュボード用データを読み込む"""
    from src.sheets_client import SheetsClient

    sheets = SheetsClient()

    # 1. ROIカテゴリ付き人員マスタ
    roi_master = sheets.read_roi_master(year, month)

    # 2. 売上データ
    sales = sheets.read_sales_data()

    # 3. 旅費集計（既存CSV + MF経費）
    expense_result = run_aggregate(year, month, use_mf=True, use_ex=True, use_racco=True, use_jalan=True, use_times=True, dry_run=True)

    return {
        "roi_master": roi_master,
        "sales": sales,
        "expenses": expense_result["summary"],
    }


def build_roi_table(roi_master: dict, expenses: list[dict], sales: dict, month_index: int) -> pd.DataFrame:
    """ROIカテゴリ別に旅費と売上を集計してROIテーブルを生成"""

    # ROIカテゴリ → 売上セグメントのマッピング
    # ROIカテゴリ例: "マーケ_SDR_TUNAG" → 売上行 "SDR_月次新規獲得売上"
    SEGMENT_SALES_MAP = {
        "SDR": "SDR_月次新規獲得売上",
        "BDR": "BDR_月次新規獲得売上",
        "ALLI": "ALLI_月次新規獲得売上",
        "UNION": "UNI_月次新規獲得売上",
        "法人": "法人_月次新規獲得売上",
    }

    from src.sheets_client import normalize_name

    # 社員名 → ROIカテゴリ
    # 旅費を ROIカテゴリ別に集計
    cat_expenses = {}  # roi_category -> total_expense
    for row in expenses:
        name = normalize_name(row["name"])
        roi_cat = roi_master.get(name, "")
        if not roi_cat:
            roi_cat = "未分類"
        cat_expenses[roi_cat] = cat_expenses.get(roi_cat, 0) + row["total"]

    # ROIカテゴリをセグメントに集約
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

    # 売上を取得
    rows = []
    for seg_key, sales_row_label in SEGMENT_SALES_MAP.items():
        expense = segment_expenses.get(seg_key, 0)
        sales_values = sales["data"].get(sales_row_label, [])
        revenue = int(sales_values[month_index]) * 1000 if month_index < len(sales_values) else 0  # 千円→円
        roi = revenue / expense if expense > 0 else 0
        rows.append({
            "セグメント": seg_key,
            "旅費交通費": expense,
            "売上": revenue,
            "ROI": round(roi, 1),
        })

    # その他
    other_expense = segment_expenses.get("その他", 0)
    if other_expense > 0:
        rows.append({
            "セグメント": "その他",
            "旅費交通費": other_expense,
            "売上": 0,
            "ROI": 0,
        })

    return pd.DataFrame(rows)


def _demo_roi_data() -> dict:
    """デモ用のROIデータを生成"""
    roi_master = {
        "佐々木 隆寛": "CS_UNION_TUNAG",
        "杉山 一彦": "マーケ_BDR_TUNAG",
        "飯田 真理子": "FS_法人_TUNAG",
        "長尾 敏": "FS_法人_TUNAG",
        "半田 優貴": "アライアンス_UNION_TUNAG",
        "長谷川 悠生": "マーケ_SDR_TUNAG",
        "東出 和輝": "マーケ_SDR_TUNAG",
        "内藤 一真": "FS_法人_TUNAG",
        "櫻井 美聡": "マーケ_SDR_TUNAG",
        "金内 唯香": "事業開発_コンサルタント_TUNAG",
    }
    expenses = [
        {"name": "佐々木 隆寛", "department": "UNION CS部", "shinkansen": 41764, "hotel": 455, "train": 11196, "other": 51264, "total": 104679, "emp_no": "222"},
        {"name": "杉山 一彦", "department": "CRO室", "shinkansen": 36537, "hotel": 7427, "train": 12114, "other": 0, "total": 56078, "emp_no": "307"},
        {"name": "飯田 真理子", "department": "営業2部", "shinkansen": 21655, "hotel": 0, "train": 31127, "other": 0, "total": 52782, "emp_no": "287"},
        {"name": "長尾 敏", "department": "営業1部", "shinkansen": 0, "hotel": 28702, "train": 21777, "other": 0, "total": 50479, "emp_no": "146"},
        {"name": "半田 優貴", "department": "UNION営業部", "shinkansen": 0, "hotel": 0, "train": 6425, "other": 39093, "total": 45518, "emp_no": "207"},
        {"name": "長谷川 悠生", "department": "営業1部", "shinkansen": 30791, "hotel": 0, "train": 14532, "other": 0, "total": 45323, "emp_no": "49"},
        {"name": "東出 和輝", "department": "営業1部", "shinkansen": 15645, "hotel": 0, "train": 15379, "other": 14091, "total": 45115, "emp_no": "247"},
        {"name": "内藤 一真", "department": "営業1部", "shinkansen": 0, "hotel": 0, "train": 8019, "other": 35608, "total": 43627, "emp_no": "224"},
        {"name": "櫻井 美聡", "department": "営業1部", "shinkansen": 26246, "hotel": 0, "train": 15508, "other": 0, "total": 41754, "emp_no": "213"},
        {"name": "金内 唯香", "department": "ビジネス共創部", "shinkansen": 0, "hotel": 0, "train": 2290, "other": 30455, "total": 32745, "emp_no": "98"},
    ]
    # 売上データ（デモ）: 月次 × 12ヶ月（千円単位）
    sales = {
        "months": ["2026年1月", "2026年2月", "2026年3月", "2026年4月", "2026年5月", "2026年6月",
                    "2026年7月", "2026年8月", "2026年9月", "2026年10月", "2026年11月", "2026年12月"],
        "data": {
            "SDR_月次新規獲得売上": [8500, 9200, 12800, 7600, 0, 0, 0, 0, 0, 0, 0, 0],
            "BDR_月次新規獲得売上": [4200, 5100, 6300, 3800, 0, 0, 0, 0, 0, 0, 0, 0],
            "ALLI_月次新規獲得売上": [3100, 2800, 4500, 2200, 0, 0, 0, 0, 0, 0, 0, 0],
            "UNI_月次新規獲得売上": [2800, 3200, 3900, 2100, 0, 0, 0, 0, 0, 0, 0, 0],
            "法人_月次新規獲得売上": [15200, 16800, 22000, 13200, 0, 0, 0, 0, 0, 0, 0, 0],
            "合計_月次売上": [33800, 37100, 49500, 28900, 0, 0, 0, 0, 0, 0, 0, 0],
        },
    }
    return {"roi_master": roi_master, "sales": sales, "expenses": expenses}


def generate_journal_csv(summary: list[dict]) -> str:
    """MF会計Plusインポート用CSVを生成"""
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

    for row in summary:
        if row["total"] == 0:
            continue
        categories = [
            ("shinkansen", "旅費交通費", "新幹線代"),
            ("shinkansen_ad", "広告宣伝費", "新幹線代（展示会等）"),
            ("shinkansen_welfare", "福利厚生費", "新幹線代（社内イベント）"),
            ("shinkansen_recruit", "採用費", "新幹線代（採用関連）"),
            ("shinkansen_subsidiary", "旅費交通費", "新幹線代（子会社）"),
            ("hotel", "旅費交通費", "出張宿泊費"),
            ("train", "旅費交通費", "電車代"),
            ("other", "旅費交通費", "その他交通費"),
        ]
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

    return output.getvalue()


# --- 認証 ---


def check_password():
    """パスワード保護"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    password = st.text_input("パスワード", type="password")
    if password == st.secrets.get("app_password", "stmn2026"):
        st.session_state.authenticated = True
        st.rerun()
    elif password:
        st.error("パスワードが違います")
    return False


if not check_password():
    st.stop()

# --- メインUI ---
st.title("旅費自動仕訳・ROI")

tab1, tab2, tab3 = st.tabs(["📊 旅費集計", "📝 仕訳生成", "📈 ROIダッシュボード"])

# --- タブ1: 旅費集計 ---
with tab1:
    st.header("旅費集計")

    col1, col2, col3 = st.columns([1, 1, 2])
    now = datetime.now()
    with col1:
        year = st.number_input("年", min_value=2024, max_value=2030, value=now.year)
    with col2:
        month = st.number_input("月", min_value=1, max_value=12, value=max(1, now.month - 1))

    st.subheader("データソース")
    use_mf = st.checkbox("MF経費（API）", value=True)
    use_ex = st.checkbox("EXカード", value=True)
    use_racco = st.checkbox("Racco（楽天トラベル）", value=True)
    use_jalan = st.checkbox("じゃらん", value=True)
    use_times = st.checkbox("タイムズカー", value=True)

    # CSV取得ボタン
    st.subheader("CSV取得（Playwright）")
    st.caption("ブラウザを起動して各サービスから最新CSVを取得します（ローカル実行のみ）")

    fetch_cols = st.columns(4)
    with fetch_cols[0]:
        if st.button("🚅 EXカード取得", use_container_width=True):
            with st.spinner("EXカード取得中..."):
                try:
                    msg = fetch_csv_source("ex", int(year), int(month))
                    st.success(msg)
                except Exception as e:
                    st.error(f"EXカード取得エラー: {e}")
    with fetch_cols[1]:
        if st.button("🏨 Racco取得", use_container_width=True):
            with st.spinner("Racco取得中..."):
                try:
                    msg = fetch_csv_source("racco", int(year), int(month))
                    st.success(msg)
                except Exception as e:
                    st.error(f"Racco取得エラー: {e}")
    with fetch_cols[2]:
        if st.button("🏨 じゃらん取得", use_container_width=True):
            with st.spinner("じゃらん取得中..."):
                try:
                    msg = fetch_csv_source("jalan", int(year), int(month))
                    st.success(msg)
                except Exception as e:
                    st.error(f"じゃらん取得エラー: {e}")
    with fetch_cols[3]:
        if st.button("🚗 タイムズ取得", use_container_width=True):
            with st.spinner("タイムズカー取得中..."):
                try:
                    msg = fetch_csv_source("times", int(year), int(month))
                    st.success(msg)
                except Exception as e:
                    st.error(f"タイムズカー取得エラー: {e}")

    if st.button("📥 全ソース一括取得", use_container_width=True):
        with st.spinner("全ソースCSV取得中（数分かかります）..."):
            results = []
            for source in ["ex", "racco", "jalan", "times"]:
                try:
                    msg = fetch_csv_source(source, int(year), int(month))
                    results.append(f"✅ {msg}")
                except Exception as e:
                    results.append(f"❌ {source}: {e}")
            for r in results:
                st.write(r)

    st.divider()
    dry_run = st.checkbox("dry-run（シート書き込みなし）", value=True)

    if st.button("▶ 集計実行", type="primary", use_container_width=True):
        with st.spinner("集計中..."):
            try:
                result = run_aggregate(int(year), int(month), use_mf, use_ex, use_racco, use_jalan, use_times, dry_run)
                st.session_state["aggregate_result"] = result
            except Exception as e:
                st.error(f"エラー: {e}")
                import traceback
                st.code(traceback.format_exc())

    if "aggregate_result" in st.session_state:
        result = st.session_state["aggregate_result"]
        summary = result["summary"]
        unmatched = result["unmatched"]

        if summary:
            df = pd.DataFrame(summary)
            total = df["total"].sum()
            st.metric("総合計", f"¥{total:,.0f}", delta=f"{len(summary)}名")

            col_a, col_b, col_c, col_d = st.columns(4)
            col_a.metric("新幹線", f"¥{df['shinkansen'].sum():,.0f}")
            col_b.metric("宿泊", f"¥{df['hotel'].sum():,.0f}")
            col_c.metric("在来線", f"¥{df['train'].sum():,.0f}")
            col_d.metric("その他", f"¥{df['other'].sum():,.0f}")

            st.dataframe(
                df[["emp_no", "name", "department", "shinkansen", "hotel", "train", "other", "total"]].rename(
                    columns={
                        "emp_no": "社員番号",
                        "name": "名前",
                        "department": "部署",
                        "shinkansen": "新幹線",
                        "hotel": "宿泊",
                        "train": "在来線",
                        "other": "その他",
                        "total": "合計",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

        if unmatched:
            st.warning(f"マッチしなかったレコード: {len(unmatched)}件")
            st.dataframe(pd.DataFrame(unmatched), use_container_width=True, hide_index=True)

        if result.get("log"):
            with st.expander("実行ログ"):
                st.code("\n".join(result["log"]))


# --- タブ2: 仕訳生成 ---
with tab2:
    st.header("MF会計Plus 仕訳CSV生成")
    st.info("集計結果からMF会計Plusインポート用CSVを生成します。先に「旅費集計」タブで集計を実行してください。")

    if "aggregate_result" in st.session_state and st.session_state["aggregate_result"]["summary"]:
        if st.button("📄 仕訳CSV生成", type="primary"):
            csv_data = generate_journal_csv(st.session_state["aggregate_result"]["summary"])
            st.download_button(
                label="⬇ CSVダウンロード",
                data=csv_data,
                file_name=f"journal_{int(year)}_{int(month):02d}.csv",
                mime="text/csv",
            )
    else:
        st.warning("先に旅費集計を実行してください。")

# --- タブ3: ROIダッシュボード ---
with tab3:
    st.header("部門別 旅費ROI")

    col_r1, col_r2 = st.columns([1, 1])
    with col_r1:
        roi_year = st.number_input("年", min_value=2024, max_value=2030, value=now.year, key="roi_year")
    with col_r2:
        roi_month = st.number_input("月", min_value=1, max_value=12, value=max(1, now.month - 1), key="roi_month")

    demo_mode = st.checkbox("デモデータで表示", value=False, key="roi_demo")

    if st.button("▶ ROI分析実行", type="primary", use_container_width=True, key="roi_btn"):
        if demo_mode:
            st.session_state["roi_data"] = _demo_roi_data()
            st.session_state["roi_target_year"] = int(roi_year)
            st.session_state["roi_target_month"] = int(roi_month)
        else:
            with st.spinner("データ読み込み中..."):
                try:
                    roi_data = load_roi_data(int(roi_year), int(roi_month))
                    st.session_state["roi_data"] = roi_data
                    st.session_state["roi_target_year"] = int(roi_year)
                    st.session_state["roi_target_month"] = int(roi_month)
                except Exception as e:
                    st.error(f"エラー: {e}")
                    import traceback
                    st.code(traceback.format_exc())

    if "roi_data" in st.session_state:
        roi_data = st.session_state["roi_data"]
        r_year = st.session_state["roi_target_year"]
        r_month = st.session_state["roi_target_month"]

        # 月インデックス（1月=0, 2月=1, ...）
        month_index = r_month - 1

        roi_df = build_roi_table(
            roi_data["roi_master"],
            roi_data["expenses"],
            roi_data["sales"],
            month_index,
        )

        st.subheader(f"{r_year}年{r_month}月 セグメント別ROI")

        # サマリ指標
        total_expense = roi_df["旅費交通費"].sum()
        total_revenue = roi_df["売上"].sum()
        overall_roi = total_revenue / total_expense if total_expense > 0 else 0

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("旅費交通費合計", f"¥{total_expense:,.0f}")
        mc2.metric("売上合計", f"¥{total_revenue:,.0f}")
        mc3.metric("全体ROI", f"{overall_roi:.1f}x")

        # テーブル
        display_df = roi_df.copy()
        display_df["旅費交通費"] = display_df["旅費交通費"].apply(lambda x: f"¥{x:,.0f}")
        display_df["売上"] = display_df["売上"].apply(lambda x: f"¥{x:,.0f}")
        display_df["ROI"] = display_df["ROI"].apply(lambda x: f"{x:.1f}x")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # 棒グラフ
        st.subheader("セグメント別 旅費 vs 売上")
        chart_df = roi_df[roi_df["セグメント"] != "その他"].melt(
            id_vars=["セグメント"],
            value_vars=["旅費交通費", "売上"],
            var_name="項目",
            value_name="金額",
        )
        st.bar_chart(
            chart_df.pivot(index="セグメント", columns="項目", values="金額"),
        )
