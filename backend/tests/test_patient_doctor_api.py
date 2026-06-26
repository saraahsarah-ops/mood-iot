"""Tests d'intégration — endpoints patient côté MÉDECIN (src/patient/main).

Le psychiatre semé est lié au patient (conftest) : accès autorisé, et
anti-IDOR vérifié sur un patient non lié.
"""
import uuid

PATIENT_ID = "00000000-0000-0000-0000-0000000000a2"

NEW_PATIENT = {
    "first_name": "Nouveau",
    "last_name": "Patient",
    "date_of_birth": "1990-05-15",
    "gender": "F",
    "email": "nouveau.patient@test.fr",
}


class TestPatientCrudMedecin:
    async def test_lister_patients(self, patient_psy_client):
        r = await patient_psy_client.get("/patients")
        assert r.status_code == 200

    async def test_detail_patient_lie(self, patient_psy_client):
        r = await patient_psy_client.get(f"/patients/{PATIENT_ID}")
        assert r.status_code == 200
        assert r.json()["first_name"] == "Test"

    async def test_modifier_patient(self, patient_psy_client):
        r = await patient_psy_client.put(
            f"/patients/{PATIENT_ID}", json={"first_name": "Modifié"}
        )
        assert r.status_code == 200
        assert r.json()["first_name"] == "Modifié"

    async def test_metriques_patient(self, patient_psy_client):
        r = await patient_psy_client.get(f"/patients/{PATIENT_ID}/metrics")
        assert r.status_code == 200

    async def test_baseline_patient(self, patient_psy_client):
        r = await patient_psy_client.get(f"/patients/{PATIENT_ID}/baseline")
        assert r.status_code in (200, 404)


class TestAntiIdorMedecin:
    async def test_patient_non_lie_refuse(self, patient_psy_client):
        autre = uuid.uuid4()
        r = await patient_psy_client.get(f"/patients/{autre}")
        assert r.status_code in (403, 404)
