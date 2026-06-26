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
from src.shared.encryption import encrypt_field
from src.shared.models import (
    Base,
    DoctorProfile,
    Patient,
    PatientPsychiatrist,
    User,
    UserRole,
)

PATIENT_USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
PATIENT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a2")
PSY_USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000b1")
ADMIN_USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000c1")

_DB_URL = os.environ.get("DATABASE_URL", "")
_async_url = _DB_URL.replace("postgresql://", "postgresql+asyncpg://").split("?sslmode=")[0]

test_engine = create_async_engine(_async_url, poolclass=NullPool) if _async_url else None
TestSession = (
    async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    if test_engine
    else None
)


async def _override_get_db():
    # Reproduit le contrat de get_db (commit en succès, rollback en erreur) :
    # sans commit, les écritures d'une requête sont annulées et invisibles
    # pour la requête suivante (lecture après écriture).
    async with TestSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _fake_user(user_id, role, email):
    return {
        "user_id": str(user_id),
        "keycloak_id": f"kc-test-{role}",
        "email": email,
        "role": role,
        "roles": [role],
        "claims": {},
    }


def fake_patient_user():
    return _fake_user(PATIENT_USER_ID, "patient", "patient@test.fr")


def fake_psychiatre_user():
    return _fake_user(PSY_USER_ID, "psychiatre", "psy@test.fr")


def fake_admin_user():
    return _fake_user(ADMIN_USER_ID, "admin", "admin@test.fr")


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
            User(id=PSY_USER_ID, email="psy@test.fr", role=UserRole.psychiatre)
        )
        s.add(User(id=ADMIN_USER_ID, email="admin@test.fr", role=UserRole.admin))
        s.add(
            Patient(
                id=PATIENT_ID,
                user_id=PATIENT_USER_ID,
                first_name="Test",
                last_name="Patient",
            )
        )
        s.add(
            DoctorProfile(
                user_id=PSY_USER_ID,
                first_name="Doc",
                last_name="Test",
                speciality="Psychiatrie",
                rpps_number_encrypted=encrypt_field("10101010101"),
                license_number_encrypted=encrypt_field("LIC-TEST"),
            )
        )
        # Lien patient <-> psychiatre (nécessaire pour l'anti-IDOR du scoring)
        s.add(
            PatientPsychiatrist(
                patient_id=PATIENT_ID,
                psychiatrist_id=PSY_USER_ID,
                is_primary=True,
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


@pytest_asyncio.fixture
async def db_query(db_ready):
    """Session de test pour vérifier l'état de la BD dans les assertions."""
    async with TestSession() as session:
        yield session


async def _client_for(app, user_factory):
    app.dependency_overrides[get_db] = _override_get_db
    if user_factory is not None:
        app.dependency_overrides[get_current_user] = user_factory
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture
async def patient_psy_client(db_ready):
    """Service patient vu par le psychiatre semé (lié au patient -> accès OK)."""
    from src.patient import main as patient_main

    client = await _client_for(patient_main.app, fake_psychiatre_user)
    async with client:
        yield client
    patient_main.app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def doctor_public_client(db_ready):
    """Service doctor sans authentification (ex. POST /doctor/register)."""
    from src.doctor import main as doctor_main

    doctor_main.app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=doctor_main.app), base_url="http://test"
    ) as client:
        yield client
    doctor_main.app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def doctor_psy_client(db_ready):
    """Service doctor authentifié comme le psychiatre semé."""
    from src.doctor import main as doctor_main

    client = await _client_for(doctor_main.app, fake_psychiatre_user)
    async with client:
        yield client
    doctor_main.app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def doctor_admin_client(db_ready):
    """Service doctor authentifié comme admin."""
    from src.doctor import main as doctor_main

    client = await _client_for(doctor_main.app, fake_admin_user)
    async with client:
        yield client
    doctor_main.app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def scoring_psy_client(db_ready):
    """Service scoring authentifié comme le psychiatre semé (lié au patient)."""
    from src.scoring import main as scoring_main

    client = await _client_for(scoring_main.app, fake_psychiatre_user)
    async with client:
        yield client
    scoring_main.app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def teleconsult_psy_client(db_ready):
    """Service teleconsult authentifié comme le psychiatre semé."""
    from src.teleconsult import main as t_main

    client = await _client_for(t_main.app, fake_psychiatre_user)
    async with client:
        yield client
    t_main.app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def notification_psy_client(db_ready):
    """Service notification authentifié comme le psychiatre semé."""
    from src.notification import main as n_main

    client = await _client_for(n_main.app, fake_psychiatre_user)
    async with client:
        yield client
    n_main.app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_patient_client(db_ready):
    """Service auth authentifié comme le patient semé."""
    from src.auth import main as a_main

    client = await _client_for(a_main.app, fake_patient_user)
    async with client:
        yield client
    a_main.app.dependency_overrides.clear()
