"""
Mood-IoT : Service ML Scoring (port 8003).
Calcul du score de risque, historique, explications SHAP.
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
    title="Mood-IoT Scoring Service",
    version="1.0.0",
    description="Service de scoring ML pour l'evaluation du risque patient",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Thresholds from config: 40 / 60 / 80
# ---------------------------------------------------------------------------

THRESHOLDS = settings.scoring_thresholds_tuple  # (40, 60, 80)


class RiskLevel(str, Enum):
    low = "low"              # 0 - 39
    moderate = "moderate"    # 40 - 59
    high = "high"            # 60 - 79
    critical = "critical"    # 80 - 100


def _classify_risk(score: float) -> RiskLevel:
    if score < THRESHOLDS[0]:
        return RiskLevel.low
    elif score < THRESHOLDS[1]:
        return RiskLevel.moderate
    elif score < THRESHOLDS[2]:
        return RiskLevel.high
    else:
        return RiskLevel.critical


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ComputeScoreRequest(BaseModel):
    phq9_total: Optional[int] = Field(None, ge=0, le=27)
    sleep_hours: Optional[float] = Field(None, ge=0, le=24)
    activity_minutes: Optional[int] = Field(None, ge=0)
    heart_rate_avg: Optional[float] = None
    hrv_avg: Optional[float] = None
    social_interaction_score: Optional[float] = Field(None, ge=0, le=10)
    force_recompute: bool = False


class ScoreResponse(BaseModel):
    score_id: str
    patient_id: str
    score: float
    risk_level: str
    confidence: float
    model_version: str
    features_used: list[str]
    computed_at: str


class ScoreHistoryResponse(BaseModel):
    patient_id: str
    scores: list[ScoreResponse]
    total: int


class SHAPFeature(BaseModel):
    feature: str
    value: float
    shap_value: float
    direction: str  # "risk_increase" | "risk_decrease"


class SHAPExplanation(BaseModel):
    score_id: str
    patient_id: str
    score: float
    risk_level: str
    base_value: float
    features: list[SHAPFeature]
    generated_at: str


# ---------------------------------------------------------------------------
# In-memory store (placeholder)
# ---------------------------------------------------------------------------

_scores_db: dict[str, dict] = {}           # score_id -> score
_patient_scores: dict[str, list[str]] = {}  # patient_id -> [score_ids]

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post(
    "/scoring/compute/{patient_id}",
    response_model=ScoreResponse,
    status_code=status.HTTP_201_CREATED,
)
async def compute_score(
    patient_id: str,
    payload: ComputeScoreRequest,
    current_user: dict = Depends(get_current_user),
):
    """Calculer le score de risque pour un patient."""
    # TODO: load real ML model from S3 (settings.MODEL_S3_BUCKET)
    # Placeholder scoring logic using weighted average of available features
    features_used: list[str] = []
    raw_values: list[float] = []

    if payload.phq9_total is not None:
        features_used.append("phq9_total")
        raw_values.append(payload.phq9_total / 27.0 * 100)  # Normalize to 0-100

    if payload.sleep_hours is not None:
        features_used.append("sleep_hours")
        # Poor sleep (<5h or >10h) increases risk
        deviation = abs(payload.sleep_hours - 7.5) / 7.5
        raw_values.append(min(deviation * 100, 100))

    if payload.activity_minutes is not None:
        features_used.append("activity_minutes")
        # Less activity = more risk
        raw_values.append(max(0, 100 - payload.activity_minutes / 60 * 100))

    if payload.heart_rate_avg is not None:
        features_used.append("heart_rate_avg")
        deviation = abs(payload.heart_rate_avg - 70) / 70
        raw_values.append(min(deviation * 100, 100))

    if payload.hrv_avg is not None:
        features_used.append("hrv_avg")
        raw_values.append(max(0, 100 - payload.hrv_avg / 100 * 100))

    if payload.social_interaction_score is not None:
        features_used.append("social_interaction_score")
        raw_values.append(max(0, 100 - payload.social_interaction_score * 10))

    if not raw_values:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Au moins une feature est requise pour calculer le score",
        )

    score = round(sum(raw_values) / len(raw_values), 2)
    score = max(0, min(100, score))
    risk_level = _classify_risk(score)

    score_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    score_record = {
        "score_id": score_id,
        "patient_id": patient_id,
        "score": score,
        "risk_level": risk_level.value,
        "confidence": round(0.6 + len(raw_values) * 0.05, 2),  # Placeholder
        "model_version": "placeholder-v0.1.0",
        "features_used": features_used,
        "computed_at": now,
    }

    _scores_db[score_id] = score_record
    _patient_scores.setdefault(patient_id, []).append(score_id)

    # TODO: persist to PostgreSQL, trigger notification if risk >= moderate
    return ScoreResponse(**score_record)


@app.get("/scoring/latest/{patient_id}", response_model=ScoreResponse)
async def get_latest_score(
    patient_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Recuperer le dernier score d'un patient."""
    score_ids = _patient_scores.get(patient_id, [])
    if not score_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun score trouve pour ce patient",
        )

    latest = _scores_db[score_ids[-1]]
    return ScoreResponse(**latest)


@app.get("/scoring/history/{patient_id}", response_model=ScoreHistoryResponse)
async def get_score_history(
    patient_id: str,
    limit: int = Query(50, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    """Recuperer l'historique des scores d'un patient."""
    score_ids = _patient_scores.get(patient_id, [])
    scores = [ScoreResponse(**_scores_db[sid]) for sid in score_ids[-limit:]]

    return ScoreHistoryResponse(
        patient_id=patient_id,
        scores=scores,
        total=len(score_ids),
    )


@app.get("/scoring/explain/{score_id}", response_model=SHAPExplanation)
async def explain_score(
    score_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Obtenir l'explication SHAP d'un score."""
    score_record = _scores_db.get(score_id)
    if score_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Score introuvable",
        )

    # TODO: compute real SHAP values from stored model + features
    # Placeholder explanation
    features_explanation = []
    for i, feat in enumerate(score_record["features_used"]):
        shap_val = round((-1) ** i * (5.0 + i * 2.3), 2)  # Fake SHAP values
        features_explanation.append(
            SHAPFeature(
                feature=feat,
                value=0.0,  # TODO: store actual feature values
                shap_value=shap_val,
                direction="risk_increase" if shap_val > 0 else "risk_decrease",
            )
        )

    return SHAPExplanation(
        score_id=score_id,
        patient_id=score_record["patient_id"],
        score=score_record["score"],
        risk_level=score_record["risk_level"],
        base_value=50.0,  # TODO: real SHAP base value
        features=features_explanation,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.scoring.main:app", host="0.0.0.0", port=8003, reload=True)
