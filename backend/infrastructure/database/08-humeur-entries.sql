-- ============================================================================
-- Migration 08 : Table humeur_entries (Phase 2.5 — humeur emoji simple)
--
-- Séparée de mood_entries (PHQ-9 clinique). Cette table stocke les saisies
-- "humeur du jour" simples : 1 emoji + note optionnelle. La partie voix +
-- IA sera ajoutée plus tard (champs déjà prévus en nullable).
--
-- Échelle 1-7 :
--   1 = Très mal       😢
--   2 = Mal            😟
--   3 = Pas terrible   😕
--   4 = Neutre         😐
--   5 = Bien           🙂
--   6 = Très bien      😊
--   7 = Excellent      😄
--
-- Idempotent : sûre à rejouer.
-- ============================================================================

BEGIN;

CREATE TYPE humeur_source AS ENUM ('emoji', 'voix');

CREATE TABLE IF NOT EXISTS humeur_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL
        REFERENCES patients(id) ON DELETE CASCADE,
    source humeur_source NOT NULL DEFAULT 'emoji',
    emoji_level SMALLINT
        CHECK (emoji_level IS NULL OR (emoji_level >= 1 AND emoji_level <= 7)),
    note TEXT,
    -- Champs voix (Phase 2.5 phase 2 — voix + Whisper + Claude)
    audio_url TEXT,
    transcription TEXT,
    humeur_globale TEXT,         -- résumé qualitatif IA
    intensite SMALLINT
        CHECK (intensite IS NULL OR (intensite >= 1 AND intensite <= 10)),
    emotions_detectees JSONB,    -- liste d'émotions ["joie", "anxiété", ...]
    mots_cles JSONB,             -- mots-clés extraits ["travail", "famille"]
    resume TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE humeur_entries IS
    'Saisies d''humeur (Phase 2.5) — emoji simple + voix IA. '
    'Différent de mood_entries qui stocke le questionnaire clinique PHQ-9.';

CREATE INDEX IF NOT EXISTS idx_humeur_entries_patient_created
    ON humeur_entries (patient_id, created_at DESC);

COMMIT;
