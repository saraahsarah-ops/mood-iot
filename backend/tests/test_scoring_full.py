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


from datetime import timedelta  # noqa: E402


class TestScoringBaselineEtInterne:
    async def _seed_aggs(self, db):
        for i in range(5):
            db.add(DailyAggregate(
                patient_id=PATIENT_ID, date=TARGET - timedelta(days=i),
                heart_rate_avg=70.0 + i, sleep_duration_min=430.0,
                step_count=6500, screen_time_min=300.0,
            ))
        await db.commit()

    async def test_baseline_trigger(self, scoring_psy_client, db_query):
        await self._seed_aggs(db_query)
        r = await scoring_psy_client.post(f"/scoring/baseline/{PATIENT_ID}")
        assert r.status_code in (200, 201)

    async def test_internal_compute_ok(self, scoring_psy_client, db_query):
        await _seed_score(db_query)  # agrégat + baselines
        r = await scoring_psy_client.post(
            f"/scoring/internal/compute/{PATIENT_ID}",
            headers={"X-Internal-Service": "test-internal-secret"},
            json={"target_date": TARGET.isoformat()},
        )
        assert r.status_code in (200, 201)

    async def test_internal_compute_mauvais_secret_403(self, scoring_psy_client):
        r = await scoring_psy_client.post(
            f"/scoring/internal/compute/{PATIENT_ID}",
            headers={"X-Internal-Service": "mauvais-secret"},
            json={"target_date": TARGET.isoformat()},
        )
        assert r.status_code == 403
