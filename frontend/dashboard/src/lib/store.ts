"use client";
import { create } from "zustand";
import type { Notification, Message } from "./types";

/* ── Store notifications ──────────────────────────────── */
interface NotifStore {
  items: Notification[];
  setItems: (n: Notification[]) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
  unreadCount: () => number;
}

export const useNotifStore = create<NotifStore>((set, get) => ({
  items: [],
  setItems: (items) => set({ items }),
  markRead: (id) =>
    set({
      items: get().items.map((n) =>
        n.id === id ? { ...n, status: "read", read_at: new Date().toISOString() } : n,
      ),
    }),
  markAllRead: () =>
    set({
      items: get().items.map((n) => ({
        ...n,
        status: "read",
        read_at: new Date().toISOString(),
      })),
    }),
  unreadCount: () => get().items.filter((n) => n.status !== "read").length,
}));

/* ── Store messagerie ─────────────────────────────────── */
interface MessageStore {
  conversations: Record<string, Message[]>;
  addMessage: (patientId: string, msg: Message) => void;
}

export const useMessageStore = create<MessageStore>((set, get) => ({
  conversations: {},
  addMessage: (patientId, msg) =>
    set({
      conversations: {
        ...get().conversations,
        [patientId]: [...(get().conversations[patientId] || []), msg],
      },
    }),
}));
