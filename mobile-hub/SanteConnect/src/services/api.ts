/**
 * Service de communication avec le backend Mood-IoT.
 *
 * Flux : App mobile -> Patient Service (:8002) -> PostgreSQL (daily_aggregates)
 *
 * L'URL du backend est configurable via la variable API_BASE_URL.
 * En dev local : pointer vers l'IP de la machine qui fait tourner docker compose.
 * En prod      : pointer vers l'API Gateway (port 8010).
 */

// -------------------------------------------------------------------
// Configuration
// -------------------------------------------------------------------

// Changer cette IP par celle de la machine qui fait tourner le backend.
// Ex : "http://192.168.1.42:8010/api/v1"
const API_BASE_URL = __DEV__
  ? 'http://10.0.2.2:8010/api/v1'   // 10.0.2.2 = host machine depuis emulateur Android
  : 'https://api.mood-iot.fr/api/v1'; // prod (a configurer)

// -------------------------------------------------------------------
// Types
// -------------------------------------------------------------------

export interface HealthDataPayload {
  date: string;                    // "2026-04-12"
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
  source_platform: 'android_health_connect' | 'ios_healthkit';
}

interface LoginResponse {
  access_token: string;
  refresh_token?: string;
  user?: {
    id: string;
    email: string;
    role: string;
    first_name?: string;
    last_name?: string;
  };
}

// -------------------------------------------------------------------
// Stockage du token (simplifie — en prod, utiliser react-native-keychain)
// -------------------------------------------------------------------

let authToken: string | null = null;
let currentPatientId: string | null = null;

export const setAuthToken = (token: string) => {
  authToken = token;
};

export const setPatientId = (id: string) => {
  currentPatientId = id;
};

export const getPatientId = () => currentPatientId;
export const getAuthToken = () => authToken;
export const isAuthenticated = () => authToken !== null;

// -------------------------------------------------------------------
// Authentification
// -------------------------------------------------------------------

export async function login(email: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const status = res.status;
    if (status === 401) throw new Error('Identifiants invalides');
    throw new Error(`Erreur serveur (${status})`);
  }

  const data: LoginResponse = await res.json();
  authToken = data.access_token;

  // Si le user connecte est un patient, stocker son ID
  if (data.user?.role === 'patient') {
    currentPatientId = data.user.id;
  }

  return data;
}

export function logout() {
  authToken = null;
  currentPatientId = null;
}

// -------------------------------------------------------------------
// Envoi des donnees de sante
// -------------------------------------------------------------------

/**
 * Envoie les donnees d'une journee au backend.
 * POST /patients/{patient_id}/health-data
 *
 * Le backend fait un UPSERT sur (patient_id, date) :
 * si les donnees du jour existent deja, elles sont mises a jour.
 */
export async function syncHealthData(
  patientId: string,
  payload: HealthDataPayload,
): Promise<{ success: boolean; message: string }> {
  if (!authToken) {
    throw new Error('Non authentifie. Veuillez vous connecter.');
  }

  const res = await fetch(
    `${API_BASE_URL}/patients/${patientId}/health-data`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify(payload),
    },
  );

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Erreur sync (${res.status}): ${body}`);
  }

  return res.json();
}

/**
 * Envoie plusieurs jours de donnees d'un coup (rattrapage offline).
 * POST /patients/{patient_id}/health-data/batch
 */
export async function syncHealthDataBatch(
  patientId: string,
  payloads: HealthDataPayload[],
): Promise<{ success: boolean; synced: number }> {
  if (!authToken) {
    throw new Error('Non authentifie. Veuillez vous connecter.');
  }

  const res = await fetch(
    `${API_BASE_URL}/patients/${patientId}/health-data/batch`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify(payloads),
    },
  );

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Erreur batch sync (${res.status}): ${body}`);
  }

  return res.json();
}
