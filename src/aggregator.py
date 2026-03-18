"""旅費集計 — 各ソースのデータを個人別・カテゴリ別に集計する"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict


def normalize_name(name: str) -> str:
    """名前を正規化（全角/半角スペース統一、前後空白除去）"""
    name = name.replace("\u3000", " ")
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def parse_amount(value: str | int | float) -> int:
    """金額文字列を整数に変換（カンマ・引用符・先頭ゼロ対応、符号保持）"""
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip().strip("'\"")
    s = s.replace(",", "").replace("，", "")
    if not s or not re.search(r"\d", s):
        return 0
    # 数値部分だけ抽出（マイナス符号を保持）
    m = re.search(r"-?[\d.]+", s)
    return int(float(m.group())) if m else 0


def tax_exclusive(amount: int) -> int:
    """税込金額を税抜（10%消費税除外）に変換"""
    return round(amount / 1.1)


class ExpenseAggregator:
    """旅費集計エンジン"""

    # 旧姓→現姓エイリアス（MF経費等で旧姓が使われるケース）
    NAME_ALIASES: dict[str, str] = {
        "宮尾 達登": "菊地 達登",
        "藤多 愛美": "渡邉 愛美",
        "下萩 ナツキ": "山内 ナツキ",
        "松本 柚奈": "安藤 柚奈",
        "梅田 友里江": "森澤 友里江",
        "市橋 渚": "松本 渚",
        "深谷 あゆ美": "植松 あゆ美",
        "高橋 優太": "髙橋 優太",
        "小澤 彩香": "藤澤 彩香",
        "ｶｽﾀﾏ-ｻｸｾｽ ﾖﾝ": "鈴置 さくら",
    }

    # EXカード会員ID → 所持者名のオーバーライド（管理シートより優先）
    EX_CARD_OVERRIDES: dict[str, str] = {
        "4859841980": "森川 智仁",          # 百五十部カード → COO森川
        "6859069977": "株式会社スタジアム",    # 営業一部カード → 子会社利用
        "9731504005": "株式会社スタジアム",    # 営業二部カード → 子会社利用
    }

    # 業務委託・退職者・インターン・子会社等（人員マスタ外だが集計対象）
    CONTRACTORS: dict[str, dict] = {
        "宍戸 未羽": {"emp_no": "-", "department": "事業開発部", "raw_name": "宍戸 未羽"},
        "鈴置 さくら": {"emp_no": "-", "department": "事業開発部", "raw_name": "鈴置 さくら"},
        "田中 誠人": {"emp_no": "-", "department": "事業開発部", "raw_name": "田中 誠人"},
        "石井 一史": {"emp_no": "-", "department": "事業開発部", "raw_name": "石井 一史"},
        "樽田 和弥": {"emp_no": "-", "department": "マーケティング1部", "raw_name": "樽田 和弥"},
        "株式会社スタジアム": {"emp_no": "-", "department": "株式会社スタジアム", "raw_name": "株式会社スタジアム"},
    }

    def __init__(
        self,
        dept_master: dict[str, dict],
        ex_card_master: dict[str, str] | None = None,
        ex_card_exclude_ids: set[str] | None = None,
        ex_card_category_map: dict[str, str] | None = None,
    ):
        """
        Args:
            dept_master: normalize_name(名前) -> {"emp_no", "department", "raw_name"}
            ex_card_master: 会員ID(10桁) -> 現カード所持者名（EXカード管理シート）
            ex_card_exclude_ids: 集計除外対象の会員IDセット
            ex_card_category_map: 会員ID -> 集計種別（広告関連貸出用/福利厚生関連貸出用/採用関連貸出用/個人貸与等）
        """
        self._master = dept_master
        self._ex_card_master = ex_card_master or {}
        self._ex_card_exclude_ids = ex_card_exclude_ids or set()
        self._ex_card_category_map = ex_card_category_map or {}
        # 業務委託メンバーをマスタに注入
        for name, info in self.CONTRACTORS.items():
            normalized = normalize_name(name)
            if normalized not in self._master:
                self._master[normalized] = info
        # name -> category -> amount
        self._data: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._unmatched: list[dict] = []

    def _add(self, name: str, category: str, amount: int, source: str) -> None:
        """内部: 1レコード追加"""
        normalized = normalize_name(name)
        if not normalized:
            return
        # エイリアス（旧姓→現姓）解決
        if normalized in self.NAME_ALIASES:
            normalized = normalize_name(self.NAME_ALIASES[normalized])
        # 完全一致で検索
        if normalized in self._master:
            self._data[normalized][category] += amount
            return
        # スペースなし名前のフォールバック（タイムズカー等）
        # マスタ側のスペースを除去して比較
        no_space = normalized.replace(" ", "")
        for master_name in self._master:
            if master_name.replace(" ", "") == no_space:
                self._data[master_name][category] += amount
                return
        self._unmatched.append({
            "name": name,
            "normalized": normalized,
            "category": category,
            "amount": amount,
            "source": source,
        })

    # 集計種別 → 仕訳カテゴリのマッピング
    EX_CATEGORY_ACCOUNT_MAP: dict[str, str] = {
        "個人貸与": "shinkansen",
        "広告関連貸出用": "shinkansen_ad",
        "福利厚生関連貸出用": "shinkansen_welfare",
        "採用関連貸出用": "shinkansen_recruit",
        "部門貸出用": "shinkansen_subsidiary",
    }

    def add_ex_card(self, records: list[dict]) -> None:
        """EXカードデータ → 集計種別に応じたカテゴリ

        CSV fields: 会員ID, 会員氏名, 購入(請求)
        会員ID → EXカード管理シートの「現カード所持者」で本人名を解決
        集計種別 → 広告/福利厚生/採用/個人貸与で勘定科目を振り分け
        """
        resolved = 0
        excluded = 0
        for r in records:
            member_id = r.get("会員ID", "").strip().lstrip("'")
            raw_name = r.get("会員氏名", "").strip().lstrip("'")
            amount = tax_exclusive(parse_amount(r.get("購入(請求)", "0")))
            if amount == 0:
                continue
            # 除外対象カード（未定）はスキップ
            if member_id in self._ex_card_exclude_ids:
                excluded += 1
                continue
            # 集計種別に応じたカテゴリを決定
            card_category = self._ex_card_category_map.get(member_id, "個人貸与")
            expense_category = self.EX_CATEGORY_ACCOUNT_MAP.get(card_category, "shinkansen")
            # カード単位のオーバーライド（管理シートより優先）
            if member_id in self.EX_CARD_OVERRIDES:
                self._add(self.EX_CARD_OVERRIDES[member_id], expense_category, amount, "EXカード")
                resolved += 1
                continue
            # EXカードマスタで所持者名を解決
            holder = self._ex_card_master.get(member_id, "")
            if holder:
                self._add(holder, expense_category, amount, "EXカード")
                resolved += 1
            else:
                # マスタに未登録の会員ID → unmatchedへ
                self._add(raw_name, expense_category, amount, "EXカード")
        if self._ex_card_master:
            print(f"  EXカードマスタで名前解決: {resolved}/{len(records)}件")
        if excluded:
            print(f"  EXカード除外（貸出用等）: {excluded}件")

    def add_mf_expense(self, records: list[dict]) -> None:
        """MF経費データ → 科目名でカテゴリ振り分け

        records: get_travel_expenses() の返り値
        """
        for r in records:
            name = r.get("name", "")
            amount = tax_exclusive(r.get("amount", 0))
            category = r.get("category", "other")
            if amount == 0:
                continue
            self._add(name, category, amount, "MF経費")

    def add_racco(self, records: list[dict]) -> None:
        """Raccoデータ → 宿泊カテゴリ

        CSV fields: 予約者名(漢字), 宿泊代表者名(ひらがな), 宿泊金額
        予約者名（漢字）を優先。なければ宿泊代表者名（ひらがな）にフォールバック
        """
        for r in records:
            name = r.get("予約者名", "").strip()
            if not name:
                name = r.get("宿泊代表者名", "").strip()
            amount = tax_exclusive(parse_amount(r.get("宿泊金額", "0")))
            if amount == 0:
                continue
            self._add(name, "hotel", amount, "Racco")

    def add_jalan(self, records: list[dict]) -> None:
        """じゃらんデータ → 宿泊カテゴリ

        CSV fields: 宿泊代表者名（姓・漢字）, 宿泊代表者名（名・漢字）, 精算料金
        ※キャンセル済みは除外
        """
        for r in records:
            status = r.get("予約ステータス", "")
            if "キャンセル" in status:
                continue
            sei = r.get("宿泊代表者名（姓・漢字）", "").strip()
            mei = r.get("宿泊代表者名（名・漢字）", "").strip()
            name = f"{sei} {mei}" if sei and mei else sei or mei
            amount = tax_exclusive(parse_amount(r.get("精算料金", "0")))
            if amount == 0:
                continue
            self._add(name, "hotel", amount, "じゃらん")

    def add_times_car(self, records: list[dict]) -> None:
        """タイムズカーデータ → その他カテゴリ

        CSV fields: 会員名, 請求金額
        """
        for r in records:
            name = r.get("会員名", "").strip()
            amount = tax_exclusive(parse_amount(r.get("請求金額", "0")))
            if amount == 0:
                continue
            self._add(name, "other", amount, "タイムズカー")

    def summarize(self) -> list[dict]:
        """個人別集計結果を返す

        Returns:
            [{emp_no, name, department, shinkansen, hotel, train, other, total}, ...]
            合計降順ソート
        """
        rows = []
        for normalized_name, categories in self._data.items():
            info = self._master[normalized_name]
            shinkansen = categories.get("shinkansen", 0)
            shinkansen_ad = categories.get("shinkansen_ad", 0)
            shinkansen_welfare = categories.get("shinkansen_welfare", 0)
            shinkansen_recruit = categories.get("shinkansen_recruit", 0)
            shinkansen_subsidiary = categories.get("shinkansen_subsidiary", 0)
            hotel = categories.get("hotel", 0)
            train = categories.get("train", 0)
            other = categories.get("other", 0)
            total = shinkansen + shinkansen_ad + shinkansen_welfare + shinkansen_recruit + shinkansen_subsidiary + hotel + train + other
            rows.append({
                "emp_no": info["emp_no"],
                "name": info["raw_name"],
                "department": info["department"],
                "shinkansen": shinkansen,
                "shinkansen_ad": shinkansen_ad,
                "shinkansen_welfare": shinkansen_welfare,
                "shinkansen_recruit": shinkansen_recruit,
                "shinkansen_subsidiary": shinkansen_subsidiary,
                "hotel": hotel,
                "train": train,
                "other": other,
                "total": total,
            })
        rows.sort(key=lambda x: x["total"], reverse=True)
        return rows

    def get_unmatched(self) -> list[dict]:
        """部署マスタとマッチしなかったレコードを返す"""
        # 重複排除（同一名・同一ソース）
        seen = set()
        unique = []
        for item in self._unmatched:
            key = (item["normalized"], item["source"])
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique
