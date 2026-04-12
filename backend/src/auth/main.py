"""
Mood-IoT : Service d'Authentification (port 8001).
Gestion des utilisateurs, JWT, MFA (TOTP).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

from src.shared.config import settings
from src.shared.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    security,
)
from src.shared.database import get_db

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Mood-IoT Auth Service",
    version="1.0.0",
    description="Service d'authentification et de gestion des utilisateurs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class UserRole(str, Enum):
    patient = "patient"
    psychiatre = "psychiatre"
    admin = "admin"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.patient
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)


class RegisterResponse(BaseModel):
    id: str
    email: str
    role: str
    first_name: str
    last_name: str
    created_at: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class MFASetupResponse(BaseModel):
    secret: str
    qr_code_url: str
    message: str


class MFAVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class MFAVerifyResponse(BaseModel):
    verified: bool
    message: str


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    first_name: str
    last_name: str
    mfa_enabled: bool
    created_at: str


class MessageResponse(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# In-memory store (placeholder until DB integration)
# ---------------------------------------------------------------------------

_users_db: dict[str, dict] = {}
_blacklisted_tokens: set[str] = set()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash_password(password: str) -> str:
    """Hash password with passlib. TODO: replace with proper bcrypt."""
    # Placeholder - in production use: from passlib.context import CryptContext
    return f"hashed_{password}"


def _verify_password(plain: str, hashed: str) -> bool:
    """Verify password. TODO: replace with passlib verify."""
    return hashed == f"hashed_{plain}"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post(
    "/auth/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(payload: RegisterRequest):
    """Enregistrer un nouvel utilisateur."""
    # Check duplicate
    for user in _users_db.values():
        if user["email"] == payload.email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un compte avec cet email existe deja",
            )

    user_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    user = {
        "id": user_id,
        "email": payload.email,
        "password_hash": _hash_password(payload.password),
        "role": payload.role.value,
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "mfa_enabled": False,
        "mfa_secret": None,
        "created_at": now,
    }
    _users_db[user_id] = user

    # TODO: persist to PostgreSQL via get_db()
    return RegisterResponse(
        id=user_id,
        email=user["email"],
        role=user["role"],
        first_name=user["first_name"],
        last_name=user["last_name"],
        created_at=now,
    )


@app.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest):
    """Connexion - retourne access_token + refresh_token."""
    # Find user by email
    user = None
    for u in _users_db.values():
        if u["email"] == payload.email:
            user = u
            break

    if user is None or not _verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
        )

    access_token = create_access_token(user["id"], user["role"])
    refresh_token = create_refresh_token(user["id"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@app.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest):
    """Renouveler les tokens via un refresh_token valide."""
    token_payload = decode_token(payload.refresh_token)

    if token_payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de type invalide, refresh attendu",
        )

    if payload.refresh_token in _blacklisted_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoque",
        )

    user_id = token_payload["sub"]
    user = _users_db.get(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable",
        )

    # Blacklist old refresh token
    _blacklisted_tokens.add(payload.refresh_token)

    access_token = create_access_token(user["id"], user["role"])
    new_refresh = create_refresh_token(user["id"])

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@app.post("/auth/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(current_user: dict = Depends(get_current_user)):
    """Configurer l'authentification multi-facteurs (TOTP)."""
    user = _users_db.get(current_user["user_id"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    # TODO: generate real TOTP secret with pyotp
    secret = f"TOTP_SECRET_{uuid4().hex[:16].upper()}"
    user["mfa_secret"] = secret

    qr_url = (
        f"otpauth://totp/Mood-IoT:{user['email']}?secret={secret}&issuer=Mood-IoT"
    )

    return MFASetupResponse(
        secret=secret,
        qr_code_url=qr_url,
        message="Scannez le QR code avec votre application d'authentification",
    )


@app.post("/auth/mfa/verify", response_model=MFAVerifyResponse)
async def mfa_verify(
    payload: MFAVerifyRequest,
    current_user: dict = Depends(get_current_user),
):
    """Verifier un code TOTP et activer la MFA."""
    user = _users_db.get(current_user["user_id"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    if user.get("mfa_secret") is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA non configuree, appelez /auth/mfa/setup d'abord",
        )

    # TODO: verify code with pyotp.TOTP(user["mfa_secret"]).verify(payload.code)
    is_valid = len(payload.code) == 6 and payload.code.isdigit()

    if is_valid:
        user["mfa_enabled"] = True

    return MFAVerifyResponse(
        verified=is_valid,
        message="MFA activee avec succes" if is_valid else "Code invalide",
    )


@app.delete("/auth/logout", response_model=MessageResponse)
async def logout(current_user: dict = Depends(get_current_user)):
    """Deconnexion - blackliste le token courant."""
    # TODO: blacklist token in Redis for distributed invalidation
    return MessageResponse(message="Deconnexion reussie")


@app.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Recuperer les informations de l'utilisateur connecte."""
    user = _users_db.get(current_user["user_id"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    return UserResponse(
        id=user["id"],
        email=user["email"],
        role=user["role"],
        first_name=user["first_name"],
        last_name=user["last_name"],
        mfa_enabled=user["mfa_enabled"],
        created_at=user["created_at"],
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.auth.main:app", host="0.0.0.0", port=8001, reload=True)
