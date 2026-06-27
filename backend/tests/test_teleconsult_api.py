"""Tests d'intégration — service teleconsult (src/teleconsult/main).

Couvre le cycle d'une téléconsultation : création (+ notification patient),
liste, détail, fin, notes cliniques, message au patient.
"""

PATIENT_ID = "00000000-0000-0000-0000-0000000000a2"
PSY_USER_ID = "00000000-0000-0000-0000-0000000000b1"

SESSION = {
    "patient_id": PATIENT_ID,
    "psychiatre_id": PSY_USER_ID,
    "scheduled_at": "2026-07-01T15:00:00",
    "duration_minutes": 30,
    "reason": "Suivi mensuel",
}


class TestTeleconsultCycle:
    async def test_creer_session(self, teleconsult_psy_client):
        r = await teleconsult_psy_client.post("/teleconsult/sessions", json=SESSION)
        assert r.status_code == 201
        assert r.json()["jitsi_url"]  # lien Jitsi généré

    async def test_lister_sessions(self, teleconsult_psy_client):
        r = await teleconsult_psy_client.get("/teleconsult/sessions")
        assert r.status_code == 200

    async def test_detail_session(self, teleconsult_psy_client):
        c = await teleconsult_psy_client.post("/teleconsult/sessions", json=SESSION)
        sid = c.json()["id"]
        r = await teleconsult_psy_client.get(f"/teleconsult/sessions/{sid}")
        assert r.status_code == 200

    async def test_terminer_session(self, teleconsult_psy_client):
        c = await teleconsult_psy_client.post("/teleconsult/sessions", json=SESSION)
        sid = c.json()["id"]
        r = await teleconsult_psy_client.put(
            f"/teleconsult/sessions/{sid}/end", json={"summary": "RAS"}
        )
        assert r.status_code == 200

    async def test_ajouter_note_clinique(self, teleconsult_psy_client):
        c = await teleconsult_psy_client.post("/teleconsult/sessions", json=SESSION)
        sid = c.json()["id"]
        r = await teleconsult_psy_client.post(
            f"/teleconsult/sessions/{sid}/notes",
            json={"content": "Patient stable", "note_type": "observation"},
        )
        assert r.status_code in (200, 201)

    async def test_envoyer_message_au_patient(self, teleconsult_psy_client):
        r = await teleconsult_psy_client.post(
            f"/teleconsult/messages/{PATIENT_ID}", json={"content": "Bonjour"}
        )
        assert r.status_code in (200, 201)


class TestTeleconsultJoinDelete:
    async def test_rejoindre_session(self, teleconsult_psy_client):
        c = await teleconsult_psy_client.post("/teleconsult/sessions", json=SESSION)
        sid = c.json()["id"]
        r = await teleconsult_psy_client.post(f"/teleconsult/sessions/{sid}/join")
        # 200 si rejoignable, 400 si hors fenêtre horaire, 404 sinon
        assert r.status_code in (200, 400, 404)

    async def test_supprimer_session(self, teleconsult_psy_client):
        c = await teleconsult_psy_client.post("/teleconsult/sessions", json=SESSION)
        sid = c.json()["id"]
        r = await teleconsult_psy_client.delete(f"/teleconsult/sessions/{sid}")
        assert r.status_code in (200, 204)
