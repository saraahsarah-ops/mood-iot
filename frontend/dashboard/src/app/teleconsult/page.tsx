"use client";
import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  getTeleconsultSessions,
  createTeleconsultSession,
  joinTeleconsultSession,
  getPatients,
} from "@/lib/api";
import { useAuthStore } from "@/lib/auth";

interface TeleconsultSession {
  id: string;
  patient_id: string;
  patient_name?: string;
  psychiatre_id: string;
  scheduled_at: string;
  duration_minutes: number;
  status: "scheduled" | "in_progress" | "completed" | "cancelled";
  jitsi_url?: string;
}

interface PatientOption {
  id: string;
  first_name: string;
  last_name: string;
}

const STATUS_CONFIG: Record<
  string,
  { label: string; bg: string; text: string; dot?: string }
> = {
  scheduled: {
    label: "Planifiee",
    bg: "bg-blue-50",
    text: "text-blue-700",
    dot: "bg-blue-500",
  },
  in_progress: {
    label: "En cours",
    bg: "bg-green-50",
    text: "text-green-700",
    dot: "bg-green-500 animate-pulse",
  },
  completed: {
    label: "Terminee",
    bg: "bg-gray-100",
    text: "text-gray-600",
    dot: "bg-gray-400",
  },
  cancelled: {
    label: "Annulee",
    bg: "bg-red-50",
    text: "text-red-700",
    dot: "bg-red-500",
  },
};

export default function TeleconsultPage() {
  const user = useAuthStore((s) => s.user);

  const [sessions, setSessions] = useState<TeleconsultSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  /* Form state */
  const [patients, setPatients] = useState<PatientOption[]>([]);
  const [patientsLoading, setPatientsLoading] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(30);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  /* Joining state */
  const [joiningId, setJoiningId] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    try {
      const res = await getTeleconsultSessions();
      const list: TeleconsultSession[] = res.sessions || res || [];
      setSessions(list);
    } catch (err) {
      console.error("Erreur chargement teleconsultations:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const openForm = async () => {
    setShowForm(true);
    setFormError(null);
    if (patients.length === 0) {
      setPatientsLoading(true);
      try {
        // page_size plafonné à 100 côté backend (Query le=100) — 200 renvoyait
        // un 422 et laissait la liste vide.
        const res = await getPatients(1, 100);
        const list = res.patients || [];
        setPatients(list);
      } catch (err) {
        console.error("Erreur chargement patients:", err);
      } finally {
        setPatientsLoading(false);
      }
    }
  };

  const handleCreate = async () => {
    if (!selectedPatient || !scheduledAt) {
      setFormError("Veuillez selectionner un patient et une date.");
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      await createTeleconsultSession({
        patient_id: selectedPatient,
        psychiatre_id: user?.id || "",
        scheduled_at: new Date(scheduledAt).toISOString(),
        duration_minutes: durationMinutes,
        reason: reason || undefined,
      });
      setShowForm(false);
      setSelectedPatient("");
      setScheduledAt("");
      setDurationMinutes(30);
      setReason("");
      await loadSessions();
    } catch (err) {
      console.error("Erreur creation session:", err);
      setFormError("Impossible de creer la session. Reessayez.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleJoin = async (sessionId: string) => {
    setJoiningId(sessionId);
    try {
      const res = await joinTeleconsultSession(sessionId);
      const url = res.jitsi_url || res.url;
      if (url) {
        window.open(url, "_blank", "noopener,noreferrer");
      }
      await loadSessions();
    } catch (err) {
      console.error("Erreur rejoindre session:", err);
    } finally {
      setJoiningId(null);
    }
  };

  const formatDate = (iso: string): string => {
    try {
      return new Date(iso).toLocaleString("fr-FR", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  };

  const now = new Date();
  const upcoming = sessions.filter(
    (s) => s.status === "scheduled" || s.status === "in_progress"
  );
  const past = sessions.filter(
    (s) => s.status === "completed" || s.status === "cancelled"
  );

  /* ── Loading state ─────────────────────────────────── */
  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary-500 border-t-transparent" />
          <p className="text-[13px] text-gray-400">Chargement...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-enter">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-gray-800">
            Teleconsultation
          </h1>
          <p className="mt-1 text-[13px] text-gray-400">
            Gerez vos sessions de teleconsultation avec les patients
          </p>
        </div>
        <button
          onClick={openForm}
          className="rounded-xl bg-primary-500 px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-primary-600"
        >
          + Nouvelle session
        </button>
      </div>

      {/* Inline form */}
      {showForm && (
        <div className="mt-6 rounded-xl bg-white p-4 shadow-card">
          <h2 className="text-[15px] font-semibold text-gray-700">
            Planifier une teleconsultation
          </h2>

          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {/* Patient select */}
            <div>
              <label className="mb-1 block text-[13px] font-medium text-gray-500">
                Patient
              </label>
              {patientsLoading ? (
                <div className="flex h-10 items-center rounded-lg border border-gray-200 px-3">
                  <span className="text-[13px] text-gray-400">Chargement...</span>
                </div>
              ) : (
                <select
                  value={selectedPatient}
                  onChange={(e) => setSelectedPatient(e.target.value)}
                  className="h-10 w-full rounded-lg border border-gray-200 px-3 text-[13px] text-gray-700 outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                >
                  <option value="">Selectionner...</option>
                  {patients.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.first_name} {p.last_name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Date / time */}
            <div>
              <label className="mb-1 block text-[13px] font-medium text-gray-500">
                Date et heure
              </label>
              <input
                type="datetime-local"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
                className="h-10 w-full rounded-lg border border-gray-200 px-3 text-[13px] text-gray-700 outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
              />
            </div>

            {/* Duration */}
            <div>
              <label className="mb-1 block text-[13px] font-medium text-gray-500">
                Duree (min)
              </label>
              <select
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(Number(e.target.value))}
                className="h-10 w-full rounded-lg border border-gray-200 px-3 text-[13px] text-gray-700 outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
              >
                <option value={15}>15 min</option>
                <option value={30}>30 min</option>
                <option value={45}>45 min</option>
                <option value={60}>60 min</option>
              </select>
            </div>

            {/* Reason */}
            <div className="sm:col-span-2 lg:col-span-3">
              <label className="mb-1 block text-[13px] font-medium text-gray-500">
                Motif de consultation (optionnel)
              </label>
              <input
                type="text"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Ex: Suivi mensuel, ajustement traitement..."
                className="h-10 w-full rounded-lg border border-gray-200 px-3 text-[13px] text-gray-700 outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
              />
            </div>

            {/* Actions */}
            <div className="flex items-end gap-2">
              <button
                onClick={handleCreate}
                disabled={submitting}
                className="h-10 rounded-xl bg-primary-500 px-4 text-[13px] font-semibold text-white transition-colors hover:bg-primary-600 disabled:opacity-50"
              >
                {submitting ? "Creation..." : "Planifier"}
              </button>
              <button
                onClick={() => setShowForm(false)}
                className="h-10 rounded-xl border border-gray-200 px-4 text-[13px] font-medium text-gray-500 transition-colors hover:bg-gray-50"
              >
                Annuler
              </button>
            </div>
          </div>

          {formError && (
            <p className="mt-3 text-[13px] text-red-500">{formError}</p>
          )}
        </div>
      )}

      {/* Empty state */}
      {sessions.length === 0 && (
        <div className="mt-16 flex flex-col items-center justify-center text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gray-100">
            <svg
              className="h-8 w-8 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15.75 10.5l4.72-4.72a.75.75 0 011.28.53v11.38a.75.75 0 01-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 002.25-2.25v-9a2.25 2.25 0 00-2.25-2.25h-9A2.25 2.25 0 002.25 7.5v9a2.25 2.25 0 002.25 2.25z"
              />
            </svg>
          </div>
          <p className="mt-4 text-[15px] font-semibold text-gray-500">
            Aucune teleconsultation
          </p>
          <p className="mt-1 text-[13px] text-gray-400">
            Planifiez une session pour commencer.
          </p>
        </div>
      )}

      {/* Upcoming sessions */}
      {upcoming.length > 0 && (
        <div className="mt-6">
          <h2 className="text-[15px] font-semibold text-gray-700">
            Sessions a venir
          </h2>
          <div className="mt-3 space-y-2.5">
            {upcoming.map((s) => (
              <SessionRow
                key={s.id}
                session={s}
                joiningId={joiningId}
                onJoin={handleJoin}
                formatDate={formatDate}
              />
            ))}
          </div>
        </div>
      )}

      {/* Past sessions */}
      {past.length > 0 && (
        <div className="mt-8">
          <h2 className="text-[15px] font-semibold text-gray-700">
            Sessions passees
          </h2>
          <div className="mt-3 space-y-2.5">
            {past.map((s) => (
              <SessionRow
                key={s.id}
                session={s}
                joiningId={joiningId}
                onJoin={handleJoin}
                formatDate={formatDate}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Session row component ───────────────────────────── */
function SessionRow({
  session,
  joiningId,
  onJoin,
  formatDate,
}: {
  session: TeleconsultSession;
  joiningId: string | null;
  onJoin: (id: string) => void;
  formatDate: (iso: string) => string;
}) {
  const cfg = STATUS_CONFIG[session.status] || STATUS_CONFIG.scheduled;
  const canJoin =
    session.status === "scheduled" || session.status === "in_progress";

  return (
    <div className="flex items-center justify-between rounded-xl bg-white px-4 py-3 shadow-card">
      <div className="flex items-center gap-4">
        {/* Avatar placeholder */}
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-50 text-[13px] font-bold text-primary-600">
          {(session.patient_name || "P")[0].toUpperCase()}
        </div>

        <div>
          <p className="text-[14px] font-semibold text-gray-800">
            {session.patient_name || `Patient ${session.patient_id.slice(0, 8)}`}
          </p>
          <p className="text-[13px] text-gray-400">
            {formatDate(session.scheduled_at)}
            {session.duration_minutes ? ` - ${session.duration_minutes} min` : ""}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Status badge */}
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-medium ${cfg.bg} ${cfg.text}`}
        >
          <span className={`inline-block h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
          {cfg.label}
        </span>

        {/* Join button */}
        {canJoin && (
          <button
            onClick={() => onJoin(session.id)}
            disabled={joiningId === session.id}
            className="rounded-xl bg-primary-500 px-3 py-1.5 text-[13px] font-semibold text-white transition-colors hover:bg-primary-600 disabled:opacity-50"
          >
            {joiningId === session.id ? "Connexion..." : "Rejoindre"}
          </button>
        )}

        {/* Detail link */}
        <Link
          href={`/teleconsult/${session.id}`}
          className="rounded-xl border border-gray-200 px-3 py-1.5 text-[13px] font-medium text-gray-500 transition-colors hover:bg-gray-50 hover:text-gray-700"
        >
          Details
        </Link>
      </div>
    </div>
  );
}
