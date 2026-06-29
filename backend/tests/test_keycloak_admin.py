"""Tests unitaires — client d'administration Keycloak (src/shared/keycloak_admin).

httpx est mocké : on vérifie le parsing base/realm, le happy path de création
de compte patient (création + rôle + email), et la gestion des erreurs
(email déjà utilisé, creds manquantes).
"""
import pytest

from src.shared import keycloak_admin as ka
from src.shared.config import settings

_TOKEN_EP = "http://keycloak:8080/realms/moodiot/protocol/openid-connect/token"


class _Resp:
    def __init__(self, status_code, json_data=None, headers=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._json


class _FakeClient:
    """Mock d'httpx.AsyncClient : route les appels selon l'URL."""

    def __init__(self, *args, **kwargs):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        self.calls.append(("POST", url))
        if url.endswith("/token"):
            return _Resp(200, {"access_token": "fake-admin-token"})
        if url.endswith("/users"):
            return _Resp(
                201,
                headers={
                    "Location": "http://kc/admin/realms/moodiot/users/new-user-id-42"
                },
            )
        if "role-mappings" in url:
            return _Resp(204)
        return _Resp(200)

    async def get(self, url, **kwargs):
        self.calls.append(("GET", url))
        if url.endswith("/roles/patient"):
            return _Resp(200, {"id": "role-id", "name": "patient"})
        return _Resp(200)

    async def put(self, url, **kwargs):
        self.calls.append(("PUT", url))
        return _Resp(204)

    async def delete(self, url, **kwargs):
        self.calls.append(("DELETE", url))
        return _Resp(204)


@pytest.fixture
def kc_settings(monkeypatch):
    monkeypatch.setattr(settings, "KEYCLOAK_TOKEN_ENDPOINT", _TOKEN_EP)
    monkeypatch.setattr(settings, "KEYCLOAK_ADMIN_CLIENT_ID", "backend-services")
    monkeypatch.setattr(settings, "KEYCLOAK_ADMIN_CLIENT_SECRET", "secret")


def test_base_and_realm_ok(kc_settings):
    base, realm = ka._base_and_realm()
    assert base == "http://keycloak:8080"
    assert realm == "moodiot"


def test_base_and_realm_mal_configure(monkeypatch):
    monkeypatch.setattr(settings, "KEYCLOAK_TOKEN_ENDPOINT", "http://bad-url")
    with pytest.raises(ka.KeycloakAdminError):
        ka._base_and_realm()


@pytest.mark.asyncio
async def test_create_patient_account_happy(kc_settings, monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(ka.httpx, "AsyncClient", lambda *a, **k: fake)

    kc_id = await ka.create_patient_account(
        email="x@y.fr", first_name="X", last_name="Y"
    )
    assert kc_id == "new-user-id-42"
    # L'email "définir mot de passe" (execute-actions-email) a bien été appelé.
    assert any("execute-actions-email" in u for (m, u) in fake.calls)


@pytest.mark.asyncio
async def test_create_patient_account_email_deja_utilise(kc_settings, monkeypatch):
    class _Conflict(_FakeClient):
        async def post(self, url, **kwargs):
            if url.endswith("/users"):
                return _Resp(409, text="conflict")
            return await super().post(url, **kwargs)

    monkeypatch.setattr(ka.httpx, "AsyncClient", lambda *a, **k: _Conflict())
    with pytest.raises(ka.KeycloakAdminError) as exc:
        await ka.create_patient_account(email="dup@y.fr", first_name="X", last_name="Y")
    assert str(exc.value) == "email_deja_utilise"


@pytest.mark.asyncio
async def test_get_admin_token_sans_creds(monkeypatch):
    monkeypatch.setattr(settings, "KEYCLOAK_ADMIN_CLIENT_ID", "")
    with pytest.raises(ka.KeycloakAdminError):
        async with ka.httpx.AsyncClient() as c:
            await ka._get_admin_token(c)


@pytest.mark.asyncio
async def test_delete_account_best_effort(kc_settings, monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(ka.httpx, "AsyncClient", lambda *a, **k: fake)
    # Ne doit pas lever, même si tout va bien comme en cas d'erreur.
    await ka.delete_account("some-id")
    assert any(m == "DELETE" for (m, u) in fake.calls)
