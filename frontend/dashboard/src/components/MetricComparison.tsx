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
  const pctChange = baseline > 0 ? Math.abs(delta / baseline) * 100 : 0;
  const isAlert = pctChange > 20;
  const deltaColor = isAlert ? "text-danger-500" : "text-success-500";
  const deltaBg = isAlert ? "bg-danger-50" : "bg-success-50";

  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-4 shadow-card transition-all duration-200 hover:shadow-card-hover">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gray-50 text-base">
            {emoji}
          </span>
          <p className="text-[13px] font-medium text-gray-400">{label}</p>
        </div>
        <span className={`rounded-lg px-2 py-0.5 text-[11px] font-bold ${deltaColor} ${deltaBg}`}>
          {deltaSign}{delta.toFixed(label === "Pas" ? 0 : 1)}
        </span>
      </div>
      <p className="mt-3 text-2xl font-extrabold tracking-tight text-gray-800">
        {current}
        <span className="ml-1 text-sm font-normal text-gray-400">{unit}</span>
      </p>
      <div className="mt-2 flex items-center gap-2">
        <div className="h-1 flex-1 overflow-hidden rounded-full bg-gray-100">
          <div
            className={`h-full rounded-full ${isAlert ? "bg-danger-400" : "bg-success-400"}`}
            style={{ width: `${Math.min(100, (current / baseline) * 100)}%` }}
          />
        </div>
        <p className="text-[11px] text-gray-400">
          ref {baseline} {unit}
        </p>
      </div>
    </div>
  );
}
