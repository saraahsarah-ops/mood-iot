"""Tests patient avec données riches — couvre les gros endpoints de calcul
(metrics, data-export RGPD, baseline) qui itèrent sur les données du patient.
"""
import uuid
from datetime import date, timedelta

from src.scoring.pipeline import ScoringPipeline
from src.shared.models import (
    Baseline,
    Consent,
    ConsentType,
    DailyAggregate,
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)

PATIENT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a2")
PATIENT_USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
D0 = date(2026, 6, 1)


async def _seed_rich(db):
    for i in range(3):
        db.add(DailyAggregate(
            patient_id=PATIENT_ID, date=D0 - timedelta(days=i),
            heart_rate_avg=70.0 + i, heart_rate_variability=40.0,
            sleep_duration_min=430.0, sleep_quality_score=70.0,
            step_count=6500, screen_time_min=300.0,
        ))
    for n, m, s in [("heart_rate_avg", 65.0, 5.0), ("sleep_duration_min", 460.0, 40.0),
                    ("step_count", 8000.0, 1500.0), ("screen_time_min", 250.0, 60.0)]:
        db.add(Baseline(patient_id=PATIENT_ID, metric_name=n,
                        mean_value=m, std_value=s, sample_count=30))
    db.add(Consent(patient_id=PATIENT_ID, consent_type=ConsentType.data_collection,
                   is_granted=True))
    db.add(Notification(
        patient_id=PATIENT_ID, type=NotificationType.system, level=1,
        channel=NotificationChannel.websocket, title="Info", body="corps",
        recipient_user_id=PATIENT_USER_ID, status=NotificationStatus.sent,
    ))
    await db.commit()
    pipe = ScoringPipeline()
    pipe._model = None
    pipe._use_heuristic = True
    await pipe.compute_score(str(PATIENT_ID), D0, db)


class TestPatientRich:
    async def test_metrics_avec_donnees(self, patient_psy_client, db_query):
        await _seed_rich(db_query)
        r = await patient_psy_client.get(f"/patients/{PATIENT_ID}/metrics")
        assert r.status_code == 200

    async def test_data_export_complet(self, patient_psy_client, db_query):
        await _seed_rich(db_query)
        r = await patient_psy_client.get(f"/patients/{PATIENT_ID}/data-export")
        assert r.status_code == 200

    async def test_baseline(self, patient_psy_client, db_query):
        await _seed_rich(db_query)
        r = await patient_psy_client.get(f"/patients/{PATIENT_ID}/baseline")
        assert r.status_code in (200, 404)
