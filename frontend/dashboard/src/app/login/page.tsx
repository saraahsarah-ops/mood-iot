"use client";

/**
 * Page de connexion du dashboard médecin (mise en page deux colonnes).
 *
 * Gauche : panneau de présentation Mood-IoT avec un carrousel de slides qui
 * défilent (expliquant le produit). Droite : la connexion OIDC.
 *
 * Depuis la migration Keycloak, un seul bouton "Se connecter" déclenche le flow
 * OIDC Authorization Code + PKCE géré par NextAuth.js (redirection vers la
 * hosted UI Keycloak en français : email/Google/Apple/MFA TOTP).
 */

import Link from "next/link";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/lib/auth";

interface Slide {
  emoji: string;
  title: string;
  desc: string;
}

const SLIDES: Slide[] = [
  {
    emoji: "📊",
    title: "Suivi continu du bien-être",
    desc: "Sommeil, activité physique, rythme cardiaque… collectés en continu depuis les objets connectés du patient.",
  },
  {
    emoji: "🧠",
    title: "Détection précoce du risque",
    desc: "Un score de risque calculé par IA et des facteurs explicables (SHAP) pour agir avant la crise.",
  },
  {
    emoji: "🌱",
    title: "Coaching IA personnalisé",
    desc: "Des recommandations bienveillantes générées pour chaque patient selon ses propres signaux.",
  },
  {
    emoji: "🎥",
    title: "Téléconsultation intégrée",
    desc: "Planifiez et lancez une visioconsultation sécurisée avec le patient en un clic.",
  },
];

const SLIDE_INTERVAL_MS = 4500;

const BADGES = [
  {
    text: "OIDC + PKCE",
    path: "M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z",
  },
  {
    text: "Conforme RGPD / HDS",
    path: "M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z",
  },
  {
    text: "MFA TOTP",
    path: "M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  },
];

export default function LoginPage() {
  const { login, loading, error } = useAuthStore();
  const [slide, setSlide] = useState(0);

  useEffect(() => {
    const timer = setInterval(
      () => setSlide((s) => (s + 1) % SLIDES.length),
      SLIDE_INTERVAL_MS,
    );
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="flex min-h-screen bg-[#f4f6fb]">
      {/* ── Gauche : présentation Mood-IoT (carrousel) — masqué sur mobile ── */}
      <aside className="relative hidden w-1/2 flex-col justify-between overflow-hidden bg-gradient-to-br from-[#0288d1] via-[#0277bd] to-[#01486f] p-12 text-white lg:flex">
        {/* halos décoratifs */}
        <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-white/10 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-20 -left-16 h-64 w-64 rounded-full bg-white/10 blur-2xl" />

        <div className="relative flex items-center gap-2">
          <span className="text-3xl">💙</span>
          <span className="text-xl font-bold tracking-tight">Mood-IoT</span>
        </div>

        <div className="relative h-72">
          <motion.div
            key={slide}
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="absolute inset-0 flex flex-col justify-center"
          >
            <div className="mb-6 text-6xl drop-shadow-sm">
              {SLIDES[slide].emoji}
            </div>
            <h2 className="mb-3 max-w-md text-3xl font-bold leading-tight">
              {SLIDES[slide].title}
            </h2>
            <p className="max-w-md text-lg leading-relaxed text-white/80">
              {SLIDES[slide].desc}
            </p>
          </motion.div>
        </div>

        <div className="relative flex gap-2">
          {SLIDES.map((s, i) => (
            <button
              key={s.title}
              type="button"
              onClick={() => setSlide(i)}
              aria-label={`Aller au slide ${i + 1}`}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                i === slide ? "w-8 bg-white" : "w-3 bg-white/40 hover:bg-white/60"
              }`}
            />
          ))}
        </div>
      </aside>

      {/* ── Droite : connexion ── */}
      <main className="flex w-full items-center justify-center px-4 lg:w-1/2">
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-md rounded-2xl bg-white p-10 shadow-[0_4px_24px_rgba(0,0,0,0.06)]"
        >
          <div className="mb-8 flex flex-col items-center gap-2">
            <div className="text-4xl lg:hidden">💙</div>
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
            Connexion sécurisée par Keycloak (OIDC). Email, Google ou Apple —
            selon votre configuration.
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
            {BADGES.map((b) => (
              <span key={b.text} className="inline-flex items-center gap-1">
                <svg
                  className="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d={b.path}
                  />
                </svg>
                {b.text}
              </span>
            ))}
          </div>
        </motion.div>
      </main>
    </div>
  );
}
