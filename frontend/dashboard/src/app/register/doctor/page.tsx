"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { registerDoctor } from "@/lib/api";
import { motion } from "framer-motion";

interface PasswordRule {
  label: string;
  test: (pw: string) => boolean;
}

const PASSWORD_RULES: PasswordRule[] = [
  { label: "Au moins 8 caracteres", test: (pw) => pw.length >= 8 },
  { label: "Une lettre majuscule", test: (pw) => /[A-Z]/.test(pw) },
  { label: "Un chiffre", test: (pw) => /\d/.test(pw) },
  { label: "Un caractere special (!@#$...)", test: (pw) => /[^A-Za-z0-9]/.test(pw) },
];

export default function DoctorRegisterPage() {
  const [form, setForm] = useState({
    email: "",
    password: "",
    confirmPassword: "",
    first_name: "",
    last_name: "",
    rpps_number: "",
    license_number: "",
    speciality: "Psychiatrie",
    institution_name: "",
    rgpd_consent: false,
  });

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [showRppsTooltip, setShowRppsTooltip] = useState(false);

  const passwordResults = useMemo(
    () => PASSWORD_RULES.map((rule) => ({ ...rule, passed: rule.test(form.password) })),
    [form.password],
  );

  const allPasswordRulesPassed = passwordResults.every((r) => r.passed);
  const passwordsMatch = form.password === form.confirmPassword && form.confirmPassword.length > 0;

  function updateField(field: string, value: string | boolean) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!allPasswordRulesPassed) {
      setError("Le mot de passe ne respecte pas les criteres requis.");
      return;
    }
    if (!passwordsMatch) {
      setError("Les mots de passe ne correspondent pas.");
      return;
    }
    if (!form.rgpd_consent) {
      setError("Vous devez accepter la politique de confidentialite.");
      return;
    }

    setLoading(true);
    try {
      await registerDoctor({
        email: form.email,
        password: form.password,
        first_name: form.first_name,
        last_name: form.last_name,
        rpps_number: form.rpps_number,
        license_number: form.license_number,
        speciality: form.speciality || "Psychiatrie",
        rgpd_consent: form.rgpd_consent,
        institution_name: form.institution_name || undefined,
      });
      setSuccess(true);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Une erreur est survenue.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  /* ── Shared input classes ───────────────────────────── */
  const inputClass =
    "w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-[13px] text-gray-800 placeholder-gray-400 transition focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20";

  const labelClass =
    "mb-1.5 block text-[12px] font-semibold uppercase tracking-wider text-gray-500";

  /* ── Eye toggle button (reused for both password fields) */
  function EyeToggle({ visible, onToggle }: { visible: boolean; onToggle: () => void }) {
    return (
      <button
        type="button"
        onClick={onToggle}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
        tabIndex={-1}
      >
        {visible ? (
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
          </svg>
        ) : (
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        )}
      </button>
    );
  }

  /* ── Success state ──────────────────────────────────── */
  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="w-full max-w-md rounded-2xl border border-green-200 bg-white p-10 text-center shadow-xl"
        >
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-green-100">
            <svg className="h-7 w-7 text-green-600" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
          </div>
          <h2 className="text-xl font-bold text-gray-900">Inscription soumise</h2>
          <p className="mt-3 text-[14px] leading-relaxed text-gray-600">
            En attente de validation par un administrateur. Vous recevrez un email de confirmation.
          </p>
          <Link
            href="/login"
            className="mt-6 inline-block rounded-xl bg-[#0f172a] px-6 py-3 text-[13px] font-semibold text-white transition hover:bg-[#1e293b]"
          >
            Retour a la connexion
          </Link>
        </motion.div>
      </div>
    );
  }

  /* ── Main layout ────────────────────────────────────── */
  return (
    <div className="flex min-h-screen">
      {/* ── Left brand panel ─────────────────────────── */}
      <div className="relative hidden w-[420px] shrink-0 flex-col justify-between overflow-hidden bg-[#0f172a] p-10 lg:flex">
        {/* Decorative blurs */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -left-20 -top-20 h-72 w-72 rounded-full bg-blue-500/8 blur-3xl" />
          <div className="absolute bottom-16 right-6 h-56 w-56 rounded-full bg-blue-400/6 blur-3xl" />
        </div>

        {/* Logo */}
        <div className="relative z-10">
          <div className="mb-3 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-400 to-blue-600 shadow-lg shadow-blue-500/20">
              <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" />
              </svg>
            </div>
            <span className="text-xl font-extrabold tracking-tight text-white">Mood-IoT</span>
          </div>
          <p className="mt-1 text-[14px] font-medium text-blue-300">
            Plateforme de telepsychiatrie intelligente
          </p>
        </div>

        {/* Feature list */}
        <div className="relative z-10 space-y-5">
          {[
            { title: "Suivi en temps reel", desc: "Donnees IoT et scores cliniques automatises" },
            { title: "Teleconsultation securisee", desc: "Visio integree conforme HDS" },
            { title: "Conformite RGPD", desc: "Hebergement certifie donnees de sante" },
          ].map((item) => (
            <div key={item.title} className="flex gap-3">
              <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-blue-500/15">
                <svg className="h-3.5 w-3.5 text-blue-400" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              </div>
              <div>
                <p className="text-[13px] font-semibold text-white">{item.title}</p>
                <p className="text-[12px] text-slate-400">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Bottom */}
        <p className="relative z-10 text-[11px] text-slate-500">
          Mood-IoT v2.0 — Fil Rouge Master ADE 2026
        </p>
      </div>

      {/* ── Right form panel ─────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: "easeOut" }}
        className="flex flex-1 items-start justify-center overflow-y-auto bg-gray-50 px-6 py-12 lg:py-10"
      >
        <div className="w-full max-w-lg">
          {/* Mobile logo */}
          <div className="mb-8 text-center lg:hidden">
            <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-blue-400 to-blue-600 shadow-lg shadow-blue-500/20">
              <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" />
              </svg>
            </div>
            <h1 className="text-xl font-extrabold tracking-tight text-gray-900">Mood-IoT</h1>
          </div>

          {/* Heading */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-gray-900">Inscription Medecin</h2>
            <p className="mt-1.5 text-[14px] text-gray-500">
              Creez votre compte professionnel de sante
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* ── Email ──────────────────────────────── */}
            <div>
              <label htmlFor="reg-email" className={labelClass}>
                Adresse email
              </label>
              <input
                id="reg-email"
                type="email"
                required
                value={form.email}
                onChange={(e) => updateField("email", e.target.value)}
                placeholder="dr.martin@exemple.fr"
                className={inputClass}
              />
            </div>

            {/* ── Password ───────────────────────────── */}
            <div>
              <label htmlFor="reg-password" className={labelClass}>
                Mot de passe
              </label>
              <div className="relative">
                <input
                  id="reg-password"
                  type={showPassword ? "text" : "password"}
                  required
                  value={form.password}
                  onChange={(e) => updateField("password", e.target.value)}
                  placeholder="••••••••••"
                  className={`${inputClass} pr-12`}
                />
                <EyeToggle visible={showPassword} onToggle={() => setShowPassword((v) => !v)} />
              </div>

              {/* Password requirements */}
              {form.password.length > 0 && (
                <div className="mt-2.5 grid grid-cols-2 gap-x-4 gap-y-1">
                  {passwordResults.map((rule) => (
                    <div key={rule.label} className="flex items-center gap-1.5">
                      <div
                        className={`h-1.5 w-1.5 rounded-full transition ${
                          rule.passed ? "bg-green-500" : "bg-red-400"
                        }`}
                      />
                      <span
                        className={`text-[11px] transition ${
                          rule.passed ? "text-green-600" : "text-red-500"
                        }`}
                      >
                        {rule.label}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* ── Confirm password ────────────────────── */}
            <div>
              <label htmlFor="reg-confirm" className={labelClass}>
                Confirmer le mot de passe
              </label>
              <div className="relative">
                <input
                  id="reg-confirm"
                  type={showConfirm ? "text" : "password"}
                  required
                  value={form.confirmPassword}
                  onChange={(e) => updateField("confirmPassword", e.target.value)}
                  placeholder="••••••••••"
                  className={`${inputClass} pr-12 ${
                    form.confirmPassword.length > 0
                      ? passwordsMatch
                        ? "border-green-400 focus:border-green-500 focus:ring-green-500/20"
                        : "border-red-300 focus:border-red-500 focus:ring-red-500/20"
                      : ""
                  }`}
                />
                <EyeToggle visible={showConfirm} onToggle={() => setShowConfirm((v) => !v)} />
              </div>
              {form.confirmPassword.length > 0 && !passwordsMatch && (
                <p className="mt-1 text-[11px] text-red-500">Les mots de passe ne correspondent pas</p>
              )}
            </div>

            {/* ── Name row ────────────────────────────── */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="reg-first" className={labelClass}>
                  Prenom
                </label>
                <input
                  id="reg-first"
                  type="text"
                  required
                  value={form.first_name}
                  onChange={(e) => updateField("first_name", e.target.value)}
                  placeholder="Jean"
                  className={inputClass}
                />
              </div>
              <div>
                <label htmlFor="reg-last" className={labelClass}>
                  Nom
                </label>
                <input
                  id="reg-last"
                  type="text"
                  required
                  value={form.last_name}
                  onChange={(e) => updateField("last_name", e.target.value)}
                  placeholder="Martin"
                  className={inputClass}
                />
              </div>
            </div>

            {/* ── RPPS ────────────────────────────────── */}
            <div>
              <label htmlFor="reg-rpps" className={labelClass}>
                <span className="flex items-center gap-1.5">
                  Numero RPPS
                  <span className="relative">
                    <button
                      type="button"
                      onMouseEnter={() => setShowRppsTooltip(true)}
                      onMouseLeave={() => setShowRppsTooltip(false)}
                      onFocus={() => setShowRppsTooltip(true)}
                      onBlur={() => setShowRppsTooltip(false)}
                      className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-gray-200 text-[10px] font-bold text-gray-500 transition hover:bg-gray-300"
                      tabIndex={-1}
                    >
                      ?
                    </button>
                    {showRppsTooltip && (
                      <span className="absolute bottom-full left-1/2 z-20 mb-2 w-56 -translate-x-1/2 rounded-lg bg-[#0f172a] px-3 py-2 text-[11px] font-normal normal-case tracking-normal text-white shadow-lg">
                        Numero du Repertoire Partage des Professionnels de Sante
                        <span className="absolute left-1/2 top-full -translate-x-1/2 border-4 border-transparent border-t-[#0f172a]" />
                      </span>
                    )}
                  </span>
                </span>
              </label>
              <input
                id="reg-rpps"
                type="text"
                required
                value={form.rpps_number}
                onChange={(e) => updateField("rpps_number", e.target.value)}
                placeholder="8xxxxxxxxxxxx"
                className={inputClass}
              />
            </div>

            {/* ── License ─────────────────────────────── */}
            <div>
              <label htmlFor="reg-license" className={labelClass}>
                Numero de licence
              </label>
              <input
                id="reg-license"
                type="text"
                required
                value={form.license_number}
                onChange={(e) => updateField("license_number", e.target.value)}
                placeholder="Numero d'ordre"
                className={inputClass}
              />
            </div>

            {/* ── Speciality ──────────────────────────── */}
            <div>
              <label htmlFor="reg-spec" className={labelClass}>
                Specialite
              </label>
              <input
                id="reg-spec"
                type="text"
                value={form.speciality}
                onChange={(e) => updateField("speciality", e.target.value)}
                className={inputClass}
              />
            </div>

            {/* ── Institution (optional) ──────────────── */}
            <div>
              <label htmlFor="reg-institution" className={labelClass}>
                Etablissement
                <span className="ml-1.5 text-[10px] font-normal normal-case tracking-normal text-gray-400">
                  (optionnel — vous deviendrez administrateur)
                </span>
              </label>
              <input
                id="reg-institution"
                type="text"
                value={form.institution_name}
                onChange={(e) => updateField("institution_name", e.target.value)}
                placeholder="Nom de l'etablissement"
                className={inputClass}
              />
            </div>

            {/* ── RGPD Consent ────────────────────────── */}
            <div className="flex items-start gap-3 rounded-xl border border-gray-200 bg-white p-4">
              <input
                id="reg-rgpd"
                type="checkbox"
                checked={form.rgpd_consent}
                onChange={(e) => updateField("rgpd_consent", e.target.checked)}
                className="mt-0.5 h-4 w-4 shrink-0 rounded border-gray-300 text-blue-500 accent-blue-500"
              />
              <label htmlFor="reg-rgpd" className="text-[13px] leading-relaxed text-gray-600">
                J&apos;accepte la{" "}
                <Link href="/privacy" className="font-medium text-blue-600 underline underline-offset-2 hover:text-blue-700">
                  politique de confidentialite
                </Link>{" "}
                et le traitement de mes donnees personnelles conformement au RGPD.
              </label>
            </div>

            {/* ── Error message ───────────────────────── */}
            {error && (
              <div className="flex items-start gap-2.5 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
                <svg className="mt-0.5 h-4 w-4 shrink-0 text-red-500" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
                <p className="text-[13px] text-red-600">{error}</p>
              </div>
            )}

            {/* ── Submit ──────────────────────────────── */}
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-[#0f172a] px-4 py-3.5 text-[13px] font-bold text-white shadow-lg shadow-slate-900/15 transition hover:bg-[#1e293b] hover:shadow-xl disabled:opacity-50"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Inscription en cours...
                </span>
              ) : (
                "Creer mon compte"
              )}
            </button>
          </form>

          {/* ── Login link ────────────────────────────── */}
          <p className="mt-6 text-center text-[13px] text-gray-500">
            Deja inscrit ?{" "}
            <Link href="/login" className="font-semibold text-[#0f172a] underline underline-offset-2 hover:text-blue-600">
              Se connecter
            </Link>
          </p>

          <p className="mt-6 text-center text-[11px] text-gray-400 lg:hidden">
            Mood-IoT v2.0 — Fil Rouge Master ADE 2026
          </p>
        </div>
      </motion.div>
    </div>
  );
}
