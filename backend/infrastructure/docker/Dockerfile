# ============================================================================
# Mood-IoT : Dockerfile multi-service (FastAPI)
# Utilisé par tous les microservices via l'argument SERVICE_NAME
# ============================================================================

FROM python:3.11-slim AS base

# Empêcher la création de fichiers .pyc et activer les logs non-bufferisés
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code source
COPY src/ ./src/

# Modele ML (XGBoost) si disponible
COPY models/ ./models/

# Argument pour sélectionner le microservice
ARG SERVICE_NAME=gateway
ENV SERVICE_NAME=${SERVICE_NAME}

# Port par défaut (surchargé par SERVICE_PORT dans docker-compose)
EXPOSE 8000

# Lancement du service approprié
CMD uvicorn src.${SERVICE_NAME}.main:app \
    --host 0.0.0.0 \
    --port ${SERVICE_PORT:-8000} \
    --reload \
    --log-level ${LOG_LEVEL:-info}
