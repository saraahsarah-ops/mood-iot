"""Tests consents patient — branches non couvertes : 404, boucle de lecture
(consentements existants) et mise à jour d'un consentement déjà présent.
"""
import uuid

PATIENT_ID = "00000000-0000-0000-0000-0000000000a2"

CONSENTS = {
    "data_collection": True,
    "data_sharing_psychiatre": True,
    "iot_monitoring": False,
    "ai_scoring": True,
    "emergency_contact": False,
}


class TestConsentsBranches:
    async def test_get_consents_introuvable_404(self, patient_psy_client):
        r = await patient_psy_client.get(f"/patients/{uuid.uuid4()}/consents")
        assert r.status_code == 404

    async def test_put_consents_introuvable_404(self, patient_psy_client):
        r = await patient_psy_client.put(
            f"/patients/{uuid.uuid4()}/consents", json=CONSENTS
        )
        assert r.status_code == 404

    async def test_put_puis_get_consents(self, patient_psy_client):
        # 1er PUT crée ; 2e PUT met à jour (branche « consentement existant ») ;
        # GET itère ensuite sur les consentements présents (boucle de lecture).
        r1 = await patient_psy_client.put(
            f"/patients/{PATIENT_ID}/consents", json=CONSENTS
        )
        assert r1.status_code == 200
        r2 = await patient_psy_client.put(
            f"/patients/{PATIENT_ID}/consents",
            json={**CONSENTS, "iot_monitoring": True},
        )
        assert r2.status_code == 200
        g = await patient_psy_client.get(f"/patients/{PATIENT_ID}/consents")
        assert g.status_code == 200
        assert g.json()["consents"]["iot_monitoring"] is True
