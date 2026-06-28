"""Tests du canal SMS OVHcloud (channels.OVHSmsChannel) + factory get_sms_channel.

Vérifie la requête signée OVH et le repli sur Twilio quand OVH n'est pas
configuré. L'appel HTTP est mocké (aucun envoi réel).
"""
from unittest.mock import AsyncMock, MagicMock, patch

from src.notification import channels
from src.notification.channels import OVHSmsChannel, get_sms_channel


def _mock_httpx_client(resp):
    client = MagicMock()
    client.post = AsyncMock(return_value=resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestOVHSmsChannel:
    async def test_non_configure_retourne_false(self):
        ch = OVHSmsChannel()
        ch.configured = False
        assert await ch.send_sms("+33612345678", "test") is False

    async def test_numero_manquant_retourne_false(self):
        ch = OVHSmsChannel()
        ch.configured = True
        assert await ch.send_sms("", "test") is False

    async def test_envoi_signe_ok(self):
        ch = OVHSmsChannel()
        ch.configured = True
        ch._app_key = "ak"
        ch._app_secret = "as"
        ch._consumer_key = "ck"
        ch._service = "sms-test-1"
        ch._sender = "MoodIoT"
        ch._endpoint = "https://eu.api.ovh.com/1.0"

        resp = MagicMock(status_code=200)
        resp.json.return_value = {"ids": [42], "validReceivers": ["+33612345678"]}
        client = _mock_httpx_client(resp)
        with patch("httpx.AsyncClient", return_value=client):
            ok = await ch.send_sms("+33612345678", "Alerte Mood-IoT")

        assert ok is True
        _, kwargs = client.post.call_args
        headers = kwargs["headers"]
        assert headers["X-Ovh-Application"] == "ak"
        assert headers["X-Ovh-Consumer"] == "ck"
        assert headers["X-Ovh-Signature"].startswith("$1$")
        assert "+33612345678" in kwargs["content"]
        assert "MoodIoT" in kwargs["content"]

    async def test_erreur_http_retourne_false(self):
        ch = OVHSmsChannel()
        ch.configured = True
        ch._app_key = "ak"
        ch._app_secret = "as"
        ch._consumer_key = "ck"
        ch._service = "sms-test-1"
        ch._endpoint = "https://eu.api.ovh.com/1.0"

        resp = MagicMock(status_code=400)
        resp.text = "Bad request"
        client = _mock_httpx_client(resp)
        with patch("httpx.AsyncClient", return_value=client):
            ok = await ch.send_sms("+33612345678", "test")
        assert ok is False


class TestGetSmsChannel:
    async def test_repli_sur_twilio_si_ovh_absent(self):
        with patch.object(channels.ovh_sms_channel, "configured", False):
            assert get_sms_channel() is channels.twilio_channel

    async def test_ovh_si_configure(self):
        with patch.object(channels.ovh_sms_channel, "configured", True):
            assert get_sms_channel() is channels.ovh_sms_channel
