"use client";

import { useState } from "react";
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

export default function AggregateTab() {
  const [year, setYear] = useState(defaultYear);
  const [month, setMonth] = useState(defaultMonth);
  const storageKey = `aggregate-v2-${year}-${String(month).padStart(2, "0")}`;
  const seedUrl = `/aggregate-result-${year}-${String(month).padStart(2, "0")}.json`;
  const { result, fetchedAt } = usePersistedResult<AggregateResponse>(storageKey, seedUrl);
  const [scope, setScope] = useState<(typeof SCOPES)[number]>("全体");

  const filtered = result?.summary
    ? scope === "スタメン単体"
      ? result.summary.filter((r) => r.department !== "株式会社スタジアム")
      : scope === "スタジアム単体"
        ? result.summary.filter((r) => r.department === "株式会社スタジアム")
        : result.summary
    : [];

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
                  新幹線 <span className="font-semibold text-[var(--foreground)] ml-1">{yen(totals.shinkansen)}</span>
                </span>
                <span className="text-[var(--muted)]">
                  宿泊 <span className="font-semibold text-[var(--foreground)] ml-1">{yen(totals.hotel)}</span>
                </span>
                <span className="text-[var(--muted)]">
                  在来線 <span className="font-semibold text-[var(--foreground)] ml-1">{yen(totals.train)}</span>
                </span>
                <span className="text-[var(--muted)]">
                  その他 <span className="font-semibold text-[var(--foreground)] ml-1">{yen(totals.other)}</span>
                </span>
                <span className="text-[var(--muted)]">
                  {filtered.length}名
                </span>
              </div>
            </div>

            {/* テーブル */}
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-[var(--border)] text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider">
                    <th className="px-5 py-2.5 text-left">社員番号</th>
                    <th className="px-5 py-2.5 text-left">名前</th>
                    <th className="px-5 py-2.5 text-left">部署</th>
                    <th className="px-5 py-2.5 text-right">新幹線</th>
                    <th className="px-5 py-2.5 text-right">宿泊</th>
                    <th className="px-5 py-2.5 text-right">在来線</th>
                    <th className="px-5 py-2.5 text-right">その他</th>
                    <th className="px-5 py-2.5 text-right">合計</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r, i) => (
                    <tr
                      key={i}
                      className="border-b border-[var(--border)] last:border-0 hover:bg-slate-50/50 transition"
                    >
                      <td className="px-5 py-2 text-[var(--muted-light)]">{r.emp_no}</td>
                      <td className="px-5 py-2 font-medium">{r.name}</td>
                      <td className="px-5 py-2 text-[var(--muted)]">{r.department}</td>
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
