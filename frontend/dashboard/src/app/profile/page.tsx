"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/lib/auth";
import { getDoctorProfile, updateDoctorProfile } from "@/lib/api";

interface DoctorData {
  user_id: string;
  email: string;
  first_name: string;
  last_name: string;
  speciality: string | null;
  rpps_number: string | null;
  license_number: string | null;
  institution_name: string | null;
  registration_status: string;
  created_at: string;
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    approved: "bg-emerald-50 text-emerald-600 border-emerald-200",
    pending_approval: "bg-amber-50 text-amber-600 border-amber-200",
    rejected: "bg-red-50 text-red-600 border-red-200",
  };
  const labels: Record<string, string> = {
    approved: "Approuve",
    pending_approval: "En attente",
    rejected: "Rejete",
  };
  return (
    <span
      className={`inline-flex rounded-full border px-3 py-1 text-[12px] font-semibold ${colors[status] || "bg-gray-50 text-gray-600 border-gray-200"}`}
    >
      {labels[status] || status}
    </span>
  );
}

function InfoRow({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex items-start justify-between border-b border-gray-100 py-3 last:border-0">
      <span className="text-[12px] font-semibold uppercase tracking-wider text-gray-400">
        {label}
      </span>
      <span className="text-[14px] font-medium text-gray-800 text-right max-w-[60%]">
        {value || "—"}
      </span>
    </div>
  );
}

export default function ProfilePage() {
  const user = useAuthStore((s) => s.user);
  const [profile, setProfile] = useState<DoctorData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit mode
  const [editing, setEditing] = useState(false);
  const [editFirst, setEditFirst] = useState("");
  const [editLast, setEditLast] = useState("");
  const [editSpec, setEditSpec] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await getDoctorProfile();
        setProfile(data);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Erreur inconnue";
        setError(msg);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  function startEdit() {
    if (!profile) return;
    setEditFirst(profile.first_name || "");
    setEditLast(profile.last_name || "");
    setEditSpec(profile.speciality || "");
    setEditing(true);
    setSaveMsg(null);
  }

  async function handleSave() {
    setSaving(true);
    setSaveMsg(null);
    try {
      const updated = await updateDoctorProfile({
        first_name: editFirst,
        last_name: editLast,
        speciality: editSpec || undefined,
      });
      setProfile((prev) => (prev ? { ...prev, ...updated } : prev));
      setEditing(false);
      setSaveMsg("Profil mis a jour avec succes");
      setTimeout(() => setSaveMsg(null), 3000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erreur";
      setSaveMsg(msg);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="page-enter flex items-center justify-center py-32">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary-500 border-t-transparent" />
          <p className="text-[13px] text-gray-400">Chargement du profil...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-enter">
        <h1 className="text-2xl font-extrabold tracking-tight text-gray-800">
          Mon profil
        </h1>
        <div className="mt-6 rounded-2xl border border-gray-100 bg-white p-8 text-center shadow-card">
          <p className="text-[14px] text-gray-500">
            Profil medecin non disponible.
          </p>
          <p className="mt-2 text-[13px] text-gray-400">
            Connecte en tant que: <span className="font-medium text-gray-700">{user?.email}</span>
          </p>
          <p className="mt-1 text-[13px] text-gray-400">
            Role: <span className="font-medium text-gray-700">{user?.role}</span>
          </p>
          <p className="mt-3 text-[12px] text-red-400">{error}</p>
        </div>
      </div>
    );
  }

  if (!profile) return null;

  return (
    <div className="page-enter">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-gray-800">
            Mon profil
          </h1>
          <p className="mt-1 text-[13px] text-gray-400">
            Informations du compte medecin
          </p>
        </div>
        <StatusBadge status={profile.registration_status} />
      </div>

      {/* Success message */}
      {saveMsg && (
        <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-[13px] text-emerald-700">
          {saveMsg}
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Identity card */}
        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-card">
          <div className="flex items-center justify-between">
            <h2 className="text-[15px] font-bold text-gray-700">Identite</h2>
            {!editing && (
              <button
                onClick={startEdit}
                className="rounded-xl bg-primary-50 px-3 py-1.5 text-[12px] font-semibold text-primary-600 transition hover:bg-primary-100"
              >
                Modifier
              </button>
            )}
          </div>

          {editing ? (
            <div className="mt-4 space-y-3">
              <div>
                <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                  Prenom
                </label>
                <input
                  type="text"
                  value={editFirst}
                  onChange={(e) => setEditFirst(e.target.value)}
                  className="w-full rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                  Nom
                </label>
                <input
                  type="text"
                  value={editLast}
                  onChange={(e) => setEditLast(e.target.value)}
                  className="w-full rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-gray-400">
                  Specialite
                </label>
                <input
                  type="text"
                  value={editSpec}
                  onChange={(e) => setEditSpec(e.target.value)}
                  placeholder="Psychiatrie, Psychologie..."
                  className="w-full rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 placeholder-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={() => setEditing(false)}
                  className="rounded-xl border border-gray-200 px-4 py-2 text-[13px] font-medium text-gray-600 transition hover:bg-gray-50"
                >
                  Annuler
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="rounded-xl bg-primary-500 px-4 py-2 text-[13px] font-semibold text-white transition hover:bg-primary-600 disabled:opacity-50"
                >
                  {saving ? "Sauvegarde..." : "Enregistrer"}
                </button>
              </div>
            </div>
          ) : (
            <div className="mt-4">
              <InfoRow label="Prenom" value={profile.first_name} />
              <InfoRow label="Nom" value={profile.last_name} />
              <InfoRow label="Specialite" value={profile.speciality} />
              <InfoRow label="Email" value={profile.email} />
            </div>
          )}
        </div>

        {/* Professional card */}
        <div className="rounded-2xl border border-gray-100 bg-white p-6 shadow-card">
          <h2 className="text-[15px] font-bold text-gray-700">
            Informations professionnelles
          </h2>
          <div className="mt-4">
            <InfoRow label="Numero RPPS" value={profile.rpps_number} />
            <InfoRow label="Licence" value={profile.license_number} />
            <InfoRow label="Institution" value={profile.institution_name} />
            <InfoRow label="Role" value={user?.role || "—"} />
            <InfoRow
              label="Membre depuis"
              value={
                profile.created_at
                  ? new Date(profile.created_at).toLocaleDateString("fr-FR", {
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                    })
                  : null
              }
            />
          </div>
        </div>
      </div>
    </div>
  );
}
