-- ============================================================================
-- Migration 06 : Bascule vers Keycloak comme source de vérité d'identité
--
-- Effets :
--   1. Ajoute users.keycloak_user_id (UNIQUE, NULL-able pour migration douce)
--   2. Rend users.password_hash NULL-able (Keycloak gère désormais le mot de passe)
--   3. Conserve users.mfa_secret pour compatibilité (Keycloak gère le TOTP côté
--      auth.moodiot.fr). Les colonnes seront supprimées en feature/deploy une
--      fois tous les comptes migrés.
--   4. Conserve la table refresh_tokens vide — sera supprimée en Phase 2.8.
--
-- Idempotent : sûre à rejouer.
-- ============================================================================

BEGIN;

-- 1. Colonne keycloak_user_id ---------------------------------------------------
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS keycloak_user_id VARCHAR(255);

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_keycloak_user_id
    ON users (keycloak_user_id)
    WHERE keycloak_user_id IS NOT NULL;

COMMENT ON COLUMN users.keycloak_user_id IS
    'Identifiant utilisateur Keycloak (claim "sub"). Source de vérité après migration auth-keycloak.';

-- 2. password_hash devient optionnel -------------------------------------------
ALTER TABLE users
    ALTER COLUMN password_hash DROP NOT NULL;

COMMENT ON COLUMN users.password_hash IS
    'DEPRECATED — Keycloak gère désormais les mots de passe. Cette colonne sera supprimée en Phase 2.8.';

-- 3. Note sur mfa_secret/mfa_enabled --------------------------------------------
COMMENT ON COLUMN users.mfa_secret IS
    'DEPRECATED — MFA TOTP gérée par Keycloak. Sera supprimée en Phase 2.8.';

COMMENT ON COLUMN users.mfa_enabled IS
    'DEPRECATED — Lire le claim "mfa" du token Keycloak. Sera supprimée en Phase 2.8.';

COMMIT;
