/* Client API — communique avec le backend FastAPI.
 *
 * Le token d'accès est récupéré depuis la session NextAuth (cookie HttpOnly)
 * via `getSession()`. Pas de localStorage : la session est gérée côté serveur
 * et NextAuth se charge du refresh transparent quand l'access_token expire.
 */

import { getSession } from "next-auth/react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010/api/v1";

async function fetcher<T>(path: string, options?: RequestInit): Promise<T> {
  // getSession() est sûr aussi bien côté client que pendant un SSR limité.
  // Si on n'a pas de session (ex. pages publiques), on appelle sans token.
  let token: string | null = null;
  try {
    const session = await getSession();
    token = session?.accessToken ?? null;
  } catch {
    token = null;
  }
  const res = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || body.message || detail;
    } catch { /* ignore parse error */ }
    throw new Error(detail);
  }
  return res.json();
}

/* ── Auth ─────────────────────────────────────────────── */

/**
 * Inscription d'un médecin : appelée APRÈS le login Keycloak depuis la
 * page /register/doctor/complete. Crée la ligne `users` + `doctor_profile`
 * avec statut "pending_approval" (un admin doit ensuite valider).
 */
export async function registerDoctorProfile(payload: {
  first_name: string;
  last_name: string;
  rpps_number: string;
  license_number: string;
  speciality: string;
}) {
  return fetcher<{ id: string; role: string; registration_status: string }>(
    "/auth/register-profile",
    {
      method: "POST",
      body: JSON.stringify({ role: "psychiatre", ...payload }),
    },
  );
}

/** Profil interne du médecin connecté. */
export async function getMyProfile() {
  return fetcher<{
    id: string;
    keycloak_id: string;
    email: string;
    role: string;
    first_name: string;
    last_name: string;
    registration_status: string;
  }>("/auth/me");
}

/* ── Patients ─────────────────────────────────────────── */
export async function getPatients(page = 1, pageSize = 50) {
  return fetcher<{ patients: any[]; total: number }>(
    `/patients?page=${page}&page_size=${pageSize}`,
  );
}

export async function getPatient(id: string) {
  return fetcher<any>(`/patients/${id}`);
}

export async function getPatientMetrics(patientId: string) {
  return fetcher<any>(`/patients/${patientId}/metrics`);
}

/* ── Scoring ──────────────────────────────────────────── */
export async function getLatestScore(patientId: string) {
  return fetcher<any>(`/scoring/latest/${patientId}`);
}

export async function getScoreHistory(
  patientId: string,
  limit = 30,
) {
  return fetcher<any>(`/scoring/history/${patientId}?limit=${limit}`);
}

export async function computeScore(patientId: string) {
  return fetcher<any>(`/scoring/compute/${patientId}`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function explainScore(scoreId: string) {
  return fetcher<any>(`/scoring/explain/${scoreId}`);
}

/* ── Notifications ────────────────────────────────────── */
export async function getAllNotifications(limit = 50) {
  return fetcher<any>(`/notifications/all?limit=${limit}`);
}

export async function getNotifications(
  patientId: string,
  unreadOnly = false,
) {
  return fetcher<any>(
    `/notifications/${patientId}?unread_only=${unreadOnly}`,
  );
}

export async function acknowledgeNotification(notifId: string) {
  return fetcher<any>(`/notifications/${notifId}/acknowledge`, {
    method: "PUT",
  });
}

export async function deleteNotification(notifId: string) {
  return fetcher<any>(`/notifications/${notifId}`, {
    method: "DELETE",
  });
}

/* ── Teleconsultation ────────────────────────────────── */
export async function getTeleconsultSessions(
  patientId?: string,
  dateFrom?: string,
  dateTo?: string,
) {
  const params = new URLSearchParams();
  if (patientId) params.set("patient_id", patientId);
  if (dateFrom) params.set("date_from", dateFrom);
  if (dateTo) params.set("date_to", dateTo);
  const query = params.toString() ? `?${params.toString()}` : "";
  return fetcher<{ sessions: any[]; total: number }>(
    `/teleconsult/sessions${query}`,
  );
}

export async function getTeleconsultSession(sessionId: string) {
  return fetcher<any>(`/teleconsult/sessions/${sessionId}`);
}

export async function createTeleconsultSession(data: {
  patient_id: string;
  psychiatre_id: string;
  scheduled_at: string;
  duration_minutes?: number;
  reason?: string;
}) {
  return fetcher<any>("/teleconsult/sessions", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function joinTeleconsultSession(sessionId: string) {
  return fetcher<any>(`/teleconsult/sessions/${sessionId}/join`, {
    method: "POST",
  });
}

export async function endTeleconsultSession(
  sessionId: string,
  summary?: string,
) {
  return fetcher<any>(`/teleconsult/sessions/${sessionId}/end`, {
    method: "PUT",
    body: JSON.stringify({ summary }),
  });
}

export async function deleteTeleconsultSession(sessionId: string) {
  return fetcher<any>(`/teleconsult/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

/* ── Session Notes ──────────────────────────────────── */
export async function getSessionNotes(sessionId: string) {
  return fetcher<any[]>(`/teleconsult/sessions/${sessionId}/notes`);
}

export async function addSessionNote(
  sessionId: string,
  data: { content: string; note_type?: string; is_private?: boolean },
) {
  return fetcher<any>(`/teleconsult/sessions/${sessionId}/notes`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/* ── Doctor / Institution ───────────────────────────── */
export async function registerDoctor(data: {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  rpps_number: string;
  license_number: string;
  speciality?: string;
  rgpd_consent: boolean;
  institution_name?: string;
}) {
  return fetcher<{ message: string }>("/doctor/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getDoctorProfile() {
  return fetcher<any>("/doctor/me");
}

export async function updateDoctorProfile(data: {
  first_name?: string;
  last_name?: string;
  speciality?: string;
}) {
  return fetcher<any>("/doctor/me", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function getPendingDoctors() {
  return fetcher<any[]>("/doctor/pending");
}

export async function approveDoctor(userId: string) {
  return fetcher<{ message: string }>(`/doctor/${userId}/approve`, {
    method: "PUT",
  });
}

export async function rejectDoctor(userId: string, reason: string) {
  return fetcher<{ message: string }>(`/doctor/${userId}/reject`, {
    method: "PUT",
    body: JSON.stringify({ reason }),
  });
}

export async function getInstitutionMembers() {
  return fetcher<any[]>("/doctor/institution/members");
}

export async function addInstitutionMember(data: {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  rpps_number: string;
  license_number: string;
  speciality?: string;
}) {
  return fetcher<{ message: string }>("/doctor/institution/members", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function removeInstitutionMember(userId: string) {
  return fetcher<{ message: string }>(
    `/doctor/institution/members/${userId}`,
    { method: "DELETE" },
  );
}

/* ── Patient CRUD ───────────────────────────────────── */
export async function createPatient(data: {
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  email?: string;
  phone?: string;
}) {
  return fetcher<any>("/patients", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updatePatient(
  patientId: string,
  data: { first_name?: string; last_name?: string; phone?: string },
) {
  return fetcher<any>(`/patients/${patientId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deletePatient(patientId: string) {
  return fetcher<{ message: string }>(`/patients/${patientId}`, {
    method: "DELETE",
  });
}

/* ── WebSocket alertes temps reel ─────────────────────── */
export function connectAlertWS(
  userId: string,
  onMessage: (data: any) => void,
): WebSocket {
  const wsUrl = API_URL.replace("http", "ws");
  const ws = new WebSocket(`${wsUrl}/notifications/ws/${userId}`);
  ws.onmessage = (event) => onMessage(JSON.parse(event.data));
  return ws;
}

/* ── Historique et Messagerie ─────────────────────────── */
export async function getPatientHistory(patientId: string) {
  return fetcher<any>(`/teleconsult/history/${patientId}`);
}

/**
 * Recommandations de coaching IA envoyées au patient (notifications de type
 * coaching_ia). Permet au médecin de voir les conseils que l'IA a donnés.
 */
export async function getPatientCoaching(patientId: string) {
  return fetcher<{
    notifications: Array<{
      id: string;
      title: string;
      body: string;
      created_at: string;
      status: string;
    }>;
    total: number;
    unread: number;
  }>(`/notifications/${patientId}?notification_type=coaching_ia`);
}

export async function sendDirectMessage(patientId: string, content: string) {
  return fetcher<any>(`/teleconsult/messages/${patientId}`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export async function generateAIAnalysis(patientId: string) {
  return fetcher<any>(`/notifications/ai-analysis/${patientId}`, {
    method: "POST"
  });
}
