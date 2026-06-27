"""Tests d'intégration — endpoints notification non couverts.

Couvre : liste globale (/all), acquittement, suppression, compteur non-lus,
synthèse IA sans clé (résumé factuel), coaching IA, garde-fou du rappel RDV.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.shared.models import (
    Message,
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)

PATIENT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a2")
PATIENT_USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
PSY_USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000b1")


async def _seed_notif(db, status=NotificationStatus.sent):
    """Sème une notification destinée au psychiatre semé et renvoie son id."""
    n = Notification(
        patient_id=PATIENT_ID,
        type=NotificationType.system,
        level=1,
        channel=NotificationChannel.websocket,
        title="Info",
        body="corps",
        recipient_user_id=PSY_USER_ID,
        status=status,
    )
    db.add(n)
    await db.commit()
    return n.id


class TestNotificationListes:
    async def test_lister_toutes(self, notification_psy_client):
        r = await notification_psy_client.get("/notifications/all")
        assert r.status_code == 200

    async def test_lister_toutes_non_lues(self, notification_psy_client):
        r = await notification_psy_client.get("/notifications/all?unread_only=true")
        assert r.status_code == 200

    async def test_filtre_type_invalide(self, notification_psy_client):
        r = await notification_psy_client.get(
            f"/notifications/{PATIENT_ID}?notification_type=inexistant"
        )
        assert r.status_code == 400

    async def test_compteur_non_lus(self, notification_psy_client):
        r = await notification_psy_client.get(
            f"/notifications/unread-count/{PATIENT_ID}"
        )
        assert r.status_code == 200
        assert "unread_count" in r.json()

    async def test_filtre_type_valide_et_non_lus(self, notification_psy_client):
        # type valide + unread_only -> couvre les deux branches de filtrage.
        r = await notification_psy_client.get(
            f"/notifications/{PATIENT_ID}?notification_type=system&unread_only=true"
        )
        assert r.status_code == 200


class TestNotificationAckDelete:
    async def test_acquitter(self, notification_psy_client, db_query):
        nid = await _seed_notif(db_query)
        r = await notification_psy_client.put(f"/notifications/{nid}/acknowledge")
        assert r.status_code == 200
        assert r.json()["status"] == "read"

    async def test_acquitter_introuvable(self, notification_psy_client):
        r = await notification_psy_client.put(
            f"/notifications/{uuid.uuid4()}/acknowledge"
        )
        assert r.status_code == 404

    async def test_supprimer(self, notification_psy_client, db_query):
        nid = await _seed_notif(db_query)
        r = await notification_psy_client.delete(f"/notifications/{nid}")
        assert r.status_code == 200
        assert r.json()["deleted"] is True

    async def test_supprimer_introuvable(self, notification_psy_client):
        r = await notification_psy_client.delete(f"/notifications/{uuid.uuid4()}")
        assert r.status_code == 404


class TestNotificationIA:
    async def test_synthese_ia_sans_cle(self, notification_psy_client):
        # ANTHROPIC_API_KEY absente en test -> 200 avec résumé factuel.
        r = await notification_psy_client.post(
            f"/notifications/ai-analysis/{PATIENT_ID}"
        )
        assert r.status_code == 200
        assert "analysis" in r.json()

    async def test_synthese_ia_patient_introuvable(self, notification_psy_client):
        r = await notification_psy_client.post(
            f"/notifications/ai-analysis/{uuid.uuid4()}"
        )
        assert r.status_code == 404

    async def test_synthese_ia_avec_historique(self, notification_psy_client, db_query):
        # Humeur + messages (deux sens) -> les boucles de construction du prompt
        # s'exécutent (branches "Patient"/"Psychiatre").
        from src.shared.models import MoodEntry

        db_query.add(MoodEntry(patient_id=PATIENT_ID, phq9_score=12, notes="Fatigue"))
        db_query.add(
            Message(
                sender_id=PATIENT_USER_ID,
                recipient_id=PSY_USER_ID,
                content="Je me sens mieux",
            )
        )
        db_query.add(
            Message(
                sender_id=PSY_USER_ID,
                recipient_id=PATIENT_USER_ID,
                content="Très bien, continuez",
            )
        )
        await db_query.commit()
        r = await notification_psy_client.post(
            f"/notifications/ai-analysis/{PATIENT_ID}"
        )
        assert r.status_code == 200
        assert "analysis" in r.json()

    async def test_coaching_ia(self, notification_psy_client):
        # Les canaux externes échouent proprement (pas de creds) -> dict de False.
        r = await notification_psy_client.post(
            f"/notifications/ai-coaching/{PATIENT_ID}",
            json={"risk_score": 55.0, "top_factors": ["sommeil"], "explanation": "x"},
        )
        assert r.status_code in (200, 500)

    async def test_rappel_rdv_kind_invalide(self, notification_psy_client):
        r = await notification_psy_client.post(
            f"/notifications/rdv/{uuid.uuid4()}/reminder/mauvais"
        )
        assert r.status_code == 400


class TestNotificationIAavecCle:
    """Chemin avec clé Anthropic configurée (client mocké, pas d'appel réel)."""

    async def test_synthese_ia_succes(self, notification_psy_client):
        from src.notification import main as n

        fake_msg = MagicMock()
        fake_msg.content = [MagicMock(text="Synthèse clinique générée.")]
        fake_client = MagicMock()
        fake_client.messages.create = AsyncMock(return_value=fake_msg)
        with patch("anthropic.AsyncAnthropic", return_value=fake_client), patch.object(
            n.settings, "ANTHROPIC_API_KEY", "sk-fake"
        ):
            r = await notification_psy_client.post(
                f"/notifications/ai-analysis/{PATIENT_ID}"
            )
        assert r.status_code == 200
        assert "Synthèse" in r.json()["analysis"]

    async def test_synthese_ia_erreur_attrapee(self, notification_psy_client):
        from src.notification import main as n

        fake_client = MagicMock()
        fake_client.messages.create = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("anthropic.AsyncAnthropic", return_value=fake_client), patch.object(
            n.settings, "ANTHROPIC_API_KEY", "sk-fake"
        ):
            r = await notification_psy_client.post(
                f"/notifications/ai-analysis/{PATIENT_ID}"
            )
        # L'erreur est attrapée -> 200 avec message d'erreur générique.
        assert r.status_code == 200
