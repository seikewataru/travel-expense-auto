"""EXカード Playwrightスクレイパー — エクスプレス予約の利用実績CSVを自動取得"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, BrowserContext

from src.config import (
    EX_LOGIN_URL,
    EX_CARD_NUMBER,
    EX_PASSWORD,
    EX_DATA_DIR,
    EX_BROWSER_PROFILE,
)
from src.gmail_otp import get_otp


class EXCardClient:
    """EXカード（エクスプレス予約）スクレイパー"""

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
        EX_BROWSER_PROFILE.mkdir(parents=True, exist_ok=True)
        EX_DATA_DIR.mkdir(parents=True, exist_ok=True)

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(EX_BROWSER_PROFILE),
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
        """EX予約にログインする（OTP対応）"""
        page = self._page
        print("[EX] ログインページへ遷移...")
        page.goto(EX_LOGIN_URL, wait_until="load")
        page.wait_for_timeout(3000)

        # フレーム内にコンテンツがある場合の対応
        target = page
        if len(page.frames) > 1:
            for frame in page.frames:
                if frame.locator("input").count() > 0:
                    target = frame
                    print("[EX] フレーム内のフォームを検出")
                    break

        # 会員ID入力（プレースホルダー「数字10桁」で特定）
        card_input = target.locator("input[placeholder*='10桁']")
        if card_input.count() == 0:
            # フォールバック: 最初のテキスト入力
            card_input = target.locator("input[type='text']").first
        else:
            card_input = card_input.first
        card_input.fill(EX_CARD_NUMBER)
        print(f"[EX] 会員ID入力完了")

        # パスワード入力（プレースホルダー「英数記号」で特定）
        pw_input = target.locator("input[placeholder*='英数記号']")
        if pw_input.count() == 0:
            pw_input = target.locator("input[type='password']").first
        else:
            pw_input = pw_input.first
        pw_input.fill(EX_PASSWORD)
        print("[EX] パスワード入力完了")

        # ログインボタン押下（input/buttonを優先、aタグのWESTERリンクを避ける）
        login_btn = target.locator("input[type='image'], input[type='submit'], input[value*='ログイン'], button:has-text('ログイン')")
        if login_btn.count() == 0:
            # フォールバック: フォーム内のリンク（WESTER以外）
            login_btn = target.locator("a:has-text('ログイン'):not(:has-text('WESTER'))")
        login_btn.first.click()
        page.wait_for_timeout(3000)

        # OTP画面が表示されるかチェック
        self._handle_otp_if_needed(page)

        print("[EX] ログイン完了")

    def _handle_otp_if_needed(self, page: Page) -> None:
        """OTP入力画面が表示されていたら、メール送信→手動入力→送信する"""
        body_text = page.inner_text("body")
        if "ワンタイムパスワード" not in body_text:
            print("[EX] OTP不要（セッション有効）")
            return

        print("[EX] OTP画面を検出")

        # STEP 1: 「メール送信」ボタンをクリック
        mail_btn = page.locator("input[value*='メール送信'], a:has-text('メール送信'), button:has-text('メール送信'), input[type='image']")
        if mail_btn.count() > 0:
            mail_btn.first.click()
            print("[EX] メール送信ボタンをクリック — OTPメール送信中...")
            page.wait_for_timeout(2000)

            # 「メールを送信しました」ダイアログの「閉じる」ボタンをクリック
            try:
                close_btn = page.get_by_text("閉じる")
                close_btn.wait_for(state="visible", timeout=5000)
                close_btn.click()
                print("[EX] ダイアログを閉じました")
                page.wait_for_timeout(1000)
            except Exception:
                print("[EX] ダイアログが見つかりません、続行します")

        # STEP 2: ターミナルでOTP入力を求める
        otp_code = get_otp()

        # OTP入力フィールド（プレースホルダー「数字6桁」で特定）
        otp_input = page.locator("input[placeholder*='6桁']")
        if otp_input.count() == 0:
            otp_input = page.locator("input[type='text'], input[type='tel'], input[type='number']")
        otp_input.first.fill(otp_code)

        # 「OK 次へ」ボタンをクリック
        ok_btn = page.locator("input[value*='OK'], input[value*='次へ'], a:has-text('OK'), button:has-text('OK')")
        if ok_btn.count() == 0:
            ok_btn = page.locator("input[type='submit'], input[type='image']")
        ok_btn.first.click()
        page.wait_for_timeout(3000)

        print("[EX] OTP認証完了")

    def download_csv(self, year: int, month: int) -> Path:
        """利用実績CSVをダウンロードする

        Args:
            year: 対象年（例: 2026）
            month: 対象月（例: 1）

        Returns:
            ダウンロードしたCSVファイルのパス
        """
        page = self._page
        print(f"[EX] 利用実績ダウンロード — {year}年{month}月")
        page.wait_for_timeout(2000)
        print(f"[EX] 現在のURL: {page.url}")

        # 利用実績ダウンロードページへ遷移（フレーム対応）
        target = self._navigate_to_download_page(page)

        # 期間指定（From: 月初 / To: 月末）
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        self._set_period(target, year, month, last_day)

        # 簡易版CSVダウンロード
        csv_path = self._do_download(page, target, year, month)

        return csv_path

    def _get_content_frame(self, page: Page):
        """フレーム構造の場合、コンテンツがあるフレームを返す。なければpage自体を返す。"""
        frames = page.frames
        if len(frames) <= 1:
            return page

        print(f"[EX] フレーム数: {len(frames)}")
        for frame in frames:
            name = frame.name or "(no name)"
            url = frame.url
            print(f"  フレーム: {name} -> {url}")

        # selectやリンクが多いフレームを探す
        for frame in frames:
            if frame == page.main_frame:
                continue
            if frame.locator("select").count() > 0 or frame.locator("a").count() > 3:
                print(f"[EX] コンテンツフレーム検出: {frame.name or frame.url}")
                return frame

        return page

    def _navigate_to_download_page(self, page: Page):
        """メニュー → ご利用実績ダウンロードページへ遷移し、操作対象を返す"""
        target = self._get_content_frame(page)

        # 既にダウンロードページにいるかチェック（selectが4つ以上ある）
        if target.locator("select").count() >= 4:
            print("[EX] 既にダウンロードページにいます")
            return target

        # メニューから「ご利用実績ダウンロード」ボタンをクリック
        dl_btn = target.locator("a:has-text('ご利用実績ダウンロード')")
        if dl_btn.count() > 0:
            print("[EX] 「ご利用実績ダウンロード」ボタンをクリック")
            dl_btn.first.click()
            page.wait_for_timeout(3000)

            # DLページ遷移時にもOTPが求められることがある
            self._handle_otp_if_needed(page)
            page.wait_for_timeout(2000)

            target = self._get_content_frame(page)
            if target.locator("select").count() >= 4:
                return target

            # selectがまだ見つからない場合、フレーム再探索
            print(f"[EX] 遷移後URL: {page.url}")
            print(f"[EX] selectボックス数: {target.locator('select').count()}")

        # デバッグ: リンク一覧を表示
        for frame in page.frames:
            all_links = frame.locator("a")
            count = all_links.count()
            if count == 0:
                continue
            fname = frame.name or frame.url
            print(f"[EX] フレーム '{fname}' のリンク ({count}件):")
            for i in range(min(count, 20)):
                text = all_links.nth(i).inner_text().strip().replace("\n", " ")
                if text:
                    print(f"  [{i}] {text}")

        raise RuntimeError("ダウンロードページへの遷移に失敗しました")

    def _set_period(self, target, year: int, month: int, last_day: int) -> None:
        """期間を設定する（From: 年月+1日 / To: 年月+末日）"""
        selects = target.locator("select")
        count = selects.count()
        print(f"[EX] セレクトボックス数: {count}")

        # From年月（「{year}年{month}月」を含むoptionを選択）
        from_ym = f"{year}年{month}月"
        to_ym = f"{year}年{month}月"

        # セレクトボックスを順番に処理: From年月, From日, To年月, To日
        if count >= 4:
            selects.nth(0).select_option(label=from_ym)
            selects.nth(1).select_option(label="1日")
            selects.nth(2).select_option(label=to_ym)
            selects.nth(3).select_option(label=f"{last_day}日")
            print(f"[EX] 期間設定: {from_ym}1日 〜 {to_ym}{last_day}日")
        else:
            print(f"[EX] セレクトボックスが{count}個しかありません（想定: 4個）")

    def _do_download(self, page: Page, target, year: int, month: int) -> Path:
        """簡易版CSVをダウンロードする"""
        # デバッグ: input/buttonも含めた全クリック要素を表示
        inputs = target.locator("input[type='image'], input[type='submit'], input[type='button']")
        input_count = inputs.count()
        print(f"[EX] input要素 ({input_count}件):")
        for i in range(input_count):
            val = inputs.nth(i).get_attribute("value") or ""
            alt = inputs.nth(i).get_attribute("alt") or ""
            src = inputs.nth(i).get_attribute("src") or ""
            print(f"  [{i}] value='{val}' alt='{alt}' src='{src}'")

        buttons = target.locator("button")
        btn_count = buttons.count()
        if btn_count > 0:
            print(f"[EX] button要素 ({btn_count}件):")
            for i in range(btn_count):
                print(f"  [{i}] {buttons.nth(i).inner_text().strip()}")

        # 簡易版「ご利用実績」ボタンを探す（opacity:0の透明オーバーレイbutton）
        dl_target = None

        # button[name] でフィルタ（name="b2"が簡易版「ご利用実績」）
        named_buttons = target.locator("button[name]")
        named_count = named_buttons.count()
        print(f"[EX] name付きbutton ({named_count}件):")
        for i in range(named_count):
            name = named_buttons.nth(i).get_attribute("name") or ""
            text = named_buttons.nth(i).inner_text().strip()
            print(f"  [{i}] name='{name}' text='{text}'")
            # 簡易版: テキストが「ご利用実績」のみ（元データ/マクロを含まない）
            if text == "ご利用実績":
                dl_target = named_buttons.nth(i)
                print(f"[EX] DLボタン検出: name='{name}'")

        if dl_target is None:
            raise RuntimeError("簡易版ダウンロードボタンが見つかりません")

        # ダウンロードイベントを待ちながらクリック（opacity:0なのでforce=True）
        with page.expect_download(timeout=30000) as download_info:
            dl_target.click(force=True)

        download = download_info.value
        save_path = EX_DATA_DIR / f"ex_{year}_{month:02d}.csv"
        download.save_as(str(save_path))
        print(f"[EX] CSVダウンロード完了: {save_path}")
        return save_path

    @staticmethod
    def parse_csv(filepath: Path) -> list[dict]:
        """ダウンロードしたCSVをパースしてdict listで返す

        CSVフォーマット:
          行0: タイトル（スキップ）
          行1: 空行（スキップ）
          行2-3: カテゴリヘッダー（スキップ）
          行4: 列名ヘッダー
          行5〜: データ

        Returns:
            各行をdictにしたリスト
        """
        # Shift-JISでデコード
        for encoding in ("shift_jis", "cp932", "utf-8"):
            try:
                text = filepath.read_text(encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError(f"CSVのエンコーディングを判定できません: {filepath}")

        lines = text.splitlines()

        # ヘッダー行（行4）を探す: 「操作日」で始まる行
        header_idx = None
        for i, line in enumerate(lines):
            if "操作日" in line:
                header_idx = i
                break
        if header_idx is None:
            raise ValueError("ヘッダー行（操作日）が見つかりません")

        # ヘッダー行以降をCSVとしてパース
        csv_text = "\n".join(lines[header_idx:])
        reader = csv.DictReader(io.StringIO(csv_text))

        records = []
        for row in reader:
            # 空行・合計行をスキップ
            date = row.get("操作日", "").strip()
            if not date or date == "":
                continue
            records.append(dict(row))

        print(f"[EX] CSV解析完了: {len(records)}件")
        return records
