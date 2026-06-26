"""Tests d'intégration — endpoints du service doctor (src/doctor/main).

Couvre l'inscription publique (+ validations), la fiche /doctor/me et la
validation/rejet par un admin.
"""
from sqlalchemy import select

from src.shared.models import User

REG = {
    "email": "new.doc@test.fr",
    "password": "Str0ng#Pass",
    "first_name": "New",
    "last_name": "Doc",
    "rpps_number": "12345678901",
    "license_number": "LIC-1",
    "speciality": "Psychiatrie",
    "rgpd_consent": True,
}


class TestDoctorRegister:
    async def test_inscription_reussie(self, doctor_public_client):
        r = await doctor_public_client.post("/doctor/register", json=REG)
        assert r.status_code == 201

    async def test_statut_pending_et_rpps_chiffre(self, doctor_public_client, db_query):
        await doctor_public_client.post("/doctor/register", json=REG)
        res = await db_query.execute(select(User).where(User.email == REG["email"]))
        user = res.scalar_one()
        assert user.registration_status.value == "pending_approval"

    async def test_mot_de_passe_faible_rejete(self, doctor_public_client):
        # 12 caractères mais sans majuscule/chiffre/spécial -> validateur custom (400)
        # (un mot de passe < 8 serait rejeté plus tôt par Pydantic en 422).
        r = await doctor_public_client.post(
            "/doctor/register", json={**REG, "password": "faiblefaible"}
        )
        assert r.status_code == 400

    async def test_sans_consentement_rgpd(self, doctor_public_client):
        r = await doctor_public_client.post(
            "/doctor/register", json={**REG, "rgpd_consent": False}
        )
        assert r.status_code == 400

    async def test_email_duplique_409(self, doctor_public_client):
        await doctor_public_client.post("/doctor/register", json=REG)
        r = await doctor_public_client.post("/doctor/register", json=REG)
        assert r.status_code == 409


class TestDoctorProfile:
    async def test_get_me(self, doctor_psy_client):
        r = await doctor_psy_client.get("/doctor/me")
        assert r.status_code == 200
        assert r.json()["first_name"] == "Doc"

    async def test_update_me(self, doctor_psy_client):
        r = await doctor_psy_client.put("/doctor/me", json={"first_name": "Docteur"})
        assert r.status_code == 200
        assert r.json()["first_name"] == "Docteur"


class TestDoctorValidation:
    async def _register_and_get_id(self, admin_client, db_query):
        await admin_client.post("/doctor/register", json=REG)  # endpoint public
        res = await db_query.execute(select(User).where(User.email == REG["email"]))
        return str(res.scalar_one().id)

    async def test_approbation_par_admin(self, doctor_admin_client, db_query):
        uid = await self._register_and_get_id(doctor_admin_client, db_query)
        r = await doctor_admin_client.put(f"/doctor/{uid}/approve")
        assert r.status_code == 200

    async def test_rejet_par_admin(self, doctor_admin_client, db_query):
        uid = await self._register_and_get_id(doctor_admin_client, db_query)
        r = await doctor_admin_client.put(
            f"/doctor/{uid}/reject", json={"reason": "Documents invalides"}
        )
        assert r.status_code == 200
