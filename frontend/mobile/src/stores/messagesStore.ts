/**
 * Store Zustand pour la messagerie médecin → patient.
 *
 * Conserve en mémoire la liste des messages reçus et le compteur de non lus
 * (utilisé par le badge du tab "Messages"). Le rafraîchissement est :
 *   - automatique au montage de l'app (cf. _layout des tabs)
 *   - périodique toutes les 60 secondes (poll léger)
 *   - manuel via `refreshMessages()` ou `markRead(id)`
 *
 * En Phase 2.3, on remplacera le polling par un push notification déclenché
 * côté backend à la création d'un message.
 */

import { create } from "zustand";
import {
  fetchMessages,
  fetchUnreadCount,
  markMessageRead,
  type MessageItem,
} from "@/services/api";

interface MessagesState {
  items: MessageItem[];
  unreadCount: number;
  loading: boolean;
  error: string | null;

  /** Recharge l'inbox complet (utilise par l'écran liste). */
  refreshMessages: (unreadOnly?: boolean) => Promise<void>;

  /** Recharge UNIQUEMENT le compteur (léger, pour le badge). */
  refreshUnreadCount: () => Promise<void>;

  /** Marque un message comme lu et met à jour l'état local. */
  markRead: (messageId: string) => Promise<void>;
}

export const useMessagesStore = create<MessagesState>((set, get) => ({
  items: [],
  unreadCount: 0,
  loading: false,
  error: null,

  refreshMessages: async (unreadOnly = false) => {
    set({ loading: true, error: null });
    try {
      const res = await fetchMessages({ unreadOnly });
      set({
        items: res.items,
        unreadCount: res.unread_count,
        loading: false,
      });
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Impossible de charger les messages";
      set({ loading: false, error: message });
    }
  },

  refreshUnreadCount: async () => {
    try {
      const res = await fetchUnreadCount();
      set({ unreadCount: res.unread_count });
    } catch {
      // Erreur silencieuse — le badge sera à jour au prochain refresh.
    }
  },

  markRead: async (messageId: string) => {
    try {
      const updated = await markMessageRead(messageId);
      set((state) => ({
        items: state.items.map((m) =>
          m.id === messageId ? { ...m, read_at: updated.read_at } : m,
        ),
        unreadCount: Math.max(0, state.unreadCount - 1),
      }));
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Erreur lors du marquage";
      set({ error: message });
    }
  },
}));
