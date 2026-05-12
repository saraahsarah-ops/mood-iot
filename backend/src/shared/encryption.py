"""
Mood-IoT : Chiffrement symetrique Fernet pour les champs sensibles (RGPD).
Utilise pour chiffrer le numero RPPS, le numero de licence, etc.
"""

import logging
from cryptography.fernet import Fernet, InvalidToken

from src.shared.config import settings

logger = logging.getLogger("mood_iot.encryption")

_fernet = None


def _get_fernet() -> Fernet:
    """Initialise le chiffrement Fernet a la demande."""
    global _fernet
    if _fernet is None:
        key = settings.ENCRYPTION_KEY
        if not key:
            raise RuntimeError(
                "ENCRYPTION_KEY non configuree. Generez une cle avec: "
                "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_field(value: str) -> str:
    """Chiffre une valeur texte et retourne le token base64."""
    if not value:
        return ""
    return _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_field(token: str) -> str:
    """Dechiffre un token Fernet et retourne la valeur originale."""
    if not token:
        return ""
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.error("Impossible de dechiffrer le champ — cle incorrecte ou donnees corrompues")
        return "[CHIFFREMENT INVALIDE]"
