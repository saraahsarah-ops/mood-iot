/**
 * Client HTTP du backend Mood-IoT.
 *
 * - Récupère un access token Keycloak frais via authStore (refresh transparent)
 * - Injecte `Authorization: Bearer <token>` sur chaque requête authentifiée
 * - Sur 401 : tente un refresh + retry une fois, puis force la déconnexion
 */

import { useAuthStore } from "@/stores/authStore";
import type { AppUser } from "@/stores/authStore";

const API_BASE = process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000";

interface RequestOptions extends RequestInit {
  /** Désactive l'injection automatique du token (endpoints publics). */
  skipAuth?: boolean;
  /** Token explicite (utilisé par `fetchMe` pendant le bootstrap). */
  bearer?: string;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { skipAuth, bearer, ...init } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init.headers as Record<string, string>) ?? {}),
  };

  if (!skipAuth) {
    const token =
      bearer ?? (await useAuthStore.getState().getValidAccessToken());
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });

  if (res.status === 401 && !skipAuth && !bearer) {
    // Try one refresh + retry (the store will clear tokens if refresh fails)
    const fresh = await useAuthStore.getState().getValidAccessToken();
    if (fresh) {
      headers["Authorization"] = `Bearer ${fresh}`;
      const retry = await fetch(`${API_BASE}${path}`, { ...init, headers });
      return handleResponse<T>(retry);
    }
  }

  return handleResponse<T>(res);
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/* ── Auth ──────────────────────────────────────── */

/**
 * Profil interne (users + patient/doctor) déduit du token Keycloak.
 * Si 404 : l'utilisateur doit POST /auth/register-profile pour finaliser.
 */
export async function fetchMe(bearer?: string): Promise<AppUser> {
  return request<AppUser>("/auth/me", { bearer });
}

export interface RegisterProfilePayload {
  role: "patient" | "psychiatre";
  first_name: string;
  last_name: string;
  date_of_birth?: string; // ISO YYYY-MM-DD
  gender?: "M" | "F" | "autre";
  rpps_number?: string;
  license_number?: string;
  speciality?: string;
}

export async function registerProfile(
  payload: RegisterProfilePayload,
  bearer: string,
): Promise<AppUser> {
  return request<AppUser>("/auth/register-profile", {
    method: "POST",
    body: JSON.stringify(payload),
    bearer,
  });
}

/* ── Scoring ──────────────────────────────────── */

export interface LatestScore {
  score: number;
  alert_level: number;
  coaching_message: string | null;
  computed_at: string;
}

export async function getLatestScore(patientId: string): Promise<LatestScore> {
  return request(`/scoring/latest/${patientId}`);
}

export interface ScoreHistory {
  date: string;
  score: number;
  steps: number;
  sleep: number;
  heartRate: number;
}

export async function getScoreHistory(
  patientId: string,
  fromDate?: string,
  toDate?: string,
): Promise<ScoreHistory[]> {
  const params = new URLSearchParams();
  if (fromDate) params.set("from_date", fromDate);
  if (toDate) params.set("to_date", toDate);
  const qs = params.toString();
  return request(`/scoring/history/${patientId}${qs ? `?${qs}` : ""}`);
}

/* ── Health Data Sync ─────────────────────────── */

export interface HealthDataPayload {
  date: string;
  heart_rate_avg: number | null;
  heart_rate_variability: number | null;
  sleep_duration_min: number | null;
  steps: number | null;
  screen_time_min: number | null;
  call_count: number | null;
  gps_radius_km: number | null;
  source_platform: "android_health_connect" | "ios_healthkit";
}

export async function syncHealthData(
  patientId: string,
  data: HealthDataPayload,
): Promise<void> {
  await request(`/patients/${patientId}/health-data`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function syncHealthDataBatch(
  patientId: string,
  data: HealthDataPayload[],
): Promise<void> {
  await request(`/patients/${patientId}/health-data/batch`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/* ── PHQ-9 (questionnaire clinique — conservé tel quel) ──────────── */

export async function submitPhq9(
  patientId: string,
  answers: number[],
): Promise<void> {
  await request(`/patients/${patientId}/phq9`, {
    method: "POST",
    body: JSON.stringify({ answers, total: answers.reduce((a, b) => a + b, 0) }),
  });
}

/* ── Notifications ────────────────────────────── */

export interface PatientNotification {
  id: string;
  title: string;
  body: string;
  type: string;
  read_at: string | null;
  created_at: string;
}

export async function getNotifications(
  patientId: string,
): Promise<PatientNotification[]> {
  return request(`/notifications/${patientId}?channel=push_fcm`);
}
