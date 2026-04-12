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
