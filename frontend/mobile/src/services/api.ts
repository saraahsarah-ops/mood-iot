import * as SecureStore from "expo-secure-store";

const API_BASE = process.env.EXPO_PUBLIC_API_URL || "http://localhost:8000";

async function getToken(): Promise<string | null> {
  return SecureStore.getItemAsync("auth_token");
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = await getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }

  return res.json();
}

/* ── Auth ──────────────────────────────────────── */

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    email: string;
    first_name: string;
    last_name: string;
    role: string;
  };
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
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

/* ── PHQ-9 ────────────────────────────────────── */

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

export async function getNotifications(patientId: string): Promise<PatientNotification[]> {
  return request(`/notifications/${patientId}?channel=push_fcm`);
}
