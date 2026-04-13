"use client";

interface MetricComparisonProps {
  emoji: string;
  label: string;
  current: number;
  baseline: number;
  unit: string;
  /** true = valeur haute est bonne (pas, sommeil), false = valeur haute est mauvaise (BPM, ecran) */
  higherIsBetter?: boolean;
}

export default function MetricComparison({
  emoji,
  label,
  current,
  baseline,
  unit,
  higherIsBetter = true,
}: MetricComparisonProps) {
  const delta = current - baseline;
  const deltaSign = delta >= 0 ? "+" : "";
  const pctChange = baseline > 0 ? Math.abs(delta / baseline) * 100 : 0;

  // Determiner si le changement est bon ou mauvais selon la direction clinique
  const isGood = higherIsBetter ? delta >= 0 : delta <= 0;
  const isSignificant = pctChange > 20;

  // Couleur : vert si bon, orange si mauvais modere, rouge si mauvais significatif
  const isAlert = !isGood && isSignificant;
  const isWarning = !isGood && !isSignificant;

  const deltaColor = isGood
    ? "text-success-500"
    : isAlert
      ? "text-danger-500"
      : "text-warning-500";
  const deltaBg = isGood
    ? "bg-success-50"
    : isAlert
      ? "bg-danger-50"
      : "bg-warning-50";
  const barColor = isGood
    ? "bg-success-400"
    : isAlert
      ? "bg-danger-400"
      : "bg-warning-400";

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
            className={`h-full rounded-full ${barColor}`}
            style={{ width: `${Math.min(100, (current / Math.max(baseline, 1)) * 100)}%` }}
          />
        </div>
        <p className="text-[11px] text-gray-400">
          ref {baseline} {unit}
        </p>
      </div>
    </div>
  );
}
