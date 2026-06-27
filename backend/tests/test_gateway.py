"""Tests — API Gateway (src/gateway/main).

Le gateway est un reverse-proxy httpx. On mocke `get_client` pour ne pas
appeler les vrais microservices.
"""
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient


class TestGatewayHealth:
    async def test_health_agrege_les_services(self):
        from src.gateway import main as gw

        resp = MagicMock(status_code=200)
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=resp)
        with patch.object(gw, "get_client", AsyncMock(return_value=mock_client)):
            async with AsyncClient(
                transport=ASGITransport(app=gw.app), base_url="http://test"
            ) as c:
                r = await c.get("/api/v1/health")
                assert r.status_code == 200
                body = r.json()
                assert "services" in body


class TestGatewayProxy:
    async def test_proxy_transfere_la_reponse(self):
        from src.gateway import main as gw

        resp = MagicMock(status_code=200)
        resp.headers = {"content-type": "application/json"}
        resp.json.return_value = {"ok": True}
        mock_client = MagicMock()
        mock_client.request = AsyncMock(return_value=resp)
        with patch.object(gw, "get_client", AsyncMock(return_value=mock_client)):
            async with AsyncClient(
                transport=ASGITransport(app=gw.app), base_url="http://test"
            ) as c:
                r = await c.get("/api/v1/auth/test")
                assert r.status_code == 200

    async def test_service_inconnu_404(self):
        from src.gateway import main as gw

        async with AsyncClient(
            transport=ASGITransport(app=gw.app), base_url="http://test"
        ) as c:
            # Une route non mappée par le gateway -> 404 (pas de proxy).
            r = await c.get("/api/v1/inexistant/xyz")
            assert r.status_code in (404, 405)
