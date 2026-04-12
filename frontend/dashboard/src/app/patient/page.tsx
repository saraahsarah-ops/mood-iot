"use client";
import { useState } from "react";
import MetricComparison from "@/components/MetricComparison";
import ScoreChart from "@/components/ScoreChart";
import { getRiskEmoji, getRiskLabel } from "@/lib/types";

const PATIENTS = ["Sophie L.", "Marie D.", "Lea R.", "Anna K."];

const DEMO_METRICS: Record<string, { steps: number; sleep: number; bpm: number; screen: number }> = {
  "Sophie L.": { steps: 2200, sleep: 4.2, bpm: 92, screen: 6.5 },
  "Marie D.": { steps: 5500, sleep: 5.8, bpm: 78, screen: 4.2 },
  "Lea R.": { steps: 8400, sleep: 7.3, bpm: 68, screen: 3.1 },
  "Anna K.": { steps: 4100, sleep: 5.1, bpm: 85, screen: 5.8 },
};

const BASELINES = { steps: 8500, sleep: 7.5, bpm: 68, screen: 3.0 };

const SCORES: Record<string, number> = {
  "Sophie L.": 82,
  "Marie D.": 55,
  "Lea R.": 35,
  "Anna K.": 68,
};

export default function FichePatiente() {
  const [selected, setSelected] = useState(PATIENTS[0]);
  const [notes, setNotes] = useState("");
  const metrics = DEMO_METRICS[selected];
  const score = SCORES[selected];

  const chartData = Array.from({ length: 21 }, (_, i) => ({
    date: `J${i + 1}`,
    score: Math.min(100, 12 + i * (score / 25) + Math.round(Math.random() * 8 - 4)),
  }));

  const scoreColor =
    score >= 70 ? "text-danger" : score >= 40 ? "text-warning" : "text-success";

  return (
    <div>
      {/* En-tete */}
      <div className="flex items-center gap-4">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="rounded-lg border border-gray-300 px-4 py-2 text-sm"
        >
          {PATIENTS.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>
        <span className="text-2xl">{getRiskEmoji(score)}</span>
        <span className={`text-3xl font-bold ${scoreColor}`}>{score}/100</span>
        <span className="text-sm text-gray-500">{getRiskLabel(score)}</span>
      </div>

      {/* Metriques vs baseline */}
      <h2 className="mt-6 text-lg font-semibold text-gray-700">
        Metriques vs Baseline (J1-J7)
      </h2>
      <div className="mt-3 grid grid-cols-4 gap-4">
        <MetricComparison emoji="👟" label="Pas" current={metrics.steps} baseline={BASELINES.steps} unit="pas" />
        <MetricComparison emoji="😴" label="Sommeil" current={metrics.sleep} baseline={BASELINES.sleep} unit="h" />
        <MetricComparison emoji="❤️" label="BPM" current={metrics.bpm} baseline={BASELINES.bpm} unit="bpm" />
        <MetricComparison emoji="📱" label="Ecran" current={metrics.screen} baseline={BASELINES.screen} unit="h" />
      </div>

      {/* Graphique evolution score */}
      <h2 className="mt-8 text-lg font-semibold text-gray-700">
        📈 Evolution du score
      </h2>
      <div className="mt-3 rounded-xl bg-white p-4 shadow-sm">
        <ScoreChart data={chartData} height={280} />
      </div>

      {/* Notes du medecin */}
      <h2 className="mt-8 text-lg font-semibold text-gray-700">
        📝 Analyse du medecin
      </h2>
      <div className="mt-3 rounded-xl bg-white p-4 shadow-sm">
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Ecrivez votre analyse ici..."
          className="w-full rounded-lg border border-gray-200 p-3 text-sm"
          rows={4}
        />
        <button className="mt-2 rounded-lg bg-primary px-4 py-2 text-sm text-white hover:bg-primary-dark">
          💾 Enregistrer
        </button>
      </div>
    </div>
  );
}
