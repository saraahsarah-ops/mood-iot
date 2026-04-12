"use client";
import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
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
  const searchParams = useSearchParams();
  const initialName = searchParams.get("name");
  const [selected, setSelected] = useState(
    initialName && PATIENTS.includes(initialName) ? initialName : PATIENTS[0]
  );
  const [notes, setNotes] = useState("");
  const metrics = DEMO_METRICS[selected];
  const score = SCORES[selected];

  const chartData = Array.from({ length: 21 }, (_, i) => ({
    date: `J${i + 1}`,
    score: Math.min(100, 12 + i * (score / 25) + Math.round(Math.random() * 8 - 4)),
  }));

  const scoreColor =
    score >= 70 ? "text-danger-500" : score >= 40 ? "text-warning-500" : "text-success-500";
  const scoreBg =
    score >= 70 ? "bg-danger-50" : score >= 40 ? "bg-warning-50" : "bg-success-50";
  const badgeColor =
    score >= 70 ? "bg-danger-50 text-danger-500 border-danger-100" : score >= 40 ? "bg-warning-50 text-warning-500 border-warning-100" : "bg-success-50 text-success-500 border-success-100";

  return (
    <div className="page-enter">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-gray-800">
            Fiche patiente
          </h1>
          <p className="mt-1 text-[13px] text-gray-400">
            Details cliniques et metriques de sante
          </p>
        </div>
      </div>

      {/* Patient selector + score card */}
      <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-[13px] font-medium text-gray-700 shadow-card focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
        >
          {PATIENTS.map((p) => (
            <option key={p}>{p}</option>
          ))}
        </select>

        <div className={`flex items-center gap-3 rounded-xl border px-4 py-2.5 ${badgeColor}`}>
          <span className="text-2xl">{getRiskEmoji(score)}</span>
          <div>
            <p className={`text-2xl font-extrabold tracking-tight ${scoreColor}`}>{score}/100</p>
            <p className="text-[11px] font-semibold uppercase tracking-wider opacity-80">
              {getRiskLabel(score)}
            </p>
          </div>
        </div>
      </div>

      {/* Metriques vs baseline */}
      <div className="mt-8">
        <div className="flex items-center gap-2">
          <h2 className="text-[15px] font-bold text-gray-700">
            Metriques vs Baseline
          </h2>
          <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-[11px] font-medium text-gray-500">
            J1-J7
          </span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 xl:grid-cols-4">
          <MetricComparison emoji="👟" label="Pas" current={metrics.steps} baseline={BASELINES.steps} unit="pas" />
          <MetricComparison emoji="😴" label="Sommeil" current={metrics.sleep} baseline={BASELINES.sleep} unit="h" />
          <MetricComparison emoji="❤️" label="BPM" current={metrics.bpm} baseline={BASELINES.bpm} unit="bpm" />
          <MetricComparison emoji="📱" label="Ecran" current={metrics.screen} baseline={BASELINES.screen} unit="h" />
        </div>
      </div>

      {/* Graphique evolution score */}
      <div className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-bold text-gray-700">
            Evolution du score
          </h2>
          <span className="text-[12px] text-gray-400">21 derniers jours</span>
        </div>
        <div className="mt-3 rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
          <ScoreChart data={chartData} height={280} />
        </div>
      </div>

      {/* Notes du medecin */}
      <div className="mt-8">
        <h2 className="text-[15px] font-bold text-gray-700">
          Analyse du medecin
        </h2>
        <div className="mt-3 rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Ecrivez votre analyse clinique ici..."
            className="w-full rounded-xl border border-gray-200 bg-gray-50/50 p-4 text-[13px] text-gray-700 placeholder-gray-400 transition focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
            rows={4}
          />
          <div className="mt-3 flex items-center justify-between">
            <p className="text-[11px] text-gray-400">
              {notes.length > 0 ? `${notes.length} caracteres` : "Aucune note enregistree"}
            </p>
            <button className="rounded-xl bg-primary-500 px-5 py-2 text-[13px] font-semibold text-white shadow-sm transition hover:bg-primary-600 hover:shadow-md active:scale-[0.98]">
              Enregistrer
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
