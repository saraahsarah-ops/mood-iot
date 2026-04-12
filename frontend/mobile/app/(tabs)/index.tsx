import { useEffect, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  RefreshControl,
} from "react-native";
import { useAuthStore } from "@/stores/authStore";
import { useHealthStore } from "@/stores/healthStore";
import WellbeingGauge from "@/components/WellbeingGauge";
import CoachingBanner from "@/components/CoachingBanner";
import MetricCard from "@/components/MetricCard";

export default function AccueilScreen() {
  const user = useAuthStore((s) => s.user);
  const { latestScore, metrics, coaching, fetchLatest } = useHealthStore();
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchLatest();
  }, []);

  async function onRefresh() {
    setRefreshing(true);
    await fetchLatest();
    setRefreshing(false);
  }

  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Bonjour" : hour < 18 ? "Bon apres-midi" : "Bonsoir";

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Saludo */}
      <Text style={styles.greeting}>
        {greeting}, {user?.first_name || "Patient"} 👋
      </Text>
      <Text style={styles.date}>
        {new Date().toLocaleDateString("fr-FR", {
          weekday: "long",
          day: "numeric",
          month: "long",
        })}
      </Text>

      {/* Gauge de bienestar */}
      <WellbeingGauge score={latestScore} />

      {/* Coaching IA */}
      {coaching ? <CoachingBanner message={coaching} /> : null}

      {/* Metricas del dia */}
      <Text style={styles.sectionTitle}>Mes donnees du jour</Text>
      <View style={styles.metricsGrid}>
        <MetricCard emoji="👟" label="Pas" value={metrics.steps} unit="pas" />
        <MetricCard emoji="😴" label="Sommeil" value={metrics.sleep} unit="h" />
        <MetricCard emoji="❤️" label="BPM moy." value={metrics.heartRate} unit="bpm" />
        <MetricCard emoji="📱" label="Ecran" value={metrics.screenTime} unit="h" />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f0f7ff" },
  content: { padding: 20, paddingBottom: 40 },
  greeting: { fontSize: 24, fontWeight: "700", color: "#333" },
  date: { fontSize: 14, color: "#888", marginTop: 4, marginBottom: 20 },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "600",
    color: "#555",
    marginTop: 24,
    marginBottom: 12,
  },
  metricsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
});
