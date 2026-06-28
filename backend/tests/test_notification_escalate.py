"""Tests — endpoint interne d'escalade (scoring -> notification).

Les canaux externes (Twilio/FCM/email) n'ont pas de credentials en test :
ils échouent proprement (False) sans rien envoyer. On vérifie le secret,
le court-circuit niveau 0, et les cascades niveau 2 / niveau 3 (qui créent
notifications + auto-téléconsultation + avis patient).
"""
PATIENT_ID = "00000000-0000-0000-0000-0000000000a2"
SECRET = {"X-Internal-Service": "test-internal-secret"}


class TestInternalEscalate:
    async def test_sans_secret_403(self, notification_psy_client):
        r = await notification_psy_client.post(
            "/notifications/internal/escalate",
            json={"patient_id": PATIENT_ID, "score": 75, "alert_level": 2},
        )
        assert r.status_code == 403

    async def test_niveau_0_court_circuite(self, notification_psy_client):
        r = await notification_psy_client.post(
            "/notifications/internal/escalate",
            headers=SECRET,
            json={"patient_id": PATIENT_ID, "score": 10, "alert_level": 0},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "skipped"

    async def test_escalade_niveau_2(self, notification_psy_client):
        r = await notification_psy_client.post(
            "/notifications/internal/escalate",
            headers=SECRET,
            json={
                "patient_id": PATIENT_ID,
                "score": 70,
                "alert_level": 2,
                "shap_explanations": ["sommeil en baisse", "activité réduite"],
            },
        )
        assert r.status_code in (200, 201)
        assert r.json()["status"] == "escalated"

    async def test_escalade_niveau_3_cree_teleconsult_et_avise_patient(
        self, notification_psy_client, db_query
    ):
        # Niveau 3 : tout le niveau 2 + auto-téléconsultation + avis au patient.
        from sqlalchemy import select
        from src.shared.models import Notification, TeleconsultSession

        r = await notification_psy_client.post(
            "/notifications/internal/escalate",
            headers=SECRET,
            json={
                "patient_id": PATIENT_ID,
                "score": 92,
                "alert_level": 3,
                "shap_explanations": ["isolement", "sommeil critique"],
            },
        )
        assert r.status_code in (200, 201)

        # Une téléconsultation d'urgence a été auto-créée.
        sess = await db_query.execute(
            select(TeleconsultSession).where(
                TeleconsultSession.patient_id == PATIENT_ID
            )
        )
        assert sess.scalars().first() is not None

        # Le patient a reçu une notification de RDV (mon ajout niveau 3).
        notifs = await db_query.execute(
            select(Notification).where(Notification.patient_id == PATIENT_ID)
        )
        titres = [n.title for n in notifs.scalars().all()]
        assert any("urgence" in (t or "").lower() for t in titres)
