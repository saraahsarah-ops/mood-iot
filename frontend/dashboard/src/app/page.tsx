"use client";
import { useState } from "react";
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
  const critiques = DEMO_PATIENTS.filter((p) => p.score >= 70).length;
  const surveiller = DEMO_PATIENTS.filter((p) => p.score >= 40 && p.score < 70).length;
  const stables = DEMO_PATIENTS.filter((p) => p.score < 40).length;
  const scoreMoyen = Math.round(
    DEMO_PATIENTS.reduce((s, p) => s + p.score, 0) / DEMO_PATIENTS.length,
  );

  return (
    <div>
      {/* Titre */}
      <h1 className="text-2xl font-bold text-gray-800">
        🏥 Mood-IoT — Dashboard Medecin
      </h1>
      <p className="mt-1 text-sm text-gray-500">
        Suivi en temps reel des patientes depressives
      </p>

      {/* KPI Cards */}
      <div className="mt-6 grid grid-cols-4 gap-4">
        <KpiCard emoji="🔴" label="Alertes critiques" value={critiques} color="danger" />
        <KpiCard emoji="🟡" label="A surveiller" value={surveiller} color="warning" />
        <KpiCard emoji="🟢" label="Stables" value={stables} color="success" />
        <KpiCard emoji="📊" label="Score moyen" value={`${scoreMoyen}/100`} color="primary" />
      </div>

      {/* Liste des patients */}
      <h2 className="mt-8 text-lg font-semibold text-gray-700">Patientes</h2>
      <div className="mt-3 space-y-3">
        {DEMO_PATIENTS.sort((a, b) => b.score - a.score).map((p) => (
          <PatientCard
            key={p.id}
            name={p.name}
            score={p.score}
            coaching={p.coaching}
          />
        ))}
      </div>

      {/* Graphique evolution */}
      <h2 className="mt-8 text-lg font-semibold text-gray-700">
        📈 Evolution des scores (21 jours)
      </h2>
      <div className="mt-3 rounded-xl bg-white p-4 shadow-sm">
        <ScoreChart
          data={DEMO_CHART}
          patients={["Sophie", "Marie", "Lea", "Anna"]}
          height={350}
        />
      </div>
    </div>
  );
}
