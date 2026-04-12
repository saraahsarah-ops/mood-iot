"use client";

interface MetricComparisonProps {
  emoji: string;
  label: string;
  current: number;
  baseline: number;
  unit: string;
}

export default function MetricComparison({
  emoji,
  label,
  current,
  baseline,
  unit,
}: MetricComparisonProps) {
  const delta = current - baseline;
  const deltaSign = delta >= 0 ? "+" : "";
  const deltaColor = Math.abs(delta) > baseline * 0.2 ? "text-danger" : "text-success";

  return (
    <div className="rounded-xl bg-white p-4 shadow-sm">
      <p className="text-sm text-gray-500">
        {emoji} {label}
      </p>
      <p className="mt-1 text-2xl font-bold text-gray-800">
        {current} <span className="text-sm font-normal text-gray-400">{unit}</span>
      </p>
      <p className={`text-sm font-medium ${deltaColor}`}>
        {deltaSign}
        {delta.toFixed(1)} vs baseline
      </p>
    </div>
  );
}
