"""Tests d'intégration — patient/main : sync santé (côté patient) + messagerie.

Couvre la branche `role == patient` de health-data (anti-IDOR mobile), le batch,
et la lecture/marquage des messages reçus par le patient.
"""
import uuid

from src.shared.models import Message

PATIENT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a2")
PATIENT_USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
PSY_USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000b1")

HEALTH = {
    "date": "2026-06-10",
    "heart_rate_avg": 70.0,
    "sleep_duration_min": 420.0,
    "step_count": 6000,
    "screen_time_min": 200.0,
    "source_platform": "android_health_connect",
}


async def _seed_message(db):
    """Sème un message du psychiatre vers le patient (content auto-chiffré)."""
    m = Message(
        sender_id=PSY_USER_ID,
        recipient_id=PATIENT_USER_ID,
        content="Bonjour, comment allez-vous ?",
    )
    db.add(m)
    await db.commit()
    return m.id


class TestHealthDataSyncPatient:
    async def test_sync_simple(self, patient_client):
        r = await patient_client.post(
            f"/patients/{PATIENT_ID}/health-data", json=HEALTH
        )
        assert r.status_code == 201

    async def test_sync_plateforme_invalide_422(self, patient_client):
        r = await patient_client.post(
            f"/patients/{PATIENT_ID}/health-data",
            json={**HEALTH, "source_platform": "garmin"},
        )
        assert r.status_code == 422

    async def test_sync_autre_patient_403(self, patient_client):
        r = await patient_client.post(
            f"/patients/{uuid.uuid4()}/health-data", json=HEALTH
        )
        assert r.status_code == 403

    async def test_batch(self, patient_client):
        r = await patient_client.post(
            f"/patients/{PATIENT_ID}/health-data/batch",
            json=[HEALTH, {**HEALTH, "date": "2026-06-11"}],
        )
        assert r.status_code == 201
        assert r.json()["synced_count"] == 2

    async def test_batch_trop_grand_422(self, patient_client):
        big = [{**HEALTH, "date": f"2026-03-{(i % 28) + 1:02d}"} for i in range(91)]
        r = await patient_client.post(
            f"/patients/{PATIENT_ID}/health-data/batch", json=big
        )
        assert r.status_code == 422


class TestMessagerieMobile:
    async def test_lire_message(self, patient_client, db_query):
        mid = await _seed_message(db_query)
        r = await patient_client.get(f"/patients/me/messages/{mid}")
        assert r.status_code == 200
        assert r.json()["content"] == "Bonjour, comment allez-vous ?"

    async def test_message_introuvable_404(self, patient_client):
        r = await patient_client.get(f"/patients/me/messages/{uuid.uuid4()}")
        assert r.status_code == 404

    async def test_marquer_lu(self, patient_client, db_query):
        mid = await _seed_message(db_query)
        r = await patient_client.patch(f"/patients/me/messages/{mid}/read")
        assert r.status_code == 200
        assert r.json()["read_at"] is not None

    async def test_marquer_lu_introuvable_404(self, patient_client):
        r = await patient_client.patch(f"/patients/me/messages/{uuid.uuid4()}/read")
        assert r.status_code == 404
