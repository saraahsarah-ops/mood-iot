"""
Mood-IoT : Service Patient (port 8002).
Gestion des dossiers patients, mood entries (PHQ-9), baseline, consentements.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.shared.config import settings
from src.shared.auth import get_current_user, require_role
from src.shared.database import get_db

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Mood-IoT Patient Service",
    version="1.0.0",
    description="Service de gestion des patients et suivi de l'humeur",
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
# In-memory store (placeholder)
# ---------------------------------------------------------------------------

_patients_db: dict[str, dict] = {}
_mood_entries_db: dict[str, list[dict]] = {}
_consents_db: dict[str, dict] = {}
_baseline_db: dict[str, dict] = {}

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


# ---------------------------------------------------------------------------
# Endpoints - Patients
# ---------------------------------------------------------------------------


@app.get("/patients", response_model=PatientListResponse)
async def list_patients(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(require_role("psychiatre", "admin")),
):
    """Lister les patients (psychiatre / admin uniquement)."""
    all_patients = list(_patients_db.values())

    # Filter: psychiatre sees only their patients
    if current_user["role"] == "psychiatre":
        all_patients = [
            p for p in all_patients if p.get("psychiatre_id") == current_user["user_id"]
        ]

    total = len(all_patients)
    start = (page - 1) * page_size
    end = start + page_size
    page_data = all_patients[start:end]

    return PatientListResponse(
        patients=[PatientResponse(**p) for p in page_data],
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
    current_user: dict = Depends(require_role("psychiatre", "admin")),
):
    """Creer un nouveau dossier patient."""
    patient_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    patient = {
        "id": patient_id,
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "date_of_birth": payload.date_of_birth,
        "gender": payload.gender.value,
        "email": payload.email,
        "phone": payload.phone,
        "psychiatre_id": payload.psychiatre_id or current_user["user_id"],
        "created_at": now,
        "updated_at": now,
    }
    _patients_db[patient_id] = patient

    # Initialize empty consent
    _consents_db[patient_id] = {
        "patient_id": patient_id,
        "consents": ConsentItem().model_dump(),
        "updated_at": now,
    }

    # TODO: persist to PostgreSQL via get_db()
    return PatientResponse(**patient)


@app.get("/patients/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Recuperer le detail d'un patient."""
    patient = _patients_db.get(patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")

    # Authorization: patient can only see themselves, psychiatre only their patients
    if current_user["role"] == "patient" and current_user["user_id"] != patient_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acces refuse")
    if (
        current_user["role"] == "psychiatre"
        and patient.get("psychiatre_id") != current_user["user_id"]
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acces refuse")

    return PatientResponse(**patient)


@app.put("/patients/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: str,
    payload: PatientUpdate,
    current_user: dict = Depends(require_role("psychiatre", "admin")),
):
    """Mettre a jour un dossier patient."""
    patient = _patients_db.get(patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")

    update_data = payload.model_dump(exclude_unset=True)
    patient.update(update_data)
    patient["updated_at"] = datetime.now(timezone.utc).isoformat()

    return PatientResponse(**patient)


# ---------------------------------------------------------------------------
# Endpoints - Baseline
# ---------------------------------------------------------------------------


@app.get("/patients/{patient_id}/baseline", response_model=BaselineData)
async def get_baseline(
    patient_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Recuperer les donnees de reference (baseline) d'un patient."""
    if patient_id not in _patients_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")

    baseline = _baseline_db.get(patient_id)
    if baseline is None:
        return BaselineData(patient_id=patient_id)

    return BaselineData(**baseline)


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
    current_user: dict = Depends(get_current_user),
):
    """Soumettre une entree d'humeur PHQ-9."""
    if patient_id not in _patients_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")

    # Validate scores range
    for score in payload.phq9_scores:
        if score < 0 or score > 3:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Chaque score PHQ-9 doit etre entre 0 et 3",
            )

    total = sum(payload.phq9_scores)
    entry_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    entry = {
        "id": entry_id,
        "patient_id": patient_id,
        "phq9_scores": payload.phq9_scores,
        "phq9_total": total,
        "severity": _phq9_severity(total),
        "notes": payload.notes,
        "sleep_hours": payload.sleep_hours,
        "activity_minutes": payload.activity_minutes,
        "submitted_at": now,
    }

    _mood_entries_db.setdefault(patient_id, []).append(entry)

    # TODO: trigger scoring computation via event/message queue
    return MoodEntryResponse(**entry)


# ---------------------------------------------------------------------------
# Endpoints - Consents
# ---------------------------------------------------------------------------


@app.get("/patients/{patient_id}/consents", response_model=ConsentResponse)
async def get_consents(
    patient_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Recuperer les consentements d'un patient."""
    if patient_id not in _patients_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")

    consent = _consents_db.get(patient_id)
    if consent is None:
        now = datetime.now(timezone.utc).isoformat()
        return ConsentResponse(
            patient_id=patient_id,
            consents=ConsentItem(),
            updated_at=now,
        )

    return ConsentResponse(
        patient_id=consent["patient_id"],
        consents=ConsentItem(**consent["consents"]),
        updated_at=consent["updated_at"],
    )


@app.put("/patients/{patient_id}/consents", response_model=ConsentResponse)
async def update_consents(
    patient_id: str,
    payload: ConsentItem,
    current_user: dict = Depends(get_current_user),
):
    """Mettre a jour les consentements d'un patient."""
    if patient_id not in _patients_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient introuvable")

    now = datetime.now(timezone.utc).isoformat()
    _consents_db[patient_id] = {
        "patient_id": patient_id,
        "consents": payload.model_dump(),
        "updated_at": now,
    }

    return ConsentResponse(
        patient_id=patient_id,
        consents=payload,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Endpoints - Health Data Sync (Health Connect / HealthKit → HTTP POST)
# ---------------------------------------------------------------------------

VALID_PLATFORMS = ("android_health_connect", "ios_healthkit")


def _sync_one_entry(patient_id: str, payload: HealthDataSync) -> HealthDataSyncResponse:
    """Logique UPSERT pour une entree de donnees de sante.
    TODO: remplacer par vrai UPSERT PostgreSQL via SQLAlchemy.
    """
    now = datetime.now(timezone.utc).isoformat()
    key = f"{patient_id}:{payload.date}"

    # Placeholder: stockage en memoire
    _health_data_db = getattr(_sync_one_entry, "_store", {})
    upserted = key in _health_data_db
    _health_data_db[key] = payload.model_dump()
    _sync_one_entry._store = _health_data_db

    return HealthDataSyncResponse(
        patient_id=patient_id,
        date=payload.date,
        source_platform=payload.source_platform,
        synced_at=now,
        upserted=upserted,
    )


@app.post(
    "/patients/{patient_id}/health-data",
    response_model=HealthDataSyncResponse,
    status_code=status.HTTP_201_CREATED,
)
async def sync_health_data(
    patient_id: str,
    payload: HealthDataSync,
    current_user: dict = Depends(get_current_user),
):
    """
    Recevoir les agregats quotidiens depuis l'appli mobile.
    L'appli lit Health Connect (Android) ou HealthKit (iOS) sur le device,
    puis envoie les donnees ici par HTTP POST.
    UPSERT dans daily_aggregates (patient_id, date).
    """
    # Securite : un patient ne peut soumettre que ses propres donnees
    if current_user["role"] == "patient" and current_user["user_id"] != patient_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acces refuse",
        )

    if payload.source_platform not in VALID_PLATFORMS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"source_platform doit etre l'un de : {VALID_PLATFORMS}",
        )

    return _sync_one_entry(patient_id, payload)


@app.post(
    "/patients/{patient_id}/health-data/batch",
    response_model=HealthDataBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def sync_health_data_batch(
    patient_id: str,
    payload: list[HealthDataSync],
    current_user: dict = Depends(get_current_user),
):
    """
    Batch sync : envoyer plusieurs jours de donnees de sante en une seule requete.
    Utile apres une periode hors ligne (le patient n'a pas ouvert l'appli pendant X jours).
    """
    if current_user["role"] == "patient" and current_user["user_id"] != patient_id:
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
        results.append(_sync_one_entry(patient_id, entry))

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
