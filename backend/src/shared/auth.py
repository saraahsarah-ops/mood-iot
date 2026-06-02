"""
Mood-IoT : Utilitaires d'authentification — vérification des tokens Keycloak.

L'identité utilisateur est gérée par Keycloak (OIDC). Le backend :
1. Reçoit un access token Bearer dans le header Authorization
2. Vérifie sa signature RS256 via le JWKS de Keycloak (cf. keycloak.py)
3. Mappe le claim `sub` (Keycloak user id) → ligne `users` en base
4. Lit le rôle depuis `realm_access.roles` (claim Keycloak)

Le backend n'émet PLUS de JWT lui-même : il n'est que vérifieur.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .keycloak import extract_roles, verify_access_token

security = HTTPBearer()

# Hiérarchie de précédence si plusieurs rôles sont attribués à un utilisateur
_ROLE_PRIORITY = ("admin", "psychiatre", "patient")


def _pick_role(roles: list[str]) -> Optional[str]:
    """Pick the most privileged role known to the application."""
    for r in _ROLE_PRIORITY:
        if r in roles:
            return r
    return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    FastAPI dependency. Verifies the Keycloak access token and returns the
    authenticated user as a plain dict.

    Returns
    -------
    dict with keys:
        - user_id (UUID str)      : internal users.id from Postgres
        - keycloak_id (str)       : `sub` claim from Keycloak
        - email (str)             : email from claims
        - role (str)              : best-matching application role
        - roles (list[str])       : all realm roles from the token
        - claims (dict)           : full decoded claims (for advanced usage)

    Raises 401 on invalid/expired token, 403 if no application role found,
    404 if the user does not have a profile yet (must POST /auth/register-profile).
    """
    # Lazy import to avoid circular dependency at module load
    from .models import User

    claims = verify_access_token(credentials.credentials)
    keycloak_id: str = claims["sub"]
    email: str = claims.get("email", "")
    roles = extract_roles(claims)
    role = _pick_role(roles)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Aucun rôle applicatif valide dans le token",
        )

    result = await db.execute(select(User).where(User.keycloak_user_id == keycloak_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Profil utilisateur introuvable. "
                "Appelez POST /auth/register-profile après le premier login."
            ),
        )

    return {
        "user_id": str(user.id),
        "keycloak_id": keycloak_id,
        "email": email or user.email,
        "role": role,
        "roles": roles,
        "claims": claims,
    }


def require_role(*allowed_roles: str):
    """Dependency factory: ensure the current user has one of the given roles."""

    async def check(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rôle requis : {', '.join(allowed_roles)}",
            )
        return current_user

    return check


def current_user_uuid(current_user: dict) -> UUID:
    """Convert the `user_id` field of the dependency dict back to a UUID."""
    return UUID(current_user["user_id"])
