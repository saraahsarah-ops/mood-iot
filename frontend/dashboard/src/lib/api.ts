/* Client API — communique avec le backend FastAPI */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010/api/v1";

async function fetcher<T>(path: string, options?: RequestInit): Promise<T> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("mood_token") : null;
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`);
  return res.json();
}

/* ── Auth ─────────────────────────────────────────────── */
export async function login(email: string, password: string) {
  return fetcher<{ access_token: string; user: { id: string; role: string } }>(
    "/auth/login",
    { method: "POST", body: JSON.stringify({ email, password }) },
  );
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
