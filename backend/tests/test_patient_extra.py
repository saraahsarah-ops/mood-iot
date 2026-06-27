"""Tests d'intégration patient supplémentaires — export RGPD, consentements."""

PATIENT_ID = "00000000-0000-0000-0000-0000000000a2"


class TestRGPD:
    async def test_export_donnees(self, patient_psy_client):
        # Export RGPD des données du patient (médecin lié -> accès OK).
        r = await patient_psy_client.get(f"/patients/{PATIENT_ID}/data-export")
        assert r.status_code == 200

    async def test_consentements_patient(self, patient_client):
        r = await patient_client.get("/patients/me/consents")
        assert r.status_code == 200
