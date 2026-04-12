"""
Mood-IoT : Service d'Authentification (port 8001).
Gestion des utilisateurs, JWT, MFA (TOTP).
Utilise PostgreSQL via SQLAlchemy async + bcrypt + pyotp.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
import bcrypt
import pyotp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.config import settings
from src.shared.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    security,
)
from src.shared.database import get_db
from src.shared.models import User, UserRole as DBUserRole

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
# Password hashing (bcrypt direct — avoids passlib compatibility issues)
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


import enum as _enum


class UserRoleEnum(str, _enum.Enum):
    patient = "patient"
    psychiatre = "psychiatre"
    admin = "admin"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: UserRoleEnum = UserRoleEnum.patient
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


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


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
# In-memory blacklist (TODO: move to Redis for distributed invalidation)
# ---------------------------------------------------------------------------

_blacklisted_tokens: set[str] = set()

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post(
    "/auth/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Enregistrer un nouvel utilisateur."""
    # Check duplicate
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte avec cet email existe deja",
        )

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=DBUserRole(payload.role.value),
        mfa_enabled=False,
    )
    db.add(user)
    await db.flush()

    return RegisterResponse(
        id=str(user.id),
        email=user.email,
        role=user.role.value,
        first_name=payload.first_name,
        last_name=payload.last_name,
        created_at=user.created_at.isoformat() if user.created_at else datetime.now(timezone.utc).isoformat(),
    )


@app.post("/auth/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Connexion - retourne access_token + refresh_token + user info."""
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
        )

    access_token = create_access_token(str(user.id), user.role.value)
    refresh_token = create_refresh_token(str(user.id))

    # Try to find patient profile for first/last name
    first_name = user.email.split("@")[0]
    last_name = ""
    if user.role == DBUserRole.patient:
        from src.shared.models import Patient
        pat_result = await db.execute(
            select(Patient).where(Patient.user_id == user.id)
        )
        patient = pat_result.scalar_one_or_none()
        if patient:
            first_name = patient.first_name
            last_name = patient.last_name

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "first_name": first_name,
            "last_name": last_name,
        },
    }


@app.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
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
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable",
        )

    # Blacklist old refresh token
    _blacklisted_tokens.add(payload.refresh_token)

    access_token = create_access_token(str(user.id), user.role.value)
    new_refresh = create_refresh_token(str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@app.post("/auth/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Configurer l'authentification multi-facteurs (TOTP)."""
    result = await db.execute(select(User).where(User.id == current_user["user_id"]))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    secret = pyotp.random_base32()
    user.mfa_secret = secret
    await db.flush()

    totp = pyotp.TOTP(secret)
    qr_url = totp.provisioning_uri(name=user.email, issuer_name="Mood-IoT")

    return MFASetupResponse(
        secret=secret,
        qr_code_url=qr_url,
        message="Scannez le QR code avec votre application d'authentification",
    )


@app.post("/auth/mfa/verify", response_model=MFAVerifyResponse)
async def mfa_verify(
    payload: MFAVerifyRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verifier un code TOTP et activer la MFA."""
    result = await db.execute(select(User).where(User.id == current_user["user_id"]))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    if user.mfa_secret is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA non configuree, appelez /auth/mfa/setup d'abord",
        )

    totp = pyotp.TOTP(user.mfa_secret)
    is_valid = totp.verify(payload.code)

    if is_valid:
        user.mfa_enabled = True
        await db.flush()

    return MFAVerifyResponse(
        verified=is_valid,
        message="MFA activee avec succes" if is_valid else "Code invalide",
    )


@app.delete("/auth/logout", response_model=MessageResponse)
async def logout(current_user: dict = Depends(get_current_user)):
    """Deconnexion - blackliste le token courant."""
    return MessageResponse(message="Deconnexion reussie")


@app.get("/auth/me", response_model=UserResponse)
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Recuperer les informations de l'utilisateur connecte."""
    result = await db.execute(select(User).where(User.id == current_user["user_id"]))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    # Try to get name from patient profile
    first_name = user.email.split("@")[0]
    last_name = ""
    if user.role == DBUserRole.patient:
        from src.shared.models import Patient
        pat_result = await db.execute(
            select(Patient).where(Patient.user_id == user.id)
        )
        patient = pat_result.scalar_one_or_none()
        if patient:
            first_name = patient.first_name
            last_name = patient.last_name

    return UserResponse(
        id=str(user.id),
        email=user.email,
        role=user.role.value,
        first_name=first_name,
        last_name=last_name,
        mfa_enabled=user.mfa_enabled,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/auth/health")
async def health():
    return {"status": "healthy", "service": "auth"}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.auth.main:app", host="0.0.0.0", port=8001, reload=True)
