"""
Mood-IoT : Service Patient (port 8002).
Gestion des dossiers patients, mood entries (PHQ-9), baseline, consentements.
Connecte a PostgreSQL via SQLAlchemy async.
"""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, func, Date, cast
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
    User,
)

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
    db_gender = GENDER_MAP.get(payload.gender.value, "autre")

    patient = Patient(
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

    if payload.first_name is not None:
        patient.first_name = payload.first_name
    if payload.last_name is not None:
        patient.last_name = payload.last_name
    if payload.phone is not None:
        patient.emergency_contact_phone = payload.phone

    patient.updated_at = datetime.now(timezone.utc)
    await db.flush()

    psych_id = await _get_primary_psychiatrist(patient_id, db)
    email = await _get_patient_email(patient.user_id, db)
    return _patient_to_response(patient, psych_id, email)


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
    # Verify patient exists
    pat_result = await db.execute(select(Patient.id).where(Patient.id == patient_id))
    if pat_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")

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
    pat_result = await db.execute(select(Patient.id).where(Patient.id == patient_id))
    if pat_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")

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


@app.get("/patients/{patient_id}/consents", response_model=ConsentResponse)
async def get_consents(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Recuperer les consentements d'un patient."""
    pat_result = await db.execute(select(Patient.id).where(Patient.id == patient_id))
    if pat_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")

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
    pat_result = await db.execute(select(Patient.id).where(Patient.id == patient_id))
    if pat_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")

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
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.patient.main:app", host="0.0.0.0", port=8002, reload=True)
