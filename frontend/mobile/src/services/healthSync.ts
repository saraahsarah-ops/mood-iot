import { Platform } from "react-native";
import { format, subDays } from "date-fns";
import type { HealthDataPayload } from "./api";

/* ────────────────────────────────────────────────
 *  Health Connect (Android) — react-native-health-connect
 *  HealthKit (iOS) — react-native-health (futur)
 *
 *  Ce service abstrait la lecture des donnees de sante
 *  quel que soit le systeme d'exploitation.
 * ──────────────────────────────────────────────── */

interface DayMetrics {
  date: string; // YYYY-MM-DD
  heartRateAvg: number | null;
  hrv: number | null;
  sleepMinutes: number | null;
  steps: number | null;
  screenTimeMin: number | null;
}

/* ── Android: Health Connect ─────────────────── */

async function readAndroidDay(date: Date): Promise<DayMetrics> {
  const dateStr = format(date, "yyyy-MM-dd");
  const startTime = new Date(date);
  startTime.setHours(0, 0, 0, 0);
  const endTime = new Date(date);
  endTime.setHours(23, 59, 59, 999);

  const timeRange = {
    operator: "between" as const,
    startTime: startTime.toISOString(),
    endTime: endTime.toISOString(),
  };

  try {
    const HC = require("react-native-health-connect");

    // Steps
    let steps: number | null = null;
    try {
      const stepsData = await HC.readRecords("Steps", { timeRangeFilter: timeRange });
      steps = stepsData.records?.reduce(
        (sum: number, r: any) => sum + (r.count || 0),
        0,
      ) ?? null;
    } catch {}

    // Heart rate
    let heartRateAvg: number | null = null;
    try {
      const hrData = await HC.readRecords("HeartRate", { timeRangeFilter: timeRange });
      const samples = hrData.records?.flatMap((r: any) => r.samples || []) ?? [];
      if (samples.length > 0) {
        heartRateAvg = Math.round(
          samples.reduce((s: number, sample: any) => s + sample.beatsPerMinute, 0) /
            samples.length,
        );
      }
    } catch {}

    // HRV
    let hrv: number | null = null;
    try {
      const hrvData = await HC.readRecords("HeartRateVariabilityRmssd", {
        timeRangeFilter: timeRange,
      });
      const records = hrvData.records ?? [];
      if (records.length > 0) {
        hrv = Math.round(
          records.reduce((s: number, r: any) => s + r.heartRateVariabilityMillis, 0) /
            records.length,
        );
      }
    } catch {}

    // Sleep
    let sleepMinutes: number | null = null;
    try {
      const sleepData = await HC.readRecords("SleepSession", {
        timeRangeFilter: timeRange,
      });
      sleepMinutes = sleepData.records?.reduce((total: number, session: any) => {
        const start = new Date(session.startTime).getTime();
        const end = new Date(session.endTime).getTime();
        return total + (end - start) / 60000;
      }, 0) ?? null;
    } catch {}

    return { date: dateStr, heartRateAvg, hrv, sleepMinutes, steps, screenTimeMin: null };
  } catch (e) {
    console.warn("Health Connect read error:", e);
    return { date: dateStr, heartRateAvg: null, hrv: null, sleepMinutes: null, steps: null, screenTimeMin: null };
  }
}

/* ── iOS: HealthKit (placeholder) ────────────── */

async function readIOSDay(date: Date): Promise<DayMetrics> {
  const dateStr = format(date, "yyyy-MM-dd");
  // TODO: implementer avec react-native-health (HealthKit)
  // import AppleHealthKit from "react-native-health";
  console.warn("HealthKit not yet implemented — returning null metrics");
  return {
    date: dateStr,
    heartRateAvg: null,
    hrv: null,
    sleepMinutes: null,
    steps: null,
    screenTimeMin: null,
  };
}

/* ── Public API ──────────────────────────────── */

export async function readDayMetrics(date: Date): Promise<DayMetrics> {
  if (Platform.OS === "android") return readAndroidDay(date);
  if (Platform.OS === "ios") return readIOSDay(date);
  // Web/dev fallback
  return {
    date: format(date, "yyyy-MM-dd"),
    heartRateAvg: null,
    hrv: null,
    sleepMinutes: null,
    steps: null,
    screenTimeMin: null,
  };
}

export function toPayload(
  day: DayMetrics,
): HealthDataPayload {
  return {
    date: day.date,
    heart_rate_avg: day.heartRateAvg,
    heart_rate_variability: day.hrv,
    sleep_duration_min: day.sleepMinutes,
    steps: day.steps,
    screen_time_min: day.screenTimeMin,
    call_count: null,
    gps_radius_km: null,
    source_platform:
      Platform.OS === "ios" ? "ios_healthkit" : "android_health_connect",
  };
}

/**
 * Lit les N derniers jours et renvoie les payloads prets a envoyer au backend.
 */
export async function readLastNDays(n: number = 7): Promise<HealthDataPayload[]> {
  const today = new Date();
  const results: HealthDataPayload[] = [];

  for (let i = 0; i < n; i++) {
    const date = subDays(today, i);
    const day = await readDayMetrics(date);
    results.push(toPayload(day));
  }

  return results;
}

/**
 * Initialise les permissions Health Connect (Android).
 * Doit etre appele au demarrage de l'app.
 */
export async function requestPermissions(): Promise<boolean> {
  if (Platform.OS === "android") {
    try {
      const HC = require("react-native-health-connect");
      await HC.initialize();
      const granted = await HC.requestPermission([
        { accessType: "read", recordType: "Steps" },
        { accessType: "read", recordType: "HeartRate" },
        { accessType: "read", recordType: "HeartRateVariabilityRmssd" },
        { accessType: "read", recordType: "SleepSession" },
      ]);
      return granted.length > 0;
    } catch (e) {
      console.warn("Health Connect permission error:", e);
      return false;
    }
  }
  // iOS: TODO
  return false;
}
