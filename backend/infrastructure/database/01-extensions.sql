-- ============================================================================
-- Mood-IoT : Extensions PostgreSQL 15
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";      -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";       -- recherche floue sur noms
