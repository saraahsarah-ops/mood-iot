"""
Mood-IoT : Service Medecin (Doctor).
Gestion des inscriptions, profils et approbations des psychiatres.
Gestion des membres d'institution.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.shared.config import settings
from src.shared.auth import get_current_user, require_role
from src.shared.database import get_db
from src.shared.encryption import encrypt_field, decrypt_field
from src.shared.models import (
    DoctorProfile,
    Institution,
    RegistrationStatus,
    User,
    UserRole,
)
from src.shared.password_policy import validate_password_strength

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Mood-IoT Doctor Service",
    version="1.0.0",
    description="Service de gestion des medecins psychiatres et institutions",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Hachage de mot de passe (bcrypt direct)
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# ---------------------------------------------------------------------------
# Schemas Pydantic
# ---------------------------------------------------------------------------


class DoctorRegisterRequest(BaseModel):
    """Schema d'inscription d'un medecin psychiatre."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    rpps_number: str = Field(..., min_length=1, max_length=20)
    license_number: str = Field(..., min_length=1, max_length=50)
    speciality: str = Field(default="Psychiatrie", max_length=100)
    rgpd_consent: bool
    institution_name: Optional[str] = Field(default=None, max_length=255)


class DoctorProfileResponse(BaseModel):
    """Profil complet d'un medecin (champs dechiffres)."""
    id: str
    user_id: str
    email: str
    first_name: str
    last_name: str
    speciality: str
    rpps_number: str
    license_number: str
    registration_status: str
    institution_id: Optional[str] = None
    created_at: str


class DoctorUpdateRequest(BaseModel):
    """Champs modifiables du profil medecin."""
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    speciality: Optional[str] = Field(default=None, max_length=100)


class PendingDoctorResponse(BaseModel):
    """Medecin en attente de validation."""
    user_id: str
    email: str
    first_name: str
    last_name: str
    speciality: str
    rpps_number: str
    license_number: str
    registration_status: str
    created_at: str


class ApprovalRequest(BaseModel):
    """Motif de rejet (utilise uniquement pour le rejet)."""
    reason: str = Field(..., min_length=1, max_length=500)


class InstitutionMemberRequest(BaseModel):
    """Schema pour ajouter un medecin a une institution."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    rpps_number: str = Field(..., min_length=1, max_length=20)
    license_number: str = Field(..., min_length=1, max_length=50)
    speciality: str = Field(default="Psychiatrie", max_length=100)


class MessageResponse(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_doctor_profile_response(
    user: User, profile: DoctorProfile
) -> DoctorProfileResponse:
    """Construit la reponse profil en dechiffrant les champs sensibles."""
    return DoctorProfileResponse(
        id=str(profile.id),
        user_id=str(user.id),
        email=user.email,
        first_name=profile.first_name,
        last_name=profile.last_name,
        speciality=profile.speciality,
        rpps_number=decrypt_field(profile.rpps_number_encrypted or ""),
        license_number=decrypt_field(profile.license_number_encrypted or ""),
        registration_status=user.registration_status.value,
        institution_id=str(user.institution_id) if user.institution_id else None,
        created_at=profile.created_at.isoformat() if profile.created_at else "",
    )


# ---------------------------------------------------------------------------
# 1. POST /doctor/register — Inscription publique (sans auth)
# ---------------------------------------------------------------------------


@app.post(
    "/doctor/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_doctor(
    payload: DoctorRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Inscrire un nouveau medecin psychiatre (en attente de validation)."""

    # Consentement RGPD obligatoire
    if not payload.rgpd_consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le consentement RGPD est obligatoire pour l'inscription.",
        )

    # Validation de la robustesse du mot de passe
    try:
        validate_password_strength(payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    # Verifier si l'email existe deja
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte avec cet email existe deja.",
        )

    # Creer l'utilisateur avec role psychiatre, statut pending_approval
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.psychiatre,
        registration_status=RegistrationStatus.pending_approval,
        rgpd_consent_at=datetime.now(timezone.utc),
        mfa_enabled=False,
    )
    db.add(user)
    await db.flush()

    # Si un nom d'institution est fourni, creer l'institution
    if payload.institution_name:
        institution = Institution(
            name=payload.institution_name,
            admin_user_id=user.id,
        )
        db.add(institution)
        await db.flush()
        user.institution_id = institution.id

    # Creer le profil medecin avec champs chiffres
    doctor_profile = DoctorProfile(
        user_id=user.id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        speciality=payload.speciality,
        rpps_number_encrypted=encrypt_field(payload.rpps_number),
        license_number_encrypted=encrypt_field(payload.license_number),
    )
    db.add(doctor_profile)
    await db.commit()

    return MessageResponse(
        message="Inscription soumise. En attente de validation."
    )


# ---------------------------------------------------------------------------
# 2. GET /doctor/me — Profil du medecin connecte
# ---------------------------------------------------------------------------


@app.get("/doctor/me", response_model=DoctorProfileResponse)
async def get_my_profile(
    current_user: dict = Depends(require_role("psychiatre")),
    db: AsyncSession = Depends(get_db),
):
    """Recuperer le profil du medecin connecte (champs dechiffres)."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.doctor_profile))
        .where(User.id == current_user["user_id"])
    )
    user = result.scalar_one_or_none()
    if user is None or user.doctor_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil medecin introuvable.",
        )

    return _build_doctor_profile_response(user, user.doctor_profile)


# ---------------------------------------------------------------------------
# 3. PUT /doctor/me — Mise a jour du profil (champs non sensibles)
# ---------------------------------------------------------------------------


@app.put("/doctor/me", response_model=DoctorProfileResponse)
async def update_my_profile(
    payload: DoctorUpdateRequest,
    current_user: dict = Depends(require_role("psychiatre")),
    db: AsyncSession = Depends(get_db),
):
    """Mettre a jour les champs non sensibles du profil medecin."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.doctor_profile))
        .where(User.id == current_user["user_id"])
    )
    user = result.scalar_one_or_none()
    if user is None or user.doctor_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil medecin introuvable.",
        )

    profile = user.doctor_profile

    if payload.first_name is not None:
        profile.first_name = payload.first_name
    if payload.last_name is not None:
        profile.last_name = payload.last_name
    if payload.speciality is not None:
        profile.speciality = payload.speciality

    await db.commit()
    await db.refresh(user)
    await db.refresh(profile)

    return _build_doctor_profile_response(user, profile)


# ---------------------------------------------------------------------------
# 4. GET /doctor/pending — Liste des medecins en attente (admin)
# ---------------------------------------------------------------------------


@app.get("/doctor/pending", response_model=list[PendingDoctorResponse])
async def list_pending_doctors(
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Lister tous les medecins en attente d'approbation (admin uniquement)."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.doctor_profile))
        .where(User.registration_status == RegistrationStatus.pending_approval)
    )
    users = result.scalars().all()

    pending_list: list[PendingDoctorResponse] = []
    for user in users:
        profile = user.doctor_profile
        if profile is None:
            continue
        pending_list.append(
            PendingDoctorResponse(
                user_id=str(user.id),
                email=user.email,
                first_name=profile.first_name,
                last_name=profile.last_name,
                speciality=profile.speciality,
                rpps_number=decrypt_field(profile.rpps_number_encrypted or ""),
                license_number=decrypt_field(profile.license_number_encrypted or ""),
                registration_status=user.registration_status.value,
                created_at=profile.created_at.isoformat() if profile.created_at else "",
            )
        )

    return pending_list


# ---------------------------------------------------------------------------
# 5. PUT /doctor/{user_id}/approve — Approuver un medecin (admin)
# ---------------------------------------------------------------------------


@app.put("/doctor/{user_id}/approve", response_model=MessageResponse)
async def approve_doctor(
    user_id: UUID,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Approuver l'inscription d'un medecin (admin uniquement)."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.doctor_profile))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )

    if user.registration_status != RegistrationStatus.pending_approval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce compte n'est pas en attente d'approbation.",
        )

    # Mettre a jour le statut
    user.registration_status = RegistrationStatus.approved

    # Mettre a jour le profil medecin
    profile = user.doctor_profile
    if profile is not None:
        profile.approved_by = UUID(current_user["user_id"])
        profile.approved_at = datetime.now(timezone.utc)

    await db.commit()

    return MessageResponse(message="Medecin approuve avec succes.")


# ---------------------------------------------------------------------------
# 6. PUT /doctor/{user_id}/reject — Rejeter un medecin (admin)
# ---------------------------------------------------------------------------


@app.put("/doctor/{user_id}/reject", response_model=MessageResponse)
async def reject_doctor(
    user_id: UUID,
    payload: ApprovalRequest,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Rejeter l'inscription d'un medecin avec un motif (admin uniquement)."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.doctor_profile))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )

    if user.registration_status != RegistrationStatus.pending_approval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce compte n'est pas en attente d'approbation.",
        )

    # Mettre a jour le statut
    user.registration_status = RegistrationStatus.rejected

    # Enregistrer le motif de rejet
    profile = user.doctor_profile
    if profile is not None:
        profile.approval_note = payload.reason

    await db.commit()

    return MessageResponse(message="Inscription rejetee.")


# ---------------------------------------------------------------------------
# 7. GET /doctor/institution/members — Membres de l'institution (admin)
# ---------------------------------------------------------------------------


@app.get("/doctor/institution/members", response_model=list[DoctorProfileResponse])
async def list_institution_members(
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Lister tous les medecins de l'institution de l'admin connecte."""
    # Recuperer l'utilisateur admin pour connaitre son institution
    admin_result = await db.execute(
        select(User).where(User.id == current_user["user_id"])
    )
    admin_user = admin_result.scalar_one_or_none()
    if admin_user is None or admin_user.institution_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous n'etes rattache a aucune institution.",
        )

    # Recuperer tous les membres de l'institution
    result = await db.execute(
        select(User)
        .options(selectinload(User.doctor_profile))
        .where(User.institution_id == admin_user.institution_id)
        .where(User.role == UserRole.psychiatre)
    )
    members = result.scalars().all()

    member_list: list[DoctorProfileResponse] = []
    for user in members:
        profile = user.doctor_profile
        if profile is None:
            continue
        member_list.append(_build_doctor_profile_response(user, profile))

    return member_list


# ---------------------------------------------------------------------------
# 8. POST /doctor/institution/members — Ajouter un medecin a l'institution
# ---------------------------------------------------------------------------


@app.post(
    "/doctor/institution/members",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_institution_member(
    payload: InstitutionMemberRequest,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Ajouter un medecin a l'institution de l'admin (cree le compte + profil)."""
    # Recuperer l'admin et son institution
    admin_result = await db.execute(
        select(User).where(User.id == current_user["user_id"])
    )
    admin_user = admin_result.scalar_one_or_none()
    if admin_user is None or admin_user.institution_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous n'etes rattache a aucune institution.",
        )

    # Validation du mot de passe
    try:
        validate_password_strength(payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    # Verifier si l'email existe deja
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte avec cet email existe deja.",
        )

    # Creer l'utilisateur rattache a l'institution
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=UserRole.psychiatre,
        registration_status=RegistrationStatus.approved,
        institution_id=admin_user.institution_id,
        mfa_enabled=False,
    )
    db.add(user)
    await db.flush()

    # Creer le profil medecin
    doctor_profile = DoctorProfile(
        user_id=user.id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        speciality=payload.speciality,
        rpps_number_encrypted=encrypt_field(payload.rpps_number),
        license_number_encrypted=encrypt_field(payload.license_number),
        approved_by=UUID(current_user["user_id"]),
        approved_at=datetime.now(timezone.utc),
    )
    db.add(doctor_profile)
    await db.commit()

    return MessageResponse(message="Medecin ajoute a l'institution avec succes.")


# ---------------------------------------------------------------------------
# 9. DELETE /doctor/institution/members/{user_id} — Retirer un medecin
# ---------------------------------------------------------------------------


@app.delete(
    "/doctor/institution/members/{user_id}",
    response_model=MessageResponse,
)
async def remove_institution_member(
    user_id: UUID,
    current_user: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Retirer un medecin de l'institution (met institution_id a null)."""
    # Recuperer l'admin et son institution
    admin_result = await db.execute(
        select(User).where(User.id == current_user["user_id"])
    )
    admin_user = admin_result.scalar_one_or_none()
    if admin_user is None or admin_user.institution_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous n'etes rattache a aucune institution.",
        )

    # Recuperer le medecin cible
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable.",
        )

    # Verifier que le medecin appartient a la meme institution
    if target_user.institution_id != admin_user.institution_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce medecin n'appartient pas a votre institution.",
        )

    # Empecher l'admin de se retirer lui-meme
    if str(target_user.id) == current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas vous retirer vous-meme de l'institution.",
        )

    # Retirer le medecin de l'institution
    target_user.institution_id = None
    await db.commit()

    return MessageResponse(message="Medecin retire de l'institution.")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/doctor/health")
async def health():
    return {"status": "healthy", "service": "doctor"}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.doctor.main:app", host="0.0.0.0", port=8006, reload=True)
