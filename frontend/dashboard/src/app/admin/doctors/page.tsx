"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuthStore } from "@/lib/auth";
import {
  getPendingDoctors,
  approveDoctor,
  rejectDoctor,
  getInstitutionMembers,
  addInstitutionMember,
  removeInstitutionMember,
} from "@/lib/api";

/* ── Types ─────────────────────────────────────────────── */

interface PendingDoctor {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  speciality?: string;
  rpps_number: string;
  license_number: string;
  created_at: string;
}

interface InstitutionMember {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  speciality?: string;
  rpps_number: string;
  license_number: string;
}

interface MemberFormData {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  rpps_number: string;
  license_number: string;
  speciality: string;
}

const EMPTY_FORM: MemberFormData = {
  email: "",
  password: "",
  first_name: "",
  last_name: "",
  rpps_number: "",
  license_number: "",
  speciality: "",
};

/* ── Skeleton placeholders ─────────────────────────────── */

function SkeletonRow() {
  return (
    <div className="rounded-xl bg-white p-5 shadow-card">
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 animate-pulse rounded-full bg-gray-200" />
        <div className="flex-1 space-y-2">
          <div className="h-4 w-36 animate-pulse rounded-lg bg-gray-200" />
          <div className="h-3 w-48 animate-pulse rounded-lg bg-gray-200" />
        </div>
        <div className="h-8 w-20 animate-pulse rounded-lg bg-gray-200" />
      </div>
    </div>
  );
}

/* ── Rejection modal ───────────────────────────────────── */

function RejectModal({
  doctorName,
  onConfirm,
  onCancel,
}: {
  doctorName: string;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}) {
  const [reason, setReason] = useState("");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <h3 className="text-[15px] font-bold text-gray-800">
          Rejeter l&apos;inscription
        </h3>
        <p className="mt-1 text-[13px] text-gray-500">
          Veuillez indiquer la raison du rejet pour{" "}
          <span className="font-semibold text-gray-700">{doctorName}</span>.
        </p>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Raison du rejet..."
          rows={3}
          className="mt-3 w-full rounded-xl border border-gray-200 bg-gray-50/50 p-3 text-[13px] text-gray-700 placeholder-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
        />
        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="rounded-xl border border-gray-200 px-4 py-2 text-[13px] font-medium text-gray-600 transition hover:bg-gray-50"
          >
            Annuler
          </button>
          <button
            onClick={() => onConfirm(reason)}
            disabled={reason.trim().length === 0}
            className="rounded-xl bg-red-500 px-4 py-2 text-[13px] font-semibold text-white transition hover:bg-red-600 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Confirmer le rejet
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Main page ─────────────────────────────────────────── */

export default function AdminDoctorsPage() {
  const user = useAuthStore((s) => s.user);

  const [pending, setPending] = useState<PendingDoctor[]>([]);
  const [members, setMembers] = useState<InstitutionMember[]>([]);
  const [loadingPending, setLoadingPending] = useState(true);
  const [loadingMembers, setLoadingMembers] = useState(true);
  const [errorPending, setErrorPending] = useState<string | null>(null);
  const [errorMembers, setErrorMembers] = useState<string | null>(null);

  const [rejectTarget, setRejectTarget] = useState<PendingDoctor | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const [showAddForm, setShowAddForm] = useState(false);
  const [formData, setFormData] = useState<MemberFormData>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [formLoading, setFormLoading] = useState(false);

  const isAdmin = user?.role === "admin";
  const hasInstitution = isAdmin; // institution members endpoint is available for admins with institutions

  /* ── Data fetching ───────────────────────────────────── */

  const fetchPending = useCallback(async () => {
    setLoadingPending(true);
    setErrorPending(null);
    try {
      const data = await getPendingDoctors();
      setPending(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Erreur inconnue";
      setErrorPending(message);
    } finally {
      setLoadingPending(false);
    }
  }, []);

  const fetchMembers = useCallback(async () => {
    setLoadingMembers(true);
    setErrorMembers(null);
    try {
      const data = await getInstitutionMembers();
      setMembers(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Erreur inconnue";
      // If the endpoint returns 404/403 it means no institution
      setErrorMembers(message);
    } finally {
      setLoadingMembers(false);
    }
  }, []);

  useEffect(() => {
    if (!isAdmin) return;
    fetchPending();
    fetchMembers();
  }, [isAdmin, fetchPending, fetchMembers]);

  /* ── Actions ─────────────────────────────────────────── */

  async function handleApprove(doctorId: string) {
    setActionLoading(doctorId);
    try {
      await approveDoctor(doctorId);
      setPending((prev) => prev.filter((d) => d.id !== doctorId));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Erreur";
      setErrorPending(message);
    } finally {
      setActionLoading(null);
    }
  }

  async function handleRejectConfirm(reason: string) {
    if (!rejectTarget) return;
    const doctorId = rejectTarget.id;
    setActionLoading(doctorId);
    setRejectTarget(null);
    try {
      await rejectDoctor(doctorId, reason);
      setPending((prev) => prev.filter((d) => d.id !== doctorId));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Erreur";
      setErrorPending(message);
    } finally {
      setActionLoading(null);
    }
  }

  async function handleAddMember(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setFormLoading(true);
    try {
      await addInstitutionMember({
        email: formData.email,
        password: formData.password,
        first_name: formData.first_name,
        last_name: formData.last_name,
        rpps_number: formData.rpps_number,
        license_number: formData.license_number,
        speciality: formData.speciality || undefined,
      });
      setFormData(EMPTY_FORM);
      setShowAddForm(false);
      fetchMembers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Erreur";
      setFormError(message);
    } finally {
      setFormLoading(false);
    }
  }

  async function handleRemoveMember(userId: string) {
    setActionLoading(userId);
    try {
      await removeInstitutionMember(userId);
      setMembers((prev) => prev.filter((m) => m.id !== userId));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Erreur";
      setErrorMembers(message);
    } finally {
      setActionLoading(null);
    }
  }

  /* ── Form field helper ───────────────────────────────── */

  function updateField(field: keyof MemberFormData, value: string) {
    setFormData((prev) => ({ ...prev, [field]: value }));
  }

  /* ── Guard: non-admin ────────────────────────────────── */

  if (!isAdmin) {
    return (
      <div className="page-enter flex items-center justify-center py-32">
        <div className="rounded-2xl bg-white p-8 text-center shadow-card">
          <p className="text-[15px] font-bold text-gray-800">
            Acces restreint
          </p>
          <p className="mt-1 text-[13px] text-gray-500">
            Cette page est reservee aux administrateurs.
          </p>
        </div>
      </div>
    );
  }

  /* ── Render ──────────────────────────────────────────── */

  return (
    <div className="page-enter">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-gray-800">
            Gestion des medecins
          </h1>
          <p className="mt-1 text-[13px] text-gray-400">
            Approbations et gestion des membres de l&apos;institution
          </p>
        </div>
      </div>

      {/* ── Section 1: Pending Approvals ───────────────── */}
      <div className="mt-8">
        <div className="flex items-center gap-2">
          <h2 className="text-[15px] font-bold text-gray-700">
            Inscriptions en attente
          </h2>
          {!loadingPending && (
            <span className="rounded-full bg-primary-50 px-2.5 py-0.5 text-[11px] font-semibold text-primary-500">
              {pending.length}
            </span>
          )}
        </div>

        {errorPending && (
          <div className="mt-3 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-[13px] text-red-600">
            {errorPending}
          </div>
        )}

        <div className="mt-3 space-y-3">
          {loadingPending ? (
            <>
              <SkeletonRow />
              <SkeletonRow />
              <SkeletonRow />
            </>
          ) : pending.length === 0 ? (
            <div className="rounded-2xl border border-gray-100 bg-white py-10 text-center shadow-card">
              <p className="text-[13px] text-gray-400">
                Aucune inscription en attente
              </p>
            </div>
          ) : (
            pending.map((doc) => (
              <div
                key={doc.id}
                className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card transition hover:shadow-md"
              >
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex-1 space-y-1">
                    <p className="text-[15px] font-bold text-gray-800">
                      Dr. {doc.first_name} {doc.last_name}
                    </p>
                    <p className="text-[13px] text-gray-500">{doc.email}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {doc.speciality && (
                        <span className="rounded-full bg-primary-50 px-2.5 py-0.5 text-[11px] font-medium text-primary-600">
                          {doc.speciality}
                        </span>
                      )}
                      <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-[11px] font-medium text-gray-500">
                        RPPS: {doc.rpps_number}
                      </span>
                      <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-[11px] font-medium text-gray-500">
                        Licence: {doc.license_number}
                      </span>
                      <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-[11px] font-medium text-gray-500">
                        {new Date(doc.created_at).toLocaleDateString("fr-FR")}
                      </span>
                    </div>
                  </div>

                  <div className="flex shrink-0 gap-2">
                    <button
                      onClick={() => handleApprove(doc.id)}
                      disabled={actionLoading === doc.id}
                      className="rounded-xl bg-emerald-500 px-4 py-2 text-[13px] font-semibold text-white transition hover:bg-emerald-600 disabled:opacity-50"
                    >
                      {actionLoading === doc.id ? "..." : "Approuver"}
                    </button>
                    <button
                      onClick={() => setRejectTarget(doc)}
                      disabled={actionLoading === doc.id}
                      className="rounded-xl bg-red-500 px-4 py-2 text-[13px] font-semibold text-white transition hover:bg-red-600 disabled:opacity-50"
                    >
                      Rejeter
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* ── Section 2: Institution Members ─────────────── */}
      {hasInstitution && (
        <div className="mt-10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-[15px] font-bold text-gray-700">
                Membres de l&apos;institution
              </h2>
              {!loadingMembers && (
                <span className="rounded-full bg-primary-50 px-2.5 py-0.5 text-[11px] font-semibold text-primary-500">
                  {members.length}
                </span>
              )}
            </div>
            <button
              onClick={() => {
                setShowAddForm(!showAddForm);
                setFormError(null);
              }}
              className="rounded-xl bg-primary-500 px-4 py-2 text-[13px] font-semibold text-white shadow-sm transition hover:bg-primary-600 hover:shadow-md active:scale-[0.98]"
            >
              {showAddForm ? "Annuler" : "Ajouter un medecin"}
            </button>
          </div>

          {errorMembers && (
            <div className="mt-3 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-[13px] text-red-600">
              {errorMembers}
            </div>
          )}

          {/* Add member form */}
          {showAddForm && (
            <form
              onSubmit={handleAddMember}
              className="mt-4 rounded-2xl border border-gray-100 bg-white p-5 shadow-card"
            >
              <h3 className="text-[14px] font-bold text-gray-700">
                Nouveau medecin
              </h3>

              {formError && (
                <div className="mt-2 rounded-xl border border-red-100 bg-red-50 px-3 py-2 text-[13px] text-red-600">
                  {formError}
                </div>
              )}

              <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                <input
                  type="text"
                  placeholder="Prenom"
                  value={formData.first_name}
                  onChange={(e) => updateField("first_name", e.target.value)}
                  required
                  className="rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 placeholder-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                />
                <input
                  type="text"
                  placeholder="Nom"
                  value={formData.last_name}
                  onChange={(e) => updateField("last_name", e.target.value)}
                  required
                  className="rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 placeholder-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                />
                <input
                  type="email"
                  placeholder="Email"
                  value={formData.email}
                  onChange={(e) => updateField("email", e.target.value)}
                  required
                  className="rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 placeholder-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                />
                <input
                  type="password"
                  placeholder="Mot de passe"
                  value={formData.password}
                  onChange={(e) => updateField("password", e.target.value)}
                  required
                  className="rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 placeholder-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                />
                <input
                  type="text"
                  placeholder="Numero RPPS"
                  value={formData.rpps_number}
                  onChange={(e) => updateField("rpps_number", e.target.value)}
                  required
                  className="rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 placeholder-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                />
                <input
                  type="text"
                  placeholder="Numero de licence"
                  value={formData.license_number}
                  onChange={(e) => updateField("license_number", e.target.value)}
                  required
                  className="rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 placeholder-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                />
                <input
                  type="text"
                  placeholder="Specialite (optionnel)"
                  value={formData.speciality}
                  onChange={(e) => updateField("speciality", e.target.value)}
                  className="rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-[13px] text-gray-700 placeholder-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-500/20 sm:col-span-2"
                />
              </div>

              <div className="mt-4 flex justify-end">
                <button
                  type="submit"
                  disabled={formLoading}
                  className="rounded-xl bg-primary-500 px-5 py-2 text-[13px] font-semibold text-white shadow-sm transition hover:bg-primary-600 hover:shadow-md disabled:opacity-50"
                >
                  {formLoading ? "Ajout en cours..." : "Ajouter"}
                </button>
              </div>
            </form>
          )}

          {/* Members list */}
          <div className="mt-4 space-y-3">
            {loadingMembers ? (
              <>
                <SkeletonRow />
                <SkeletonRow />
              </>
            ) : members.length === 0 ? (
              <div className="rounded-2xl border border-gray-100 bg-white py-10 text-center shadow-card">
                <p className="text-[13px] text-gray-400">
                  Aucun membre dans l&apos;institution
                </p>
              </div>
            ) : (
              members.map((member) => (
                <div
                  key={member.id}
                  className="flex items-center justify-between rounded-2xl border border-gray-100 bg-white p-4 shadow-card transition hover:shadow-md"
                >
                  <div className="space-y-0.5">
                    <p className="text-[14px] font-semibold text-gray-800">
                      Dr. {member.first_name} {member.last_name}
                    </p>
                    <p className="text-[12px] text-gray-500">{member.email}</p>
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {member.speciality && (
                        <span className="rounded-full bg-primary-50 px-2 py-0.5 text-[10px] font-medium text-primary-600">
                          {member.speciality}
                        </span>
                      )}
                      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-500">
                        RPPS: {member.rpps_number}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleRemoveMember(member.id)}
                    disabled={actionLoading === member.id}
                    className="shrink-0 rounded-xl border border-red-200 px-3 py-1.5 text-[12px] font-semibold text-red-500 transition hover:bg-red-50 disabled:opacity-50"
                  >
                    {actionLoading === member.id ? "..." : "Retirer"}
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Reject modal */}
      {rejectTarget && (
        <RejectModal
          doctorName={`${rejectTarget.first_name} ${rejectTarget.last_name}`}
          onConfirm={handleRejectConfirm}
          onCancel={() => setRejectTarget(null)}
        />
      )}
    </div>
  );
}
