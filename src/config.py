"""設定ロード — .env / st.secrets から認証情報を読み込む

ログイン失敗時はパスワード管理シート（EX_CARD_MASTER_SHEET_ID, gid=1874845869）から
最新の認証情報を再取得し、.envを更新する。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str = "") -> str:
    """環境変数を取得。Streamlit Cloud の st.secrets もフォールバック"""
    val = os.getenv(key, "")
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default

# MF経費 OAuth 2.0
MF_CLIENT_ID = _get("MF_CLIENT_ID")
MF_CLIENT_SECRET = _get("MF_CLIENT_SECRET")
MF_REDIRECT_URI = _get("MF_REDIRECT_URI", "urn:ietf:wg:oauth:2.0:oob")

# MF経費 API エンドポイント
MF_AUTH_URL = "https://expense.moneyforward.com/oauth/authorize"
MF_TOKEN_URL = "https://expense.moneyforward.com/oauth/token"
MF_API_BASE = "https://expense.moneyforward.com/api/external/v1"

# EXカード（エクスプレス予約）
EX_LOGIN_URL = _get("EX_LOGIN_URL", "https://shinkansen1.jr-central.co.jp/RSV_P/index.htm")
EX_CARD_NUMBER = _get("EX_CARD_NUMBER")
EX_PASSWORD = _get("EX_PASSWORD")
EX_OTP_EMAIL = _get("EX_OTP_EMAIL", "backoffice@stmn.co.jp")

# GAS OTP Webhook（設定されていればOTP自動取得、未設定なら手動入力）
GAS_OTP_WEBHOOK_URL = _get("GAS_OTP_WEBHOOK_URL")

# タイムズカー（法人管理者Web）
TIMES_LOGIN_URL = _get("TIMES_LOGIN_URL", "https://plus.timescar.jp/view/corporation/login.jsp")
TIMES_CONTRACT_ID = _get("TIMES_CONTRACT_ID")
TIMES_EMAIL = _get("TIMES_EMAIL")
TIMES_PASSWORD = _get("TIMES_PASSWORD")
TIMES_BROWSER_PROFILE = Path(__file__).resolve().parent.parent / "data" / "times_browser_profile"

# Racco（楽天トラベル法人管理）
RACCO_LOGIN_URL = _get("RACCO_LOGIN_URL", "https://manage.travel.rakuten.co.jp/alcemng/mng/corpLogin")
RACCO_CORP_ID = _get("RACCO_CORP_ID")
RACCO_USERNAME = _get("RACCO_USERNAME")
RACCO_PASSWORD = _get("RACCO_PASSWORD")
RACCO_BROWSER_PROFILE = Path(__file__).resolve().parent.parent / "data" / "racco_browser_profile"

# じゃらん（法人予約管理）
JALAN_LOGIN_URL = _get("JALAN_LOGIN_URL", "https://jcscl.jalan.net/jc/jcp9000/jcw9001Init.do")
JALAN_CORP_ID = _get("JALAN_CORP_ID")
JALAN_PASSWORD = _get("JALAN_PASSWORD")
JALAN_BROWSER_PROFILE = Path(__file__).resolve().parent.parent / "data" / "jalan_browser_profile"

# GCP サービスアカウント（ローカル用ファイルパス。Cloud では st.secrets を使用）
GCP_SERVICE_ACCOUNT_PATH = _get(
    "GCP_SERVICE_ACCOUNT_PATH",
    os.path.expanduser("~/.config/gcp/service-account.json"),
)

# データディレクトリ
EX_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EX_BROWSER_PROFILE = EX_DATA_DIR / "ex_browser_profile"

# トークン保存先
MF_TOKEN_FILE = ".mf_tokens.json"

# Google Sheets — 部署マスタ・出力先・EXカード管理・売上データ
DEPT_MASTER_SHEET_ID = "1gL6ShZUta6vM_TOcx0VB10_sjb_lZ7ZX6o9V-5LL3yc"
OUTPUT_SHEET_ID = "1nJXQ2Wt7ilpcg_yktIxlaZvvaMvRf87B8dIALoyXbaA"
EX_CARD_MASTER_SHEET_ID = "13fajhD-qWgerxdIJ31_6jfhajR1OJjm4XPamiFn-qjM"
EX_CARD_MASTER_GID = 111917276  # EXカード管理シート
SALES_SHEET_ID = "1Gho3cQ6U_cYg21QWx02prRCd962oNyIyZNrmE1qDka8"  # 売上実績シート
SALES_YOJITSU_GID = 1791092796  # 予実シート
RINGI_SHEET_ID = "16dKIWWL-m8XtZeIw1acrv8ZvdKoZLM-7kbl8Fxr7_YA"  # 稟議一覧シート
RINGI_SHEET_GID = 1556503880  # 稟議一覧タブ

# EXカード除外対象シート（福利厚生振替判定用）
EX_EXCLUSION_SHEET_ID = "1YWyDrpyHPq2MHoHeBHwQ2W-ouDg8Kqn7aW5vPLyMfzQ"
EX_EXCLUSION_GID = 2017086761  # 新幹線代_エクスプレス タブ

# パスワード管理シート（2箇所）
CREDENTIALS_SHEET_ID = EX_CARD_MASTER_SHEET_ID  # 同一スプシ
CREDENTIALS_GID = 1874845869  # 「スタメン」タブ
CREDENTIALS_SHEET_ID_2 = "1lvHOGEaSBZ0qMOSCc3i0B79K1_TXce300R8FQ0mBWTI"  # 別管理シート
CREDENTIALS_GID_2 = 468893395

# サービス名 → (Account検索キーワード, .envキーマッピング)
CREDENTIALS_MAP = {
    "racco": {
        "keyword": "楽天 Racco",
        "env_keys": {
            "RACCO_CORP_ID": "corp_id",     # Password列から抽出
            "RACCO_USERNAME": "username",    # Password列から抽出
            "RACCO_PASSWORD": "password",    # Password列から抽出
        },
    },
    "jalan": {
        "keyword": "じゃらん",
        "match_keywords": ["じゃらん法人", "じゃらん：法人WEB"],  # 複数シートで名称が異なる
        "env_keys": {
            "JALAN_CORP_ID": "login_name",
            "JALAN_PASSWORD": "password",
        },
    },
    "times": {
        "keyword": "タイムズ24",
        "env_keys": {
            "TIMES_CONTRACT_ID": "login_name",
            "TIMES_PASSWORD": "password",
        },
    },
}

# MF経費 事業者ID
MF_OFFICE_IDS = {
    "stamen": "3eX7QWyXMWfqh1UffaF7Ng",
    "stage": "LzIfBpr3fz6OZfx5RZhdRw",
}


def refresh_credentials(service: str) -> dict[str, str]:
    """パスワード管理シートから最新の認証情報を取得し、.envを更新する

    Args:
        service: "racco", "jalan", "times"

    Returns:
        {"env_key": "new_value", ...}
    """
    import gspread
    import re

    svc = CREDENTIALS_MAP.get(service)
    if not svc:
        raise ValueError(f"未知のサービス: {service}")

    gc = gspread.service_account(filename=GCP_SERVICE_ACCOUNT_PATH)

    # シート1 → シート2 の順に検索
    sheets_to_search = [
        (CREDENTIALS_SHEET_ID, CREDENTIALS_GID, "シート1"),
        (CREDENTIALS_SHEET_ID_2, CREDENTIALS_GID_2, "シート2"),
    ]

    target_row = None
    for sheet_id, gid, label in sheets_to_search:
        try:
            sh = gc.open_by_key(sheet_id)
            ws = sh.get_worksheet_by_id(gid)
            all_values = ws.get_all_values()
            for row in all_values[1:]:
                account = row[1].strip() if len(row) > 1 else ""
                if svc["keyword"] in account or any(kw in account for kw in svc.get("match_keywords", [])):
                    target_row = row
                    print(f"[Config] {service} 認証情報を{label}で発見: {account}")
                    break
            if target_row:
                break
        except Exception as e:
            print(f"[Config] {label}の読み込みエラー: {e}")

    if not target_row:
        raise RuntimeError(f"パスワードシートに '{svc['keyword']}' が見つかりません")

    login_name = target_row[2].strip() if len(target_row) > 2 else ""
    password_raw = target_row[3].strip() if len(target_row) > 3 else ""

    # Racco は Password列に複数行（認証コード + パスワード）が入っている
    result = {}
    if service == "racco":
        # 法人ID = login_name, 認証コード・パスワードはPassword列から抽出
        result["RACCO_CORP_ID"] = login_name
        # "上級管理者認証コード：xxx\n管理者用パスワード：yyy"
        auth_match = re.search(r"認証コード[：:]\s*(\S+)", password_raw)
        pass_match = re.search(r"パスワード[：:]\s*(\S+)", password_raw)
        result["RACCO_USERNAME"] = auth_match.group(1) if auth_match else ""
        result["RACCO_PASSWORD"] = pass_match.group(1) if pass_match else ""
    else:
        # じゃらん/タイムズ: login_name = Login Name, password = Password
        for env_key, field in svc["env_keys"].items():
            if field == "login_name":
                result[env_key] = login_name
            elif field == "password":
                result[env_key] = password_raw

    # .env ファイルを更新
    env_path = Path(__file__).resolve().parent.parent / ".env"
    env_content = env_path.read_text()
    for env_key, new_val in result.items():
        # 既存行を置換
        pattern = re.compile(rf'^{env_key}=.*$', re.MULTILINE)
        if pattern.search(env_content):
            env_content = pattern.sub(f'{env_key}={new_val}', env_content)
        # グローバル変数も更新
        globals()[env_key] = new_val
        os.environ[env_key] = new_val
    env_path.write_text(env_content)

    print(f"[Config] {service} 認証情報を更新: {', '.join(result.keys())}")
    return result
