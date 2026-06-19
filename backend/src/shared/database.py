"""
Mood-IoT : Connexion à PostgreSQL via SQLAlchemy 2 (async).
"""

import ssl as _ssl

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from .config import settings

# Remplacer postgresql:// par postgresql+asyncpg:// pour le driver async
# Retirer ?sslmode=require car asyncpg ne le supporte pas (on passe ssl via connect_args)
_async_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
_async_url = _async_url.split("?sslmode=")[0] if "?sslmode=" in _async_url else _async_url

# SSL activé uniquement si la BD est externe (cloud managé qui l'exige).
# Un Postgres interne (même réseau Docker / localhost) n'a pas de SSL et le
# rejette → ne JAMAIS forcer SSL par le simple fait d'être en "production".
_INTERNAL_DB_HOSTS = ("@postgres:", "@localhost:", "@127.0.0.1:", "@db:")
_db_is_internal = any(h in settings.DATABASE_URL for h in _INTERNAL_DB_HOSTS)
_is_cloud = "supabase" in settings.DATABASE_URL or (
    settings.ENVIRONMENT == "production" and not _db_is_internal
)

_engine_kwargs: dict = {"echo": settings.LOG_LEVEL == "DEBUG"}
if _is_cloud:
    _ssl_ctx = _ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = _ssl.CERT_NONE
    _engine_kwargs["connect_args"] = {"ssl": _ssl_ctx}

engine = create_async_engine(_async_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """Dependency FastAPI : fournit une session de base de données."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_session() -> AsyncSession:
    """Variante callable hors-FastAPI (scheduler, scripts). Même contrat."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
