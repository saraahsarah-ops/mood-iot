"""Tests d'intégration — service auth (register-profile, sync, me).

`register-profile` vérifie le token Keycloak à la main via
`verify_access_token` (fonction module) → on la mocke (pas de Keycloak réel).
"""
from unittest.mock import patch


class TestAuthMe:
    async def test_me(self, auth_patient_client):
        r = await auth_patient_client.get("/auth/me")
        assert r.status_code == 200
        assert r.json()["role"] == "patient"


class TestAuthSync:
    async def test_sync_met_a_jour_nom(self, auth_patient_client):
        r = await auth_patient_client.post(
            "/auth/sync", json={"first_name": "Nouveau", "last_name": "Nom"}
        )
        assert r.status_code == 200


class TestAuthRegister:
    async def test_register_nouveau_patient(self, auth_patient_client):
        claims = {"sub": "kc-new-patient", "email": "nouveaupatient@clinique.fr"}
        with patch("src.auth.main.verify_access_token", return_value=claims):
            r = await auth_patient_client.post(
                "/auth/register-profile",
                headers={"Authorization": "Bearer faux-token"},
                json={
                    "role": "patient",
                    "first_name": "Jean",
                    "last_name": "Test",
                    "date_of_birth": "1990-05-01",
                    "gender": "M",
                },
            )
        assert r.status_code == 201
        assert r.json()["email"] == "nouveaupatient@clinique.fr"

    async def test_register_psychiatre(self, auth_patient_client):
        claims = {"sub": "kc-new-psy", "email": "nouveaupsy@clinique.fr"}
        with patch("src.auth.main.verify_access_token", return_value=claims):
            r = await auth_patient_client.post(
                "/auth/register-profile",
                headers={"Authorization": "Bearer faux-token"},
                json={
                    "role": "psychiatre",
                    "first_name": "Marie",
                    "last_name": "Doc",
                    "rpps_number": "55555555555",
                    "license_number": "LIC-NEW",
                    "speciality": "Psychiatrie",
                },
            )
        assert r.status_code == 201

    async def test_register_sans_bearer_401(self, auth_patient_client):
        r = await auth_patient_client.post(
            "/auth/register-profile",
            json={"role": "patient", "first_name": "X", "last_name": "Y"},
        )
        assert r.status_code == 401

    async def test_register_idempotent(self, auth_patient_client):
        # 2e appel avec le même sub Keycloak -> mise à jour, pas de doublon.
        claims = {"sub": "kc-idem", "email": "idem@clinique.fr"}
        with patch("src.auth.main.verify_access_token", return_value=claims):
            r1 = await auth_patient_client.post(
                "/auth/register-profile",
                headers={"Authorization": "Bearer t"},
                json={"role": "patient", "first_name": "A", "last_name": "B", "gender": "F"},
            )
            r2 = await auth_patient_client.post(
                "/auth/register-profile",
                headers={"Authorization": "Bearer t"},
                json={"role": "patient", "first_name": "A", "last_name": "B", "gender": "F"},
            )
        assert r1.status_code == 201
        assert r2.status_code == 201
