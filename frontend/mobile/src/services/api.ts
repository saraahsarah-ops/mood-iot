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
  risk_level: string;
  alert_level: number;
}

/** Le backend renvoie { patient_id, scores: [...], total } → on déballe scores. */
export async function getScoreHistory(
  patientId: string,
  fromDate?: string,
  toDate?: string,
): Promise<ScoreHistory[]> {
  const params = new URLSearchParams();
  if (fromDate) params.set("from_date", fromDate);
  if (toDate) params.set("to_date", toDate);
  const qs = params.toString();
  const res = await request<{ scores?: ScoreHistory[] }>(
    `/scoring/history/${patientId}${qs ? `?${qs}` : ""}`,
  );
  return res.scores ?? [];
}

/* ── Profil patient du user connecté (résout patient.id) ──────── */
export interface MyPatient {
  id: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  email?: string | null;
  phone?: string | null;
}

/** GET /patients/me — le client n'a que user.id ; ceci donne le patient.id. */
export async function getMyPatient(): Promise<MyPatient> {
  return request("/patients/me");
}

/* ── Health Data Sync ─────────────────────────── */

export interface HealthDataPayload {
  date: string;
  heart_rate_avg: number | null;
  heart_rate_variability: number | null;
  sleep_duration_min: number | null;
  step_count: number | null;
  screen_time_min: number | null;
  call_count: number | null;
  gps_radius_km: number | null;
  source_platform: "android_health_connect" | "ios_healthkit";
}

/**
 * Envoie 1 jour de données pour le patient connecté.
 * Endpoint `/me/` → pas d'IDOR : le backend résout le patient depuis le JWT.
 */
export async function syncHealthData(data: HealthDataPayload): Promise<void> {
  await request("/patients/me/health-data", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** Batch sync (max 90 jours) pour le patient connecté. */
export async function syncHealthDataBatch(
  data: HealthDataPayload[],
): Promise<void> {
  await request("/patients/me/health-data/batch", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export interface HealthSyncStatus {
  last_sync_at: string | null;
  last_date_synced: string | null;
  source_platform: string | null;
  days_synced_last_30: number;
}

export async function fetchHealthSyncStatus(): Promise<HealthSyncStatus> {
  return request<HealthSyncStatus>("/patients/me/health-data/status");
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

/* ── Consentements RGPD / CGU ──────────────────── */

export interface MyConsents {
  accepted_at: string | null;
  cgu: boolean;
  rgpd: boolean;
  health_sensors: boolean;
  ai_recommendations: boolean;
}

export async function fetchMyConsents(): Promise<MyConsents> {
  return request<MyConsents>("/patients/me/consents");
}

export async function updateMyConsents(
  consents: Omit<MyConsents, "accepted_at">,
): Promise<MyConsents> {
  return request<MyConsents>("/patients/me/consents", {
    method: "PUT",
    body: JSON.stringify(consents),
  });
}

/* ── Préférences notification ──────────────────── */

export interface NotificationPreferences {
  push_enabled: boolean;
  sms_enabled: boolean;
  email_enabled: boolean;
  rdv_reminder_24h: boolean;
  rdv_reminder_1h: boolean;
  rdv_reminder_now: boolean;
  push_token: string | null;
  phone_e164: string | null;
}

export async function fetchNotificationPreferences(): Promise<NotificationPreferences> {
  return request<NotificationPreferences>(
    "/patients/me/notification-preferences",
  );
}

export async function updateNotificationPreferences(
  patch: Partial<NotificationPreferences>,
): Promise<NotificationPreferences> {
  return request<NotificationPreferences>(
    "/patients/me/notification-preferences",
    {
      method: "PATCH",
      body: JSON.stringify(patch),
    },
  );
}

/* ── Humeur (emoji) ────────────────────────────── */

export interface HumeurEntry {
  id: string;
  source: "emoji" | "voix";
  emoji_level: number | null;
  note: string | null;
  created_at: string;
}

export async function submitHumeurEmoji(
  emojiLevel: number,
  note?: string,
): Promise<HumeurEntry> {
  return request<HumeurEntry>("/patients/me/humeur/emoji", {
    method: "POST",
    body: JSON.stringify({
      emoji_level: emojiLevel,
      note: note?.trim() || null,
    }),
  });
}

export async function fetchHumeurHistory(limit = 30): Promise<HumeurEntry[]> {
  return request<HumeurEntry[]>(`/patients/me/humeur?limit=${limit}`);
}

export async function patchLatestHumeur(
  emojiLevel: number,
  note?: string,
): Promise<HumeurEntry> {
  return request<HumeurEntry>("/patients/me/humeur/latest", {
    method: "PATCH",
    body: JSON.stringify({
      emoji_level: emojiLevel,
      note: note?.trim() || null,
    }),
  });
}

export async function deleteLatestHumeur(): Promise<void> {
  await request<void>("/patients/me/humeur/latest", { method: "DELETE" });
}

/* ── Messagerie médecin → patient ─────────────── */

export interface MessageItem {
  id: string;
  sender_id: string;
  sender_name: string;
  sender_role: "patient" | "psychiatre" | "admin";
  content: string;
  sent_at: string;
  read_at: string | null;
}

export interface MessageListResponse {
  items: MessageItem[];
  total: number;
  unread_count: number;
}

export async function fetchMessages(opts?: {
  unreadOnly?: boolean;
  limit?: number;
  offset?: number;
}): Promise<MessageListResponse> {
  const params = new URLSearchParams();
  if (opts?.unreadOnly) params.set("unread_only", "true");
  if (opts?.limit != null) params.set("limit", String(opts.limit));
  if (opts?.offset != null) params.set("offset", String(opts.offset));
  const qs = params.toString();
  return request<MessageListResponse>(
    `/patients/me/messages${qs ? `?${qs}` : ""}`,
  );
}

export async function fetchUnreadCount(): Promise<{ unread_count: number }> {
  return request<{ unread_count: number }>(
    "/patients/me/messages/unread-count",
  );
}

export async function fetchMessage(messageId: string): Promise<MessageItem> {
  return request<MessageItem>(`/patients/me/messages/${messageId}`);
}

export async function markMessageRead(messageId: string): Promise<MessageItem> {
  return request<MessageItem>(`/patients/me/messages/${messageId}/read`, {
    method: "PATCH",
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
