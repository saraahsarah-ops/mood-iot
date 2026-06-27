"""Tests — routes proxy du gateway (un handler par service) + chemins d'erreur.

On mocke `get_client` pour ne pas appeler les vrais microservices.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from httpx import ASGITransport, AsyncClient


def _mock_resp(status_code=200, body=None):
    resp = MagicMock(status_code=status_code)
    resp.headers = {"content-type": "application/json"}
    resp.json.return_value = body if body is not None else {"ok": True}
    return resp


async def _call(path, method="get", client_mock=None):
    from src.gateway import main as gw

    with patch.object(gw, "get_client", AsyncMock(return_value=client_mock)):
        async with AsyncClient(
            transport=ASGITransport(app=gw.app), base_url="http://test"
        ) as c:
            return await getattr(c, method)(path)


def _ok_client():
    mc = MagicMock()
    mc.request = AsyncMock(return_value=_mock_resp())
    return mc


class TestGatewayProxyRoutes:
    async def test_patients_base(self):
        r = await _call("/api/v1/patients", client_mock=_ok_client())
        assert r.status_code == 200

    async def test_patients_path(self):
        r = await _call("/api/v1/patients/123/metrics", client_mock=_ok_client())
        assert r.status_code == 200

    async def test_scoring(self):
        r = await _call("/api/v1/scoring/latest/123", client_mock=_ok_client())
        assert r.status_code == 200

    async def test_scoring_internal_bloque_404(self):
        # Défense en profondeur : /internal/ jamais exposé publiquement.
        r = await _call("/api/v1/scoring/internal/compute/123", client_mock=_ok_client())
        assert r.status_code == 404

    async def test_notification(self):
        r = await _call("/api/v1/notifications/all", client_mock=_ok_client())
        assert r.status_code == 200

    async def test_teleconsult(self):
        r = await _call("/api/v1/teleconsult/sessions", client_mock=_ok_client())
        assert r.status_code == 200

    async def test_doctor(self):
        r = await _call("/api/v1/doctor/me", client_mock=_ok_client())
        assert r.status_code == 200

    async def test_avec_query_params(self):
        r = await _call(
            "/api/v1/notifications/all?unread_only=true", client_mock=_ok_client()
        )
        assert r.status_code == 200


class TestGatewayProxyErreurs:
    async def test_service_indisponible_503(self):
        mc = MagicMock()
        mc.request = AsyncMock(side_effect=httpx.ConnectError("boom"))
        r = await _call("/api/v1/auth/test", client_mock=mc)
        assert r.status_code == 503

    async def test_erreur_proxy_502(self):
        mc = MagicMock()
        mc.request = AsyncMock(side_effect=RuntimeError("boom"))
        r = await _call("/api/v1/auth/test", client_mock=mc)
        assert r.status_code == 502

    async def test_reponse_non_json_enveloppee(self):
        resp = MagicMock(status_code=200)
        resp.headers = {"content-type": "text/plain"}
        resp.text = "coucou"
        mc = MagicMock()
        mc.request = AsyncMock(return_value=resp)
        r = await _call("/api/v1/auth/test", client_mock=mc)
        assert r.status_code == 200
        assert r.json()["raw"] == "coucou"


class TestGatewayHealthInjoignable:
    async def test_services_injoignables(self):
        mc = MagicMock()
        mc.get = AsyncMock(side_effect=Exception("down"))
        r = await _call("/api/v1/health", client_mock=mc)
        assert r.status_code == 200
        assert all(v == "unreachable" for v in r.json()["services"].values())
