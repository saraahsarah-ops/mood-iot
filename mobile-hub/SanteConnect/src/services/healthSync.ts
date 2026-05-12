/**
 * Mood-IoT : Synchronisation des donnees de sante vers le backend.
 *
 * Collecte les metriques IoT locales (pas, BPM, sommeil, GPS)
 * et les envoie au backend pour le pipeline ML (daily_aggregates).
 */

import { authService } from './auth';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HealthPayload {
  heart_rate_avg: number | null;
  heart_rate_variability: number | null;
  sleep_duration_min: number | null;
  sleep_quality_score: number | null;
  step_count: number | null;
  gps_radius_km: number | null;
  gps_locations_count: number | null;
  screen_time_min: number | null;
  call_count: number | null;
  call_duration_min: number | null;
  recorded_at: string;
}

interface SyncResult {
  success: boolean;
  message: string;
}

// ---------------------------------------------------------------------------
// Sync function
// ---------------------------------------------------------------------------

/**
 * Envoie les donnees de sante collectees vers le backend.
 *
 * @param data - Metriques IoT du jour (partielles acceptees)
 * @returns Resultat de la synchronisation
 */
async function syncHealthData(data: Partial<HealthPayload>): Promise<SyncResult> {
  try {
    const payload: HealthPayload = {
      heart_rate_avg: data.heart_rate_avg ?? null,
      heart_rate_variability: data.heart_rate_variability ?? null,
      sleep_duration_min: data.sleep_duration_min ?? null,
      sleep_quality_score: data.sleep_quality_score ?? null,
      step_count: data.step_count ?? null,
      gps_radius_km: data.gps_radius_km ?? null,
      gps_locations_count: data.gps_locations_count ?? null,
      screen_time_min: data.screen_time_min ?? null,
      call_count: data.call_count ?? null,
      call_duration_min: data.call_duration_min ?? null,
      recorded_at: data.recorded_at ?? new Date().toISOString(),
    };

    const response = await authService.authFetch('/patients/me/health-data', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    if (response.ok) {
      return { success: true, message: 'Donnees synchronisees avec succes' };
    }

    const errorBody = await response.json().catch(() => ({}));
    const detail = errorBody.detail || `Erreur serveur (${response.status})`;
    return { success: false, message: detail };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur reseau';
    return { success: false, message };
  }
}

/**
 * Construit le payload de sante a partir des donnees collectees localement.
 */
function buildPayloadFromLocal(params: {
  steps: string;
  heartRate: string;
  sleepMinutes: number | null;
  latitude: number | null;
  longitude: number | null;
}): Partial<HealthPayload> {
  const stepsNum = parseInt(params.steps, 10);
  const hrNum = parseInt(params.heartRate, 10);

  return {
    step_count: isNaN(stepsNum) ? null : stepsNum,
    heart_rate_avg: isNaN(hrNum) ? null : hrNum,
    sleep_duration_min: params.sleepMinutes,
    gps_radius_km: params.latitude !== null ? 0.5 : null,
    gps_locations_count: params.latitude !== null ? 1 : null,
    recorded_at: new Date().toISOString(),
  };
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

export const healthSyncService = {
  syncHealthData,
  buildPayloadFromLocal,
};
