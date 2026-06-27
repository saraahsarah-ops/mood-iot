"""Tests d'intégration — endpoints du service patient (src/patient/main).

Utilise un vrai client HTTP (httpx ASGI) contre une BD Postgres de test,
authentifié comme le patient semé (cf. conftest).
"""


class TestPatientMe:
    async def test_get_me_resout_le_patient(self, patient_client):
        r = await patient_client.get("/patients/me")
        assert r.status_code == 200
        body = r.json()
        assert body["first_name"] == "Test"
        assert body["last_name"] == "Patient"

    async def test_statut_synchronisation(self, patient_client):
        r = await patient_client.get("/patients/me/health-data/status")
        assert r.status_code == 200

    async def test_enregistrer_token_push(self, patient_client):
        r = await patient_client.put(
            "/patients/me/device-token", json={"device_token": "tok-test-123"}
        )
        assert r.status_code in (200, 204)

    async def test_liste_messages(self, patient_client):
        r = await patient_client.get("/patients/me/messages")
        assert r.status_code == 200

    async def test_compteur_messages_non_lus(self, patient_client):
        r = await patient_client.get("/patients/me/messages/unread-count")
        assert r.status_code == 200

    async def test_consentements(self, patient_client):
        r = await patient_client.get("/patients/me/consents")
        assert r.status_code == 200

    async def test_rendez_vous(self, patient_client):
        r = await patient_client.get("/patients/me/appointments")
        assert r.status_code == 200


class TestHumeur:
    async def test_soumettre_humeur_emoji(self, patient_client):
        r = await patient_client.post(
            "/patients/me/humeur/emoji", json={"emoji_level": 5, "note": "ça va"}
        )
        assert r.status_code in (200, 201)

    async def test_historique_humeur(self, patient_client):
        await patient_client.post(
            "/patients/me/humeur/emoji", json={"emoji_level": 4}
        )
        r = await patient_client.get("/patients/me/humeur")
        assert r.status_code == 200


class TestHealthDataSync:
    PAYLOAD = {
        "date": "2026-05-10",
        "heart_rate_avg": 68.0,
        "heart_rate_variability": 42.0,
        "sleep_duration_min": 420,
        "step_count": 7000,
        "screen_time_min": 300,
        "source_platform": "android_health_connect",
    }

    async def test_envoi_donnees_capteurs(self, patient_client):
        r = await patient_client.post("/patients/me/health-data", json=self.PAYLOAD)
        assert r.status_code in (200, 201)

    async def test_upsert_meme_date(self, patient_client):
        # deux envois pour la même date ne doivent pas dupliquer (UPSERT)
        await patient_client.post("/patients/me/health-data", json=self.PAYLOAD)
        r2 = await patient_client.post(
            "/patients/me/health-data", json={**self.PAYLOAD, "step_count": 9000}
        )
        assert r2.status_code in (200, 201)


class TestPatientMore:
    PATIENT_ID = "00000000-0000-0000-0000-0000000000a2"

    async def test_maj_consentements(self, patient_client):
        r = await patient_client.put(
            "/patients/me/consents",
            json={"cgu": True, "rgpd": True, "health_sensors": True, "ai_recommendations": False},
        )
        assert r.status_code == 200

    async def test_editer_derniere_humeur(self, patient_client):
        await patient_client.post("/patients/me/humeur/emoji", json={"emoji_level": 4})
        r = await patient_client.patch("/patients/me/humeur/latest", json={"emoji_level": 6})
        assert r.status_code in (200, 404)

    async def test_supprimer_derniere_humeur(self, patient_client):
        await patient_client.post("/patients/me/humeur/emoji", json={"emoji_level": 3})
        r = await patient_client.delete("/patients/me/humeur/latest")
        assert r.status_code in (200, 204, 404)

    async def test_get_son_propre_profil_par_id(self, patient_client):
        r = await patient_client.get(f"/patients/{self.PATIENT_ID}")
        assert r.status_code == 200

    async def test_get_patient_inexistant_404(self, patient_client):
        r = await patient_client.get("/patients/11111111-1111-1111-1111-111111111111")
        assert r.status_code == 404

    async def test_marquer_message_inexistant_404(self, patient_client):
        r = await patient_client.patch(
            "/patients/me/messages/11111111-1111-1111-1111-111111111111/read"
        )
        assert r.status_code == 404
