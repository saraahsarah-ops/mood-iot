"""Tests unitaires — émetteurs bas niveau (src/notification/senders).

Chemins « non configuré » (par défaut en test) + succès mocké pour l'email.
"""
from unittest.mock import AsyncMock, MagicMock, patch

from src.notification.senders import email_sender, push_sender, sms_sender


class TestEmailSender:
    async def test_sans_cle_resend(self):
        with patch.object(email_sender.settings, "RESEND_API_KEY", ""):
            r = await email_sender.send_email(to="a@b.fr", subject="s", html="<p>x</p>")
            assert r.success is False
            assert r.error == "resend_api_key_missing"

    async def test_succes_mocke(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"id": "email_1"}
        client = AsyncMock()
        client.post = AsyncMock(return_value=resp)
        with patch.object(email_sender.settings, "RESEND_API_KEY", "re_x"), patch(
            "httpx.AsyncClient"
        ) as AC:
            AC.return_value.__aenter__ = AsyncMock(return_value=client)
            AC.return_value.__aexit__ = AsyncMock(return_value=False)
            r = await email_sender.send_email(to="a@b.fr", subject="s", html="<p>x</p>")
            assert r.success is True

    async def test_http_erreur(self):
        resp = MagicMock(status_code=422, text="bad")
        client = AsyncMock()
        client.post = AsyncMock(return_value=resp)
        with patch.object(email_sender.settings, "RESEND_API_KEY", "re_x"), patch(
            "httpx.AsyncClient"
        ) as AC:
            AC.return_value.__aenter__ = AsyncMock(return_value=client)
            AC.return_value.__aexit__ = AsyncMock(return_value=False)
            r = await email_sender.send_email(to="a@b.fr", subject="s", html="<p>x</p>")
            assert r.success is False


class TestPushSender:
    async def test_token_format_invalide(self):
        r = await push_sender.send_push(
            push_token="pas-un-token-expo", title="t", body="b"
        )
        assert r.success is False
        assert r.error == "invalid_token_format"


class TestSmsSender:
    async def test_sans_creds_twilio(self):
        # En test, pas de creds Twilio -> échec propre, pas d'appel réseau.
        with patch.object(sms_sender.settings, "TWILIO_ACCOUNT_SID", ""):
            r = await sms_sender.send_sms(to="+33768963773", body="msg")
            assert r.success is False
