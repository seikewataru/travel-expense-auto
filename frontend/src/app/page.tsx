"use client";

import { useState } from "react";
import AggregateTab from "@/components/AggregateTab";
import JournalTab from "@/components/JournalTab";
import ROITab from "@/components/ROITab";
import DeptROITab from "@/components/DeptROITab";

const SECTIONS = [
  {
    label: "分析",
    tabs: [
      { key: "dept-roi", label: "部門別ROI" },
      { key: "aggregate", label: "個人別交通費" },
    ],
  },
  {
    label: "集計（経理）",
    tabs: [
      { key: "roi", label: "科目別" },
      { key: "journal", label: "仕訳生成" },
    ],
  },
] as const;

type TabKey = (typeof SECTIONS)[number]["tabs"][number]["key"];

export default function Home() {
  const [tab, setTab] = useState<TabKey>("dept-roi");

  return (
    <div className="flex min-h-screen">
      {/* サイドバー */}
      <aside className="fixed top-0 left-0 h-screen w-[220px] border-r border-[var(--border)] bg-[var(--card)] flex flex-col z-20">
        <div className="px-5 py-5 border-b border-[var(--border)]">
          <h1 className="text-base font-bold text-[var(--foreground)] tracking-tight">
            旅費ROIチェック
          </h1>
        </div>
        <nav className="flex-1 px-3 py-4">
          {SECTIONS.map((section) => (
            <div key={section.label} className="mb-4">
              <p className="px-3 mb-1.5 text-[10px] font-semibold tracking-wider uppercase text-[var(--muted-light)]">
                {section.label}
              </p>
              <div className="space-y-0.5">
                {section.tabs.map((t) => (
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
              </div>
            </div>
          ))}
        </nav>
        <div className="px-5 py-4 border-t border-[var(--border)]">
          <p className="text-[10px] text-[var(--muted-light)]">v2.0 — Next.js + FastAPI</p>
        </div>
      </aside>

      {/* メインコンテンツ */}
      <main className="flex-1 ml-[220px]">
        <div className="max-w-[1100px] mx-auto px-8 py-6">
          {tab === "aggregate" && <AggregateTab />}
          {tab === "journal" && <JournalTab />}
          {tab === "roi" && <ROITab />}
          {tab === "dept-roi" && <DeptROITab />}
        </div>
      </main>
    </div>
  );
}
