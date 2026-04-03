"""Google Sheets クライアント — 部署マスタ読み込み + 集計結果出力"""

from __future__ import annotations

import re

import gspread

from src.config import (
    DEPT_MASTER_SHEET_ID,
    EX_CARD_MASTER_GID,
    EX_CARD_MASTER_SHEET_ID,
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

    # ROIタブの月ごとのカラム構成（6列/月: 新幹線, 在来線, 車移動, 飛行機, 宿泊費, 合計）
    ROI_COLS_PER_MONTH = 6
    ROI_DATA_START_COL = 3  # D列 = index 3 (0-based)
    ROI_HEADER_ROW = 3      # Row 3 がカラムヘッダー
    ROI_DATA_START_ROW = 4  # Row 4 からデータ

    def write_expense_summary(
        self, rows: list[dict], year: int, month: int
    ) -> None:
        """集計結果をROIタブに書き込み（既存フォーマット準拠）

        ROIタブ構造:
          Row 1: 年ヘッダー
          Row 2: 月ヘッダー（D列=1月, J列=2月...各6列幅）
          Row 3: 新幹線, 在来線, 車移動, 飛行機, 宿泊費, 合計
          Row 4~: B=名前, C=部署, D~I=1月データ, J~O=2月データ...

        Args:
            rows: aggregator.summarize() の結果
            year: 対象年
            month: 対象月
        """
        sh = self._gc.open_by_key(OUTPUT_SHEET_ID)
        ws = sh.worksheet("ROI")

        # 対象月の開始列を計算（1月=D列(col4), 2月=J列(col10)...）
        month_col_start = self.ROI_DATA_START_COL + (month - 1) * self.ROI_COLS_PER_MONTH  # 0-based

        # 既存のB列（名前一覧）を取得
        all_values = ws.get_all_values()
        existing_names = {}  # normalize_name -> row_index (0-based)
        for i in range(self.ROI_DATA_START_ROW - 1, len(all_values)):
            name = all_values[i][1].strip() if len(all_values[i]) > 1 else ""
            if name:
                existing_names[normalize_name(name)] = i

        # 月ヘッダーを書き込み（Row 2 に月名）
        month_label = f"{month}月"
        # gspread のcol番号は1-based
        ws.update_cell(2, month_col_start + 1, month_label)

        # カラムヘッダー（Row 3）— 初回のみ書き込み（既に入っていれば上書き）
        col_headers = ["新幹線", "在来線", "車移動", "飛行機", "宿泊費", "合計"]
        header_cells = []
        for j, h in enumerate(col_headers):
            header_cells.append(gspread.Cell(
                self.ROI_HEADER_ROW,
                month_col_start + 1 + j,
                h,
            ))
        ws.update_cells(header_cells)

        # データ書き込み
        next_row = max(existing_names.values()) + 2 if existing_names else self.ROI_DATA_START_ROW
        cells_to_update = []

        for r in rows:
            name = r.get("name", "")
            normalized = normalize_name(name)
            if not normalized:
                continue

            # 既存行を探す or 新規行を追加
            if normalized in existing_names:
                row_idx = existing_names[normalized] + 1  # 1-based
            else:
                row_idx = next_row
                next_row += 1
                existing_names[normalized] = row_idx - 1
                # B列=名前, C列=部署を書き込み
                cells_to_update.append(gspread.Cell(row_idx, 1, r.get("emp_no", "")))
                cells_to_update.append(gspread.Cell(row_idx, 2, name))
                cells_to_update.append(gspread.Cell(row_idx, 3, r.get("department", "")))

            # 各カテゴリの値（振替含む合算）
            shinkansen_total = (r.get("shinkansen", 0) + r.get("shinkansen_ad", 0)
                                + r.get("shinkansen_welfare", 0) + r.get("shinkansen_recruit", 0)
                                + r.get("shinkansen_subsidiary", 0))
            train_total = r.get("train", 0) + r.get("train_ad", 0) + r.get("train_recruit", 0)
            car_total = r.get("car", 0) + r.get("car_ad", 0) + r.get("car_recruit", 0)
            airplane_total = r.get("airplane", 0) + r.get("airplane_ad", 0) + r.get("airplane_recruit", 0)
            hotel_total = r.get("hotel", 0) + r.get("hotel_ad", 0) + r.get("hotel_recruit", 0)
            # other は car/airplane 分離前の残り
            other_leftover = r.get("other", 0) + r.get("other_ad", 0) + r.get("other_recruit", 0)
            # other_leftover は車移動に加算（バス等）
            car_total += other_leftover
            row_total = shinkansen_total + train_total + car_total + airplane_total + hotel_total

            values = [shinkansen_total, train_total, car_total, airplane_total, hotel_total, row_total]
            for j, v in enumerate(values):
                cells_to_update.append(gspread.Cell(
                    row_idx,
                    month_col_start + 1 + j,
                    v if v != 0 else "",
                ))

        if cells_to_update:
            ws.update_cells(cells_to_update)

        # 書式設定
        self._format_roi_tab(ws, month_col_start, next_row - 1)

        print(f"[Sheets] ROIタブ書き込み完了: {len(rows)}名 → {month}月列")

    def _format_roi_tab(self, ws, month_col_start: int, last_data_row: int) -> None:
        """ROIタブの書式を設定"""
        from gspread_formatting import (
            CellFormat, Color, TextFormat, NumberFormat,
            format_cell_range, set_frozen, Borders, Border,
        )

        sheet_id = ws.id

        # 色定義
        header_bg = Color(0.22, 0.46, 0.85)     # 青 (#3876D9)
        header_text = Color(1, 1, 1)              # 白
        month_bg = Color(0.87, 0.92, 0.98)        # 薄い青 (#DEEBFA)
        total_bg = Color(0.95, 0.97, 0.99)        # 極薄い青 (#F2F8FE)
        name_bg = Color(0.98, 0.98, 0.98)         # 極薄グレー
        border_color = Color(0.82, 0.85, 0.89)    # ボーダーグレー

        thin_border = Border("SOLID", color=border_color)
        all_borders = Borders(top=thin_border, bottom=thin_border, left=thin_border, right=thin_border)

        # 月ヘッダーの列範囲（1-based col letter）
        def col_letter(col_0based):
            c = col_0based
            if c < 26:
                return chr(65 + c)
            return chr(64 + c // 26) + chr(65 + c % 26)

        start_col = col_letter(month_col_start)
        end_col = col_letter(month_col_start + self.ROI_COLS_PER_MONTH - 1)
        total_col_letter = end_col  # 合計列

        # Row 2 月ヘッダー: 青背景 + 白文字
        format_cell_range(ws, f"{start_col}2:{end_col}2", CellFormat(
            backgroundColor=header_bg,
            textFormat=TextFormat(bold=True, foregroundColor=header_text, fontSize=10),
            horizontalAlignment="CENTER",
            borders=all_borders,
        ))

        # Row 3 カラムヘッダー: 薄い青背景
        format_cell_range(ws, f"{start_col}3:{end_col}3", CellFormat(
            backgroundColor=month_bg,
            textFormat=TextFormat(bold=True, fontSize=9),
            horizontalAlignment="CENTER",
            borders=all_borders,
        ))

        # A〜C列ヘッダー（Row 3）: 薄い青背景
        format_cell_range(ws, "A3:C3", CellFormat(
            backgroundColor=month_bg,
            textFormat=TextFormat(bold=True, fontSize=9),
            borders=all_borders,
        ))

        # B列（名前）: 薄グレー背景
        if last_data_row >= self.ROI_DATA_START_ROW:
            format_cell_range(ws, f"A{self.ROI_DATA_START_ROW}:C{last_data_row}", CellFormat(
                backgroundColor=name_bg,
                borders=all_borders,
            ))

        # データセル: 数値フォーマット（カンマ区切り） + ボーダー
        if last_data_row >= self.ROI_DATA_START_ROW:
            data_range = f"{start_col}{self.ROI_DATA_START_ROW}:{end_col}{last_data_row}"
            format_cell_range(ws, data_range, CellFormat(
                numberFormat=NumberFormat(type="NUMBER", pattern="#,##0"),
                horizontalAlignment="RIGHT",
                borders=all_borders,
            ))

            # 合計列: 太字 + 薄い青背景
            total_range = f"{total_col_letter}{self.ROI_DATA_START_ROW}:{total_col_letter}{last_data_row}"
            format_cell_range(ws, total_range, CellFormat(
                backgroundColor=total_bg,
                textFormat=TextFormat(bold=True),
                numberFormat=NumberFormat(type="NUMBER", pattern="#,##0"),
                horizontalAlignment="RIGHT",
                borders=all_borders,
            ))

        # ヘッダー行を固定
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
        "UNI": "UNI_月次新規獲得売上",
        "法人": "法人_月次新規獲得売上",
        "CCS": "CCS_MRR",
        "事業開発": "SH_合計売上",
        "COM": "COM_合計収益",
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
        "広告費採用費": "ad",  # 両方含む場合は広告費寄せ（要確認）
    }

    def read_ringi_lookup(self) -> dict[str, str]:
        """稟議一覧シートから 利用ID → 振替分類 のルックアップを生成

        Returns:
            {"35990549": "ad", "34761210": "recruit", ...}
            V列が「その他」or 空 → ルックアップに含めない（旅費交通費のまま）
        """
        sh = self._gc.open_by_key(RINGI_SHEET_ID)
        ws = sh.get_worksheet_by_id(RINGI_SHEET_GID)

        # B列(利用ID)=col2, V列(広告費・採用費・その他)=col22
        # ヘッダーは8行目、データは9行目以降
        data = ws.get_values("B9:V")

        result = {}
        for row in data:
            rid = row[0].strip() if len(row) > 0 and row[0] else ""
            v_col = row[20].strip() if len(row) > 20 and row[20] else ""
            if not rid or not v_col:
                continue
            category = self.RINGI_CATEGORY_MAP.get(v_col)
            if category:
                result[rid] = category

        print(f"[Sheets] 稟議ルックアップ読み込み完了: {len(result)}件（広告費/採用費のみ）")
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
