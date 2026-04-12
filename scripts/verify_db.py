"""
Mood-IoT : Script de vérification de la base de données.
Usage : python scripts/verify_db.py

Vérifie que toutes les tables, types et index ont été créés correctement
après un `docker compose up`.
"""

import psycopg2
import sys

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "mood_iot",
    "user": "mood_user",
    "password": "mood_secret_2026",
}

EXPECTED_TABLES = [
    "users",
    "refresh_tokens",
    "audit_log",
    "patients",
    "patient_psychiatrist",
    "consents",
    "mood_entries",
    "alert_thresholds",
    "baselines",
    "daily_aggregates",
    "feature_vectors",
    "model_versions",
    "risk_scores",
    "notifications",
    "escalation_log",
    "teleconsult_sessions",
    "session_notes",
]

EXPECTED_TYPES = [
    "user_role",
    "gender_type",
    "baseline_status",
    "consent_type",
    "notif_type",
    "notif_channel",
    "notif_status",
    "teleconsult_trigger",
    "teleconsult_status",
    "alert_feedback_type",
]


def main():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        print("✅ Connexion PostgreSQL OK\n")

        # ── Vérifier les tables ────────────────────────────────────────────
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        existing_tables = {row[0] for row in cur.fetchall()}

        print(f"{'TABLE':<30} {'STATUT'}")
        print("-" * 42)
        ok = True
        for table in EXPECTED_TABLES:
            found = table in existing_tables
            status = "✅" if found else "❌ MANQUANTE"
            print(f"  {table:<28} {status}")
            if not found:
                ok = False

        # ── Vérifier les types ENUM ────────────────────────────────────────
        cur.execute("""
            SELECT typname FROM pg_type
            WHERE typcategory = 'E' ORDER BY typname;
        """)
        existing_types = {row[0] for row in cur.fetchall()}

        print(f"\n{'TYPE ENUM':<30} {'STATUT'}")
        print("-" * 42)
        for t in EXPECTED_TYPES:
            found = t in existing_types
            status = "✅" if found else "❌ MANQUANT"
            print(f"  {t:<28} {status}")
            if not found:
                ok = False

        # ── Vérifier les données seed ──────────────────────────────────────
        print("\n── Données seed ──")
        cur.execute("SELECT COUNT(*) FROM users;")
        nb_users = cur.fetchone()[0]
        print(f"  users          : {nb_users} (attendu: 5)")

        cur.execute("SELECT COUNT(*) FROM patients;")
        nb_patients = cur.fetchone()[0]
        print(f"  patients       : {nb_patients} (attendu: 4)")

        cur.execute("SELECT COUNT(*) FROM consents;")
        nb_consents = cur.fetchone()[0]
        print(f"  consents       : {nb_consents} (attendu: 12)")

        cur.execute("SELECT COUNT(*) FROM alert_thresholds;")
        nb_thresholds = cur.fetchone()[0]
        print(f"  alert_thresholds: {nb_thresholds} (attendu: 4)")

        # ── Vérifier les index ─────────────────────────────────────────────
        cur.execute("""
            SELECT COUNT(*) FROM pg_indexes
            WHERE schemaname = 'public' AND indexname LIKE 'idx_%';
        """)
        nb_indexes = cur.fetchone()[0]
        print(f"\n  Index custom   : {nb_indexes} (attendu: 15)")

        cur.close()
        conn.close()

        if ok:
            print("\n🎉 Base de données conforme aux diagrammes !")
            sys.exit(0)
        else:
            print("\n⚠️  Certains éléments sont manquants.")
            sys.exit(1)

    except psycopg2.OperationalError as e:
        print(f"❌ Impossible de se connecter à PostgreSQL : {e}")
        print("\n   Assurez-vous que Docker est lancé : docker compose up -d postgres")
        sys.exit(1)


if __name__ == "__main__":
    main()
