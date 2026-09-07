"use client";

import clsx from "clsx";

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: boolean;
  danger?: boolean;
  warning?: boolean;
}

export function StatCard({ label, value, sub, accent, danger, warning }: StatCardProps) {
  return (
    <div
      className="card"
      style={{
        borderColor: accent
          ? "rgba(99,102,241,0.35)"
          : danger
          ? "rgba(239,68,68,0.3)"
          : warning
          ? "rgba(245,158,11,0.3)"
          : undefined,
      }}
    >
      <div
        style={{
          fontSize: "0.7rem",
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: "var(--text-muted)",
          marginBottom: "0.5rem",
        }}
      >
        {label}
      </div>
      <div
        className="mono"
        style={{
          fontSize: "1.75rem",
          fontWeight: 700,
          color: accent
            ? "#818cf8"
            : danger
            ? "#f87171"
            : warning
            ? "#fbbf24"
            : "var(--text-primary)",
          lineHeight: 1,
        }}
      >
        {value}
      </div>
      {sub && (
        <div
          style={{
            fontSize: "0.72rem",
            color: "var(--text-muted)",
            marginTop: "0.35rem",
          }}
        >
          {sub}
        </div>
      )}
    </div>
  );
}
