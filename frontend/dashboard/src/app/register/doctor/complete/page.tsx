"use client";

/**
 * Finalisation du profil médecin après login Keycloak.
 *
 * Cette page est ouverte au retour du callback NextAuth si le médecin n'a
 * pas encore de profil interne (registerDoctorProfile renverra 200 la
 * première fois). On lui demande RPPS, licence et spécialité, puis on
 * appelle `POST /auth/register-profile` avec role=psychiatre.
 */

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { registerDoctorProfile } from "@/lib/api";
import { useAuthStore } from "@/lib/auth";

export default function CompleteDoctorProfilePage() {
  const router = useRouter();
  const { isAuthenticated, user, loading: authLoading } = useAuthStore();
  const [form, setForm] = useState({
    first_name: user?.first_name ?? "",
    last_name: user?.last_name ?? "",
    rpps_number: "",
    license_number: "",
    speciality: "Psychiatrie",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f4f6fb]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#22c55e] border-t-transparent" />
          <p className="text-[13px] text-gray-500">Vérification de la session…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    // Pas connecte -> le layout va rediriger vers /login, mais en attendant
    // on affiche un message clair plutot qu'une page blanche.
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f4f6fb] px-4">
        <div className="w-full max-w-md rounded-2xl bg-white p-10 text-center shadow">
          <div className="text-4xl mb-3">🔒</div>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">
            Session requise
          </h2>
          <p className="text-sm text-gray-600 mb-6">
            Vous devez d&apos;abord créer un compte ou vous connecter pour
            finaliser votre inscription.
          </p>
          <a
            href="/register/doctor"
            className="inline-flex items-center justify-center rounded-lg bg-[#22c55e] px-4 py-2 text-sm font-semibold text-white hover:bg-[#16a34a]"
          >
            Créer mon compte
          </a>
        </div>
      </div>
    );
  }

  const isValid =
    form.first_name.trim().length >= 1 &&
    form.last_name.trim().length >= 1 &&
    /^\d{11}$/.test(form.rpps_number) &&
    form.license_number.trim().length >= 4 &&
    form.speciality.trim().length >= 1;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid) return;
    setLoading(true);
    setError(null);
    try {
      await registerDoctorProfile({
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        rpps_number: form.rpps_number,
        license_number: form.license_number.trim(),
        speciality: form.speciality.trim(),
      });
      setSuccess(true);
      setTimeout(() => router.push("/"), 2200);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Erreur lors de la création du profil",
      );
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f4f6fb] px-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="w-full max-w-md rounded-2xl bg-white p-10 text-center shadow"
        >
          <div className="text-5xl mb-3">✅</div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            Compte créé
          </h2>
          <p className="text-sm text-gray-600">
            Votre inscription est en attente de validation par un
            administrateur. Vous recevrez un email dès que votre compte sera
            approuvé.
          </p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f4f6fb] px-4">
      <motion.form
        onSubmit={handleSubmit}
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md rounded-2xl bg-white p-10 shadow"
      >
        <h1 className="text-xl font-bold text-[#22c55e] mb-1">
          Informations professionnelles
        </h1>
        <p className="text-sm text-gray-500 mb-6">
          Bienvenue {user?.email}. Complétez votre profil pour soumettre votre
          inscription.
        </p>

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field
              label="Prénom"
              value={form.first_name}
              onChange={(v) => setForm({ ...form, first_name: v })}
              required
            />
            <Field
              label="Nom"
              value={form.last_name}
              onChange={(v) => setForm({ ...form, last_name: v })}
              required
            />
          </div>
          <Field
            label="Numéro RPPS (11 chiffres)"
            value={form.rpps_number}
            onChange={(v) => setForm({ ...form, rpps_number: v.replace(/\D/g, "").slice(0, 11) })}
            required
            placeholder="10003456789"
            inputMode="numeric"
            pattern="\d{11}"
            hint="L'identifiant RPPS figure sur votre carte professionnelle."
          />
          <Field
            label="Numéro de licence"
            value={form.license_number}
            onChange={(v) => setForm({ ...form, license_number: v })}
            required
          />
          <Field
            label="Spécialité"
            value={form.speciality}
            onChange={(v) => setForm({ ...form, speciality: v })}
            required
          />
        </div>

        <button
          type="submit"
          disabled={!isValid || loading}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg bg-[#22c55e] px-4 py-3 text-sm font-semibold text-white shadow hover:bg-[#16a34a] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "Création…" : "Soumettre mon inscription"}
        </button>
      </motion.form>
    </div>
  );
}

interface FieldProps {
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  placeholder?: string;
  hint?: string;
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
  pattern?: string;
}

function Field({
  label,
  value,
  onChange,
  required,
  placeholder,
  hint,
  inputMode,
  pattern,
}: FieldProps) {
  return (
    <label className="block">
      <span className="text-[13px] font-medium text-gray-700">
        {label}
        {required && <span className="text-red-500"> *</span>}
      </span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        placeholder={placeholder}
        inputMode={inputMode}
        pattern={pattern}
        className="mt-1 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-[#22c55e] focus:outline-none focus:ring-2 focus:ring-[#22c55e]/20"
      />
      {hint && <p className="mt-1 text-[11px] text-gray-400">{hint}</p>}
    </label>
  );
}
