"use client";

/**
 * Inscription d'un médecin psychiatre — version Keycloak.
 *
 * Avant : formulaire local email/password + RPPS + license envoye au
 * backend `/auth/register`.
 *
 * Maintenant :
 *   1. Cette page presente le bouton "Creer mon compte"
 *   2. Click -> redirection vers Keycloak (UI hosted FR) pour creer ou
 *      reutiliser un compte
 *   3. Retour sur /register/doctor/complete pour saisir RPPS / licence /
 *      specialite, puis POST /auth/register-profile avec role=psychiatre
 *   4. Le compte reste en pending_approval jusqu'a validation admin
 */

import Link from "next/link";
import { motion } from "framer-motion";
import { useAuthStore } from "@/lib/auth";

export default function DoctorRegisterPage() {
  const { login, loading } = useAuthStore();

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f4f6fb] px-4">
      <motion.div
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="w-full max-w-md rounded-2xl bg-white p-10 shadow-[0_4px_24px_rgba(0,0,0,0.06)]"
      >
        <div className="mb-8 flex flex-col items-center gap-2">
          <div className="text-4xl">🩺</div>
          <h1 className="text-2xl font-bold text-[#0288d1]">
            Inscription psychiatre
          </h1>
          <p className="text-sm text-gray-500 text-center">
            Créez votre compte médecin sécurisé
          </p>
        </div>

        <div className="mb-6 rounded-lg border border-blue-100 bg-blue-50 p-4 text-sm text-blue-900">
          <p className="font-semibold mb-2">Étapes :</p>
          <ol className="list-decimal list-inside space-y-1 text-[13px]">
            <li>Créez votre identifiant Keycloak (email, mot de passe, MFA)</li>
            <li>Renseignez vos informations professionnelles (RPPS, licence)</li>
            <li>Attendez la validation par un administrateur</li>
          </ol>
        </div>

        <button
          type="button"
          onClick={() => void login()}
          disabled={loading}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#0288d1] px-4 py-3 text-sm font-semibold text-white shadow transition hover:bg-[#0277bd] disabled:opacity-60"
        >
          {loading ? (
            <>
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Redirection en cours…
            </>
          ) : (
            <>Créer mon compte</>
          )}
        </button>

        <p className="mt-3 text-center text-[12px] text-gray-400">
          Vous serez redirigé vers la page d&apos;inscription sécurisée.
        </p>

        <div className="my-6 h-px bg-gray-100" />

        <p className="text-center text-sm text-gray-600">
          Déjà inscrit ?{" "}
          <Link
            href="/login"
            className="font-semibold text-[#0288d1] hover:underline"
          >
            Se connecter
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
