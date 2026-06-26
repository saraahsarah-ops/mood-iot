"""Tests d'intégration — service auth (src/auth/main).

/auth/me résout l'utilisateur courant en base à partir du JWT (ici mocké
comme le patient semé).
"""


class TestAuthMe:
    async def test_auth_me_retourne_utilisateur(self, auth_patient_client):
        r = await auth_patient_client.get("/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == "patient@test.fr"
