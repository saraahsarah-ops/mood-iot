"""Tests d'intégration — POST /scoring/compute (pipeline ML via HTTP).

Le pipeline pur est déjà testé (test_pipeline_compute) ; ici on couvre le
*endpoint* : calcul, ré-utilisation d'un score existant, et 422 sans données.
"""
import uuid
from datetime import date, timedelta

from src.shared.models import Baseline, DailyAggregate

PATIENT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a2")
D0 = date(2026, 6, 1)


async def _seed_metrics(db):
    """Sème agrégats journaliers + baselines (requis par compute_score)."""
    for i in range(3):
        db.add(
            DailyAggregate(
                patient_id=PATIENT_ID,
                date=D0 - timedelta(days=i),
                heart_rate_avg=70.0 + i,
                heart_rate_variability=40.0,
                sleep_duration_min=430.0,
                sleep_quality_score=70.0,
                step_count=6500,
                screen_time_min=300.0,
            )
        )
    for name, mean, std in [
        ("heart_rate_avg", 65.0, 5.0),
        ("sleep_duration_min", 460.0, 40.0),
        ("step_count", 8000.0, 1500.0),
        ("screen_time_min", 250.0, 60.0),
    ]:
        db.add(
            Baseline(
                patient_id=PATIENT_ID,
                metric_name=name,
                mean_value=mean,
                std_value=std,
                sample_count=30,
            )
        )
    await db.commit()


class TestScoringComputeApi:
    async def test_calculer_score(self, scoring_psy_client, db_query):
        await _seed_metrics(db_query)
        r = await scoring_psy_client.post(
            f"/scoring/compute/{PATIENT_ID}",
            json={"target_date": "2026-06-01", "force_recompute": True},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["patient_id"] == str(PATIENT_ID)
        assert 0 <= body["score"] <= 100

    async def test_reutilise_score_existant(self, scoring_psy_client, db_query):
        # 1er calcul crée le score ; 2e sans force_recompute le ré-utilise.
        await _seed_metrics(db_query)
        first = await scoring_psy_client.post(
            f"/scoring/compute/{PATIENT_ID}",
            json={"target_date": "2026-06-01", "force_recompute": True},
        )
        assert first.status_code == 201
        again = await scoring_psy_client.post(
            f"/scoring/compute/{PATIENT_ID}",
            json={"target_date": "2026-06-01", "force_recompute": False},
        )
        assert again.status_code == 201
        assert again.json()["score_id"] == first.json()["score_id"]

    async def test_sans_donnees_422(self, scoring_psy_client):
        # Aucun agrégat -> le pipeline lève ValueError -> 422.
        r = await scoring_psy_client.post(
            f"/scoring/compute/{PATIENT_ID}",
            json={"target_date": "2026-06-01", "force_recompute": True},
        )
        assert r.status_code == 422
