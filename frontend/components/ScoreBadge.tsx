"use client";

import clsx from "clsx";

interface ScoreBadgeProps {
  score: number | null;
  type?: "quality" | "drift";
  size?: "sm" | "md";
}

export function ScoreBadge({ score, type = "quality", size = "md" }: ScoreBadgeProps) {
  if (score === null || score === undefined) {
    return (
      <div className={clsx("score-ring neutral", size === "sm" && "!w-8 !h-8 !text-xs")}>
        —
      </div>
    );
  }

  let cls = "neutral";
  if (type === "quality") {
    if (score >= 7) cls = "good";
    else if (score >= 5) cls = "warn";
    else cls = "danger";
  } else {
    // drift: lower is better
    if (score < 0.2) cls = "good";
    else if (score < 0.35) cls = "warn";
    else cls = "danger";
  }

  const display =
    type === "quality" ? score.toFixed(1) : score.toFixed(2);

  return (
    <div className={clsx("score-ring", cls, size === "sm" && "!w-8 !h-8 !text-xs")}>
      {display}
    </div>
  );
}
