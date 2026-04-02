"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";

const now = new Date();

export default function JournalTab() {
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(Math.max(1, now.getMonth()));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [csvReady, setCsvReady] = useState(false);
  const [csvData, setCsvData] = useState("");
  const [log, setLog] = useState<string[]>([]);

  const generate = async () => {
    setLoading(true);
    setError("");
    setCsvReady(false);
    try {
      const res = await apiPost<{ csv: string; log: string[] }>("/api/journal-csv", {
        year, month, use_mf: true, use_ex: true, use_racco: true, use_jalan: true, use_times: true, dry_run: true,
      });
      setCsvData(res.csv);
      setLog(res.log);
      setCsvReady(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "エラー");
    } finally {
      setLoading(false);
    }
  };

  const download = () => {
    const blob = new Blob([csvData], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `journal_${year}_${String(month).padStart(2, "0")}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-lg font-bold">仕訳生成</h2>
        <p className="text-xs text-[var(--muted)] mt-0.5">MF会計Plusインポート用の仕訳CSVを生成します</p>
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
        <div className="flex items-end gap-6">
          <div>
            <label className="block text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider mb-1.5">年</label>
            <input
              type="number"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="w-24 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/20 focus:border-[var(--primary)]"
            />
          </div>
          <div>
            <label className="block text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider mb-1.5">月</label>
            <input
              type="number"
              min={1}
              max={12}
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              className="w-20 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/20 focus:border-[var(--primary)]"
            />
          </div>
          <button
            onClick={generate}
            disabled={loading}
            className="rounded-lg bg-[var(--primary)] px-5 py-2 text-sm font-medium text-white hover:bg-[var(--primary-hover)] disabled:opacity-50 transition"
          >
            {loading ? "生成中..." : "仕訳CSV生成"}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {csvReady && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-[var(--success)]" />
              <p className="text-sm font-medium">CSV生成完了</p>
            </div>
            <button
              onClick={download}
              className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-1.5 text-sm font-medium hover:bg-slate-50 transition"
            >
              ダウンロード
            </button>
          </div>
          {log.length > 0 && (
            <pre className="rounded-lg bg-[var(--background)] border border-[var(--border)] px-4 py-3 text-[11px] text-[var(--muted)] whitespace-pre-wrap font-mono">
              {log.join("\n")}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
