/**
 * Écran "Humeur" — saisie simple par emoji.
 *
 * Le patient choisit un emoji (1-7), ajoute optionnellement une note courte,
 * et enregistre. Affiche en dessous l'historique récent.
 *
 * Phase 2.5 phase 2 (à venir) ajoutera la saisie vocale avec analyse IA.
 */

import { useEffect, useState, useCallback } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { format, isToday, isYesterday } from "date-fns";
import { fr } from "date-fns/locale";
import {
  deleteLatestHumeur,
  fetchHumeurHistory,
  submitHumeurEmoji,
  type HumeurEntry,
} from "@/services/api";

interface EmojiOption {
  level: number;
  emoji: string;
  label: string;
  color: string;
}

const EMOJIS: EmojiOption[] = [
  { level: 1, emoji: "😢", label: "Très mal",     color: "#c0392b" },
  { level: 2, emoji: "😟", label: "Mal",          color: "#e67e22" },
  { level: 3, emoji: "😕", label: "Pas terrible", color: "#f39c12" },
  { level: 4, emoji: "😐", label: "Neutre",       color: "#7f8c8d" },
  { level: 5, emoji: "🙂", label: "Bien",         color: "#27ae60" },
  { level: 6, emoji: "😊", label: "Très bien",    color: "#2ecc71" },
  { level: 7, emoji: "😄", label: "Excellent",    color: "#16a085" },
];

const NOTE_MAX = 280;

export default function MoodScreen() {
  const [selected, setSelected] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [history, setHistory] = useState<HumeurEntry[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const items = await fetchHumeurHistory(10);
      setHistory(items);
    } catch {
      /* ignore — l'historique n'est pas critique pour la saisie */
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const onSubmit = async () => {
    if (selected === null) {
      Alert.alert("Choix requis", "Veuillez sélectionner un emoji.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await submitHumeurEmoji(selected, note);
      setSelected(null);
      setNote("");
      await loadHistory();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Impossible d'enregistrer l'humeur",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const onDeleteLast = () => {
    Alert.alert(
      "Supprimer cette saisie ?",
      "Vous ne pouvez modifier que votre dernière saisie.",
      [
        { text: "Annuler", style: "cancel" },
        {
          text: "Supprimer",
          style: "destructive",
          onPress: async () => {
            try {
              await deleteLatestHumeur();
              await loadHistory();
            } catch {
              Alert.alert(
                "Erreur",
                "Suppression impossible. Réessayez plus tard.",
              );
            }
          },
        },
      ],
    );
  };

  return (
    <KeyboardAvoidingView
      style={styles.kav}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={
          <RefreshControl refreshing={loadingHistory} onRefresh={loadHistory} />
        }
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.question}>Comment vous sentez-vous ?</Text>
        <Text style={styles.help}>
          Choisissez l&apos;émoji qui correspond le mieux à votre humeur, là, maintenant.
        </Text>

        <View style={styles.emojiGrid}>
          {EMOJIS.map((opt) => {
            const isSelected = selected === opt.level;
            return (
              <Pressable
                key={opt.level}
                onPress={() => setSelected(opt.level)}
                style={({ pressed }) => [
                  styles.emojiCard,
                  isSelected && {
                    backgroundColor: opt.color + "15",
                    borderColor: opt.color,
                  },
                  pressed && { opacity: 0.7 },
                ]}
                accessibilityRole="radio"
                accessibilityState={{ selected: isSelected }}
                accessibilityLabel={`Humeur ${opt.label}`}
              >
                <Text style={styles.emojiBig}>{opt.emoji}</Text>
                <Text
                  style={[
                    styles.emojiLabel,
                    isSelected && { color: opt.color, fontWeight: "700" },
                  ]}
                >
                  {opt.label}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <Text style={styles.label}>Une note (facultatif)</Text>
        <TextInput
          style={styles.noteInput}
          value={note}
          onChangeText={(t) => t.length <= NOTE_MAX && setNote(t)}
          placeholder="Ce qui se passe, ce que vous ressentez…"
          placeholderTextColor="#aaa"
          multiline
          numberOfLines={3}
          accessibilityLabel="Note libre"
        />
        <Text style={styles.charCounter}>
          {note.length}/{NOTE_MAX}
        </Text>

        {error ? (
          <View style={styles.errorBox} accessibilityRole="alert">
            <Text style={styles.errorText}>{error}</Text>
          </View>
        ) : null}

        <Pressable
          style={({ pressed }) => [
            styles.submitBtn,
            (selected === null || submitting) && styles.submitBtnDisabled,
            pressed && selected !== null && styles.submitBtnPressed,
          ]}
          onPress={onSubmit}
          disabled={selected === null || submitting}
          accessibilityRole="button"
          accessibilityLabel="Enregistrer cette humeur"
        >
          {submitting ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.submitText}>Enregistrer</Text>
          )}
        </Pressable>

        <View style={styles.historyHeader}>
          <Text style={styles.historyTitle}>Mes dernières saisies</Text>
        </View>
        {history.length === 0 ? (
          <View style={styles.empty}>
            <Text style={styles.emptyEmoji}>🌱</Text>
            <Text style={styles.emptyText}>
              Vos saisies apparaîtront ici. Commencez quand vous voulez !
            </Text>
          </View>
        ) : (
          history.map((h, idx) => (
            <HumeurRow
              key={h.id}
              entry={h}
              isLatest={idx === 0}
              onDelete={onDeleteLast}
            />
          ))
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

interface HumeurRowProps {
  entry: HumeurEntry;
  isLatest: boolean;
  onDelete: () => void;
}

function HumeurRow({ entry, isLatest, onDelete }: HumeurRowProps) {
  const opt = EMOJIS.find((e) => e.level === entry.emoji_level);
  const date = new Date(entry.created_at);
  const dateLabel = isToday(date)
    ? `Aujourd'hui, ${format(date, "HH:mm")}`
    : isYesterday(date)
      ? `Hier, ${format(date, "HH:mm")}`
      : format(date, "EEEE d MMM 'à' HH:mm", { locale: fr });

  return (
    <View style={styles.historyRow}>
      <Text style={styles.historyEmoji}>{opt?.emoji ?? "❓"}</Text>
      <View style={styles.historyText}>
        <Text style={styles.historyLabel}>{opt?.label ?? "Saisie"}</Text>
        <Text style={styles.historyDate}>{dateLabel}</Text>
        {entry.note ? (
          <Text style={styles.historyNote} numberOfLines={2}>
            « {entry.note} »
          </Text>
        ) : null}
      </View>
      {isLatest ? (
        <Pressable
          onPress={onDelete}
          style={styles.deleteBtn}
          accessibilityRole="button"
          accessibilityLabel="Supprimer la dernière saisie"
          hitSlop={8}
        >
          <Text style={styles.deleteIcon}>🗑️</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  kav: { flex: 1, backgroundColor: "#f0f7ff" },
  scroll: { padding: 20, paddingBottom: 60 },

  question: { fontSize: 22, fontWeight: "700", color: "#222", marginBottom: 6 },
  help: { fontSize: 14, color: "#666", marginBottom: 20, lineHeight: 20 },

  emojiGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
    justifyContent: "center",
  },
  emojiCard: {
    width: "30%",
    minWidth: 100,
    backgroundColor: "#fff",
    borderRadius: 16,
    borderWidth: 2,
    borderColor: "#e5edf5",
    padding: 12,
    alignItems: "center",
  },
  emojiBig: { fontSize: 40, marginBottom: 6 },
  emojiLabel: {
    fontSize: 12,
    color: "#555",
    textAlign: "center",
    fontWeight: "500",
  },

  label: {
    fontSize: 14,
    fontWeight: "600",
    color: "#444",
    marginTop: 24,
    marginBottom: 8,
  },
  noteInput: {
    backgroundColor: "#fff",
    borderColor: "#e5edf5",
    borderWidth: 1,
    borderRadius: 12,
    padding: 14,
    fontSize: 15,
    minHeight: 90,
    textAlignVertical: "top",
    color: "#222",
  },
  charCounter: {
    fontSize: 11,
    color: "#999",
    textAlign: "right",
    marginTop: 4,
  },

  errorBox: {
    backgroundColor: "#fdecea",
    borderColor: "#f5b7b1",
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    marginTop: 12,
  },
  errorText: { color: "#c0392b", fontSize: 13 },

  submitBtn: {
    height: 52,
    backgroundColor: "#0288d1",
    borderRadius: 14,
    justifyContent: "center",
    alignItems: "center",
    marginTop: 20,
    shadowColor: "#0288d1",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 3,
  },
  submitBtnDisabled: { opacity: 0.5, shadowOpacity: 0 },
  submitBtnPressed: { opacity: 0.85 },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "700" },

  historyHeader: { marginTop: 32, marginBottom: 12 },
  historyTitle: { fontSize: 16, fontWeight: "700", color: "#333" },

  empty: { alignItems: "center", padding: 24 },
  emptyEmoji: { fontSize: 36, marginBottom: 8 },
  emptyText: {
    fontSize: 13,
    color: "#777",
    textAlign: "center",
    maxWidth: 280,
    lineHeight: 18,
  },

  historyRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 14,
    marginBottom: 10,
    gap: 14,
  },
  historyEmoji: { fontSize: 30 },
  historyText: { flex: 1, minWidth: 0 },
  historyLabel: { fontSize: 14, fontWeight: "600", color: "#333" },
  historyDate: { fontSize: 11, color: "#999", marginTop: 2 },
  historyNote: {
    fontSize: 12,
    color: "#666",
    marginTop: 6,
    fontStyle: "italic",
    lineHeight: 16,
  },
  deleteBtn: { padding: 6, borderRadius: 8 },
  deleteIcon: { fontSize: 18 },
});
