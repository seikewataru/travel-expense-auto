"""Racco（楽天トラベル法人）Playwrightスクレイパー — 宿泊実績CSVを自動取得

フロー:
  1. ログイン（法人ID + 上級管理者認証コード + パスワード）
  2. トップ画面の「■予約実績確認」セクションで:
     - 期間セレクト（From年/月/日 ～ To年/月/日）を設定
     - 「チェックアウト日を対象とする」ラジオ選択
     - 「全ての予約を表示する」ラジオ選択
     - 検索ボタンをクリック
  3. 結果ページで「ヘッダ行を表示する」にチェック → CSVダウンロード
"""

from __future__ import annotations

import calendar
import csv
import io
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, BrowserContext

from src.config import (
    RACCO_LOGIN_URL,
    RACCO_CORP_ID,
    RACCO_USERNAME,
    RACCO_PASSWORD,
    RACCO_BROWSER_PROFILE,
    EX_DATA_DIR,
)


class RaccoClient:
    """Racco（楽天トラベル法人管理）スクレイパー"""

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
        RACCO_BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)
        EX_DATA_DIR.mkdir(parents=True, exist_ok=True)

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(RACCO_BROWSER_PROFILE),
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
        """Racco法人管理画面にログイン"""
        page = self._page
        print("[Racco] ログインページへ遷移...")
        page.goto(RACCO_LOGIN_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # ログイン済みチェック
        if "Login" not in page.url and "login" not in page.url and page.locator("input[type='text']").count() == 0:
            print("[Racco] ログイン済み（セッション有効）")
            return

        # 3つの入力フィールド: 法人ID, ID/上級管理者認証コード, パスワード
        text_inputs = page.locator("input[type='text']")
        pw_inputs = page.locator("input[type='password']")

        if pw_inputs.count() > 0:
            text_inputs.nth(0).fill(RACCO_CORP_ID)
            print("[Racco] 法人ID入力完了")
            text_inputs.nth(1).fill(RACCO_USERNAME)
            print("[Racco] ID/上級管理者認証コード入力完了")
            pw_inputs.first.fill(RACCO_PASSWORD)
            print("[Racco] パスワード入力完了")
        else:
            text_inputs.nth(0).fill(RACCO_CORP_ID)
            print("[Racco] 法人ID入力完了")
            text_inputs.nth(1).fill(RACCO_USERNAME)
            print("[Racco] ID/上級管理者認証コード入力完了")
            text_inputs.nth(2).fill(RACCO_PASSWORD)
            print("[Racco] パスワード入力完了")

        login_btn = page.locator(
            "input[type='submit'], button:has-text('ログイン'), input[value*='ログイン']"
        )
        login_btn.first.click()
        page.wait_for_timeout(3000)

        # ログイン失敗チェック → パスワードシートから再取得してリトライ
        # ※トップページのお知らせに「ログインできません」が含まれるためURLで判定
        login_failed = "login" in page.url.lower().rsplit("/", 1)[-1]
        if login_failed:
            print("[Racco] ログイン失敗 — パスワードシートから最新認証情報を取得中...")
            from src.config import refresh_credentials
            creds = refresh_credentials("racco")
            # リトライ
            page.goto(RACCO_LOGIN_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            text_inputs = page.locator("input[type='text']")
            pw_inputs = page.locator("input[type='password']")
            text_inputs.nth(0).fill(creds.get("RACCO_CORP_ID", ""))
            text_inputs.nth(1).fill(creds.get("RACCO_USERNAME", ""))
            if pw_inputs.count() > 0:
                pw_inputs.first.fill(creds.get("RACCO_PASSWORD", ""))
            else:
                text_inputs.nth(2).fill(creds.get("RACCO_PASSWORD", ""))
            login_btn = page.locator(
                "input[type='submit'], button:has-text('ログイン'), input[value*='ログイン']"
            )
            login_btn.first.click()
            page.wait_for_timeout(3000)
            if "login" in page.url.lower().rsplit("/", 1)[-1]:
                raise RuntimeError("[Racco] パスワードシート更新後もログイン失敗。手動確認が必要です。")
            print("[Racco] リトライ成功")
        else:
            print("[Racco] ログイン完了")

    def download_csv(self, year: int, month: int) -> Path:
        """宿泊実績CSVをダウンロードする

        Args:
            year: 対象年（例: 2026）
            month: 対象月（例: 1）

        Returns:
            ダウンロードしたCSVファイルのパス
        """
        page = self._page
        print(f"[Racco] 宿泊実績ダウンロード — {year}年{month}月")

        # STEP 1: トップページの「■予約実績確認」セクションで期間・条件を設定
        self._set_search_conditions(page, year, month)

        # STEP 2: 検索ボタンをクリック
        search_btn = page.locator("input[value='検　索'], input[value='検索'], input[value*='検'], button:has-text('検索')")
        if search_btn.count() > 0:
            search_btn.first.click()
            print("[Racco] 検索ボタンをクリック")
            page.wait_for_timeout(5000)
        else:
            raise RuntimeError("検索ボタンが見つかりません")

        # STEP 3: 結果ページでCSVダウンロード
        csv_path = self._do_csv_download(page, year, month)
        return csv_path

    def _set_search_conditions(self, page: Page, year: int, month: int) -> None:
        """予約実績確認セクションの検索条件を設定"""
        last_day = calendar.monthrange(year, month)[1]
        year_str = str(year)
        month_str = str(month)

        # 予約実績確認セクションの最初の6つのセレクトのみ操作
        # name: tripStartYear, tripStartMonth, tripStartDay, tripEndYear, tripEndMonth, tripEndDay
        # 同名セレクトが他タブにもあるため、.first で最初の可視要素を取得
        targets = [
            ("tripStartYear", year_str),
            ("tripStartMonth", month_str),
            ("tripStartDay", "1"),
            ("tripEndYear", year_str),
            ("tripEndMonth", month_str),
            ("tripEndDay", str(last_day)),
        ]
        for name, val in targets:
            sel = page.locator(f"select[name='{name}']:visible")
            if sel.count() > 0:
                sel.first.select_option(value=val)
                print(f"[Racco] {name} → {val}")
            else:
                # :visible が効かない場合は最初のnthを使う
                sel = page.locator(f"select[name='{name}']").first
                sel.select_option(value=val)
                print(f"[Racco] {name} → {val} (first)")

        # ラジオボタン: デバッグ出力 + 「チェックアウト日を対象とする」を選択
        radios = page.locator("input[type='radio']")
        radio_count = radios.count()
        print(f"[Racco] ラジオボタン数: {radio_count}")
        for i in range(radio_count):
            r = radios.nth(i)
            rname = r.get_attribute("name") or ""
            rvalue = r.get_attribute("value") or ""
            checked = r.is_checked()
            print(f"  radio[{i}] name='{rname}' value='{rvalue}' checked={checked}")

        # チェックアウト日を対象とする: name='searchFlag' value='3'
        checkout_radio = page.locator("input[name='searchFlag'][value='3']")
        if checkout_radio.count() > 0:
            checkout_radio.first.click()
            print("[Racco] ラジオ選択: チェックアウト日を対象とする (searchFlag=3)")
        else:
            print("[Racco] WARNING: searchFlag=3 ラジオが見つかりません")

        print(f"[Racco] 検索条件設定完了: {year}/{month}/1 ～ {year}/{month}/{last_day} チェックアウト日基準")

    def _do_csv_download(self, page: Page, year: int, month: int) -> Path:
        """検索結果ページでCSVダウンロード"""
        print(f"[Racco] 検索結果ページ: {page.url}")

        # 「ヘッダ行を表示する」チェックボックスをONにする
        checkboxes = page.locator("input[type='checkbox']")
        cb_count = checkboxes.count()
        print(f"[Racco] チェックボックス数: {cb_count}")
        for i in range(cb_count):
            # チェックボックスの隣接テキストを親要素から取得
            parent_text = checkboxes.nth(i).locator("xpath=..").inner_text().strip()
            if "ヘッダ" in parent_text:
                if not checkboxes.nth(i).is_checked():
                    checkboxes.nth(i).check()
                    print(f"[Racco] 「ヘッダ行を表示する」にチェック")
                else:
                    print(f"[Racco] 「ヘッダ行を表示する」は既にチェック済み")
                break

        # CSVダウンロードボタン: input[type='submit'][value='CSVダウンロード']
        csv_btn = page.locator("input[type='submit'][value='CSVダウンロード']")
        if csv_btn.count() == 0:
            # フォールバック
            csv_btn = page.locator("input[value*='CSV']")
        if csv_btn.count() == 0:
            raise RuntimeError("CSVダウンロードボタンが見つかりません")

        print(f"[Racco] CSVダウンロードボタン検出")

        # ダウンロード実行
        with page.expect_download(timeout=30000) as download_info:
            csv_btn.first.click()

        download = download_info.value
        save_path = EX_DATA_DIR / f"racco_{year}_{month:02d}.csv"
        download.save_as(str(save_path))
        print(f"[Racco] CSVダウンロード完了: {save_path}")
        return save_path

    @staticmethod
    def parse_csv(filepath: Path) -> list[dict]:
        """ダウンロードしたCSVをパースしてdict listで返す"""
        for encoding in ("shift_jis", "cp932", "utf-8", "utf-8-sig"):
            try:
                text = filepath.read_text(encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError(f"CSVのエンコーディングを判定できません: {filepath}")

        lines = text.splitlines()

        # ヘッダー行を探す
        header_idx = None
        for i, line in enumerate(lines):
            if any(kw in line for kw in ["宿泊", "チェックイン", "予約", "施設", "宿名", "ホテル", "予約番号"]):
                header_idx = i
                break

        if header_idx is None:
            header_idx = 0

        csv_text = "\n".join(lines[header_idx:])
        reader = csv.DictReader(io.StringIO(csv_text))

        records = []
        for row in reader:
            if not any(v.strip() for v in row.values() if v):
                continue
            records.append(dict(row))

        print(f"[Racco] CSV解析完了: {len(records)}件")
        return records
