"use client";

const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1);

/** データが存在する最新月（これ以降は選択不可） */
const DATA_MAX_YEAR = 2026;
const DATA_MAX_MONTH = 3;

interface Props {
  year: number;
  month: number;
  onYearChange: (y: number) => void;
  onMonthChange: (m: number) => void;
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
}: Props) {
  return (
    <div className="flex items-center gap-4 flex-wrap">
      <span className="text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider">
        年
      </span>
      <div className="flex gap-0.5 rounded-lg bg-[var(--background)] p-0.5">
        <Pill active={year === 2026} onClick={() => onYearChange(2026)}>
          2026
        </Pill>
      </div>

      <span className="text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider ml-2">
        月
      </span>
      <div className="flex gap-0.5 rounded-lg bg-[var(--background)] p-0.5">
        {MONTHS.map((m) => {
          const disabled = year > DATA_MAX_YEAR || (year === DATA_MAX_YEAR && m > DATA_MAX_MONTH);
          return (
            <Pill key={m} active={month === m} disabled={disabled} onClick={() => onMonthChange(m)}>
              {m}
            </Pill>
          );
        })}
      </div>
    </div>
  );
}
