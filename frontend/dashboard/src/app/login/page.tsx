"use client";

/**
 * Page de connexion du dashboard médecin.
 *
 * Depuis la migration Keycloak, on n'a plus de formulaire email/password
 * local : un seul bouton "Se connecter" déclenche le flow OIDC Authorization
 * Code + PKCE géré par NextAuth.js. L'utilisateur est redirigé vers la
 * hosted UI Keycloak (en français), gère email/Google/Apple/MFA TOTP, puis
 * revient sur le dashboard authentifié.
 */

import Link from "next/link";
import { motion } from "framer-motion";
import { useAuthStore } from "@/lib/auth";

export default function LoginPage() {
  const { login, loading, error, isAuthenticated } = useAuthStore();

  // Si deja connecte, NextAuth redirige automatiquement vers la page
  // d'origine ou /. Pas besoin de logique supplementaire ici.

  const badges = [
    {
      icon: (
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
        </svg>
      ),
      text: "OIDC + PKCE",
    },
    {
      icon: (
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
        </svg>
      ),
      text: "Conforme RGPD / HDS",
    },
    {
      icon: (
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      text: "MFA TOTP",
    },
  ];

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f4f6fb] px-4">
      <motion.div
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="w-full max-w-md rounded-2xl bg-white p-10 shadow-[0_4px_24px_rgba(0,0,0,0.06)]"
      >
        <div className="mb-8 flex flex-col items-center gap-2">
          <div className="text-4xl">💙</div>
          <h1 className="text-2xl font-bold text-[#0288d1]">Mood-IoT</h1>
          <p className="text-sm text-gray-500">Dashboard médecin</p>
        </div>

        {error && (
          <div
            className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
            role="alert"
          >
            {error}
          </div>
        )}

        <button
          type="button"
          onClick={() => void login()}
          disabled={loading}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#0288d1] px-4 py-3 text-sm font-semibold text-white shadow transition hover:bg-[#0277bd] disabled:opacity-60"
        >
          {loading ? (
            <>
              <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Connexion en cours…
            </>
          ) : (
            <>Se connecter</>
          )}
        </button>

        <p className="mt-3 text-center text-[12px] text-gray-400">
          Connexion sécurisée par Keycloak (OIDC).{" "}
          Email, Google ou Apple — selon votre configuration.
        </p>

        <div className="my-6 h-px bg-gray-100" />

        <p className="text-center text-sm text-gray-600">
          Pas encore de compte ?{" "}
          <Link
            href="/register/doctor"
            className="font-semibold text-[#0288d1] hover:underline"
          >
            S&apos;inscrire en tant que psychiatre
          </Link>
        </p>

        <div className="mt-6 flex flex-wrap items-center justify-center gap-3 text-[11px] text-gray-400">
          {badges.map((b, idx) => (
            <span key={idx} className="inline-flex items-center gap-1">
              {b.icon}
              {b.text}
            </span>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
