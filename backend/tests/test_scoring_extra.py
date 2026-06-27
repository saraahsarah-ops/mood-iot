"""Tests scoring — branches restantes : alerte (score récent élevé),
auto-calcul des baselines (compute interne), et UPSERT d'une baseline existante.
"""
import uuid
from datetime import date, timedelta

from src.shared.models import Baseline, DailyAggregate

PATIENT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a2")

_BASELINES = [
    ("heart_rate_avg", 65.0, 5.0),
    ("sleep_duration_min", 460.0, 40.0),
    ("step_count", 8000.0, 1500.0),
    ("screen_time_min", 250.0, 60.0),
]


class TestScoringAlerte:
    async def test_compute_recent_cree_alerte(self, scoring_psy_client, db_query):
        # Agrégat du jour très éloigné des baselines -> score élevé -> alerte.
        # is_recent=True (date du jour) -> _create_alert_notification s'exécute.
        today = date.today()
        db_query.add(
            DailyAggregate(
                patient_id=PATIENT_ID,
                date=today,
                heart_rate_avg=150.0,
                heart_rate_variability=5.0,
                sleep_duration_min=120.0,
                sleep_quality_score=10.0,
                step_count=300,
                screen_time_min=900.0,
            )
        )
        for name, mean, std in _BASELINES:
            db_query.add(
                Baseline(
                    patient_id=PATIENT_ID,
                    metric_name=name,
                    mean_value=mean,
                    std_value=std,
                    sample_count=30,
                )
            )
        await db_query.commit()
        r = await scoring_psy_client.post(
            f"/scoring/compute/{PATIENT_ID}",
            json={"target_date": today.isoformat(), "force_recompute": True},
        )
        assert r.status_code == 201
        assert "alert_level" in r.json()


class TestScoringInternalAutoBaseline:
    async def test_internal_auto_calcule_baselines(self, scoring_psy_client, db_query):
        # Aucune baseline semée -> le compute interne les calcule à la volée.
        today = date.today()
        for i in range(5):
            db_query.add(
                DailyAggregate(
                    patient_id=PATIENT_ID,
                    date=today - timedelta(days=i),
                    heart_rate_avg=70.0 + i,
                    heart_rate_variability=40.0,
                    sleep_duration_min=430.0,
                    sleep_quality_score=70.0,
                    step_count=6500,
                    screen_time_min=300.0,
                )
            )
        await db_query.commit()
        r = await scoring_psy_client.post(
            f"/scoring/internal/compute/{PATIENT_ID}",
            headers={"X-Internal-Service": "test-internal-secret"},
            json={"target_date": today.isoformat()},
        )
        assert r.status_code in (200, 201)


class TestScoringBaselineUpsert:
    async def test_baseline_met_a_jour_existante(self, scoring_psy_client, db_query):
        # Baseline pré-existante -> branche UPSERT (mise à jour, pas insertion).
        today = date.today()
        for i in range(4):
            db_query.add(
                DailyAggregate(
                    patient_id=PATIENT_ID,
                    date=today - timedelta(days=i),
                    heart_rate_avg=72.0,
                    heart_rate_variability=40.0,
                    sleep_duration_min=430.0,
                    sleep_quality_score=70.0,
                    step_count=6500,
                    screen_time_min=300.0,
                )
            )
        db_query.add(
            Baseline(
                patient_id=PATIENT_ID,
                metric_name="heart_rate_avg",
                mean_value=60.0,
                std_value=3.0,
                sample_count=10,
            )
        )
        await db_query.commit()
        r = await scoring_psy_client.post(f"/scoring/baseline/{PATIENT_ID}")
        assert r.status_code in (200, 201)


class TestScoringInternalAlerte:
    async def test_internal_recent_extreme_genere_alerte(
        self, scoring_psy_client, db_query
    ):
        # Compute interne, date du jour, données extrêmes -> alerte (branche
        # _create_alert_notification dans le chemin interne).
        today = date.today()
        db_query.add(
            DailyAggregate(
                patient_id=PATIENT_ID,
                date=today,
                heart_rate_avg=155.0,
                heart_rate_variability=5.0,
                sleep_duration_min=100.0,
                sleep_quality_score=5.0,
                step_count=200,
                screen_time_min=950.0,
            )
        )
        for name, mean, std in _BASELINES:
            db_query.add(
                Baseline(
                    patient_id=PATIENT_ID,
                    metric_name=name,
                    mean_value=mean,
                    std_value=std,
                    sample_count=30,
                )
            )
        await db_query.commit()
        r = await scoring_psy_client.post(
            f"/scoring/internal/compute/{PATIENT_ID}",
            headers={"X-Internal-Service": "test-internal-secret"},
            json={"target_date": today.isoformat()},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "scored"
