"""
Tests unitaires pour la vérification des tokens Keycloak.

On mocke `PyJWKClient.get_signing_key_from_jwt` pour éviter un Keycloak
réellement démarré. On forge des tokens RS256 avec une clé privée éphémère
puis on vérifie que `verify_access_token` accepte les tokens valides et
rejette les autres avec une 401.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from src.shared import keycloak as kc_module
from src.shared.keycloak import extract_roles, verify_access_token


@pytest.fixture(scope="module")
def rsa_keypair() -> tuple[Any, Any]:
    """Génère une paire RSA 2048 utilisable pour signer/vérifier."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


@pytest.fixture
def configured_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force la config Keycloak à des valeurs déterministes pour les tests."""
    from src.shared.config import settings

    monkeypatch.setattr(
        settings, "KEYCLOAK_JWKS_URI", "https://example.test/jwks", raising=False
    )
    monkeypatch.setattr(
        settings, "KEYCLOAK_ISSUER", "https://example.test/realms/moodiot", raising=False
    )
    monkeypatch.setattr(
        settings,
        "KEYCLOAK_AUDIENCE",
        "mobile-app,backend-services",
        raising=False,
    )
    # Reset module-level caches between tests
    monkeypatch.setattr(kc_module, "_jwks_client", None, raising=False)
    monkeypatch.setattr(kc_module, "_jwks_client_loaded_at", 0.0, raising=False)
    kc_module._token_cache.clear()


def _make_token(
    private_key: Any,
    *,
    sub: str = "kc-user-123",
    email: str = "patient@example.test",
    roles: list[str] | None = None,
    audience: str | list[str] = "mobile-app",
    issuer: str = "https://example.test/realms/moodiot",
    expires_in: int = 300,
) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": sub,
        "email": email,
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + expires_in,
        "realm_access": {"roles": roles or ["patient"]},
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def _patch_signing_key(monkeypatch: pytest.MonkeyPatch, public_key: Any) -> None:
    mock_client = MagicMock()
    mock_key = MagicMock()
    mock_key.key = public_key
    mock_client.get_signing_key_from_jwt.return_value = mock_key
    monkeypatch.setattr(kc_module, "_get_jwks_client", lambda: mock_client)


def test_verify_valid_token_returns_claims(
    rsa_keypair: tuple[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
    configured_settings: None,
) -> None:
    private_key, public_key = rsa_keypair
    _patch_signing_key(monkeypatch, public_key)
    token = _make_token(private_key)

    claims = verify_access_token(token)

    assert claims["sub"] == "kc-user-123"
    assert claims["email"] == "patient@example.test"
    assert extract_roles(claims) == ["patient"]


def test_verify_expired_token_raises_401(
    rsa_keypair: tuple[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
    configured_settings: None,
) -> None:
    private_key, public_key = rsa_keypair
    _patch_signing_key(monkeypatch, public_key)
    token = _make_token(private_key, expires_in=-10)

    with pytest.raises(HTTPException) as exc:
        verify_access_token(token)
    assert exc.value.status_code == 401


def test_verify_wrong_audience_raises_401(
    rsa_keypair: tuple[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
    configured_settings: None,
) -> None:
    private_key, public_key = rsa_keypair
    _patch_signing_key(monkeypatch, public_key)
    token = _make_token(private_key, audience="some-other-app")

    with pytest.raises(HTTPException) as exc:
        verify_access_token(token)
    assert exc.value.status_code == 401


def test_verify_wrong_issuer_raises_401(
    rsa_keypair: tuple[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
    configured_settings: None,
) -> None:
    private_key, public_key = rsa_keypair
    _patch_signing_key(monkeypatch, public_key)
    token = _make_token(
        private_key, issuer="https://evil.example/realms/moodiot"
    )

    with pytest.raises(HTTPException) as exc:
        verify_access_token(token)
    assert exc.value.status_code == 401


def test_verify_tampered_signature_raises_401(
    rsa_keypair: tuple[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
    configured_settings: None,
) -> None:
    private_key, public_key = rsa_keypair
    _patch_signing_key(monkeypatch, public_key)
    token = _make_token(private_key)
    # Flip a byte in the signature
    parts = token.rsplit(".", 1)
    tampered = parts[0] + "." + ("A" * len(parts[1]))

    with pytest.raises(HTTPException) as exc:
        verify_access_token(tampered)
    assert exc.value.status_code == 401


def test_token_is_cached_between_calls(
    rsa_keypair: tuple[Any, Any],
    monkeypatch: pytest.MonkeyPatch,
    configured_settings: None,
) -> None:
    private_key, public_key = rsa_keypair
    mock_client = MagicMock()
    mock_key = MagicMock()
    mock_key.key = public_key
    mock_client.get_signing_key_from_jwt.return_value = mock_key
    monkeypatch.setattr(kc_module, "_get_jwks_client", lambda: mock_client)
    token = _make_token(private_key)

    verify_access_token(token)
    verify_access_token(token)
    verify_access_token(token)

    # JWKS lookup should happen only on the first verification
    assert mock_client.get_signing_key_from_jwt.call_count == 1


def test_extract_roles_handles_missing_realm_access() -> None:
    assert extract_roles({}) == []
    assert extract_roles({"realm_access": {}}) == []
    assert extract_roles({"realm_access": {"roles": ["patient", 42, "admin"]}}) == [
        "patient",
        "admin",
    ]
