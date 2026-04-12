import { useEffect } from "react";
import { View, Text, ScrollView, StyleSheet } from "react-native";
import { useHealthStore } from "@/stores/healthStore";

function getWellbeingLevel(score: number) {
  if (score >= 70) return { level: "Niveau 3", emoji: "🔴", color: "#e74c3c", label: "Consultez votre medecin" };
  if (score >= 40) return { level: "Niveau 2", emoji: "🟡", color: "#f39c12", label: "Restez vigilant(e)" };
  return { level: "Niveau 1", emoji: "🟢", color: "#2ecc71", label: "Tout va bien" };
}

export default function HistoryScreen() {
  const { history, fetchHistory } = useHealthStore();

  useEffect(() => {
    fetchHistory();
  }, []);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.header}>Mon historique</Text>
      <Text style={styles.subheader}>Evolution de votre bien-etre</Text>

      {history.length === 0 ? (
        <View style={styles.emptyBox}>
          <Text style={styles.emptyEmoji}>📊</Text>
          <Text style={styles.emptyText}>
            Pas encore de donnees. Vos resultats apparaitront ici apres quelques jours.
          </Text>
        </View>
      ) : (
        history.map((entry, i) => {
          const wb = getWellbeingLevel(entry.score);
          return (
            <View key={i} style={styles.card}>
              <View style={styles.cardHeader}>
                <Text style={styles.cardDate}>{entry.date}</Text>
                <View style={[styles.badge, { backgroundColor: wb.color + "20" }]}>
                  <Text style={{ color: wb.color, fontWeight: "600", fontSize: 12 }}>
                    {wb.emoji} {wb.level}
                  </Text>
                </View>
              </View>
              <Text style={styles.cardLabel}>{wb.label}</Text>
              <View style={styles.metricsRow}>
                <MiniMetric emoji="👟" value={`${entry.steps}`} />
                <MiniMetric emoji="😴" value={`${entry.sleep}h`} />
                <MiniMetric emoji="❤️" value={`${entry.heartRate}`} />
              </View>
            </View>
          );
        })
      )}
    </ScrollView>
  );
}

function MiniMetric({ emoji, value }: { emoji: string; value: string }) {
  return (
    <View style={styles.miniMetric}>
      <Text style={{ fontSize: 14 }}>{emoji}</Text>
      <Text style={styles.miniValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f0f7ff" },
  content: { padding: 20, paddingBottom: 40 },
  header: { fontSize: 22, fontWeight: "700", color: "#333" },
  subheader: { fontSize: 13, color: "#777", marginTop: 4, marginBottom: 20 },
  emptyBox: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 32,
    alignItems: "center",
  },
  emptyEmoji: { fontSize: 40, marginBottom: 12 },
  emptyText: { fontSize: 14, color: "#999", textAlign: "center", lineHeight: 22 },
  card: {
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 16,
    marginBottom: 10,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  cardDate: { fontSize: 14, fontWeight: "600", color: "#444" },
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 8 },
  cardLabel: { fontSize: 12, color: "#888", marginTop: 4 },
  metricsRow: { flexDirection: "row", gap: 16, marginTop: 10 },
  miniMetric: { flexDirection: "row", alignItems: "center", gap: 4 },
  miniValue: { fontSize: 13, color: "#555", fontWeight: "500" },
});
