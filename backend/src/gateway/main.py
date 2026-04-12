"""
Mood-IoT : API Gateway (port 8000).
Point d'entree unique qui route les requetes vers les microservices internes.
"""

from datetime import datetime, timezone

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.shared.config import settings

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Mood-IoT API Gateway",
    version="1.0.0",
    description="Passerelle API pour la plateforme Mood-IoT",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Internal service registry (URLs resolved at runtime)
# ---------------------------------------------------------------------------

SERVICE_URLS = {
    "auth": "http://localhost:8001",
    "patient": "http://localhost:8002",
    "scoring": "http://localhost:8003",
    "notification": "http://localhost:8004",
    "teleconsult": "http://localhost:8005",
}

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/api/v1/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Verification de sante de la gateway et des services en aval."""
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {name: "unknown" for name in SERVICE_URLS},
    }


# ---------------------------------------------------------------------------
# Proxy placeholder routes
# ---------------------------------------------------------------------------


@app.api_route(
    "/api/v1/auth/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_auth(request: Request, path: str):
    """Proxy vers le service Auth (port 8001). TODO: implementer httpx forward."""
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "detail": "Proxy non implemente",
            "target": f"{SERVICE_URLS['auth']}/auth/{path}",
        },
    )


@app.api_route(
    "/api/v1/patients/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_patient(request: Request, path: str):
    """Proxy vers le service Patient (port 8002). TODO: implementer httpx forward."""
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "detail": "Proxy non implemente",
            "target": f"{SERVICE_URLS['patient']}/patients/{path}",
        },
    )


@app.api_route(
    "/api/v1/scoring/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_scoring(request: Request, path: str):
    """Proxy vers le service Scoring (port 8003). TODO: implementer httpx forward."""
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "detail": "Proxy non implemente",
            "target": f"{SERVICE_URLS['scoring']}/scoring/{path}",
        },
    )


@app.api_route(
    "/api/v1/notifications/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_notification(request: Request, path: str):
    """Proxy vers le service Notification (port 8004). TODO: implementer httpx forward."""
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "detail": "Proxy non implemente",
            "target": f"{SERVICE_URLS['notification']}/notifications/{path}",
        },
    )


@app.api_route(
    "/api/v1/teleconsult/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_teleconsult(request: Request, path: str):
    """Proxy vers le service Teleconsult (port 8005). TODO: implementer httpx forward."""
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "detail": "Proxy non implemente",
            "target": f"{SERVICE_URLS['teleconsult']}/teleconsult/{path}",
        },
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.gateway.main:app", host="0.0.0.0", port=8000, reload=True)
