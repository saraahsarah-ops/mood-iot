"""Tests unitaires — fonctions pures du pipeline de scoring (src/scoring/pipeline).

Couvre la logique de seuils d'alerte (40/60/80) et la génération de messages
SHAP, sans BD ni modèle ML.
"""
import pytest

from src.scoring.pipeline import _determine_alert_level, _generate_shap_message


class TestDetermineAlertLevel:
    @pytest.mark.parametrize(
        "score,niveau",
        [
            (0, 0), (20, 0), (39.9, 0),     # < 40 -> niveau 0
            (40, 1), (50, 1), (59.9, 1),    # 40-60 -> niveau 1
            (60, 2), (70, 2), (79.9, 2),    # 60-80 -> niveau 2
            (80, 3), (90, 3), (100, 3),     # >= 80 -> niveau 3
        ],
    )
    def test_seuils(self, score, niveau):
        assert _determine_alert_level(score) == niveau


class TestGenerateShapMessage:
    def test_dans_la_norme(self):
        msg = _generate_shap_message("sleep_duration_min", 0.3)
        assert isinstance(msg, str) and msg

    def test_valeur_elevee(self):
        msg = _generate_shap_message("sleep_duration_min", 2.5)
        assert isinstance(msg, str) and msg

    def test_valeur_basse(self):
        msg = _generate_shap_message("sleep_duration_min", -2.5)
        assert isinstance(msg, str) and msg

    def test_feature_inconnue_fallback(self):
        # Une feature sans template ne doit pas planter (repli générique).
        msg = _generate_shap_message("feature_inexistante", 2.0)
        assert isinstance(msg, str) and msg
