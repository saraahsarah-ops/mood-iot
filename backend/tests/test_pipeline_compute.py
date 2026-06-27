"""Test d'intégration — pipeline de scoring complet (compute_score + explain).

Sème un agrégat quotidien + des baselines pour le patient, puis exécute
compute_score (z-scores -> feature vector -> prédiction -> persistance) et
explain_score. Couvre les fonctions async DB du pipeline.
"""
import uuid
from datetime import date

import pytest

from src.scoring.pipeline import ScoringPipeline
from src.shared.models import Baseline, DailyAggregate

PATIENT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a2")
TARGET = date(2026, 6, 1)


@pytest.fixture
def heuristic_pipeline():
    p = ScoringPipeline()
    p._model = None
    p._use_heuristic = True
    return p


async def _seed_aggregate_and_baselines(session):
    session.add(
        DailyAggregate(
            patient_id=PATIENT_ID,
            date=TARGET,
            heart_rate_avg=72.0,
            sleep_duration_min=430.0,
            step_count=6500,
            screen_time_min=320.0,
        )
    )
    for name, mean, std in [
        ("heart_rate_avg", 65.0, 5.0),
        ("sleep_duration_min", 460.0, 40.0),
        ("step_count", 8000.0, 1500.0),
        ("screen_time_min", 250.0, 60.0),
    ]:
        session.add(
            Baseline(
                patient_id=PATIENT_ID,
                metric_name=name,
                mean_value=mean,
                std_value=std,
                sample_count=30,
            )
        )
    await session.commit()


class TestComputeScore:
    async def test_compute_score_complet(self, heuristic_pipeline, db_query):
        await _seed_aggregate_and_baselines(db_query)

        result = await heuristic_pipeline.compute_score(str(PATIENT_ID), TARGET, db_query)

        assert 0 <= result["score"] <= 100
        assert result["alert_level"] in (0, 1, 2, 3)
        assert result["score_id"]
        assert "shap_explanations" in result

    async def test_explain_score(self, heuristic_pipeline, db_query):
        await _seed_aggregate_and_baselines(db_query)
        result = await heuristic_pipeline.compute_score(str(PATIENT_ID), TARGET, db_query)

        explanation = await heuristic_pipeline.explain_score(result["score_id"], db_query)
        assert explanation is not None

    async def test_sans_agregat_leve_valueerror(self, heuristic_pipeline, db_query):
        # Aucun agrégat semé pour cette date -> ValueError attendu.
        with pytest.raises(ValueError):
            await heuristic_pipeline.compute_score(
                str(PATIENT_ID), date(2025, 1, 1), db_query
            )
