"""タイムズカー Playwrightスクレイパー — 法人管理者Webから利用明細CSVを自動取得"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, BrowserContext

from src.config import (
    TIMES_LOGIN_URL,
    TIMES_CONTRACT_ID,
    TIMES_EMAIL,
    TIMES_PASSWORD,
    TIMES_BROWSER_PROFILE,
    EX_DATA_DIR,
)


class TimesCarClient:
    """タイムズカー法人管理者Webスクレイパー"""

    def __init__(self):
        self._playwright = None
        self._browser: BrowserContext | None = None
        self._page: Page | None = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.close()

    def start(self) -> None:
        """Playwright起動（headful + persistent context）"""
        TIMES_BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)
        EX_DATA_DIR.mkdir(parents=True, exist_ok=True)

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(TIMES_BROWSER_PROFILE),
            headless=False,
            accept_downloads=True,
            locale="ja-JP",
        )
        self._page = self._browser.new_page()

    def close(self) -> None:
        """ブラウザ終了"""
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def login(self) -> None:
        """タイムズビジネスサービス法人管理者Webにログイン"""
        page = self._page
        print("[Times] ログインページへ遷移...")
        page.goto(TIMES_LOGIN_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # ログイン済みかチェック（マイページトップが表示されていればスキップ）
        body_text = page.inner_text("body")
        if "マイページトップ" in body_text and "ログイン" not in page.url:
            print("[Times] ログイン済み（セッション有効）")
            return

        # テキスト入力フィールドを順番で特定（契約先ID, メールアドレス）
        text_inputs = page.locator("input[type='text']")
        text_inputs.nth(0).fill(TIMES_CONTRACT_ID)
        print("[Times] 契約先ID入力完了")

        text_inputs.nth(1).fill(TIMES_EMAIL)
        print("[Times] メールアドレス入力完了")

        # パスワード
        page.locator("input[type='password']").first.fill(TIMES_PASSWORD)
        print("[Times] パスワード入力完了")

        # ログインボタン
        login_btn = page.locator("input[type='submit'], button:has-text('ログイン'), input[value*='ログイン']")
        login_btn.first.click()
        page.wait_for_timeout(3000)

        # ログイン失敗チェック
        body_text = page.locator("body").text_content() or ""
        if "ログインできません" in body_text or "認証に失敗" in body_text or "エラー" in body_text and "login" in page.url.lower():
            print("[Times] ログイン失敗 — パスワードシートから最新認証情報を取得中...")
            from src.config import refresh_credentials
            creds = refresh_credentials("times")
            page.goto(TIMES_LOGIN_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            text_inputs = page.locator("input[type='text']")
            text_inputs.nth(0).fill(creds.get("TIMES_CONTRACT_ID", ""))
            text_inputs.nth(1).fill(TIMES_EMAIL)
            page.locator("input[type='password']").first.fill(creds.get("TIMES_PASSWORD", ""))
            login_btn = page.locator("input[type='submit'], button:has-text('ログイン'), input[value*='ログイン']")
            login_btn.first.click()
            page.wait_for_timeout(3000)
            body_text = page.locator("body").text_content() or ""
            if "ログインできません" in body_text or "認証に失敗" in body_text:
                raise RuntimeError("[Times] パスワードシート更新後もログイン失敗。手動確認が必要です。")
            print("[Times] リトライ成功")

        # ログイン後のモーダルポップアップを閉じる
        self._dismiss_popups(page)

        print("[Times] ログイン完了")

    def _dismiss_popups(self, page: Page) -> None:
        """ログイン後に表示されるお知らせモーダルを閉じる"""
        for _ in range(5):  # 複数のポップアップが連続する場合
            dismissed = False
            # announce_box（お知らせオーバーレイ）を先に閉じる
            announce = page.locator("#announce_box")
            if announce.count() > 0 and announce.first.is_visible():
                close_btn = announce.locator("a, button, input[type='button']")
                if close_btn.count() > 0:
                    close_btn.first.click(force=True)
                    print("[Times] お知らせボックス閉じ")
                    page.wait_for_timeout(1500)
                    dismissed = True
                    continue
                # 閉じるボタンがなければJS で非表示にする
                page.evaluate("document.getElementById('announce_box').style.display='none'")
                print("[Times] お知らせボックス非表示（JS）")
                page.wait_for_timeout(500)
                dismissed = True
                continue

            for label in ["同意する", "閉じる", "OK", "確認"]:
                btn = page.locator(f"button:has-text('{label}'), a:has-text('{label}'), input[value*='{label}']")
                if btn.count() > 0 and btn.first.is_visible():
                    try:
                        btn.first.click(timeout=5000)
                    except Exception:
                        btn.first.click(force=True)
                    print(f"[Times] ポップアップ閉じ: {label}")
                    page.wait_for_timeout(1500)
                    dismissed = True
                    break
            if not dismissed:
                break

    def download_csv(self, year: int, month: int) -> Path:
        """利用明細CSVをダウンロードする

        Args:
            year: 対象年（例: 2026）
            month: 対象月（例: 1）

        Returns:
            ダウンロードしたCSVファイルのパス
        """
        page = self._page
        print(f"[Times] 利用明細ダウンロード — {year}年{month}月")

        # ご利用履歴ページへ遷移
        self._navigate_to_usage_history(page)

        # 対象月のCSVダウンロードボタンをクリック
        csv_path = self._download_month_csv(page, year, month)

        return csv_path

    def _navigate_to_usage_history(self, page: Page) -> None:
        """ご利用履歴（タイムズカー）ページへ遷移"""
        body_text = page.inner_text("body")

        # 既にご利用履歴ページにいるかチェック
        if "ご利用履歴・明細" in body_text:
            print("[Times] 既にご利用履歴ページにいます")
            return

        # まだ残っているオーバーレイ・ポップアップを強制非表示
        page.evaluate("""
            document.querySelectorAll(
                '#CONTAINER > h3, #announce_box, .modal, .overlay, ' +
                '[class*="popup"], [class*="Popup"], [id*="popup"], [id*="Popup"], ' +
                '[class*="dialog"], [class*="Dialog"], ' +
                '.fancybox-overlay, .fancybox-wrap, ' +
                '[style*="z-index"][style*="position: fixed"], ' +
                '[style*="z-index"][style*="position: absolute"]'
            ).forEach(el => {
                el.style.display = 'none';
                el.style.visibility = 'hidden';
            });
        """)
        page.wait_for_timeout(500)

        # ナビメニューから「ご利用履歴」をホバーしてサブメニュー展開
        usage_link = page.locator("a:has-text('ご利用履歴')")
        if usage_link.count() > 0:
            usage_link.first.hover()
            page.wait_for_timeout(1000)
            # ホバーでサブメニューが出ない場合はクリック
            times_car_link = page.locator("a:has-text('タイムズカー'):not(:has-text('レンタル'))")
            if times_car_link.count() == 0 or not times_car_link.first.is_visible():
                usage_link.first.click(force=True)
                page.wait_for_timeout(2000)

        # サブメニューから「タイムズカー」をクリック
        times_car_link = page.locator("a:has-text('タイムズカー'):not(:has-text('レンタル'))")
        if times_car_link.count() > 0:
            # サブメニュー内のリンクを可視化して直接遷移
            target_href = times_car_link.first.get_attribute("href")
            if target_href:
                print(f"[Times] タイムズカーリンクURL: {target_href}")
                page.goto(target_href if target_href.startswith("http") else f"https://plus.timescar.jp{target_href}")
            else:
                times_car_link.first.click(force=True)
            page.wait_for_timeout(3000)
            print("[Times] タイムズカー利用履歴ページへ遷移完了")
        else:
            # フォールバック: 直接URLで遷移
            print("[Times] サブメニューが見つからないため直接URL遷移")
            page.goto("https://share.timescar.jp/view/corporation/use/list.jsp")
            page.wait_for_timeout(3000)
            print("[Times] タイムズカー利用履歴ページへ遷移完了")

    def _download_month_csv(self, page: Page, year: int, month: int) -> Path:
        """対象月のCSVダウンロードボタンをクリック"""
        target_month = f"{year}年{month:02d}月"

        # doOutPutCsvボタンの親行から対象月を特定
        csv_buttons = page.locator("input[name*='doOutPutCsv']")
        btn_count = csv_buttons.count()
        print(f"[Times] CSVボタン数: {btn_count}")

        for i in range(btn_count):
            # ボタンの親行（tr）のテキストを取得
            row = csv_buttons.nth(i).locator("xpath=ancestor::tr")
            row_text = row.inner_text()
            if target_month in row_text:
                print(f"[Times] {target_month}のCSVボタンを検出 (index={i})")

                with page.expect_download(timeout=30000) as download_info:
                    csv_buttons.nth(i).click()

                download = download_info.value
                save_path = EX_DATA_DIR / f"times_{year}_{month:02d}.csv"
                download.save_as(str(save_path))
                print(f"[Times] CSVダウンロード完了: {save_path}")
                return save_path

        raise RuntimeError(f"{target_month}のCSVボタンが見つかりません")

    @staticmethod
    def parse_csv(filepath: Path) -> list[dict]:
        """ダウンロードしたCSVをパースしてdict listで返す"""
        # エンコーディング判定
        for encoding in ("shift_jis", "cp932", "utf-8"):
            try:
                text = filepath.read_text(encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError(f"CSVのエンコーディングを判定できません: {filepath}")

        lines = text.splitlines()

        # ヘッダー行を探す（「会員」「利用」「金額」等のキーワードを含む行）
        header_idx = None
        for i, line in enumerate(lines):
            if "会員" in line or "利用日" in line or "カード番号" in line:
                header_idx = i
                break

        if header_idx is None:
            # ヘッダーが見つからなければ1行目をヘッダーとして扱う
            header_idx = 0

        csv_text = "\n".join(lines[header_idx:])
        reader = csv.DictReader(io.StringIO(csv_text))

        records = []
        for row in reader:
            if not any(v.strip() for v in row.values() if v):
                continue
            records.append(dict(row))

        print(f"[Times] CSV解析完了: {len(records)}件")
        return records
