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
        <body className="flex min-h-screen items-center justify-center">
          <p className="text-gray-400">Chargement...</p>
        </body>
      </html>
    );
  }

  // Authenticated — full layout
  return (
    <html lang="fr">
      <body className="flex min-h-screen">
        <Sidebar />
        <main className="flex-1 overflow-auto p-8">{children}</main>
      </body>
    </html>
  );
}
