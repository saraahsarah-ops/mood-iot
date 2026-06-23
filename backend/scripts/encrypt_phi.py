"""
Migration ponctuelle — chiffre au repos les champs PHI déjà présents en base.

Contexte : les colonnes PHI sont désormais typées `EncryptedText` (chiffrement
transparent à l'écriture). Ce script chiffre les lignes existantes restées en
clair, et agrandit en `TEXT` les 2 colonnes `VARCHAR` qui ne peuvent plus
contenir un token Fernet.

Propriétés :
- IDEMPOTENT : une valeur déjà chiffrée (token Fernet valide) est ignorée.
  Relancer le script ne double-chiffre rien.
- SÛR avec le code applicatif déployé : `EncryptedText` lit indifféremment le
  clair (legacy) et le chiffré, donc l'app fonctionne avant/pendant/après.

Exécution (depuis un conteneur backend qui a src/, ENCRYPTION_KEY et l'accès DB) :
    docker cp backend/scripts/encrypt_phi.py mood-iot-auth-service-1:/app/encrypt_phi.py
    docker compose -f docker-compose.prod.yml --env-file .env.prod \
        exec auth-service python /app/encrypt_phi.py
"""

from __future__ import annotations

import os
import sys

import psycopg2

from src.shared.encryption import encrypt_field, is_encrypted

# (table, clé primaire, [colonnes PHI à chiffrer])
PHI_COLUMNS: list[tuple[str, str, list[str]]] = [
    ("patients", "id", ["diagnosis", "emergency_contact_phone"]),
    ("mood_entries", "id", ["notes"]),
    ("session_notes", "id", ["content", "treatment_adjustment"]),
    ("messages", "id", ["content"]),
    ("humeur_entries", "id", ["note", "transcription", "humeur_globale", "resume"]),
]

# Colonnes VARCHAR(n) trop petites pour un token Fernet → passer en TEXT.
WIDEN_TO_TEXT: list[tuple[str, str]] = [
    ("patients", "diagnosis"),
    ("patients", "emergency_contact_phone"),
]


def _psycopg2_dsn() -> str:
    """Construit un DSN psycopg2 à partir de DATABASE_URL ou des POSTGRES_*."""
    url = os.environ.get("DATABASE_URL", "")
    if url:
        # SQLAlchemy async → driver psycopg2 synchrone.
        return url.replace("+asyncpg", "").replace("postgresql+psycopg2", "postgresql")
    user = os.environ["POSTGRES_USER"]
    pwd = os.environ["POSTGRES_PASSWORD"]
    db = os.environ["POSTGRES_DB"]
    host = os.environ.get("POSTGRES_HOST", "postgres")
    return f"postgresql://{user}:{pwd}@{host}:5432/{db}"


def main() -> int:
    conn = psycopg2.connect(_psycopg2_dsn())
    conn.autocommit = False
    cur = conn.cursor()

    # 1) Élargir les colonnes VARCHAR en TEXT (no-op si déjà TEXT).
    for table, col in WIDEN_TO_TEXT:
        cur.execute(f"ALTER TABLE {table} ALTER COLUMN {col} TYPE TEXT;")
        print(f"[schema] {table}.{col} -> TEXT")

    # 2) Chiffrer les valeurs encore en clair.
    total_chiffre = 0
    for table, pk, cols in PHI_COLUMNS:
        select_cols = ", ".join([pk] + cols)
        cur.execute(f"SELECT {select_cols} FROM {table};")
        rows = cur.fetchall()
        updated_rows = 0
        for row in rows:
            row_id = row[0]
            set_parts: list[str] = []
            params: list[str] = []
            for i, col in enumerate(cols, start=1):
                value = row[i]
                if value is None or value == "":
                    continue
                if is_encrypted(value):
                    continue  # déjà chiffré → idempotent
                set_parts.append(f"{col} = %s")
                params.append(encrypt_field(value))
                total_chiffre += 1
            if set_parts:
                params.append(row_id)
                cur.execute(
                    f"UPDATE {table} SET {', '.join(set_parts)} WHERE {pk} = %s;",
                    params,
                )
                updated_rows += 1
        print(f"[data]   {table}: {updated_rows} ligne(s) mise(s) à jour")

    conn.commit()
    cur.close()
    conn.close()
    print(f"OK — {total_chiffre} valeur(s) PHI chiffrée(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
