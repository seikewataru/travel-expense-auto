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

    ex_card_master, ex_card_exclude_ids = sheets.read_ex_card_master()
    log.append(f"EXカードマスタ: {len(ex_card_master)}件（除外: {len(ex_card_exclude_ids)}件）")

    agg = ExpenseAggregator(dept_master, ex_card_master=ex_card_master, ex_card_exclude_ids=ex_card_exclude_ids)

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
    use_ex = st.checkbox("EXカード（既存CSV）", value=True)
    use_racco = st.checkbox("Racco（既存CSV）", value=True)
    use_jalan = st.checkbox("じゃらん（既存CSV）", value=True)
    use_times = st.checkbox("タイムズカー（既存CSV）", value=True)

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
    st.info("Phase 4 で実装予定")
