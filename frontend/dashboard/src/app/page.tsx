"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import KpiCard from "@/components/KpiCard";
import PatientCard from "@/components/PatientCard";
import ScoreChart from "@/components/ScoreChart";

/* Donnees de demonstration (remplacer par appels API) */
const DEMO_PATIENTS = [
  { id: "1", name: "Sophie L.", score: 82, coaching: "Votre medecin a ete informe et va vous contacter rapidement." },
  { id: "2", name: "Marie D.", score: 55, coaching: "Votre sommeil semble perturbe. Essayez une courte marche aujourd'hui." },
  { id: "3", name: "Lea R.", score: 35, coaching: "Continuez comme ca, votre routine est stable." },
  { id: "4", name: "Anna K.", score: 68, coaching: "Votre sommeil semble perturbe. Essayez une courte marche aujourd'hui." },
];

const DEMO_CHART = Array.from({ length: 21 }, (_, i) => ({
  date: `J${i + 1}`,
  Sophie: Math.min(100, 12 + i * 4 + Math.round(Math.random() * 10 - 5)),
  Marie: Math.min(100, 15 + i * 3 + Math.round(Math.random() * 10 - 5)),
  Lea: Math.min(100, 10 + i * 1.5 + Math.round(Math.random() * 8 - 4)),
  Anna: Math.min(100, 18 + i * 3.5 + Math.round(Math.random() * 10 - 5)),
}));

export default function VueGenerale() {
  const router = useRouter();
  const critiques = DEMO_PATIENTS.filter((p) => p.score >= 70).length;
  const surveiller = DEMO_PATIENTS.filter((p) => p.score >= 40 && p.score < 70).length;
  const stables = DEMO_PATIENTS.filter((p) => p.score < 40).length;
  const scoreMoyen = Math.round(
    DEMO_PATIENTS.reduce((s, p) => s + p.score, 0) / DEMO_PATIENTS.length,
  );

  const today = new Date().toLocaleDateString("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="page-enter">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-gray-800">
            Vue generale
          </h1>
          <p className="mt-1 text-[13px] text-gray-400">
            Suivi en temps reel des patientes depressives
          </p>
        </div>
        <p className="text-[13px] text-gray-400 capitalize">{today}</p>
      </div>

      {/* KPI Cards */}
      <div className="mt-6 grid grid-cols-2 gap-3 xl:grid-cols-4">
        <KpiCard
          emoji="🚨"
          label="Alertes critiques"
          value={critiques}
          color="danger"
          trend={{ value: 0, label: "vs hier" }}
        />
        <KpiCard
          emoji="⚡"
          label="A surveiller"
          value={surveiller}
          color="warning"
          trend={{ value: -15, label: "vs sem." }}
        />
        <KpiCard
          emoji="✓"
          label="Stables"
          value={stables}
          color="success"
          trend={{ value: 8, label: "vs sem." }}
        />
        <KpiCard
          emoji="📊"
          label="Score moyen"
          value={`${scoreMoyen}`}
          color="primary"
        />
      </div>

      {/* Chart */}
      <div className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-bold text-gray-700">
            Evolution des scores
          </h2>
          <span className="text-[12px] text-gray-400">21 derniers jours</span>
        </div>
        <div className="mt-3 rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
          <ScoreChart
            data={DEMO_CHART}
            patients={["Sophie", "Marie", "Lea", "Anna"]}
            height={300}
          />
        </div>
      </div>

      {/* Patient list */}
      <div className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-bold text-gray-700">Patientes</h2>
          <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-[11px] font-semibold text-gray-500">
            {DEMO_PATIENTS.length}
          </span>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-2.5 lg:grid-cols-2">
          {DEMO_PATIENTS.sort((a, b) => b.score - a.score).map((p) => (
            <PatientCard
              key={p.id}
              name={p.name}
              score={p.score}
              coaching={p.coaching}
              onClick={() => router.push(`/patient?name=${encodeURIComponent(p.name)}`)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
