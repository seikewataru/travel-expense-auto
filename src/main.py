"""CLIエントリポイント — auth / fetch / ex-fetch / times-fetch / aggregate サブコマンド"""

import argparse
import json
import sys
from pathlib import Path

from src.mf_expense import MFExpenseClient


def cmd_auth(_args: argparse.Namespace) -> None:
    """初回OAuth認証"""
    client = MFExpenseClient()
    client.authorize()


def cmd_fetch(args: argparse.Namespace) -> None:
    """経費データ取得"""
    client = MFExpenseClient()
    client.ensure_token()

    # 事業者一覧を取得
    offices = client.get_offices()
    if not offices:
        print("事業者が見つかりません", file=sys.stderr)
        sys.exit(1)

    # 最初の事業者を使用（複数ある場合は一覧表示）
    if len(offices) > 1:
        print("事業者一覧:")
        for i, office in enumerate(offices):
            print(f"  {i + 1}. {office.get('name', 'N/A')} (id: {office['id']})")
        print(f"\n最初の事業者を使用: {offices[0].get('name', 'N/A')}")

    office_id = offices[0]["id"]

    # 経費明細を取得（月初〜月末）
    recognized_from = f"{args.year}-{args.month:02d}-01"
    if args.month == 12:
        recognized_to = f"{args.year + 1}-01-01"
    else:
        recognized_to = f"{args.year}-{args.month + 1:02d}-01"
    print(f"\n経費明細を取得中... ({args.year}年{args.month}月)")
    transactions = client.get_ex_transactions(office_id, recognized_from, recognized_to)
    print(f"取得件数: {len(transactions)}件")

    if args.dry_run:
        print("\n[dry-run] 取得データ:")
        print(json.dumps(transactions, indent=2, ensure_ascii=False))
    else:
        # TODO: Phase 2でGoogle Sheets書き込み
        print(json.dumps(transactions, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="出張旅費ROI — MF経費データ取得")
    sub = parser.add_subparsers(dest="command", required=True)

    # auth サブコマンド
    sub.add_parser("auth", help="初回OAuth認証（ブラウザ→コード入力→トークン保存）")

    # fetch サブコマンド
    fetch_parser = sub.add_parser("fetch", help="経費データ取得")
    fetch_parser.add_argument("--year", type=int, required=True, help="対象年")
    fetch_parser.add_argument("--month", type=int, required=True, help="対象月")
    fetch_parser.add_argument(
        "--dry-run", action="store_true", help="取得のみ（書き込みなし）"
    )

    # ex-fetch サブコマンド
    ex_parser = sub.add_parser("ex-fetch", help="EXカード利用実績CSV取得")
    ex_parser.add_argument("--year", type=int, required=True, help="対象年")
    ex_parser.add_argument("--month", type=int, required=True, help="対象月")
    ex_parser.add_argument(
        "--dry-run", action="store_true", help="取得・表示のみ（書き込みなし）"
    )

    # times-fetch サブコマンド
    times_parser = sub.add_parser("times-fetch", help="タイムズカー利用明細CSV取得")
    times_parser.add_argument("--year", type=int, required=True, help="対象年")
    times_parser.add_argument("--month", type=int, required=True, help="対象月")
    times_parser.add_argument(
        "--dry-run", action="store_true", help="取得・表示のみ（書き込みなし）"
    )

    # racco-fetch サブコマンド
    racco_parser = sub.add_parser("racco-fetch", help="Racco宿泊実績CSV取得")
    racco_parser.add_argument("--year", type=int, required=True, help="対象年")
    racco_parser.add_argument("--month", type=int, required=True, help="対象月")
    racco_parser.add_argument(
        "--dry-run", action="store_true", help="取得・表示のみ（書き込みなし）"
    )

    # jalan-fetch サブコマンド
    jalan_parser = sub.add_parser("jalan-fetch", help="じゃらん宿泊予約データCSV取得")
    jalan_parser.add_argument("--year", type=int, required=True, help="対象年")
    jalan_parser.add_argument("--month", type=int, required=True, help="対象月")
    jalan_parser.add_argument(
        "--dry-run", action="store_true", help="取得・表示のみ（書き込みなし）"
    )

    # aggregate サブコマンド
    agg_parser = sub.add_parser("aggregate", help="旅費集計（部署マスタ連携 → スプレッドシート出力）")
    agg_parser.add_argument("--year", type=int, required=True, help="対象年")
    agg_parser.add_argument("--month", type=int, required=True, help="対象月")
    agg_parser.add_argument(
        "--dry-run", action="store_true", help="集計結果を表示のみ（シート書き込みなし）"
    )
    agg_parser.add_argument(
        "--skip-fetch", action="store_true", help="CSVの再取得をスキップ（data/内の既存CSVを使用）"
    )

    args = parser.parse_args()
    if args.command == "auth":
        cmd_auth(args)
    elif args.command == "fetch":
        cmd_fetch(args)
    elif args.command == "ex-fetch":
        cmd_ex_fetch(args)
    elif args.command == "times-fetch":
        cmd_times_fetch(args)
    elif args.command == "racco-fetch":
        cmd_racco_fetch(args)
    elif args.command == "jalan-fetch":
        cmd_jalan_fetch(args)
    elif args.command == "aggregate":
        cmd_aggregate(args)


def cmd_ex_fetch(args: argparse.Namespace) -> None:
    """EXカード利用実績CSV取得"""
    from src.ex_card import EXCardClient

    with EXCardClient() as client:
        client.login()
        csv_path = client.download_csv(args.year, args.month)
        records = client.parse_csv(csv_path)

    print(f"\n取得件数: {len(records)}件")
    if args.dry_run or True:  # Phase 1bでは常に表示のみ
        print(json.dumps(records, indent=2, ensure_ascii=False))


def cmd_times_fetch(args: argparse.Namespace) -> None:
    """タイムズカー利用明細CSV取得"""
    from src.times_car import TimesCarClient

    with TimesCarClient() as client:
        client.login()
        csv_path = client.download_csv(args.year, args.month)
        records = client.parse_csv(csv_path)

    print(f"\n取得件数: {len(records)}件")
    print(json.dumps(records, indent=2, ensure_ascii=False))


def cmd_racco_fetch(args: argparse.Namespace) -> None:
    """Racco宿泊実績CSV取得"""
    from src.racco import RaccoClient

    with RaccoClient() as client:
        client.login()
        csv_path = client.download_csv(args.year, args.month)
        records = client.parse_csv(csv_path)

    print(f"\n取得件数: {len(records)}件")
    print(json.dumps(records, indent=2, ensure_ascii=False))


def cmd_jalan_fetch(args: argparse.Namespace) -> None:
    """じゃらん宿泊予約データCSV取得"""
    from src.jalan import JalanClient

    with JalanClient() as client:
        client.login()
        csv_path = client.download_csv(args.year, args.month)
        records = client.parse_csv(csv_path)

    print(f"\n取得件数: {len(records)}件")
    print(json.dumps(records, indent=2, ensure_ascii=False))


def cmd_aggregate(args: argparse.Namespace) -> None:
    """旅費集計 — 部署マスタ連携 → カテゴリ別個人集計 → スプレッドシート出力"""
    from src.config import EX_DATA_DIR, MF_OFFICE_IDS
    from src.sheets_client import SheetsClient
    from src.aggregator import ExpenseAggregator

    year, month = args.year, args.month

    # 1. マスタ読み込み（部署マスタ + EXカードマスタ）
    print(f"=== 旅費集計 {year}年{month}月 ===\n")
    sheets = SheetsClient()
    dept_master = sheets.read_department_master(year, month)
    ex_card_master, ex_card_exclude_ids, ex_card_category_map = sheets.read_ex_card_master()
    ringi_lookup = sheets.read_ringi_lookup()

    agg = ExpenseAggregator(dept_master, ex_card_master=ex_card_master, ex_card_exclude_ids=ex_card_exclude_ids, ex_card_category_map=ex_card_category_map, ringi_lookup=ringi_lookup)

    # 2. 各ソースCSV取得（--skip-fetch なら既存CSVを使用）
    data_dir = EX_DATA_DIR

    # EXカード（除外対象シートから乗車日基準・PL税抜一致のデータを使用）
    print("\n--- EXカード（除外対象シート）---")
    ex_accounting = sheets.read_ex_card_accounting(year, month)
    agg.add_ex_card_accounting(ex_accounting)

    # タイムズカー
    times_csv = data_dir / f"times_{year}_{month:02d}.csv"
    if not args.skip_fetch:
        from src.times_car import TimesCarClient
        print("\n--- タイムズカー取得 ---")
        with TimesCarClient() as client:
            client.login()
            times_csv = client.download_csv(year, month)
    if times_csv.exists():
        from src.times_car import TimesCarClient
        times_records = TimesCarClient.parse_csv(times_csv)
        agg.add_times_car(times_records)
        print(f"  タイムズカー: {len(times_records)}件追加")
    else:
        print(f"  タイムズカー: CSVなし ({times_csv})")

    # Racco
    racco_csv = data_dir / f"racco_{year}_{month:02d}.csv"
    if not args.skip_fetch:
        from src.racco import RaccoClient
        print("\n--- Racco取得 ---")
        with RaccoClient() as client:
            client.login()
            racco_csv = client.download_csv(year, month)
    if racco_csv.exists():
        from src.racco import RaccoClient
        racco_records = RaccoClient.parse_csv(racco_csv)
        agg.add_racco(racco_records)
        print(f"  Racco: {len(racco_records)}件追加")
    else:
        print(f"  Racco: CSVなし ({racco_csv})")

    # じゃらん
    jalan_csv = data_dir / f"jalan_{year}_{month:02d}.csv"
    if not args.skip_fetch:
        from src.jalan import JalanClient
        print("\n--- じゃらん取得 ---")
        with JalanClient() as client:
            client.login()
            jalan_csv = client.download_csv(year, month)
    if jalan_csv.exists():
        from src.jalan import JalanClient
        jalan_records = JalanClient.parse_csv(jalan_csv)
        agg.add_jalan(jalan_records)
        print(f"  じゃらん: {len(jalan_records)}件追加")
    else:
        print(f"  じゃらん: CSVなし ({jalan_csv})")

    # 3. MF経費API取得（--skip-fetch でもAPIは常に取得する）
    print("\n--- MF経費API取得 ---")
    mf = MFExpenseClient()
    mf.ensure_token()
    from_date = f"{year}-{month:02d}-01"
    if month == 12:
        to_date = f"{year + 1}-01-01"
    else:
        to_date = f"{year}-{month + 1:02d}-01"
    mf_records = []
    for label, office_id in MF_OFFICE_IDS.items():
        print(f"  {label}: 旅費交通費取得中...")
        records = mf.get_travel_expenses(office_id, from_date, to_date)
        mf_records.extend(records)
        print(f"  {label}: {len(records)}件")
    agg.add_mf_expense(mf_records)
    print(f"  MF経費合計: {len(mf_records)}件追加")

    # 4. 集計
    print("\n--- 集計結果 ---")
    summary = agg.summarize()
    unmatched = agg.get_unmatched()

    if unmatched:
        print(f"\n[WARNING] マッチしなかったレコード ({len(unmatched)}件):")
        for u in unmatched:
            print(f"  {u['source']}: {u['name']} → ¥{u['amount']:,} ({u['category']})")

    print(f"\n個人別集計 ({len(summary)}名):")
    total_all = 0
    for r in summary:
        print(
            f"  {r['name']:12s} ({r['department']:20s}): "
            f"新幹線¥{r['shinkansen']:>8,} / 宿泊¥{r['hotel']:>8,} / "
            f"在来線¥{r['train']:>8,} / その他¥{r['other']:>8,} / "
            f"合計¥{r['total']:>9,}"
        )
        total_all += r["total"]
    print(f"\n  総合計: ¥{total_all:,}")

    # 5. シート書き込み
    if args.dry_run:
        print("\n[dry-run] シート書き込みスキップ")
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print("\n--- スプレッドシート出力 ---")
        sheets.write_expense_summary(summary, year, month)
        print("完了!")


if __name__ == "__main__":
    main()
