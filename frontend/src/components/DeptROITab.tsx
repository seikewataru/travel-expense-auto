"use client";

import { useState, useMemo } from "react";
import { type DeptROIResponse } from "@/lib/api";
import { usePersistedResult } from "@/lib/usePersistedResult";
import MetricCard from "./MetricCard";
import YearMonthSelector from "./YearMonthSelector";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

const now = new Date();

function yen(n: number) {
  return `¥${n.toLocaleString()}`;
}

type SortKey = "department" | "headcount" | "shinkansen" | "train" | "car" | "airplane" | "hotel" | "total" | "sales" | "roi";
type SortDir = "asc" | "desc";

const COLUMNS: { key: SortKey; label: string; align: "left" | "right" }[] = [
  { key: "department", label: "部門", align: "left" },
  { key: "headcount", label: "人数", align: "right" },
  { key: "shinkansen", label: "新幹線", align: "right" },
  { key: "train", label: "在来線", align: "right" },
  { key: "car", label: "車移動", align: "right" },
  { key: "airplane", label: "飛行機", align: "right" },
  { key: "hotel", label: "宿泊費", align: "right" },
  { key: "total", label: "旅費合計", align: "right" },
  { key: "sales", label: "売上", align: "right" },
  { key: "roi", label: "ROI", align: "right" },
];

export default function DeptROITab() {
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(Math.max(1, now.getMonth()));
  const storageKey = `dept-roi-result-${year}-${String(month).padStart(2, "0")}`;
  const seedUrl = `/dept-roi-result-${year}-${String(month).padStart(2, "0")}.json`;
  const { result, fetchedAt } = usePersistedResult<DeptROIResponse>(storageKey, seedUrl);

  const [sortKey, setSortKey] = useState<SortKey>("total");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "department" ? "asc" : "desc");
    }
  };

  const toggleExpand = (dept: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(dept)) next.delete(dept);
      else next.add(dept);
      return next;
    });
  };

  const sorted = useMemo(() => {
    if (!result) return [];
    return [...result.departments].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "string" && typeof bv === "string") {
        return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
  }, [result, sortKey, sortDir]);

  const chartData = result?.departments.map((d) => ({
    name: d.department,
    旅費合計: d.total,
    売上: d.sales,
  }));

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold">部門別ROI</h2>
          <p className="text-xs text-[var(--muted)] mt-0.5">部門ごとの旅費ROIを分析します</p>
        </div>
      </div>

      {/* 年月選択 */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 flex items-center justify-between">
        <YearMonthSelector year={year} month={month} onYearChange={setYear} onMonthChange={setMonth} />
        {fetchedAt && (
          <span className="text-[11px] text-[var(--muted)]">集計日: {fetchedAt}</span>
        )}
      </div>

      {result && (
        <>
          {/* メトリクスカード */}
          <div className="grid grid-cols-3 gap-4">
            <MetricCard label="旅費合計" value={yen(result.totals.total_expense)} />
            <MetricCard label="売上合計" value={yen(result.totals.total_sales)} />
            <MetricCard
              label="全体ROI"
              value={`${result.totals.overall_roi}x`}
              accent={result.totals.overall_roi >= 50 ? "success" : result.totals.overall_roi >= 10 ? "primary" : "warning"}
            />
          </div>

          {/* テーブル */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] overflow-hidden">
            <div className="px-5 py-3 border-b border-[var(--border)] bg-slate-50/50">
              <span className="text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider">
                部門別ROI
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-[var(--border)] text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider">
                    <th className="w-8" />
                    {COLUMNS.map((col) => (
                      <th
                        key={col.key}
                        onClick={() => handleSort(col.key)}
                        className={`px-5 py-2.5 cursor-pointer select-none hover:text-[var(--foreground)] transition ${
                          col.align === "left" ? "text-left" : "text-right"
                        }`}
                      >
                        {col.label}
                        {sortKey === col.key && (
                          <span className="ml-1">{sortDir === "asc" ? "▲" : "▼"}</span>
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((d, i) => {
                    const isExpanded = expanded.has(d.department);
                    const hasMembers = d.members && d.members.length > 0;
                    return (
                      <>
                        <tr
                          key={i}
                          className="border-b border-[var(--border)] last:border-0 hover:bg-slate-50/50 transition"
                        >
                          <td className="pl-3 py-2.5 text-center">
                            {hasMembers && (
                              <button
                                onClick={() => toggleExpand(d.department)}
                                className="text-[var(--muted)] hover:text-[var(--foreground)] transition text-xs w-5 h-5 flex items-center justify-center rounded hover:bg-slate-100"
                              >
                                {isExpanded ? "−" : "+"}
                              </button>
                            )}
                          </td>
                          <td className="px-5 py-2.5 font-medium">{d.department}</td>
                          <td className="px-5 py-2.5 text-right tabular-nums">{d.headcount}</td>
                          <td className="px-5 py-2.5 text-right tabular-nums">{d.shinkansen ? yen(d.shinkansen) : "—"}</td>
                          <td className="px-5 py-2.5 text-right tabular-nums">{d.train ? yen(d.train) : "—"}</td>
                          <td className="px-5 py-2.5 text-right tabular-nums">{d.car ? yen(d.car) : "—"}</td>
                          <td className="px-5 py-2.5 text-right tabular-nums">{d.airplane ? yen(d.airplane) : "—"}</td>
                          <td className="px-5 py-2.5 text-right tabular-nums">{d.hotel ? yen(d.hotel) : "—"}</td>
                          <td className="px-5 py-2.5 text-right font-semibold tabular-nums">{yen(d.total)}</td>
                          <td className="px-5 py-2.5 text-right tabular-nums">{yen(d.sales)}</td>
                          <td className="px-5 py-2.5 text-right font-semibold tabular-nums">
                            <span className={d.roi >= 50 ? "text-[var(--success)]" : d.roi >= 10 ? "text-[var(--primary)]" : "text-[var(--muted)]"}>
                              {d.roi}x
                            </span>
                          </td>
                        </tr>
                        {isExpanded && d.members?.map((m, j) => (
                          <tr
                            key={`${i}-${j}`}
                            className="border-b border-[var(--border)] bg-slate-50/30"
                          >
                            <td />
                            <td className="px-5 py-1.5 pl-10 text-[12px] text-[var(--muted)]">{m.name}</td>
                            <td />
                            <td className="px-5 py-1.5 text-right text-[12px] tabular-nums text-[var(--muted)]">{m.shinkansen ? yen(m.shinkansen) : "—"}</td>
                            <td className="px-5 py-1.5 text-right text-[12px] tabular-nums text-[var(--muted)]">{m.train ? yen(m.train) : "—"}</td>
                            <td className="px-5 py-1.5 text-right text-[12px] tabular-nums text-[var(--muted)]">{m.car ? yen(m.car) : "—"}</td>
                            <td className="px-5 py-1.5 text-right text-[12px] tabular-nums text-[var(--muted)]">{m.airplane ? yen(m.airplane) : "—"}</td>
                            <td className="px-5 py-1.5 text-right text-[12px] tabular-nums text-[var(--muted)]">{m.hotel ? yen(m.hotel) : "—"}</td>
                            <td className="px-5 py-1.5 text-right text-[12px] font-medium tabular-nums text-[var(--muted)]">{yen(m.total)}</td>
                            <td />
                            <td />
                          </tr>
                        ))}
                      </>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* グラフ */}
          {chartData && chartData.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
              <p className="text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider mb-4">
                部門別 旅費合計 vs 売上
              </p>
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={chartData} barGap={4}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: "var(--muted)" }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "var(--muted)" }} axisLine={false} tickLine={false} tickFormatter={(v) => `${(v / 10000).toFixed(0)}万`} />
                  <Tooltip
                    formatter={(value) => yen(Number(value))}
                    contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--border)" }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="旅費合計" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="売上" fill="var(--primary)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  );
}
