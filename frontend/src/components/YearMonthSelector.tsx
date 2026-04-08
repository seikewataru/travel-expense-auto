"use client";

const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1);
const QUARTERS = [
  { key: 1, label: "1Q", months: [1, 2, 3] },
  { key: 2, label: "2Q", months: [4, 5, 6] },
  { key: 3, label: "3Q", months: [7, 8, 9] },
  { key: 4, label: "4Q", months: [10, 11, 12] },
];

/** データが存在する最新月（これ以降は選択不可） */
const DATA_MAX_YEAR = 2026;
const DATA_MAX_MONTH = 3;

type PeriodMode = "monthly" | "quarterly";

interface Props {
  year: number;
  month: number;
  onYearChange: (y: number) => void;
  onMonthChange: (m: number) => void;
  /** 四半期モード対応（省略時は月別のみ） */
  periodMode?: PeriodMode;
  onPeriodModeChange?: (mode: PeriodMode) => void;
  quarter?: number;
  onQuarterChange?: (q: number) => void;
}

function Pill({
  active,
  disabled,
  onClick,
  children,
}: {
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`rounded-md px-3 py-1 text-xs font-medium transition ${
        disabled
          ? "text-[var(--muted)]/30 cursor-not-allowed"
          : active
            ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm"
            : "text-[var(--muted)] hover:text-[var(--foreground)]"
      }`}
    >
      {children}
    </button>
  );
}

export default function YearMonthSelector({
  year,
  month,
  onYearChange,
  onMonthChange,
  periodMode,
  onPeriodModeChange,
  quarter,
  onQuarterChange,
}: Props) {
  const showQuarterly = periodMode !== undefined;
  const mode = periodMode ?? "monthly";

  return (
    <div className="flex flex-col gap-3">
      {/* 年 */}
      <div className="flex items-center gap-4 flex-wrap">
        <span className="text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider w-6">
          年
        </span>
        <div className="flex gap-0.5 rounded-lg bg-[var(--background)] p-0.5">
          <Pill active={year === 2026} onClick={() => onYearChange(2026)}>
            2026
          </Pill>
        </div>
      </div>

      {/* 月別 */}
      <div className="flex items-center gap-4 flex-wrap">
        {showQuarterly ? (
          <button
            onClick={() => onPeriodModeChange?.("monthly")}
            className={`text-[11px] font-medium uppercase tracking-wider w-6 transition ${
              mode === "monthly" ? "text-[var(--primary)]" : "text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
          >
            月別
          </button>
        ) : (
          <span className="text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider w-6">
            月
          </span>
        )}
        <div className="flex gap-0.5 rounded-lg bg-[var(--background)] p-0.5">
          {MONTHS.map((m) => {
            const disabled = year > DATA_MAX_YEAR || (year === DATA_MAX_YEAR && m > DATA_MAX_MONTH);
            return (
              <Pill key={m} active={mode === "monthly" && month === m} disabled={disabled} onClick={() => {
                onPeriodModeChange?.("monthly");
                onMonthChange(m);
              }}>
                {m}
              </Pill>
            );
          })}
        </div>
      </div>

      {/* 四半期別 */}
      {showQuarterly && (
        <div className="flex items-center gap-4 flex-wrap">
          <button
            onClick={() => onPeriodModeChange?.("quarterly")}
            className={`text-[11px] font-medium uppercase tracking-wider w-6 transition ${
              mode === "quarterly" ? "text-[var(--primary)]" : "text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
          >
            四半期
          </button>
          <div className="flex gap-0.5 rounded-lg bg-[var(--background)] p-0.5">
            {QUARTERS.map((q) => {
              const disabled = year === DATA_MAX_YEAR && q.months[0] > DATA_MAX_MONTH;
              return (
                <Pill key={q.key} active={mode === "quarterly" && quarter === q.key} disabled={disabled} onClick={() => {
                  onPeriodModeChange?.("quarterly");
                  onQuarterChange?.(q.key);
                }}>
                  {q.label}
                </Pill>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export { QUARTERS };
