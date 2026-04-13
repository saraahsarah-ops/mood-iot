"use client";
import { useState, useEffect } from "react";
import NotificationCard from "@/components/NotificationCard";
import { getAllNotifications, acknowledgeNotification, deleteNotification } from "@/lib/api";
import { useNotifStore } from "@/lib/store";

import type { Notification as NotifData } from "@/lib/types";

export default function NotificationsPage() {
  const [items, setItems] = useState<NotifData[]>([]);
  const [loading, setLoading] = useState(true);
  const setStoreItems = useNotifStore((s) => s.setItems);

  /* Synchroniser le store global pour le badge sidebar */
  const syncStore = (list: NotifData[]) => setStoreItems(list);

  useEffect(() => {
    async function load() {
      try {
        const res = await getAllNotifications(50);
        const notifs = res.notifications || [];
        setItems(notifs);
        syncStore(notifs);
      } catch (err) {
        console.error("Erreur chargement notifications:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const markRead = async (id: string) => {
    try {
      await acknowledgeNotification(id);
      const updated = items.map((n) =>
        n.id === id ? { ...n, status: "read" } : n
      );
      setItems(updated);
      syncStore(updated);
    } catch (err) {
      console.error("Erreur acknowledge:", err);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteNotification(id);
      const updated = items.filter((n) => n.id !== id);
      setItems(updated);
      syncStore(updated);
    } catch (err) {
      console.error("Erreur suppression:", err);
    }
  };

  /* Extraire le score reel depuis le body ("Score de risque XX/100") */
  const extractScore = (body: string): number => {
    const m = body.match(/Score\s+(?:de\s+risque\s+)?(\d+(?:\.\d+)?)\s*\/\s*100/i);
    return m ? Math.round(parseFloat(m[1])) : 0;
  };

  const unreadCount = items.filter((n) => n.status !== "read").length;

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary-500 border-t-transparent" />
          <p className="text-[13px] text-gray-400">Chargement...</p>
        </div>
      </div>
    );
  }

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
      </div>

      {/* Stats bar */}
      <div className="mt-6 flex items-center gap-4">
        <div className="flex items-center gap-2 rounded-xl bg-white px-4 py-2 shadow-card">
          <span className="h-2 w-2 rounded-full bg-danger-500 animate-pulse-soft" />
          <span className="text-[13px] font-medium text-gray-600">
            {unreadCount} non lue{unreadCount > 1 ? "s" : ""}
          </span>
        </div>
        <div className="flex items-center gap-2 rounded-xl bg-white px-4 py-2 shadow-card">
          <span className="h-2 w-2 rounded-full bg-gray-300" />
          <span className="text-[13px] font-medium text-gray-600">
            {items.length - unreadCount} lue{items.length - unreadCount > 1 ? "s" : ""}
          </span>
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
              score={extractScore(n.body)}
              level={n.level}
              message={n.body}
              time={new Date(n.created_at).toLocaleString("fr-FR")}
              read={n.status === "read"}
              onMarkRead={() => markRead(n.id)}
              onDelete={() => handleDelete(n.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
