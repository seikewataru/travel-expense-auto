/**
 * EXカード OTP自動取得 — GAS Web App
 *
 * デプロイ手順:
 * 1. Google Apps Script (script.google.com) で新規プロジェクト作成
 * 2. このコードを貼り付け
 * 3. デプロイ → ウェブアプリ → アクセス: 全員 → デプロイ
 * 4. URLをコピーして .env の GAS_OTP_WEBHOOK_URL に設定
 *
 * 転送設定:
 * - backoffice@stmn.co.jp → このGASを実行するGmailアカウントに転送
 * - または同一Workspaceアカウントで実行（転送不要）
 */

function doGet(e) {
  var maxAgeMinutes = 5; // 直近5分以内のメールを検索
  var now = new Date();
  var cutoff = new Date(now.getTime() - maxAgeMinutes * 60 * 1000);

  // EXカード（JR東海）からのOTPメールを検索
  var query = 'subject:(ワンタイムパスワード OR "One-Time Password" OR "認証コード") newer_than:1h';
  var threads = GmailApp.search(query, 0, 5);

  if (threads.length === 0) {
    return ContentService.createTextOutput(
      JSON.stringify({ status: "not_found", message: "OTPメールが見つかりません", otp: null })
    ).setMimeType(ContentService.MimeType.JSON);
  }

  // 最新のメールからOTPを抽出
  var latestThread = threads[0];
  var messages = latestThread.getMessages();
  var latestMessage = messages[messages.length - 1];
  var messageDate = latestMessage.getDate();

  // 古すぎるメールは無視
  if (messageDate < cutoff) {
    return ContentService.createTextOutput(
      JSON.stringify({ status: "expired", message: "OTPメールが古すぎます（5分以上前）", otp: null })
    ).setMimeType(ContentService.MimeType.JSON);
  }

  var body = latestMessage.getPlainBody();

  // OTPを抽出（6桁 or 8桁の数字）
  var otpMatch = body.match(/(\d{6,8})/);
  if (!otpMatch) {
    return ContentService.createTextOutput(
      JSON.stringify({ status: "parse_error", message: "OTPコードを抽出できません", body: body.substring(0, 200), otp: null })
    ).setMimeType(ContentService.MimeType.JSON);
  }

  var otp = otpMatch[1];

  return ContentService.createTextOutput(
    JSON.stringify({
      status: "ok",
      otp: otp,
      received_at: messageDate.toISOString(),
      subject: latestMessage.getSubject()
    })
  ).setMimeType(ContentService.MimeType.JSON);
}
