"use client";
import { useNotifStore } from "@/lib/store";
import NotificationCard from "@/components/NotificationCard";
import { useEffect } from "react";
import type { Notification } from "@/lib/types";

const DEMO_NOTIFS: Notification[] = [
  {
    id: "1", patient_id: "1", type: "urgence", level: 3,
    channel: "push_fcm", title: "Alerte critique", recipient_user_id: "doc1",
    body: "Sophie L. — Score 82/100. Protocole d'urgence active.",
    status: "sent", sent_at: "2026-04-12T10:30:00Z", read_at: null,
    created_at: "2026-04-12T10:30:00Z",
  },
  {
    id: "2", patient_id: "4", type: "alerte_psychiatre", level: 2,
    channel: "websocket", title: "Score eleve", recipient_user_id: "doc1",
    body: "Anna K. — Score 68/100. Sommeil perturbe depuis 3 jours.",
    status: "sent", sent_at: "2026-04-12T09:15:00Z", read_at: null,
    created_at: "2026-04-12T09:15:00Z",
  },
];

export default function NotificationsPage() {
  const { items, setItems, markRead, markAllRead, unreadCount } = useNotifStore();

  useEffect(() => {
    if (items.length === 0) setItems(DEMO_NOTIFS);
  }, []);

  const unread = unreadCount();

  return (
    <div className="page-enter">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-gray-800">
            Notifications
          </h1>
          <p className="mt-1 text-[13px] text-gray-400">
            Alertes et mises a jour des patientes
          </p>
        </div>
        {unread > 0 && (
          <button
            onClick={markAllRead}
            className="flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-2 text-[13px] font-medium text-gray-600 shadow-card transition-all hover:border-success-400 hover:bg-success-50 hover:text-success-500"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
            Tout marquer comme lu
          </button>
        )}
      </div>

      {/* Stats bar */}
      <div className="mt-6 flex items-center gap-4">
        <div className="flex items-center gap-2 rounded-xl bg-white px-4 py-2 shadow-card">
          <span className="h-2 w-2 rounded-full bg-danger-500 animate-pulse-soft" />
          <span className="text-[13px] font-medium text-gray-600">{unread} non lue{unread > 1 ? "s" : ""}</span>
        </div>
        <div className="flex items-center gap-2 rounded-xl bg-white px-4 py-2 shadow-card">
          <span className="h-2 w-2 rounded-full bg-gray-300" />
          <span className="text-[13px] font-medium text-gray-600">{items.length - unread} lue{items.length - unread > 1 ? "s" : ""}</span>
        </div>
      </div>

      {items.length === 0 ? (
        <div className="mt-16 flex flex-col items-center justify-center text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gray-100">
            <svg className="h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
            </svg>
          </div>
          <p className="mt-4 text-[15px] font-semibold text-gray-500">
            Aucune notification
          </p>
          <p className="mt-1 text-[13px] text-gray-400">
            Tout est sous controle pour le moment.
          </p>
        </div>
      ) : (
        <div className="mt-4 space-y-2.5">
          {items.map((n) => (
            <NotificationCard
              key={n.id}
              patientName={n.title}
              score={n.level * 30}
              message={n.body}
              time={new Date(n.created_at).toLocaleString("fr-FR")}
              read={n.status === "read"}
              onMarkRead={() => markRead(n.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
