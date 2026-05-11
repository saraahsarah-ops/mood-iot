"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";

const STORAGE_KEY = "mood_cookie_consent";

export default function CookieConsent() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const accepted = localStorage.getItem(STORAGE_KEY);
    if (!accepted) {
      setVisible(true);
    }
  }, []);

  const handleAccept = () => {
    localStorage.setItem(STORAGE_KEY, "true");
    setVisible(false);
  };

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ y: 100, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 100, opacity: 0 }}
          transition={{ type: "spring", stiffness: 260, damping: 24 }}
          className="fixed bottom-0 left-1/2 z-50 w-full max-w-lg -translate-x-1/2 px-4 pb-0"
        >
          <div className="rounded-t-2xl bg-white px-6 py-5 shadow-lg ring-1 ring-gray-100">
            <div className="flex items-start gap-3">
              {/* Lock icon */}
              <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary-50 text-primary-600">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                  className="h-4 w-4"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 1a4.5 4.5 0 00-4.5 4.5V9H5a2 2 0 00-2 2v6a2 2 0 002 2h10a2 2 0 002-2v-6a2 2 0 00-2-2h-.5V5.5A4.5 4.5 0 0010 1zm3 8V5.5a3 3 0 10-6 0V9h6z"
                    clipRule="evenodd"
                  />
                </svg>
              </span>
              <div className="flex-1">
                <p className="text-[13px] leading-relaxed text-gray-600">
                  Ce site utilise des cookies strictement necessaires au
                  fonctionnement du service. Aucun cookie publicitaire n'est
                  utilise.
                </p>
                <div className="mt-3 flex items-center gap-3">
                  <button
                    onClick={handleAccept}
                    className="rounded-lg bg-primary-600 px-4 py-1.5 text-[13px] font-medium text-white transition-colors hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
                  >
                    Accepter
                  </button>
                  <Link
                    href="/privacy"
                    className="text-[13px] font-medium text-gray-500 transition-colors hover:text-gray-700"
                  >
                    En savoir plus
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
