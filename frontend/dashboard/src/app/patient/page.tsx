"use client";
import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import MetricComparison from "@/components/MetricComparison";
import ScoreChart from "@/components/ScoreChart";
import { getRiskEmoji, getRiskLabel } from "@/lib/types";
import { getPatients, getPatientMetrics, getLatestScore, getScoreHistory } from "@/lib/api";

interface PatientOption {
  id: string;
  name: string;
}

interface DailyMetrics {
  steps: number;
  sleep: number;
  bpm: number;
  screen: number;
}

const DEFAULT_BASELINES: DailyMetrics = { steps: 8500, sleep: 7.5, bpm: 68, screen: 3.0 };

export default function FichePatiente() {
  const searchParams = useSearchParams();
  const initialId = searchParams.get("id");

  const [patientsList, setPatientsList] = useState<PatientOption[]>([]);
  const [selectedId, setSelectedId] = useState<string>(initialId || "");
  const [score, setScore] = useState(0);
  const [metrics, setMetrics] = useState<DailyMetrics>({ steps: 0, sleep: 0, bpm: 0, screen: 0 });
  const [baselines, setBaselines] = useState<DailyMetrics>(DEFAULT_BASELINES);
  const [chartData, setChartData] = useState<Record<string, string | number>[]>([]);
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);

  // Load patients list
  useEffect(() => {
    async function loadPatients() {
      try {
        const res = await getPatients(1, 50);
        const list = (res.patients || []).map((p: any) => ({
          id: p.id,
          name: `${p.first_name} ${(p.last_name || "")[0]}.`,
        }));
        setPatientsList(list);
        if (!selectedId && list.length > 0) {
          setSelectedId(list[0].id);
        }
      } catch (err) {
        console.error("Erreur chargement patients:", err);
      }
    }
    loadPatients();
  }, []);

  // Load selected patient data
  useEffect(() => {
    if (!selectedId) return;

    async function loadPatientData() {
      setLoading(true);
      try {
        // Fetch latest score
        try {
          const s = await getLatestScore(selectedId);
          setScore(Math.round(s.score));
        } catch {
          setScore(0);
        }

        // Fetch patient metrics (latest aggregate + baselines)
        try {
          const m = await getPatientMetrics(selectedId);
          setMetrics({
            steps: m.step_count || 0,
            sleep: Math.round(((m.sleep_duration_min || 0) / 60) * 10) / 10,
            bpm: m.heart_rate_avg || 0,
            screen: Math.round(((m.screen_time_min || 0) / 60) * 10) / 10,
          });
          if (m.baselines) {
            const bl = m.baselines;
            setBaselines({
              steps: Math.round(bl.step_count || DEFAULT_BASELINES.steps),
              sleep: Math.round(((bl.sleep_duration_min || DEFAULT_BASELINES.sleep * 60) / 60) * 10) / 10,
              bpm: Math.round(bl.heart_rate_avg || DEFAULT_BASELINES.bpm),
              screen: Math.round(((bl.screen_time_min || DEFAULT_BASELINES.screen * 60) / 60) * 10) / 10,
            });
          }
        } catch {
          // Use defaults
        }

        // Fetch score history
        try {
          const h = await getScoreHistory(selectedId, 21);
          const scores = (h.scores || []).reverse();
          setChartData(
            scores.map((s: any) => ({
              date: s.date.slice(5), // MM-DD
              score: Math.round(s.score),
            }))
          );
        } catch {
          setChartData([]);
        }
      } catch (err) {
        console.error("Erreur:", err);
      } finally {
        setLoading(false);
      }
    }
    loadPatientData();
  }, [selectedId]);

  const scoreColor =
    score >= 70
      ? "text-danger-500"
      : score >= 40
        ? "text-warning-500"
        : "text-success-500";
  const badgeColor =
    score >= 70
      ? "bg-danger-50 text-danger-500 border-danger-100"
      : score >= 40
        ? "bg-warning-50 text-warning-500 border-warning-100"
        : "bg-success-50 text-success-500 border-success-100";

  const selectedName =
    patientsList.find((p) => p.id === selectedId)?.name || "...";

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
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          className="rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-[13px] font-medium text-gray-700 shadow-card focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
        >
          {patientsList.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>

        <div
          className={`flex items-center gap-3 rounded-xl border px-4 py-2.5 ${badgeColor}`}
        >
          <span className="text-2xl">{getRiskEmoji(score)}</span>
          <div>
            <p
              className={`text-2xl font-extrabold tracking-tight ${scoreColor}`}
            >
              {loading ? "..." : `${score}/100`}
            </p>
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
            Derniere journee
          </span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 xl:grid-cols-4">
          <MetricComparison
            emoji="👟"
            label="Pas"
            current={metrics.steps}
            baseline={baselines.steps}
            unit="pas"
            higherIsBetter={true}
          />
          <MetricComparison
            emoji="😴"
            label="Sommeil"
            current={metrics.sleep}
            baseline={baselines.sleep}
            unit="h"
            higherIsBetter={true}
          />
          <MetricComparison
            emoji="❤️"
            label="BPM"
            current={metrics.bpm}
            baseline={baselines.bpm}
            unit="bpm"
            higherIsBetter={false}
          />
          <MetricComparison
            emoji="📱"
            label="Ecran"
            current={metrics.screen}
            baseline={baselines.screen}
            unit="h"
            higherIsBetter={false}
          />
        </div>
      </div>

      {/* Graphique evolution score */}
      <div className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-bold text-gray-700">
            Evolution du score
          </h2>
          <span className="text-[12px] text-gray-400">Historique</span>
        </div>
        <div className="mt-3 rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
          {chartData.length > 0 ? (
            <ScoreChart data={chartData} height={280} />
          ) : (
            <p className="py-10 text-center text-[13px] text-gray-400">
              {loading
                ? "Chargement..."
                : "Aucun historique de scores disponible"}
            </p>
          )}
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
              {notes.length > 0
                ? `${notes.length} caracteres`
                : "Aucune note enregistree"}
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
