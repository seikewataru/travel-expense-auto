"use client";

import { useState, useMemo, useEffect } from "react";
import { type DeptROIResponse, type DeptROIRow } from "@/lib/api";
import { usePersistedResult } from "@/lib/usePersistedResult";
import MetricCard from "./MetricCard";
import YearMonthSelector, { QUARTERS } from "./YearMonthSelector";
import {
  LineChart,
  Line,
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

type PeriodMode = "monthly" | "quarterly";
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

const OTHER_LABEL = "その他（非売上部門）";

/** 複数月のDeptROIResponseを合算する */
function mergeResults(results: (DeptROIResponse | null)[]): DeptROIResponse | null {
  const valid = results.filter((r): r is DeptROIResponse => r !== null);
  if (valid.length === 0) return null;
  if (valid.length === 1) return valid[0];

  // 部門別に合算（人数は重複排除のためmax）
  const deptMap = new Map<string, DeptROIRow>();
  const memberNamesMap = new Map<string, Set<string>>();

  for (const res of valid) {
    for (const d of res.departments) {
      const existing = deptMap.get(d.department);
      if (existing) {
        existing.shinkansen += d.shinkansen;
        existing.train += d.train;
        existing.car += d.car;
        existing.airplane += d.airplane;
        existing.hotel += d.hotel;
        existing.total += d.total;
        existing.sales += d.sales;
        // 人数は各月の最大値（同一人物が毎月いるため）
        existing.headcount = Math.max(existing.headcount, d.headcount);
        // メンバーをマージ（名前で重複排除、金額は合算）
        if (d.members) {
          const memberMap = new Map<string, typeof d.members[0]>();
          for (const m of existing.members ?? []) {
            memberMap.set(m.name, { ...m });
          }
          for (const m of d.members) {
            const ex = memberMap.get(m.name);
            if (ex) {
              ex.shinkansen += m.shinkansen;
              ex.train += m.train;
              ex.car += m.car;
              ex.airplane += m.airplane;
              ex.hotel += m.hotel;
              ex.total += m.total;
            } else {
              memberMap.set(m.name, { ...m });
            }
          }
          existing.members = Array.from(memberMap.values());
        }
      } else {
        deptMap.set(d.department, {
          ...d,
          members: d.members?.map((m) => ({ ...m })),
        });
      }
    }
  }

  const departments = Array.from(deptMap.values());
  // ROI再計算
  for (const d of departments) {
    d.roi = d.total > 0 ? Math.round((d.sales / d.total) * 10) / 10 : 0;
    d.members?.sort((a, b) => b.total - a.total);
  }

  const total_expense = departments.reduce((s, d) => s + d.total, 0);
  const total_sales = departments.reduce((s, d) => s + d.sales, 0);

  return {
    departments,
    totals: {
      total_expense,
      total_sales,
      overall_roi: total_expense > 0 ? Math.round((total_sales / total_expense) * 10) / 10 : 0,
    },
  };
}

function useQuarterlyData(year: number, quarter: number) {
  const months = QUARTERS.find((q) => q.key === quarter)?.months ?? [1, 2, 3];
  const m1 = months[0], m2 = months[1], m3 = months[2];

  const sk = (m: number) => `dept-roi-v7-${year}-${String(m).padStart(2, "0")}`;
  const su = (m: number) => `/dept-roi-result-${year}-${String(m).padStart(2, "0")}.json`;

  const { result: r1 } = usePersistedResult<DeptROIResponse>(sk(m1), su(m1));
  const { result: r2 } = usePersistedResult<DeptROIResponse>(sk(m2), su(m2));
  const { result: r3 } = usePersistedResult<DeptROIResponse>(sk(m3), su(m3));

  const merged = useMemo(() => mergeResults([r1, r2, r3]), [r1, r2, r3]);
  return merged;
}

export default function DeptROITab() {
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(Math.max(1, now.getMonth()));
  const [periodMode, setPeriodMode] = useState<PeriodMode>("monthly");
  const [quarter, setQuarter] = useState(1);

  // 月別データ
  const storageKey = `dept-roi-v7-${year}-${String(month).padStart(2, "0")}`;
  const seedUrl = `/dept-roi-result-${year}-${String(month).padStart(2, "0")}.json`;
  const { result: monthlyResult, fetchedAt } = usePersistedResult<DeptROIResponse>(storageKey, seedUrl);

  // 四半期データ
  const quarterlyResult = useQuarterlyData(year, quarter);

  // トレンドチャート用: 1〜3月を個別ロード
  const sk = (m: number) => `dept-roi-v7-${year}-${String(m).padStart(2, "0")}`;
  const su = (m: number) => `/dept-roi-result-${year}-${String(m).padStart(2, "0")}.json`;
  const { result: trend1 } = usePersistedResult<DeptROIResponse>(sk(1), su(1));
  const { result: trend2 } = usePersistedResult<DeptROIResponse>(sk(2), su(2));
  const { result: trend3 } = usePersistedResult<DeptROIResponse>(sk(3), su(3));

  const result = periodMode === "quarterly" ? quarterlyResult : monthlyResult;

  const [sortKey, setSortKey] = useState<SortKey>("headcount");
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

  const HIDDEN_DEPTS = ["株式会社スタジアム"];

  const sorted = useMemo(() => {
    if (!result) return [];
    return [...result.departments].filter((d) => !HIDDEN_DEPTS.includes(d.department)).sort((a, b) => {
      const isOtherA = a.department === OTHER_LABEL || a.department === "その他";
      const isOtherB = b.department === OTHER_LABEL || b.department === "その他";
      if (isOtherA) return 1;
      if (isOtherB) return -1;
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "string" && typeof bv === "string") {
        return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
  }, [result, sortKey, sortDir]);

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
        <YearMonthSelector
          year={year}
          month={month}
          onYearChange={setYear}
          onMonthChange={setMonth}
          periodMode={periodMode}
          onPeriodModeChange={setPeriodMode}
          quarter={quarter}
          onQuarterChange={setQuarter}
        />
        {fetchedAt && periodMode === "monthly" && (
          <span className="text-[11px] text-[var(--muted)] self-start">集計日: {fetchedAt}</span>
        )}
      </div>

      {result && sorted.length > 0 && (() => {
        const visibleExpense = sorted.reduce((s, d) => s + d.total, 0);
        const visibleSales = sorted.reduce((s, d) => s + d.sales, 0);
        const visibleRoi = visibleExpense > 0 ? Math.round((visibleSales / visibleExpense) * 10) / 10 : 0;
        return (
        <>
          {/* メトリクスカード */}
          <div className="grid grid-cols-3 gap-4">
            <MetricCard label="旅費合計" value={yen(visibleExpense)} />
            <MetricCard label="売上合計" value={yen(visibleSales)} />
            <MetricCard
              label="全体ROI"
              value={`${visibleRoi}x`}
              accent={visibleRoi >= 50 ? "success" : visibleRoi >= 10 ? "primary" : "warning"}
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
              <table className="w-full text-[13px] min-w-[1100px]">
                <thead>
                  <tr className="border-b border-[var(--border)] text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider">
                    <th className="w-6" />
                    {COLUMNS.map((col) => (
                      <th
                        key={col.key}
                        onClick={() => handleSort(col.key)}
                        className={`px-4 py-2.5 cursor-pointer select-none hover:text-[var(--foreground)] transition whitespace-nowrap ${
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
                  {/* 合計行 */}
                  <tr className="border-b-2 border-[var(--border)] bg-slate-50/80 font-semibold text-[13px]">
                    <td />
                    <td className="px-4 py-3">合計</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {sorted.reduce((s, d) => s + d.headcount, 0)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {yen(sorted.reduce((s, d) => s + d.shinkansen, 0))}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {yen(sorted.reduce((s, d) => s + d.train, 0))}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {yen(sorted.reduce((s, d) => s + d.car, 0))}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {yen(sorted.reduce((s, d) => s + d.airplane, 0))}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {yen(sorted.reduce((s, d) => s + d.hotel, 0))}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {yen(visibleExpense)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {yen(visibleSales)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      <span className={visibleRoi >= 50 ? "text-[var(--success)]" : visibleRoi >= 10 ? "text-[var(--primary)]" : ""}>
                        {visibleRoi}x
                      </span>
                    </td>
                  </tr>
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
                          <td className="px-5 py-2.5 font-medium whitespace-nowrap">{d.department}</td>
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
                            <td className="px-5 py-1.5 pl-10 text-[12px] text-[var(--muted)] whitespace-nowrap">{m.name}</td>
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

          {/* 月別推移グラフ */}
          {(() => {
            const trendMonths = [
              { label: "1月", data: trend1 },
              { label: "2月", data: trend2 },
              { label: "3月", data: trend3 },
            ].filter((m) => m.data);

            if (trendMonths.length < 2) return null;

            // 売上がある部門のみ（その他・スタジアム除外）
            const deptNames = new Set<string>();
            for (const m of trendMonths) {
              for (const d of m.data!.departments) {
                if (d.department !== OTHER_LABEL && d.department !== "その他" && d.department !== "株式会社スタジアム" && d.department !== "監査等委員" && d.total > 0) {
                  deptNames.add(d.department);
                }
              }
            }

            const COLORS = ["#3b82f6", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#f97316", "#6366f1", "#14b8a6", "#e11d48", "#84cc16"];

            const roiData = trendMonths.map((m) => {
              const row: Record<string, string | number> = { month: m.label };
              for (const name of deptNames) {
                const dept = m.data!.departments.find((d) => d.department === name);
                row[name] = dept?.roi ?? 0;
              }
              return row;
            });

            const deptList = Array.from(deptNames);

            return (
              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
                <p className="text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider mb-4">
                  月別 ROI推移
                </p>
                <ResponsiveContainer width="100%" height={360}>
                  <LineChart data={roiData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="month" tick={{ fontSize: 12, fill: "var(--muted)" }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: "var(--muted)" }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}x`} />
                    <Tooltip formatter={(value) => `${value}x`} contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--border)" }} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    {deptList.map((name, i) => (
                      <Line key={name} type="monotone" dataKey={name} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={{ r: 4 }} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            );
          })()}
        </>
        );
      })()}
    </div>
  );
}
