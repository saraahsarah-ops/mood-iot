-- ============================================================================
-- Création du schéma Postgres dédié à Keycloak.
--
-- Keycloak (service `keycloak` dans docker-compose) partage l'instance
-- Postgres avec l'application mais utilise son propre schéma pour isoler
-- ses tables (KEYCLOAK_DB_SCHEMA=keycloak).
--
-- Ce script s'exécute en premier (préfixe 00-) lors de la création initiale
-- de la base de données par le conteneur postgres:15-alpine.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS keycloak;

COMMENT ON SCHEMA keycloak IS
    'Tables de Keycloak (identité, sessions, realms). Géré par le service keycloak.';
