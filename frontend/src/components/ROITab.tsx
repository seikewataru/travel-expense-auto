"use client";

import { useState } from "react";
import { apiPost, type ROIResponse } from "@/lib/api";
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

export default function ROITab() {
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(Math.max(1, now.getMonth()));
  const [demo, setDemo] = useState(false);
  const [loading, setLoading] = useState(false);
  const [writing, setWriting] = useState(false);
  const storageKey = `roi-result-${year}-${String(month).padStart(2, "0")}`;
  const { result, fetchedAt, saveResult } = usePersistedResult<ROIResponse>(storageKey);
  const [error, setError] = useState("");
  const [writeMsg, setWriteMsg] = useState("");

  const run = async () => {
    setLoading(true);
    setError("");
    setWriteMsg("");
    try {
      const res = await apiPost<ROIResponse>("/api/roi", { year, month, demo });
      saveResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "エラー");
    } finally {
      setLoading(false);
    }
  };

  const writeSheet = async () => {
    setWriting(true);
    setWriteMsg("");
    try {
      const res = await apiPost<{ message: string }>("/api/roi/write", { year, month });
      setWriteMsg(res.message);
    } catch (e) {
      setWriteMsg(e instanceof Error ? e.message : "エラー");
    } finally {
      setWriting(false);
    }
  };

  const chartData = result?.rows
    .filter((r) => r.セグメント !== "その他")
    .map((r) => ({
      name: r.セグメント,
      旅費交通費: r.旅費交通費,
      売上: r.売上,
    }));

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold">ROI分析</h2>
          <p className="text-xs text-[var(--muted)] mt-0.5">セグメント別の旅費ROIを分析します</p>
        </div>
      </div>

      {/* 年月選択 */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 space-y-4">
        <YearMonthSelector year={year} month={month} onYearChange={setYear} onMonthChange={setMonth} />
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-1.5 text-xs text-[var(--muted)] cursor-pointer">
            <input
              type="checkbox"
              checked={demo}
              onChange={(e) => setDemo(e.target.checked)}
              className="rounded border-[var(--border)] text-[var(--primary)] focus:ring-[var(--primary)]/20"
            />
            デモデータ
          </label>
          <div className="flex items-center gap-3">
            {fetchedAt && (
              <span className="text-[11px] text-[var(--muted)]">集計日: {fetchedAt}</span>
            )}
            <button
              onClick={run}
              disabled={loading}
              className="rounded-lg bg-[var(--primary)] px-5 py-2 text-sm font-medium text-white hover:bg-[var(--primary-hover)] disabled:opacity-50 transition"
            >
              {loading ? "読み込み中..." : "ROI分析実行"}
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {result && (
        <>
          {/* メトリクスカード */}
          <div className="grid grid-cols-3 gap-4">
            <MetricCard label="旅費交通費合計" value={yen(result.total_expense)} />
            <MetricCard label="売上合計" value={yen(result.total_revenue)} />
            <MetricCard
              label="全体ROI"
              value={`${result.overall_roi}x`}
              accent={result.overall_roi >= 50 ? "success" : result.overall_roi >= 10 ? "primary" : "warning"}
            />
          </div>

          {/* テーブル */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] overflow-hidden">
            <div className="px-5 py-3 border-b border-[var(--border)] bg-slate-50/50">
              <span className="text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider">
                セグメント別ROI
              </span>
            </div>
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-[var(--border)] text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider">
                  <th className="px-5 py-2.5 text-left">セグメント</th>
                  <th className="px-5 py-2.5 text-right">旅費交通費</th>
                  <th className="px-5 py-2.5 text-right">売上</th>
                  <th className="px-5 py-2.5 text-right">ROI</th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((r, i) => (
                  <tr
                    key={i}
                    className="border-b border-[var(--border)] last:border-0 hover:bg-slate-50/50 transition"
                  >
                    <td className="px-5 py-2.5 font-medium">{r.セグメント}</td>
                    <td className="px-5 py-2.5 text-right tabular-nums">{yen(r.旅費交通費)}</td>
                    <td className="px-5 py-2.5 text-right tabular-nums">{yen(r.売上)}</td>
                    <td className="px-5 py-2.5 text-right font-semibold tabular-nums">
                      <span className={r.ROI >= 50 ? "text-[var(--success)]" : r.ROI >= 10 ? "text-[var(--primary)]" : "text-[var(--muted)]"}>
                        {r.ROI}x
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* グラフ */}
          {chartData && chartData.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
              <p className="text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider mb-4">
                セグメント別 旅費 vs 売上
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
                  <Bar dataKey="旅費交通費" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="売上" fill="var(--primary)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* スプシ書き出し */}
          <div className="flex items-center gap-3">
            <button
              onClick={writeSheet}
              disabled={writing}
              className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-2 text-xs font-medium hover:bg-slate-50 disabled:opacity-50 transition"
            >
              {writing ? "書き込み中..." : "スプレッドシートに書き出し"}
            </button>
            {writeMsg && (
              <span className="text-xs text-[var(--success)]">{writeMsg}</span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
