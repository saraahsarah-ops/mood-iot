"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import KpiCard from "@/components/KpiCard";
import PatientCard from "@/components/PatientCard";
import ScoreChart from "@/components/ScoreChart";
import { getPatients, getLatestScore, getScoreHistory } from "@/lib/api";

interface PatientData {
  id: string;
  name: string;
  score: number;
  coaching: string;
}

function coachingMessage(score: number): string {
  if (score >= 70)
    return "Votre medecin a ete informe et va vous contacter rapidement.";
  if (score >= 40)
    return "Votre sommeil semble perturbe. Essayez une courte marche aujourd'hui.";
  return "Continuez comme ca, votre routine est stable.";
}

export default function VueGenerale() {
  const router = useRouter();
  const [patients, setPatients] = useState<PatientData[]>([]);
  const [chartData, setChartData] = useState<Record<string, string | number | null>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        // 1. Fetch patients
        const res = await getPatients(1, 50);
        const patientList = res.patients || [];

        // 2. Fetch latest score for each patient
        // 2. Fetch latest score for each patient
        const scoresPromises = patientList.map(async (p) => {
          try {
            const s = await getLatestScore(p.id);
            return { p, score: Math.round(s.score) };
          } catch {
            return { p, score: 0 };
          }
        });

        const scoresResults = await Promise.all(scoresPromises);

        const withScores: PatientData[] = scoresResults.map(({ p, score }) => ({
          id: p.id,
          name: `${p.first_name} ${(p.last_name || "")[0]}.`,
          score,
          coaching: coachingMessage(score),
        }));
        setPatients(withScores);

        // 3. Fetch score history for chart (each patient last 21 days)
        const nameMap: Record<string, string> = {};
        const allDates = new Set<string>();
        const histories: Record<string, Record<string, number>> = {};

        const historiesPromises = withScores.map(async (p) => {
          const shortName = p.name.split(" ")[0];
          nameMap[p.id] = shortName;
          try {
            const h = await getScoreHistory(p.id, 21);
            return { shortName, scores: h.scores || [] };
          } catch {
            return { shortName, scores: [] };
          }
        });

        const historiesResults = await Promise.all(historiesPromises);

        for (const { shortName, scores } of historiesResults) {
          histories[shortName] = {};
          for (const s of scores) {
            const d = s.date;
            allDates.add(d);
            histories[shortName][d] = Math.round(s.score);
          }
        }

        const sortedDates = Array.from(allDates).sort();
        const chart = sortedDates.map((d) => {
          const entry: Record<string, string | number | null> = {
            date: d.slice(5), // MM-DD
          };
          for (const name of Object.keys(histories)) {
            // null si pas de score pour cette date (evite d'afficher 0)
            entry[name] = histories[name][d] ?? null;
          }
          return entry;
        });
        setChartData(chart);
      } catch (err) {
        console.error("Erreur chargement:", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const critiquesList = patients.filter((p) => p.score >= 70);
  const surveillerList = patients.filter((p) => p.score >= 40 && p.score < 70);
  const stablesList = patients.filter((p) => p.score < 40);
  const critiques = critiquesList.length;
  const surveiller = surveillerList.length;
  const stables = stablesList.length;
  const scoreMoyen =
    patients.length > 0
      ? Math.round(
          patients.reduce((s, p) => s + p.score, 0) / patients.length
        )
      : 0;

  const today = new Date().toLocaleDateString("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  const patientNames = patients.length > 0
    ? [...new Set(patients.map((p) => p.name.split(" ")[0]))]
    : [];

  const toKpiPatients = (list: PatientData[]) =>
    list.map((p) => ({ id: p.id, name: p.name, score: p.score }));

  const handlePatientClick = (id: string) => {
    const p = patients.find((pt) => pt.id === id);
    if (p) router.push(`/patient?id=${id}&name=${encodeURIComponent(p.name)}`);
  };

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary-500 border-t-transparent" />
          <p className="text-[13px] text-gray-400">
            Chargement des donnees...
          </p>
        </div>
      </div>
    );
  }

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
      <div className="mt-6 grid grid-cols-2 items-start gap-3 xl:grid-cols-4">
        <KpiCard
          emoji="🚨"
          label="Alertes critiques"
          value={critiques}
          color="danger"
          patients={toKpiPatients(critiquesList)}
          onPatientClick={handlePatientClick}
        />
        <KpiCard
          emoji="⚡"
          label="A surveiller"
          value={surveiller}
          color="warning"
          patients={toKpiPatients(surveillerList)}
          onPatientClick={handlePatientClick}
        />
        <KpiCard
          emoji="✓"
          label="Stables"
          value={stables}
          color="success"
          patients={toKpiPatients(stablesList)}
          onPatientClick={handlePatientClick}
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
          <span className="text-[12px] text-gray-400">Historique</span>
        </div>
        <div className="mt-3 rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
          {chartData.length > 0 ? (
            <ScoreChart
              data={chartData}
              patients={patientNames}
              height={300}
            />
          ) : (
            <p className="py-10 text-center text-[13px] text-gray-400">
              Aucun historique de scores disponible
            </p>
          )}
        </div>
      </div>

      {/* Patient list */}
      <div className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-bold text-gray-700">Patientes</h2>
          <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-[11px] font-semibold text-gray-500">
            {patients.length}
          </span>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-2.5 lg:grid-cols-2">
          {patients
            .sort((a, b) => b.score - a.score)
            .map((p) => (
              <PatientCard
                key={p.id}
                name={p.name}
                score={p.score}
                coaching={p.coaching}
                onClick={() =>
                  router.push(`/patient?id=${p.id}&name=${encodeURIComponent(p.name)}`)
                }
              />
            ))}
        </div>
      </div>
    </div>
  );
}
