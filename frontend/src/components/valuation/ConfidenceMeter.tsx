"use client";

interface ConfidenceMeterProps {
  score: number;
  label: string;
}

export function ConfidenceMeter({ score, label }: ConfidenceMeterProps) {
  const color =
    score >= 75
      ? "var(--color-success)"
      : score >= 50
        ? "var(--color-warning)"
        : "var(--color-danger)";

  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-xs font-medium text-[var(--color-text-secondary)]">
          Confidence
        </span>
        <span className="text-xs font-medium" style={{ color }}>
          {label} ({Math.round(score)}/100)
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-[var(--color-bg-secondary)]">
        <div
          className="h-2 rounded-full transition-all"
          style={{ width: `${score}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}
