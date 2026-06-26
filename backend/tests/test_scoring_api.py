"""Tests d'intégration — endpoints du service scoring (src/scoring/main).

Le psychiatre semé est lié au patient (cf. conftest), ce qui permet de
couvrir le contrôle d'accès (anti-IDOR) et les requêtes d'historique.
"""
import uuid

# Doit correspondre à PATIENT_ID semé dans conftest.py
PATIENT_ID = "00000000-0000-0000-0000-0000000000a2"


class TestScoringAccess:
    async def test_historique_patient_lie(self, scoring_psy_client):
        # Patient lié au psychiatre -> accès autorisé (liste vide acceptable).
        r = await scoring_psy_client.get(f"/scoring/history/{PATIENT_ID}")
        assert r.status_code == 200

    async def test_dernier_score_patient_lie(self, scoring_psy_client):
        # Aucun score semé -> 200 (vide) ou 404 selon l'implémentation.
        r = await scoring_psy_client.get(f"/scoring/latest/{PATIENT_ID}")
        assert r.status_code in (200, 404)

    async def test_anti_idor_patient_non_lie(self, scoring_psy_client):
        # Patient non lié au psychiatre -> accès refusé (403) ou introuvable (404).
        autre = uuid.uuid4()
        r = await scoring_psy_client.get(f"/scoring/latest/{autre}")
        assert r.status_code in (403, 404)
