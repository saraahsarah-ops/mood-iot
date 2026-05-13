"use client";
import "./globals.css";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import { useAuthStore } from "@/lib/auth";
import { useNotifStore } from "@/lib/store";
import { getAllNotifications } from "@/lib/api";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.min.css";
import CookieConsent from "@/components/CookieConsent";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, restore, user } = useAuthStore();
  const [ready, setReady] = useState(false);
  const setStoreItems = useNotifStore((s) => s.setItems);

  const PUBLIC_ROUTES = ["/login", "/register/doctor", "/privacy"];
  const isPublicPage = PUBLIC_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(route + "/"),
  );

  useEffect(() => {
    restore();
    setReady(true);
  }, []);

  /* Charger les notifications pour le badge sidebar */
  useEffect(() => {
    if (!isAuthenticated) return;
    getAllNotifications(50)
      .then((res) => {
        if (res.notifications) {
          setStoreItems(res.notifications);
        }
      })
      .catch(() => {});
  }, [isAuthenticated]);

  useEffect(() => {
    if (!ready) return;
    if (!isAuthenticated && !isPublicPage) {
      router.push("/login");
    }
  }, [ready, isAuthenticated, isPublicPage, router]);

  // Public pages — no sidebar
  if (isPublicPage) {
    return (
      <html lang="fr">
        <body>
          <ToastContainer position="top-right" autoClose={3000} hideProgressBar newestOnTop theme="light" />
          <CookieConsent />
          {children}
        </body>
      </html>
    );
  }

  // Not ready or not authenticated — loading
  if (!ready || !isAuthenticated) {
    return (
      <html lang="fr">
        <body className="flex min-h-screen items-center justify-center bg-[#f4f6fb]">
          <ToastContainer position="top-right" autoClose={3000} hideProgressBar newestOnTop theme="light" />
          <CookieConsent />
          <div className="flex flex-col items-center gap-3">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary-500 border-t-transparent" />
            <p className="text-[13px] text-gray-400">Chargement...</p>
          </div>
        </body>
      </html>
    );
  }

  // Authenticated — full layout
  return (
    <html lang="fr">
      <body className="flex min-h-screen bg-[#f4f6fb]">
        <ToastContainer position="top-right" autoClose={3000} hideProgressBar newestOnTop theme="light" />
        <CookieConsent />
        <Sidebar />
        <main className="min-w-0 flex-1 overflow-y-auto overflow-x-hidden px-5 py-5">{children}</main>
      </body>
    </html>
  );
}
