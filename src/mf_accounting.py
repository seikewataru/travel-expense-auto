"""MF会計Plus API クライアント（OAuth 2.0 認可コードフロー）

初回実行時にブラウザで認証 → トークンをローカルに保存。
以後はリフレッシュトークンで自動更新。
"""

from __future__ import annotations

import json
import os
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

# === 設定 ===
CLIENT_ID = os.getenv("MF_ACCOUNTING_CLIENT_ID")
CLIENT_SECRET = os.getenv("MF_ACCOUNTING_CLIENT_SECRET")
REDIRECT_URI = "https://localhost:8080/callback"
TOKEN_FILE = Path(__file__).parent.parent / "data" / "mf_accounting_token.json"

AUTH_URL = "https://api.biz.moneyforward.com/authorize"
TOKEN_URL = "https://api.biz.moneyforward.com/token"
API_BASE = "https://api-enterprise-accounting.moneyforward.com/api/v3"

SCOPES = "mfc/enterprise-accounting/journal.read mfc/enterprise-accounting/office.read mfc/enterprise-accounting/report.read mfc/enterprise-accounting/master.read mfc/admin/tenant.read"


# === OAuth 認証 ===
class _CallbackHandler(BaseHTTPRequestHandler):
    """認可コード受信用の一時HTTPサーバー"""
    auth_code: str | None = None

    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        code = qs.get("code", [None])[0]
        if code:
            _CallbackHandler.auth_code = code
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("認証成功！このタブを閉じてください。".encode())
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Error: no code received")

    def log_message(self, format, *args):
        pass  # ログ抑制


def _get_auth_code() -> str:
    """ブラウザで認可画面を開き、コールバックで認可コードを受け取る"""
    import ssl
    import tempfile

    # 自己署名証明書を生成（https://localhost用）
    cert_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
    key_file = tempfile.NamedTemporaryFile(suffix=".pem", delete=False)
    cert_file.close()
    key_file.close()

    os.system(
        f'openssl req -x509 -newkey rsa:2048 -keyout {key_file.name} '
        f'-out {cert_file.name} -days 1 -nodes -subj "/CN=localhost" 2>/dev/null'
    )

    server = HTTPServer(("localhost", 8080), _CallbackHandler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert_file.name, key_file.name)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)

    params = urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": os.urandom(16).hex(),
    })
    url = f"{AUTH_URL}?{params}"
    print(f"ブラウザで認証画面を開きます...")
    webbrowser.open(url)

    # コールバック待機（最大120秒）
    server.timeout = 120
    while _CallbackHandler.auth_code is None:
        server.handle_request()

    server.server_close()
    os.unlink(cert_file.name)
    os.unlink(key_file.name)

    return _CallbackHandler.auth_code


def _exchange_code(code: str) -> dict:
    """認可コード → アクセストークン交換"""
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }, auth=(CLIENT_ID, CLIENT_SECRET))
    resp.raise_for_status()
    return resp.json()


def _refresh_token(refresh_token: str) -> dict:
    """リフレッシュトークンでアクセストークン更新"""
    resp = requests.post(TOKEN_URL, data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }, auth=(CLIENT_ID, CLIENT_SECRET))
    resp.raise_for_status()
    return resp.json()


def _save_token(token_data: dict) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    token_data["saved_at"] = time.time()
    TOKEN_FILE.write_text(json.dumps(token_data, indent=2))


def _load_token() -> dict | None:
    if TOKEN_FILE.exists():
        return json.loads(TOKEN_FILE.read_text())
    return None


def get_access_token() -> str:
    """有効なアクセストークンを返す（必要に応じて認証・リフレッシュ）"""
    token = _load_token()

    if token:
        # トークンの有効期限チェック
        expires_in = token.get("expires_in", 3600)
        saved_at = token.get("saved_at", 0)
        if time.time() < saved_at + expires_in - 60:
            return token["access_token"]

        # リフレッシュ
        if "refresh_token" in token:
            try:
                new_token = _refresh_token(token["refresh_token"])
                _save_token(new_token)
                return new_token["access_token"]
            except requests.HTTPError:
                print("リフレッシュトークン期限切れ。再認証します。")

    # 初回認証
    code = _get_auth_code()
    token_data = _exchange_code(code)
    _save_token(token_data)
    return token_data["access_token"]


# === API呼び出し ===
def api_get(path: str, params: dict | None = None) -> dict:
    """MF会計Plus APIにGETリクエスト"""
    token = get_access_token()
    resp = requests.get(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
    )
    resp.raise_for_status()
    return resp.json()


def get_journals(year: int, month: int) -> list[dict]:
    """指定月の仕訳一覧を取得"""
    # 月初〜月末
    from datetime import date
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month:02d}-{last_day}"

    return api_get("/journals", params={
        "start_date": start,
        "end_date": end,
    })


def get_all_journals(year: int, month: int) -> list[dict]:
    """指定月の仕訳を全件取得（ページネーション対応）"""
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month:02d}-{last_day}"

    all_journals = []
    cursor = None
    while True:
        params = {"start_date": start, "end_date": end}
        if cursor:
            params["cursor"] = cursor
        data = api_get("/journals", params=params)
        all_journals.extend(data.get("journals", []))
        cursor = data.get("next_cursor")
        if not cursor:
            break
    return all_journals


# S05_旅費交通費の勘定科目・補助科目ID
S05_ACCOUNT_ID = 226862
S05_SUB_IDS = {
    "S0501_通勤手当": 641747,
    "S0502_交通費（公共交通機関）": 647741,
    "S0503_交通費（新幹線）": 647742,
    "S0504_交通費（タクシー）": 647743,
    "S0505_交通費（カーシェア）": 647744,
    "S0506_交通費（航空機）": 647745,
    "S0507_宿泊費": 647746,
}


def get_non_expense_entries(year: int, month: int, sub_account_id: int) -> list[dict]:
    """MF経費連携以外の仕訳明細を取得する

    MF経費から自動連携された仕訳（creator=システムユーザー）を除外し、
    UPSIDERカード等の手動計上分のみを返す。

    Returns:
        [{"date": "2026-01-14", "value": 105860, "remark": "...", "creator": "..."}, ...]
    """
    journals = get_all_journals(year, month)
    entries = []
    for j in journals:
        creator = j.get("creator", "")
        if creator == "システムユーザー":
            continue
        for b in j.get("branches", []):
            d = b.get("debitor", {})
            if d.get("account_id") == S05_ACCOUNT_ID and d.get("sub_account_id") == sub_account_id:
                entries.append({
                    "date": j["transaction_date"],
                    "value": d.get("value", 0),
                    "remark": b.get("remark", ""),
                    "creator": creator,
                })
    return entries


def get_office_info() -> dict:
    """事業者情報を取得（認可サーバーAPI経由）"""
    token = get_access_token()
    resp = requests.get(
        "https://api.biz.moneyforward.com/v2/tenant",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()


# === テスト実行 ===
if __name__ == "__main__":
    print("MF会計Plus API 接続テスト")
    print("=" * 40)

    # 事業者情報取得
    try:
        info = get_office_info()
        print(f"事業者情報: {json.dumps(info, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"エラー: {e}")
        # レスポンスボディを表示
        import traceback
        traceback.print_exc()
