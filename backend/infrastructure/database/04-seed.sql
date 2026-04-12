-- ============================================================================
-- Mood-IoT : Données de développement (seed)
-- ============================================================================

-- Médecin par défaut
INSERT INTO users (id, email, password_hash, role, mfa_enabled) VALUES
    ('a0000000-0000-0000-0000-000000000001', 'dr.martin@mood-iot.fr',
     -- password: MoodIoT2026! (bcrypt)
     '$2b$12$LJ3m8Cq5Q4Z9v5e6f7g8hOiJkLmNoPqRsTuVwXyZ0123456789ab',
     'psychiatre', false);

-- 4 patientes (profils du simulateur)
INSERT INTO users (id, email, password_hash, role) VALUES
    ('b0000000-0000-0000-0000-000000000001', 'sophie.dupont@email.fr',
     '$2b$12$LJ3m8Cq5Q4Z9v5e6f7g8hOiJkLmNoPqRsTuVwXyZ0123456789ab', 'patient'),
    ('b0000000-0000-0000-0000-000000000002', 'marie.laurent@email.fr',
     '$2b$12$LJ3m8Cq5Q4Z9v5e6f7g8hOiJkLmNoPqRsTuVwXyZ0123456789ab', 'patient'),
    ('b0000000-0000-0000-0000-000000000003', 'lea.moreau@email.fr',
     '$2b$12$LJ3m8Cq5Q4Z9v5e6f7g8hOiJkLmNoPqRsTuVwXyZ0123456789ab', 'patient'),
    ('b0000000-0000-0000-0000-000000000004', 'anna.bernard@email.fr',
     '$2b$12$LJ3m8Cq5Q4Z9v5e6f7g8hOiJkLmNoPqRsTuVwXyZ0123456789ab', 'patient');

INSERT INTO patients (id, user_id, first_name, last_name, date_of_birth, gender, diagnosis, treatment_start_date, baseline_status) VALUES
    ('c0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001',
     'Sophie', 'Dupont', '1995-03-15', 'F', 'Trouble dépressif majeur — insomnie', '2026-04-01', 'ready'),
    ('c0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000002',
     'Marie', 'Laurent', '1992-07-22', 'F', 'Épisode dépressif modéré — hypersomnie', '2026-04-01', 'ready'),
    ('c0000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000003',
     'Léa', 'Moreau', '1998-11-08', 'F', 'Trouble dépressif majeur — insomnie', '2026-04-01', 'ready'),
    ('c0000000-0000-0000-0000-000000000004', 'b0000000-0000-0000-0000-000000000004',
     'Anna', 'Bernard', '1990-01-30', 'F', 'Épisode dépressif modéré — hypersomnie', '2026-04-01', 'ready');

-- Assignation psychiatre → patientes
INSERT INTO patient_psychiatrist (patient_id, psychiatrist_id) VALUES
    ('c0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001'),
    ('c0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001'),
    ('c0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000001'),
    ('c0000000-0000-0000-0000-000000000004', 'a0000000-0000-0000-0000-000000000001');

-- Consentements RGPD
INSERT INTO consents (patient_id, consent_type, is_granted, granted_at) VALUES
    ('c0000000-0000-0000-0000-000000000001', 'data_collection', true, '2026-04-01'),
    ('c0000000-0000-0000-0000-000000000001', 'data_sharing', true, '2026-04-01'),
    ('c0000000-0000-0000-0000-000000000001', 'notifications', true, '2026-04-01'),
    ('c0000000-0000-0000-0000-000000000002', 'data_collection', true, '2026-04-01'),
    ('c0000000-0000-0000-0000-000000000002', 'data_sharing', true, '2026-04-01'),
    ('c0000000-0000-0000-0000-000000000002', 'notifications', true, '2026-04-01'),
    ('c0000000-0000-0000-0000-000000000003', 'data_collection', true, '2026-04-01'),
    ('c0000000-0000-0000-0000-000000000003', 'data_sharing', true, '2026-04-01'),
    ('c0000000-0000-0000-0000-000000000003', 'notifications', true, '2026-04-01'),
    ('c0000000-0000-0000-0000-000000000004', 'data_collection', true, '2026-04-01'),
    ('c0000000-0000-0000-0000-000000000004', 'data_sharing', true, '2026-04-01'),
    ('c0000000-0000-0000-0000-000000000004', 'notifications', true, '2026-04-01');

-- Seuils d'alerte par défaut (40/60/80)
INSERT INTO alert_thresholds (patient_id, metric_name, z_score_warning, z_score_alert, z_score_critical, set_by) VALUES
    ('c0000000-0000-0000-0000-000000000001', 'composite_risk', 2.0, 3.0, 4.0, 'a0000000-0000-0000-0000-000000000001'),
    ('c0000000-0000-0000-0000-000000000002', 'composite_risk', 2.0, 3.0, 4.0, 'a0000000-0000-0000-0000-000000000001'),
    ('c0000000-0000-0000-0000-000000000003', 'composite_risk', 2.0, 3.0, 4.0, 'a0000000-0000-0000-0000-000000000001'),
    ('c0000000-0000-0000-0000-000000000004', 'composite_risk', 2.0, 3.0, 4.0, 'a0000000-0000-0000-0000-000000000001');

-- Version initiale du modèle ML
INSERT INTO model_versions (version, algorithm, s3_artifact_path, training_samples, metrics_json, is_active, promoted_at) VALUES
    ('v1.0.0', 'XGBoost', 's3://mood-iot-models/v1.0.0/model.joblib', 0,
     '{"precision": 0.0, "recall": 0.0, "f1": 0.0, "auc": 0.0, "note": "placeholder — modèle initial"}',
     true, now());
