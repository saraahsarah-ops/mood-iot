"use client";

import Link from "next/link";
import { motion } from "framer-motion";

export default function AboutPage() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <div className="relative overflow-hidden bg-gradient-to-b from-slate-900 via-[#0a1172] to-slate-900 py-16 text-center lg:py-24">
        {/* Decorative elements */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute left-1/2 top-0 h-96 w-96 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#00c8e8]/20 blur-3xl" />
        </div>
        
        <div className="relative z-10 flex flex-col items-center px-4">
          <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary-400 to-primary-700 shadow-xl shadow-primary-500/25">
            <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" />
            </svg>
          </div>
          <h1 className="text-4xl font-extrabold tracking-tight text-white lg:text-5xl">
            Qu'est-ce que Mood-IoT ?
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg font-medium text-slate-300">
            Une plateforme de télépsychiatrie innovante conçue pour prévenir les rechutes chez les patients dépressifs grâce à la collecte de données IoT et l'analyse prédictive par Machine Learning.
          </p>
        </div>
      </div>

      <div className="mx-auto max-w-5xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-12 lg:grid-cols-3">
          
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="rounded-3xl border border-gray-100 bg-white p-8 shadow-card"
          >
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-primary-50 text-primary-500">
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 1.5H8.25A2.25 2.25 0 006 3.75v16.5a2.25 2.25 0 002.25 2.25h7.5A2.25 2.25 0 0018 20.25V3.75a2.25 2.25 0 00-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 18.75h3" />
              </svg>
            </div>
            <h3 className="mb-3 text-xl font-bold text-gray-900">Données IoT</h3>
            <p className="text-[15px] leading-relaxed text-gray-600">
              Nous collectons des biomarqueurs digitaux en temps réel via des capteurs portables (montres intelligentes et smartphones) : rythme cardiaque, qualité du sommeil et niveau d'activité physique.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="rounded-3xl border border-gray-100 bg-white p-8 shadow-card"
          >
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-purple-50 text-purple-500">
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941" />
              </svg>
            </div>
            <h3 className="mb-3 text-xl font-bold text-gray-900">Analyse IA</h3>
            <p className="text-[15px] leading-relaxed text-gray-600">
              Notre modèle de Machine Learning (XGBoost) analyse l'évolution de ces variables pour détecter précocement les anomalies et calculer un score de risque de rechute dépressive.
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="rounded-3xl border border-gray-100 bg-white p-8 shadow-card"
          >
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-50 text-emerald-500">
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="mb-3 text-xl font-bold text-gray-900">Alertes Médecins</h3>
            <p className="text-[15px] leading-relaxed text-gray-600">
              Les psychiatres sont alertés en temps réel sur ce tableau de bord dès qu'un patient présente un risque de rechute critique, leur permettant d'intervenir rapidement (téléconsultation).
            </p>
          </motion.div>
        </div>

        <div className="mt-16 text-center">
          <Link
            href="/login"
            className="inline-flex items-center justify-center rounded-xl bg-gradient-to-r from-primary-500 to-primary-600 px-8 py-3.5 text-sm font-bold text-white shadow-lg shadow-primary-500/25 transition hover:shadow-xl hover:shadow-primary-500/30"
          >
            Retourner à la connexion
          </Link>
        </div>
      </div>
    </div>
  );
}
