/**
 * Service Health Connect (Android uniquement).
 * Librairie : react-native-health-connect v3.x
 */

import {
  initialize,
  requestPermission,
  readRecords,
  getSdkStatus,
  getGrantedPermissions,
  SdkAvailabilityStatus,
} from 'react-native-health-connect';
import { screenTime } from './screenTime';

// ────────────────────────────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────────────────────────────

export interface DailyMetrics {
  steps: number;
  sleepHours: number;
  heartRateBpm: number;
  screenTimeHours: number;
  screenTimePermission: boolean;
}

export interface WeeklyPoint {
  dayLabel: string;
  steps: number;
  sleepHours: number;
}

export type HealthConnectStatus = 'unavailable' | 'needs_install' | 'ready';

const REQUIRED_PERMISSIONS = [
  { accessType: 'read' as const, recordType: 'Steps' as const },
  { accessType: 'read' as const, recordType: 'SleepSession' as const },
  { accessType: 'read' as const, recordType: 'HeartRate' as const },
  { accessType: 'read' as const, recordType: 'TotalCaloriesBurned' as const },
];

// ────────────────────────────────────────────────────────────────────────────
// Helpers
// ────────────────────────────────────────────────────────────────────────────

/**
 * Minuit local d'un jour décalé de `daysOffset` par rapport à aujourd'hui.
 * setHours(0,0,0,0) opère dans le fuseau local du device → toISOString()
 * convertit ensuite en UTC, ce qui donne la bonne borne pour Health Connect.
 * Ex. Paris (+02:00) : minuit local = 2026-06-26T22:00:00.000Z ✓
 */
function localMidnight(daysOffset: number = 0): Date {
  const d = new Date();
  d.setDate(d.getDate() + daysOffset);
  d.setHours(0, 0, 0, 0);
  return d;
}

function todayRange() {
  const start = localMidnight(0);          // minuit ce matin (heure locale)
  const end   = new Date(localMidnight(1).getTime() - 1); // 23:59:59.999 ce soir
  return { startTime: start.toISOString(), endTime: end.toISOString() };
}

function dayRange(daysAgo: number) {
  const start = localMidnight(-daysAgo);
  const end   = new Date(localMidnight(-daysAgo + 1).getTime() - 1);
  return { startTime: start.toISOString(), endTime: end.toISOString() };
}

/**
 * Fenêtre sommeil unifiée pour un jour donné.
 * Couvre J-1 20h → J 14h pour capturer les couche-tard (après minuit)
 * tout en évitant de déborder sur la sieste de l'après-midi suivante.
 */
function sleepRangeForDay(dayStart: Date) {
  const start = new Date(dayStart);
  start.setDate(start.getDate() - 1);
  start.setHours(20, 0, 0, 0);
  const end = new Date(dayStart);
  end.setHours(14, 0, 0, 0);
  return { startTime: start.toISOString(), endTime: end.toISOString() };
}

function weekLabels(): string[] {
  const days = ['D', 'L', 'M', 'M', 'J', 'V', 'S'];
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() - (6 - i));
    return days[d.getDay()];
  });
}

function toMs(t: unknown): number {
  if (typeof t === 'string') return new Date(t).getTime();
  if (t && typeof (t as any).epochMilliseconds === 'number') return (t as any).epochMilliseconds;
  return 0;
}

// ────────────────────────────────────────────────────────────────────────────
// API publique
// ────────────────────────────────────────────────────────────────────────────

export async function checkHealthConnectStatus(): Promise<HealthConnectStatus> {
  const status = await getSdkStatus();
  if (status === SdkAvailabilityStatus.SDK_AVAILABLE) return 'ready';
  if (status === SdkAvailabilityStatus.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED) return 'needs_install';
  return 'unavailable';
}

export async function initHealthConnect(): Promise<boolean> {
  const available = await checkHealthConnectStatus();
  if (available !== 'ready') return false;
  await initialize();

  const already = await getGrantedPermissions();
  const alreadyGranted = new Set(already.map(p => `${p.accessType}:${p.recordType}`));
  const missing = REQUIRED_PERMISSIONS.filter(
    p => !alreadyGranted.has(`${p.accessType}:${p.recordType}`)
  );
  if (missing.length === 0) return true;

  const granted = await requestPermission(missing);
  return granted.length > 0;
}

export async function checkGrantedPermissions(): Promise<boolean> {
  try {
    await initialize();
    const granted = await getGrantedPermissions();
    const grantedSet = new Set(granted.map(p => `${p.accessType}:${p.recordType}`));
    return REQUIRED_PERMISSIONS.every(p => grantedSet.has(`${p.accessType}:${p.recordType}`));
  } catch { return false; }
}

export async function fetchDailyMetrics(): Promise<DailyMetrics> {
  const range = todayRange();

  // ── Pas ──────────────────────────────────────────────────────────────────
  const { records: stepsRecords } = await readRecords('Steps', {
    timeRangeFilter: { operator: 'between', ...range },
  });
  const steps = stepsRecords.reduce((sum, r) => sum + r.count, 0);

  // ── Sommeil : fenêtre unifiée J-1 20h → J 14h ───────────────────────────
  const todayStart = new Date();
  todayStart.setHours(0, 0, 0, 0);
  const sleepRange = sleepRangeForDay(todayStart);

  const { records: sleepRecords } = await readRecords('SleepSession', {
    timeRangeFilter: {
      operator: 'between',
      startTime: sleepRange.startTime,
      endTime: sleepRange.endTime,
    },
  });

  // On garde uniquement la session la plus récente
  const lastSleep = sleepRecords.length > 0
    ? sleepRecords.reduce((latest, r) =>
        toMs(r.endTime) > toMs(latest.endTime) ? r : latest
      )
    : null;
  const sleepMs = lastSleep
    ? toMs(lastSleep.endTime) - toMs(lastSleep.startTime)
    : 0;
  const sleepHours = Math.round((sleepMs / 3_600_000) * 10) / 10;

  // ── Fréquence cardiaque ───────────────────────────────────────────────────
  const { records: hrRecords } = await readRecords('HeartRate', {
    timeRangeFilter: { operator: 'between', ...range },
  });

  const allBpm = hrRecords
    .flatMap(r => (r.samples ?? []).map((s: any) => s.beatsPerMinute ?? s.bpm ?? 0))
    // Filtre les valeurs nulles ET les mesures aberrantes de capteur (< 30 ou > 250)
    .filter((v: number) => v >= 30 && v <= 250);

  const heartRateBpm = allBpm.length
    ? Math.round(allBpm.reduce((a: number, b: number) => a + b, 0) / allBpm.length)
    : 0;

  // ── Temps d'écran ────────────────────────────────────────────────────────
  const [screenTimeHours, screenTimePermission] = await Promise.all([
    screenTime.getDailyScreenTime().catch(() => -1),
    screenTime.hasPermission().catch(() => false),
  ]);

 // Juste après const range = todayRange();
console.log('RANGE steps/HR:', range);

// Juste après sleepRangeForDay
console.log('RANGE sleep:', sleepRange);

// Juste après readRecords SleepSession
console.log('SLEEP count:', sleepRecords.length);
console.log('SLEEP[0]:', JSON.stringify(sleepRecords[0], null, 2));

// Juste après readRecords HeartRate  
console.log('HR count:', hrRecords.length);
console.log('HR[0]:', JSON.stringify(hrRecords[0], null, 2));

  return { steps, sleepHours, heartRateBpm, screenTimeHours, screenTimePermission };
}

export async function fetchWeeklyData(): Promise<WeeklyPoint[]> {
  const labels = weekLabels();

  return Promise.all(
    Array.from({ length: 7 }, async (_, i): Promise<WeeklyPoint> => {
      const daysAgo = 6 - i;
      const range = dayRange(daysAgo);

      // Fenêtre sommeil unifiée : même helper que fetchDailyMetrics
      const dayStart = new Date(range.startTime);
      const sleepRange = sleepRangeForDay(dayStart);

      const [{ records: stepsRecords }, { records: sleepRecords }] = await Promise.all([
        readRecords('Steps', { timeRangeFilter: { operator: 'between', ...range } }),
        readRecords('SleepSession', {
          timeRangeFilter: {
            operator: 'between',
            startTime: sleepRange.startTime,
            endTime: sleepRange.endTime,
          },
        }),
      ]);

      const steps = stepsRecords.reduce((sum, r) => sum + r.count, 0);
      const sleepMs = sleepRecords.reduce((sum, r) =>
        sum + (toMs(r.endTime) - toMs(r.startTime)), 0);

      return {
        dayLabel: labels[i],
        steps,
        sleepHours: Math.round((sleepMs / 3_600_000) * 10) / 10,
      };
    }),
  );
}

export { screenTime };