"""Tests unitaires — politique de mot de passe (src/shared/password_policy)."""
import pytest

from src.shared.password_policy import validate_password_strength


class TestValidatePasswordStrength:
    def test_mot_de_passe_valide_ne_leve_rien(self):
        # Aucune exception attendue pour un mot de passe conforme.
        validate_password_strength("Abcdef1!")

    def test_trop_court(self):
        with pytest.raises(ValueError) as exc:
            validate_password_strength("Ab1!")
        assert "8 caracteres" in str(exc.value)

    def test_sans_majuscule(self):
        with pytest.raises(ValueError) as exc:
            validate_password_strength("abcdef1!")
        assert "majuscule" in str(exc.value)

    def test_sans_chiffre(self):
        with pytest.raises(ValueError) as exc:
            validate_password_strength("Abcdefg!")
        assert "chiffre" in str(exc.value)

    def test_sans_caractere_special(self):
        with pytest.raises(ValueError) as exc:
            validate_password_strength("Abcdefg1")
        assert "special" in str(exc.value)

    def test_cumule_plusieurs_erreurs(self):
        # "abc" : trop court + pas de majuscule + pas de chiffre + pas de spécial.
        with pytest.raises(ValueError) as exc:
            validate_password_strength("abc")
        msg = str(exc.value)
        assert "8 caracteres" in msg
        assert "majuscule" in msg
        assert "chiffre" in msg
        assert "special" in msg

    @pytest.mark.parametrize("pwd", ["Str0ng#Pass", "Aa1@aaaa", "ZZZ9!zzz"])
    def test_divers_mots_de_passe_valides(self, pwd):
        validate_password_strength(pwd)
