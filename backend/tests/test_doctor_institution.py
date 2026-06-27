"""Tests d'intégration — endpoints doctor admin (approbation + institution).

Couvre : liste des médecins en attente, approbation/rejet, et la gestion des
membres de l'institution (liste, ajout, retrait) avec leurs garde-fous.
"""
import uuid

from src.shared.encryption import encrypt_field
from src.shared.models import (
    DoctorProfile,
    Institution,
    RegistrationStatus,
    User,
    UserRole,
)

ADMIN_USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000c1")
PSY_USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000b1")


async def _seed_pending(db, email="pending@clinique.fr"):
    """Sème un médecin en attente d'approbation (avec profil)."""
    uid = uuid.uuid4()
    db.add(
        User(
            id=uid,
            email=email,
            role=UserRole.psychiatre,
            registration_status=RegistrationStatus.pending_approval,
        )
    )
    db.add(
        DoctorProfile(
            user_id=uid,
            first_name="Pend",
            last_name="Doc",
            speciality="Psychiatrie",
            rpps_number_encrypted=encrypt_field("22222222222"),
            license_number_encrypted=encrypt_field("LIC-PEND"),
        )
    )
    await db.commit()
    return uid


async def _attach_institution(db):
    """Crée une institution et y rattache l'admin + le psychiatre semés."""
    inst = Institution(name="Clinique Test", admin_user_id=ADMIN_USER_ID)
    db.add(inst)
    await db.flush()
    admin = await db.get(User, ADMIN_USER_ID)
    admin.institution_id = inst.id
    psy = await db.get(User, PSY_USER_ID)
    psy.institution_id = inst.id
    await db.commit()
    return inst.id


class TestDoctorApprobation:
    async def test_lister_en_attente(self, doctor_admin_client, db_query):
        await _seed_pending(db_query)
        r = await doctor_admin_client.get("/doctor/pending")
        assert r.status_code == 200
        assert any(d["registration_status"] == "pending_approval" for d in r.json())

    async def test_approuver(self, doctor_admin_client, db_query):
        uid = await _seed_pending(db_query)
        r = await doctor_admin_client.put(f"/doctor/{uid}/approve")
        assert r.status_code == 200

    async def test_approuver_introuvable(self, doctor_admin_client):
        r = await doctor_admin_client.put(f"/doctor/{uuid.uuid4()}/approve")
        assert r.status_code == 404

    async def test_approuver_deja_traite_400(self, doctor_admin_client, db_query):
        uid = await _seed_pending(db_query)
        ok = await doctor_admin_client.put(f"/doctor/{uid}/approve")
        assert ok.status_code == 200
        # 2e approbation : le compte n'est plus en attente -> 400.
        again = await doctor_admin_client.put(f"/doctor/{uid}/approve")
        assert again.status_code == 400

    async def test_rejeter(self, doctor_admin_client, db_query):
        uid = await _seed_pending(db_query)
        r = await doctor_admin_client.put(
            f"/doctor/{uid}/reject", json={"reason": "Dossier incomplet"}
        )
        assert r.status_code == 200

    async def test_rejeter_introuvable(self, doctor_admin_client):
        r = await doctor_admin_client.put(
            f"/doctor/{uuid.uuid4()}/reject", json={"reason": "x"}
        )
        assert r.status_code == 404

    async def test_rejeter_deja_traite_400(self, doctor_admin_client, db_query):
        uid = await _seed_pending(db_query)
        ok = await doctor_admin_client.put(f"/doctor/{uid}/approve")
        assert ok.status_code == 200
        again = await doctor_admin_client.put(
            f"/doctor/{uid}/reject", json={"reason": "x"}
        )
        assert again.status_code == 400


class TestDoctorInstitution:
    async def test_membres_sans_institution_400(self, doctor_admin_client):
        # L'admin semé n'a pas d'institution par défaut -> 400.
        r = await doctor_admin_client.get("/doctor/institution/members")
        assert r.status_code == 400

    async def test_lister_membres(self, doctor_admin_client, db_query):
        await _attach_institution(db_query)
        r = await doctor_admin_client.get("/doctor/institution/members")
        assert r.status_code == 200

    async def test_ajouter_membre(self, doctor_admin_client, db_query):
        await _attach_institution(db_query)
        r = await doctor_admin_client.post(
            "/doctor/institution/members",
            json={
                "email": "nouveau@clinique.fr",
                "password": "Membre2026!",
                "first_name": "Nouveau",
                "last_name": "Medecin",
                "rpps_number": "33333333333",
                "license_number": "LIC-NEW",
            },
        )
        assert r.status_code == 201

    async def test_ajouter_membre_sans_institution_400(self, doctor_admin_client):
        # Admin sans institution -> 400 (garde avant toute création).
        r = await doctor_admin_client.post(
            "/doctor/institution/members",
            json={
                "email": "x@clinique.fr",
                "password": "Membre2026!",
                "first_name": "X",
                "last_name": "Y",
                "rpps_number": "99999999999",
                "license_number": "LIC-X",
            },
        )
        assert r.status_code == 400

    async def test_ajouter_membre_mdp_faible_400(self, doctor_admin_client, db_query):
        # Mot de passe assez long pour passer Pydantic mais sans majuscule/chiffre/
        # caractère spécial -> rejet par validate_password_strength (400).
        await _attach_institution(db_query)
        r = await doctor_admin_client.post(
            "/doctor/institution/members",
            json={
                "email": "faible@clinique.fr",
                "password": "faiblefaible",
                "first_name": "X",
                "last_name": "Y",
                "rpps_number": "88888888888",
                "license_number": "LIC-F",
            },
        )
        assert r.status_code == 400

    async def test_ajouter_membre_email_existant_409(self, doctor_admin_client, db_query):
        await _attach_institution(db_query)
        r = await doctor_admin_client.post(
            "/doctor/institution/members",
            json={
                "email": "psy@test.fr",  # déjà semé
                "password": "Membre2026!",
                "first_name": "Doublon",
                "last_name": "Medecin",
                "rpps_number": "44444444444",
                "license_number": "LIC-DUP",
            },
        )
        assert r.status_code == 409

    async def test_retirer_membre(self, doctor_admin_client, db_query):
        await _attach_institution(db_query)
        r = await doctor_admin_client.delete(
            f"/doctor/institution/members/{PSY_USER_ID}"
        )
        assert r.status_code == 200

    async def test_retirer_soi_meme_400(self, doctor_admin_client, db_query):
        await _attach_institution(db_query)
        r = await doctor_admin_client.delete(
            f"/doctor/institution/members/{ADMIN_USER_ID}"
        )
        assert r.status_code == 400

    async def test_retirer_introuvable_404(self, doctor_admin_client, db_query):
        await _attach_institution(db_query)
        r = await doctor_admin_client.delete(
            f"/doctor/institution/members/{uuid.uuid4()}"
        )
        assert r.status_code == 404
