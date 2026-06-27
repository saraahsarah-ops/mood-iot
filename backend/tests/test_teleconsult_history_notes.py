"""Tests teleconsult — liste des notes d'une session + historique patient.

Couvre list_session_notes (GET notes) et get_patient_history (téléconsults +
notes + messages), non couverts par test_teleconsult_api.
"""
import uuid

PATIENT_ID = "00000000-0000-0000-0000-0000000000a2"
PSY_USER_ID = "00000000-0000-0000-0000-0000000000b1"

SESSION = {
    "patient_id": PATIENT_ID,
    "psychiatre_id": PSY_USER_ID,
    "scheduled_at": "2026-07-02T10:00:00",
    "duration_minutes": 30,
    "reason": "Suivi",
}


class TestSessionNotes:
    async def test_lister_notes(self, teleconsult_psy_client):
        c = await teleconsult_psy_client.post("/teleconsult/sessions", json=SESSION)
        sid = c.json()["id"]
        await teleconsult_psy_client.post(
            f"/teleconsult/sessions/{sid}/notes",
            json={"content": "Patient stable", "note_type": "observation"},
        )
        r = await teleconsult_psy_client.get(f"/teleconsult/sessions/{sid}/notes")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    async def test_lister_notes_session_introuvable(self, teleconsult_psy_client):
        r = await teleconsult_psy_client.get(
            f"/teleconsult/sessions/{uuid.uuid4()}/notes"
        )
        assert r.status_code == 404


class TestHistorique:
    async def test_historique_patient(self, teleconsult_psy_client):
        # Session + note + message -> remplit les trois sections de l'historique.
        c = await teleconsult_psy_client.post("/teleconsult/sessions", json=SESSION)
        sid = c.json()["id"]
        await teleconsult_psy_client.post(
            f"/teleconsult/sessions/{sid}/notes",
            json={"content": "Note test", "note_type": "observation"},
        )
        await teleconsult_psy_client.post(
            f"/teleconsult/messages/{PATIENT_ID}", json={"content": "Bonjour"}
        )
        r = await teleconsult_psy_client.get(f"/teleconsult/history/{PATIENT_ID}")
        assert r.status_code == 200
        body = r.json()
        assert "teleconsults" in body
        assert "notes" in body
        assert "messages" in body
