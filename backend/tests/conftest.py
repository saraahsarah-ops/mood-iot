"""Infrastructure de tests d'intégration des endpoints (FastAPI + BD de test).

Stratégie :
- BD Postgres de test (les modèles utilisent UUID/JSONB/PgEnum -> pas SQLite).
- Engine dédié en NullPool (chaque connexion est fraîche -> pas de
  « attached to different event loop » avec pytest-asyncio).
- Override de `get_db` (session de test) et `get_current_user` (utilisateur
  factice) — style « Mockito » pour l'authentification.
- Avant chaque test qui demande la BD : create_all (idempotent) + TRUNCATE +
  seed d'un patient de base.

DATABASE_URL doit pointer vers une BD de test (fournie par la CI ou le
conteneur). Les tests purement unitaires (channels, escalation…) ne
demandent pas ces fixtures et ne touchent donc pas la BD.
"""
import os
import uuid

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("ENCRYPTION_KEY", "zZ8kQwManbY9X4n2pV6cR3tL1sH7jD0fG5wE8uA2bN4=")
os.environ.setdefault("JWT_SECRET_KEY", "ci-test-secret-32-chars-long-please")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.shared.auth import get_current_user
from src.shared.database import get_db
from src.shared.models import Base, Patient, User, UserRole

PATIENT_USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
PATIENT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a2")

_DB_URL = os.environ.get("DATABASE_URL", "")
_async_url = _DB_URL.replace("postgresql://", "postgresql+asyncpg://").split("?sslmode=")[0]

test_engine = create_async_engine(_async_url, poolclass=NullPool) if _async_url else None
TestSession = (
    async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    if test_engine
    else None
)


async def _override_get_db():
    async with TestSession() as session:
        yield session


def fake_patient_user():
    return {
        "user_id": str(PATIENT_USER_ID),
        "keycloak_id": "kc-test-patient",
        "email": "patient@test.fr",
        "role": "patient",
        "roles": ["patient"],
        "claims": {},
    }


@pytest_asyncio.fixture
async def db_ready():
    """Schéma prêt + base nettoyée + patient de base semé."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    async with TestSession() as s:
        s.add(User(id=PATIENT_USER_ID, email="patient@test.fr", role=UserRole.patient))
        s.add(
            Patient(
                id=PATIENT_ID,
                user_id=PATIENT_USER_ID,
                first_name="Test",
                last_name="Patient",
            )
        )
        await s.commit()
    yield


@pytest_asyncio.fixture
async def patient_client(db_ready):
    """Client HTTP du service patient, authentifié comme le patient semé."""
    from src.patient import main as patient_main

    patient_main.app.dependency_overrides[get_db] = _override_get_db
    patient_main.app.dependency_overrides[get_current_user] = fake_patient_user
    transport = ASGITransport(app=patient_main.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    patient_main.app.dependency_overrides.clear()
