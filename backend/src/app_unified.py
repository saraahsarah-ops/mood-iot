"""
Mood-IoT : Application FastAPI unifiee pour deploiement cloud (Render free tier).
Monte tous les microservices sous un seul processus.

Architecture :
  Chaque microservice (auth, patient, scoring, notification, teleconsult)
  definit ses routes sur son propre objet FastAPI. Cette app les rassemble
  dans une unique application ASGI sous le prefixe /api/v1.

URLs finales :
  /api/v1/auth/login          (auth service)
  /api/v1/patients             (patient service)
  /api/v1/scoring/compute/{id} (scoring service)
  /api/v1/notifications/all    (notification service)
  /api/v1/teleconsult/sessions (teleconsult service)

Usage :
  uvicorn src.app_unified:app --host 0.0.0.0 --port ${PORT:-8000}
"""

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.routing import Route, WebSocketRoute

# ---------------------------------------------------------------------------
# Import des sous-applications
# ---------------------------------------------------------------------------

from src.auth.main import app as auth_app
from src.patient.main import app as patient_app
from src.scoring.main import app as scoring_app
from src.notification.main import app as notification_app
from src.teleconsult.main import app as teleconsult_app

# ---------------------------------------------------------------------------
# Application principale
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Mood-IoT Unified API",
    version="2.0.0",
    description=(
        "API unifiee Mood-IoT — deploiement mono-processus pour Render free tier. "
        "Monte auth, patient, scoring, notification et teleconsult sous /api/v1/."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Endpoints propres a l'app unifiee
# ---------------------------------------------------------------------------


@app.get("/")
async def root():
    """Racine — informations basiques."""
    return {
        "service": "mood-iot-unified",
        "version": "2.0.0",
        "docs": "/docs",
    }


@app.get("/api/v1/health")
async def health():
    """Verification de sante de l'application unifiee."""
    return {
        "status": "healthy",
        "service": "unified",
        "mode": "single-process",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "auth": "mounted",
            "patient": "mounted",
            "scoring": "mounted",
            "notification": "mounted",
            "teleconsult": "mounted",
        },
    }


# ---------------------------------------------------------------------------
# Aggregation des routes sous /api/v1
# ---------------------------------------------------------------------------
# Chaque sous-application definit ses routes avec des prefixes internes :
#   auth_app         -> /auth/login, /auth/register, /auth/me ...
#   patient_app      -> /patients, /patients/{id}/mood ...
#   scoring_app      -> /scoring/compute/{id}, /scoring/latest/{id} ...
#   notification_app -> /notifications/all, /notifications/{id} ...
#   teleconsult_app  -> /teleconsult/sessions ...
#
# On cree une app intermediaire (_v1) et on copie toutes les routes
# dedans, puis on la monte sous /api/v1 sur l'app principale.
# ---------------------------------------------------------------------------

_v1 = FastAPI(
    title="Mood-IoT API v1",
    description="Aggregation de tous les microservices",
)

# Copier les evenements startup/shutdown
_startup_handlers = []
_shutdown_handlers = []

_SUB_APPS = [auth_app, patient_app, scoring_app, notification_app, teleconsult_app]

for sub_app in _SUB_APPS:
    # Copier les routes (HTTP + WebSocket)
    for route in sub_app.routes:
        if isinstance(route, (Route, WebSocketRoute)):
            _v1.routes.append(route)

    # Copier les event handlers
    _startup_handlers.extend(sub_app.router.on_startup)
    _shutdown_handlers.extend(sub_app.router.on_shutdown)

# Enregistrer les handlers sur _v1
for handler in _startup_handlers:
    _v1.add_event_handler("startup", handler)

for handler in _shutdown_handlers:
    _v1.add_event_handler("shutdown", handler)

# Monter l'app v1 sous /api/v1
app.mount("/api/v1", _v1)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.app_unified:app", host="0.0.0.0", port=8000, reload=True)
