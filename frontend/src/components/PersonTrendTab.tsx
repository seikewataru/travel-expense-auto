"use client";

import { useState, useMemo } from "react";
import { type AggregateResponse } from "@/lib/api";
import { usePersistedResult } from "@/lib/usePersistedResult";
import YearMonthSelector from "./YearMonthSelector";
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

const CATEGORIES = [
  { key: "shinkansen", label: "新幹線" },
  { key: "train", label: "在来線" },
  { key: "car", label: "車移動" },
  { key: "airplane", label: "飛行機" },
  { key: "hotel", label: "宿泊費" },
] as const;

type CategoryKey = (typeof CATEGORIES)[number]["key"];
type SortDir = "asc" | "desc";

const MONTHS = [
  { key: 1, label: "1月" },
  { key: 2, label: "2月" },
  { key: 3, label: "3月" },
];

const COLORS = ["#3b82f6", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#f97316", "#6366f1", "#14b8a6"];

function yen(n: number) {
  return `¥${n.toLocaleString()}`;
}

// PLベース: baseカテゴリのみ（_ad/_welfare等除外）
// car + airplane は個別カテゴリとして扱う
function getBaseValue(row: Record<string, unknown>, cat: CategoryKey): number {
  return (row[cat] as number) || 0;
}

interface PersonRow {
  name: string;
  department: string;
  emp_no: string;
  m1: number;
  m2: number;
  m3: number;
  total: number;
}

export default function PersonTrendTab() {
  const [category, setCategory] = useState<CategoryKey>("shinkansen");
  const [sortCol, setSortCol] = useState<"name" | "department" | "m1" | "m2" | "m3" | "total">("total");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const sk = (m: number) => `aggregate-v3-2026-${String(m).padStart(2, "0")}`;
  const su = (m: number) => `/aggregate-result-2026-${String(m).padStart(2, "0")}.json`;
  const { result: r1 } = usePersistedResult<AggregateResponse>(sk(1), su(1));
  const { result: r2 } = usePersistedResult<AggregateResponse>(sk(2), su(2));
  const { result: r3 } = usePersistedResult<AggregateResponse>(sk(3), su(3));

  const rows = useMemo(() => {
    const personMap = new Map<string, PersonRow>();

    const addMonth = (result: AggregateResponse | null, monthKey: "m1" | "m2" | "m3") => {
      if (!result) return;
      for (const r of result.summary) {
        const val = getBaseValue(r, category);
        const existing = personMap.get(r.name);
        if (existing) {
          existing[monthKey] = val;
          existing.total += val;
        } else {
          personMap.set(r.name, {
            name: r.name,
            department: r.department,
            emp_no: r.emp_no,
            m1: 0, m2: 0, m3: 0,
            total: 0,
            [monthKey]: val,
          } as PersonRow);
          personMap.get(r.name)!.total = val;
        }
      }
    };

    addMonth(r1, "m1");
    addMonth(r2, "m2");
    addMonth(r3, "m3");

    // total再計算（addMonthで加算しているがリセット）
    for (const p of personMap.values()) {
      p.total = p.m1 + p.m2 + p.m3;
    }

    return Array.from(personMap.values()).filter((p) => p.total > 0);
  }, [r1, r2, r3, category]);

  const sorted = useMemo(() => {
    return [...rows].sort((a, b) => {
      const av = a[sortCol];
      const bv = b[sortCol];
      if (typeof av === "string" && typeof bv === "string") {
        return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
  }, [rows, sortCol, sortDir]);

  const handleSort = (key: typeof sortCol) => {
    if (sortCol === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortCol(key);
      setSortDir(key === "name" || key === "department" ? "asc" : "desc");
    }
  };

  // Top 8 for chart
  const topPersons = useMemo(() => {
    return [...rows].sort((a, b) => b.total - a.total).slice(0, 8);
  }, [rows]);

  const chartData = useMemo(() => {
    return MONTHS.map((m) => {
      const row: Record<string, string | number> = { month: m.label };
      for (const p of topPersons) {
        row[p.name] = p[`m${m.key}` as "m1" | "m2" | "m3"];
      }
      return row;
    });
  }, [topPersons]);

  const grandTotal = rows.reduce((s, r) => s + r.total, 0);

  const TABLE_COLS: { key: typeof sortCol; label: string; align: "left" | "right" }[] = [
    { key: "name", label: "名前", align: "left" },
    { key: "department", label: "部署", align: "left" },
    { key: "m1", label: "1月", align: "right" },
    { key: "m2", label: "2月", align: "right" },
    { key: "m3", label: "3月", align: "right" },
    { key: "total", label: "Q1合計", align: "right" },
  ];

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-bold">個人別推移</h2>
        <p className="text-xs text-[var(--muted)] mt-0.5">カテゴリ別の個人旅費月間推移</p>
      </div>

      {/* カテゴリ選択 */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
        <div className="flex items-center gap-4">
          <span className="text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider">カテゴリ</span>
          <div className="flex gap-0.5 rounded-lg bg-[var(--background)] p-0.5">
            {CATEGORIES.map((c) => (
              <button
                key={c.key}
                onClick={() => setCategory(c.key)}
                className={`rounded-md px-4 py-1.5 text-xs font-medium transition ${
                  category === c.key
                    ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm"
                    : "text-[var(--muted)] hover:text-[var(--foreground)]"
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>
          <span className="ml-auto text-xs text-[var(--muted)]">
            Q1合計 <span className="font-bold text-[var(--foreground)] text-sm ml-1">{yen(grandTotal)}</span>
            <span className="ml-3">{rows.length}名</span>
          </span>
        </div>
      </div>

      {/* グラフ: Top 8 推移 */}
      {topPersons.length > 0 && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
          <p className="text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider mb-4">
            {CATEGORIES.find((c) => c.key === category)?.label} — 上位{topPersons.length}名の月別推移
          </p>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="month" tick={{ fontSize: 12, fill: "var(--muted)" }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "var(--muted)" }} axisLine={false} tickLine={false} tickFormatter={(v) => `${(v / 10000).toFixed(0)}万`} />
              <Tooltip formatter={(value) => yen(Number(value))} contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--border)" }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {topPersons.map((p, i) => (
                <Line key={p.name} type="monotone" dataKey={p.name} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={{ r: 3 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* テーブル */}
      {sorted.length > 0 && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-[13px] min-w-[700px]">
              <thead>
                <tr className="border-b border-[var(--border)] text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider">
                  {TABLE_COLS.map((col) => (
                    <th
                      key={col.key}
                      onClick={() => handleSort(col.key)}
                      className={`px-5 py-2.5 cursor-pointer select-none hover:text-[var(--foreground)] transition whitespace-nowrap ${
                        col.align === "left" ? "text-left" : "text-right"
                      }`}
                    >
                      {col.label}
                      <span className={`ml-0.5 text-[10px] ${sortCol === col.key ? "text-[var(--primary)]" : "opacity-20"}`}>
                        {sortCol === col.key
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
                    <td className="px-5 py-2 font-medium whitespace-nowrap">{r.name}</td>
                    <td className="px-5 py-2 text-[var(--muted)] whitespace-nowrap">{r.department}</td>
                    <td className="px-5 py-2 text-right tabular-nums">{r.m1 ? yen(r.m1) : "—"}</td>
                    <td className="px-5 py-2 text-right tabular-nums">{r.m2 ? yen(r.m2) : "—"}</td>
                    <td className="px-5 py-2 text-right tabular-nums">{r.m3 ? yen(r.m3) : "—"}</td>
                    <td className="px-5 py-2 text-right font-semibold tabular-nums">{yen(r.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
