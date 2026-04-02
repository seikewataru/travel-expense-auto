"use client";

import { useState } from "react";
import AggregateTab from "@/components/AggregateTab";
import JournalTab from "@/components/JournalTab";
import ROITab from "@/components/ROITab";

const TABS = [
  { key: "aggregate", label: "旅費集計" },
  { key: "journal", label: "仕訳生成" },
  { key: "roi", label: "ROI分析" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export default function Home() {
  const [tab, setTab] = useState<TabKey>("aggregate");

  return (
    <div className="flex min-h-screen">
      {/* サイドバー */}
      <aside className="fixed top-0 left-0 h-screen w-[var(--sidebar-w)] border-r border-[var(--border)] bg-[var(--card)] flex flex-col z-20">
        <div className="px-5 py-5 border-b border-[var(--border)]">
          <h1 className="text-base font-bold text-[var(--foreground)] tracking-tight">
            旅費自動仕訳
          </h1>
          <p className="text-xs text-[var(--muted)] mt-0.5">Travel Expense Auto</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`w-full text-left rounded-lg px-3 py-2 text-[13px] font-medium transition ${
                tab === t.key
                  ? "bg-[var(--primary-light)] text-[var(--primary)]"
                  : "text-[var(--muted)] hover:text-[var(--foreground)] hover:bg-slate-50"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <div className="px-5 py-4 border-t border-[var(--border)]">
          <p className="text-[10px] text-[var(--muted-light)]">v2.0 — Next.js + FastAPI</p>
        </div>
      </aside>

      {/* メインコンテンツ */}
      <main className="flex-1 ml-[var(--sidebar-w)]">
        <div className="max-w-[1100px] mx-auto px-8 py-6">
          {tab === "aggregate" && <AggregateTab />}
          {tab === "journal" && <JournalTab />}
          {tab === "roi" && <ROITab />}
        </div>
      </main>
    </div>
  );
}
