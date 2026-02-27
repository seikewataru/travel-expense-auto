"""MF経費APIクライアント — OAuth 2.0 認証 + 経費明細取得"""

from __future__ import annotations

import json
import time
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlencode

import requests

from src.config import (
    MF_API_BASE,
    MF_AUTH_URL,
    MF_CLIENT_ID,
    MF_CLIENT_SECRET,
    MF_REDIRECT_URI,
    MF_TOKEN_FILE,
    MF_TOKEN_URL,
)


class MFExpenseClient:
    """MFクラウド経費 REST API クライアント"""

    def __init__(self):
        self.token_path = Path(MF_TOKEN_FILE)
        self.access_token: str | None = None
        self.refresh_token_value: str | None = None
        self.expires_at: datetime | None = None
        self._load_tokens()

    # ── OAuth 認証フロー ──

    def authorize(self) -> None:
        """ブラウザで認可URLを開き、ユーザーに認可コードを入力させる"""
        params = {
            "client_id": MF_CLIENT_ID,
            "redirect_uri": MF_REDIRECT_URI,
            "response_type": "code",
            "scope": "office_setting:write user_setting:write transaction:write report:write account:write public_resource:read",
        }
        auth_url = f"{MF_AUTH_URL}?{urlencode(params)}"
        print(f"ブラウザで認可URLを開きます:\n{auth_url}\n")
        webbrowser.open(auth_url)

        code = input("認可コードを貼り付けてください: ").strip()
        self.exchange_token(code)
        print("トークン保存完了")

    def exchange_token(self, code: str) -> None:
        """認可コードをアクセストークンに交換"""
        resp = requests.post(
            MF_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": MF_CLIENT_ID,
                "client_secret": MF_CLIENT_SECRET,
                "redirect_uri": MF_REDIRECT_URI,
            },
            timeout=30,
        )
        resp.raise_for_status()
        self._save_token_response(resp.json())

    def refresh_token(self) -> None:
        """リフレッシュトークンでアクセストークンを更新"""
        if not self.refresh_token_value:
            raise RuntimeError("リフレッシュトークンがありません。`auth`を再実行してください。")
        resp = requests.post(
            MF_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token_value,
                "client_id": MF_CLIENT_ID,
                "client_secret": MF_CLIENT_SECRET,
            },
            timeout=30,
        )
        resp.raise_for_status()
        self._save_token_response(resp.json())

    def ensure_token(self) -> None:
        """トークンが有効か確認し、期限切れならリフレッシュ"""
        if not self.access_token:
            raise RuntimeError("未認証です。`auth`コマンドを先に実行してください。")
        if self.expires_at and datetime.now() >= self.expires_at:
            print("トークン期限切れ — リフレッシュ中...")
            self.refresh_token()

    # ── API メソッド ──

    def get_offices(self) -> list[dict]:
        """事業者一覧を取得"""
        return self._get("/offices")["offices"]

    def get_ex_transactions(
        self, office_id: str, recognized_at_from: str, recognized_at_to: str
    ) -> list[dict]:
        """経費明細を取得（ページネーション対応）"""
        all_transactions: list[dict] = []
        page = 1
        while True:
            data = self._get(
                f"/offices/{office_id}/ex_transactions",
                params={
                    "page": page,
                    "query_object[recognized_at_from]": recognized_at_from,
                    "query_object[recognized_at_to]": recognized_at_to,
                },
            )
            transactions = data.get("ex_transactions", [])
            if not transactions:
                break
            all_transactions.extend(transactions)
            page += 1
        return all_transactions

    # ── 内部ヘルパー ──

    def _get(self, path: str, params: dict | None = None) -> dict:
        """認証付きGETリクエスト（レート制限対応）"""
        self.ensure_token()
        resp = requests.get(
            f"{MF_API_BASE}{path}",
            headers={"Authorization": f"Bearer {self.access_token}"},
            params=params,
            timeout=30,
        )
        # レート制限チェック
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "60"))
            print(f"レート制限 — {retry_after}秒待機...")
            time.sleep(retry_after)
            return self._get(path, params)
        resp.raise_for_status()
        return resp.json()

    def _save_token_response(self, data: dict) -> None:
        """トークンレスポンスを保存"""
        self.access_token = data["access_token"]
        self.refresh_token_value = data.get("refresh_token", self.refresh_token_value)
        expires_in = data.get("expires_in", 7200)
        self.expires_at = datetime.now() + timedelta(seconds=expires_in)
        token_data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token_value,
            "expires_at": self.expires_at.isoformat(),
        }
        self.token_path.write_text(json.dumps(token_data, indent=2))

    def _load_tokens(self) -> None:
        """保存済みトークンを読み込む"""
        if not self.token_path.exists():
            return
        try:
            data = json.loads(self.token_path.read_text())
            self.access_token = data.get("access_token")
            self.refresh_token_value = data.get("refresh_token")
            expires_at = data.get("expires_at")
            if expires_at:
                self.expires_at = datetime.fromisoformat(expires_at)
        except (json.JSONDecodeError, KeyError):
            pass
