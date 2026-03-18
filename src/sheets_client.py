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
    SALES_SHEET_ID,
)


class SheetsClient:
    """Google Sheets 読み書きクライアント（サービスアカウント認証）"""

    def __init__(self):
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

    def read_ex_card_master(self) -> tuple[dict[str, str], set[str]]:
        """EXカード管理シートを読み込み、会員ID→現カード所持者マッピングを返す

        ※毎月所持者が変わる可能性があるため、集計前に必ず最新を読み込むこと

        Returns:
            (holder_map, exclude_ids)
            holder_map: {"6943717236": "丸岡 智泰", ...}
            exclude_ids: I列が除外対象の会員IDセット
        """
        # I列がこれらの値のカードは集計から除外
        EXCLUDE_CATEGORIES = {"広告関連貸出用", "福利厚生関連貸出用", "採用関連貸出用", "未定"}

        sh = self._gc.open_by_key(EX_CARD_MASTER_SHEET_ID)
        ws = sh.get_worksheet_by_id(EX_CARD_MASTER_GID)
        all_values = ws.get_all_values()

        # Row 7 (index 7) がヘッダー: col2=会員ID, col7=現カード所持者(氏名), col8=集計種別
        result = {}
        exclude_ids: set[str] = set()
        for row in all_values[8:]:  # Row 8以降がデータ
            member_id = row[2].strip() if len(row) > 2 else ""
            holder = row[7].strip() if len(row) > 7 else ""
            category = row[8].strip() if len(row) > 8 else ""
            if not member_id:
                continue
            result[member_id] = holder
            if category in EXCLUDE_CATEGORIES:
                exclude_ids.add(member_id)

        print(f"[Sheets] EXカードマスタ読み込み完了: {len(result)}件（除外: {len(exclude_ids)}件）")
        return result, exclude_ids

    def write_expense_summary(
        self, rows: list[dict], year: int, month: int
    ) -> None:
        """集計結果を出力先シートに書き込み

        Args:
            rows: aggregator.summarize() の結果
            year: 対象年
            month: 対象月
        """
        sh = self._gc.open_by_key(OUTPUT_SHEET_ID)

        # シート名: "YYYY年MM月"
        sheet_title = f"{year}年{month:02d}月"

        # 既存シートを探す or 新規作成
        try:
            ws = sh.worksheet(sheet_title)
            ws.clear()
            print(f"[Sheets] 既存シート '{sheet_title}' をクリア")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title=sheet_title, rows=len(rows) + 10, cols=10)
            print(f"[Sheets] 新規シート '{sheet_title}' を作成")

        # ヘッダー
        headers = ["社員番号", "名前", "部署", "新幹線", "宿泊", "在来線", "その他", "合計"]

        # データ行
        data = [headers]
        for r in rows:
            data.append([
                r.get("emp_no", ""),
                r.get("name", ""),
                r.get("department", ""),
                r.get("shinkansen", 0),
                r.get("hotel", 0),
                r.get("train", 0),
                r.get("other", 0),
                r.get("total", 0),
            ])

        ws.update(range_name="A1", values=data)
        print(f"[Sheets] 書き込み完了: {len(rows)}行")


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
