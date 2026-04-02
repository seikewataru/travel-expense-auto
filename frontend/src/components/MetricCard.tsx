"use client";

export default function MetricCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: "primary" | "success" | "warning" | "danger";
}) {
  const accentColor = accent
    ? {
        primary: "text-[var(--primary)]",
        success: "text-[var(--success)]",
        warning: "text-[var(--warning)]",
        danger: "text-[var(--danger)]",
      }[accent]
    : "text-[var(--foreground)]";

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-5 py-4">
      <p className="text-[11px] font-medium text-[var(--muted)] uppercase tracking-wider">
        {label}
      </p>
      <p className={`mt-1.5 text-xl font-bold tracking-tight ${accentColor}`}>
        {value}
      </p>
      {sub && (
        <p className="mt-0.5 text-[11px] text-[var(--muted-light)]">{sub}</p>
      )}
    </div>
  );
}
