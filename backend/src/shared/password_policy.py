"""
Mood-IoT : Politique de mot de passe robuste.
Minimum 8 caracteres, 1 majuscule, 1 chiffre, 1 caractere special.
"""

import re


def validate_password_strength(password: str) -> None:
    """
    Valide la robustesse d'un mot de passe.
    Leve ValueError avec un message descriptif si le mot de passe est trop faible.
    """
    errors: list[str] = []

    if len(password) < 8:
        errors.append("au moins 8 caracteres")
    if not re.search(r"[A-Z]", password):
        errors.append("au moins une lettre majuscule")
    if not re.search(r"[0-9]", password):
        errors.append("au moins un chiffre")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", password):
        errors.append("au moins un caractere special (!@#$%...)")

    if errors:
        raise ValueError(
            "Le mot de passe doit contenir : " + ", ".join(errors)
        )
