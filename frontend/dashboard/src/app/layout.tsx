"use client";
import "./globals.css";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Sidebar from "@/components/Sidebar";
import { useAuthStore } from "@/lib/auth";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, restore, user } = useAuthStore();
  const [ready, setReady] = useState(false);

  const isLoginPage = pathname === "/login";

  useEffect(() => {
    restore();
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (!isAuthenticated && !isLoginPage) {
      router.push("/login");
    }
  }, [ready, isAuthenticated, isLoginPage, router]);

  // Login page — no sidebar
  if (isLoginPage) {
    return (
      <html lang="fr">
        <body>{children}</body>
      </html>
    );
  }

  // Not ready or not authenticated — loading
  if (!ready || !isAuthenticated) {
    return (
      <html lang="fr">
        <body className="flex min-h-screen items-center justify-center bg-[#f4f6fb]">
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
        <Sidebar />
        <main className="min-w-0 flex-1 overflow-y-auto overflow-x-hidden px-5 py-5">{children}</main>
      </body>
    </html>
  );
}
