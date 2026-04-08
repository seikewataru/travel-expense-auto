"use client";

import { useState } from "react";
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

export default function DeptROITab() {
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(Math.max(1, now.getMonth()));
  const storageKey = `dept-roi-result-${year}-${String(month).padStart(2, "0")}`;
  const seedUrl = `/dept-roi-result-${year}-${String(month).padStart(2, "0")}.json`;
  const { result, fetchedAt } = usePersistedResult<DeptROIResponse>(storageKey, seedUrl);

  const chartData = result?.departments.map((d) => ({
    name: d.department,
    旅費合計: d.total,
    売上: d.sales,
  }));

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold">セグメント別ROI</h2>
          <p className="text-xs text-[var(--muted)] mt-0.5">法人セグメントごとの旅費ROIを分析します</p>
        </div>
      </div>

      {/* 年月選択 */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 flex items-center justify-between">
        <YearMonthSelector year={year} month={month} onYearChange={setYear} onMonthChange={setMonth} />
        {fetchedAt && (
          <span className="text-[11px] text-[var(--muted)]">前回: {fetchedAt}</span>
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
                セグメント別ROI
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="border-b border-[var(--border)] text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider">
                    <th className="px-5 py-2.5 text-left">セグメント</th>
                    <th className="px-5 py-2.5 text-right">人数</th>
                    <th className="px-5 py-2.5 text-right">新幹線</th>
                    <th className="px-5 py-2.5 text-right">在来線</th>
                    <th className="px-5 py-2.5 text-right">車移動</th>
                    <th className="px-5 py-2.5 text-right">飛行機</th>
                    <th className="px-5 py-2.5 text-right">宿泊費</th>
                    <th className="px-5 py-2.5 text-right">旅費合計</th>
                    <th className="px-5 py-2.5 text-right">売上</th>
                    <th className="px-5 py-2.5 text-right">ROI</th>
                  </tr>
                </thead>
                <tbody>
                  {result.departments.map((d, i) => (
                    <tr
                      key={i}
                      className="border-b border-[var(--border)] last:border-0 hover:bg-slate-50/50 transition"
                    >
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
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* グラフ */}
          {chartData && chartData.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
              <p className="text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider mb-4">
                セグメント別 旅費合計 vs 売上
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
