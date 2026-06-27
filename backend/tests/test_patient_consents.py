"""Tests patient — batch capteurs, préférences notif, consentements (médecin + RGPD)."""

PATIENT_ID = "00000000-0000-0000-0000-0000000000a2"


class TestBatchEtPrefs:
    async def test_health_data_batch(self, patient_client):
        items = [
            {"date": f"2026-05-0{i + 1}", "step_count": 5000 + i,
             "heart_rate_avg": 68.0, "source_platform": "android_health_connect"}
            for i in range(3)
        ]
        r = await patient_client.post("/patients/me/health-data/batch", json=items)
        assert r.status_code in (200, 201)

    async def test_get_notif_preferences(self, patient_client):
        r = await patient_client.get("/patients/me/notification-preferences")
        assert r.status_code == 200

    async def test_put_notif_preferences(self, patient_client):
        r = await patient_client.patch("/patients/me/notification-preferences", json={"push_enabled": True})
        assert r.status_code == 200


class TestConsentementsMedecin:
    async def test_get_consents(self, patient_psy_client):
        r = await patient_psy_client.get(f"/patients/{PATIENT_ID}/consents")
        assert r.status_code == 200

    async def test_put_consents(self, patient_psy_client):
        r = await patient_psy_client.put(
            f"/patients/{PATIENT_ID}/consents",
            json={"data_collection": True, "ai_scoring": True, "iot_monitoring": True},
        )
        assert r.status_code == 200

    async def test_put_rgpd_consent(self, patient_psy_client):
        r = await patient_psy_client.put(
            f"/patients/{PATIENT_ID}/consents/rgpd",
            json={"consent_type": "data_collection", "granted": True},
        )
        assert r.status_code == 200
