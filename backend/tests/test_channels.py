"""Tests unitaires — canaux de notification (src/notification/channels).

Style « JUnit + Mockito » : on instancie chaque canal puis on injecte des
mocks (client Twilio/SES, fb_messaging, httpx…) pour couvrir les chemins
succès / échec / non-configuré sans appeler les vrais services externes.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.notification import channels as ch


# ---------------------------------------------------------------------------
# WebSocketChannel — pas de dépendance externe, testable intégralement
# ---------------------------------------------------------------------------
class TestWebSocketChannel:
    def test_register_et_unregister(self):
        c = ch.WebSocketChannel()
        ws = MagicMock()
        c.register("psy1", ws)
        assert "psy1" in c._connections and ws in c._connections["psy1"]
        c.unregister("psy1", ws)
        assert "psy1" not in c._connections  # set vidé -> clé supprimée

    def test_unregister_psychiatre_inconnu_ne_plante_pas(self):
        ch.WebSocketChannel().unregister("inconnu", MagicMock())

    @pytest.mark.asyncio
    async def test_broadcast_sans_connexion_retourne_false(self):
        c = ch.WebSocketChannel()
        assert await c.broadcast_alert("psy1", {"x": 1}) is False

    @pytest.mark.asyncio
    async def test_broadcast_envoie_a_la_connexion(self):
        c = ch.WebSocketChannel()
        ws = MagicMock()
        ws.send_text = AsyncMock()
        c.register("psy1", ws)
        assert await c.broadcast_alert("psy1", {"score": 70}) is True
        ws.send_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_nettoie_les_connexions_defaillantes(self):
        c = ch.WebSocketChannel()
        ws = MagicMock()
        ws.send_text = AsyncMock(side_effect=RuntimeError("socket mort"))
        c.register("psy1", ws)
        assert await c.broadcast_alert("psy1", {"x": 1}) is False
        # la connexion défaillante est retirée du set (la clé peut rester, vide)
        assert ws not in c._connections.get("psy1", set())


# ---------------------------------------------------------------------------
# ClaudeCoachingChannel
# ---------------------------------------------------------------------------
class TestClaudeCoachingChannel:
    @pytest.mark.asyncio
    async def test_message_par_defaut_sans_client(self):
        c = ch.ClaudeCoachingChannel()
        c._client = None
        msg = await c.generate_coaching({"patient_first_name": "Hugo", "score": 70})
        assert "Hugo" in msg

    @pytest.mark.asyncio
    async def test_succes_avec_client_mocke(self):
        c = ch.ClaudeCoachingChannel()
        fake = MagicMock()
        fake.content = [MagicMock(text="  Courage Hugo !  ")]
        c._client = MagicMock()
        c._client.messages.create = AsyncMock(return_value=fake)
        msg = await c.generate_coaching({"patient_first_name": "Hugo", "score": 70, "shap_top3": ["sommeil"]})
        assert msg == "Courage Hugo !"

    @pytest.mark.asyncio
    async def test_fallback_si_erreur_api(self):
        c = ch.ClaudeCoachingChannel()
        c._client = MagicMock()
        c._client.messages.create = AsyncMock(side_effect=RuntimeError("API down"))
        msg = await c.generate_coaching({"patient_first_name": "Hugo", "score": 70})
        assert "Hugo" in msg  # message de repli


# ---------------------------------------------------------------------------
# FCMChannel
# ---------------------------------------------------------------------------
class TestFCMChannel:
    @pytest.mark.asyncio
    async def test_non_initialise_retourne_false(self):
        c = ch.FCMChannel()
        c._initialized = False
        assert await c.send_push("tok", "t", "b") is False

    @pytest.mark.asyncio
    async def test_token_manquant_retourne_false(self):
        c = ch.FCMChannel()
        c._initialized = True
        assert await c.send_push("", "t", "b") is False

    @pytest.mark.asyncio
    async def test_succes(self):
        c = ch.FCMChannel()
        c._initialized = True
        with patch.object(ch.fb_messaging, "send", return_value="msg-id") as send:
            assert await c.send_push("tok", "Titre", "Corps", {"k": "v"}) is True
            send.assert_called_once()

    @pytest.mark.asyncio
    async def test_erreur_envoi(self):
        c = ch.FCMChannel()
        c._initialized = True
        with patch.object(ch.fb_messaging, "send", side_effect=RuntimeError("boom")):
            assert await c.send_push("tok", "t", "b") is False


# ---------------------------------------------------------------------------
# TwilioChannel
# ---------------------------------------------------------------------------
class TestTwilioChannel:
    @pytest.mark.asyncio
    async def test_sms_sans_client_retourne_false(self):
        c = ch.TwilioChannel()
        c._client = None
        assert await c.send_sms("+33...", "msg") is False

    @pytest.mark.asyncio
    async def test_sms_sans_numero_retourne_false(self):
        c = ch.TwilioChannel()
        c._client = MagicMock()
        assert await c.send_sms("", "msg") is False

    @pytest.mark.asyncio
    async def test_sms_succes(self):
        c = ch.TwilioChannel()
        c._client = MagicMock()
        c._client.messages.create.return_value = MagicMock(sid="SM1")
        assert await c.send_sms("+33768963773", "Alerte") is True

    @pytest.mark.asyncio
    async def test_sms_erreur(self):
        c = ch.TwilioChannel()
        c._client = MagicMock()
        c._client.messages.create.side_effect = RuntimeError("region")
        assert await c.send_sms("+33768963773", "Alerte") is False

    @pytest.mark.asyncio
    async def test_appel_sans_client(self):
        c = ch.TwilioChannel()
        c._client = None
        assert await c.make_call("+33...", "bonjour") is False

    @pytest.mark.asyncio
    async def test_appel_succes(self):
        c = ch.TwilioChannel()
        c._client = MagicMock()
        c._client.calls.create.return_value = MagicMock(sid="CA1")
        assert await c.make_call("+33768963773", "Alerte urgente") is True


# ---------------------------------------------------------------------------
# SESChannel
# ---------------------------------------------------------------------------
class TestSESChannel:
    @pytest.mark.asyncio
    async def test_sans_client_retourne_false(self):
        c = ch.SESChannel()
        c._client = None
        assert await c.send_email("a@b.fr", "obj", "<p>x</p>") is False

    @pytest.mark.asyncio
    async def test_sans_destinataire(self):
        c = ch.SESChannel()
        c._client = MagicMock()
        assert await c.send_email("", "obj", "<p>x</p>") is False

    @pytest.mark.asyncio
    async def test_succes(self):
        c = ch.SESChannel()
        c._client = MagicMock()
        c._client.send_email.return_value = {"MessageId": "id1"}
        assert await c.send_email("a@b.fr", "obj", "<p>x</p>") is True

    @pytest.mark.asyncio
    async def test_erreur(self):
        c = ch.SESChannel()
        c._client = MagicMock()
        c._client.send_email.side_effect = RuntimeError("ses down")
        assert await c.send_email("a@b.fr", "obj", "<p>x</p>") is False


# ---------------------------------------------------------------------------
# ResendChannel
# ---------------------------------------------------------------------------
class TestResendChannel:
    @pytest.mark.asyncio
    async def test_sans_cle_api(self):
        c = ch.ResendChannel()
        c._api_key = ""
        assert await c.send_email("a@b.fr", "obj", "<p>x</p>") is False

    @pytest.mark.asyncio
    async def test_sans_destinataire(self):
        c = ch.ResendChannel()
        c._api_key = "re_xxx"
        assert await c.send_email("", "obj", "<p>x</p>") is False

    @pytest.mark.asyncio
    async def test_succes(self):
        c = ch.ResendChannel()
        c._api_key = "re_xxx"
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"id": "email_1"}
        client = AsyncMock()
        client.post = AsyncMock(return_value=resp)
        with patch("httpx.AsyncClient") as AC:
            AC.return_value.__aenter__ = AsyncMock(return_value=client)
            AC.return_value.__aexit__ = AsyncMock(return_value=False)
            assert await c.send_email("a@b.fr", "Alerte", "<p>x</p>") is True

    @pytest.mark.asyncio
    async def test_status_non_2xx(self):
        c = ch.ResendChannel()
        c._api_key = "re_xxx"
        resp = MagicMock(status_code=422, text="bad")
        client = AsyncMock()
        client.post = AsyncMock(return_value=resp)
        with patch("httpx.AsyncClient") as AC:
            AC.return_value.__aenter__ = AsyncMock(return_value=client)
            AC.return_value.__aexit__ = AsyncMock(return_value=False)
            assert await c.send_email("a@b.fr", "obj", "<p>x</p>") is False

    @pytest.mark.asyncio
    async def test_exception_reseau(self):
        c = ch.ResendChannel()
        c._api_key = "re_xxx"
        with patch("httpx.AsyncClient", side_effect=RuntimeError("réseau")):
            assert await c.send_email("a@b.fr", "obj", "<p>x</p>") is False


# ---------------------------------------------------------------------------
# get_email_channel
# ---------------------------------------------------------------------------
class TestGetEmailChannel:
    def test_resend_si_cle_presente(self):
        with patch.object(ch.resend_channel, "_api_key", "re_xxx"):
            assert ch.get_email_channel() is ch.resend_channel

    def test_ses_si_pas_de_cle_resend(self):
        with patch.object(ch.resend_channel, "_api_key", ""):
            assert ch.get_email_channel() is ch.ses_channel
