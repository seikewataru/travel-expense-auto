"""じゃらん（法人予約管理）Playwrightスクレイパー — 宿泊予約データCSVを自動取得

フロー:
  1. ログイン（企業ID + パスワード）
  2. 宿泊予約データ検索画面へ遷移
  3. 抽出期間: 対象月を指定
  4. 抽出条件: 宿泊日基準（チェックアウト日を含む）
  5. キャンセル条件: キャンセルを含む
  6. 予約データ一覧画面へ → CSVダウンロード
  7. 「DailyReservation_COMMON_*」ファイルを使用
"""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, BrowserContext

from src.config import (
    JALAN_LOGIN_URL,
    JALAN_CORP_ID,
    JALAN_PASSWORD,
    JALAN_BROWSER_PROFILE,
    EX_DATA_DIR,
)


class JalanClient:
    """じゃらん法人予約管理スクレイパー"""

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
        JALAN_BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)
        EX_DATA_DIR.mkdir(parents=True, exist_ok=True)

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(JALAN_BROWSER_PROFILE),
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
        """じゃらん法人予約管理にログイン"""
        page = self._page
        print("[Jalan] ログインページへ遷移...")
        page.goto(JALAN_LOGIN_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # ログイン済みチェック
        if page.locator("input[type='text'], input[type='password']").count() == 0:
            print("[Jalan] ログイン済み（セッション有効）")
            return

        # 企業ID入力
        text_inputs = page.locator("input[type='text']")
        pw_inputs = page.locator("input[type='password']")

        print(f"[Jalan] 企業ID: {JALAN_CORP_ID} (len={len(JALAN_CORP_ID)})")
        print(f"[Jalan] パスワード長: {len(JALAN_PASSWORD)}")

        if text_inputs.count() > 0:
            text_inputs.first.click()
            text_inputs.first.fill("")
            text_inputs.first.type(JALAN_CORP_ID, delay=50)
            print("[Jalan] 企業ID入力完了")

        if pw_inputs.count() > 0:
            pw_inputs.first.click()
            pw_inputs.first.fill("")
            pw_inputs.first.type(JALAN_PASSWORD, delay=50)
            print("[Jalan] パスワード入力完了")

        # ログインボタン（input[type='button']のonclick）
        login_btn = page.locator("input[value*='ログイン']")
        if login_btn.count() > 0:
            login_btn.first.click()
            print("[Jalan] ログインボタンクリック")
            page.wait_for_timeout(5000)

        # ログイン成功チェック
        if "Login" in page.url or "login" in page.url:
            body = page.inner_text("body")
            if "エラー" in body or "パスワード" in body:
                print(f"[Jalan] ログイン失敗の可能性あり。URL: {page.url}")
                # エラーメッセージを表示
                font_err = page.locator("font[color]")
                if font_err.count() > 0:
                    print(f"[Jalan] エラー: {font_err.first.inner_text()}")
            else:
                print(f"[Jalan] WARNING: まだログインページにいます。URL: {page.url}")
        else:
            print("[Jalan] ログイン完了")

    def download_csv(self, year: int, month: int) -> Path:
        """宿泊予約データCSVをダウンロードする

        Args:
            year: 対象年（例: 2026）
            month: 対象月（例: 1）

        Returns:
            ダウンロードしたCSVファイルのパス
        """
        page = self._page
        print(f"[Jalan] 宿泊予約データダウンロード — {year}年{month}月")

        # STEP 1: 宿泊予約データ検索画面へ遷移
        self._navigate_to_search(page)

        # STEP 2: 検索条件設定
        self._set_search_conditions(page, year, month)

        # STEP 3: CSVダウンロード（検索画面から直接 or 一覧経由）
        csv_path = self._do_csv_download(page, year, month)
        return csv_path

    def _navigate_to_search(self, page: Page) -> None:
        """宿泊予約データ検索画面へ遷移"""
        print(f"[Jalan] 現在のURL: {page.url}")

        # 既に検索画面にいるかチェック（抽出期間セレクトがあれば検索画面）
        body_text = page.inner_text("body")
        if "抽出期間" in body_text:
            print("[Jalan] 既に検索画面にいます")
            return

        # メニューから「宿泊予約データ検索」ボタンをクリック
        # input[type='submit']/input[type='button'] またはリンク
        for keyword in ["宿泊予約データ検索"]:
            btn = page.locator(
                f"input[value='{keyword}'], input[value*='{keyword}'], "
                f"button:has-text('{keyword}'), a:has-text('{keyword}')"
            )
            if btn.count() > 0:
                btn.first.click()
                page.wait_for_timeout(3000)
                print(f"[Jalan] 「{keyword}」をクリック")
                return

        # 見つからない場合デバッグ
        inputs = page.locator("input[type='submit'], input[type='button']")
        input_count = inputs.count()
        print(f"[Jalan] ボタン要素 ({input_count}件):")
        for i in range(input_count):
            val = inputs.nth(i).get_attribute("value") or ""
            print(f"  [{i}] value='{val}'")

        raise RuntimeError("「宿泊予約データ検索」ボタンが見つかりません")

    def _set_search_conditions(self, page: Page, year: int, month: int) -> None:
        """検索条件を設定"""
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        year_str = str(year)
        month_str = str(month)
        print(f"[Jalan] 検索条件設定: {year}年{month}月")

        # セレクトボックス: 位置で直接指定（From年/月/日 ～ To年/月/日）
        # select[0]=From年, [1]=From月, [2]=From日, [3]=To年, [4]=To月, [5]=To日
        selects = page.locator("select")
        select_count = selects.count()
        print(f"[Jalan] セレクトボックス数: {select_count}")

        # デバッグ: 最初の6つのname表示
        for i in range(min(select_count, 6)):
            name = selects.nth(i).get_attribute("name") or ""
            print(f"  select[{i}] name='{name}'")

        if select_count >= 6:
            selects.nth(0).select_option(value=year_str)
            print(f"[Jalan] select[0] → {year_str} (From年)")
            selects.nth(1).select_option(value=month_str)
            print(f"[Jalan] select[1] → {month_str} (From月)")
            selects.nth(2).select_option(value="1")
            print(f"[Jalan] select[2] → 1 (From日)")
            selects.nth(3).select_option(value=year_str)
            print(f"[Jalan] select[3] → {year_str} (To年)")
            selects.nth(4).select_option(value=month_str)
            print(f"[Jalan] select[4] → {month_str} (To月)")
            selects.nth(5).select_option(value=str(last_day))
            print(f"[Jalan] select[5] → {last_day} (To日)")

        # ラジオ: 宿泊日基準（チェックアウト日を含む）= condSearchKind value=3
        checkout_radio = page.locator("input[name='condSearchKind'][value='3']")
        if checkout_radio.count() > 0:
            checkout_radio.first.click()
            print("[Jalan] ラジオ選択: 宿泊日基準(チェックアウト日を含む)")

        # キャンセル条件: 「キャンセルを含む」はデフォルト選択済み
        print(f"[Jalan] 検索条件設定完了: {year}/{month}/1 ～ {year}/{month}/{last_day}")

    def _do_csv_download(self, page: Page, year: int, month: int) -> Path:
        """検索画面から直接ファイルダウンロード、またはー覧経由でCSVダウンロード"""

        # データなしチェック
        body_text = page.inner_text("body")
        if "宿泊予約は存在しません" in body_text:
            print(f"[Jalan] {year}年{month}月のデータなし")
            # 空CSVを作成して返す
            save_path = EX_DATA_DIR / f"jalan_{year}_{month:02d}.csv"
            save_path.write_text("")
            return save_path

        # 方法1: 検索画面の「ファイルダウンロード」ボタンで直接DL
        dl_btn = page.locator("input[value='ファイルダウンロード'], input[value*='ファイルダウンロード']")
        if dl_btn.count() > 0:
            print("[Jalan] 「ファイルダウンロード」ボタンを検出 — 直接ダウンロード")
            with page.expect_download(timeout=30000) as download_info:
                dl_btn.first.click()

            download = download_info.value
            save_path = EX_DATA_DIR / f"jalan_{year}_{month:02d}.csv"
            download.save_as(str(save_path))
            print(f"[Jalan] CSVダウンロード完了: {save_path}")
            return save_path

        # 方法2: 「予約データ一覧画面へ」→ 一覧ページでCSV DL
        list_btn = page.locator("input[name='btnChange'][value='予約データ一覧画面へ']")
        if list_btn.count() > 0:
            list_btn.first.click()
            print("[Jalan] 「予約データ一覧画面へ」をクリック")
            page.wait_for_timeout(5000)

            # 一覧ページでCSVボタンを探す
            csv_btn = page.locator("input[value*='CSV'], a:has-text('CSV'), button:has-text('CSV')")
            if csv_btn.count() > 0:
                with page.expect_download(timeout=30000) as download_info:
                    csv_btn.first.click()

                download = download_info.value
                save_path = EX_DATA_DIR / f"jalan_{year}_{month:02d}.csv"
                download.save_as(str(save_path))
                print(f"[Jalan] CSVダウンロード完了: {save_path}")
                return save_path

        # デバッグ
        inputs = page.locator("input[type='submit'], input[type='button']")
        input_count = inputs.count()
        print(f"[Jalan] ボタン要素 ({input_count}件):")
        for i in range(input_count):
            val = inputs.nth(i).get_attribute("value") or ""
            print(f"  [{i}] value='{val}'")

        raise RuntimeError("CSVダウンロードボタンが見つかりません")

    @staticmethod
    def parse_csv(filepath: Path) -> list[dict]:
        """ダウンロードしたCSV（ZIP内）をパースしてdict listで返す

        ダウンロードファイルはZIP。中の「DailyReservation_COMMON_*」CSVを使用。
        ※チェックアウト日が翌月のデータも含まれるため、呼び出し元でフィルタが必要
        """
        # 空ファイル（データなし）チェック
        if filepath.stat().st_size == 0:
            print("[Jalan] データなし（空ファイル）")
            return []

        # ZIPファイルの場合、解凍してCSVを取得
        if zipfile.is_zipfile(str(filepath)):
            with zipfile.ZipFile(str(filepath)) as zf:
                # DailyReservation_COMMON_* を優先
                csv_name = None
                for name in zf.namelist():
                    if "COMMON" in name:
                        csv_name = name
                        break
                if csv_name is None:
                    csv_name = zf.namelist()[0]

                print(f"[Jalan] ZIP内CSVファイル: {csv_name}")
                raw = zf.read(csv_name)
        else:
            raw = filepath.read_bytes()

        # エンコーディング判定
        for encoding in ("shift_jis", "cp932", "utf-8", "utf-8-sig"):
            try:
                text = raw.decode(encoding)
                break
            except (UnicodeDecodeError, AttributeError):
                continue
        else:
            raise ValueError(f"CSVのエンコーディングを判定できません: {filepath}")

        lines = text.splitlines()

        # ヘッダー行を探す
        header_idx = None
        for i, line in enumerate(lines):
            if any(kw in line for kw in ["予約番号", "宿泊日", "チェックイン", "精算"]):
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

        print(f"[Jalan] CSV解析完了: {len(records)}件")
        return records
