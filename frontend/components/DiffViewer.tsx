"use client";

import { PromptFix } from "@/lib/api";

interface DiffViewerProps {
  fix: PromptFix;
}

export function DiffViewer({ fix }: DiffViewerProps) {
  const diff = fix.diff_json;

  if (!diff || diff.length === 0) {
    // Fallback: side-by-side
    return (
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
        <div>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "0.5rem" }}>
            Original
          </div>
          <div
            className="card mono"
            style={{
              fontSize: "0.8rem",
              lineHeight: 1.6,
              whiteSpace: "pre-wrap",
              color: "#fca5a5",
              background: "rgba(239,68,68,0.05)",
              borderColor: "rgba(239,68,68,0.2)",
            }}
          >
            {fix.original_prompt}
          </div>
        </div>
        <div>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "0.5rem" }}>
            Proposed
          </div>
          <div
            className="card mono"
            style={{
              fontSize: "0.8rem",
              lineHeight: 1.6,
              whiteSpace: "pre-wrap",
              color: "#6ee7b7",
              background: "rgba(16,185,129,0.05)",
              borderColor: "rgba(16,185,129,0.2)",
            }}
          >
            {fix.proposed_prompt}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="card"
      style={{
        fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
        padding: "1rem",
        overflowX: "auto",
      }}
    >
      <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "0.75rem" }}>
        Unified Diff
      </div>
      {diff.map((item, i) => {
        const line = item.line ?? String(item);
        let cls = "diff-ctx";
        if (line.startsWith("+") && !line.startsWith("+++")) cls = "diff-add";
        else if (line.startsWith("-") && !line.startsWith("---")) cls = "diff-del";
        else if (line.startsWith("@@")) cls = "";

        return (
          <div
            key={i}
            className={`diff-line ${cls}`}
            style={
              line.startsWith("@@")
                ? { color: "#818cf8", background: "rgba(99,102,241,0.08)" }
                : undefined
            }
          >
            {line || " "}
          </div>
        );
      })}
    </div>
  );
}
