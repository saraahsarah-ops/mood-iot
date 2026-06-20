"""
Mood-IoT : Service Patient (port 8002).
Gestion des dossiers patients, mood entries (PHQ-9), baseline, consentements.
Connecte a PostgreSQL via SQLAlchemy async.
"""

from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, func, delete, Date, cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

import httpx
import logging

from src.shared.config import settings
from src.shared.auth import get_current_user, require_role
from src.shared.database import get_db
from src.shared.models import (
    Patient,
    PatientPsychiatrist,
    MoodEntry,
    Consent,
    ConsentType,
    Baseline,
    DailyAggregate,
    FeatureVector,
    RiskScore,
    Notification,
    NotificationPreference,
    HumeurEntry,
    HumeurSource,
    Message,
    TeleconsultSession,
    User,
)
from src.shared.audit import log_action

logger = logging.getLogger("mood_iot.patient")

SCORING_SERVICE_URL = "http://ml-scoring:8003"

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Mood-IoT Patient Service",
    version="2.0.0",
    description="Service de gestion des patients et suivi de l'humeur — PostgreSQL",
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


class Gender(str, Enum):
    male = "male"
    female = "female"
    other = "other"


GENDER_MAP = {"male": "M", "female": "F", "other": "autre"}
GENDER_REVERSE = {"M": "male", "F": "female", "autre": "other"}


class PatientCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: str = Field(..., description="Format ISO 8601 (YYYY-MM-DD)")
    gender: Gender
    email: Optional[str] = None
    phone: Optional[str] = None
    psychiatre_id: Optional[str] = None


class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    psychiatre_id: Optional[str] = None


class PatientResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    date_of_birth: str
    gender: str
    email: Optional[str]
    phone: Optional[str]
    psychiatre_id: Optional[str]
    created_at: str
    updated_at: str


class PatientListResponse(BaseModel):
    patients: list[PatientResponse]
    total: int
    page: int
    page_size: int


class BaselineData(BaseModel):
    patient_id: str
    phq9_initial: Optional[int] = None
    gad7_initial: Optional[int] = None
    sleep_quality: Optional[float] = None
    activity_level: Optional[float] = None
    social_interaction: Optional[float] = None
    collected_at: Optional[str] = None


class MoodEntryCreate(BaseModel):
    """PHQ-9 mood entry submission."""
    phq9_scores: list[int] = Field(
        ...,
        min_length=9,
        max_length=9,
        description="9 reponses PHQ-9 (0-3 chacune)",
    )
    notes: Optional[str] = None
    sleep_hours: Optional[float] = Field(None, ge=0, le=24)
    activity_minutes: Optional[int] = Field(None, ge=0)


class MoodEntryResponse(BaseModel):
    id: str
    patient_id: str
    phq9_scores: list[int]
    phq9_total: int
    severity: str
    notes: Optional[str]
    sleep_hours: Optional[float]
    activity_minutes: Optional[int]
    submitted_at: str


class ConsentItem(BaseModel):
    data_collection: bool = False
    data_sharing_psychiatre: bool = False
    iot_monitoring: bool = False
    ai_scoring: bool = False
    emergency_contact: bool = False


class ConsentResponse(BaseModel):
    patient_id: str
    consents: ConsentItem
    updated_at: str


# ---------------------------------------------------------------------------
# Health Data Sync (Health Connect / HealthKit)
# ---------------------------------------------------------------------------


class HealthDataSync(BaseModel):
    """Donnees de sante agregees envoyees par l'appli mobile."""
    date: str = Field(..., description="Date ISO 8601 (YYYY-MM-DD)")
    heart_rate_avg: Optional[float] = Field(None, ge=0, le=300)
    heart_rate_variability: Optional[float] = Field(None, ge=0)
    sleep_duration_min: Optional[float] = Field(None, ge=0, le=1440)
    sleep_quality_score: Optional[float] = Field(None, ge=0, le=100)
    step_count: Optional[int] = Field(None, ge=0)
    gps_radius_km: Optional[float] = Field(None, ge=0)
    gps_locations_count: Optional[int] = Field(None, ge=0)
    screen_time_min: Optional[float] = Field(None, ge=0, le=1440)
    call_count: Optional[int] = Field(None, ge=0)
    call_duration_min: Optional[float] = Field(None, ge=0)
    source_platform: str = Field(
        ..., description="'android_health_connect' ou 'ios_healthkit'"
    )


class HealthDataSyncResponse(BaseModel):
    patient_id: str
    date: str
    source_platform: str
    synced_at: str
    upserted: bool


class HealthDataBatchResponse(BaseModel):
    patient_id: str
    synced_count: int
    synced_at: str
    results: list[HealthDataSyncResponse]


# ---------------------------------------------------------------------------
# Health check (avant les routes protegees)
# ---------------------------------------------------------------------------


@app.get("/patients/health")
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "patient"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PHQ9_SEVERITY = [
    (0, 4, "minimal"),
    (5, 9, "mild"),
    (10, 14, "moderate"),
    (15, 19, "moderately_severe"),
    (20, 27, "severe"),
]


def _phq9_severity(total: int) -> str:
    for low, high, label in PHQ9_SEVERITY:
        if low <= total <= high:
            return label
    return "unknown"


def _patient_to_response(
    patient: Patient,
    psychiatre_id: Optional[str] = None,
    email: Optional[str] = None,
) -> PatientResponse:
    """Convert a Patient ORM object to a PatientResponse."""
    gender_str = GENDER_REVERSE.get(
        patient.gender.value if hasattr(patient.gender, "value") else str(patient.gender),
        "other",
    )
    return PatientResponse(
        id=str(patient.id),
        first_name=patient.first_name,
        last_name=patient.last_name,
        date_of_birth=str(patient.date_of_birth) if patient.date_of_birth else "",
        gender=gender_str,
        email=email,
        phone=patient.emergency_contact_phone,
        psychiatre_id=psychiatre_id,
        created_at=patient.created_at.isoformat() if patient.created_at else "",
        updated_at=patient.updated_at.isoformat() if patient.updated_at else "",
    )


async def _get_primary_psychiatrist(patient_id: str, db: AsyncSession) -> Optional[str]:
    """Get the primary psychiatrist for a patient."""
    result = await db.execute(
        select(PatientPsychiatrist.psychiatrist_id)
        .where(PatientPsychiatrist.patient_id == patient_id)
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return str(row) if row else None


async def _get_patient_email(user_id, db: AsyncSession) -> Optional[str]:
    """Get the email for a patient's user account."""
    result = await db.execute(select(User.email).where(User.id == user_id))
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Endpoints - Patients
# ---------------------------------------------------------------------------


@app.get("/patients", response_model=PatientListResponse)
async def list_patients(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("psychiatre", "admin")),
):
    """Lister les patients (psychiatre / admin uniquement)."""
    query = select(Patient)

    # psychiatre sees only their assigned patients
    if current_user["role"] == "psychiatre":
        subq = select(PatientPsychiatrist.patient_id).where(
            PatientPsychiatrist.psychiatrist_id == current_user["user_id"]
        )
        query = query.where(Patient.id.in_(subq))

    # Count total
    count_q = select(func.count(Patient.id))
    if current_user["role"] == "psychiatre":
        count_q = count_q.where(Patient.id.in_(subq))
    total = (await db.execute(count_q)).scalar() or 0

    # Paginate
    query = query.order_by(Patient.last_name).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    patients = result.scalars().all()

    # Build responses
    patient_responses = []
    for p in patients:
        psych_id = await _get_primary_psychiatrist(str(p.id), db)
        email = await _get_patient_email(p.user_id, db)
        patient_responses.append(_patient_to_response(p, psych_id, email))

    return PatientListResponse(
        patients=patient_responses,
        total=total,
        page=page,
        page_size=page_size,
    )


@app.post(
    "/patients",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_patient(
    payload: PatientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("psychiatre", "admin")),
):
    """Creer un nouveau dossier patient."""
    import uuid
    import secrets
    import bcrypt
    
    db_gender = GENDER_MAP.get(payload.gender.value, "autre")
    
    user_email = payload.email or f"patient_{uuid.uuid4().hex[:8]}@mood-iot.local"
    password = secrets.token_urlsafe(12)
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    
    user = User(
        email=user_email,
        password_hash=password_hash,
        role="patient",
        mfa_enabled=False,
    )
    db.add(user)
    await db.flush()

    patient = Patient(
        user_id=user.id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        date_of_birth=date.fromisoformat(payload.date_of_birth) if payload.date_of_birth else None,
        gender=db_gender,
        emergency_contact_phone=payload.phone,
    )
    db.add(patient)
    await db.flush()

    # Assign psychiatrist
    psych_id = payload.psychiatre_id or current_user["user_id"]
    assignment = PatientPsychiatrist(
        patient_id=patient.id,
        psychiatrist_id=psych_id,
        is_primary=True,
    )
    db.add(assignment)

    # Initialize default consents (all False)
    for ct in ConsentType:
        consent = Consent(
            patient_id=patient.id,
            consent_type=ct,
            is_granted=False,
        )
        db.add(consent)

    await db.flush()

    return _patient_to_response(patient, psych_id, payload.email)


@app.get("/patients/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Recuperer le detail d'un patient."""
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")

    # Authorization: patient can only see their own profile
    if current_user["role"] == "patient" and str(patient.user_id) != current_user["user_id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acces refuse")

    # Authorization: psychiatre can only see their assigned patients
    if current_user["role"] == "psychiatre":
        check = await db.execute(
            select(PatientPsychiatrist).where(
                and_(
                    PatientPsychiatrist.patient_id == patient_id,
                    PatientPsychiatrist.psychiatrist_id == current_user["user_id"],
                )
            )
        )
        if check.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acces refuse")

    # Audit log
    await log_action(
        db,
        user_id=current_user.get("user_id"),
        action="view_patient",
        resource="patient",
        resource_id=patient_id,
    )
    await db.commit()

    psych_id = await _get_primary_psychiatrist(patient_id, db)
    email = await _get_patient_email(patient.user_id, db)
    return _patient_to_response(patient, psych_id, email)


@app.put("/patients/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: str,
    payload: PatientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("psychiatre", "admin")),
):
    """Mettre a jour un dossier patient."""
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")

    if current_user["role"] == "psychiatre":
        check = await db.execute(
            select(PatientPsychiatrist).where(
                and_(
                    PatientPsychiatrist.patient_id == patient_id,
                    PatientPsychiatrist.psychiatrist_id == current_user["user_id"],
                )
            )
        )
        if check.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="Vous n'etes pas assigne a ce patient")

    if payload.first_name is not None:
        patient.first_name = payload.first_name
    if payload.last_name is not None:
        patient.last_name = payload.last_name
    if payload.phone is not None:
        patient.emergency_contact_phone = payload.phone

    patient.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()

    psych_id = await _get_primary_psychiatrist(patient_id, db)
    email = await _get_patient_email(patient.user_id, db)
    return _patient_to_response(patient, psych_id, email)


@app.delete("/patients/{patient_id}", status_code=status.HTTP_200_OK)
async def delete_patient(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("psychiatre", "admin")),
):
    """
    Supprimer un dossier patient.
    Le psychiatre ne peut supprimer que ses propres patients assignes.
    L'admin peut supprimer n'importe quel patient.
    """
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")

    # Verifier que le psychiatre est bien assigne a ce patient
    if current_user["role"] == "psychiatre":
        check = await db.execute(
            select(PatientPsychiatrist).where(
                and_(
                    PatientPsychiatrist.patient_id == patient_id,
                    PatientPsychiatrist.psychiatrist_id == current_user["user_id"],
                )
            )
        )
        if check.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous n'etes pas assigne a ce patient",
            )

    # Supprimer les donnees liees (cascades en BD, mais on nettoie explicitement)
    await db.execute(delete(DailyAggregate).where(DailyAggregate.patient_id == patient_id))
    await db.execute(delete(FeatureVector).where(FeatureVector.patient_id == patient_id))
    await db.execute(delete(RiskScore).where(RiskScore.patient_id == patient_id))
    await db.execute(delete(Consent).where(Consent.patient_id == patient_id))
    await db.execute(delete(MoodEntry).where(MoodEntry.patient_id == patient_id))
    await db.execute(delete(PatientPsychiatrist).where(PatientPsychiatrist.patient_id == patient_id))

    await db.delete(patient)

    # Audit log
    await log_action(
        db,
        user_id=current_user.get("user_id"),
        action="delete_patient",
        resource="patient",
        resource_id=patient_id,
    )
    await db.commit()

    return {"message": f"Patient {patient_id} supprime avec succes."}


# ---------------------------------------------------------------------------
# Endpoints - Baseline
# ---------------------------------------------------------------------------


@app.get("/patients/{patient_id}/baseline", response_model=BaselineData)
async def get_baseline(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Recuperer les donnees de reference (baseline) d'un patient."""
    # Anti-IDOR : vérifier l'appartenance (patient lui-même / psychiatre / admin)
    await _verify_patient_access(patient_id, current_user, db)

    # Get baselines
    result = await db.execute(
        select(Baseline).where(Baseline.patient_id == patient_id)
    )
    baselines = result.scalars().all()

    # Map baselines to response fields
    data = {"patient_id": patient_id}
    for b in baselines:
        if b.metric_name == "phq9":
            data["phq9_initial"] = int(b.mean_value) if b.mean_value else None
        elif b.metric_name == "sleep_quality":
            data["sleep_quality"] = b.mean_value
        elif b.metric_name == "activity":
            data["activity_level"] = b.mean_value
        elif b.metric_name == "social":
            data["social_interaction"] = b.mean_value
        if b.calculated_at:
            data["collected_at"] = b.calculated_at.isoformat()

    return BaselineData(**data)


# ---------------------------------------------------------------------------
# Endpoints - Mood entries (PHQ-9)
# ---------------------------------------------------------------------------


@app.post(
    "/patients/{patient_id}/mood",
    response_model=MoodEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_mood_entry(
    patient_id: str,
    payload: MoodEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Soumettre une entree d'humeur PHQ-9."""
    # Verify patient exists
    pat_result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = pat_result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")
        
    if current_user["role"] == "patient" and str(patient.user_id) != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Acces refuse - Vous ne pouvez modifier que vos propres donnees")

    # Validate scores range
    for score in payload.phq9_scores:
        if score < 0 or score > 3:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Chaque score PHQ-9 doit etre entre 0 et 3",
            )

    total = sum(payload.phq9_scores)

    # Store in DB — phq9_score is the total, individual scores go in notes
    entry = MoodEntry(
        patient_id=patient_id,
        phq9_score=total,
        notes=payload.notes,
    )
    db.add(entry)
    await db.flush()

    return MoodEntryResponse(
        id=str(entry.id),
        patient_id=patient_id,
        phq9_scores=payload.phq9_scores,
        phq9_total=total,
        severity=_phq9_severity(total),
        notes=payload.notes,
        sleep_hours=payload.sleep_hours,
        activity_minutes=payload.activity_minutes,
        submitted_at=entry.submitted_at.isoformat() if entry.submitted_at else datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Endpoints - Consents
# ---------------------------------------------------------------------------

# Map our API boolean fields to DB ConsentType
_CONSENT_FIELD_MAP = {
    "data_collection": ConsentType.data_collection,
    "data_sharing_psychiatre": ConsentType.data_sharing,
    "ai_scoring": ConsentType.research,
    "iot_monitoring": ConsentType.notifications,
}


# ===========================================================================
# Consentements — wrapper "moi" (Phase 2.7)
#
# DOIT être déclaré AVANT `/patients/{patient_id}/consents` car FastAPI
# matche les routes dans l'ordre de déclaration et `me` capturerait
# `{patient_id}`.
# ===========================================================================


class MyConsentsResponse(BaseModel):
    accepted_at: Optional[str]
    cgu: bool
    rgpd: bool
    health_sensors: bool
    ai_recommendations: bool


class MyConsentsUpdate(BaseModel):
    cgu: bool
    rgpd: bool
    health_sensors: bool = False
    ai_recommendations: bool = False


def _my_consents_to_response(items: list[Consent]) -> "MyConsentsResponse":
    by_type: dict[ConsentType, bool] = {}
    last_at: Optional[datetime] = None
    for c in items:
        by_type[c.consent_type] = bool(c.is_granted)
        if c.granted_at and (last_at is None or c.granted_at > last_at):
            last_at = c.granted_at
    return MyConsentsResponse(
        accepted_at=last_at.isoformat() if last_at else None,
        cgu=by_type.get(ConsentType.data_sharing, False),
        rgpd=by_type.get(ConsentType.data_collection, False),
        health_sensors=by_type.get(ConsentType.notifications, False),
        ai_recommendations=by_type.get(ConsentType.research, False),
    )


async def _get_my_patient_simple(
    db: AsyncSession, user_id: str
) -> Patient:
    res = await db.execute(select(Patient).where(Patient.user_id == user_id))
    patient = res.scalar_one_or_none()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil patient introuvable",
        )
    return patient


@app.get("/patients/me/consents", response_model=MyConsentsResponse)
async def my_consents(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Renvoie les consentements de l'utilisateur connecté (vide si jamais donnés)."""
    patient = await _get_my_patient_simple(db, current_user["user_id"])
    res = await db.execute(select(Consent).where(Consent.patient_id == patient.id))
    return _my_consents_to_response(list(res.scalars().all()))


@app.put("/patients/me/consents", response_model=MyConsentsResponse)
async def update_my_consents(
    payload: MyConsentsUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Met à jour les 4 consentements de l'utilisateur connecté en une fois."""
    patient = await _get_my_patient_simple(db, current_user["user_id"])
    now = datetime.now(timezone.utc)
    mapping: list[tuple[ConsentType, bool]] = [
        (ConsentType.data_sharing, payload.cgu),
        (ConsentType.data_collection, payload.rgpd),
        (ConsentType.notifications, payload.health_sensors),
        (ConsentType.research, payload.ai_recommendations),
    ]
    for consent_type, granted in mapping:
        res = await db.execute(
            select(Consent).where(
                and_(
                    Consent.patient_id == patient.id,
                    Consent.consent_type == consent_type,
                )
            )
        )
        existing = res.scalar_one_or_none()
        if existing:
            existing.is_granted = granted
            if granted:
                existing.granted_at = now
                existing.revoked_at = None
            else:
                existing.revoked_at = now
        else:
            db.add(
                Consent(
                    patient_id=patient.id,
                    consent_type=consent_type,
                    is_granted=granted,
                    granted_at=now if granted else None,
                    revoked_at=None if granted else now,
                )
            )
    await log_action(
        db,
        user_id=current_user["user_id"],
        action="my_consents_update",
        resource="consent",
        resource_id=str(patient.id),
        details=payload.model_dump(),
    )
    await db.commit()
    res = await db.execute(select(Consent).where(Consent.patient_id == patient.id))
    return _my_consents_to_response(list(res.scalars().all()))


@app.get("/patients/{patient_id}/consents", response_model=ConsentResponse)
async def get_consents(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Recuperer les consentements d'un patient."""
    pat_result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = pat_result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")
        
    if current_user["role"] == "patient" and str(patient.user_id) != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Acces refuse - Vous ne pouvez voir que vos propres donnees")

    result = await db.execute(
        select(Consent).where(Consent.patient_id == patient_id)
    )
    consents = result.scalars().all()

    # Build consent item from DB rows
    consent_dict = {}
    latest_update = datetime.min.replace(tzinfo=timezone.utc)
    for c in consents:
        ct_val = c.consent_type.value if hasattr(c.consent_type, "value") else str(c.consent_type)
        # Reverse map
        for field_name, db_type in _CONSENT_FIELD_MAP.items():
            if db_type.value == ct_val:
                consent_dict[field_name] = c.is_granted
                if c.granted_at and c.granted_at > latest_update:
                    latest_update = c.granted_at

    return ConsentResponse(
        patient_id=patient_id,
        consents=ConsentItem(**consent_dict),
        updated_at=latest_update.isoformat() if latest_update.year > 1 else datetime.now(timezone.utc).isoformat(),
    )


@app.put("/patients/{patient_id}/consents", response_model=ConsentResponse)
async def update_consents(
    patient_id: str,
    payload: ConsentItem,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Mettre a jour les consentements d'un patient."""
    pat_result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = pat_result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")
        
    if current_user["role"] == "patient" and str(patient.user_id) != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Acces refuse - Vous ne pouvez modifier que vos propres donnees")

    now = datetime.now(timezone.utc)
    payload_dict = payload.model_dump()

    for field_name, db_type in _CONSENT_FIELD_MAP.items():
        is_granted = payload_dict.get(field_name, False)
        result = await db.execute(
            select(Consent).where(
                and_(
                    Consent.patient_id == patient_id,
                    Consent.consent_type == db_type,
                )
            )
        )
        consent = result.scalar_one_or_none()
        if consent:
            consent.is_granted = is_granted
            consent.granted_at = now if is_granted else None
            consent.revoked_at = now if not is_granted else None
        else:
            new_consent = Consent(
                patient_id=patient_id,
                consent_type=db_type,
                is_granted=is_granted,
                granted_at=now if is_granted else None,
            )
            db.add(new_consent)

    await db.flush()

    return ConsentResponse(
        patient_id=patient_id,
        consents=payload,
        updated_at=now.isoformat(),
    )


# ---------------------------------------------------------------------------
# Endpoints - Health Data Sync (Health Connect / HealthKit -> HTTP POST)
# ---------------------------------------------------------------------------

VALID_PLATFORMS = ("android_health_connect", "ios_healthkit")


async def _trigger_scoring(patient_id: str, target_date: str):
    """Fire-and-forget: appeler le service scoring apres sync des donnees."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{SCORING_SERVICE_URL}/scoring/internal/compute/{patient_id}",
                json={"target_date": target_date, "force_recompute": True},
                headers={"X-Internal-Service": settings.INTERNAL_SERVICE_SECRET},
            )
            if resp.status_code in (200, 201):
                logger.info("Scoring triggered for patient %s date %s: score=%s",
                            patient_id, target_date, resp.json().get("score"))
            else:
                logger.warning("Scoring returned %d for patient %s: %s",
                               resp.status_code, patient_id, resp.text[:200])
    except Exception as e:
        logger.warning("Could not trigger scoring for %s: %s", patient_id, e)


async def _sync_one_entry(
    patient_id: str, payload: HealthDataSync, db: AsyncSession
) -> HealthDataSyncResponse:
    """UPSERT reel dans daily_aggregates via PostgreSQL ON CONFLICT."""
    now = datetime.now(timezone.utc)
    target_date = date.fromisoformat(payload.date)

    values = {
        "patient_id": patient_id,
        "date": target_date,
        "heart_rate_avg": payload.heart_rate_avg,
        "heart_rate_variability": payload.heart_rate_variability,
        "sleep_duration_min": payload.sleep_duration_min,
        "sleep_quality_score": payload.sleep_quality_score,
        "step_count": payload.step_count,
        "gps_radius_km": payload.gps_radius_km,
        "gps_locations_count": payload.gps_locations_count,
        "screen_time_min": payload.screen_time_min,
        "call_count": payload.call_count,
        "call_duration_min": payload.call_duration_min,
        "source_platform": payload.source_platform,
        "synced_at": now,
    }

    # Check if exists first for upserted flag
    existing = await db.execute(
        select(DailyAggregate.id).where(
            and_(
                DailyAggregate.patient_id == patient_id,
                DailyAggregate.date == target_date,
            )
        )
    )
    was_existing = existing.scalar_one_or_none() is not None

    if was_existing:
        # UPDATE
        await db.execute(
            select(DailyAggregate).where(
                and_(
                    DailyAggregate.patient_id == patient_id,
                    DailyAggregate.date == target_date,
                )
            )
        )
        result = await db.execute(
            select(DailyAggregate).where(
                and_(
                    DailyAggregate.patient_id == patient_id,
                    DailyAggregate.date == target_date,
                )
            )
        )
        agg = result.scalar_one()
        for key, val in values.items():
            if key not in ("patient_id", "date") and val is not None:
                setattr(agg, key, val)
    else:
        # INSERT
        agg = DailyAggregate(**values)
        db.add(agg)

    await db.flush()

    return HealthDataSyncResponse(
        patient_id=patient_id,
        date=payload.date,
        source_platform=payload.source_platform,
        synced_at=now.isoformat(),
        upserted=was_existing,
    )


# ── /me/* — variantes patient-scoped (anti-IDOR) ───────────────────────────


async def _resolve_my_patient_id(
    db: AsyncSession, current_user: dict
) -> str:
    """Récupère l'ID du Patient lié au user courant (404 si pas patient)."""
    res = await db.execute(
        select(Patient).where(Patient.user_id == current_user["user_id"])
    )
    patient = res.scalar_one_or_none()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil patient introuvable",
        )
    return str(patient.id)


async def _verify_patient_access(
    patient_id: str, current_user: dict, db: AsyncSession
) -> None:
    """
    Anti-IDOR : vérifie que `current_user` peut accéder aux données de
    `patient_id`. patient → soi-même ; psychiatre → patients assignés ;
    admin → tout. Lève 403/404 sinon.
    """
    role = current_user.get("role")
    if role == "admin":
        res = await db.execute(select(Patient.id).where(Patient.id == patient_id))
        if res.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable"
            )
        return

    res = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = res.scalar_one_or_none()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable"
        )

    if role == "patient":
        if str(patient.user_id) != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Acces refuse"
            )
        return

    if role == "psychiatre":
        check = await db.execute(
            select(PatientPsychiatrist).where(
                and_(
                    PatientPsychiatrist.patient_id == patient_id,
                    PatientPsychiatrist.psychiatrist_id == current_user["user_id"],
                )
            )
        )
        if check.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Acces refuse"
            )
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acces refuse")


class SyncStatusResponse(BaseModel):
    last_sync_at: Optional[str] = None
    last_date_synced: Optional[str] = None
    source_platform: Optional[str] = None
    days_synced_last_30: int = 0


@app.get("/patients/me/health-data/status", response_model=SyncStatusResponse)
async def my_health_sync_status(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Statut de synchronisation des capteurs du patient connecté."""
    patient_id = await _resolve_my_patient_id(db, current_user)
    # Dernier enregistrement
    res = await db.execute(
        select(DailyAggregate)
        .where(DailyAggregate.patient_id == patient_id)
        .order_by(DailyAggregate.date.desc())
        .limit(1)
    )
    latest = res.scalar_one_or_none()
    # Compteur 30 derniers jours
    thirty_days_ago = (datetime.now(timezone.utc).date() - timedelta(days=30))
    res2 = await db.execute(
        select(func.count(DailyAggregate.id))
        .where(DailyAggregate.patient_id == patient_id)
        .where(DailyAggregate.date >= thirty_days_ago)
    )
    days_count = int(res2.scalar() or 0)
    return SyncStatusResponse(
        last_sync_at=(
            latest.updated_at.isoformat()
            if latest and getattr(latest, "updated_at", None)
            else (latest.date.isoformat() if latest else None)
        ),
        last_date_synced=latest.date.isoformat() if latest else None,
        source_platform=getattr(latest, "source_platform", None) if latest else None,
        days_synced_last_30=days_count,
    )


@app.post(
    "/patients/me/health-data",
    response_model=HealthDataSyncResponse,
    status_code=status.HTTP_201_CREATED,
)
async def sync_my_health_data(
    payload: HealthDataSync,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Envoie un agrégat quotidien pour le patient connecté."""
    patient_id = await _resolve_my_patient_id(db, current_user)
    if payload.source_platform not in VALID_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"source_platform doit etre l'un de : {VALID_PLATFORMS}",
        )
    result = await _sync_one_entry(patient_id, payload, db)
    await db.commit()
    await _trigger_scoring(patient_id, payload.date)
    return result


@app.post(
    "/patients/me/health-data/batch",
    response_model=HealthDataBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def sync_my_health_data_batch(
    payload: list[HealthDataSync],
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Batch sync pour le patient connecté (max 90 jours)."""
    patient_id = await _resolve_my_patient_id(db, current_user)
    if len(payload) > 90:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Maximum 90 jours par batch",
        )
    results = []
    for entry in payload:
        if entry.source_platform not in VALID_PLATFORMS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"source_platform invalide pour la date {entry.date}",
            )
        results.append(await _sync_one_entry(patient_id, entry, db))
    await db.commit()
    if results:
        latest_date = max(entry.date for entry in payload)
        await _trigger_scoring(patient_id, latest_date)
    return HealthDataBatchResponse(
        patient_id=patient_id,
        synced_count=len(results),
        synced_at=datetime.now(timezone.utc).isoformat(),
        results=results,
    )


# ── /{patient_id}/* — legacy (dashboard médecin) ───────────────────────────


@app.post(
    "/patients/{patient_id}/health-data",
    response_model=HealthDataSyncResponse,
    status_code=status.HTTP_201_CREATED,
)
async def sync_health_data(
    patient_id: str,
    payload: HealthDataSync,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Recevoir les agregats quotidiens depuis l'appli mobile.
    L'appli lit Health Connect (Android) ou HealthKit (iOS) sur le device,
    puis envoie les donnees ici par HTTP POST.
    UPSERT dans daily_aggregates (patient_id, date).
    """
    if current_user["role"] == "patient":
        # Verifier que le patient_id correspond au user connecte
        result = await db.execute(
            select(Patient).where(Patient.id == patient_id)
        )
        patient = result.scalars().first()
        if not patient or str(patient.user_id) != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acces refuse",
            )

    if payload.source_platform not in VALID_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"source_platform doit etre l'un de : {VALID_PLATFORMS}",
        )

    result = await _sync_one_entry(patient_id, payload, db)
    await db.commit()
    await _trigger_scoring(patient_id, payload.date)
    return result


@app.post(
    "/patients/{patient_id}/health-data/batch",
    response_model=HealthDataBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def sync_health_data_batch(
    patient_id: str,
    payload: list[HealthDataSync],
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Batch sync : envoyer plusieurs jours de donnees de sante en une seule requete.
    Utile apres une periode hors ligne.
    """
    if current_user["role"] == "patient":
        result = await db.execute(
            select(Patient).where(Patient.id == patient_id)
        )
        patient = result.scalars().first()
        if not patient or str(patient.user_id) != current_user["user_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acces refuse",
            )

    if len(payload) > 90:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Maximum 90 jours par batch",
        )

    results = []
    for entry in payload:
        if entry.source_platform not in VALID_PLATFORMS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"source_platform invalide pour la date {entry.date}",
            )
        results.append(await _sync_one_entry(patient_id, entry, db))

    await db.commit()

    # Trigger scoring for the most recent date in the batch
    if results:
        latest_date = max(entry.date for entry in payload)
        await _trigger_scoring(patient_id, latest_date)

    return HealthDataBatchResponse(
        patient_id=patient_id,
        synced_count=len(results),
        synced_at=datetime.now(timezone.utc).isoformat(),
        results=results,
    )


# ---------------------------------------------------------------------------
# Endpoint - Metriques patient (latest aggregate + baselines calculees)
# ---------------------------------------------------------------------------


class MetricsResponse(BaseModel):
    patient_id: str
    date: Optional[str] = None
    heart_rate_avg: Optional[float] = None
    heart_rate_variability: Optional[float] = None
    sleep_duration_min: Optional[float] = None
    sleep_quality_score: Optional[float] = None
    step_count: Optional[int] = None
    screen_time_min: Optional[float] = None
    gps_radius_km: Optional[float] = None
    call_count: Optional[int] = None
    call_duration_min: Optional[float] = None
    baselines: Optional[dict] = None


@app.get("/patients/{patient_id}/metrics", response_model=MetricsResponse)
async def get_patient_metrics(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Recuperer les metriques les plus recentes d'un patient
    (derniere journee) et les baselines calculees sur l'historique.
    """
    # Anti-IDOR : vérifier l'appartenance (patient lui-même / psychiatre / admin)
    await _verify_patient_access(patient_id, current_user, db)

    # Get latest daily aggregate
    agg_result = await db.execute(
        select(DailyAggregate)
        .where(DailyAggregate.patient_id == patient_id)
        .order_by(DailyAggregate.date.desc())
        .limit(1)
    )
    latest = agg_result.scalar_one_or_none()

    # Calculate baselines from all history (mean of all daily aggregates)
    baseline_result = await db.execute(
        select(
            func.avg(DailyAggregate.heart_rate_avg).label("hr_avg"),
            func.avg(DailyAggregate.sleep_duration_min).label("sleep_avg"),
            func.avg(DailyAggregate.step_count).label("steps_avg"),
            func.avg(DailyAggregate.screen_time_min).label("screen_avg"),
            func.avg(DailyAggregate.heart_rate_variability).label("hrv_avg"),
            func.avg(DailyAggregate.sleep_quality_score).label("sq_avg"),
        ).where(DailyAggregate.patient_id == patient_id)
    )
    bl = baseline_result.one()

    baselines = {
        "heart_rate_avg": round(float(bl.hr_avg), 1) if bl.hr_avg else 68,
        "sleep_duration_min": round(float(bl.sleep_avg), 1) if bl.sleep_avg else 450,
        "step_count": round(float(bl.steps_avg)) if bl.steps_avg else 8500,
        "screen_time_min": round(float(bl.screen_avg), 1) if bl.screen_avg else 180,
        "heart_rate_variability": round(float(bl.hrv_avg), 1) if bl.hrv_avg else 40,
        "sleep_quality_score": round(float(bl.sq_avg), 1) if bl.sq_avg else 7,
    }

    if latest:
        return MetricsResponse(
            patient_id=patient_id,
            date=str(latest.date),
            heart_rate_avg=latest.heart_rate_avg,
            heart_rate_variability=latest.heart_rate_variability,
            sleep_duration_min=latest.sleep_duration_min,
            sleep_quality_score=latest.sleep_quality_score,
            step_count=latest.step_count,
            screen_time_min=latest.screen_time_min,
            gps_radius_km=latest.gps_radius_km,
            call_count=latest.call_count,
            call_duration_min=latest.call_duration_min,
            baselines=baselines,
        )

    return MetricsResponse(patient_id=patient_id, baselines=baselines)


# ---------------------------------------------------------------------------
# Endpoints - RGPD (Donnees personnelles)
# ---------------------------------------------------------------------------


class RGPDConsentUpdate(BaseModel):
    """Mise a jour d'un consentement unique (RGPD)."""
    consent_type: str = Field(..., description="Type de consentement (data_collection, data_sharing, research, notifications)")
    granted: bool


class RGPDConsentResponse(BaseModel):
    patient_id: str
    consent_type: str
    granted: bool
    updated_at: str


@app.get("/patients/{patient_id}/data-export")
async def rgpd_data_export(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("psychiatre", "admin")),
):
    """
    RGPD Article 20 — Portabilite des donnees.
    Exporte toutes les donnees d'un patient au format JSON.
    """
    # Verify patient exists
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")

    # Patient info
    patient_data = {
        "id": str(patient.id),
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "date_of_birth": str(patient.date_of_birth) if patient.date_of_birth else None,
        "gender": patient.gender.value if hasattr(patient.gender, "value") else str(patient.gender) if patient.gender else None,
        "diagnosis": patient.diagnosis,
        "emergency_contact_phone": patient.emergency_contact_phone,
        "baseline_status": patient.baseline_status.value if hasattr(patient.baseline_status, "value") else str(patient.baseline_status),
        "created_at": patient.created_at.isoformat() if patient.created_at else None,
        "updated_at": patient.updated_at.isoformat() if patient.updated_at else None,
    }

    # Daily aggregates
    agg_result = await db.execute(
        select(DailyAggregate).where(DailyAggregate.patient_id == patient_id).order_by(DailyAggregate.date.desc())
    )
    aggregates = agg_result.scalars().all()
    daily_aggregates_data = [
        {
            "id": str(a.id),
            "date": str(a.date),
            "heart_rate_avg": a.heart_rate_avg,
            "heart_rate_variability": a.heart_rate_variability,
            "sleep_duration_min": a.sleep_duration_min,
            "sleep_quality_score": a.sleep_quality_score,
            "step_count": a.step_count,
            "gps_radius_km": a.gps_radius_km,
            "screen_time_min": a.screen_time_min,
            "call_count": a.call_count,
            "call_duration_min": a.call_duration_min,
            "source_platform": a.source_platform,
        }
        for a in aggregates
    ]

    # Risk scores
    rs_result = await db.execute(
        select(RiskScore).where(RiskScore.patient_id == patient_id).order_by(RiskScore.date.desc())
    )
    risk_scores_data = [
        {
            "id": str(r.id),
            "date": str(r.date),
            "score": r.score,
            "alert_level": r.alert_level,
            "model_version": r.model_version,
            "confidence": r.confidence,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rs_result.scalars().all()
    ]

    # Notifications
    notif_result = await db.execute(
        select(Notification).where(Notification.patient_id == patient_id).order_by(Notification.created_at.desc())
    )
    notifications_data = [
        {
            "id": str(n.id),
            "type": n.type.value if hasattr(n.type, "value") else str(n.type),
            "level": n.level,
            "title": n.title,
            "body": n.body,
            "status": n.status.value if hasattr(n.status, "value") else str(n.status),
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notif_result.scalars().all()
    ]

    # Consents
    consent_result = await db.execute(
        select(Consent).where(Consent.patient_id == patient_id)
    )
    consents_data = [
        {
            "consent_type": c.consent_type.value if hasattr(c.consent_type, "value") else str(c.consent_type),
            "is_granted": c.is_granted,
            "granted_at": c.granted_at.isoformat() if c.granted_at else None,
            "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
        }
        for c in consent_result.scalars().all()
    ]

    # Baselines
    bl_result = await db.execute(
        select(Baseline).where(Baseline.patient_id == patient_id)
    )
    baselines_data = [
        {
            "metric_name": b.metric_name,
            "mean_value": b.mean_value,
            "std_value": b.std_value,
            "min_value": b.min_value,
            "max_value": b.max_value,
            "sample_count": b.sample_count,
            "calculated_at": b.calculated_at.isoformat() if b.calculated_at else None,
        }
        for b in bl_result.scalars().all()
    ]

    # Audit log
    await log_action(
        db,
        user_id=current_user.get("user_id"),
        action="rgpd_data_export",
        resource="patient",
        resource_id=patient_id,
        details={"article": "RGPD Art. 20 — Portabilite"},
    )
    await db.commit()

    return {
        "patient": patient_data,
        "daily_aggregates": daily_aggregates_data,
        "risk_scores": risk_scores_data,
        "notifications": notifications_data,
        "consents": consents_data,
        "baselines": baselines_data,
        "export_date": datetime.now(timezone.utc).isoformat(),
    }


@app.delete("/patients/{patient_id}/data-anonymize")
async def rgpd_data_anonymize(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    """
    RGPD Article 17 — Droit a l'effacement.
    Anonymise le patient et supprime ses donnees de sante.
    Le dossier patient est conserve (anonymise) pour la piste d'audit.
    """
    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")

    # Anonymize patient record
    random_suffix = uuid4().hex[:8]
    patient.first_name = "Anonyme"
    patient.last_name = "XXXXX"
    patient.emergency_contact_phone = None
    patient.diagnosis = None
    patient.device_token_fcm = None
    patient.smartwatch_model = None
    patient.updated_at = datetime.now(timezone.utc)

    # Anonymize associated user email if user exists
    if patient.user_id:
        user_result = await db.execute(select(User).where(User.id == patient.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            user.email = f"anonyme_{random_suffix}@deleted.mood-iot.local"
            user.is_active = False

    # Delete health data (daily_aggregates, feature_vectors, risk_scores)
    await db.execute(delete(DailyAggregate).where(DailyAggregate.patient_id == patient_id))
    await db.execute(delete(FeatureVector).where(FeatureVector.patient_id == patient_id))
    await db.execute(delete(RiskScore).where(RiskScore.patient_id == patient_id))

    # Audit log
    await log_action(
        db,
        user_id=current_user.get("user_id"),
        action="rgpd_data_anonymize",
        resource="patient",
        resource_id=patient_id,
        details={"article": "RGPD Art. 17 — Droit a l'effacement"},
    )
    await db.commit()

    return {
        "message": f"Patient {patient_id} anonymise avec succes.",
        "anonymized_at": datetime.now(timezone.utc).isoformat(),
        "deleted_data": ["daily_aggregates", "feature_vectors", "risk_scores"],
    }


@app.put("/patients/{patient_id}/consents/rgpd", response_model=RGPDConsentResponse)
async def rgpd_update_consent(
    patient_id: str,
    payload: RGPDConsentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("psychiatre", "admin")),
):
    """
    RGPD — Mise a jour d'un consentement individuel.
    Cree ou met a jour un enregistrement de consentement pour le patient.
    """
    # Verify patient exists
    pat_result = await db.execute(select(Patient.id).where(Patient.id == patient_id))
    if pat_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")

    # Resolve consent type enum
    try:
        consent_type_enum = ConsentType(payload.consent_type)
    except ValueError:
        valid_types = [ct.value for ct in ConsentType]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Type de consentement invalide. Valeurs acceptees : {valid_types}",
        )

    now = datetime.now(timezone.utc)

    # Find existing consent
    result = await db.execute(
        select(Consent).where(
            and_(
                Consent.patient_id == patient_id,
                Consent.consent_type == consent_type_enum,
            )
        )
    )
    consent = result.scalar_one_or_none()

    if consent:
        consent.is_granted = payload.granted
        consent.granted_at = now if payload.granted else consent.granted_at
        consent.revoked_at = now if not payload.granted else None
    else:
        consent = Consent(
            patient_id=patient_id,
            consent_type=consent_type_enum,
            is_granted=payload.granted,
            granted_at=now if payload.granted else None,
            revoked_at=now if not payload.granted else None,
        )
        db.add(consent)

    # Audit log
    await log_action(
        db,
        user_id=current_user.get("user_id"),
        action="rgpd_update_consent",
        resource="consent",
        resource_id=patient_id,
        details={
            "consent_type": payload.consent_type,
            "granted": payload.granted,
        },
    )
    await db.commit()

    return RGPDConsentResponse(
        patient_id=patient_id,
        consent_type=payload.consent_type,
        granted=payload.granted,
        updated_at=now.isoformat(),
    )


# ===========================================================================
# Messagerie médecin → patient (côté patient)
# ===========================================================================
#
# Les messages sont stockés dans la table `messages` (modèle Message), partagée
# avec le dashboard médecin (qui les crée via teleconsult/main.py). Ici on
# expose uniquement les endpoints *patient-facing* :
#
#   GET    /patients/me/messages                  → inbox du patient connecté
#   GET    /patients/me/messages/unread-count     → badge "non lus"
#   GET    /patients/me/messages/{message_id}     → détail d'un message
#   PATCH  /patients/me/messages/{message_id}/read → marquer comme lu
#
# Sécurité : `recipient_id` est forcé à `current_user.user_id`. Aucun risque
# qu'un patient accède à la boîte d'un autre (cf. IDOR identifiés dans
# AUDIT_REPORT.md).
# ---------------------------------------------------------------------------


class MessageItem(BaseModel):
    id: str
    sender_id: str
    sender_name: str
    sender_role: str  # "psychiatre" | "patient"
    content: str
    sent_at: str
    read_at: Optional[str]


class MessageListResponse(BaseModel):
    items: list[MessageItem]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int


def _serialize_message(msg: Message, sender: User) -> MessageItem:
    """Convert SQLAlchemy Message + User → MessageItem DTO."""
    return MessageItem(
        id=str(msg.id),
        sender_id=str(msg.sender_id),
        sender_name=sender.email.split("@")[0] if sender else "",
        sender_role=sender.role.value if sender else "psychiatre",
        content=msg.content,
        sent_at=msg.sent_at.isoformat() if msg.sent_at else "",
        read_at=msg.read_at.isoformat() if msg.read_at else None,
    )


@app.get("/patients/me/messages", response_model=MessageListResponse)
async def list_my_messages(
    unread_only: bool = Query(False, description="Ne retourne que les non lus"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Inbox du patient connecté (messages reçus, du plus récent au plus ancien)."""
    user_id = current_user["user_id"]

    base_where = Message.recipient_id == user_id
    if unread_only:
        base_where = and_(base_where, Message.read_at.is_(None))

    # Récupère les messages + senders en une seule query
    res = await db.execute(
        select(Message, User)
        .join(User, Message.sender_id == User.id)
        .where(base_where)
        .order_by(Message.sent_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = res.all()
    items = [_serialize_message(m, s) for (m, s) in rows]

    # Total + unread_count globaux
    total_res = await db.execute(
        select(func.count(Message.id)).where(Message.recipient_id == user_id)
    )
    total = int(total_res.scalar() or 0)

    unread_res = await db.execute(
        select(func.count(Message.id)).where(
            and_(Message.recipient_id == user_id, Message.read_at.is_(None))
        )
    )
    unread_count = int(unread_res.scalar() or 0)

    return MessageListResponse(items=items, total=total, unread_count=unread_count)


@app.get("/patients/me/messages/unread-count", response_model=UnreadCountResponse)
async def my_unread_count(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compteur de messages non lus — utilisé par le badge de l'app mobile."""
    res = await db.execute(
        select(func.count(Message.id)).where(
            and_(
                Message.recipient_id == current_user["user_id"],
                Message.read_at.is_(None),
            )
        )
    )
    return UnreadCountResponse(unread_count=int(res.scalar() or 0))


@app.get("/patients/me/messages/{message_id}", response_model=MessageItem)
async def get_my_message(
    message_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Détail d'un message reçu. 404 si le message ne s'adresse pas à l'utilisateur."""
    res = await db.execute(
        select(Message, User)
        .join(User, Message.sender_id == User.id)
        .where(
            and_(
                Message.id == message_id,
                Message.recipient_id == current_user["user_id"],
            )
        )
    )
    row = res.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message introuvable",
        )
    msg, sender = row
    return _serialize_message(msg, sender)


@app.patch("/patients/me/messages/{message_id}/read", response_model=MessageItem)
async def mark_my_message_read(
    message_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Marque un message comme lu. Idempotent : si déjà lu, retourne tel quel."""
    res = await db.execute(
        select(Message, User)
        .join(User, Message.sender_id == User.id)
        .where(
            and_(
                Message.id == message_id,
                Message.recipient_id == current_user["user_id"],
            )
        )
    )
    row = res.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message introuvable",
        )
    msg, sender = row
    if msg.read_at is None:
        msg.read_at = datetime.now(timezone.utc)
        await log_action(
            db,
            user_id=current_user["user_id"],
            action="message_read",
            resource="message",
            resource_id=str(msg.id),
            details={"sender_id": str(msg.sender_id)},
        )
        await db.commit()
    return _serialize_message(msg, sender)


# ===========================================================================
# Notifications RDV — préférences et liste RDV futurs (Phase 2.3)
# ===========================================================================


class NotifPreferencesResponse(BaseModel):
    push_enabled: bool
    sms_enabled: bool
    email_enabled: bool
    rdv_reminder_24h: bool
    rdv_reminder_1h: bool
    rdv_reminder_now: bool
    push_token: Optional[str]
    phone_e164: Optional[str]


class NotifPreferencesUpdate(BaseModel):
    push_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    rdv_reminder_24h: Optional[bool] = None
    rdv_reminder_1h: Optional[bool] = None
    rdv_reminder_now: Optional[bool] = None
    push_token: Optional[str] = None
    phone_e164: Optional[str] = None


class UpcomingAppointment(BaseModel):
    id: str
    scheduled_at: str
    doctor_name: str
    speciality: str
    status: str
    reason: Optional[str]
    jitsi_room_id: Optional[str]


def _serialize_prefs(p: NotificationPreference) -> NotifPreferencesResponse:
    return NotifPreferencesResponse(
        push_enabled=p.push_enabled,
        sms_enabled=p.sms_enabled,
        email_enabled=p.email_enabled,
        rdv_reminder_24h=p.rdv_reminder_24h,
        rdv_reminder_1h=p.rdv_reminder_1h,
        rdv_reminder_now=p.rdv_reminder_now,
        push_token=p.push_token,
        phone_e164=p.phone_e164,
    )


async def _get_or_create_prefs(
    db: AsyncSession, user_id: str
) -> NotificationPreference:
    res = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    prefs = res.scalar_one_or_none()
    if prefs is None:
        prefs = NotificationPreference(user_id=user_id)
        db.add(prefs)
        await db.flush()
    return prefs


@app.get(
    "/patients/me/notification-preferences",
    response_model=NotifPreferencesResponse,
)
async def get_my_notif_preferences(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Préférences de notification de l'utilisateur connecté (crée si absent)."""
    prefs = await _get_or_create_prefs(db, current_user["user_id"])
    await db.commit()
    return _serialize_prefs(prefs)


@app.patch(
    "/patients/me/notification-preferences",
    response_model=NotifPreferencesResponse,
)
async def update_my_notif_preferences(
    payload: NotifPreferencesUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Met à jour partiellement les préférences (les champs `null` sont ignorés)."""
    prefs = await _get_or_create_prefs(db, current_user["user_id"])
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(prefs, field, value)
    await log_action(
        db,
        user_id=current_user["user_id"],
        action="update_notif_preferences",
        resource="notification_preferences",
        resource_id=current_user["user_id"],
        details=payload.model_dump(exclude_unset=True),
    )
    await db.commit()
    return _serialize_prefs(prefs)


@app.get("/patients/me/appointments", response_model=list[UpcomingAppointment])
async def list_my_appointments(
    upcoming_only: bool = Query(True),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Liste les RDV (téléconsultations) du patient connecté."""
    from src.shared.models import DoctorProfile

    # Récupère le patient depuis user_id
    res = await db.execute(
        select(Patient).where(Patient.user_id == current_user["user_id"])
    )
    patient = res.scalar_one_or_none()
    if patient is None:
        # Pas de profil patient → retourne liste vide
        return []

    stmt = (
        select(TeleconsultSession, DoctorProfile)
        .join(
            DoctorProfile,
            DoctorProfile.user_id == TeleconsultSession.psychiatrist_id,
            isouter=True,
        )
        .where(TeleconsultSession.patient_id == patient.id)
    )
    if upcoming_only:
        stmt = stmt.where(TeleconsultSession.scheduled_at >= func.now())
    stmt = stmt.order_by(TeleconsultSession.scheduled_at.asc()).limit(limit)

    res = await db.execute(stmt)
    rows = res.all()
    return [
        UpcomingAppointment(
            id=str(s.id),
            scheduled_at=s.scheduled_at.isoformat() if s.scheduled_at else "",
            doctor_name=(
                f"{d.first_name} {d.last_name}" if d else "Praticien"
            ),
            speciality=d.speciality if d else "Psychiatrie",
            status=s.status.value if s.status else "scheduled",
            reason=s.reason,
            jitsi_room_id=s.jitsi_room_id,
        )
        for (s, d) in rows
    ]


# ===========================================================================
# Humeur — saisies emoji simples (Phase 2.5)
# ===========================================================================


class HumeurEmojiSubmit(BaseModel):
    """1=Très mal, 7=Excellent. Note libre optionnelle (max 500 caractères)."""

    emoji_level: int = Field(..., ge=1, le=7)
    note: Optional[str] = Field(None, max_length=500)


class HumeurEntryResponse(BaseModel):
    id: str
    source: str  # "emoji" | "voix"
    emoji_level: Optional[int]
    note: Optional[str]
    created_at: str


def _serialize_humeur(h: HumeurEntry) -> HumeurEntryResponse:
    return HumeurEntryResponse(
        id=str(h.id),
        source=h.source.value if h.source else "emoji",
        emoji_level=h.emoji_level,
        note=h.note,
        created_at=h.created_at.isoformat() if h.created_at else "",
    )


async def _get_my_patient(
    db: AsyncSession, user_id: str
) -> Patient:
    """Récupère le profil Patient lié à l'utilisateur connecté, sinon 404."""
    res = await db.execute(select(Patient).where(Patient.user_id == user_id))
    patient = res.scalar_one_or_none()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil patient introuvable",
        )
    return patient


@app.post(
    "/patients/me/humeur/emoji",
    response_model=HumeurEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_humeur_emoji(
    payload: HumeurEmojiSubmit,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Saisie d'humeur par emoji (1-7 + note optionnelle)."""
    patient = await _get_my_patient(db, current_user["user_id"])
    entry = HumeurEntry(
        patient_id=patient.id,
        source=HumeurSource.emoji,
        emoji_level=payload.emoji_level,
        note=payload.note,
    )
    db.add(entry)
    await db.flush()
    await log_action(
        db,
        user_id=current_user["user_id"],
        action="humeur_emoji_submit",
        resource="humeur_entry",
        resource_id=str(entry.id),
        details={"emoji_level": payload.emoji_level},
    )
    await db.commit()
    return _serialize_humeur(entry)


@app.get("/patients/me/humeur", response_model=list[HumeurEntryResponse])
async def list_my_humeur(
    limit: int = Query(30, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Historique des saisies humeur de l'utilisateur connecté."""
    patient = await _get_my_patient(db, current_user["user_id"])
    res = await db.execute(
        select(HumeurEntry)
        .where(HumeurEntry.patient_id == patient.id)
        .order_by(HumeurEntry.created_at.desc())
        .limit(limit)
    )
    return [_serialize_humeur(h) for h in res.scalars().all()]


@app.patch(
    "/patients/me/humeur/latest",
    response_model=HumeurEntryResponse,
)
async def edit_my_latest_humeur(
    payload: HumeurEmojiSubmit,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Édite la DERNIÈRE saisie humeur du patient (les précédentes sont immuables)."""
    patient = await _get_my_patient(db, current_user["user_id"])
    res = await db.execute(
        select(HumeurEntry)
        .where(HumeurEntry.patient_id == patient.id)
        .order_by(HumeurEntry.created_at.desc())
        .limit(1)
    )
    entry = res.scalar_one_or_none()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune saisie d'humeur à modifier",
        )
    entry.emoji_level = payload.emoji_level
    entry.note = payload.note
    await db.commit()
    return _serialize_humeur(entry)


@app.delete(
    "/patients/me/humeur/latest",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_my_latest_humeur(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Supprime la DERNIÈRE saisie humeur (un changement d'avis du même jour)."""
    patient = await _get_my_patient(db, current_user["user_id"])
    res = await db.execute(
        select(HumeurEntry)
        .where(HumeurEntry.patient_id == patient.id)
        .order_by(HumeurEntry.created_at.desc())
        .limit(1)
    )
    entry = res.scalar_one_or_none()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune saisie d'humeur à supprimer",
        )
    await db.delete(entry)
    await db.commit()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.patient.main:app", host="0.0.0.0", port=8002, reload=True)
