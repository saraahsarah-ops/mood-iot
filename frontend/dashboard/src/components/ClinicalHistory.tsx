"use client";
import { useState, useEffect } from "react";
import {
  getPatientHistory,
  generateAIAnalysis,
  getPatientCoaching,
} from "@/lib/api";

interface CoachingItem {
  id: string;
  title: string;
  body: string;
  created_at: string;
}

interface ClinicalHistoryProps {
  patientId: string;
}

export default function ClinicalHistory({ patientId }: ClinicalHistoryProps) {
  const [loading, setLoading] = useState(true);
  const [history, setHistory] = useState<any>(null);
  const [coaching, setCoaching] = useState<CoachingItem[]>([]);
  const [aiAnalysis, setAiAnalysis] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  useEffect(() => {
    async function loadHistory() {
      setLoading(true);
      try {
        const [hist, coach] = await Promise.all([
          getPatientHistory(patientId),
          getPatientCoaching(patientId).catch(() => ({ notifications: [] })),
        ]);
        setHistory(hist);
        setCoaching((coach.notifications || []) as CoachingItem[]);
      } catch (err) {
        console.error("Erreur chargement historique:", err);
      } finally {
        setLoading(false);
      }
    }
    if (patientId) loadHistory();
  }, [patientId]);

  async function handleGenerateAI() {
    setAiLoading(true);
    try {
      const data = await generateAIAnalysis(patientId);
      setAiAnalysis(data.analysis);
    } catch (err) {
      setAiAnalysis("Erreur lors de la génération de l'analyse IA.");
    } finally {
      setAiLoading(false);
    }
  }

  if (loading) return <div className="py-10 text-center text-[13px] text-gray-400">Chargement de l'historique...</div>;

  return (
    <div className="space-y-6">
      {/* AI Analysis Section */}
      <div className="rounded-2xl border border-primary-100 bg-primary-50/30 p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-[15px] font-bold text-primary-800">Analyse IA (Claude)</h3>
          <button
            onClick={handleGenerateAI}
            disabled={aiLoading}
            className="rounded-xl bg-primary-500 px-4 py-2 text-[12px] font-semibold text-white shadow-sm transition hover:bg-primary-600 disabled:opacity-50"
          >
            {aiLoading ? "Génération..." : "✨ Générer l'analyse"}
          </button>
        </div>
        {aiAnalysis ? (
          <div className="rounded-xl bg-white p-4 text-[13px] text-gray-700 whitespace-pre-wrap leading-relaxed shadow-inner">
            {aiAnalysis}
          </div>
        ) : (
          <p className="text-[13px] text-gray-500">
            Cliquez sur le bouton pour générer une synthèse clinique automatique de ce dossier.
          </p>
        )}
      </div>

      {/* Coaching IA envoyé au patient */}
      <div className="rounded-2xl border border-emerald-100 bg-emerald-50/30 p-5 shadow-sm">
        <h3 className="text-[15px] font-bold text-emerald-800 mb-3">
          Recommandations de coaching IA{" "}
          <span className="text-[12px] font-normal text-emerald-600">
            (envoyées au patient)
          </span>
        </h3>
        {coaching.length > 0 ? (
          <div className="space-y-3">
            {coaching.map((c) => (
              <div
                key={c.id}
                className="rounded-xl bg-white p-4 shadow-inner border border-emerald-50"
              >
                <p className="text-[12px] font-semibold text-emerald-600 mb-1">
                  🌱 {new Date(c.created_at).toLocaleString("fr-FR")}
                </p>
                <p className="text-[13px] text-gray-700 whitespace-pre-wrap leading-relaxed">
                  {c.body}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-[13px] text-gray-500">
            Aucune recommandation de coaching envoyée pour le moment.
          </p>
        )}
      </div>

      {/* History Timeline */}
      <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
        <h3 className="text-[15px] font-bold text-gray-800 mb-4">Historique des Appels & Notes</h3>
        
        {history?.teleconsults?.length > 0 || history?.notes?.length > 0 ? (
          <div className="space-y-4">
            {/* Sort everything by date descending */}
            {[...(history?.teleconsults || []).map((t: any) => ({ ...t, type: 'call', date: t.scheduled_at })),
              ...(history?.notes || []).map((n: any) => ({ ...n, type: 'note', date: n.created_at }))]
              .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
              .map((item, idx) => (
                <div key={idx} className="flex gap-4 p-3 rounded-xl border border-gray-100 bg-gray-50/50">
                  <div className="text-2xl">{item.type === 'call' ? '📹' : '📝'}</div>
                  <div>
                    <p className="text-[12px] font-semibold text-gray-500">
                      {new Date(item.date).toLocaleString('fr-FR')}
                    </p>
                    {item.type === 'call' ? (
                      <p className="text-[13px] text-gray-700">Appel vidéo - Statut: {item.status}</p>
                    ) : (
                      <p className="text-[13px] text-gray-700 whitespace-pre-wrap">{item.content}</p>
                    )}
                  </div>
                </div>
              ))}
          </div>
        ) : (
          <p className="text-center text-[13px] text-gray-400">Aucun historique disponible.</p>
        )}
      </div>
    </div>
  );
}
