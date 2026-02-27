"""CLIエントリポイント — auth / fetch / ex-fetch / times-fetch サブコマンド"""

import argparse
import json
import sys

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

    args = parser.parse_args()
    if args.command == "auth":
        cmd_auth(args)
    elif args.command == "fetch":
        cmd_fetch(args)
    elif args.command == "ex-fetch":
        cmd_ex_fetch(args)
    elif args.command == "times-fetch":
        cmd_times_fetch(args)


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


if __name__ == "__main__":
    main()
