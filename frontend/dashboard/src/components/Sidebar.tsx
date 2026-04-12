"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useNotifStore } from "@/lib/store";

const NAV_ITEMS = [
  { href: "/", label: "Vue generale", emoji: "🏠" },
  { href: "/patient", label: "Fiche patiente", emoji: "👤" },
  { href: "/notifications", label: "Notifications", emoji: "🔔" },
  { href: "/messagerie", label: "Messagerie", emoji: "💬" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const unread = useNotifStore((s) => s.unreadCount());

  return (
    <aside className="flex h-screen w-64 flex-col bg-gradient-to-b from-primary-dark to-primary text-white">
      {/* Logo */}
      <div className="flex items-center gap-3 border-b border-white/20 px-6 py-5">
        <span className="text-2xl">🏥</span>
        <div>
          <h1 className="text-lg font-bold">Mood-IoT</h1>
          <p className="text-xs text-blue-200">Dashboard Medecin</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="mt-4 flex-1 space-y-1 px-3">
        {NAV_ITEMS.map(({ href, label, emoji }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 rounded-lg px-4 py-3 text-sm font-medium transition ${
                active
                  ? "bg-white/20 text-white"
                  : "text-blue-100 hover:bg-white/10 hover:text-white"
              }`}
            >
              <span>{emoji}</span>
              <span>{label}</span>
              {href === "/notifications" && unread > 0 && (
                <span className="ml-auto rounded-full bg-danger px-2 py-0.5 text-xs font-bold">
                  {unread}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-white/20 px-6 py-4">
        <p className="text-xs text-blue-200">Dr. Martin</p>
        <p className="text-xs text-blue-300">Psychiatre</p>
      </div>
    </aside>
  );
}
