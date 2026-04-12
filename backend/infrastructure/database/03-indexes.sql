-- ============================================================================
-- Mood-IoT : Index de performance
-- ============================================================================

-- Recherche rapide par user_id
CREATE INDEX idx_patients_user_id            ON patients(user_id);
CREATE INDEX idx_refresh_tokens_user_id      ON refresh_tokens(user_id);
CREATE INDEX idx_audit_log_user_id           ON audit_log(user_id);

-- Recherche par patient_id (requêtes les plus fréquentes)
CREATE INDEX idx_daily_aggregates_patient     ON daily_aggregates(patient_id, date DESC);
CREATE INDEX idx_risk_scores_patient          ON risk_scores(patient_id, date DESC);
CREATE INDEX idx_feature_vectors_patient      ON feature_vectors(patient_id, date DESC);
CREATE INDEX idx_baselines_patient            ON baselines(patient_id, metric_name);
CREATE INDEX idx_notifications_patient        ON notifications(patient_id, created_at DESC);
CREATE INDEX idx_mood_entries_patient         ON mood_entries(patient_id, submitted_at DESC);

-- Recherche par statut de notification (dashboard temps réel)
CREATE INDEX idx_notifications_status         ON notifications(status) WHERE status != 'read';
CREATE INDEX idx_notifications_recipient      ON notifications(recipient_user_id, status);

-- Teleconsultation par statut
CREATE INDEX idx_teleconsult_status           ON teleconsult_sessions(status)
                                              WHERE status IN ('scheduled', 'in_progress');

-- Assignment psychiatre-patient
CREATE INDEX idx_patient_psychiatrist_psych   ON patient_psychiatrist(psychiatrist_id);

-- Audit log par date
CREATE INDEX idx_audit_log_created            ON audit_log(created_at DESC);

-- Modèle actif
CREATE INDEX idx_model_versions_active        ON model_versions(is_active) WHERE is_active = true;
