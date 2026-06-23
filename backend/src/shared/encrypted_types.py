"""
Type SQLAlchemy `EncryptedText` — chiffrement transparent des champs PHI au
repos (RGPD), via Fernet.

- Écriture  : la valeur Python est chiffrée avant d'atteindre la base.
- Lecture   : la valeur en base est déchiffrée avant d'atteindre l'application.
- Legacy    : si la valeur en base n'est pas un token Fernet valide (donnée
              héritée en clair), elle est renvoyée telle quelle → migration
              progressive sans casse.

Le type est adossé à `Text` (impl) car un token Fernet est sensiblement plus
long que la valeur d'origine : les colonnes `VARCHAR(n)` doivent être migrées
en `TEXT` (cf. scripts/encrypt_phi.py).

Usage dans un modèle :

    diagnosis: Mapped[Optional[str]] = mapped_column(EncryptedText, nullable=True)

Aucun changement dans les endpoints : ils lisent/écrivent du texte clair, le
chiffrement est invisible.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from src.shared.encryption import decrypt_lenient, encrypt_field


class EncryptedText(TypeDecorator):
    """Colonne texte chiffrée au repos (Fernet), déchiffrée à la lecture."""

    impl = Text
    cache_ok = True

    def process_bind_param(
        self, value: Optional[str], dialect
    ) -> Optional[str]:
        # None et chaîne vide restent tels quels (pas de token pour du vide).
        if value is None or value == "":
            return value
        return encrypt_field(value)

    def process_result_value(
        self, value: Optional[str], dialect
    ) -> Optional[str]:
        if value is None or value == "":
            return value
        # Tolérant : déchiffre si chiffré, sinon renvoie le clair hérité.
        return decrypt_lenient(value)
