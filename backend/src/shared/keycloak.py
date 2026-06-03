"""
Mood-IoT : Vérification des tokens émis par Keycloak (OIDC RS256).

Keycloak est la source de vérité de l'identité (email, mot de passe, Google
Sign-In, Apple Sign-In, MFA TOTP, reset password). Le backend ne fait QUE
vérifier les access tokens qu'il reçoit dans le header Authorization.

Conformité HDS : Keycloak est hébergé sur le même cluster OVH HDS que le
backend. Aucune donnée d'identité ne quitte la France.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx
import jwt
from cachetools import TTLCache
from fastapi import HTTPException, status
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

from .config import settings

# ---------------------------------------------------------------------------
# JWKS client (cache 1h, fetch async-safe via PyJWKClient)
# ---------------------------------------------------------------------------

# PyJWKClient is sync but uses urllib internally; we wrap fetches and cache
# the resulting client. The client itself caches keys for 5 min by default.
_jwks_client: Optional[PyJWKClient] = None
_jwks_client_loaded_at: float = 0.0
_JWKS_CLIENT_TTL_SECONDS = 3600  # 1 hour

# Per-token cache to avoid re-verifying the same token within its lifetime
_token_cache: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=1024, ttl=60)


def _get_jwks_client() -> PyJWKClient:
    """Return a cached PyJWKClient pointing at Keycloak's JWKS endpoint."""
    global _jwks_client, _jwks_client_loaded_at
    now = time.monotonic()
    if _jwks_client is None or (now - _jwks_client_loaded_at) > _JWKS_CLIENT_TTL_SECONDS:
        if not settings.KEYCLOAK_JWKS_URI:
            raise RuntimeError(
                "KEYCLOAK_JWKS_URI must be configured to verify access tokens."
            )
        _jwks_client = PyJWKClient(settings.KEYCLOAK_JWKS_URI, cache_keys=True)
        _jwks_client_loaded_at = now
    return _jwks_client


def verify_access_token(token: str) -> dict[str, Any]:
    """
    Validate a Keycloak-issued RS256 access token.

    Returns the decoded claims dict on success.
    Raises HTTPException 401 on any validation error.

    Validates:
    - Signature against Keycloak public key (via JWKS)
    - Expiration (exp)
    - Issuer (iss) matches KEYCLOAK_ISSUER
    - Audience (aud) matches one of KEYCLOAK_AUDIENCE entries
    """
    cached = _token_cache.get(token)
    if cached is not None:
        return cached

    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token).key
    except Exception as exc:  # noqa: BLE001 — surface as 401 to the client
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signature du token invalide",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    audiences = [
        a.strip() for a in settings.KEYCLOAK_AUDIENCE.split(",") if a.strip()
    ]
    # On accepte plusieurs issuers separes par des virgules. En dev local
    # Keycloak emet une URL differente selon le Host header
    # (localhost / 10.0.2.2 / keycloak), donc on tolere la liste configuree.
    allowed_issuers = [
        i.strip() for i in (settings.KEYCLOAK_ISSUER or "").split(",") if i.strip()
    ]
    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            # On valide la signature et l'audience automatiquement,
            # mais on verifie l'issuer manuellement (pyjwt n'accepte qu'une
            # seule valeur, alors qu'on en a plusieurs en local).
            audience=audiences if audiences else None,
            options={
                "require": ["exp", "iss", "sub"],
                "verify_aud": bool(audiences),
                "verify_iss": False,
            },
        )
        if allowed_issuers:
            token_iss = claims.get("iss")
            if token_iss not in allowed_issuers:
                raise InvalidTokenError(
                    f"Issuer '{token_iss}' n'est pas dans la liste autorisee "
                    f"{allowed_issuers}"
                )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token invalide ou expiré : {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    _token_cache[token] = claims
    return claims


def extract_roles(claims: dict[str, Any]) -> list[str]:
    """Pull realm roles from Keycloak access token claims."""
    realm_access = claims.get("realm_access") or {}
    roles = realm_access.get("roles") or []
    return [r for r in roles if isinstance(r, str)]


# ---------------------------------------------------------------------------
# Admin API helper (optional — used for /auth/sync and webhooks)
# ---------------------------------------------------------------------------


async def fetch_admin_token() -> Optional[str]:
    """
    Fetch a Keycloak admin token using the backend service-account client.
    Used for syncing user attributes back to Keycloak (rare).
    Returns None if admin credentials are not configured.
    """
    if not (
        settings.KEYCLOAK_ADMIN_CLIENT_ID
        and settings.KEYCLOAK_ADMIN_CLIENT_SECRET
        and settings.KEYCLOAK_TOKEN_ENDPOINT
    ):
        return None

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            settings.KEYCLOAK_TOKEN_ENDPOINT,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.KEYCLOAK_ADMIN_CLIENT_ID,
                "client_secret": settings.KEYCLOAK_ADMIN_CLIENT_SECRET,
            },
        )
    resp.raise_for_status()
    return resp.json().get("access_token")
