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
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-800">🔔 Notifications</h1>
        {unread > 0 && (
          <button
            onClick={markAllRead}
            className="rounded-lg bg-success px-4 py-2 text-sm text-white hover:opacity-90"
          >
            ✅ Tout marquer comme lu
          </button>
        )}
      </div>

      {items.length === 0 ? (
        <p className="mt-8 text-center text-gray-400">
          ✅ Aucune notification pour le moment.
        </p>
      ) : (
        <div className="mt-6 space-y-3">
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
