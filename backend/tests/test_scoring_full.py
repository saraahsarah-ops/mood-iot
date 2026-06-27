"""Tests d'intégration scoring AVEC données — endpoints latest/explain/history.

Sème un agrégat + baselines, calcule un score réel via le pipeline, puis
interroge les endpoints du service scoring (psychiatre lié au patient).
"""
import uuid
from datetime import date

import pytest

from src.scoring.pipeline import ScoringPipeline
from src.shared.models import Baseline, DailyAggregate

PATIENT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a2")
TARGET = date(2026, 6, 1)


async def _seed_score(db):
    db.add(
        DailyAggregate(
            patient_id=PATIENT_ID, date=TARGET, heart_rate_avg=72.0,
            sleep_duration_min=430.0, step_count=6500, screen_time_min=320.0,
        )
    )
    for name, mean, std in [
        ("heart_rate_avg", 65.0, 5.0),
        ("sleep_duration_min", 460.0, 40.0),
        ("step_count", 8000.0, 1500.0),
        ("screen_time_min", 250.0, 60.0),
    ]:
        db.add(Baseline(patient_id=PATIENT_ID, metric_name=name,
                        mean_value=mean, std_value=std, sample_count=30))
    await db.commit()
    pipe = ScoringPipeline()
    pipe._model = None
    pipe._use_heuristic = True
    return await pipe.compute_score(str(PATIENT_ID), TARGET, db)


class TestScoringEndpointsAvecDonnees:
    async def test_latest_retourne_le_score(self, scoring_psy_client, db_query):
        await _seed_score(db_query)
        r = await scoring_psy_client.get(f"/scoring/latest/{PATIENT_ID}")
        assert r.status_code == 200

    async def test_explain_retourne_les_facteurs(self, scoring_psy_client, db_query):
        res = await _seed_score(db_query)
        r = await scoring_psy_client.get(f"/scoring/explain/{res['score_id']}")
        assert r.status_code == 200

    async def test_history_contient_le_score(self, scoring_psy_client, db_query):
        await _seed_score(db_query)
        r = await scoring_psy_client.get(f"/scoring/history/{PATIENT_ID}")
        assert r.status_code == 200
        body = r.json()
        assert body.get("total", 0) >= 1 or len(body.get("scores", [])) >= 1
