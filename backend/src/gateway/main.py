"""
Mood-IoT : API Gateway (port 8000).
Point d'entree unique qui route les requetes vers les microservices internes.
Utilise httpx pour le reverse proxy.
"""

import os
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.shared.config import settings

# ---------------------------------------------------------------------------
# Rate limiting (anti brute-force / abus) — appliqué au gateway, point d'entrée
# ---------------------------------------------------------------------------
# 120 requêtes/minute par IP sur tout le gateway. Suffisant pour bloquer le
# brute-force / scraping sans gêner un usage normal. (Keycloak a en plus sa
# propre protection brute-force sur le login.)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["120/minute"],
    headers_enabled=True,
)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

# Refuse de démarrer en production avec des secrets par défaut (« change-me »).
settings.validate_production_secrets()

app = FastAPI(
    title="Mood-IoT API Gateway",
    version="1.0.0",
    description="Passerelle API pour la plateforme Mood-IoT",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Internal service registry
# In Docker: services are resolved by container name
# Locally: services run on localhost with different ports
# ---------------------------------------------------------------------------

_IN_DOCKER = os.path.exists("/.dockerenv") or os.environ.get("ENVIRONMENT") == "docker"

# Docker compose uses service names (not container_name) for DNS resolution
SERVICE_URLS = {
    "auth": "http://auth-service:8001" if _IN_DOCKER else "http://localhost:8001",
    "patient": "http://patient-service:8002" if _IN_DOCKER else "http://localhost:8002",
    "scoring": "http://ml-scoring:8003" if _IN_DOCKER else "http://localhost:8003",
    "notification": "http://notification-service:8004" if _IN_DOCKER else "http://localhost:8004",
    "teleconsult": "http://teleconsult-service:8005" if _IN_DOCKER else "http://localhost:8005",
    "doctor": "http://doctor-service:8006" if _IN_DOCKER else "http://localhost:8006",
}

# Shared httpx client (connection pooling)
_client: httpx.AsyncClient | None = None


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30.0)
    return _client


@app.on_event("shutdown")
async def shutdown():
    global _client
    if _client:
        await _client.aclose()


# ---------------------------------------------------------------------------
# Reverse proxy logic
# ---------------------------------------------------------------------------

async def _proxy(request: Request, service: str, path: str):
    """Forward a request to the target microservice."""
    base_url = SERVICE_URLS.get(service)
    if not base_url:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": f"Service inconnu: {service}"},
        )

    # Remove trailing slash to avoid 307 redirects
    path = path.rstrip("/")
    target_url = f"{base_url}/{path}"

    # Forward query params
    if request.url.query:
        target_url += f"?{request.url.query}"

    # Forward headers (remove host)
    headers = dict(request.headers)
    headers.pop("host", None)

    # Read body
    body = await request.body()

    client = await get_client()
    try:
        response = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
        )

        return JSONResponse(
            status_code=response.status_code,
            content=response.json() if response.headers.get("content-type", "").startswith("application/json") else {"raw": response.text},
            headers={
                k: v for k, v in response.headers.items()
                if k.lower() not in ("content-encoding", "content-length", "transfer-encoding")
            },
        )
    except httpx.ConnectError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": f"Service {service} indisponible", "target": target_url},
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": f"Erreur proxy: {str(e)}"},
        )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/api/v1/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Verification de sante de la gateway et des services en aval."""
    service_status = {}
    client = await get_client()
    # Health paths per service
    health_paths = {
        "auth": "/auth/health",
        "patient": "/health",
        "scoring": "/scoring/health",
        "notification": "/health",
        "teleconsult": "/teleconsult/health",
        "doctor": "/doctor/health",
    }
    for name, url in SERVICE_URLS.items():
        try:
            path = health_paths.get(name, "/health")
            r = await client.get(f"{url}{path}", timeout=3.0)
            service_status[name] = "healthy" if r.status_code == 200 else f"unhealthy ({r.status_code})"
        except Exception:
            service_status[name] = "unreachable"

    return {
        "status": "healthy",
        "service": "gateway",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": service_status,
    }


# ---------------------------------------------------------------------------
# Proxy routes
# ---------------------------------------------------------------------------


@app.api_route(
    "/api/v1/auth/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_auth(request: Request, path: str):
    """Proxy vers le service Auth (port 8001)."""
    return await _proxy(request, "auth", f"auth/{path}")


@app.api_route(
    "/api/v1/patients",
    methods=["GET", "POST"],
)
async def proxy_patient_base(request: Request):
    """Proxy vers le service Patient — route de base (liste)."""
    return await _proxy(request, "patient", "patients")


@app.api_route(
    "/api/v1/patients/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_patient(request: Request, path: str):
    """Proxy vers le service Patient (port 8002)."""
    return await _proxy(request, "patient", f"patients/{path}")


@app.api_route(
    "/api/v1/scoring/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_scoring(request: Request, path: str):
    """Proxy vers le service Scoring (port 8003)."""
    # Défense en profondeur : les routes /internal/ ne sont jamais exposées
    # publiquement (réservées aux appels inter-services dans le réseau privé).
    if path.startswith("internal/") or "/internal/" in path:
        raise HTTPException(status_code=404, detail="Not found")
    return await _proxy(request, "scoring", f"scoring/{path}")


@app.api_route(
    "/api/v1/notifications/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_notification(request: Request, path: str):
    """Proxy vers le service Notification (port 8004)."""
    return await _proxy(request, "notification", f"notifications/{path}")


@app.api_route(
    "/api/v1/teleconsult/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_teleconsult(request: Request, path: str):
    """Proxy vers le service Teleconsult (port 8005)."""
    return await _proxy(request, "teleconsult", f"teleconsult/{path}")


@app.api_route(
    "/api/v1/doctor/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_doctor(request: Request, path: str):
    """Proxy vers le service Doctor (port 8006)."""
    return await _proxy(request, "doctor", f"doctor/{path}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.gateway.main:app", host="0.0.0.0", port=8000, reload=True)
