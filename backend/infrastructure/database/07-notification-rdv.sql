-- ============================================================================
-- Migration 07 : Notifications RDV multicanal (Phase 2.3)
--
--   1. Ajoute la valeur `rdv_rappel` à l'enum notif_type pour les rappels RDV.
--   2. Crée la table `notification_preferences` (1:1 avec users) qui pilote
--      les canaux activés (push / sms / email) et les rappels RDV (J-1/H-1/H0).
--   3. Index dédié sur teleconsult_sessions(scheduled_at) pour les scans
--      périodiques du scheduler.
--
-- Idempotente : sûre à rejouer.
-- ============================================================================

BEGIN;

-- 1. Enum notif_type --------------------------------------------------------
DO $$ BEGIN
    ALTER TYPE notif_type ADD VALUE IF NOT EXISTS 'rdv_rappel';
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 2. notification_preferences -----------------------------------------------
CREATE TABLE IF NOT EXISTS notification_preferences (
    user_id UUID PRIMARY KEY
        REFERENCES users(id) ON DELETE CASCADE,
    push_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sms_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    email_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    -- Rappels RDV (timing). NULL ou FALSE = désactivé.
    rdv_reminder_24h BOOLEAN NOT NULL DEFAULT TRUE,
    rdv_reminder_1h BOOLEAN NOT NULL DEFAULT TRUE,
    rdv_reminder_now BOOLEAN NOT NULL DEFAULT TRUE,
    -- Token push (Expo / FCM) — chargé par l'app mobile à l'inscription
    push_token VARCHAR(255),
    -- N° de téléphone pour SMS (E.164, ex. +33612345678)
    phone_e164 VARCHAR(32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE notification_preferences IS
    'Préférences de notification par utilisateur (canaux + types de rappels RDV).';

-- 3. Index pour le scheduler ------------------------------------------------
-- Le scheduler scanne les RDV `scheduled` dans une fenêtre [now, now + 25h].
-- Index partiel pour éviter de scanner les sessions terminées/annulées.
CREATE INDEX IF NOT EXISTS idx_teleconsult_scheduled_upcoming
    ON teleconsult_sessions (scheduled_at)
    WHERE status = 'scheduled' AND scheduled_at IS NOT NULL;

-- 4. Table d'idempotence pour le scheduler ----------------------------------
-- Évite d'envoyer 2 fois le même rappel pour la même session.
CREATE TABLE IF NOT EXISTS rdv_reminder_log (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL
        REFERENCES teleconsult_sessions(id) ON DELETE CASCADE,
    reminder_kind VARCHAR(16) NOT NULL,  -- '24h' | '1h' | 'now'
    channel VARCHAR(16) NOT NULL,         -- 'push_fcm' | 'sms' | 'email'
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notification_id UUID
        REFERENCES notifications(id) ON DELETE SET NULL,
    UNIQUE (session_id, reminder_kind, channel)
);

COMMENT ON TABLE rdv_reminder_log IS
    'Trace les rappels RDV émis pour assurer l''idempotence du scheduler.';

CREATE INDEX IF NOT EXISTS idx_rdv_reminder_log_session
    ON rdv_reminder_log (session_id);

COMMIT;
