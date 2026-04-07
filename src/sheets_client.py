"""Google Sheets クライアント — 部署マスタ読み込み + 集計結果出力"""

from __future__ import annotations

import re

import gspread

from src.config import (
    DEPT_MASTER_SHEET_ID,
    EX_CARD_MASTER_GID,
    EX_CARD_MASTER_SHEET_ID,
    EX_EXCLUSION_GID,
    EX_EXCLUSION_SHEET_ID,
    GCP_SERVICE_ACCOUNT_PATH,
    OUTPUT_SHEET_ID,
    RINGI_SHEET_GID,
    RINGI_SHEET_ID,
    SALES_SHEET_ID,
    SALES_YOJITSU_GID,
)


class SheetsClient:
    """Google Sheets 読み書きクライアント（サービスアカウント認証）"""

    def __init__(self):
        # Streamlit Cloud: st.secrets["gcp_service_account"] から読む
        # ローカル: ファイルパスから読む
        try:
            import streamlit as st
            if "gcp_service_account" in st.secrets:
                self._gc = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
                return
        except Exception:
            pass
        self._gc = gspread.service_account(filename=GCP_SERVICE_ACCOUNT_PATH)

    def read_department_master(self, year: int, month: int) -> dict[str, dict]:
        """部署マスタ（人員マスタシート）を読み込む

        Args:
            year: 対象年
            month: 対象月

        Returns:
            {"山田 太郎": {"emp_no": "2", "department": "営業部_営業1課"}, ...}
            ※退職者（A列="退職"）はスキップ
        """
        sh = self._gc.open_by_key(DEPT_MASTER_SHEET_ID)
        ws = sh.worksheet("人員マスタ")
        all_values = ws.get_all_values()

        # ヘッダー行（Row 3 = index 2）
        if len(all_values) < 3:
            raise ValueError("人員マスタのデータが不足しています")

        header_row = all_values[2]  # Row 3

        # B列=社員番号(index 1), C列=氏名(index 2)
        emp_no_col = 1
        name_col = 2

        # 対象月の「部署_YYMM」列を探す
        yymm = f"{year % 100:02d}{month:02d}"
        dept_col = None
        for i, h in enumerate(header_row):
            if f"部署_{yymm}" in str(h):
                dept_col = i
                break

        if dept_col is None:
            print(f"[Sheets] WARNING: 部署_{yymm} 列が見つかりません。最新の部署列を使用します。")
            # 最新の部署列を探す（右端の「部署_YYMM」）
            for i in range(len(header_row) - 1, -1, -1):
                if re.match(r"部署_\d{4}", str(header_row[i])):
                    dept_col = i
                    print(f"[Sheets] 代替列: {header_row[i]} (col {i})")
                    break

        if dept_col is None:
            raise ValueError("部署列が見つかりません")

        result = {}
        for row_idx, row in enumerate(all_values[3:], start=4):  # Row 4以降がデータ
            # A列が「退職」→スキップ
            if len(row) > 0 and row[0].strip() == "退職":
                continue

            emp_no = row[emp_no_col].strip() if len(row) > emp_no_col else ""
            name = row[name_col].strip() if len(row) > name_col else ""
            dept = row[dept_col].strip() if len(row) > dept_col else ""

            if not name:
                continue

            # 名前を正規化（全角/半角スペース統一、前後空白除去）
            normalized_name = normalize_name(name)
            result[normalized_name] = {
                "emp_no": emp_no,
                "department": dept,
                "raw_name": name,
            }

        print(f"[Sheets] 部署マスタ読み込み完了: {len(result)}名（退職者除く）")
        return result

    def read_ex_card_master(self) -> tuple[dict[str, str], set[str], dict[str, str]]:
        """EXカード管理シートを読み込み、会員ID→現カード所持者マッピングを返す

        ※毎月所持者が変わる可能性があるため、集計前に必ず最新を読み込むこと

        Returns:
            (holder_map, exclude_ids, category_map)
            holder_map: {"6943717236": "丸岡 智泰", ...}
            exclude_ids: 集計除外対象（未定・部門貸出用）の会員IDセット
            category_map: {"0498368181": "広告関連貸出用", ...} 全カードの集計種別
        """
        # これらは集計から完全除外（仕訳も生成しない）
        EXCLUDE_CATEGORIES = {"未定"}

        sh = self._gc.open_by_key(EX_CARD_MASTER_SHEET_ID)
        ws = sh.get_worksheet_by_id(EX_CARD_MASTER_GID)
        all_values = ws.get_all_values()

        # Row 7 (index 7) がヘッダー: col2=会員ID, col7=現カード所持者(氏名), col8=集計種別
        result = {}
        exclude_ids: set[str] = set()
        category_map: dict[str, str] = {}
        for row in all_values[8:]:  # Row 8以降がデータ
            member_id = row[2].strip() if len(row) > 2 else ""
            holder = row[7].strip() if len(row) > 7 else ""
            category = row[8].strip() if len(row) > 8 else ""
            if not member_id:
                continue
            result[member_id] = holder
            category_map[member_id] = category
            if category in EXCLUDE_CATEGORIES:
                exclude_ids.add(member_id)

        print(f"[Sheets] EXカードマスタ読み込み完了: {len(result)}件（除外: {len(exclude_ids)}件）")
        return result, exclude_ids, category_map

    # 除外対象シートの集計種別 → 仕訳カテゴリ
    _EX_SHEET_CATEGORY_MAP: dict[str, str] = {
        "個人貸与": "shinkansen",
        "広告関連貸出用": "shinkansen_ad",
        "部門貸出用": "shinkansen_subsidiary",
    }

    # 除外対象シートの「実際の利用者」→ 子会社名マッピング
    _EX_SUBSIDIARY_MAP: dict[str, str] = {
        "スタジアム": "株式会社スタジアム",
    }

    def read_ex_card_accounting(self, year: int, month: int) -> list[dict]:
        """除外対象シートからEXカード計上データを読み込む（乗車日基準・PL税抜一致）

        経理が手動で乗車日基準の年月・税抜額・振替分類を設定済みのシートから
        そのまま読み込むことで、期間ずれ・税端数差を解消する。

        Args:
            year: 対象年
            month: 対象月

        Returns:
            [{"name": "山田 太郎", "amount": 12345, "category": "shinkansen"}, ...]
        """
        from src.aggregator import normalize_name

        sh = self._gc.open_by_key(EX_EXCLUSION_SHEET_ID)
        ws = sh.get_worksheet_by_id(EX_EXCLUSION_GID)
        all_values = ws.get_all_values()

        # 列: [43]=年月, [45]=計上額（税抜）, [46]=現カード所持者, [47]=集計種別, [48]=実際の利用者
        target_ym = f"{year}-{month:02d}"
        records: list[dict] = []

        for row in all_values[1:]:
            if len(row) <= 48:
                continue
            ym = row[43].strip()
            if ym != target_ym:
                continue
            amount_str = row[45].replace(",", "").strip()
            amount = int(float(amount_str)) if amount_str else 0
            if amount == 0:
                continue

            holder = row[46].strip()
            sheet_category = row[47].strip()
            actual_user = row[48].strip()

            # カテゴリ決定
            if "福利厚生" in actual_user:
                category = "shinkansen_welfare"
                name = holder
            elif sheet_category == "広告関連貸出用":
                category = "shinkansen_ad"
                name = holder
            elif sheet_category == "部門貸出用":
                # スタジアムのみ子会社振替、それ以外は通常扱い（PL準拠）
                if actual_user in self._EX_SUBSIDIARY_MAP:
                    category = "shinkansen_subsidiary"
                    name = self._EX_SUBSIDIARY_MAP[actual_user]
                else:
                    category = "shinkansen"
                    name = actual_user if actual_user else holder
            else:
                # 個人貸与: 現カード所持者 = 実際の利用者
                category = "shinkansen"
                name = holder

            if not name:
                continue
            records.append({"name": name, "amount": amount, "category": category})

        # 集計ログ
        from collections import Counter
        cat_totals: dict[str, int] = {}
        for r in records:
            cat_totals[r["category"]] = cat_totals.get(r["category"], 0) + r["amount"]
        total = sum(cat_totals.values())
        cat_str = ", ".join(f"{k}=¥{v:,}" for k, v in sorted(cat_totals.items()))
        print(f"[Sheets] EXカード計上データ読み込み完了: {len(records)}件, ¥{total:,} ({cat_str})")
        return records

    # ROIタブの月ごとのカラム構成（6列/月: 新幹線, 在来線, 車移動, 飛行機, 宿泊費, 合計）
    ROI_COLS_PER_MONTH = 6
    ROI_DATA_START_COL = 3  # D列 = index 3 (0-based)
    ROI_HEADER_ROW = 3      # Row 3 がカラムヘッダー
    ROI_DATA_START_ROW = 4  # Row 4 からデータ

    # セグメント判定キーワード（aggregator.SEGMENT_KEYWORDS と同じ）
    SEGMENT_KEYWORDS = ["SDR", "BDR", "ALLI", "CCS", "UNION", "UNI", "事業開発", "COM", "コミュニティ"]

    def _calc_row_values(self, r: dict) -> list[int]:
        """個人集計行から[新幹線, 在来線, 車移動, 飛行機, 宿泊費, 合計]を算出"""
        shinkansen = (r.get("shinkansen", 0) + r.get("shinkansen_ad", 0)
                      + r.get("shinkansen_welfare", 0) + r.get("shinkansen_recruit", 0)
                      + r.get("shinkansen_subsidiary", 0))
        train = r.get("train", 0) + r.get("train_ad", 0) + r.get("train_recruit", 0)
        car = r.get("car", 0) + r.get("car_ad", 0) + r.get("car_recruit", 0)
        airplane = r.get("airplane", 0) + r.get("airplane_ad", 0) + r.get("airplane_recruit", 0)
        hotel = r.get("hotel", 0) + r.get("hotel_ad", 0) + r.get("hotel_recruit", 0)
        other = r.get("other", 0) + r.get("other_ad", 0) + r.get("other_recruit", 0)
        car += other
        total = shinkansen + train + car + airplane + hotel
        return [shinkansen, train, car, airplane, hotel, total]

    def write_expense_summary(
        self, rows: list[dict], year: int, month: int,
        segment_map: dict[str, str] | None = None,
        roi_master: dict[str, str] | None = None,
    ) -> None:
        """集計結果をROIタブに2階層構造で書き込み

        セグメント小計（太字）→ メンバー明細（インデント）の構造。
        segment_map が渡されればセグメント別にグループ化。

        Args:
            rows: aggregator.summarize() の結果
            year: 対象年
            month: 対象月
            segment_map: normalize_name(名前) -> セグメントキー（推奨）
            roi_master: 後方互換（未使用、segment_mapを使うこと）
        """
        sh = self._gc.open_by_key(OUTPUT_SHEET_ID)
        ws = sh.get_worksheet_by_id(0)  # 交通費まとめ（gid=0）

        # 対象月の開始列を計算
        month_col_start = self.ROI_DATA_START_COL + (month - 1) * self.ROI_COLS_PER_MONTH

        # --- セグメント別にグループ化 ---
        segments: dict[str, list[dict]] = {}
        for r in rows:
            name = normalize_name(r.get("name", ""))
            if not name:
                continue
            seg = segment_map.get(name, "その他") if segment_map else "その他"
            if seg not in segments:
                segments[seg] = []
            segments[seg].append(r)

        # セグメント順序: 売上責任セグメント先、その他・スタジアム・監査等委員は最後
        FIXED_ORDER = ["SDR", "BDR", "ALLI", "CCS", "UNI", "UCS", "事業開発", "BCC", "COM", "Watchy"]
        seg_order = [s for s in FIXED_ORDER if s in segments]
        # 残り（その他、スタジアム、監査等委員等）を末尾に
        for s in segments:
            if s not in seg_order:
                seg_order.append(s)

        # --- 書式リセット + ヘッダー書き込み ---
        # 既存データ・書式をクリア（A〜I列、3行目以降）
        max_row = max(len(ws.col_values(2)), 300)
        ws.batch_clear([f"A4:I{max_row}"])
        ws.format(f"A4:I{max_row}", {
            "backgroundColor": {"red": 1, "green": 1, "blue": 1},
            "textFormat": {"bold": False, "foregroundColor": {"red": 0, "green": 0, "blue": 0}, "fontSize": 9},
        })

        ws.update_cell(1, month_col_start + 1, f"{year}~")
        ws.update_cell(2, month_col_start + 1, f"{month}月")

        col_headers = ["新幹線", "在来線", "車移動", "飛行機", "宿泊費", "合計"]
        header_cells = []
        for j, h in enumerate(col_headers):
            header_cells.append(gspread.Cell(3, month_col_start + 1 + j, h))
        # A〜Cヘッダー
        header_cells.append(gspread.Cell(3, 1, "社員番号"))
        header_cells.append(gspread.Cell(3, 2, "名前"))
        header_cells.append(gspread.Cell(3, 3, "部署"))
        ws.update_cells(header_cells)

        # --- 2階層データ書き込み ---
        cells = []
        row_idx = self.ROI_DATA_START_ROW  # 4行目開始
        segment_header_rows = []  # 書式設定用

        for seg in seg_order:
            members = segments[seg]
            members.sort(key=lambda r: sum(self._calc_row_values(r)), reverse=True)

            # セグメント小計行
            seg_totals = [0] * 6
            for r in members:
                vals = self._calc_row_values(r)
                for j in range(6):
                    seg_totals[j] += vals[j]

            display_name = self.SEGMENT_DISPLAY_NAMES.get(seg, seg)
            cells.append(gspread.Cell(row_idx, 1, ""))
            cells.append(gspread.Cell(row_idx, 2, f"▼ {display_name}（{len(members)}名）"))
            cells.append(gspread.Cell(row_idx, 3, ""))
            for j, v in enumerate(seg_totals):
                cells.append(gspread.Cell(row_idx, month_col_start + 1 + j, v if v else ""))
            segment_header_rows.append(row_idx)
            row_idx += 1

            # メンバー明細行
            for r in members:
                vals = self._calc_row_values(r)
                if sum(vals) == 0:
                    continue
                cells.append(gspread.Cell(row_idx, 1, r.get("emp_no", "")))
                cells.append(gspread.Cell(row_idx, 2, f"  {r.get('name', '')}"))
                cells.append(gspread.Cell(row_idx, 3, r.get("department", "")))
                for j, v in enumerate(vals):
                    cells.append(gspread.Cell(row_idx, month_col_start + 1 + j, v if v else ""))
                row_idx += 1

        if cells:
            ws.update_cells(cells)

        # 書式設定
        self._format_roi_tab_hierarchical(ws, month_col_start, row_idx - 1, segment_header_rows)

        print(f"[Sheets] ROIタブ書き込み完了: {len(rows)}名 {len(seg_order)}セグメント → {month}月列")

    def _format_roi_tab_hierarchical(
        self, ws, month_col_start: int, last_data_row: int, segment_rows: list[int]
    ) -> None:
        """ROIタブの2階層構造用書式設定"""
        from gspread_formatting import (
            CellFormat, Color, TextFormat, NumberFormat,
            format_cell_range, set_frozen, Borders, Border,
        )

        header_bg = Color(0.22, 0.46, 0.85)
        header_text = Color(1, 1, 1)
        month_bg = Color(0.87, 0.92, 0.98)
        seg_bg = Color(0.93, 0.95, 0.98)       # セグメント小計行
        name_bg = Color(0.98, 0.98, 0.98)
        border_color = Color(0.82, 0.85, 0.89)

        thin_border = Border("SOLID", color=border_color)
        all_borders = Borders(top=thin_border, bottom=thin_border, left=thin_border, right=thin_border)

        def col_letter(col_0based):
            c = col_0based
            if c < 26:
                return chr(65 + c)
            return chr(64 + c // 26) + chr(65 + c % 26)

        start_col = col_letter(month_col_start)
        end_col = col_letter(month_col_start + self.ROI_COLS_PER_MONTH - 1)

        # Row 2: 月ヘッダー（青）
        format_cell_range(ws, f"{start_col}2:{end_col}2", CellFormat(
            backgroundColor=header_bg,
            textFormat=TextFormat(bold=True, foregroundColor=header_text, fontSize=10),
            horizontalAlignment="CENTER",
            borders=all_borders,
        ))

        # Row 3: カラムヘッダー（薄青）
        format_cell_range(ws, f"A3:C3", CellFormat(
            backgroundColor=month_bg, textFormat=TextFormat(bold=True, fontSize=9), borders=all_borders,
        ))
        format_cell_range(ws, f"{start_col}3:{end_col}3", CellFormat(
            backgroundColor=month_bg, textFormat=TextFormat(bold=True, fontSize=9),
            horizontalAlignment="CENTER", borders=all_borders,
        ))

        if last_data_row < self.ROI_DATA_START_ROW:
            return

        # 全データ範囲: 数値フォーマット + ボーダー
        format_cell_range(ws, f"{start_col}{self.ROI_DATA_START_ROW}:{end_col}{last_data_row}", CellFormat(
            numberFormat=NumberFormat(type="NUMBER", pattern="#,##0"),
            horizontalAlignment="RIGHT",
            borders=all_borders,
        ))
        format_cell_range(ws, f"A{self.ROI_DATA_START_ROW}:C{last_data_row}", CellFormat(
            borders=all_borders,
        ))

        # セグメント小計行 + メンバー行をバッチで書式設定
        from gspread_formatting import batch_updater
        with batch_updater(ws.spreadsheet) as batch:
            for sr in segment_rows:
                batch.format_cell_range(ws, f"A{sr}:{end_col}{sr}", CellFormat(
                    backgroundColor=seg_bg,
                    textFormat=TextFormat(bold=True),
                    borders=all_borders,
                ))
            for r in range(self.ROI_DATA_START_ROW, last_data_row + 1):
                if r not in segment_rows:
                    batch.format_cell_range(ws, f"A{r}:C{r}", CellFormat(
                        backgroundColor=name_bg,
                        textFormat=TextFormat(fontSize=9),
                    ))

        set_frozen(ws, rows=3, cols=3)


    def read_expense_summary(self, year: int, month: int) -> list[dict]:
        """出力先シートから集計済み旅費データを読み込む

        Args:
            year: 対象年
            month: 対象月

        Returns:
            [{"emp_no": "2", "name": "山田 太郎", "department": "営業部",
              "shinkansen": 10000, "hotel": 5000, "train": 3000, "other": 0, "total": 18000}, ...]
        """
        sh = self._gc.open_by_key(OUTPUT_SHEET_ID)
        sheet_title = f"{year}年{month:02d}月"

        try:
            ws = sh.worksheet(sheet_title)
        except gspread.exceptions.WorksheetNotFound:
            print(f"[Sheets] シート '{sheet_title}' が見つかりません")
            return []

        all_values = ws.get_all_values()
        if len(all_values) < 2:
            return []

        # Row 1 = ヘッダー: 社員番号, 名前, 部署, 新幹線, 宿泊, 在来線, その他, 合計
        result = []
        for row in all_values[1:]:
            if len(row) < 8 or not row[1].strip():
                continue
            result.append({
                "emp_no": row[0].strip(),
                "name": row[1].strip(),
                "department": row[2].strip(),
                "shinkansen": self._parse_number(row[3]),
                "hotel": self._parse_number(row[4]),
                "train": self._parse_number(row[5]),
                "other": self._parse_number(row[6]),
                "total": self._parse_number(row[7]),
            })

        print(f"[Sheets] 集計データ読み込み完了: {len(result)}名（{sheet_title}）")
        return result

    def read_roi_master(self, year: int, month: int) -> dict[str, str]:
        """人員マスタからROI分析用カテゴリを読み込む

        Args:
            year: 対象年
            month: 対象月

        Returns:
            {"山田 太郎": "マーケ_SDR_TUNAG", ...}
        """
        sh = self._gc.open_by_key(DEPT_MASTER_SHEET_ID)
        ws = sh.worksheet("人員マスタ")
        all_values = ws.get_all_values()

        header_row = all_values[2]  # Row 3
        name_col = 2

        # ROI_分析用_YYMM 列を探す
        yymm = f"{year % 100:02d}{month:02d}"
        roi_col = None
        for i, h in enumerate(header_row):
            if f"ROI_分析用_{yymm}" in str(h):
                roi_col = i
                break

        if roi_col is None:
            # 最新のROI列を使用
            for i in range(len(header_row) - 1, -1, -1):
                if "ROI_分析用_" in str(header_row[i]):
                    roi_col = i
                    break

        if roi_col is None:
            return {}

        result = {}
        for row in all_values[3:]:
            if len(row) > 0 and row[0].strip() == "退職":
                continue
            name = row[name_col].strip() if len(row) > name_col else ""
            roi_cat = row[roi_col].strip() if len(row) > roi_col else ""
            if name and roi_cat:
                result[normalize_name(name)] = roi_cat

        print(f"[Sheets] ROIマスタ読み込み完了: {len(result)}名")
        return result

    # セグメント判定ルール: (条件フィールド, キーワード, セグメントキー)
    # 上から順に評価、最初にマッチしたものを採用
    # 個別オーバーライド: normalize_name(名前) -> セグメントキー
    SEGMENT_OVERRIDES: dict[str, str] = {
        "杉山 一彦": "ALLI",      # CRO室だがアライアンス営業本部扱い
        "藤井 鈴菜": "スタジアム",  # 株式会社スタジアム
        "高谷 莉子": "スタジアム",  # 株式会社スタジアム
        "植松 あゆ美": "監査等委員",
        "藤田 豪人": "監査等委員",
        "村瀬 敬太": "監査等委員",
    }

    # field: "dept"=部署_YYMM, "honbu"=本部, "roi"=ROI_分析用_YYMM(詳細版)
    SEGMENT_RULES = [
        ("dept", "Watchy", "Watchy"),
        ("dept", "UNION CS", "UCS"),
        ("dept", "デザイン部", "その他"),           # デザイン部は売上責任なし
        ("dept", "事業開発部", "事業開発"),          # グロース戦略本部の事業開発部
        ("dept", "コミュニティ推進部", "COM"),
        ("dept", "ビジネス共創部", "BCC"),           # 事業共創本部のビジネス共創部（ALLI売上と突合）
        ("honbu", "SDR本部", "SDR"),
        ("honbu", "BDR本部", "BDR"),
        ("honbu", "アライアンス営業本部", "ALLI"),
        ("honbu", "カスタマーサクセス本部", "CCS"),
        ("honbu", "UNION事業本部", "UNI"),
        ("honbu", "事業共創本部", "事業開発"),       # 事業共創本部付など
        ("roi", "事業開発_コンサルタント", "事業開発"),
        ("roi", "事業開発_制作", "事業開発"),
        ("roi", "コムデ", "COM"),
    ]

    # セグメントキー → 正式名称
    SEGMENT_DISPLAY_NAMES = {
        "SDR": "SDR本部",
        "BDR": "BDR本部",
        "ALLI": "アライアンス本部",
        "CCS": "CS本部",
        "UNI": "UNION事業本部",
        "UCS": "UNION CS部",
        "事業開発": "事業開発",
        "BCC": "ビジネス共創部",
        "COM": "コミュニティ推進部",
        "Watchy": "Watchy事業部",
        "スタジアム": "株式会社スタジアム",
        "監査等委員": "監査等委員",
        "その他": "その他",
    }

    def read_segment_map(self, year: int, month: int) -> dict[str, str]:
        """人員マスタから社員→セグメントキーのマッピングを取得

        部署_YYMM と ROI_分析用_YYMM（詳細版）の両方を使って判定。

        Returns:
            {"山田 太郎": "SDR", "鈴木 花子": "CCS", ...}
        """
        sh = self._gc.open_by_key(DEPT_MASTER_SHEET_ID)
        ws = sh.worksheet("人員マスタ")
        all_values = ws.get_all_values()
        header_row = all_values[2]
        name_col = 2

        # 対象月のYYMM
        yymm = f"{year % 100:02d}{month:02d}"

        # 部署_YYMM, 本部, ROI_分析用_YYMM（詳細版）の列を探す
        dept_col = None
        honbu_col = None
        roi_detail_col = None
        for i, h in enumerate(header_row):
            if f"部署_{yymm}" in str(h):
                dept_col = i
            if f"ROI_分析用_{yymm}" in str(h):
                roi_detail_col = i

        # 本部列: 部署列の直前にある「本部」列
        if dept_col is not None:
            for i in range(dept_col - 1, max(dept_col - 5, -1), -1):
                if header_row[i].strip() == "本部":
                    honbu_col = i
                    break

        # フォールバック: 最新月を探す
        if dept_col is None:
            for i in range(len(header_row) - 1, -1, -1):
                if "部署_" in str(header_row[i]):
                    dept_col = i
                    break
        if roi_detail_col is None:
            for i in range(len(header_row) - 1, -1, -1):
                if "ROI_分析用_" in str(header_row[i]):
                    roi_detail_col = i
                    break
        if honbu_col is None and dept_col:
            for i in range(dept_col - 1, max(dept_col - 5, -1), -1):
                if header_row[i].strip() == "本部":
                    honbu_col = i
                    break

        result = {}
        for row in all_values[3:]:
            if len(row) > 0 and row[0].strip() == "退職":
                continue
            name = row[name_col].strip() if len(row) > name_col else ""
            if not name:
                continue
            dept = row[dept_col].strip() if dept_col and len(row) > dept_col else ""
            honbu = row[honbu_col].strip() if honbu_col and len(row) > honbu_col else ""
            roi_detail = row[roi_detail_col].strip() if roi_detail_col and len(row) > roi_detail_col else ""

            seg_key = "その他"
            for field, keyword, s_key in self.SEGMENT_RULES:
                if field == "dept":
                    source = dept
                elif field == "honbu":
                    source = honbu
                else:
                    source = roi_detail
                if keyword in source:
                    seg_key = s_key
                    break

            normalized = normalize_name(name)
            # 個別オーバーライド
            if normalized in self.SEGMENT_OVERRIDES:
                seg_key = self.SEGMENT_OVERRIDES[normalized]
            result[normalized] = seg_key

        from collections import Counter
        counts = Counter(result.values())
        seg_info = ", ".join(f"{self.SEGMENT_DISPLAY_NAMES.get(k,k)}={v}" for k, v in counts.most_common() if k != "その他")
        print(f"[Sheets] セグメントマップ読み込み完了: {len(result)}名 | {seg_info}")
        return result

    def read_sales_data(self) -> dict[str, list]:
        """売上実績シートから月次売上を読み込む

        Returns:
            {
                "row_label": [...],  # KPI行ラベル（C列）
                "months": ["2026年1月", ...],  # 月ヘッダー
                "data": {  # row_label -> [月次値, ...]
                    "合計_月次売上": [123456, ...],
                    "PF_MRR": [270198, ...],
                    ...
                }
            }
        """
        sh = self._gc.open_by_key(SALES_SHEET_ID)
        ws = sh.worksheet("実績")
        all_values = ws.get_all_values()

        # Row 1 (index 0): ヘッダー（D列以降が月）
        header = all_values[0]
        months = header[3:15]  # D〜O列 = 12ヶ月

        data = {}
        for row in all_values[1:]:
            label = row[2].strip() if len(row) > 2 else ""
            if not label:
                continue
            values = []
            for cell in row[3:15]:
                values.append(self._parse_number(cell))
            data[label] = values

        print(f"[Sheets] 売上データ読み込み完了: {len(data)}行 × {len(months)}ヶ月")
        return {"months": months, "data": data}

    # セグメント別売上行（予実シート）
    SEGMENT_SALES_ROWS = {
        "SDR": "SDR_月次新規獲得売上",
        "BDR": "BDR_月次新規獲得売上",
        "ALLI": "ALLI_月次新規獲得売上",
        "CCS": "CCS_保有MRR",          # CS本部は保有MRR（守っている売上）で評価
        "UNI": "UNI_月次新規獲得売上",
        "UCS": "UCS_保有MRR",          # UNION CSも保有MRRで評価
        "事業開発": "SH_合計売上",
        "COM": "COM_合計収益",
        # Watchyは別スプシ — read_segment_sales で個別対応
    }

    def read_segment_sales(self, month: int) -> dict[str, int]:
        """予実シートからセグメント別の月次売上実績を取得

        Args:
            month: 対象月（1〜12）

        Returns:
            {"SDR": 5534000, "BDR": 4750000, ...}（円単位）
        """
        sh = self._gc.open_by_key(SALES_SHEET_ID)
        ws = sh.get_worksheet_by_id(SALES_YOJITSU_GID)
        all_values = ws.get_all_values()

        # 月ごとに4列（予算/実績/予算差異/達成率）、D列(index 3)が1月予算
        # 実績列 = 3 + (month-1)*4 + 1 = 4 + (month-1)*4
        actual_col = 4 + (month - 1) * 4  # 0-based

        # C列(index 2)でKPI行ラベルを検索
        label_to_value = {}
        for row in all_values:
            label = row[2].strip() if len(row) > 2 else ""
            if label and actual_col < len(row):
                label_to_value[label] = self._parse_number(row[actual_col])

        result = {}
        for seg, label in self.SEGMENT_SALES_ROWS.items():
            val = label_to_value.get(label, 0)
            result[seg] = int(val * 1000)  # 千円→円

        # BCC（ビジネス共創部）: COMタブの実績セクション内 ALLI_月次新規獲得売上
        try:
            com_ws = sh.get_worksheet_by_id(103384075)  # COMタブ
            com_values = com_ws.get_all_values()
            bcc_col = 3 + month  # E=4(1月), F=5(2月)... 0-based
            in_actual = False
            in_bcc = False
            for row in com_values:
                a_val = row[0].strip() if len(row) > 0 else ""
                b_val = row[1].strip() if len(row) > 1 else ""
                c_val = row[2].strip() if len(row) > 2 else ""
                if "実績" in a_val:
                    in_actual = True
                if in_actual and "ビジネス共創部" in b_val:
                    in_bcc = True
                elif in_bcc and b_val and "ビジネス共創部" not in b_val:
                    in_bcc = False
                if in_bcc and "ALLI_月次新規獲得売上" in c_val:
                    if bcc_col < len(row):
                        result["BCC"] = int(self._parse_number(row[bcc_col]) * 1000)
                    break
        except Exception as e:
            print(f"[Sheets] BCC売上取得エラー: {e}")

        print(f"[Sheets] セグメント別売上読み込み完了: {month}月 | {', '.join(f'{k}={v//1000}K' for k, v in result.items() if v > 0)}")
        return result

    def write_roi_summary(
        self, roi_df, year: int, month: int, overall_roi: float
    ) -> None:
        """ROI集計結果を出力先シートに書き込み

        Args:
            roi_df: build_roi_table() の結果（DataFrame）
            year: 対象年
            month: 対象月
            overall_roi: 全体ROI
        """
        sh = self._gc.open_by_key(OUTPUT_SHEET_ID)

        sheet_title = f"ROI_{year}年{month:02d}月"

        try:
            ws = sh.worksheet(sheet_title)
            ws.clear()
            print(f"[Sheets] 既存シート '{sheet_title}' をクリア")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title=sheet_title, rows=20, cols=6)
            print(f"[Sheets] 新規シート '{sheet_title}' を作成")

        # ヘッダー + データ
        headers = ["セグメント", "旅費交通費", "売上", "ROI"]
        data = [headers]
        for _, row in roi_df.iterrows():
            data.append([
                row["セグメント"],
                int(row["旅費交通費"]),
                int(row["売上"]),
                round(float(row["ROI"]), 1),
            ])

        # 合計行
        data.append([
            "合計",
            int(roi_df["旅費交通費"].sum()),
            int(roi_df["売上"].sum()),
            round(overall_roi, 1),
        ])

        ws.update(range_name="A1", values=data)
        print(f"[Sheets] ROI書き込み完了: {len(roi_df)}セグメント（{sheet_title}）")

    # 稟議シートV列 → 振替カテゴリのマッピング
    RINGI_CATEGORY_MAP: dict[str, str] = {
        "広告費": "ad",
        "採用費": "recruit",
        "広告費採用費": "ad",  # 両方含む場合は広告費寄せ
    }

    # I列タイトル/J列内容からの振替判定キーワード
    RINGI_KEYWORD_RULES: list[tuple[list[str], str]] = [
        (["EXPO", "展示会", "出展"], "ad"),       # 広告宣伝費
        (["採用イベント", "採用説明会"], "recruit"),  # 採用費
    ]

    def read_ringi_lookup(self) -> dict[str, str]:
        """稟議一覧シートから 利用ID → 振替分類 のルックアップを生成

        判定優先順位:
        1. V列（広告費・採用費・その他）に値がある → そのまま使う
        2. V列が空 → I列（タイトル）+ J列（内容）のキーワードで判定

        Returns:
            {"35990549": "ad", "34761210": "recruit", ...}
        """
        sh = self._gc.open_by_key(RINGI_SHEET_ID)
        ws = sh.get_worksheet_by_id(RINGI_SHEET_GID)

        # B列(利用ID), I列(タイトル), J列(内容), V列(広告費・採用費・その他)
        # ヘッダーは8行目、データは9行目以降
        # B=col0, I=col7, J=col8, V=col20 (B9:Vの範囲内)
        data = ws.get_values("B9:V")

        result = {}
        keyword_matched = 0
        for row in data:
            rid = row[0].strip() if len(row) > 0 and row[0] else ""
            if not rid:
                continue

            v_col = row[20].strip() if len(row) > 20 and row[20] else ""

            # 1. V列で判定
            if v_col:
                category = self.RINGI_CATEGORY_MAP.get(v_col)
                if category:
                    result[rid] = category
                continue

            # 2. V列が空 → I列(タイトル) + J列(内容) のキーワード判定
            title = row[7].strip() if len(row) > 7 else ""
            content = row[8].strip() if len(row) > 8 else ""
            text = f"{title} {content}"

            for keywords, cat in self.RINGI_KEYWORD_RULES:
                if any(kw in text for kw in keywords):
                    result[rid] = cat
                    keyword_matched += 1
                    break

        v_count = len(result) - keyword_matched
        print(f"[Sheets] 稟議ルックアップ読み込み完了: {len(result)}件（V列={v_count}, キーワード={keyword_matched}）")
        return result

    def write_segment_roi(
        self,
        result_rows: list[dict],
        year: int,
        month: int,
    ) -> None:
        """セグメント別ROI集計結果を「部門別ROI」タブに書き込み

        Args:
            result_rows: 売上・ROI付きのセグメント別集計結果
            year: 対象年
            month: 対象月
        """
        from gspread_formatting import (
            CellFormat, Color, TextFormat, NumberFormat,
            format_cell_range, set_frozen, Borders, Border,
        )

        sh = self._gc.open_by_key(OUTPUT_SHEET_ID)
        tab_title = "部門別ROI"

        try:
            ws = sh.worksheet(tab_title)
            ws.clear()
            ws.format("A1:J100", {
                "backgroundColor": {"red": 1, "green": 1, "blue": 1},
                "textFormat": {"bold": False, "foregroundColor": {"red": 0, "green": 0, "blue": 0}, "fontSize": 10},
            })
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title=tab_title, rows=100, cols=12)

        title = f"{year}年{month}月 セグメント別ROI"
        headers = ["セグメント", "人数", "新幹線", "在来線", "車移動", "飛行機", "宿泊費", "旅費合計", "売上", "ROI"]

        values = [[title] + [""] * (len(headers) - 1)]
        values.append(headers)

        for r in result_rows:
            values.append([
                r["department"],
                r["headcount"],
                r["shinkansen"],
                r["train"],
                r["car"],
                r["airplane"],
                r["hotel"],
                r["total"],
                r["sales"],
                r["roi"],
            ])

        # 合計行
        total_expense = sum(r["total"] for r in result_rows)
        total_sales = sum(r["sales"] for r in result_rows)
        values.append([
            "合計",
            sum(r["headcount"] for r in result_rows),
            sum(r["shinkansen"] for r in result_rows),
            sum(r["train"] for r in result_rows),
            sum(r["car"] for r in result_rows),
            sum(r["airplane"] for r in result_rows),
            sum(r["hotel"] for r in result_rows),
            total_expense,
            total_sales,
            round(total_sales / total_expense, 1) if total_expense > 0 else 0,
        ])

        ws.update(range_name="A1", values=values)

        # --- 書式設定 ---
        last_row = len(values)
        header_bg = Color(0.22, 0.46, 0.85)
        header_text = Color(1, 1, 1)
        total_bg = Color(0.95, 0.97, 0.99)
        border_color = Color(0.82, 0.85, 0.89)
        thin_border = Border("SOLID", color=border_color)
        all_borders = Borders(top=thin_border, bottom=thin_border, left=thin_border, right=thin_border)

        # タイトル行
        format_cell_range(ws, "A1:J1", CellFormat(
            textFormat=TextFormat(bold=True, fontSize=12),
        ))

        # ヘッダー行 (Row 2): 青背景 + 白文字
        format_cell_range(ws, "A2:J2", CellFormat(
            backgroundColor=header_bg,
            textFormat=TextFormat(bold=True, foregroundColor=header_text, fontSize=10),
            horizontalAlignment="CENTER",
            borders=all_borders,
        ))

        # データ行: 数値フォーマット + ボーダー
        if last_row > 2:
            # 部門列 (A)
            format_cell_range(ws, f"A3:A{last_row}", CellFormat(
                borders=all_borders,
            ))
            # 人数列 (B)
            format_cell_range(ws, f"B3:B{last_row}", CellFormat(
                numberFormat=NumberFormat(type="NUMBER", pattern="#,##0"),
                horizontalAlignment="CENTER",
                borders=all_borders,
            ))
            # 金額列 (C-I)
            format_cell_range(ws, f"C3:I{last_row}", CellFormat(
                numberFormat=NumberFormat(type="NUMBER", pattern="#,##0"),
                horizontalAlignment="RIGHT",
                borders=all_borders,
            ))
            # ROI列 (J)
            format_cell_range(ws, f"J3:J{last_row}", CellFormat(
                numberFormat=NumberFormat(type="NUMBER", pattern="#,##0.0"),
                horizontalAlignment="RIGHT",
                borders=all_borders,
            ))
            # 合計行: 太字 + 背景色
            format_cell_range(ws, f"A{last_row}:J{last_row}", CellFormat(
                backgroundColor=total_bg,
                textFormat=TextFormat(bold=True),
                borders=all_borders,
            ))

        set_frozen(ws, rows=2, cols=1)

        print(f"[Sheets] セグメント別ROIタブ書き込み完了: {len(result_rows)}セグメント")

    @staticmethod
    def _parse_number(value: str) -> float:
        """数値文字列をfloatに変換（カンマ対応）"""
        if not value:
            return 0.0
        s = str(value).strip().replace(",", "").replace("，", "")
        try:
            return float(s)
        except ValueError:
            return 0.0


def normalize_name(name: str) -> str:
    """名前を正規化（全角/半角スペース統一、前後空白除去）"""
    # 全角スペースを半角に統一
    name = name.replace("\u3000", " ")
    # 連続する空白を1つに
    name = re.sub(r"\s+", " ", name)
    return name.strip()
