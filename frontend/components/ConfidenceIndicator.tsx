// ConfidenceIndicator.tsx — Renders a confidence score badge
"use client";

interface Props {
  score: number; // 0–1
}

export default function ConfidenceIndicator({ score }: Props) {
  const pct = Math.round(score * 100);
  const colour = pct >= 80 ? "bg-green-600" : pct >= 50 ? "bg-yellow-500" : "bg-red-500";
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium text-white ${colour}`}>
      {pct}%
    </span>
  );
}
