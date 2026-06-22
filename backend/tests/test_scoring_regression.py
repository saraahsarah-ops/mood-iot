"""
Tests de régression de la COUCHE 1 (heuristique direction-aware) du scoring.

Ces tests vérifient la mécanique pure de l'heuristique (Z-scores, pénalités
cliniques, comorbidité, tendance). Ils forcent volontairement le mode
heuristique : en production, `ScoringPipeline()` charge l'artefact XGBoost s'il
est présent et bascule sur un score HYBRIDE (0.65 heuristique + 0.35 modèle).
Charger ou non le modèle dépend de l'environnement (présence de l'artefact,
version d'xgboost), ce qui rendrait ces assertions non déterministes. On isole
donc la couche heuristique pour la tester seule.
"""

import pytest

from src.scoring.pipeline import ScoringPipeline


@pytest.fixture
def heuristic_pipeline() -> ScoringPipeline:
    """Pipeline forcé en mode heuristique seul (Couche 1 isolée)."""
    pipeline = ScoringPipeline()
    # Neutralise la Couche 2 (modèle) quel que soit l'artefact chargé.
    pipeline._model = None
    pipeline._use_heuristic = True
    return pipeline


def test_heuristic_predict_score_normal(heuristic_pipeline: ScoringPipeline):
    feature_vector = {
        "z_sleep_duration": 0.0,
        "z_sleep_quality": 0.0,
        "z_heart_rate": 0.0,
        "z_hrv": 0.0,
        "z_step_count": 0.0,
        "z_gps_radius": 0.0,
        "z_screen_time": 0.0,
        "z_call_frequency": 0.0,
        "trend_7d": 0.0,
        "trend_14d": 0.0,
    }
    raw_metrics = {
        "sleep_duration_min": 480,  # 8h
        "heart_rate_avg": 70,
        "step_count": 8000,
        "screen_time_min": 120,
    }

    score, confidence = heuristic_pipeline._predict_score(feature_vector, raw_metrics)

    # Sigmoid of -1.8 is approx 0.1418 -> 100 * 0.1418 = ~14.18 (Base score)
    # No clinical penalties, no comorbidity, no trend.
    assert 14.0 <= score <= 15.0
    assert confidence == 0.85  # all 8 features present


def test_heuristic_predict_score_critical(heuristic_pipeline: ScoringPipeline):
    # High risk direction values
    feature_vector = {
        "z_sleep_duration": -2.0,  # -2 std
        "z_heart_rate": 2.0,       # +2 std
        "z_step_count": -3.0,      # -3 std
        "z_screen_time": 3.0,      # +3 std
        "trend_7d": 5.0,           # worsening 5 pts/day
        "trend_14d": 2.0,
    }
    raw_metrics = {
        "sleep_duration_min": 200,  # < 4h -> +25 penalty AND comorbidity count 1
        "heart_rate_avg": 110,      # > 100 -> +18 penalty AND comorbidity count 2
        "step_count": 400,          # < 500 -> +20 penalty AND comorbidity count 3
        "screen_time_min": 600,     # > 540 -> +15 penalty AND comorbidity count 4
    }

    score, confidence = heuristic_pipeline._predict_score(feature_vector, raw_metrics)

    # Penalties: 25 + 18 + 20 + 15 = 78
    # Comorbidity: 4 bad metrics -> +20 bonus
    # Trend: 5.0 * 0.7 + 2.0 * 0.3 = 4.1 -> +4.1
    # Base Score: Positive z-scores mapped to risk -> near 100%
    # Total should max out at 100.0
    assert score == 100.0


def test_heuristic_approximate_shap(heuristic_pipeline: ScoringPipeline):
    feature_vector = {
        "z_heart_rate": 1.0,
        "trend_7d": 2.0,
    }

    shap_vals = heuristic_pipeline._approximate_shap_values(feature_vector)
    # Heart rate weight is 0.15 -> 0.15 * 1.0 = 0.15
    # Trend 7d is 2.0 * 0.1 = 0.2

    shap_features = {s["feature"]: s["shap_value"] for s in shap_vals}
    assert shap_features["z_heart_rate"] == 0.15
    assert shap_features["trend_7d"] == 0.20
