# ============================================================================
# Mood-IoT — Dockerfile multi-stage, multi-service
#
# Build:
#   docker build \
#     --build-arg SERVICE_NAME=patient \
#     -t mood-iot/patient:latest \
#     -f backend/infrastructure/docker/Dockerfile backend/
#
# Run (exemple) :
#   docker run --rm -p 8002:8000 \
#     -e DATABASE_URL=... -e KEYCLOAK_ISSUER=... \
#     mood-iot/patient:latest
#
# Conçu pour OVH Managed Kubernetes HDS (Healthcare Hosted Service) :
#   - User non-root (uid 1001) → respect des PodSecurityPolicy
#   - Healthcheck HTTP → readinessProbe Kubernetes
#   - Logs JSON sur stdout (structlog côté app)
#   - Pas de fichiers .pyc générés (PYTHONDONTWRITEBYTECODE)
# ============================================================================

# ── Stage 1 : builder ───────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Build deps (purgés ensuite via le stage runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Stage 2 : runtime ───────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:$PATH" \
    PYTHONPATH="/install/lib/python3.11/site-packages"

WORKDIR /app

# Runtime deps : curl pour le healthcheck, libpq5 pour asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    # User non-root (UID > 1000 = compat OVH HDS PSP)
    && groupadd --system --gid 1001 mood \
    && useradd  --system --uid 1001 --gid mood --no-create-home --shell /bin/false mood

# Copie des dépendances compilées
COPY --from=builder /install /install

# Code applicatif + modèle ML
COPY --chown=mood:mood src/    ./src/
COPY --chown=mood:mood models/ ./models/

# Service à lancer (override via --build-arg ou docker-compose)
ARG SERVICE_NAME=gateway
ENV SERVICE_NAME=${SERVICE_NAME} \
    SERVICE_PORT=8000

EXPOSE 8000

# Healthcheck — chaque service expose GET /health (200 = OK)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://localhost:${SERVICE_PORT}/health" || exit 1

USER mood

# Pas de --reload en prod (consomme CPU + ne lit pas les volumes en K8s)
CMD ["sh", "-c", "uvicorn src.${SERVICE_NAME}.main:app --host 0.0.0.0 --port ${SERVICE_PORT} --log-level ${LOG_LEVEL:-info} --proxy-headers --forwarded-allow-ips='*'"]
