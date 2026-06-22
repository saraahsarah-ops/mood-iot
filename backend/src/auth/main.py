"""
Mood-IoT : Service d'Authentification (port 8001) — version Keycloak.

Depuis la migration `feature/auth-keycloak`, l'identité est gérée par
Keycloak (réalm `moodiot` hébergé sur auth.moodiot.fr).

Ce service ne fait plus de login / refresh / MFA : il expose uniquement
3 endpoints applicatifs :

  - GET  /auth/me              → profil interne déduit du token Keycloak
  - POST /auth/register-profile → création profil patient/médecin au 1er login
  - POST /auth/sync             → mise à jour email/nom si modifiés côté Keycloak

Toute l'UI de login, OAuth Google/Apple, TOTP MFA, reset password, email verify
est rendue par Keycloak (FR via realm theme).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.config import settings
from src.shared.auth import current_user_uuid, get_current_user
from src.shared.audit import log_action
from src.shared.database import get_db
from src.shared.keycloak import verify_access_token
from src.shared.models import (
    DoctorProfile,
    Patient,
    RegistrationStatus,
    User,
    UserRole as DBUserRole,
)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Mood-IoT Auth Service",
    version="2.0.0",
    description=(
        "Service d'authentification adossé à Keycloak. "
        "Le backend ne fait que vérifier les access tokens — toutes les "
        "opérations de gestion d'identité passent par auth.moodiot.fr."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class UserResponse(BaseModel):
    id: str
    keycloak_id: str
    email: str
    role: str
    first_name: str
    last_name: str
    mfa_enabled: bool
    registration_status: str
    created_at: str


class RegisterProfileRequest(BaseModel):
    """Payload envoyé par l'app mobile lors du tout premier login Keycloak."""

    role: str = Field(..., pattern="^(patient|psychiatre)$")
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    # Champs spécifiques patient
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, pattern="^(M|F|autre)$")
    # Champs spécifiques médecin
    rpps_number: Optional[str] = None
    license_number: Optional[str] = None
    speciality: Optional[str] = None


class SyncRequest(BaseModel):
    """Payload optionnel : sync du nom si modifié côté Keycloak."""

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _resolve_name(user: User, db: AsyncSession) -> tuple[str, str]:
    """Return (first_name, last_name) from the patient or doctor profile."""
    if user.role == DBUserRole.patient:
        res = await db.execute(select(Patient).where(Patient.user_id == user.id))
        profile = res.scalar_one_or_none()
        if profile:
            return profile.first_name, profile.last_name
    elif user.role in (DBUserRole.psychiatre, DBUserRole.admin):
        res = await db.execute(
            select(DoctorProfile).where(DoctorProfile.user_id == user.id)
        )
        profile = res.scalar_one_or_none()
        if profile:
            return profile.first_name, profile.last_name
    fallback = user.email.split("@")[0] if user.email else ""
    return fallback, ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/auth/me", response_model=UserResponse)
async def get_me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Profil interne déduit du token Keycloak fourni en Bearer."""
    user_id = current_user_uuid(current_user)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable",
        )

    first_name, last_name = await _resolve_name(user, db)

    return UserResponse(
        id=str(user.id),
        keycloak_id=current_user["keycloak_id"],
        email=user.email,
        role=user.role.value,
        first_name=first_name,
        last_name=last_name,
        mfa_enabled=user.mfa_enabled,
        registration_status=(
            user.registration_status.value
            if user.registration_status is not None
            else "approved"
        ),
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@app.post(
    "/auth/register-profile",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_profile(
    payload: RegisterProfileRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Crée le profil interne (users + patient/doctor_profile) après le tout
    premier sign-in Keycloak. Idempotent : si la ligne existe déjà, met à
    jour les champs métier puis renvoie le profil.

    Le token Keycloak doit être passé en Bearer. On le vérifie à la main car
    `get_current_user` exige déjà un profil existant en base.
    """
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header Authorization Bearer manquant",
        )
    token = auth.split(" ", 1)[1].strip()
    claims = verify_access_token(token)
    keycloak_id: str = claims["sub"]
    email: str = claims.get("email", "")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le token Keycloak ne contient pas d'email",
        )

    # 1. user déjà créé ? (idempotence)
    result = await db.execute(
        select(User).where(User.keycloak_user_id == keycloak_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        # Conflit potentiel : un user avec ce même email existe (legacy)
        res_email = await db.execute(select(User).where(User.email == email))
        legacy = res_email.scalar_one_or_none()
        if legacy is not None and legacy.keycloak_user_id is None:
            # Lien automatique : on annote l'utilisateur legacy avec son sub Keycloak
            legacy.keycloak_user_id = keycloak_id
            user = legacy
        else:
            user = User(
                email=email,
                keycloak_user_id=keycloak_id,
                role=DBUserRole(payload.role),
                mfa_enabled=False,
                registration_status=(
                    RegistrationStatus.pending_approval
                    if payload.role == "psychiatre"
                    else RegistrationStatus.approved
                ),
            )
            db.add(user)
            await db.flush()

    # 2. Création du profil métier si absent
    if user.role == DBUserRole.patient:
        res = await db.execute(select(Patient).where(Patient.user_id == user.id))
        if res.scalar_one_or_none() is None:
            patient = Patient(
                user_id=user.id,
                first_name=payload.first_name,
                last_name=payload.last_name,
                date_of_birth=payload.date_of_birth,
                gender=payload.gender,
            )
            db.add(patient)
    elif user.role == DBUserRole.psychiatre:
        res = await db.execute(
            select(DoctorProfile).where(DoctorProfile.user_id == user.id)
        )
        if res.scalar_one_or_none() is None:
            doctor = DoctorProfile(
                user_id=user.id,
                first_name=payload.first_name,
                last_name=payload.last_name,
                rpps_number_encrypted=payload.rpps_number or "",
                license_number_encrypted=payload.license_number or "",
                speciality=payload.speciality or "",
                approval_status=RegistrationStatus.pending_approval,
            )
            db.add(doctor)

    await log_action(
        db,
        user_id=str(user.id),
        action="register_profile",
        resource="user",
        resource_id=str(user.id),
        details={
            "role": payload.role,
            "keycloak_id": keycloak_id,
            "email": email,
        },
    )
    await db.commit()

    first_name, last_name = await _resolve_name(user, db)
    return UserResponse(
        id=str(user.id),
        keycloak_id=keycloak_id,
        email=user.email,
        role=user.role.value,
        first_name=first_name,
        last_name=last_name,
        mfa_enabled=user.mfa_enabled,
        registration_status=(
            user.registration_status.value
            if user.registration_status is not None
            else "approved"
        ),
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@app.post("/auth/sync", response_model=UserResponse)
async def sync_profile(
    payload: SyncRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Synchronise email/nom local si modifié côté Keycloak."""
    user_id = current_user_uuid(current_user)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable"
        )

    claims = current_user["claims"]
    claims_email: str = claims.get("email", "")
    if claims_email and claims_email != user.email:
        user.email = claims_email

    if payload.first_name or payload.last_name:
        if user.role == DBUserRole.patient:
            res = await db.execute(select(Patient).where(Patient.user_id == user.id))
            patient = res.scalar_one_or_none()
            if patient:
                if payload.first_name:
                    patient.first_name = payload.first_name
                if payload.last_name:
                    patient.last_name = payload.last_name
        elif user.role in (DBUserRole.psychiatre, DBUserRole.admin):
            res = await db.execute(
                select(DoctorProfile).where(DoctorProfile.user_id == user.id)
            )
            doctor = res.scalar_one_or_none()
            if doctor:
                if payload.first_name:
                    doctor.first_name = payload.first_name
                if payload.last_name:
                    doctor.last_name = payload.last_name

    await log_action(
        db,
        user_id=str(user.id),
        action="sync_profile",
        resource="user",
        resource_id=str(user.id),
        details={"email": user.email},
    )
    await db.commit()

    first_name, last_name = await _resolve_name(user, db)
    return UserResponse(
        id=str(user.id),
        keycloak_id=current_user["keycloak_id"],
        email=user.email,
        role=user.role.value,
        first_name=first_name,
        last_name=last_name,
        mfa_enabled=user.mfa_enabled,
        registration_status=(
            user.registration_status.value
            if user.registration_status is not None
            else "approved"
        ),
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/auth/health")
async def health():
    return {"status": "healthy", "service": "auth", "auth_provider": "keycloak"}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.auth.main:app", host="0.0.0.0", port=8001, reload=True)
