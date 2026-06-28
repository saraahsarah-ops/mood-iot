"""
Mood-IoT : Service ML Scoring (port 8003).
Calcul du score de risque via pipeline ML, historique, explications SHAP.
Connecte a PostgreSQL via SQLAlchemy async.
"""

import logging
import os
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, status, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession


from src.shared.config import settings
from src.shared.auth import get_current_user, require_role
from src.shared.database import get_db
from src.shared.models import (
    RiskScore, Patient, Baseline, DailyAggregate, PatientPsychiatrist,
)
from src.scoring.pipeline import get_pipeline

logger = logging.getLogger("mood_iot.scoring")


# ---------------------------------------------------------------------------
# Contrôle d'accès (anti-IDOR)
# ---------------------------------------------------------------------------
async def verify_patient_access(
    patient_id: str, current_user: dict, db: AsyncSession
) -> None:
    """
    Vérifie que `current_user` a le droit d'accéder aux données de `patient_id`.

    - patient   : uniquement ses propres données (Patient.user_id == user_id)
    - psychiatre : uniquement ses patients assignés (PatientPsychiatrist)
    - admin     : accès total

    Lève 403 sinon, 404 si le patient n'existe pas. Empêche les IDOR.
    """
    role = current_user.get("role")
    if role == "admin":
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

    # Rôle inconnu → refus par défaut
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acces refuse")


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
    allow_origins=settings.cors_origins_list,
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


class DeviationItem(BaseModel):
    """Déviation d'une métrique vs le baseline du patient (Z-score lisible)."""
    metric: str
    label: str
    sigma: float
    direction: str  # "below" | "above"
    notable: bool
    text: str


class SHAPExplanation(BaseModel):
    score_id: str
    patient_id: str
    score: float
    risk_level: str
    base_value: float
    features: list[SHAPFeature]
    # Couche 1 (cf. MODEL_DESIGN.md) : écarts au baseline individuel du patient.
    deviations: list[DeviationItem] = []
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


# ---------------------------------------------------------------------------
# Escalade des alertes (déléguée au service notification)
# ---------------------------------------------------------------------------

# Service notification (reseau interne Docker/K8s). Surchargé en test via env
# pour ne JAMAIS taper le vrai service (escalades reelles : emails/SMS).
NOTIFICATION_SERVICE_URL = os.environ.get(
    "NOTIFICATION_SERVICE_URL", "http://notification-service:8004"
)


async def _trigger_escalation(
    patient_id: str,
    score: float,
    alert_level: int,
    risk_score_id: str | None,
    top_features: list,
) -> None:
    """Fire-and-forget : declenche l'escalade COMPLETE (coaching patient,
    alerte temps reel + email + SMS au psychiatre, auto-teleconsult niveau 3)
    dans le service notification via son endpoint interne. Un echec ici ne doit
    jamais interrompre le calcul du score.
    """
    import httpx

    shap = [
        f.get("message", "")
        for f in (top_features or [])
        if isinstance(f, dict) and f.get("message")
    ]
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(
                f"{NOTIFICATION_SERVICE_URL}/notifications/internal/escalate",
                json={
                    "patient_id": patient_id,
                    "score": score,
                    "alert_level": alert_level,
                    "risk_score_id": risk_score_id,
                    "shap_explanations": shap,
                },
                headers={"X-Internal-Service": settings.INTERNAL_SERVICE_SECRET},
            )
    except Exception as exc:  # best-effort
        logger.warning("Escalade non declenchee pour %s : %s", patient_id, exc)


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
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Calculer le score de risque pour un patient via le pipeline ML."""

    # Anti-IDOR : seul le patient lui-même, son psychiatre, ou un admin.
    await verify_patient_access(patient_id, current_user, db)

    target_date = payload.target_date or date.today()
    pipeline = get_pipeline()

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

    # Creer une notification SEULEMENT pour le score du jour le plus recent
    # (pas pour les recomputes historiques)
    from datetime import timedelta as _td
    is_recent = target_date >= (date.today() - _td(days=1))
    if result.get("alert_level", 0) >= 0 and is_recent:
        # Déclenche l'escalade complète (coaching patient / alerte temps réel +
        # email + SMS psychiatre / auto-téléconsult niveau 3) — best-effort.
        await _trigger_escalation(
            patient_id=patient_id,
            score=result["score"],
            alert_level=result["alert_level"],
            risk_score_id=str(result["score_id"]),
            top_features=result.get("top_features", []),
        )

    # Audit log
    from src.shared.audit import log_action
    await log_action(
        db,
        user_id=current_user.get("user_id"),
        action="compute_score",
        resource="risk_score",
        resource_id=str(result["score_id"]),
        details={
            "patient_id": patient_id,
            "score": result["score"],
            "alert_level": result["alert_level"],
            "date": str(target_date),
        },
    )
    await db.commit()

    return ScoreResponse(
        score_id=str(result["score_id"]),
        patient_id=patient_id,
        date=str(target_date),
        score=result["score"],
        risk_level=_classify_risk(result["score"]),
        alert_level=result["alert_level"],
        confidence=result.get("confidence"),
        model_version=result.get("model_version", "heuristic-v1"),
        computed_at=datetime.now(timezone.utc).isoformat(),
    )


@app.post("/scoring/internal/compute/{patient_id}")
async def internal_compute_score(
    patient_id: str,
    payload: ComputeScoreRequest,
    db: AsyncSession = Depends(get_db),
    x_internal_service: str = Header(default=""),
):
    """
    Endpoint interne pour les appels inter-services (patient → scoring).

    Protégé par un secret partagé `INTERNAL_SERVICE_SECRET` passé en header
    `X-Internal-Service`. Sans secret valide → 403. Empêche le déclenchement
    externe de recalculs/alertes (l'ancien param était un query non validé).
    """
    expected = settings.INTERNAL_SERVICE_SECRET
    if not expected or x_internal_service != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acces interne refuse",
        )
    target_date = payload.target_date or date.today()
    pipeline = get_pipeline()

    result_check = await db.execute(
        select(Patient).where(Patient.id == patient_id)
    )
    if result_check.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Patient introuvable")

    # Check baselines exist, auto-compute if missing
    baseline_check = await db.execute(
        select(Baseline).where(Baseline.patient_id == patient_id)
    )
    if not baseline_check.scalars().first():
        logger.info("Auto-computing baselines for patient %s", patient_id)
        from src.scoring.main import _compute_and_store_baselines
        await _compute_and_store_baselines(patient_id, db)

    try:
        result = await pipeline.compute_score(patient_id, target_date, db)
    except ValueError as e:
        logger.warning("Scoring failed for %s: %s", patient_id, e)
        return {"status": "skipped", "reason": str(e)}

    from datetime import timedelta as _td
    is_recent = target_date >= (date.today() - _td(days=1))
    if result.get("alert_level", 0) >= 0 and is_recent:
        # Idem flux interne (déclenché après sync des données du patient).
        await _trigger_escalation(
            patient_id=patient_id,
            score=result["score"],
            alert_level=result["alert_level"],
            risk_score_id=str(result["score_id"]),
            top_features=result.get("top_features", []),
        )

    return {
        "status": "scored",
        "patient_id": patient_id,
        "score": result["score"],
        "alert_level": result["alert_level"],
    }


@app.get("/scoring/latest/{patient_id}", response_model=ScoreResponse)
async def get_latest_score(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Recuperer le dernier score d'un patient."""
    await verify_patient_access(patient_id, current_user, db)
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
    await verify_patient_access(patient_id, current_user, db)
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

    # Anti-IDOR : vérifier l'accès au patient propriétaire de ce score.
    await verify_patient_access(str(explanation["patient_id"]), current_user, db)

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
        deviations=[
            DeviationItem(**d) for d in explanation.get("deviations", [])
        ],
        summary_fr=explanation.get("summary_fr", ""),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@app.post("/scoring/baseline/{patient_id}")
async def trigger_baseline(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("psychiatre")),
):
    """Recalculer les baselines pour un patient a partir de ses daily_aggregates."""
    return await _compute_and_store_baselines(patient_id, db)


async def _compute_and_store_baselines(patient_id: str, db: AsyncSession) -> dict:
    """Calcule mean/std de chaque metrique sur les daily_aggregates disponibles."""
    from sqlalchemy import func as sqla_func

    metrics_cols = {
        "heart_rate_avg": DailyAggregate.heart_rate_avg,
        "heart_rate_variability": DailyAggregate.heart_rate_variability,
        "sleep_duration_min": DailyAggregate.sleep_duration_min,
        "sleep_quality_score": DailyAggregate.sleep_quality_score,
        "step_count": DailyAggregate.step_count,
        "gps_radius_km": DailyAggregate.gps_radius_km,
        "screen_time_min": DailyAggregate.screen_time_min,
        "call_count": DailyAggregate.call_count,
    }

    # Get date range
    range_stmt = select(
        sqla_func.min(DailyAggregate.date),
        sqla_func.max(DailyAggregate.date),
        sqla_func.count(DailyAggregate.id),
    ).where(DailyAggregate.patient_id == patient_id)
    range_result = await db.execute(range_stmt)
    row = range_result.one()
    window_start, window_end, sample_count = row[0], row[1], row[2]

    if not sample_count or sample_count < 3:
        return {
            "status": "insufficient_data",
            "patient_id": patient_id,
            "sample_count": sample_count or 0,
            "message": "Au moins 3 jours de donnees sont necessaires",
        }

    computed = []
    for metric_name, col in metrics_cols.items():
        stmt = select(
            sqla_func.avg(col),
            sqla_func.stddev_pop(col),
            sqla_func.min(col),
            sqla_func.max(col),
        ).where(
            and_(
                DailyAggregate.patient_id == patient_id,
                col.isnot(None),
            )
        )
        result = await db.execute(stmt)
        stats = result.one()
        mean_val, std_val, min_val, max_val = stats[0], stats[1], stats[2], stats[3]

        if mean_val is None:
            continue

        std_val = max(float(std_val or 0), 1e-6)

        # UPSERT baseline
        existing = await db.execute(
            select(Baseline).where(
                and_(
                    Baseline.patient_id == patient_id,
                    Baseline.metric_name == metric_name,
                )
            )
        )
        baseline = existing.scalars().first()
        if baseline:
            baseline.mean_value = float(mean_val)
            baseline.std_value = std_val
            baseline.min_value = float(min_val) if min_val else None
            baseline.max_value = float(max_val) if max_val else None
            baseline.sample_count = sample_count
            baseline.window_start = window_start
            baseline.window_end = window_end
        else:
            baseline = Baseline(
                patient_id=patient_id,
                metric_name=metric_name,
                mean_value=float(mean_val),
                std_value=std_val,
                min_value=float(min_val) if min_val else None,
                max_value=float(max_val) if max_val else None,
                sample_count=sample_count,
                window_start=window_start,
                window_end=window_end,
            )
            db.add(baseline)

        computed.append(metric_name)

    await db.commit()

    return {
        "status": "completed",
        "patient_id": patient_id,
        "metrics_computed": computed,
        "sample_count": sample_count,
        "window": f"{window_start} -> {window_end}",
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.scoring.main:app", host="0.0.0.0", port=8003, reload=True)
