"""Tests unitaires — moteur d'escalade (src/notification/escalation).

DB et canaux externes mockés (Mockito-style). Couvre le routage par niveau
et les handlers niveau 1/2, dont le chemin corrigé (psychiatrist.phone /
device_token_fcm / email via get_email_channel) qui plantait avant.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.notification import escalation as esc


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _result(entity):
    r = MagicMock()
    r.scalars.return_value.first.return_value = entity
    return r


def make_db(*entities):
    """AsyncSession mock dont chaque execute() renvoie l'entité suivante."""
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[_result(e) for e in entities])
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def patient():
    return SimpleNamespace(id="p1", user_id="u1", first_name="Hugo",
                           last_name="Petit", device_token_fcm="tok-patient")


@pytest.fixture
def psychiatrist():
    return SimpleNamespace(id="psy1", email="dr.martin@example.test",
                           phone="+33768963773", device_token_fcm=None,
                           last_name="Martin")


@pytest.fixture
def mock_channels():
    with patch.object(esc, "claude_coaching") as cc, \
         patch.object(esc, "fcm_channel") as fcm, \
         patch.object(esc, "ws_channel") as ws, \
         patch.object(esc, "twilio_channel") as tw, \
         patch.object(esc, "get_sms_channel") as gsms, \
         patch.object(esc, "get_email_channel") as gec:
        cc.generate_coaching = AsyncMock(return_value="Courage Hugo")
        fcm.send_push = AsyncMock(return_value=True)
        ws.broadcast_alert = AsyncMock(return_value=True)
        tw.send_sms = AsyncMock(return_value=True)
        tw.make_call = AsyncMock(return_value=True)
        # Les SMS passent par get_sms_channel() (OVH si configuré, sinon Twilio).
        gsms.return_value = tw
        email = MagicMock()
        email.send_email = AsyncMock(return_value=True)
        gec.return_value = email
        yield SimpleNamespace(cc=cc, fcm=fcm, ws=ws, tw=tw, email=email)


@pytest.fixture
def engine():
    return esc.EscalationEngine()


# --------------------------------------------------------------------------
# Routage process_alert
# --------------------------------------------------------------------------
class TestProcessAlertRouting:
    @pytest.mark.asyncio
    async def test_niveau_0_aucune_action(self, engine):
        db = make_db()
        res = await engine.process_alert(patient_id="p1", score=20, alert_level=0,
                                         risk_score_id="r1", shap_explanations=[], db=db)
        assert res["alert_level"] == 0
        assert res["channels_used"] == []
        db.execute.assert_not_called()  # pas de requête pour le niveau 0

    @pytest.mark.asyncio
    async def test_patient_introuvable(self, engine, mock_channels):
        db = make_db(None)  # _get_patient -> None
        res = await engine.process_alert(patient_id="zzz", score=70, alert_level=2,
                                         risk_score_id="r1", shap_explanations=[], db=db)
        assert res["error"] == "patient_introuvable"


# --------------------------------------------------------------------------
# Niveau 1 — coaching IA au patient
# --------------------------------------------------------------------------
class TestNiveau1:
    @pytest.mark.asyncio
    async def test_coaching_et_push_patient(self, engine, patient, mock_channels):
        db = make_db(patient)
        res = await engine.process_alert(patient_id="p1", score=50, alert_level=1,
                                         risk_score_id="r1",
                                         shap_explanations=["sommeil bas"], db=db)
        mock_channels.cc.generate_coaching.assert_awaited_once()
        mock_channels.fcm.send_push.assert_awaited_once()
        db.add.assert_called_once()       # notification persistée
        db.flush.assert_awaited_once()
        assert "error" not in res


# --------------------------------------------------------------------------
# Niveau 2 — alerte multi-canal au psychiatre (chemin corrigé)
# --------------------------------------------------------------------------
class TestNiveau2:
    @pytest.mark.asyncio
    async def test_alerte_multicanal(self, engine, patient, psychiatrist, mock_channels):
        db = make_db(patient, psychiatrist)
        res = await engine.process_alert(patient_id="p1", score=70, alert_level=2,
                                         risk_score_id="r1",
                                         shap_explanations=["sommeil", "activité"], db=db)
        # tous les canaux du niveau 2 sont sollicités
        mock_channels.ws.broadcast_alert.assert_awaited_once()
        mock_channels.tw.send_sms.assert_awaited_once()
        mock_channels.email.send_email.assert_awaited_once()
        # Le patient reçoit AUSSI un coaching au niveau 2 -> coaching généré,
        # 2e push FCM (psychiatre + patient) et 2e add (alerte + coaching).
        mock_channels.cc.generate_coaching.assert_awaited_once()
        assert mock_channels.fcm.send_push.await_count == 2
        assert db.add.call_count == 2
        assert "error" not in res
        assert "websocket" in res["channels_used"]
        assert "claude_coaching" in res["channels_used"]

    @pytest.mark.asyncio
    async def test_psychiatre_introuvable(self, engine, patient, mock_channels):
        db = make_db(patient, None)  # patient ok, psychiatre None
        res = await engine.process_alert(patient_id="p1", score=70, alert_level=2,
                                         risk_score_id="r1", shap_explanations=[], db=db)
        assert res["error"] == "psychiatre_introuvable"
        mock_channels.email.send_email.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ne_plante_pas_si_phone_none(self, engine, patient, mock_channels):
        # device_token_fcm=None + phone défini : ne doit pas lever d'AttributeError
        psy = SimpleNamespace(id="psy2", email="d@x.fr", phone=None,
                              device_token_fcm=None, last_name="X")
        db = make_db(patient, psy)
        res = await engine.process_alert(patient_id="p1", score=75, alert_level=2,
                                         risk_score_id="r1", shap_explanations=[], db=db)
        assert "error" not in res
