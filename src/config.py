"""設定ロード — .envから認証情報を読み込む"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# MF経費 OAuth 2.0
MF_CLIENT_ID = os.getenv("MF_CLIENT_ID", "")
MF_CLIENT_SECRET = os.getenv("MF_CLIENT_SECRET", "")
MF_REDIRECT_URI = os.getenv("MF_REDIRECT_URI", "urn:ietf:wg:oauth:2.0:oob")

# MF経費 API エンドポイント
MF_AUTH_URL = "https://expense.moneyforward.com/oauth/authorize"
MF_TOKEN_URL = "https://expense.moneyforward.com/oauth/token"
MF_API_BASE = "https://expense.moneyforward.com/api/external/v1"

# EXカード（エクスプレス予約）
EX_LOGIN_URL = os.getenv("EX_LOGIN_URL", "https://shinkansen1.jr-central.co.jp/RSV_P/index.htm")
EX_CARD_NUMBER = os.getenv("EX_CARD_NUMBER", "")
EX_PASSWORD = os.getenv("EX_PASSWORD", "")
EX_OTP_EMAIL = os.getenv("EX_OTP_EMAIL", "backoffice@stmn.co.jp")

# タイムズカー（法人管理者Web）
TIMES_LOGIN_URL = os.getenv("TIMES_LOGIN_URL", "https://plus.timescar.jp/view/corporation/login.jsp")
TIMES_CONTRACT_ID = os.getenv("TIMES_CONTRACT_ID", "")
TIMES_EMAIL = os.getenv("TIMES_EMAIL", "")
TIMES_PASSWORD = os.getenv("TIMES_PASSWORD", "")
TIMES_BROWSER_PROFILE = Path(__file__).resolve().parent.parent / "data" / "times_browser_profile"

# Racco（楽天トラベル法人管理）
RACCO_LOGIN_URL = os.getenv("RACCO_LOGIN_URL", "https://manage.travel.rakuten.co.jp/alcemng/mng/corpLogin")
RACCO_CORP_ID = os.getenv("RACCO_CORP_ID", "")
RACCO_USERNAME = os.getenv("RACCO_USERNAME", "")
RACCO_PASSWORD = os.getenv("RACCO_PASSWORD", "")
RACCO_BROWSER_PROFILE = Path(__file__).resolve().parent.parent / "data" / "racco_browser_profile"

# じゃらん（法人予約管理）
JALAN_LOGIN_URL = os.getenv("JALAN_LOGIN_URL", "https://jcscl.jalan.net/jc/jcp9000/jcw9001Init.do")
JALAN_CORP_ID = os.getenv("JALAN_CORP_ID", "")
JALAN_PASSWORD = os.getenv("JALAN_PASSWORD", "")
JALAN_BROWSER_PROFILE = Path(__file__).resolve().parent.parent / "data" / "jalan_browser_profile"

# GCP サービスアカウント
GCP_SERVICE_ACCOUNT_PATH = os.getenv(
    "GCP_SERVICE_ACCOUNT_PATH",
    os.path.expanduser("~/.config/gcp/service-account.json"),
)

# データディレクトリ
EX_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EX_BROWSER_PROFILE = EX_DATA_DIR / "ex_browser_profile"

# トークン保存先
MF_TOKEN_FILE = ".mf_tokens.json"
