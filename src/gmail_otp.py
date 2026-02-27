"""OTP取得 — ターミナルで手動入力（Workspace管理者権限なしでも動作）"""


def get_otp() -> str:
    """OTPをターミナルから手動入力で取得する。

    backoffice@stmn.co.jp に届くワンタイムパスワードを
    ユーザーがメールで確認し、ターミナルに入力する。

    Returns:
        OTP文字列
    """
    print()
    print("=" * 50)
    print("[OTP] backoffice@stmn.co.jp にワンタイムパスワードが届きます")
    print("[OTP] メールを確認して、以下に入力してください")
    print("=" * 50)
    otp = input("[OTP] ワンタイムパスワード: ").strip()
    print(f"[OTP] 入力確認: {otp}")
    return otp
