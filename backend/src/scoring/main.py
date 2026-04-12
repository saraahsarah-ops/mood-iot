"""
Mood-IoT : Service ML Scoring (port 8003).
Calcul du score de risque via pipeline ML, historique, explications SHAP.
Connecte a PostgreSQL via SQLAlchemy async.
"""

import logging
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.config import settings
from src.shared.auth import get_current_user, require_role
from src.shared.database import get_db
from src.shared.models import RiskScore, FeatureVector, Patient
from src.scoring.pipeline import get_pipeline

logger = logging.getLogger("mood_iot.scoring")

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Mood-IoT Scoring Service",
    version="2.0.0",
    description="Service de scoring ML — pipeline reel avec PostgreSQL",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Seuils : 40 / 60 / 80
# ---------------------------------------------------------------------------

THRESHOLDS = settings.scoring_thresholds_tuple  # (40, 60, 80)


class RiskLevel(str):
    low = "low"              # 0 - 39
    moderate = "moderate"    # 40 - 59
    high = "high"            # 60 - 79
    critical = "critical"    # 80 - 100


def _classify_risk(score: float) -> str:
    if score < THRESHOLDS[0]:
        return "low"
    elif score < THRESHOLDS[1]:
        return "moderate"
    elif score < THRESHOLDS[2]:
        return "high"
    else:
        return "critical"


# ---------------------------------------------------------------------------
# Modeles Pydantic
# ---------------------------------------------------------------------------


class ComputeScoreRequest(BaseModel):
    target_date: Optional[date] = Field(None, description="Date cible (defaut: aujourd'hui)")
    force_recompute: bool = False


class ScoreResponse(BaseModel):
    score_id: str
    patient_id: str
    date: str
    score: float
    risk_level: str
    alert_level: int
    confidence: Optional[float]
    model_version: str
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
    description_fr: str


class SHAPExplanation(BaseModel):
    score_id: str
    patient_id: str
    score: float
    risk_level: str
    base_value: float
    features: list[SHAPFeature]
    summary_fr: str
    generated_at: str


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def on_startup():
    logger.info("Service ML Scoring demarre sur le port 8003")
    logger.info("Seuils d'alerte : %s", THRESHOLDS)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
@app.get("/scoring/health")
async def health():
    return {"status": "healthy", "service": "scoring"}


@app.post(
    "/scoring/compute/{patient_id}",
    response_model=ScoreResponse,
    status_code=status.HTTP_201_CREATED,
)
async def compute_score(
    patient_id: str,
    payload: ComputeScoreRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Calculer le score de risque pour un patient via le pipeline ML."""

    target_date = payload.target_date or date.today()
    pipeline = get_pipeline()

    # Verifier que le patient existe
    result = await db.execute(
        select(Patient).where(Patient.id == patient_id)
    )
    patient = result.scalar_one_or_none()
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient introuvable",
        )

    # Verifier si un score existe deja pour cette date
    if not payload.force_recompute:
        existing = await db.execute(
            select(RiskScore).where(
                and_(
                    RiskScore.patient_id == patient_id,
                    RiskScore.date == target_date,
                )
            )
        )
        existing_score = existing.scalar_one_or_none()
        if existing_score is not None:
            return ScoreResponse(
                score_id=str(existing_score.id),
                patient_id=str(existing_score.patient_id),
                date=str(existing_score.date),
                score=existing_score.score,
                risk_level=_classify_risk(existing_score.score),
                alert_level=existing_score.alert_level,
                confidence=existing_score.confidence,
                model_version=existing_score.model_version,
                computed_at=existing_score.created_at.isoformat(),
            )

    # Executer le pipeline ML complet
    try:
        result = await pipeline.compute_score(patient_id, target_date, db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    # Declencher l'escalade si alert_level >= 1
    if result.get("alert_level", 0) >= 1:
        try:
            from src.notification.escalation import EscalationEngine
            engine = EscalationEngine()
            await engine.process_alert(
                patient_id=patient_id,
                score=result["score"],
                alert_level=result["alert_level"],
                risk_score_id=str(result["risk_score_id"]),
                shap_explanations=result.get("shap_explanations", []),
                db=db,
            )
            logger.info(
                "Escalade declenchee pour patient %s (niveau %d, score %.1f)",
                patient_id, result["alert_level"], result["score"],
            )
        except Exception:
            logger.exception("Erreur lors de l'escalade pour patient %s", patient_id)

    return ScoreResponse(
        score_id=str(result["risk_score_id"]),
        patient_id=patient_id,
        date=str(target_date),
        score=result["score"],
        risk_level=_classify_risk(result["score"]),
        alert_level=result["alert_level"],
        confidence=result.get("confidence"),
        model_version=result.get("model_version", "heuristic-v1"),
        computed_at=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/scoring/latest/{patient_id}", response_model=ScoreResponse)
async def get_latest_score(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Recuperer le dernier score d'un patient."""
    result = await db.execute(
        select(RiskScore)
        .where(RiskScore.patient_id == patient_id)
        .order_by(RiskScore.created_at.desc())
        .limit(1)
    )
    score = result.scalar_one_or_none()

    if score is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun score trouve pour ce patient",
        )

    return ScoreResponse(
        score_id=str(score.id),
        patient_id=str(score.patient_id),
        date=str(score.date),
        score=score.score,
        risk_level=_classify_risk(score.score),
        alert_level=score.alert_level,
        confidence=score.confidence,
        model_version=score.model_version,
        computed_at=score.created_at.isoformat(),
    )


@app.get("/scoring/history/{patient_id}", response_model=ScoreHistoryResponse)
async def get_score_history(
    patient_id: str,
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Recuperer l'historique des scores d'un patient."""
    query = select(RiskScore).where(RiskScore.patient_id == patient_id)

    if from_date:
        query = query.where(RiskScore.date >= from_date)
    if to_date:
        query = query.where(RiskScore.date <= to_date)

    query = query.order_by(RiskScore.date.desc()).limit(limit)
    result = await db.execute(query)
    rows = result.scalars().all()

    # Compter le total sans limit
    count_query = select(RiskScore.id).where(RiskScore.patient_id == patient_id)
    if from_date:
        count_query = count_query.where(RiskScore.date >= from_date)
    if to_date:
        count_query = count_query.where(RiskScore.date <= to_date)
    count_result = await db.execute(count_query)
    total = len(count_result.all())

    scores = [
        ScoreResponse(
            score_id=str(s.id),
            patient_id=str(s.patient_id),
            date=str(s.date),
            score=s.score,
            risk_level=_classify_risk(s.score),
            alert_level=s.alert_level,
            confidence=s.confidence,
            model_version=s.model_version,
            computed_at=s.created_at.isoformat(),
        )
        for s in rows
    ]

    return ScoreHistoryResponse(
        patient_id=patient_id,
        scores=scores,
        total=total,
    )


@app.get("/scoring/explain/{score_id}", response_model=SHAPExplanation)
async def explain_score(
    score_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Obtenir l'explication SHAP d'un score."""
    pipeline = get_pipeline()

    try:
        explanation = await pipeline.explain_score(score_id, db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    features = []
    for feat in explanation.get("features", []):
        features.append(
            SHAPFeature(
                feature=feat["feature"],
                value=feat.get("value", 0.0),
                shap_value=feat.get("shap_value", 0.0),
                direction="risk_increase" if feat.get("shap_value", 0) > 0 else "risk_decrease",
                description_fr=feat.get("description_fr", ""),
            )
        )

    return SHAPExplanation(
        score_id=score_id,
        patient_id=str(explanation["patient_id"]),
        score=explanation["score"],
        risk_level=_classify_risk(explanation["score"]),
        base_value=explanation.get("base_value", 50.0),
        features=features,
        summary_fr=explanation.get("summary_fr", ""),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@app.post("/scoring/baseline/{patient_id}")
async def trigger_baseline(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("psychiatre")),
):
    """Declencher le recalcul des baselines pour un patient (TODO: implementation complete)."""
    # TODO Phase 3 : recalcul des baselines a partir des 14 derniers jours
    return {
        "status": "accepted",
        "patient_id": patient_id,
        "message": "Recalcul des baselines programme (TODO)",
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.scoring.main:app", host="0.0.0.0", port=8003, reload=True)
