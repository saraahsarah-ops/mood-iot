/* Types partagés — Dashboard Psychiatre Mood-IoT */

export interface Patient {
  id: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  email?: string;
  phone?: string;
  psychiatre_id?: string;
  baseline_status?: string;
  created_at: string;
  updated_at?: string;
}

/* ── Doctor / Institution ───────────────────────────── */

export interface DoctorProfile {
  id: string;
  user_id: string;
  email: string;
  first_name: string;
  last_name: string;
  speciality: string;
  rpps_number: string;
  license_number: string;
  registration_status: "pending_approval" | "approved" | "rejected";
  institution_id?: string;
  created_at: string;
}

export interface DoctorRegisterPayload {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  rpps_number: string;
  license_number: string;
  speciality?: string;
  rgpd_consent: boolean;
  institution_name?: string;
}

export interface PendingDoctor {
  user_id: string;
  email: string;
  first_name: string;
  last_name: string;
  speciality: string;
  rpps_number: string;
  license_number: string;
  registration_status: string;
  created_at: string;
}

/* ── Teleconsult ───────────────────────────────────── */

export interface TeleconsultSession {
  id: string;
  patient_id: string;
  psychiatre_id: string;
  status: "scheduled" | "in_progress" | "completed" | "cancelled";
  scheduled_at: string;
  duration_minutes: number;
  reason?: string;
  jitsi_room_name?: string;
  jitsi_url?: string;
  started_at?: string;
  ended_at?: string;
  created_at: string;
}

export interface SessionNote {
  id: string;
  session_id: string;
  author_id: string;
  content: string;
  note_type: string;
  is_private: boolean;
  created_at: string;
}

export interface RiskScore {
  score_id: string;
  patient_id: string;
  date: string;
  score: number;
  risk_level: string;
  alert_level: number;
  confidence: number | null;
  model_version: string;
  computed_at: string;
}

export interface Notification {
  id: string;
  patient_id: string;
  type: string;
  level: number;
  channel: string;
  title: string;
  body: string;
  recipient_user_id: string;
  status: string;
  sent_at: string | null;
  read_at: string | null;
  created_at: string;
}

export interface Message {
  id: string;
  role: "medecin" | "patiente";
  texte: string;
  heure: string;
}

export type RiskColor = "success" | "warning" | "danger";

export function getRiskColor(score: number): RiskColor {
  if (score < 40) return "success";
  if (score < 70) return "warning";
  return "danger";
}

export function getRiskLabel(score: number): string {
  if (score < 40) return "Stable";
  if (score < 70) return "À surveiller";
  return "Critique";
}

export function getRiskEmoji(score: number): string {
  if (score < 40) return "🟢";
  if (score < 70) return "🟡";
  return "🔴";
}
