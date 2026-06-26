-- Migration : ajoute les colonnes de contact aux psychiatres (users).
--
-- Contexte : l'escalade d'alerte niveau 2/3 (notification/escalation.py) lit
-- psychiatrist.phone et psychiatrist.device_token_fcm, mais le modèle User /
-- la table users ne les avaient pas -> AttributeError -> l'alerte au médecin
-- d'un patient critique plantait (ni SMS, ni FCM, ni email, ni notification
-- persistée). Ces colonnes corrigent ce défaut.
--
-- Idempotent (IF NOT EXISTS). À appliquer sur la base de prod :
--   docker exec mood-iot-postgres-1 psql -U mood_user -d mood_iot \
--     -f /chemin/add_user_contact_columns.sql

ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS device_token_fcm VARCHAR(500);
