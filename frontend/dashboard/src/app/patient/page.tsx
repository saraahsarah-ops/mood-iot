"use client";
import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import MetricComparison from "@/components/MetricComparison";
import ScoreChart from "@/components/ScoreChart";
import ClinicalHistory from "@/components/ClinicalHistory";
import Messagerie from "@/components/Messagerie";
import { getRiskEmoji, getRiskLabel } from "@/lib/types";
import {
  getPatients,
  getPatientMetrics,
  getLatestScore,
  getScoreHistory,
  createPatient,
  updatePatient,
  deletePatient,
  createTeleconsultSession,
  getMyProfile,
} from "@/lib/api";

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

interface NewPatientForm {
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  email: string;
  phone: string;
}

const EMPTY_FORM: NewPatientForm = {
  first_name: "",
  last_name: "",
  date_of_birth: "",
  gender: "female",
  email: "",
  phone: "",
};

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
  const [activeTab, setActiveTab] = useState<"metrics" | "history" | "messages">("metrics");

  // CRUD state
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showEditForm, setShowEditForm] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [formData, setFormData] = useState<NewPatientForm>(EMPTY_FORM);
  const [crudLoading, setCrudLoading] = useState(false);
  const [crudMsg, setCrudMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  // Teleconsultation depuis la fiche (patient pre-selectionne)
  const [showTeleconsultForm, setShowTeleconsultForm] = useState(false);
  const [tcDate, setTcDate] = useState("");
  const [tcDuration, setTcDuration] = useState(30);
  const [tcReason, setTcReason] = useState("");
  const [tcLoading, setTcLoading] = useState(false);

  function updateField(field: keyof NewPatientForm, value: string) {
    setFormData((prev) => ({ ...prev, [field]: value }));
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCrudLoading(true);
    setCrudMsg(null);
    try {
      await createPatient({
        first_name: formData.first_name,
        last_name: formData.last_name,
        date_of_birth: formData.date_of_birth,
        gender: formData.gender,
        email: formData.email,
        phone: formData.phone || undefined,
      });
      setCrudMsg({ type: "ok", text: "Patient cree avec succes" });
      setShowCreateForm(false);
      setFormData(EMPTY_FORM);
      // Reload patients list
      const res = await getPatients(1, 50);
      const list = (res.patients || []).map((p: any) => ({
        id: p.id,
        name: `${p.first_name} ${(p.last_name || "")[0]}.`,
      }));
      setPatientsList(list);
      setTimeout(() => setCrudMsg(null), 3000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erreur";
      setCrudMsg({ type: "err", text: msg });
    } finally {
      setCrudLoading(false);
    }
  }

  async function handleUpdate(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedId) return;
    setCrudLoading(true);
    setCrudMsg(null);
    try {
      await updatePatient(selectedId, {
        first_name: formData.first_name,
        last_name: formData.last_name,
        phone: formData.phone || undefined,
      });
      setCrudMsg({ type: "ok", text: "Patient mis a jour" });
      setShowEditForm(false);
      // Reload
      const res = await getPatients(1, 50);
      const list = (res.patients || []).map((p: any) => ({
        id: p.id,
        name: `${p.first_name} ${(p.last_name || "")[0]}.`,
      }));
      setPatientsList(list);
      setTimeout(() => setCrudMsg(null), 3000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erreur";
      setCrudMsg({ type: "err", text: msg });
    } finally {
      setCrudLoading(false);
    }
  }

  async function handleScheduleTeleconsult(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedId || !tcDate) return;
    setTcLoading(true);
    setCrudMsg(null);
    try {
      // psychiatre_id = id interne du medecin connecte (cf. /auth/me)
      const profile = await getMyProfile();
      await createTeleconsultSession({
        patient_id: selectedId,
        psychiatre_id: profile.id,
        scheduled_at: new Date(tcDate).toISOString(),
        duration_minutes: tcDuration,
        reason: tcReason || undefined,
      });
      setCrudMsg({ type: "ok", text: "Teleconsultation planifiee" });
      setShowTeleconsultForm(false);
      setTcDate("");
      setTcDuration(30);
      setTcReason("");
      setTimeout(() => setCrudMsg(null), 3000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erreur";
      setCrudMsg({ type: "err", text: msg });
    } finally {
      setTcLoading(false);
    }
  }

  async function handleDelete() {
    if (!selectedId) return;
    setCrudLoading(true);
    setCrudMsg(null);
    try {
      await deletePatient(selectedId);
      setCrudMsg({ type: "ok", text: "Patient supprime" });
      setShowDeleteConfirm(false);
      // Reload
      const res = await getPatients(1, 50);
      const list = (res.patients || []).map((p: any) => ({
        id: p.id,
        name: `${p.first_name} ${(p.last_name || "")[0]}.`,
      }));
      setPatientsList(list);
      if (list.length > 0) setSelectedId(list[0].id);
      else setSelectedId("");
      setTimeout(() => setCrudMsg(null), 3000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erreur";
      setCrudMsg({ type: "err", text: msg });
    } finally {
      setCrudLoading(false);
    }
  }

  function openEdit() {
    const p = patientsList.find((pt) => pt.id === selectedId);
    if (!p) return;
    const parts = p.name.split(" ");
    setFormData({
      first_name: parts[0] || "",
      last_name: parts.slice(1).join(" ").replace(".", "") || "",
      date_of_birth: "",
      gender: "",
      email: "",
      phone: "",
    });
    setShowEditForm(true);
    setCrudMsg(null);
  }

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
            bpm: Math.round(m.heart_rate_avg || 0),
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
          const h = await getScoreHistory(selectedId, 30);
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
        <div className="flex gap-2">
          <button
            onClick={() => { setShowCreateForm(true); setFormData(EMPTY_FORM); setCrudMsg(null); }}
            className="rounded-xl bg-primary-500 px-4 py-2 text-[13px] font-semibold text-white shadow-sm transition hover:bg-primary-600 hover:shadow-md active:scale-[0.98]"
          >
            + Nouveau patient
          </button>
          {selectedId && (
            <>
              <button
                onClick={() => { setShowTeleconsultForm(true); setCrudMsg(null); }}
                className="rounded-xl border border-primary-200 bg-primary-50 px-3 py-2 text-[13px] font-semibold text-primary-600 transition hover:bg-primary-100"
              >
                Teleconsultation
              </button>
              <button
                onClick={openEdit}
                className="rounded-xl border border-primary-200 bg-primary-50 px-3 py-2 text-[13px] font-semibold text-primary-600 transition hover:bg-primary-100"
              >
                Modifier
              </button>
              <button
                onClick={() => { setShowDeleteConfirm(true); setCrudMsg(null); }}
                className="rounded-xl border border-red-200 px-3 py-2 text-[13px] font-semibold text-red-500 transition hover:bg-red-50"
              >
                Supprimer
              </button>
            </>
          )}
        </div>
      </div>

      {/* CRUD feedback message */}
      {crudMsg && (
        <div className={`mt-3 rounded-xl border px-4 py-3 text-[13px] ${crudMsg.type === "ok" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-600"}`}>
          {crudMsg.text}
        </div>
      )}

      {/* Create Patient Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <form onSubmit={handleCreate} className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-[15px] font-bold text-gray-800">Nouveau patient</h3>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <input type="text" placeholder="Prenom *" value={formData.first_name} onChange={(e) => updateField("first_name", e.target.value)} required className="rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 placeholder-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20" />
              <input type="text" placeholder="Nom *" value={formData.last_name} onChange={(e) => updateField("last_name", e.target.value)} required className="rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 placeholder-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20" />
              <div>
                <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-gray-400">Date de naissance *</label>
                <input type="date" value={formData.date_of_birth} onChange={(e) => updateField("date_of_birth", e.target.value)} required className="w-full rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-gray-400">Genre *</label>
                <select value={formData.gender} onChange={(e) => updateField("gender", e.target.value)} className="w-full rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20">
                  <option value="female">Femme</option>
                  <option value="male">Homme</option>
                  <option value="other">Autre</option>
                </select>
              </div>
              <input type="email" placeholder="Email * (le patient recevra un lien pour creer son mot de passe)" value={formData.email} onChange={(e) => updateField("email", e.target.value)} required className="rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 placeholder-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20" />
              <input type="tel" placeholder="Telephone (optionnel)" value={formData.phone} onChange={(e) => updateField("phone", e.target.value)} className="rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 placeholder-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20" />
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" onClick={() => setShowCreateForm(false)} className="rounded-xl border border-gray-200 px-4 py-2 text-[13px] font-medium text-gray-600 transition hover:bg-gray-50">Annuler</button>
              <button type="submit" disabled={crudLoading} className="rounded-xl bg-primary-500 px-5 py-2 text-[13px] font-semibold text-white transition hover:bg-primary-600 disabled:opacity-50">{crudLoading ? "Creation..." : "Creer"}</button>
            </div>
          </form>
        </div>
      )}

      {/* Edit Patient Modal */}
      {showEditForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <form onSubmit={handleUpdate} className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-[15px] font-bold text-gray-800">Modifier patient</h3>
            <div className="mt-4 space-y-3">
              <input type="text" placeholder="Prenom" value={formData.first_name} onChange={(e) => updateField("first_name", e.target.value)} required className="w-full rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 placeholder-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20" />
              <input type="text" placeholder="Nom" value={formData.last_name} onChange={(e) => updateField("last_name", e.target.value)} required className="w-full rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 placeholder-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20" />
              <input type="tel" placeholder="Telephone" value={formData.phone} onChange={(e) => updateField("phone", e.target.value)} className="w-full rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 placeholder-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20" />
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" onClick={() => setShowEditForm(false)} className="rounded-xl border border-gray-200 px-4 py-2 text-[13px] font-medium text-gray-600 transition hover:bg-gray-50">Annuler</button>
              <button type="submit" disabled={crudLoading} className="rounded-xl bg-primary-500 px-5 py-2 text-[13px] font-semibold text-white transition hover:bg-primary-600 disabled:opacity-50">{crudLoading ? "Sauvegarde..." : "Enregistrer"}</button>
            </div>
          </form>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-[15px] font-bold text-gray-800">Confirmer la suppression</h3>
            <p className="mt-2 text-[13px] text-gray-500">
              Voulez-vous vraiment supprimer <span className="font-semibold text-gray-700">{selectedName}</span> et toutes ses donnees associees ? Cette action est irreversible.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setShowDeleteConfirm(false)} className="rounded-xl border border-gray-200 px-4 py-2 text-[13px] font-medium text-gray-600 transition hover:bg-gray-50">Annuler</button>
              <button onClick={handleDelete} disabled={crudLoading} className="rounded-xl bg-red-500 px-4 py-2 text-[13px] font-semibold text-white transition hover:bg-red-600 disabled:opacity-50">{crudLoading ? "Suppression..." : "Supprimer"}</button>
            </div>
          </div>
        </div>
      )}

      {/* Teleconsult Modal (planifier depuis la fiche, patient pre-selectionne) */}
      {showTeleconsultForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <form onSubmit={handleScheduleTeleconsult} className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
            <h3 className="text-[15px] font-bold text-gray-800">Planifier une teleconsultation</h3>
            <p className="mt-1 text-[13px] text-gray-400">Patient : <span className="font-semibold text-gray-600">{selectedName}</span></p>
            <div className="mt-4 space-y-3">
              <div>
                <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-gray-400">Date et heure *</label>
                <input type="datetime-local" value={tcDate} onChange={(e) => setTcDate(e.target.value)} required className="w-full rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20" />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-gray-400">Duree</label>
                <select value={tcDuration} onChange={(e) => setTcDuration(Number(e.target.value))} className="w-full rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20">
                  <option value={30}>30 min</option>
                  <option value={45}>45 min</option>
                  <option value={60}>60 min</option>
                </select>
              </div>
              <input type="text" placeholder="Motif (optionnel)" value={tcReason} onChange={(e) => setTcReason(e.target.value)} className="w-full rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 placeholder-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20" />
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" onClick={() => setShowTeleconsultForm(false)} className="rounded-xl border border-gray-200 px-4 py-2 text-[13px] font-medium text-gray-600 transition hover:bg-gray-50">Annuler</button>
              <button type="submit" disabled={tcLoading} className="rounded-xl bg-primary-500 px-5 py-2 text-[13px] font-semibold text-white transition hover:bg-primary-600 disabled:opacity-50">{tcLoading ? "Planification..." : "Planifier"}</button>
            </div>
          </form>
        </div>
      )}

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

      {/* Tabs */}
      <div className="mt-8 mb-4 flex border-b border-gray-200">
        <button
          onClick={() => setActiveTab("metrics")}
          className={`px-4 py-2 text-[14px] font-semibold transition ${activeTab === "metrics" ? "border-b-2 border-primary-500 text-primary-600" : "text-gray-500 hover:text-gray-700"}`}
        >
          Métriques & Santé
        </button>
        <button
          onClick={() => setActiveTab("history")}
          className={`px-4 py-2 text-[14px] font-semibold transition ${activeTab === "history" ? "border-b-2 border-primary-500 text-primary-600" : "text-gray-500 hover:text-gray-700"}`}
        >
          Historique Clinique & IA
        </button>
        <button
          onClick={() => setActiveTab("messages")}
          className={`px-4 py-2 text-[14px] font-semibold transition ${activeTab === "messages" ? "border-b-2 border-primary-500 text-primary-600" : "text-gray-500 hover:text-gray-700"}`}
        >
          Messagerie
        </button>
      </div>

      {activeTab === "metrics" && (
        <>
          {/* Metriques vs baseline */}
          <div className="mt-4">
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
        </>
      )}

      {activeTab === "history" && selectedId && (
        <div className="mt-4">
          <ClinicalHistory patientId={selectedId} />
        </div>
      )}

      {activeTab === "messages" && selectedId && (
        <div className="mt-4">
          <Messagerie patientId={selectedId} />
        </div>
      )}
    </div>
  );
}
