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

Swagger UI :
  /docs                        (documentation interactive de toute l'API)

Usage :
  uvicorn src.app_unified:app --host 0.0.0.0 --port ${PORT:-8000}
"""

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute, APIWebSocketRoute
from starlette.routing import Route, WebSocketRoute

# ---------------------------------------------------------------------------
# Import des sous-applications
# ---------------------------------------------------------------------------

from src.auth.main import app as auth_app
from src.doctor.main import app as doctor_app
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
        "API unifiee de la plateforme Mood-IoT de telepsychiatrie.\n\n"
        "## Services\n"
        "- **Auth** : Authentification JWT, inscription, MFA (TOTP)\n"
        "- **Patient** : Gestion des patients, donnees IoT, metriques\n"
        "- **Scoring** : Pipeline ML heuristique, scores de risque, SHAP\n"
        "- **Notification** : Systeme d'escalade (coaching IA → alerte → urgence)\n"
        "- **Teleconsult** : Sessions Jitsi Meet avec JWT\n\n"
        "## RGPD\n"
        "- Export de donnees (Art. 20)\n"
        "- Droit a l'oubli (Art. 17)\n"
        "- Gestion des consentements\n"
    ),
    contact={
        "name": "Equipe Mood-IoT",
        "email": "contact@mood-iot.fr",
    },
    license_info={
        "name": "Projet universitaire — Master ADE 2026",
    },
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


@app.get("/", tags=["System"])
async def root():
    """Racine — informations basiques."""
    return {
        "service": "mood-iot-unified",
        "version": "2.0.0",
        "docs": "/docs",
    }


@app.get("/api/v1/health", tags=["System"])
async def health():
    """Verification de sante de l'application unifiee."""
    return {
        "status": "healthy",
        "service": "unified",
        "mode": "single-process",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "auth": "mounted",
            "doctor": "mounted",
            "patient": "mounted",
            "scoring": "mounted",
            "notification": "mounted",
            "teleconsult": "mounted",
        },
    }


# ---------------------------------------------------------------------------
# Aggregation des routes sous /api/v1 — directement dans l'app principale
# ---------------------------------------------------------------------------
# Au lieu de app.mount() (qui isole le sous-app et son Swagger),
# on copie chaque route dans l'app principale avec le prefixe /api/v1.
# Resultat : toutes les routes apparaissent dans /docs.
# ---------------------------------------------------------------------------

_SUB_APPS = [
    (auth_app, "Auth"),
    (doctor_app, "Doctor"),
    (patient_app, "Patient"),
    (scoring_app, "Scoring"),
    (notification_app, "Notification"),
    (teleconsult_app, "Teleconsult"),
]

_startup_handlers = []
_shutdown_handlers = []

for sub_app, tag in _SUB_APPS:
    for route in sub_app.routes:
        if isinstance(route, (APIRoute, Route)):
            # Creer une nouvelle route avec le prefixe /api/v1
            new_route = APIRoute(
                path=f"/api/v1{route.path}",
                endpoint=route.endpoint,
                methods=route.methods,
                name=route.name,
                tags=[tag],
                response_model=getattr(route, "response_model", None),
                status_code=getattr(route, "status_code", None),
                dependencies=getattr(route, "dependencies", None),
            )
            app.routes.append(new_route)
        elif isinstance(route, (APIWebSocketRoute, WebSocketRoute)):
            new_ws = APIWebSocketRoute(
                path=f"/api/v1{route.path}",
                endpoint=route.endpoint,
                name=route.name,
            )
            app.routes.append(new_ws)

    # Copier les event handlers
    _startup_handlers.extend(sub_app.router.on_startup)
    _shutdown_handlers.extend(sub_app.router.on_shutdown)

# Enregistrer les handlers startup/shutdown
for handler in _startup_handlers:
    app.add_event_handler("startup", handler)

for handler in _shutdown_handlers:
    app.add_event_handler("shutdown", handler)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.app_unified:app", host="0.0.0.0", port=8000, reload=True)
