-- ============================================================================
-- Mood-IoT : Extensions PostgreSQL 15
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";      -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";       -- recherche floue sur noms
-- ============================================================================
-- Mood-IoT : Schéma complet PostgreSQL 15
-- Conforme aux diagrammes : data_model, microservices_api, c4_container
-- ============================================================================

-- ──────────────────────────────────────────────────────────────────────────────
-- ZONE 1 — Utilisateurs & Authentification
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TYPE user_role AS ENUM ('patient', 'psychiatre', 'admin');

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            user_role NOT NULL,
    mfa_enabled     BOOLEAN DEFAULT false,
    mfa_secret      VARCHAR(255),
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE refresh_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,
    device_info     JSONB,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID REFERENCES users(id),
    action          VARCHAR(100) NOT NULL,
    resource        VARCHAR(100) NOT NULL,
    resource_id     UUID,
    ip_address      INET,
    details         JSONB,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ──────────────────────────────────────────────────────────────────────────────
-- ZONE 2 — Patients & Clinique
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TYPE gender_type     AS ENUM ('M', 'F', 'autre');
CREATE TYPE baseline_status AS ENUM ('pending', 'collecting', 'ready');
CREATE TYPE consent_type    AS ENUM ('data_collection', 'data_sharing', 'research', 'notifications');

CREATE TABLE patients (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    first_name              VARCHAR(100) NOT NULL,   -- chiffré AES-256 en application
    last_name               VARCHAR(100) NOT NULL,   -- chiffré AES-256 en application
    date_of_birth           DATE NOT NULL,
    gender                  gender_type NOT NULL,
    diagnosis               VARCHAR(255),
    treatment_start_date    DATE,
    emergency_contact_phone VARCHAR(20),              -- chiffré AES-256
    device_token_fcm        VARCHAR(500),
    smartwatch_model        VARCHAR(100),
    baseline_status         baseline_status DEFAULT 'pending',
    baseline_start_date     DATE,
    created_at              TIMESTAMPTZ DEFAULT now(),
    updated_at              TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE patient_psychiatrist (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    psychiatrist_id UUID NOT NULL REFERENCES users(id),
    is_primary      BOOLEAN DEFAULT true,
    assigned_at     TIMESTAMPTZ DEFAULT now(),
    UNIQUE (patient_id, psychiatrist_id)
);

CREATE TABLE consents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    consent_type    consent_type NOT NULL,
    is_granted      BOOLEAN NOT NULL,
    granted_at      TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ,
    ip_address      INET,
    UNIQUE (patient_id, consent_type)
);

CREATE TABLE mood_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    phq9_score      SMALLINT CHECK (phq9_score BETWEEN 0 AND 27),
    mood_rating     SMALLINT CHECK (mood_rating BETWEEN 1 AND 10),
    notes           TEXT,
    submitted_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE alert_thresholds (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id          UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    metric_name         VARCHAR(50) NOT NULL,
    z_score_warning     FLOAT DEFAULT 2.0,
    z_score_alert       FLOAT DEFAULT 3.0,
    z_score_critical    FLOAT DEFAULT 4.0,
    set_by              UUID REFERENCES users(id),
    updated_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE (patient_id, metric_name)
);

-- ──────────────────────────────────────────────────────────────────────────────
-- ZONE 3 — ML Scoring & Alertes
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE baselines (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id      UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    metric_name     VARCHAR(50) NOT NULL,
    mean_value      FLOAT NOT NULL,
    std_value       FLOAT NOT NULL,
    min_value       FLOAT,
    max_value       FLOAT,
    sample_count    INT NOT NULL,
    window_start    DATE NOT NULL,
    window_end      DATE NOT NULL,
    calculated_at   TIMESTAMPTZ DEFAULT now(),
    UNIQUE (patient_id, metric_name, window_end)
);

CREATE TABLE daily_aggregates (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id              UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    date                    DATE NOT NULL,
    heart_rate_avg          FLOAT,
    heart_rate_variability  FLOAT,
    sleep_duration_min      FLOAT,
    sleep_quality_score     FLOAT,
    step_count              INT,
    gps_radius_km           FLOAT,
    gps_locations_count     INT,
    screen_time_min         FLOAT,
    call_count              INT,
    call_duration_min       FLOAT,
    source_platform         VARCHAR(30),            -- 'android_health_connect' | 'ios_healthkit'
    synced_at               TIMESTAMPTZ,            -- quand l'appli mobile a envoye ces donnees
    created_at              TIMESTAMPTZ DEFAULT now(),
    UNIQUE (patient_id, date)
);

CREATE TABLE feature_vectors (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id          UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    date                DATE NOT NULL,
    z_heart_rate        FLOAT,
    z_hrv               FLOAT,
    z_sleep_duration    FLOAT,
    z_sleep_quality     FLOAT,
    z_step_count        FLOAT,
    z_gps_radius        FLOAT,
    z_screen_time       FLOAT,
    z_call_frequency    FLOAT,
    trend_7d            FLOAT,
    trend_14d           FLOAT,
    is_weekend          BOOLEAN NOT NULL,
    vector_json         JSONB NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE (patient_id, date)
);

CREATE TABLE model_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version             VARCHAR(50) UNIQUE NOT NULL,
    algorithm           VARCHAR(50) NOT NULL,
    s3_artifact_path    VARCHAR(500) NOT NULL,
    training_samples    INT NOT NULL,
    metrics_json        JSONB NOT NULL,
    is_active           BOOLEAN DEFAULT false,
    promoted_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE risk_scores (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id          UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    date                DATE NOT NULL,
    score               FLOAT NOT NULL CHECK (score BETWEEN 0 AND 100),
    alert_level         SMALLINT NOT NULL CHECK (alert_level BETWEEN 0 AND 3),
    model_version       VARCHAR(50) NOT NULL,
    feature_vector_id   UUID REFERENCES feature_vectors(id),
    shap_values         JSONB,
    confidence          FLOAT,
    created_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE (patient_id, date)
);

-- ──────────────────────────────────────────────────────────────────────────────
-- ZONE 4 — Notifications & Téléconsultation
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TYPE notif_type    AS ENUM ('coaching_ia', 'alerte_psychiatre', 'urgence', 'system');
CREATE TYPE notif_channel AS ENUM ('push_fcm', 'sms', 'email', 'websocket', 'call');
CREATE TYPE notif_status  AS ENUM ('pending', 'sent', 'delivered', 'read', 'failed');

CREATE TABLE notifications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id          UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    risk_score_id       UUID REFERENCES risk_scores(id),
    type                notif_type NOT NULL,
    level               SMALLINT NOT NULL CHECK (level BETWEEN 1 AND 3),
    channel             notif_channel NOT NULL,
    title               VARCHAR(255) NOT NULL,
    body                TEXT NOT NULL,
    recipient_user_id   UUID NOT NULL REFERENCES users(id),
    status              notif_status DEFAULT 'pending',
    sent_at             TIMESTAMPTZ,
    read_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE escalation_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id     UUID NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
    from_level          SMALLINT NOT NULL,
    to_level            SMALLINT NOT NULL,
    reason              TEXT NOT NULL,
    escalated_at        TIMESTAMPTZ DEFAULT now()
);

CREATE TYPE teleconsult_trigger AS ENUM ('scheduled', 'alert_level3', 'manual');
CREATE TYPE teleconsult_status  AS ENUM ('scheduled', 'in_progress', 'completed', 'cancelled', 'no_show');
CREATE TYPE alert_feedback_type AS ENUM ('confirmed_crisis', 'false_alarm', 'partially_relevant');

CREATE TABLE teleconsult_sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id          UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    psychiatrist_id     UUID NOT NULL REFERENCES users(id),
    trigger             teleconsult_trigger NOT NULL,
    risk_score_id       UUID REFERENCES risk_scores(id),
    jitsi_room_id       VARCHAR(255) NOT NULL,
    jitsi_jwt           TEXT,
    status              teleconsult_status DEFAULT 'scheduled',
    scheduled_at        TIMESTAMPTZ NOT NULL,
    started_at          TIMESTAMPTZ,
    ended_at            TIMESTAMPTZ,
    duration_min        INT,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE session_notes (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id              UUID NOT NULL REFERENCES teleconsult_sessions(id) ON DELETE CASCADE,
    psychiatrist_id         UUID NOT NULL REFERENCES users(id),
    content                 TEXT NOT NULL,   -- chiffré AES-256 en application
    alert_feedback          alert_feedback_type,
    treatment_adjustment    TEXT,
    created_at              TIMESTAMPTZ DEFAULT now()
);
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
-- ============================================================================
-- Mood-IoT : Données de développement (seed)
-- ============================================================================

-- Médecin par défaut
INSERT INTO users (id, email, password_hash, role, mfa_enabled) VALUES
    ('a0000000-0000-0000-0000-000000000001', 'dr.martin@mood-iot.fr',
     -- password: MoodIoT2026! (bcrypt)
     '$2b$12$rlUy7ToqKYbBg2p32VwfCeItT0Osyts6c69rZ8bXmLPpoU2Q3brIq',
     'psychiatre', false);

-- 4 patientes (profils du simulateur)
INSERT INTO users (id, email, password_hash, role) VALUES
    ('b0000000-0000-0000-0000-000000000001', 'sophie.dupont@email.fr',
     '$2b$12$rlUy7ToqKYbBg2p32VwfCeItT0Osyts6c69rZ8bXmLPpoU2Q3brIq', 'patient'),
    ('b0000000-0000-0000-0000-000000000002', 'marie.laurent@email.fr',
     '$2b$12$rlUy7ToqKYbBg2p32VwfCeItT0Osyts6c69rZ8bXmLPpoU2Q3brIq', 'patient'),
    ('b0000000-0000-0000-0000-000000000003', 'lea.moreau@email.fr',
     '$2b$12$rlUy7ToqKYbBg2p32VwfCeItT0Osyts6c69rZ8bXmLPpoU2Q3brIq', 'patient'),
    ('b0000000-0000-0000-0000-000000000004', 'anna.bernard@email.fr',
     '$2b$12$rlUy7ToqKYbBg2p32VwfCeItT0Osyts6c69rZ8bXmLPpoU2Q3brIq', 'patient');

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

-- ============================================================================
-- Données IoT de 14 jours pour les 4 patientes (baseline window)
-- ============================================================================
-- Sophie — profil à risque élevé (insomnie, sédentarité)
INSERT INTO daily_aggregates (id, patient_id, date, heart_rate_avg, heart_rate_variability, sleep_duration_min, sleep_quality_score, step_count, gps_radius_km, screen_time_min, call_count, call_duration_min, source_platform, synced_at) VALUES
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000001', '2026-03-19', 88, 28, 280, 4.2, 2100, 1.2, 420, 1, 3,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000001', '2026-03-20', 91, 25, 260, 3.8, 1800, 0.9, 450, 0, 0,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000001', '2026-03-21', 85, 30, 300, 4.5, 2500, 1.5, 390, 2, 5,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000001', '2026-03-22', 92, 24, 250, 3.5, 1600, 0.8, 480, 1, 2,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000001', '2026-03-23', 87, 29, 290, 4.0, 2200, 1.1, 410, 1, 4,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000001', '2026-03-24', 90, 26, 270, 3.9, 1900, 1.0, 440, 0, 0,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000001', '2026-03-25', 86, 31, 310, 4.6, 2800, 1.4, 380, 2, 6,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000001', '2026-03-26', 93, 23, 240, 3.3, 1500, 0.7, 500, 0, 0,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000001', '2026-03-27', 89, 27, 275, 4.1, 2300, 1.3, 430, 1, 3,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000001', '2026-03-28', 84, 32, 320, 4.8, 3000, 1.6, 360, 3, 8,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000001', '2026-03-29', 91, 25, 255, 3.7, 1700, 0.9, 460, 1, 2,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000001', '2026-03-30', 88, 28, 285, 4.3, 2400, 1.2, 400, 2, 5,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000001', '2026-03-31', 90, 26, 265, 3.6, 1800, 1.0, 445, 0, 0,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000001', '2026-04-01', 87, 29, 295, 4.4, 2600, 1.3, 405, 2, 6,  'android_health_connect', now());

-- Marie — profil modéré (hypersomnie, activité variable)
INSERT INTO daily_aggregates (id, patient_id, date, heart_rate_avg, heart_rate_variability, sleep_duration_min, sleep_quality_score, step_count, gps_radius_km, screen_time_min, call_count, call_duration_min, source_platform, synced_at) VALUES
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-19', 76, 38, 480, 6.5, 5200, 3.2, 280, 3, 12, 'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-20', 78, 36, 510, 6.8, 4800, 2.8, 300, 2, 8,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-21', 74, 40, 460, 6.2, 5500, 3.5, 260, 4, 15, 'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-22', 79, 35, 520, 7.0, 4500, 2.5, 310, 2, 7,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-23', 75, 39, 470, 6.3, 5100, 3.0, 275, 3, 10, 'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-24', 77, 37, 490, 6.6, 4900, 2.9, 290, 2, 9,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-25', 73, 41, 450, 6.0, 5800, 3.8, 250, 5, 18, 'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-26', 80, 34, 530, 7.2, 4200, 2.3, 320, 1, 5,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-27', 76, 38, 475, 6.4, 5300, 3.1, 285, 3, 11, 'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-28', 72, 42, 440, 5.8, 6000, 4.0, 240, 4, 16, 'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-29', 78, 36, 500, 6.7, 4700, 2.7, 295, 2, 8,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-30', 75, 39, 465, 6.1, 5400, 3.3, 270, 3, 13, 'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-31', 77, 37, 495, 6.5, 5000, 3.0, 288, 2, 9,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-04-01', 74, 40, 455, 6.0, 5600, 3.4, 265, 4, 14, 'android_health_connect', now());

-- Léa — profil stable/sain (bonne activité, bon sommeil)
INSERT INTO daily_aggregates (id, patient_id, date, heart_rate_avg, heart_rate_variability, sleep_duration_min, sleep_quality_score, step_count, gps_radius_km, screen_time_min, call_count, call_duration_min, source_platform, synced_at) VALUES
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-19', 65, 52, 450, 8.2, 8500, 5.2, 180, 5, 20, 'ios_healthkit', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-20', 67, 50, 440, 8.0, 8200, 4.8, 190, 4, 18, 'ios_healthkit', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-21', 64, 53, 460, 8.4, 8800, 5.5, 170, 6, 22, 'ios_healthkit', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-22', 66, 51, 445, 8.1, 8400, 5.0, 185, 5, 19, 'ios_healthkit', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-23', 63, 54, 455, 8.3, 8700, 5.3, 175, 6, 21, 'ios_healthkit', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-24', 68, 49, 435, 7.8, 7900, 4.5, 200, 4, 16, 'ios_healthkit', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-25', 64, 53, 465, 8.5, 9100, 5.7, 165, 7, 25, 'ios_healthkit', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-26', 66, 51, 448, 8.0, 8300, 5.1, 188, 5, 18, 'ios_healthkit', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-27', 65, 52, 452, 8.2, 8600, 5.4, 178, 5, 20, 'ios_healthkit', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-28', 63, 55, 470, 8.6, 9300, 5.8, 160, 7, 26, 'ios_healthkit', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-29', 67, 50, 442, 8.1, 8100, 4.9, 192, 4, 17, 'ios_healthkit', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-30', 65, 52, 455, 8.3, 8500, 5.2, 180, 5, 20, 'ios_healthkit', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-31', 66, 51, 447, 8.0, 8350, 5.0, 185, 5, 19, 'ios_healthkit', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-04-01', 64, 53, 458, 8.4, 8700, 5.4, 172, 6, 22, 'ios_healthkit', now());

-- Anna — profil modéré-élevé (sommeil perturbé, écran excessif)
INSERT INTO daily_aggregates (id, patient_id, date, heart_rate_avg, heart_rate_variability, sleep_duration_min, sleep_quality_score, step_count, gps_radius_km, screen_time_min, call_count, call_duration_min, source_platform, synced_at) VALUES
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-19', 82, 32, 340, 5.0, 3800, 2.0, 360, 2, 6,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-20', 85, 30, 320, 4.6, 3500, 1.8, 380, 1, 4,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-21', 80, 34, 360, 5.4, 4200, 2.3, 340, 3, 9,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-22', 84, 31, 325, 4.8, 3600, 1.9, 375, 1, 3,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-23', 81, 33, 350, 5.2, 4000, 2.1, 355, 2, 7,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-24', 86, 29, 310, 4.4, 3300, 1.7, 395, 1, 3,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-25', 79, 35, 370, 5.6, 4500, 2.5, 330, 3, 10, 'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-26', 87, 28, 300, 4.2, 3100, 1.5, 410, 0, 0,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-27', 83, 32, 345, 5.1, 3900, 2.0, 365, 2, 6,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-28', 78, 36, 380, 5.8, 4700, 2.6, 320, 4, 12, 'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-29', 85, 30, 315, 4.5, 3400, 1.8, 385, 1, 4,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-30', 82, 33, 355, 5.3, 4100, 2.2, 350, 2, 7,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-31', 84, 31, 330, 4.7, 3700, 1.9, 370, 1, 5,  'android_health_connect', now()),
    (gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-04-01', 80, 34, 365, 5.5, 4300, 2.4, 335, 3, 9,  'android_health_connect', now());
