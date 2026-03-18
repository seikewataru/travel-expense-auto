"""OTP取得 — GAS Webhook自動取得 + 手動入力フォールバック"""

import os
import time

import requests


def get_otp(max_wait: int = 120, poll_interval: int = 5) -> str:
    """OTPを自動取得する。GAS Webhookが設定されていればポーリング、なければ手動入力。

    Args:
        max_wait: 最大待機時間（秒）
        poll_interval: ポーリング間隔（秒）

    Returns:
        OTP文字列
    """
    webhook_url = os.getenv("GAS_OTP_WEBHOOK_URL", "")

    if webhook_url:
        return _get_otp_from_webhook(webhook_url, max_wait, poll_interval)
    else:
        return _get_otp_manual()


def _get_otp_from_webhook(webhook_url: str, max_wait: int, poll_interval: int) -> str:
    """GAS WebhookからOTPを自動取得（ポーリング）"""
    print(f"[OTP] GAS Webhookでポーリング開始（最大{max_wait}秒）")
    elapsed = 0

    while elapsed < max_wait:
        try:
            resp = requests.get(webhook_url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "ok" and data.get("otp"):
                    otp = data["otp"]
                    print(f"[OTP] 自動取得成功: {otp}（受信: {data.get('received_at', '不明')}）")
                    return otp
                elif data.get("status") == "expired":
                    print(f"[OTP] メールが古すぎます。新しいOTPを待機中...")
                else:
                    print(f"[OTP] 待機中... ({elapsed}s / {max_wait}s)")
            else:
                print(f"[OTP] Webhook応答エラー: {resp.status_code}")
        except requests.RequestException as e:
            print(f"[OTP] Webhook接続エラー: {e}")

        time.sleep(poll_interval)
        elapsed += poll_interval

    print("[OTP] タイムアウト。手動入力に切り替えます。")
    return _get_otp_manual()


def _get_otp_manual() -> str:
    """OTPをターミナルから手動入力で取得する（フォールバック）"""
    print()
    print("=" * 50)
    print("[OTP] backoffice@stmn.co.jp にワンタイムパスワードが届きます")
    print("[OTP] メールを確認して、以下に入力してください")
    print("=" * 50)
    otp = input("[OTP] ワンタイムパスワード: ").strip()
    print(f"[OTP] 入力確認: {otp}")
    return otp
