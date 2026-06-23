"""
Tests du chiffrement PHI au repos (Fernet) et du type `EncryptedText`.

La clé de chiffrement est générée à la volée et injectée via monkeypatch, pour
ne dépendre d'aucune variable d'environnement réelle.
"""

import pytest
from cryptography.fernet import Fernet

from src.shared import encryption as enc
from src.shared.encrypted_types import EncryptedText


@pytest.fixture
def fernet_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Configure une clé Fernet de test et réinitialise le cache du module."""
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(enc.settings, "ENCRYPTION_KEY", key, raising=False)
    monkeypatch.setattr(enc, "_fernet", None, raising=False)  # reset cache
    yield key
    monkeypatch.setattr(enc, "_fernet", None, raising=False)


def test_encrypt_decrypt_roundtrip(fernet_key: str) -> None:
    clair = "Trouble dépressif récurrent, épisode sévère"
    chiffre = enc.encrypt_field(clair)
    assert chiffre != clair
    assert enc.decrypt_field(chiffre) == clair


def test_encrypt_empty_returns_empty(fernet_key: str) -> None:
    assert enc.encrypt_field("") == ""
    assert enc.decrypt_field("") == ""


def test_is_encrypted(fernet_key: str) -> None:
    assert enc.is_encrypted(enc.encrypt_field("x")) is True
    assert enc.is_encrypted("texte en clair") is False
    assert enc.is_encrypted("") is False


def test_decrypt_lenient_handles_legacy_plaintext(fernet_key: str) -> None:
    # Token chiffré → déchiffré
    assert enc.decrypt_lenient(enc.encrypt_field("note")) == "note"
    # Clair hérité → renvoyé tel quel (pas de "[CHIFFREMENT INVALIDE]")
    assert enc.decrypt_lenient("note héritée en clair") == "note héritée en clair"


def test_encrypted_text_type_roundtrip(fernet_key: str) -> None:
    col = EncryptedText()

    stored = col.process_bind_param("contenu clinique sensible", None)
    assert stored != "contenu clinique sensible"
    assert enc.is_encrypted(stored)
    assert col.process_result_value(stored, None) == "contenu clinique sensible"


def test_encrypted_text_type_none_and_empty(fernet_key: str) -> None:
    col = EncryptedText()
    assert col.process_bind_param(None, None) is None
    assert col.process_bind_param("", None) == ""
    assert col.process_result_value(None, None) is None
    assert col.process_result_value("", None) == ""


def test_encrypted_text_type_reads_legacy_plaintext(fernet_key: str) -> None:
    # Une valeur en clair déjà en base (avant migration) doit rester lisible.
    col = EncryptedText()
    assert col.process_result_value("diagnostic en clair legacy", None) == (
        "diagnostic en clair legacy"
    )
