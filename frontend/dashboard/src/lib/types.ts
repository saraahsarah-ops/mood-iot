/* Types partagés — Dashboard Psychiatre Mood-IoT */

export interface Patient {
  id: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  baseline_status: string;
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
