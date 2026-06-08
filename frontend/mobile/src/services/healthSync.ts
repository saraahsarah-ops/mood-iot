/**
 * Service de synchronisation des données de santé.
 *
 * - Android : `react-native-health-connect` (Health Connect)
 * - iOS     : `react-native-health` (HealthKit) — STUB pour le moment,
 *             à activer dans une étape ultérieure (Mac + Xcode requis).
 *
 * Les permissions sont demandées au premier lancement via `requestPermissions()`.
 * L'état (granted / lastSync) est persisté dans expo-secure-store.
 */

import { Platform } from "react-native";
import { format, subDays } from "date-fns";
import * as SecureStore from "expo-secure-store";
import type { HealthDataPayload } from "./api";

// Clés SecureStore
const KEY_PERMISSIONS_GRANTED = "health_permissions_granted_v1";
const KEY_LAST_SYNC_AT = "health_last_sync_at_v1";

interface DayMetrics {
  date: string; // YYYY-MM-DD
  heartRateAvg: number | null;
  hrv: number | null;
  sleepMinutes: number | null;
  steps: number | null;
  screenTimeMin: number | null;
  bloodPressureSystolic: number | null;
  bloodPressureDiastolic: number | null;
  spo2: number | null;
}

/** Plateformes pour lesquelles la lecture des capteurs est implémentée. */
export type SupportedPlatform = "android" | "ios" | "unsupported";

export function getSupportedPlatform(): SupportedPlatform {
  if (Platform.OS === "android") return "android";
  if (Platform.OS === "ios") return "ios";
  return "unsupported";
}

/* ── Android : Health Connect ──────────────────────────────────────────── */

/**
 * Liste des record types requis. On lit `Steps`, `HeartRate`, `HRV` et
 * `SleepSession` partout, et `BloodPressure` + `OxygenSaturation` quand
 * l'utilisateur l'autorise (optionnels — pas tous les téléphones les ont).
 */
const ANDROID_PERMISSIONS = [
  { accessType: "read" as const, recordType: "Steps" },
  { accessType: "read" as const, recordType: "HeartRate" },
  { accessType: "read" as const, recordType: "HeartRateVariabilityRmssd" },
  { accessType: "read" as const, recordType: "SleepSession" },
  { accessType: "read" as const, recordType: "BloodPressure" },
  { accessType: "read" as const, recordType: "OxygenSaturation" },
];

async function getHC(): Promise<any | null> {
  if (Platform.OS !== "android") return null;
  try {
    return require("react-native-health-connect");
  } catch (e) {
    console.warn("[healthSync] Health Connect indisponible:", e);
    return null;
  }
}

async function readAndroidDay(date: Date): Promise<DayMetrics> {
  const dateStr = format(date, "yyyy-MM-dd");
  const startTime = new Date(date);
  startTime.setHours(0, 0, 0, 0);
  const endTime = new Date(date);
  endTime.setHours(23, 59, 59, 999);

  const timeRangeFilter = {
    operator: "between" as const,
    startTime: startTime.toISOString(),
    endTime: endTime.toISOString(),
  };

  const HC = await getHC();
  const empty: DayMetrics = {
    date: dateStr,
    heartRateAvg: null,
    hrv: null,
    sleepMinutes: null,
    steps: null,
    screenTimeMin: null,
    bloodPressureSystolic: null,
    bloodPressureDiastolic: null,
    spo2: null,
  };
  if (!HC) return empty;

  // Steps (cumul des records)
  let steps: number | null = null;
  try {
    const r = await HC.readRecords("Steps", { timeRangeFilter });
    steps =
      r.records?.reduce(
        (sum: number, rec: { count?: number }) => sum + (rec.count ?? 0),
        0,
      ) ?? null;
  } catch {
    // Permission non accordée pour Steps → on ignore
  }

  // Heart rate (moyenne des samples)
  let heartRateAvg: number | null = null;
  try {
    const r = await HC.readRecords("HeartRate", { timeRangeFilter });
    const samples: { beatsPerMinute: number }[] =
      r.records?.flatMap((rec: { samples?: { beatsPerMinute: number }[] }) =>
        rec.samples ?? [],
      ) ?? [];
    if (samples.length > 0) {
      heartRateAvg = Math.round(
        samples.reduce((s, x) => s + x.beatsPerMinute, 0) / samples.length,
      );
    }
  } catch {}

  // HRV (RMSSD)
  let hrv: number | null = null;
  try {
    const r = await HC.readRecords("HeartRateVariabilityRmssd", {
      timeRangeFilter,
    });
    const records: { heartRateVariabilityMillis: number }[] = r.records ?? [];
    if (records.length > 0) {
      hrv = Math.round(
        records.reduce((s, x) => s + x.heartRateVariabilityMillis, 0) /
          records.length,
      );
    }
  } catch {}

  // Sleep (somme des durées de session)
  let sleepMinutes: number | null = null;
  try {
    const r = await HC.readRecords("SleepSession", { timeRangeFilter });
    const total =
      r.records?.reduce(
        (sum: number, sess: { startTime: string; endTime: string }) => {
          const start = new Date(sess.startTime).getTime();
          const end = new Date(sess.endTime).getTime();
          return sum + (end - start) / 60000;
        },
        0,
      ) ?? 0;
    sleepMinutes = total > 0 ? Math.round(total) : null;
  } catch {}

  // Blood pressure (dernière mesure du jour)
  let bloodPressureSystolic: number | null = null;
  let bloodPressureDiastolic: number | null = null;
  try {
    const r = await HC.readRecords("BloodPressure", { timeRangeFilter });
    const records = r.records ?? [];
    if (records.length > 0) {
      const last = records[records.length - 1];
      bloodPressureSystolic = Math.round(last.systolic?.inMillimetersOfMercury ?? 0) || null;
      bloodPressureDiastolic = Math.round(last.diastolic?.inMillimetersOfMercury ?? 0) || null;
    }
  } catch {}

  // SpO2 (moyenne du jour)
  let spo2: number | null = null;
  try {
    const r = await HC.readRecords("OxygenSaturation", { timeRangeFilter });
    const records: { percentage: number }[] = r.records ?? [];
    if (records.length > 0) {
      spo2 = Math.round(
        records.reduce((s, x) => s + (x.percentage ?? 0), 0) / records.length,
      );
    }
  } catch {}

  return {
    date: dateStr,
    heartRateAvg,
    hrv,
    sleepMinutes,
    steps,
    screenTimeMin: null,
    bloodPressureSystolic,
    bloodPressureDiastolic,
    spo2,
  };
}

/* ── iOS : HealthKit (stub documenté) ──────────────────────────────────── */

/**
 * Stub iOS — délibérément non implémenté pour le moment.
 *
 * Pour activer HealthKit :
 *   1. `npm i react-native-health`
 *   2. Configurer `app.json` (NSHealthShareUsageDescription en FR)
 *   3. EAS build iOS avec entitlement `com.apple.developer.healthkit`
 *   4. Remplacer ce stub par les appels `AppleHealthKit.getDailyStepCountSamples`
 *
 * Voir AUDIT.md (Phase 2.4) pour les détails de l'activation.
 */
async function readIOSDay(date: Date): Promise<DayMetrics> {
  return {
    date: format(date, "yyyy-MM-dd"),
    heartRateAvg: null,
    hrv: null,
    sleepMinutes: null,
    steps: null,
    screenTimeMin: null,
    bloodPressureSystolic: null,
    bloodPressureDiastolic: null,
    spo2: null,
  };
}

/* ── Public API ────────────────────────────────────────────────────────── */

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
    bloodPressureSystolic: null,
    bloodPressureDiastolic: null,
    spo2: null,
  };
}

/**
 * Convertit un `DayMetrics` en payload backend.
 *
 * NB : backend attend `step_count` (pas `steps`). Les métriques BP/SpO2 sont
 * volontairement omises ici tant que le modèle backend ne les expose pas —
 * elles sont lues côté mobile mais on ne les transmet pas encore.
 */
export function toPayload(day: DayMetrics): HealthDataPayload {
  return {
    date: day.date,
    heart_rate_avg: day.heartRateAvg,
    heart_rate_variability: day.hrv,
    sleep_duration_min: day.sleepMinutes,
    step_count: day.steps,
    screen_time_min: day.screenTimeMin,
    call_count: null,
    gps_radius_km: null,
    source_platform:
      Platform.OS === "ios" ? "ios_healthkit" : "android_health_connect",
  };
}

/** Lit les N derniers jours et renvoie les payloads à envoyer. */
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

/* ── Permissions ───────────────────────────────────────────────────────── */

export interface PermissionsState {
  granted: boolean;
  /** True ssi l'utilisateur a déjà passé l'écran de permissions au moins une fois. */
  hasAsked: boolean;
}

export async function getPermissionsState(): Promise<PermissionsState> {
  try {
    const raw = await SecureStore.getItemAsync(KEY_PERMISSIONS_GRANTED);
    if (raw === null) return { granted: false, hasAsked: false };
    return { granted: raw === "true", hasAsked: true };
  } catch {
    return { granted: false, hasAsked: false };
  }
}

/**
 * Demande les permissions Health Connect (Android) ou HealthKit (iOS — stub).
 * Persiste le résultat dans SecureStore.
 */
export async function requestPermissions(): Promise<boolean> {
  let granted = false;

  if (Platform.OS === "android") {
    const HC = await getHC();
    if (HC) {
      try {
        await HC.initialize();
        const result = await HC.requestPermission(ANDROID_PERMISSIONS);
        granted = Array.isArray(result) && result.length > 0;
      } catch (e) {
        console.warn("[healthSync] requestPermission error:", e);
        granted = false;
      }
    }
  } else if (Platform.OS === "ios") {
    // Stub : on marque comme "demandé" mais non accordé jusqu'à activation
    // de react-native-health. Voir bloc "iOS stub" plus haut.
    granted = false;
  }

  try {
    await SecureStore.setItemAsync(
      KEY_PERMISSIONS_GRANTED,
      granted ? "true" : "false",
    );
  } catch {}
  return granted;
}

/** Marque l'écran de permission comme "vu" sans accorder. Utile si l'user refuse. */
export async function markPermissionsAsked(): Promise<void> {
  try {
    await SecureStore.setItemAsync(KEY_PERMISSIONS_GRANTED, "false");
  } catch {}
}

/* ── Dernière sync ─────────────────────────────────────────────────────── */

export async function getLastSyncAt(): Promise<Date | null> {
  try {
    const raw = await SecureStore.getItemAsync(KEY_LAST_SYNC_AT);
    if (!raw) return null;
    const d = new Date(raw);
    return isNaN(d.getTime()) ? null : d;
  } catch {
    return null;
  }
}

export async function setLastSyncAt(at: Date = new Date()): Promise<void> {
  try {
    await SecureStore.setItemAsync(KEY_LAST_SYNC_AT, at.toISOString());
  } catch {}
}
