/**
 * Écran "Messages" — inbox du patient.
 *
 * Liste les messages reçus du médecin, du plus récent au plus ancien. Click
 * sur un message → modal de détail + marquage automatique comme lu.
 *
 * Composants prévus pour Phase 2.7 (UX/UI) :
 *  - Pull-to-refresh
 *  - Skeleton loaders
 *  - États vides illustrés
 *  - Recherche par contenu
 */

import { useEffect, useState, useCallback } from "react";
import {
  FlatList,
  Modal,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
  ActivityIndicator,
} from "react-native";
import { formatDistanceToNow, format } from "date-fns";
import { fr } from "date-fns/locale";
import { useMessagesStore } from "@/stores/messagesStore";
import type { MessageItem } from "@/services/api";

export default function MessagesScreen() {
  const items = useMessagesStore((s) => s.items);
  const loading = useMessagesStore((s) => s.loading);
  const error = useMessagesStore((s) => s.error);
  const refresh = useMessagesStore((s) => s.refreshMessages);
  const markRead = useMessagesStore((s) => s.markRead);

  const [selected, setSelected] = useState<MessageItem | null>(null);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onPressItem = useCallback(
    (item: MessageItem) => {
      setSelected(item);
      if (item.read_at === null) {
        void markRead(item.id);
      }
    },
    [markRead],
  );

  return (
    <View style={styles.container}>
      {error ? (
        <View style={styles.errorBanner} accessibilityRole="alert">
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <FlatList
        data={items}
        keyExtractor={(m) => m.id}
        contentContainerStyle={items.length === 0 ? styles.emptyContainer : undefined}
        refreshControl={
          <RefreshControl
            refreshing={loading}
            onRefresh={() => void refresh()}
            tintColor="#0288d1"
          />
        }
        ListEmptyComponent={
          loading ? (
            <View style={styles.empty}>
              <ActivityIndicator color="#0288d1" />
            </View>
          ) : (
            <View style={styles.empty}>
              <Text style={styles.emptyEmoji}>📭</Text>
              <Text style={styles.emptyTitle}>Aucun message</Text>
              <Text style={styles.emptyText}>
                Vous n'avez encore reçu aucun message de votre médecin.
              </Text>
            </View>
          )
        }
        renderItem={({ item }) => (
          <MessageRow item={item} onPress={() => onPressItem(item)} />
        )}
      />

      {/* Modal de détail */}
      <Modal
        visible={selected !== null}
        animationType="slide"
        transparent
        onRequestClose={() => setSelected(null)}
      >
        <Pressable style={styles.backdrop} onPress={() => setSelected(null)}>
          <Pressable style={styles.modalCard} onPress={(e) => e.stopPropagation()}>
            {selected ? (
              <>
                <Text style={styles.modalSender}>
                  {selected.sender_role === "psychiatre" ? "Dr." : ""}{" "}
                  {selected.sender_name}
                </Text>
                <Text style={styles.modalDate}>
                  {format(new Date(selected.sent_at), "EEEE d MMMM yyyy 'à' HH:mm", {
                    locale: fr,
                  })}
                </Text>
                <Text style={styles.modalContent}>{selected.content}</Text>
                <Pressable
                  style={styles.modalClose}
                  onPress={() => setSelected(null)}
                  accessibilityRole="button"
                  accessibilityLabel="Fermer le message"
                >
                  <Text style={styles.modalCloseText}>Fermer</Text>
                </Pressable>
              </>
            ) : null}
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

interface MessageRowProps {
  item: MessageItem;
  onPress: () => void;
}

function MessageRow({ item, onPress }: MessageRowProps) {
  const isUnread = item.read_at === null;
  return (
    <Pressable
      style={({ pressed }) => [
        styles.row,
        isUnread && styles.rowUnread,
        pressed && styles.rowPressed,
      ]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`Message ${isUnread ? "non lu" : "lu"} de ${item.sender_name}`}
      accessibilityHint="Toucher pour ouvrir le détail"
    >
      <View style={styles.rowDot}>
        {isUnread ? <View style={styles.unreadDot} /> : null}
      </View>
      <View style={styles.rowContent}>
        <View style={styles.rowHeader}>
          <Text style={[styles.rowSender, isUnread && styles.rowSenderUnread]}>
            {item.sender_role === "psychiatre" ? "Dr." : ""} {item.sender_name}
          </Text>
          <Text style={styles.rowDate}>
            {formatDistanceToNow(new Date(item.sent_at), {
              addSuffix: true,
              locale: fr,
            })}
          </Text>
        </View>
        <Text
          style={[styles.rowPreview, isUnread && styles.rowPreviewUnread]}
          numberOfLines={2}
        >
          {item.content}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f4f6fb" },
  errorBanner: {
    backgroundColor: "#fdecea",
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#f5b7b1",
  },
  errorText: { color: "#c0392b", fontSize: 13 },
  emptyContainer: { flex: 1, justifyContent: "center" },
  empty: { alignItems: "center", padding: 40 },
  emptyEmoji: { fontSize: 48, marginBottom: 12 },
  emptyTitle: {
    fontSize: 17,
    fontWeight: "600",
    color: "#333",
    marginBottom: 6,
  },
  emptyText: {
    fontSize: 14,
    color: "#666",
    textAlign: "center",
    lineHeight: 20,
  },
  row: {
    flexDirection: "row",
    alignItems: "flex-start",
    backgroundColor: "#fff",
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderBottomWidth: 0.5,
    borderBottomColor: "#e5e7eb",
  },
  rowUnread: { backgroundColor: "#f0f7ff" },
  rowPressed: { opacity: 0.7 },
  rowDot: { width: 18, alignItems: "center", paddingTop: 6 },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#0288d1",
  },
  rowContent: { flex: 1, minWidth: 0 },
  rowHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginBottom: 4,
  },
  rowSender: { fontSize: 14, fontWeight: "500", color: "#444" },
  rowSenderUnread: { fontWeight: "700", color: "#222" },
  rowDate: { fontSize: 11, color: "#888" },
  rowPreview: { fontSize: 13, color: "#555", lineHeight: 19 },
  rowPreviewUnread: { color: "#333" },
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.45)",
    justifyContent: "flex-end",
  },
  modalCard: {
    backgroundColor: "#fff",
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 24,
    paddingBottom: 40,
  },
  modalSender: {
    fontSize: 18,
    fontWeight: "700",
    color: "#0288d1",
    marginBottom: 4,
  },
  modalDate: { fontSize: 12, color: "#888", marginBottom: 16 },
  modalContent: {
    fontSize: 16,
    color: "#333",
    lineHeight: 24,
    marginBottom: 20,
  },
  modalClose: {
    height: 44,
    borderRadius: 12,
    backgroundColor: "#0288d1",
    justifyContent: "center",
    alignItems: "center",
  },
  modalCloseText: { color: "#fff", fontSize: 15, fontWeight: "600" },
});
