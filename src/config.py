"""設定ロード — .envから認証情報を読み込む"""

import os
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

# GCP サービスアカウント
GCP_SERVICE_ACCOUNT_PATH = os.getenv(
    "GCP_SERVICE_ACCOUNT_PATH",
    os.path.expanduser("~/.config/gcp/service-account.json"),
)

# トークン保存先
MF_TOKEN_FILE = ".mf_tokens.json"
