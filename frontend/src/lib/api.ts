const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "APIエラー");
  }
  return res.json();
}

export type SummaryRow = {
  emp_no: string;
  name: string;
  department: string;
  shinkansen: number;
  shinkansen_ad: number;
  shinkansen_welfare: number;
  shinkansen_recruit: number;
  shinkansen_subsidiary: number;
  hotel: number;
  hotel_ad: number;
  hotel_recruit: number;
  train: number;
  train_ad: number;
  train_recruit: number;
  other: number;
  other_ad: number;
  other_recruit: number;
  total: number;
};

export type AggregateResponse = {
  summary: SummaryRow[];
  unmatched: { name: string; normalized: string; category: string; amount: number; source: string }[];
  log: string[];
};

export type ROIRow = {
  セグメント: string;
  旅費交通費: number;
  売上: number;
  ROI: number;
};

export type ROIResponse = {
  rows: ROIRow[];
  total_expense: number;
  total_revenue: number;
  overall_roi: number;
};

export type DeptROIRow = {
  department: string;
  headcount: number;
  shinkansen: number;
  train: number;
  car: number;
  airplane: number;
  hotel: number;
  total: number;
  sales: number;
  roi: number;
};

export type DeptROIResponse = {
  departments: DeptROIRow[];
  totals: { total_expense: number; total_sales: number; overall_roi: number };
};
