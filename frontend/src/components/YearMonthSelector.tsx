"use client";

const now = new Date();
const YEARS = [now.getFullYear() - 1, now.getFullYear()];
const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1);

interface Props {
  year: number;
  month: number;
  onYearChange: (y: number) => void;
  onMonthChange: (m: number) => void;
}

function Pill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-md px-3 py-1 text-xs font-medium transition ${
        active
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
        {YEARS.map((y) => (
          <Pill key={y} active={year === y} onClick={() => onYearChange(y)}>
            {y}
          </Pill>
        ))}
      </div>

      <span className="text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider ml-2">
        月
      </span>
      <div className="flex gap-0.5 rounded-lg bg-[var(--background)] p-0.5">
        {MONTHS.map((m) => (
          <Pill key={m} active={month === m} onClick={() => onMonthChange(m)}>
            {m}
          </Pill>
        ))}
      </div>
    </div>
  );
}
