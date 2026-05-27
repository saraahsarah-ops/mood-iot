"use client";
import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getTeleconsultSession,
  getSessionNotes,
  addSessionNote,
  joinTeleconsultSession,
  endTeleconsultSession,
  deleteTeleconsultSession,
} from "@/lib/api";

/* ── Types ───────────────────────────────────────────── */
interface SessionDetail {
  id: string;
  patient_id: string;
  psychiatre_id: string;
  status: "scheduled" | "in_progress" | "completed" | "cancelled";
  scheduled_at: string;
  ended_at?: string;
  duration_minutes?: number;
  reason?: string;
  jitsi_url?: string;
  summary?: string;
}

interface SessionNote {
  id: string;
  session_id: string;
  author_id: string;
  content: string;
  note_type: string;
  is_private: boolean;
  created_at: string;
}

/* ── Status config (matches teleconsult list page) ──── */
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

const NOTE_TYPE_CONFIG: Record<string, { label: string; bg: string; text: string }> = {
  general: { label: "General", bg: "bg-gray-100", text: "text-gray-600" },
  observation: { label: "Observation", bg: "bg-purple-50", text: "text-purple-700" },
  prescription: { label: "Prescription", bg: "bg-amber-50", text: "text-amber-700" },
  follow_up: { label: "Suivi", bg: "bg-teal-50", text: "text-teal-700" },
};

/* ── Helpers ─────────────────────────────────────────── */
function truncateId(id: string): string {
  return id.length > 8 ? `${id.slice(0, 8)}...` : id;
}

function formatDate(iso: string): string {
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
}

/* ── Page component ──────────────────────────────────── */
export default function TeleconsultDetailPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.id as string;

  /* Data state */
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [notes, setNotes] = useState<SessionNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /* Action state */
  const [joining, setJoining] = useState(false);
  const [ending, setEnding] = useState(false);
  const [endSummary, setEndSummary] = useState("");
  const [showEndDialog, setShowEndDialog] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  /* Note form state */
  const [noteContent, setNoteContent] = useState("");
  const [noteType, setNoteType] = useState("general");
  const [notePrivate, setNotePrivate] = useState(false);
  const [submittingNote, setSubmittingNote] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);

  /* ── Fetch data ────────────────────────────────────── */
  const loadData = useCallback(async () => {
    try {
      const [sessionData, notesData] = await Promise.all([
        getTeleconsultSession(sessionId),
        getSessionNotes(sessionId),
      ]);
      setSession(sessionData);
      const notesList: SessionNote[] = Array.isArray(notesData)
        ? notesData
        : (notesData as any).notes || [];
      setNotes(notesList.sort((a, b) =>
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      ));
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erreur inconnue";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  /* ── Actions ───────────────────────────────────────── */
  const handleJoin = async () => {
    setJoining(true);
    try {
      const res = await joinTeleconsultSession(sessionId);
      const url = res.jitsi_url || res.url;
      if (url) {
        window.open(url, "_blank", "noopener,noreferrer");
      }
      await loadData();
    } catch (err) {
      console.error("Erreur rejoindre session:", err);
    } finally {
      setJoining(false);
    }
  };

  const handleEnd = async () => {
    setEnding(true);
    try {
      await endTeleconsultSession(sessionId, endSummary || undefined);
      setShowEndDialog(false);
      setEndSummary("");
      await loadData();
    } catch (err) {
      console.error("Erreur terminer session:", err);
    } finally {
      setEnding(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await deleteTeleconsultSession(sessionId);
      router.push("/teleconsult");
    } catch (err) {
      console.error("Erreur suppression session:", err);
      setDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  const handleAddNote = async () => {
    if (!noteContent.trim()) {
      setNoteError("Le contenu de la note est requis.");
      return;
    }
    setSubmittingNote(true);
    setNoteError(null);
    try {
      await addSessionNote(sessionId, {
        content: noteContent.trim(),
        note_type: noteType,
        is_private: notePrivate,
      });
      setNoteContent("");
      setNoteType("general");
      setNotePrivate(false);
      await loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erreur inconnue";
      setNoteError(`Impossible d'ajouter la note : ${message}`);
    } finally {
      setSubmittingNote(false);
    }
  };

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

  /* ── Error state ───────────────────────────────────── */
  if (error || !session) {
    return (
      <div className="page-enter">
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-red-50">
            <svg className="h-8 w-8 text-red-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
          </div>
          <p className="mt-4 text-[15px] font-semibold text-gray-600">
            {error || "Session introuvable"}
          </p>
          <button
            onClick={() => router.push("/teleconsult")}
            className="mt-4 rounded-xl bg-primary-500 px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-primary-600"
          >
            Retour aux sessions
          </button>
        </div>
      </div>
    );
  }

  const statusCfg = STATUS_CONFIG[session.status] || STATUS_CONFIG.scheduled;
  const canJoin = session.status === "scheduled" || session.status === "in_progress";
  const canEnd = session.status === "scheduled" || session.status === "in_progress";
  const canDelete = session.status !== "completed";

  return (
    <div className="page-enter space-y-6">
      {/* ── Back link ─────────────────────────────────── */}
      <button
        onClick={() => router.push("/teleconsult")}
        className="inline-flex items-center gap-1.5 text-[13px] font-medium text-gray-400 transition-colors hover:text-gray-600"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
        </svg>
        Retour aux teleconsultations
      </button>

      {/* ── Session Info Card ─────────────────────────── */}
      <div className="rounded-xl bg-white p-6 shadow-card">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          {/* Left: info */}
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-extrabold tracking-tight text-gray-800">
                Session de teleconsultation
              </h1>
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-medium ${statusCfg.bg} ${statusCfg.text}`}
              >
                <span className={`inline-block h-1.5 w-1.5 rounded-full ${statusCfg.dot}`} />
                {statusCfg.label}
              </span>
            </div>

            <div className="grid gap-2 text-[13px] sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <span className="font-medium text-gray-400">Patient</span>
                <p className="mt-0.5 font-semibold text-gray-700">
                  Patient {truncateId(session.patient_id)}
                </p>
              </div>
              <div>
                <span className="font-medium text-gray-400">Psychiatre</span>
                <p className="mt-0.5 font-semibold text-gray-700">
                  {truncateId(session.psychiatre_id)}
                </p>
              </div>
              <div>
                <span className="font-medium text-gray-400">Date prevue</span>
                <p className="mt-0.5 font-semibold text-gray-700">
                  {formatDate(session.scheduled_at)}
                </p>
              </div>
              {session.duration_minutes && (
                <div>
                  <span className="font-medium text-gray-400">Duree</span>
                  <p className="mt-0.5 font-semibold text-gray-700">
                    {session.duration_minutes} min
                  </p>
                </div>
              )}
              {session.reason && (
                <div className="sm:col-span-2">
                  <span className="font-medium text-gray-400">Motif</span>
                  <p className="mt-0.5 font-semibold text-gray-700">
                    {session.reason}
                  </p>
                </div>
              )}
              {session.status === "completed" && session.ended_at && (
                <div>
                  <span className="font-medium text-gray-400">Terminee le</span>
                  <p className="mt-0.5 font-semibold text-gray-700">
                    {formatDate(session.ended_at)}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Right: actions */}
          <div className="flex flex-wrap items-center gap-2">
            {canJoin && (
              <button
                onClick={handleJoin}
                disabled={joining}
                className="rounded-xl bg-primary-500 px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-primary-600 disabled:opacity-50"
              >
                {joining ? "Connexion..." : "Rejoindre"}
              </button>
            )}
            {canEnd && (
              <button
                onClick={() => setShowEndDialog(true)}
                className="rounded-xl border border-gray-200 px-4 py-2 text-[13px] font-medium text-gray-600 transition-colors hover:bg-gray-50"
              >
                Terminer la session
              </button>
            )}
            {canDelete && (
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="rounded-xl border border-red-200 px-4 py-2 text-[13px] font-medium text-red-500 transition-colors hover:bg-red-50"
              >
                Supprimer
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── End session dialog ────────────────────────── */}
      {showEndDialog && (
        <div className="rounded-xl bg-white p-5 shadow-card">
          <h3 className="text-[15px] font-semibold text-gray-700">
            Terminer la session
          </h3>
          <p className="mt-1 text-[13px] text-gray-400">
            Ajoutez un resume optionnel avant de terminer.
          </p>
          <textarea
            value={endSummary}
            onChange={(e) => setEndSummary(e.target.value)}
            placeholder="Resume de la session (optionnel)..."
            rows={3}
            className="mt-3 w-full rounded-lg border border-gray-200 px-3 py-2 text-[13px] text-gray-700 outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
          />
          <div className="mt-3 flex items-center gap-2">
            <button
              onClick={handleEnd}
              disabled={ending}
              className="rounded-xl bg-primary-500 px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-primary-600 disabled:opacity-50"
            >
              {ending ? "En cours..." : "Confirmer"}
            </button>
            <button
              onClick={() => {
                setShowEndDialog(false);
                setEndSummary("");
              }}
              className="rounded-xl border border-gray-200 px-4 py-2 text-[13px] font-medium text-gray-500 transition-colors hover:bg-gray-50"
            >
              Annuler
            </button>
          </div>
        </div>
      )}

      {/* ── Delete confirmation ───────────────────────── */}
      {showDeleteConfirm && (
        <div className="rounded-xl border border-red-100 bg-red-50 p-5">
          <h3 className="text-[15px] font-semibold text-red-700">
            Confirmer la suppression
          </h3>
          <p className="mt-1 text-[13px] text-red-600">
            Cette action est irreversible. La session et toutes ses notes seront supprimees.
          </p>
          <div className="mt-3 flex items-center gap-2">
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="rounded-xl bg-red-500 px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-red-600 disabled:opacity-50"
            >
              {deleting ? "Suppression..." : "Supprimer definitivement"}
            </button>
            <button
              onClick={() => setShowDeleteConfirm(false)}
              className="rounded-xl border border-gray-200 bg-white px-4 py-2 text-[13px] font-medium text-gray-500 transition-colors hover:bg-gray-50"
            >
              Annuler
            </button>
          </div>
        </div>
      )}

      {/* ── Session Notes ─────────────────────────────── */}
      <div className="rounded-xl bg-white p-6 shadow-card">
        <h2 className="text-[17px] font-bold text-gray-800">
          Notes de session
        </h2>

        {/* Notes list */}
        {notes.length === 0 ? (
          <div className="mt-6 flex flex-col items-center py-8 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gray-100">
              <svg className="h-6 w-6 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
            </div>
            <p className="mt-3 text-[13px] text-gray-400">
              Aucune note pour cette session.
            </p>
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {notes.map((note) => {
              const typeCfg = NOTE_TYPE_CONFIG[note.note_type] || NOTE_TYPE_CONFIG.general;
              return (
                <div
                  key={note.id}
                  className="rounded-lg border border-gray-100 bg-gray-50/50 px-4 py-3"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${typeCfg.bg} ${typeCfg.text}`}
                    >
                      {typeCfg.label}
                    </span>
                    {note.is_private && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-yellow-50 px-2 py-0.5 text-[11px] font-medium text-yellow-700">
                        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                        </svg>
                        Privee
                      </span>
                    )}
                    <span className="text-[11px] text-gray-400">
                      par {truncateId(note.author_id)}
                    </span>
                    <span className="text-[11px] text-gray-400">
                      {formatDate(note.created_at)}
                    </span>
                  </div>
                  <p className="mt-2 whitespace-pre-wrap text-[13px] leading-relaxed text-gray-700">
                    {note.content}
                  </p>
                </div>
              );
            })}
          </div>
        )}

        {/* ── Add note form ───────────────────────────── */}
        <div className="mt-6 border-t border-gray-100 pt-5">
          <h3 className="text-[15px] font-semibold text-gray-700">
            Ajouter une note
          </h3>

          <textarea
            value={noteContent}
            onChange={(e) => setNoteContent(e.target.value)}
            placeholder="Contenu de la note..."
            rows={4}
            className="mt-3 w-full rounded-lg border border-gray-200 px-3 py-2 text-[13px] text-gray-700 outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
          />

          <div className="mt-3 flex flex-wrap items-center gap-4">
            {/* Note type */}
            <div>
              <label className="mb-1 block text-[12px] font-medium text-gray-400">
                Type
              </label>
              <select
                value={noteType}
                onChange={(e) => setNoteType(e.target.value)}
                className="h-9 rounded-lg border border-gray-200 px-3 text-[13px] text-gray-700 outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
              >
                <option value="general">General</option>
                <option value="observation">Observation</option>
                <option value="prescription">Prescription</option>
                <option value="follow_up">Suivi</option>
              </select>
            </div>

            {/* Private checkbox */}
            <label className="flex cursor-pointer items-center gap-2 self-end pb-0.5">
              <input
                type="checkbox"
                checked={notePrivate}
                onChange={(e) => setNotePrivate(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300 text-primary-500 focus:ring-primary-500"
              />
              <span className="text-[13px] text-gray-600">Note privee</span>
            </label>

            {/* Submit */}
            <div className="ml-auto self-end">
              <button
                onClick={handleAddNote}
                disabled={submittingNote || !noteContent.trim()}
                className="rounded-xl bg-primary-500 px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-primary-600 disabled:opacity-50"
              >
                {submittingNote ? "Envoi..." : "Ajouter la note"}
              </button>
            </div>
          </div>

          {noteError && (
            <p className="mt-3 text-[13px] text-red-500">{noteError}</p>
          )}
        </div>
      </div>
    </div>
  );
}
