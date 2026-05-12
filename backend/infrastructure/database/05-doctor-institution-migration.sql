-- ============================================================================
-- Migration 05 : Médecins, Institutions & Statut d'inscription
-- Mood-IoT — PostgreSQL 15 / Supabase
-- Idempotent : utilise IF NOT EXISTS et DO $$ blocks
-- ============================================================================

-- ──────────────────────────────────────────────────────────────────────────────
-- 1. Type ENUM : statut d'inscription utilisateur
-- ──────────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'registration_status') THEN
        CREATE TYPE registration_status AS ENUM ('pending_approval', 'approved', 'rejected');
    END IF;
END
$$;

-- ──────────────────────────────────────────────────────────────────────────────
-- 2. Table institutions (créée AVANT l'ALTER sur users pour la FK)
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS institutions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    siret           VARCHAR(20) UNIQUE,
    address         TEXT,
    phone           VARCHAR(20),
    admin_user_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ──────────────────────────────────────────────────────────────────────────────
-- 3. ALTER TABLE users : ajout des colonnes manquantes
-- ──────────────────────────────────────────────────────────────────────────────

-- 3a. Colonne registration_status
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'registration_status'
    ) THEN
        ALTER TABLE users
            ADD COLUMN registration_status registration_status NOT NULL DEFAULT 'approved';
    END IF;
END
$$;

-- 3b. Colonne rgpd_consent_at (consentement RGPD)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'rgpd_consent_at'
    ) THEN
        ALTER TABLE users
            ADD COLUMN rgpd_consent_at TIMESTAMPTZ NULL;
    END IF;
END
$$;

-- 3c. Colonne institution_id (FK vers institutions)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'institution_id'
    ) THEN
        ALTER TABLE users
            ADD COLUMN institution_id UUID NULL REFERENCES institutions(id) ON DELETE SET NULL;
    END IF;
END
$$;

-- ──────────────────────────────────────────────────────────────────────────────
-- 4. Table doctor_profiles : profil médecin avec données chiffrées
-- ──────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS doctor_profiles (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                     UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    first_name                  VARCHAR(100) NOT NULL,
    last_name                   VARCHAR(100) NOT NULL,
    speciality                  VARCHAR(100) DEFAULT 'Psychiatrie',
    rpps_number_encrypted       VARCHAR(500),          -- numéro RPPS chiffré AES-256
    license_number_encrypted    VARCHAR(500),          -- numéro de licence chiffré AES-256
    certification_file_path     VARCHAR(500),          -- chemin vers le fichier de certification
    approval_note               TEXT,                  -- note de l'administrateur lors de la validation
    approved_by                 UUID REFERENCES users(id) ON DELETE SET NULL,
    approved_at                 TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ DEFAULT now(),
    updated_at                  TIMESTAMPTZ DEFAULT now()
);

-- ──────────────────────────────────────────────────────────────────────────────
-- 5. ALTER TABLE teleconsult_sessions : ajout du motif de consultation
-- ──────────────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'teleconsult_sessions' AND column_name = 'reason'
    ) THEN
        ALTER TABLE teleconsult_sessions
            ADD COLUMN reason VARCHAR(500);
    END IF;
END
$$;

-- ──────────────────────────────────────────────────────────────────────────────
-- 6. Index pour accélérer les requêtes fréquentes
-- ──────────────────────────────────────────────────────────────────────────────

-- Index sur l'administrateur de l'institution
CREATE INDEX IF NOT EXISTS idx_institutions_admin_user_id
    ON institutions(admin_user_id);

-- Index sur le user_id du profil médecin
CREATE INDEX IF NOT EXISTS idx_doctor_profiles_user_id
    ON doctor_profiles(user_id);

-- Index sur le statut d'inscription des utilisateurs
CREATE INDEX IF NOT EXISTS idx_users_registration_status
    ON users(registration_status);

-- ──────────────────────────────────────────────────────────────────────────────
-- 7. Données initiales : profil médecin pour dr.martin existant
-- ──────────────────────────────────────────────────────────────────────────────
INSERT INTO doctor_profiles (user_id, first_name, last_name, speciality)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'Dr. Martin',
    'Dupont',
    'Psychiatrie'
)
ON CONFLICT (user_id) DO NOTHING;
