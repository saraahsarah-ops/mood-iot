"""Tests d'intégration — service notification (src/notification/main).

Couvre l'envoi manuel, le déclenchement d'escalade (niveau 1) et la liste.
Les canaux externes (Twilio/FCM/email) ne sont pas configurés en test : ils
échouent proprement (False) sans planter, et la notification est persistée.
"""

PATIENT_ID = "00000000-0000-0000-0000-0000000000a2"


class TestNotificationSend:
    async def test_envoi_manuel(self, notification_psy_client):
        r = await notification_psy_client.post(
            "/notifications/send",
            json={"patient_id": PATIENT_ID, "title": "Info", "body": "Message de test"},
        )
        assert r.status_code in (200, 201)

    async def test_manuel_sans_titre_rejete(self, notification_psy_client):
        # Notification manuelle sans titre ni corps -> 422 (validation métier).
        r = await notification_psy_client.post(
            "/notifications/send", json={"patient_id": PATIENT_ID}
        )
        assert r.status_code in (400, 422)

    async def test_escalade_niveau_1(self, notification_psy_client):
        r = await notification_psy_client.post(
            "/notifications/send",
            json={
                "patient_id": PATIENT_ID,
                "score": 50,
                "alert_level": 1,
                "shap_explanations": ["sommeil en baisse"],
            },
        )
        assert r.status_code in (200, 201)


class TestNotificationList:
    async def test_liste_par_patient(self, notification_psy_client):
        r = await notification_psy_client.get(f"/notifications/{PATIENT_ID}")
        assert r.status_code == 200
