import { create } from "zustand";
import * as api from "@/services/api";
import * as healthSync from "@/services/healthSync";
import { useAuthStore } from "./authStore";

interface Metrics {
  steps: number;
  sleep: number;
  heartRate: number;
  screenTime: number;
}

interface HistoryEntry {
  date: string;
  score: number;
  steps: number;
  sleep: number;
  heartRate: number;
}

interface HealthState {
  latestScore: number;
  coaching: string | null;
  metrics: Metrics;
  history: HistoryEntry[];

  /** Charge le dernier score + metriques du jour */
  fetchLatest: () => Promise<void>;

  /** Charge l'historique des 21 derniers jours */
  fetchHistory: () => Promise<void>;

  /** Sync les donnees de sante vers le backend */
  syncHealthData: () => Promise<void>;

  /** Envoie le PHQ-9 */
  submitPhq9: (answers: number[]) => Promise<void>;
}

function getPatientId(): string {
  return useAuthStore.getState().user?.id || "";
}

export const useHealthStore = create<HealthState>((set) => ({
  latestScore: 0,
  coaching: null,
  metrics: { steps: 0, sleep: 0, heartRate: 0, screenTime: 0 },
  history: [],

  fetchLatest: async () => {
    const pid = getPatientId();
    if (!pid) return;
    try {
      const data = await api.getLatestScore(pid);
      set({
        latestScore: data.score,
        coaching: data.coaching_message,
      });
    } catch (e) {
      console.warn("fetchLatest error:", e);
      // Fallback: lire les metriques du device
      try {
        const today = await healthSync.readDayMetrics(new Date());
        set({
          metrics: {
            steps: today.steps || 0,
            sleep: today.sleepMinutes ? Math.round(today.sleepMinutes / 60 * 10) / 10 : 0,
            heartRate: today.heartRateAvg || 0,
            screenTime: today.screenTimeMin ? Math.round(today.screenTimeMin / 60 * 10) / 10 : 0,
          },
        });
      } catch {}
    }
  },

  fetchHistory: async () => {
    const pid = getPatientId();
    if (!pid) return;
    try {
      const data = await api.getScoreHistory(pid);
      set({
        history: data.map((d) => ({
          date: new Date(d.date).toLocaleDateString("fr-FR", {
            day: "numeric",
            month: "short",
          }),
          score: d.score,
          steps: d.steps,
          sleep: d.sleep,
          heartRate: d.heartRate,
        })),
      });
    } catch (e) {
      console.warn("fetchHistory error:", e);
    }
  },

  syncHealthData: async () => {
    // Sync /me/ : pas besoin de patient_id côté client, le backend résout via JWT.
    // Filtre les jours sans aucune métrique non-nulle pour éviter de polluer la BDD.
    const payloads = (await healthSync.readLastNDays(7)).filter((p) =>
      p.step_count != null ||
      p.heart_rate_avg != null ||
      p.heart_rate_variability != null ||
      p.sleep_duration_min != null,
    );
    if (payloads.length === 0) {
      throw new Error(
        "Aucune donnée à synchroniser. Vérifiez vos autorisations Health Connect.",
      );
    }
    await api.syncHealthDataBatch(payloads);
    await healthSync.setLastSyncAt();
  },

  submitPhq9: async (answers) => {
    const pid = getPatientId();
    if (!pid) throw new Error("Not authenticated");
    await api.submitPhq9(pid, answers);
  },
}));
