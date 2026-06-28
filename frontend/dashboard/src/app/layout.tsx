"use client";
import "./globals.css";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { SessionProvider } from "next-auth/react";
import Sidebar from "@/components/Sidebar";
import { useAuthStore } from "@/lib/auth";
import { useNotifStore } from "@/lib/store";
import { getAllNotifications } from "@/lib/api";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.min.css";
import CookieConsent from "@/components/CookieConsent";

// Routes accessibles sans authentification.
// `/register/doctor` est public (entree de l'inscription), mais
// `/register/doctor/complete` exige une session Keycloak active : la matche
// exacte ci-dessous evite que startsWith() considere /complete comme public.
const PUBLIC_ROUTES_EXACT = ["/login", "/register/doctor"];
const PUBLIC_ROUTES_PREFIX = ["/privacy", "/about"];

/**
 * Layout racine. `<html>` et `<body>` doivent être ici (App Router).
 * `<SessionProvider>` est posé à l'intérieur de `<body>` pour exposer la
 * session NextAuth à tous les composants client.
 */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <head>
        <title>Mood-IoT — Suivi du bien-être</title>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta
          name="description"
          content="Plateforme française de suivi du bien-être. Tableau de bord médecin pour la téléconsultation et la prévention des rechutes dépressives."
        />
        <meta name="theme-color" content="#22c55e" />
        <meta name="application-name" content="Mood-IoT" />
        <link rel="icon" href="/favicon.ico" sizes="any" />
        <link rel="icon" href="/icon-192.png" type="image/png" sizes="192x192" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
        <link rel="manifest" href="/manifest.webmanifest" />
        {/* Open Graph (partage sur Slack / Discord / réseaux) */}
        <meta property="og:title" content="Mood-IoT — Tableau de bord médecin" />
        <meta
          property="og:description"
          content="Détection précoce des rechutes dépressives et téléconsultation sécurisée. Données chiffrées hébergées en France."
        />
        <meta property="og:type" content="website" />
        <meta property="og:image" content="/icon-512.png" />
      </head>
      <body>
        <SessionProvider>
          <ToastContainer position="top-right" autoClose={3000} hideProgressBar newestOnTop theme="light" />
          <CookieConsent />
          <RouteGate>{children}</RouteGate>
        </SessionProvider>
      </body>
    </html>
  );
}

/**
 * Decide entre :
 *  - page publique : juste rendre les children
 *  - page privee + non auth : redirige vers /login
 *  - page privee + auth : sidebar + main
 *  - en cours de chargement : spinner
 */
function RouteGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, user, loading } = useAuthStore();
  const setStoreItems = useNotifStore((s) => s.setItems);

  const isPublicPage =
    PUBLIC_ROUTES_EXACT.includes(pathname) ||
    PUBLIC_ROUTES_PREFIX.some(
      (route) => pathname === route || pathname.startsWith(route + "/"),
    );

  // Charge les notifications pour le badge sidebar quand connecte
  // ET seulement quand l'utilisateur a deja un profil cote backend
  useEffect(() => {
    if (!isAuthenticated || !user) return;
    getAllNotifications(50)
      .then((res) => {
        if (res.notifications) {
          setStoreItems(res.notifications);
        }
      })
      .catch(() => {
        // 404 = pas encore de profil, l'utilisateur doit completer son inscription
      });
  }, [isAuthenticated, user, setStoreItems]);

  // Redirige vers /login si page privee et non connecte
  useEffect(() => {
    if (loading) return;
    if (!isAuthenticated && !isPublicPage) {
      router.push("/login");
    }
  }, [loading, isAuthenticated, isPublicPage, router]);

  if (isPublicPage) {
    return <div className="min-h-screen bg-[#f4f6fb]">{children}</div>;
  }

  if (loading || !isAuthenticated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f4f6fb]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary-500 border-t-transparent" />
          <p className="text-[13px] text-gray-400">Chargement...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-[#f4f6fb]">
      <Sidebar />
      <main className="min-w-0 flex-1 overflow-y-auto overflow-x-hidden px-5 py-5">
        {children}
      </main>
    </div>
  );
}
