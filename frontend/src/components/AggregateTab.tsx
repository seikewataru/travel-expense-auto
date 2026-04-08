"use client";

import { useState, useMemo } from "react";
import { type AggregateResponse } from "@/lib/api";
import { usePersistedResult } from "@/lib/usePersistedResult";
import YearMonthSelector from "./YearMonthSelector";

const now = new Date();
const defaultYear = now.getFullYear();
const defaultMonth = Math.max(1, now.getMonth());

const SCOPES = ["全体", "スタメン単体", "スタジアム単体"] as const;

function yen(n: number) {
  return `¥${n.toLocaleString()}`;
}

type SortKey = "emp_no" | "name" | "department" | "shinkansen" | "hotel" | "train" | "other" | "total";
type SortDir = "asc" | "desc";

const COLUMNS: { key: SortKey; label: string; align: "left" | "right" }[] = [
  { key: "emp_no", label: "社員番号", align: "left" },
  { key: "name", label: "名前", align: "left" },
  { key: "department", label: "部署", align: "left" },
  { key: "shinkansen", label: "新幹線", align: "right" },
  { key: "hotel", label: "宿泊", align: "right" },
  { key: "train", label: "在来線", align: "right" },
  { key: "other", label: "その他", align: "right" },
  { key: "total", label: "合計", align: "right" },
];

export default function AggregateTab() {
  const [year, setYear] = useState(defaultYear);
  const [month, setMonth] = useState(defaultMonth);
  const storageKey = `aggregate-v3-${year}-${String(month).padStart(2, "0")}`;
  const seedUrl = `/aggregate-result-${year}-${String(month).padStart(2, "0")}.json`;
  const { result, fetchedAt } = usePersistedResult<AggregateResponse>(storageKey, seedUrl);
  const [scope, setScope] = useState<(typeof SCOPES)[number]>("全体");
  const [sortKey, setSortKey] = useState<SortKey>("department");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "name" || key === "department" || key === "emp_no" ? "asc" : "desc");
    }
  };

  // PLベース: _ad, _welfare, _recruit, _subsidiary を除外した通常分のみ
  const plBase = (r: Record<string, unknown>) => {
    const shinkansen = (r.shinkansen as number) || 0;
    const hotel = (r.hotel as number) || 0;
    const train = (r.train as number) || 0;
    const car = (r.car as number) || 0;
    const airplane = (r.airplane as number) || 0;
    const other = (r.other as number) || 0;
    return {
      shinkansen, hotel, train, other: car + airplane + other,
      total: shinkansen + hotel + train + car + airplane + other,
    };
  };

  const filtered = useMemo(() => {
    if (!result?.summary) return [];
    const scoped = scope === "スタメン単体"
      ? result.summary.filter((r) => r.department !== "株式会社スタジアム")
      : scope === "スタジアム単体"
        ? result.summary.filter((r) => r.department === "株式会社スタジアム")
        : result.summary;
    return scoped
      .map((r) => ({ ...r, ...plBase(r) }))
      .filter((r) => r.total > 0);
  }, [result, scope]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      // 部署ソート時は部署名→合計降順の二段ソート
      if (sortKey === "department") {
        const cmp = sortDir === "asc" ? a.department.localeCompare(b.department) : b.department.localeCompare(a.department);
        if (cmp !== 0) return cmp;
        return b.total - a.total;
      }
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "string" && typeof bv === "string") {
        return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
  }, [filtered, sortKey, sortDir]);

  const totals = filtered.reduce(
    (acc, r) => ({
      shinkansen: acc.shinkansen + r.shinkansen,
      hotel: acc.hotel + r.hotel,
      train: acc.train + r.train,
      other: acc.other + r.other,
      total: acc.total + r.total,
    }),
    { shinkansen: 0, hotel: 0, train: 0, other: 0, total: 0 }
  );

  return (
    <div className="space-y-5">
      {/* ページヘッダー */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold">旅費集計</h2>
          <p className="text-xs text-[var(--muted)] mt-0.5">月次の旅費交通費を集計します</p>
        </div>
      </div>

      {/* 年月選択 */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 flex items-center justify-between">
        <YearMonthSelector year={year} month={month} onYearChange={setYear} onMonthChange={setMonth} />
        {fetchedAt && (
          <span className="text-[11px] text-[var(--muted)]">集計日: {fetchedAt}</span>
        )}
      </div>

      {/* 結果 */}
      {result && filtered.length > 0 && (
        <>
          {/* スコープ + サマリ帯 */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] overflow-hidden">
            {/* スコープ切替 */}
            <div className="flex items-center gap-4 px-5 py-3 border-b border-[var(--border)] bg-slate-50/50">
              <span className="text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider">表示範囲</span>
              <div className="flex gap-0.5 rounded-lg bg-[var(--background)] p-0.5">
                {SCOPES.map((s) => (
                  <button
                    key={s}
                    onClick={() => setScope(s)}
                    className={`rounded-md px-3 py-1 text-xs font-medium transition ${
                      scope === s
                        ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm"
                        : "text-[var(--muted)] hover:text-[var(--foreground)]"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>

              {/* インラインメトリクス */}
              <div className="ml-auto flex items-center gap-6 text-xs">
                <span className="text-[var(--muted)]">
                  合計 <span className="font-bold text-[var(--foreground)] text-sm ml-1">{yen(totals.total)}</span>
                </span>
                <span className="text-[var(--muted)]">
                  {filtered.length}名
                </span>
              </div>
            </div>

            {/* テーブル */}
            <div className="overflow-x-auto">
              <table className="w-full text-[13px] min-w-[900px]">
                <thead>
                  <tr className="border-b border-[var(--border)] text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider">
                    {COLUMNS.map((col) => (
                      <th
                        key={col.key}
                        onClick={() => handleSort(col.key)}
                        className={`px-5 py-2.5 cursor-pointer select-none hover:text-[var(--foreground)] transition whitespace-nowrap ${
                          col.align === "left" ? "text-left" : "text-right"
                        }`}
                      >
                        {col.label}
                        <span className={`ml-0.5 text-[10px] ${sortKey === col.key ? "text-[var(--primary)]" : "opacity-20"}`}>
                          {sortKey === col.key
                            ? sortDir === "asc" ? "▲" : "▼"
                            : "▼"}
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((r, i) => (
                    <tr
                      key={i}
                      className="border-b border-[var(--border)] last:border-0 hover:bg-slate-50/50 transition"
                    >
                      <td className="px-5 py-2 text-[var(--muted-light)]">{r.emp_no}</td>
                      <td className="px-5 py-2 font-medium whitespace-nowrap">{r.name}</td>
                      <td className="px-5 py-2 text-[var(--muted)] whitespace-nowrap">{r.department}</td>
                      <td className="px-5 py-2 text-right tabular-nums">{r.shinkansen ? yen(r.shinkansen) : "—"}</td>
                      <td className="px-5 py-2 text-right tabular-nums">{r.hotel ? yen(r.hotel) : "—"}</td>
                      <td className="px-5 py-2 text-right tabular-nums">{r.train ? yen(r.train) : "—"}</td>
                      <td className="px-5 py-2 text-right tabular-nums">{r.other ? yen(r.other) : "—"}</td>
                      <td className="px-5 py-2 text-right font-semibold tabular-nums">{yen(r.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 未マッチ */}
          {result.unmatched.length > 0 && (
            <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-4">
              <p className="text-xs font-medium text-amber-700 mb-2">
                未マッチレコード — {result.unmatched.length}件
              </p>
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="text-left text-amber-600">
                    <th className="pr-4 py-1">名前</th>
                    <th className="pr-4 py-1">ソース</th>
                    <th className="pr-4 py-1">カテゴリ</th>
                    <th className="py-1 text-right">金額</th>
                  </tr>
                </thead>
                <tbody className="text-amber-800">
                  {result.unmatched.map((u, i) => (
                    <tr key={i}>
                      <td className="pr-4 py-0.5">{u.name}</td>
                      <td className="pr-4 py-0.5">{u.source}</td>
                      <td className="pr-4 py-0.5">{u.category}</td>
                      <td className="py-0.5 text-right">{yen(u.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* ログ */}
          {result.log.length > 0 && (
            <details className="rounded-xl border border-[var(--border)] bg-[var(--card)]">
              <summary className="cursor-pointer px-5 py-3 text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider">
                実行ログ（{result.log.length}件）
              </summary>
              <pre className="border-t border-[var(--border)] px-5 py-3 text-[11px] text-[var(--muted)] whitespace-pre-wrap font-mono">
                {result.log.join("\n")}
              </pre>
            </details>
          )}
        </>
      )}
    </div>
  );
}
