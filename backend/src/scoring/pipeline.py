"""
Mood-IoT : Pipeline de scoring ML pour l'evaluation du risque patient.

Ce module implementee le pipeline complet de calcul du score de risque (0-100)
a partir des donnees capteurs IoT agreges quotidiennement.

Flux du pipeline :
    1. Recuperer les agregats quotidiens (daily_aggregates) du patient
    2. Recuperer les baselines historiques du patient
    3. Calculer les Z-scores par rapport aux baselines
    4. Construire le vecteur de features (Z-scores + tendances)
    5. Prediction XGBoost → score 0-100
    6. Explication SHAP → features contributives
    7. Determiner le niveau d'alerte (0-3)
    8. Persister dans feature_vectors et risk_scores
    9. Retourner le resultat
"""

from __future__ import annotations

import json
import logging
import math
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import numpy as np
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.config import settings
from src.shared.database import AsyncSessionLocal
from src.shared.models import (
    DailyAggregate,
    Baseline,
    FeatureVector,
    RiskScore,
    ModelVersion,
)

# ── Logging ───────────────────────────────────────────────────────────────────

logger = logging.getLogger("mood-iot.scoring.pipeline")

# ── Constantes ────────────────────────────────────────────────────────────────

# Correspondance entre les colonnes daily_aggregates et les noms de metriques
# dans la table baselines (metric_name)
METRIC_MAPPING: dict[str, str] = {
    "heart_rate_avg": "heart_rate_avg",
    "heart_rate_variability": "heart_rate_variability",
    "sleep_duration_min": "sleep_duration_min",
    "sleep_quality_score": "sleep_quality_score",
    "step_count": "step_count",
    "gps_radius_km": "gps_radius_km",
    "screen_time_min": "screen_time_min",
    "call_count": "call_count",
}

# Correspondance entre les metriques et les noms de Z-scores dans feature_vectors
ZSCORE_COLUMN_MAPPING: dict[str, str] = {
    "heart_rate_avg": "z_heart_rate",
    "heart_rate_variability": "z_hrv",
    "sleep_duration_min": "z_sleep_duration",
    "sleep_quality_score": "z_sleep_quality",
    "step_count": "z_step_count",
    "gps_radius_km": "z_gps_radius",
    "screen_time_min": "z_screen_time",
    "call_count": "z_call_frequency",
}

# Poids pour le modele heuristique de repli (somme = 1.0)
HEURISTIC_WEIGHTS: dict[str, float] = {
    "z_sleep_duration": 0.20,
    "z_sleep_quality": 0.15,
    "z_heart_rate": 0.15,
    "z_hrv": 0.15,
    "z_step_count": 0.15,     # Aumentado (antes 0.10) para absorber colinealidad
    "z_gps_radius": 0.10,
    "z_screen_time": 0.05,    # Reducido (antes 0.10) para mitigar feature leakage
    "z_call_frequency": 0.05,
}

# ── Direction clinique : +1 = valeur haute = risque, -1 = valeur basse = risque
# Ex: sommeil reduit → risque, donc direction = -1 (un Z negatif = risque)
# Ex: screen_time eleve → risque, donc direction = +1 (un Z positif = risque)
CLINICAL_DIRECTION: dict[str, int] = {
    "z_sleep_duration": -1,   # dormir MOINS → risque
    "z_sleep_quality":  -1,   # qualite BASSE → risque
    "z_heart_rate":     +1,   # BPM ELEVE → risque / stress
    "z_hrv":            -1,   # HRV BAS → risque / stress
    "z_step_count":     -1,   # MOINS de pas → risque / inactivite
    "z_gps_radius":     -1,   # MOINS de mobilite → risque / isolation
    "z_screen_time":    +1,   # PLUS d'ecran → risque / sedentarite
    "z_call_frequency": -1,   # MOINS d'appels → risque / isolation
}

# ── Seuils cliniques absolus (valeurs brutes) ────────────────────────────
# Penalites supplementaires pour des valeurs objectivement mauvaises,
# meme si le patient a toujours eu de "mauvaises" baselines.
# Seuils cliniques a 3 niveaux : critique, modere, leger
# Basees sur recommandations OMS et litterature clinique psychiatrique
CLINICAL_THRESHOLDS = {
    "sleep_duration_min": [
        # OMS recommande 7-9h (420-540 min). < 6h est un facteur de risque.
        (lambda v: v < 240, 25),    # <4h  : critique  +25 pts
        (lambda v: v < 360, 15),    # <6h  : modere    +15 pts
        (lambda v: v < 420, 8),     # <7h  : leger     +8 pts
    ],
    "heart_rate_avg": [
        # FC repos normale : 60-80 BPM. >= 80 au repos = stress ou deconditionnement.
        (lambda v: v > 100, 18),    # >100 : critique  +18 pts (tachycardie)
        (lambda v: v > 90,  12),    # >90  : modere    +12 pts
        (lambda v: v >= 80, 6),     # >=80 : leger     +6 pts
    ],
    "step_count": [
        # OMS recommande 7000-8000 pas/jour. < 5000 = sedentaire.
        (lambda v: v < 500,  20),   # <500  : critique +20 pts (alite)
        (lambda v: v < 2000, 12),   # <2000 : modere   +12 pts
        (lambda v: v < 5000, 7),    # <5000 : leger    +7 pts (sedentaire)
    ],
    "screen_time_min": [
        # > 4h ecran associe a risque depressif dans la litterature
        (lambda v: v > 540, 15),    # >9h  : critique +15 pts
        (lambda v: v > 420, 10),    # >7h  : modere   +10 pts
        (lambda v: v > 300, 6),     # >5h  : leger    +6 pts
    ],
    "heart_rate_variability": [
        (lambda v: v is not None and v < 15, 12),   # HRV <15ms : +12 pts
        (lambda v: v is not None and v < 25, 6),    # HRV <25ms : +6 pts
    ],
    "sleep_quality_score": [
        (lambda v: v is not None and v < 3, 12),    # Qualite <3/10  : +12 pts
        (lambda v: v is not None and v < 5, 6),     # Qualite <5/10  : +6 pts
    ],
}

# Ecart-type minimal pour eviter la division par zero
MIN_STD = 1e-6

# Chemin local par defaut pour le modele XGBoost
DEFAULT_MODEL_PATH = Path("models/xgboost_risk_model.json")

# Seuils d'alerte depuis la configuration
_t1, _t2, _t3 = settings.scoring_thresholds_tuple  # (40, 60, 80)

# Version courante du modele heuristique
HEURISTIC_MODEL_VERSION = "heuristic-v1.0.0"

# Version + features du modèle XGBoost réentraîné (Depresjon, sans leakage).
# DOIT correspondre exactement à MODEL_FEATURES de train_model.py (ordre inclus).
XGBOOST_MODEL_VERSION = "xgboost-depresjon-v2"
MODEL_FEATURES = [
    "is_weekend",
    "trend_14d",
    "trend_7d",
    "z_sleep_duration",
    "z_sleep_quality",
    "z_step_count",
]

# Score HYBRIDE (cf. MODEL_DESIGN.md) : combine la déviation au baseline
# (heuristique direction-aware → détecte la RECHUTE) et le niveau clinique
# (modèle XGBoost/Depresjon). Poids dominant à l'heuristique car c'est elle qui
# capte le but du projet (rechute). Le modèle apporte le contexte de niveau.
HYBRID_MODEL_VERSION = "hybrid-heuristic+xgboost-v1"
HYBRID_HEUR_WEIGHT = 0.65  # 65 % heuristique (déviation) / 35 % modèle (niveau)

# Libellés FR des Z-scores pour exposer les déviations de façon lisible.
# +1 = la valeur haute est "bonne" ; -1 = la valeur basse est "à risque".
_ZSCORE_LABELS_FR = {
    "z_sleep_duration": "Sommeil",
    "z_sleep_quality": "Qualité du sommeil / rythme",
    "z_step_count": "Activité physique",
    "z_heart_rate": "Fréquence cardiaque",
    "z_hrv": "Variabilité cardiaque",
    "z_gps_radius": "Mobilité (déplacements)",
    "z_screen_time": "Temps d'écran",
    "z_call_frequency": "Interactions sociales",
}
# Seuil (en écarts-types) à partir duquel une déviation est jugée notable.
_DEVIATION_THRESHOLD = 1.0


def _readable_deviations(feature_vector: dict[str, float]) -> list[dict[str, Any]]:
    """
    Convertit les Z-scores en déviations lisibles par un clinicien.

    Couche 1 (cf. MODEL_DESIGN.md) : « ce patient s'écarte-t-il de SON normal ? ».
    Ex : z_sleep_duration = -2.3 → {label: "Sommeil", sigma: -2.3,
         direction: "below", notable: true, text: "Sommeil : 2.3σ sous l'habitude"}
    Trié par amplitude décroissante. Indépendant du modèle (pur écart au baseline).
    """
    out: list[dict[str, Any]] = []
    for z_name, label in _ZSCORE_LABELS_FR.items():
        z = feature_vector.get(z_name)
        if z is None:
            continue
        z = float(z)
        direction = "below" if z < 0 else "above"
        sense = "sous" if z < 0 else "au-dessus de"
        out.append({
            "metric": z_name,
            "label": label,
            "sigma": round(z, 2),
            "direction": direction,
            "notable": abs(z) >= _DEVIATION_THRESHOLD,
            "text": f"{label} : {abs(z):.1f}σ {sense} l'habitude du patient",
        })
    out.sort(key=lambda d: abs(d["sigma"]), reverse=True)
    return out

# ── Messages SHAP en francais ────────────────────────────────────────────────

# Modeles de messages explicatifs lisibles par les cliniciens
SHAP_MESSAGES_FR: dict[str, dict[str, str]] = {
    "z_heart_rate": {
        "high": "Frequence cardiaque elevee (+{sigma:.1f}\u03c3)",
        "low": "Frequence cardiaque basse ({sigma:.1f}\u03c3)",
        "normal": "Frequence cardiaque dans la norme",
    },
    "z_hrv": {
        "high": "Variabilite cardiaque anormalement elevee (+{sigma:.1f}\u03c3)",
        "low": "Variabilite cardiaque reduite ({sigma:.1f}\u03c3)",
        "normal": "Variabilite cardiaque normale",
    },
    "z_sleep_duration": {
        "high": "Sommeil excessif (+{sigma:.1f}\u03c3 par rapport a la baseline)",
        "low": "Sommeil reduit de {sigma_abs:.1f}\u03c3 par rapport a la baseline",
        "normal": "Duree de sommeil normale",
    },
    "z_sleep_quality": {
        "high": "Qualite de sommeil anormalement elevee (+{sigma:.1f}\u03c3)",
        "low": "Qualite de sommeil degradee ({sigma:.1f}\u03c3)",
        "normal": "Qualite de sommeil dans la norme",
    },
    "z_step_count": {
        "high": "Activite physique elevee (+{sigma:.1f}\u03c3)",
        "low": "Activite physique en baisse ({sigma:.1f}\u03c3)",
        "normal": "Activite physique normale",
    },
    "z_gps_radius": {
        "high": "Rayon de mobilite GPS elargi (+{sigma:.1f}\u03c3)",
        "low": "Mobilite GPS en baisse ({sigma:.1f}\u03c3)",
        "normal": "Mobilite GPS dans la norme",
    },
    "z_screen_time": {
        "high": "Temps d'ecran excessif (+{sigma:.1f}\u03c3)",
        "low": "Temps d'ecran reduit ({sigma:.1f}\u03c3)",
        "normal": "Temps d'ecran normal",
    },
    "z_call_frequency": {
        "high": "Frequence d'appels elevee (+{sigma:.1f}\u03c3)",
        "low": "Frequence d'appels en baisse ({sigma:.1f}\u03c3)",
        "normal": "Frequence d'appels normale",
    },
}


def _generate_shap_message(feature_name: str, z_value: float) -> str:
    """Generer un message explicatif en francais pour une feature donnee."""
    templates = SHAP_MESSAGES_FR.get(feature_name, {})
    sigma_abs = abs(z_value)

    if sigma_abs < 1.0:
        return templates.get("normal", f"{feature_name} dans la norme")

    if z_value > 0:
        return templates.get("high", f"{feature_name} eleve (+{z_value:.1f}\u03c3)").format(
            sigma=z_value, sigma_abs=sigma_abs
        )
    else:
        return templates.get("low", f"{feature_name} bas ({z_value:.1f}\u03c3)").format(
            sigma=z_value, sigma_abs=sigma_abs
        )


def _determine_alert_level(score: float) -> int:
    """
    Determiner le niveau d'alerte en fonction du score.

    Niveaux :
        0 : score < 40  (faible)
        1 : 40 <= score < 60  (modere)
        2 : 60 <= score < 80  (eleve)
        3 : score >= 80  (critique)
    """
    if score < _t1:
        return 0
    elif score < _t2:
        return 1
    elif score < _t3:
        return 2
    else:
        return 3


# ── Pipeline principal ────────────────────────────────────────────────────────


class ScoringPipeline:
    """
    Pipeline de scoring ML pour Mood-IoT.

    Charge un modele XGBoost depuis un chemin local (ou un modele heuristique
    de repli si aucun modele entraine n'est disponible), puis calcule le score
    de risque d'un patient a partir de ses donnees capteurs quotidiennes.
    """

    def __init__(self, model_path: Optional[Path] = None) -> None:
        """
        Initialiser le pipeline de scoring.

        Args:
            model_path: Chemin vers le fichier du modele XGBoost (.json).
                        Si None, utilise le chemin par defaut.
        """
        self._model_path = model_path or DEFAULT_MODEL_PATH
        self._model = None
        self._model_version: str = HEURISTIC_MODEL_VERSION
        self._use_heuristic: bool = True
        self._load_model()

    # ── Chargement du modele ──────────────────────────────────────────────

    def _load_model(self) -> None:
        """
        Charger le modele XGBoost depuis le disque.

        Si le fichier n'existe pas ou si XGBoost n'est pas installe,
        on bascule sur le modele heuristique de repli.
        """
        from src.shared.config import settings
        if settings.SCORING_DISABLE_XGBOOST:
            logger.info(
                "XGBoost desactive via SCORING_DISABLE_XGBOOST. "
                "Utilisation exclusive du modele heuristique."
            )
            self._use_heuristic = True
            self._model_version = HEURISTIC_MODEL_VERSION
            return

        if not self._model_path.exists():
            logger.warning(
                "Modele XGBoost introuvable a '%s'. "
                "Utilisation du modele heuristique de repli.",
                self._model_path,
            )
            self._use_heuristic = True
            return

        try:
            import xgboost as xgb

            model = xgb.XGBRegressor()
            model.load_model(str(self._model_path))
            self._model = model
            self._use_heuristic = False

            # Score HYBRIDE : heuristique (déviation/rechute) + modèle (niveau).
            # model_version le reflète honnêtement.
            self._model_version = HYBRID_MODEL_VERSION
            logger.info(
                "Modèle XGBoost chargé depuis '%s' — scoring HYBRIDE "
                "(heuristique + modèle, version: %s)",
                self._model_path,
                self._model_version,
            )
        except ImportError:
            logger.warning(
                "Le package xgboost n'est pas installe. "
                "Utilisation du modele heuristique de repli."
            )
            self._use_heuristic = True
        except Exception as exc:
            logger.error(
                "Erreur lors du chargement du modele XGBoost : %s. "
                "Basculement sur le modele heuristique.",
                exc,
            )
            self._use_heuristic = True

    # ── Etape 1 : Recuperer les agregats quotidiens ──────────────────────

    async def _fetch_daily_aggregates(
        self, patient_id: str, target_date: date, db: AsyncSession
    ) -> Optional[DailyAggregate]:
        """
        Recuperer les agregats quotidiens d'un patient pour une date donnee.

        Args:
            patient_id: Identifiant unique du patient.
            target_date: Date cible du scoring.
            db: Session asynchrone SQLAlchemy.

        Returns:
            L'objet DailyAggregate ou None si aucune donnee n'est disponible.
        """
        stmt = select(DailyAggregate).where(
            and_(
                DailyAggregate.patient_id == patient_id,
                DailyAggregate.date == target_date,
            )
        )
        result = await db.execute(stmt)
        aggregate = result.scalar_one_or_none()

        if aggregate is None:
            logger.warning(
                "Aucun agregat quotidien pour le patient %s a la date %s",
                patient_id,
                target_date,
            )
        return aggregate

    # ── Etape 2 : Recuperer les baselines ────────────────────────────────

    async def _fetch_baselines(
        self, patient_id: str, db: AsyncSession
    ) -> dict[str, dict[str, float]]:
        """
        Recuperer les baselines historiques d'un patient.

        Args:
            patient_id: Identifiant unique du patient.
            db: Session asynchrone SQLAlchemy.

        Returns:
            Dictionnaire {metric_name: {"mean": float, "std": float}}.
        """
        stmt = select(Baseline).where(Baseline.patient_id == patient_id)
        result = await db.execute(stmt)
        baselines_rows = result.scalars().all()

        baselines: dict[str, dict[str, float]] = {}
        for row in baselines_rows:
            baselines[row.metric_name] = {
                "mean": float(row.mean_value),
                "std": max(float(row.std_value), MIN_STD),
            }

        if not baselines:
            logger.warning(
                "Aucune baseline trouvee pour le patient %s", patient_id
            )
        return baselines

    # ── Etape 3 : Calculer les Z-scores ──────────────────────────────────

    def _compute_zscores(
        self,
        aggregate: DailyAggregate,
        baselines: dict[str, dict[str, float]],
    ) -> dict[str, float]:
        """
        Calculer les Z-scores pour chaque metrique capteur.

        Formule : z = (valeur_courante - baseline_mean) / baseline_std

        Args:
            aggregate: Agregats quotidiens du patient.
            baselines: Baselines historiques {metric: {mean, std}}.

        Returns:
            Dictionnaire {z_feature_name: z_value}.
        """
        zscores: dict[str, float] = {}

        for metric_col, metric_name in METRIC_MAPPING.items():
            current_value = getattr(aggregate, metric_col, None)
            if current_value is None:
                logger.debug("Metrique '%s' absente des agregats", metric_col)
                continue

            # -- Outlier Rejection --
            # Filtro básico de anomalías de hardware (Smartwatch error)
            if metric_col == "heart_rate_avg" and float(current_value) <= 30:
                logger.warning("Rejet de valeur aberrante pour heart_rate: %.1f", current_value)
                continue
            if metric_col == "sleep_duration_min" and float(current_value) <= 0:
                logger.warning("Rejet de valeur aberrante pour sleep: %.1f", current_value)
                continue
            if metric_col == "step_count" and float(current_value) < 0:
                continue
            # -----------------------

            baseline = baselines.get(metric_name)
            if baseline is None:
                logger.debug(
                    "Pas de baseline pour la metrique '%s'", metric_name
                )
                continue

            z = (float(current_value) - baseline["mean"]) / baseline["std"]
            z_col = ZSCORE_COLUMN_MAPPING[metric_col]
            zscores[z_col] = round(z, 4)

        return zscores

    # ── Etape 4 : Construire le vecteur de features ──────────────────────

    async def _build_feature_vector(
        self,
        patient_id: str,
        target_date: date,
        zscores: dict[str, float],
        db: AsyncSession,
    ) -> dict[str, float]:
        """
        Construire le vecteur de features complet (Z-scores + tendances).

        Inclut :
            - Les Z-scores de chaque metrique
            - trend_7d  : tendance du score sur 7 jours
            - trend_14d : tendance du score sur 14 jours
            - is_weekend : 1.0 si la date tombe un samedi ou dimanche

        Args:
            patient_id: Identifiant du patient.
            target_date: Date cible.
            zscores: Z-scores calcules a l'etape 3.
            db: Session asynchrone SQLAlchemy.

        Returns:
            Dictionnaire representant le vecteur de features complet.
        """
        vector: dict[str, float] = dict(zscores)

        # Calculer les tendances a partir des scores precedents
        trend_7d = await self._compute_trend(patient_id, target_date, days=7, db=db)
        trend_14d = await self._compute_trend(patient_id, target_date, days=14, db=db)

        vector["trend_7d"] = round(trend_7d, 4)
        vector["trend_14d"] = round(trend_14d, 4)

        # Indicateur week-end (samedi=5, dimanche=6)
        vector["is_weekend"] = 1.0 if target_date.weekday() >= 5 else 0.0

        return vector

    async def _compute_trend(
        self,
        patient_id: str,
        target_date: date,
        days: int,
        db: AsyncSession,
    ) -> float:
        """
        Calculer la tendance du score de risque sur les N derniers jours.

        Utilise une regression lineaire simple (pente) sur les scores
        precedents. Retourne 0.0 s'il n'y a pas assez de donnees.

        Args:
            patient_id: Identifiant du patient.
            target_date: Date cible (exclue du calcul).
            days: Nombre de jours de retrospective.
            db: Session asynchrone SQLAlchemy.

        Returns:
            Pente de la tendance (positif = aggravation, negatif = amelioration).
        """
        start_date = target_date - timedelta(days=days)
        stmt = (
            select(RiskScore.date, RiskScore.score)
            .where(
                and_(
                    RiskScore.patient_id == patient_id,
                    RiskScore.date >= start_date,
                    RiskScore.date < target_date,
                )
            )
            .order_by(RiskScore.date)
        )
        result = await db.execute(stmt)
        rows = result.all()

        if len(rows) < 2:
            return 0.0

        # Regression lineaire simple : pente = cov(x,y) / var(x)
        x = np.array([float(i) for i in range(len(rows))])
        y = np.array([float(row.score) for row in rows])

        x_mean = x.mean()
        y_mean = y.mean()
        variance = ((x - x_mean) ** 2).sum()

        if variance < MIN_STD:
            return 0.0

        slope = ((x - x_mean) * (y - y_mean)).sum() / variance
        return float(slope)

    # ── Etape 5 : Prediction du score (heuristique clinique) ──────────────

    def _predict_score(
        self,
        feature_vector: dict[str, float],
        raw_metrics: Optional[dict[str, float]] = None,
    ) -> tuple[float, float]:
        """
        Predire le score de risque via un modele hybride clinique.

        Combine :
          A) Moyenne ponderee direction-aware des Z-scores (deviation relative)
          B) Penalites cliniques absolues (valeurs objectivement dangereuses)
          C) Ajustement de tendance

        Args:
            feature_vector: Vecteur de features (Z-scores + trends).
            raw_metrics: Valeurs brutes du jour {metric_name: value}.

        Returns:
            Tuple (score 0-100, confiance 0-1).
        """
        # ── Couche 2 (modèle XGBoost) : NIVEAU clinique appris sur Depresjon ─
        # On le calcule SANS retourner tout de suite : il sera combiné avec
        # l'heuristique (Couche 1) pour former le score hybride final.
        model_score: Optional[float] = None
        if self._model is not None and not self._use_heuristic:
            try:
                x = np.array(
                    [[feature_vector.get(f, 0.0) for f in MODEL_FEATURES]],
                    dtype=np.float64,
                )
                model_score = max(0.0, min(100.0, float(self._model.predict(x)[0])))
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Prédiction XGBoost échouée, ignorée dans l'hybride : %s", exc
                )

        # ── Couche 1 (heuristique direction-aware) : DÉVIATION = rechute ──
        # ── A) Score base sur les Z-scores direction-aware ───────────────
        weighted_risk = 0.0
        total_weight = 0.0

        for z_name, weight in HEURISTIC_WEIGHTS.items():
            z_value = feature_vector.get(z_name)
            if z_value is None:
                continue

            direction = CLINICAL_DIRECTION.get(z_name, +1)
            # Contribution au risque : si le Z va dans la direction a risque,
            # c'est positif. Sinon c'est negatif (protecteur).
            # Ex: z_sleep_duration=-2.0, direction=-1 → risk_contribution = +2.0
            risk_contribution = z_value * direction
            # Seule la contribution positive (risque) est comptee.
            # Les valeurs protectrices reduisent le score (min 0).
            weighted_risk += max(0.0, risk_contribution) * weight
            total_weight += weight

        if total_weight < MIN_STD:
            logger.warning("Aucun Z-score disponible pour le calcul")
            base_score = 30.0
            confidence = 0.0
        else:
            mean_risk_z = weighted_risk / total_weight
            # Sigmoide : mean_risk_z=0 → ~17, =1 → ~38, =2 → ~65, =3 → ~85
            base_score = 100.0 / (1.0 + math.exp(-1.0 * (mean_risk_z - 1.8)))
            n_available = sum(
                1 for z in HEURISTIC_WEIGHTS if feature_vector.get(z) is not None
            )
            confidence = round(n_available / len(HEURISTIC_WEIGHTS) * 0.85, 3)

        # ── B) Penalites cliniques absolues ──────────────────────────────
        clinical_penalty = 0.0
        if raw_metrics:
            for metric_name, thresholds in CLINICAL_THRESHOLDS.items():
                value = raw_metrics.get(metric_name)
                if value is None:
                    continue
                for condition_fn, penalty in thresholds:
                    if condition_fn(value):
                        clinical_penalty += penalty
                        logger.debug(
                            "Penalite clinique +%d pour %s=%.1f",
                            penalty, metric_name, value,
                        )
                        break  # On prend seulement le seuil le plus severe

        # ── C) Bonus de comorbidite ──────────────────────────────────────
        # Quand plusieurs metriques sont simultanement mauvaises,
        # le risque est plus qu'additif (effet synergique)
        comorbidity_bonus = 0.0
        if raw_metrics:
            bad_count = 0
            core_metrics_bad = {
                "sleep_duration_min": lambda v: v < 420,    # <7h
                "heart_rate_avg":     lambda v: v >= 80,    # >=80 BPM
                "step_count":         lambda v: v < 5000,   # <5000 pas
                "screen_time_min":    lambda v: v > 300,    # >5h
            }
            for metric_name, is_bad_fn in core_metrics_bad.items():
                value = raw_metrics.get(metric_name)
                if value is not None and is_bad_fn(value):
                    bad_count += 1
            # 2 metriques mauvaises : +5, 3 : +12, 4 : +20
            if bad_count >= 4:
                comorbidity_bonus = 20.0
            elif bad_count >= 3:
                comorbidity_bonus = 12.0
            elif bad_count >= 2:
                comorbidity_bonus = 5.0
            if comorbidity_bonus > 0:
                logger.info(
                    "Bonus comorbidite +%.0f (%d metriques hors norme)",
                    comorbidity_bonus, bad_count,
                )

        # ── D) Ajustement de tendance (plafonne a ±10 pts) ────────────────
        trend_7d = feature_vector.get("trend_7d", 0.0)
        trend_14d = feature_vector.get("trend_14d", 0.0)
        raw_trend = (trend_7d * 0.7 + trend_14d * 0.3) * 1.0
        trend_adjustment = max(-10.0, min(10.0, raw_trend))

        # ── Score heuristique (Couche 1) ─────────────────────────────────
        heuristic_score = base_score + clinical_penalty + comorbidity_bonus + trend_adjustment
        heuristic_score = max(0.0, min(100.0, heuristic_score))

        # ── Score HYBRIDE : Couche 1 (déviation/rechute) + Couche 2 (niveau) ─
        if model_score is not None:
            score = (
                HYBRID_HEUR_WEIGHT * heuristic_score
                + (1.0 - HYBRID_HEUR_WEIGHT) * model_score
            )
            logger.info(
                "Score HYBRIDE: %.0f%% heuristique(%.1f) + %.0f%% modèle(%.1f) = %.1f",
                HYBRID_HEUR_WEIGHT * 100, heuristic_score,
                (1 - HYBRID_HEUR_WEIGHT) * 100, model_score, score,
            )
        else:
            score = heuristic_score
            logger.info(
                "Score heuristique seul: base_z=%.1f + clinical=%.1f + comorbid=%.1f + trend=%.1f = %.1f",
                base_score, clinical_penalty, comorbidity_bonus, trend_adjustment, heuristic_score,
            )

        score = round(max(0.0, min(100.0, score)), 2)
        return score, confidence

    def _estimate_confidence(self, feature_vector: dict[str, float]) -> float:
        """
        Estimer la confiance de la prediction selon la completude des features.

        Args:
            feature_vector: Vecteur de features.

        Returns:
            Score de confiance entre 0.0 et 1.0.
        """
        total_features = len(HEURISTIC_WEIGHTS) + 3  # Z-scores + trend_7d, trend_14d, is_weekend
        available = sum(1 for k in feature_vector if feature_vector[k] is not None)
        return min(available / total_features, 1.0)

    # ── Etape 6 : Explication SHAP ───────────────────────────────────────

    def _compute_shap_values(
        self, feature_vector: dict[str, float]
    ) -> list[dict[str, Any]]:
        """
        Calculer les valeurs SHAP pour expliquer la prediction.

        Si le modele XGBoost est charge et que le package shap est disponible,
        utilise TreeExplainer. Sinon, approxime les valeurs SHAP en utilisant
        la contribution ponderee de chaque feature dans le modele heuristique.

        Args:
            feature_vector: Vecteur de features.

        Returns:
            Liste de dictionnaires {feature, z_value, shap_value, message}.
        """
        # Essayer d'utiliser SHAP avec le modele XGBoost reel
        if not self._use_heuristic and self._model is not None:
            try:
                import shap

                feature_names = sorted(feature_vector.keys())
                X = np.array([[feature_vector.get(f, 0.0) for f in feature_names]])
                explainer = shap.TreeExplainer(self._model)
                shap_values_array = explainer.shap_values(X)[0]

                explanations = []
                for i, fname in enumerate(feature_names):
                    z_val = feature_vector.get(fname, 0.0)
                    sv = float(shap_values_array[i])
                    explanations.append({
                        "feature": fname,
                        "z_value": round(z_val, 4),
                        "shap_value": round(sv, 4),
                        "message": _generate_shap_message(fname, z_val),
                    })

                # Trier par importance absolue (les plus contributives en premier)
                explanations.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
                return explanations

            except ImportError:
                logger.info(
                    "Le package shap n'est pas installe. "
                    "Utilisation de l'approximation heuristique."
                )
            except Exception as exc:
                logger.error(
                    "Erreur lors du calcul SHAP : %s. "
                    "Utilisation de l'approximation heuristique.",
                    exc,
                )

        # Approximation heuristique des valeurs SHAP
        return self._approximate_shap_values(feature_vector)

    def _approximate_shap_values(
        self, feature_vector: dict[str, float]
    ) -> list[dict[str, Any]]:
        """
        Approximation des valeurs SHAP pour le modele heuristique.

        Chaque contribution est calculee comme : weight_i * |z_i| / total
        avec le signe du Z-score pour indiquer la direction.

        Args:
            feature_vector: Vecteur de features.

        Returns:
            Liste triee par importance absolue decroissante.
        """
        explanations = []

        for z_name, weight in HEURISTIC_WEIGHTS.items():
            z_value = feature_vector.get(z_name)
            if z_value is None:
                continue

            # Contribution approximee : poids * z_value
            approx_shap = weight * z_value
            explanations.append({
                "feature": z_name,
                "z_value": round(z_value, 4),
                "shap_value": round(approx_shap, 4),
                "message": _generate_shap_message(z_name, z_value),
            })

        # Ajouter les tendances si significatives
        for trend_name in ("trend_7d", "trend_14d"):
            trend_val = feature_vector.get(trend_name, 0.0)
            if abs(trend_val) > 0.5:
                explanations.append({
                    "feature": trend_name,
                    "z_value": round(trend_val, 4),
                    "shap_value": round(trend_val * 0.1, 4),
                    "message": (
                        f"Tendance {'a la hausse' if trend_val > 0 else 'a la baisse'} "
                        f"sur {'7' if '7' in trend_name else '14'} jours "
                        f"({'+' if trend_val > 0 else ''}{trend_val:.1f} pts/jour)"
                    ),
                })

        # Trier par importance absolue decroissante
        explanations.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
        return explanations

    # ── Etape 7-8 : Persister les resultats ──────────────────────────────

    async def _persist_feature_vector(
        self,
        patient_id: str,
        target_date: date,
        zscores: dict[str, float],
        feature_vector: dict[str, float],
        db: AsyncSession,
    ) -> str:
        """
        Persister le vecteur de features dans la base de donnees (UPSERT).

        Args:
            patient_id: Identifiant du patient.
            target_date: Date cible.
            zscores: Z-scores calcules.
            feature_vector: Vecteur complet.
            db: Session asynchrone.

        Returns:
            L'identifiant du vecteur de features.
        """
        # Check if a feature vector already exists for this patient+date
        existing = await db.execute(
            select(FeatureVector).where(
                and_(
                    FeatureVector.patient_id == patient_id,
                    FeatureVector.date == target_date,
                )
            )
        )
        fv = existing.scalar_one_or_none()

        if fv is None:
            fv_id = str(uuid4())
            fv = FeatureVector(
                id=fv_id,
                patient_id=patient_id,
                date=target_date,
            )
            db.add(fv)
        else:
            fv_id = str(fv.id)

        fv.z_heart_rate = zscores.get("z_heart_rate")
        fv.z_hrv = zscores.get("z_hrv")
        fv.z_sleep_duration = zscores.get("z_sleep_duration")
        fv.z_sleep_quality = zscores.get("z_sleep_quality")
        fv.z_step_count = zscores.get("z_step_count")
        fv.z_gps_radius = zscores.get("z_gps_radius")
        fv.z_screen_time = zscores.get("z_screen_time")
        fv.z_call_frequency = zscores.get("z_call_frequency")
        fv.trend_7d = feature_vector.get("trend_7d", 0.0)
        fv.trend_14d = feature_vector.get("trend_14d", 0.0)
        fv.is_weekend = feature_vector.get("is_weekend", 0.0)
        fv.vector_json = json.dumps(feature_vector)

        await db.flush()

        logger.debug(
            "Vecteur de features persiste (id=%s) pour patient %s a la date %s",
            fv_id,
            patient_id,
            target_date,
        )
        return fv_id

    async def _persist_risk_score(
        self,
        patient_id: str,
        target_date: date,
        score: float,
        alert_level: int,
        feature_vector_id: str,
        shap_values: list[dict[str, Any]],
        confidence: float,
        db: AsyncSession,
    ) -> str:
        """
        Persister le score de risque dans la base de donnees (UPSERT).

        Args:
            patient_id: Identifiant du patient.
            target_date: Date cible.
            score: Score de risque (0-100).
            alert_level: Niveau d'alerte (0-3).
            feature_vector_id: Identifiant du vecteur de features associe.
            shap_values: Valeurs SHAP en format JSON.
            confidence: Niveau de confiance (0-1).
            db: Session asynchrone.

        Returns:
            L'identifiant du score de risque.
        """
        # Check if a score already exists for this patient+date
        existing = await db.execute(
            select(RiskScore).where(
                and_(
                    RiskScore.patient_id == patient_id,
                    RiskScore.date == target_date,
                )
            )
        )
        risk_score = existing.scalar_one_or_none()

        if risk_score is None:
            score_id = str(uuid4())
            risk_score = RiskScore(
                id=score_id,
                patient_id=patient_id,
                date=target_date,
            )
            db.add(risk_score)
        else:
            score_id = str(risk_score.id)

        risk_score.score = score
        risk_score.alert_level = alert_level
        risk_score.model_version = self._model_version
        risk_score.feature_vector_id = feature_vector_id
        risk_score.shap_values = shap_values
        risk_score.confidence = confidence

        await db.flush()

        logger.info(
            "Score de risque persiste (id=%s) : patient=%s, score=%.2f, "
            "alerte=%d, confiance=%.3f",
            score_id,
            patient_id,
            score,
            alert_level,
            confidence,
        )
        return score_id

    # ── Point d'entree principal ─────────────────────────────────────────

    async def compute_score(
        self,
        patient_id: str,
        target_date: date,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """
        Calculer le score de risque complet pour un patient a une date donnee.

        Execute le pipeline complet :
            1. Recuperation des agregats quotidiens
            2. Recuperation des baselines
            3. Calcul des Z-scores
            4. Construction du vecteur de features
            5. Prediction du score
            6. Calcul des explications SHAP
            7. Determination du niveau d'alerte
            8. Persistance des resultats

        Args:
            patient_id: Identifiant unique du patient.
            target_date: Date pour laquelle calculer le score.
            db: Session asynchrone SQLAlchemy.

        Returns:
            Dictionnaire contenant :
                - score_id: Identifiant du score
                - patient_id: Identifiant du patient
                - date: Date du scoring
                - score: Score de risque (0-100)
                - alert_level: Niveau d'alerte (0-3)
                - model_version: Version du modele utilise
                - confidence: Confiance de la prediction (0-1)
                - feature_vector_id: Identifiant du vecteur de features
                - shap_explanations: Liste des explications SHAP
                - top_features: Top 3 features contributives avec messages FR

        Raises:
            ValueError: Si aucune donnee n'est disponible pour le patient.
        """
        logger.info(
            "Demarrage du pipeline de scoring pour patient=%s, date=%s",
            patient_id,
            target_date,
        )

        # Etape 1 : Recuperer les agregats quotidiens
        aggregate = await self._fetch_daily_aggregates(patient_id, target_date, db)
        if aggregate is None:
            raise ValueError(
                f"Aucune donnee disponible pour le patient {patient_id} "
                f"a la date {target_date}. Le scoring ne peut pas etre effectue."
            )

        # Etape 2 : Recuperer les baselines
        baselines = await self._fetch_baselines(patient_id, db)
        if not baselines:
            raise ValueError(
                f"Aucune baseline disponible pour le patient {patient_id}. "
                f"Le scoring necessite des donnees historiques."
            )

        # Etape 3 : Calculer les Z-scores
        zscores = self._compute_zscores(aggregate, baselines)
        if not zscores:
            raise ValueError(
                f"Impossible de calculer les Z-scores pour le patient {patient_id}. "
                f"Verifier la correspondance entre agregats et baselines."
            )

        logger.debug("Z-scores calcules : %s", zscores)

        # Etape 4 : Construire le vecteur de features
        feature_vector = await self._build_feature_vector(
            patient_id, target_date, zscores, db
        )
        logger.debug("Vecteur de features : %s", feature_vector)

        # Extraire les valeurs brutes pour les seuils cliniques absolus
        raw_metrics = {}
        for metric_col in METRIC_MAPPING:
            val = getattr(aggregate, metric_col, None)
            if val is not None:
                raw_metrics[metric_col] = float(val)

        # Etape 5 : Prediction du score
        score, confidence = self._predict_score(feature_vector, raw_metrics)

        # Etape 6 : Explication SHAP
        shap_explanations = self._compute_shap_values(feature_vector)

        # Etape 7 : Determination du niveau d'alerte
        alert_level = _determine_alert_level(score)

        # Etape 8 : Persistance
        feature_vector_id = await self._persist_feature_vector(
            patient_id, target_date, zscores, feature_vector, db
        )
        score_id = await self._persist_risk_score(
            patient_id,
            target_date,
            score,
            alert_level,
            feature_vector_id,
            shap_explanations,
            confidence,
            db,
        )

        await db.commit()

        # Etape 9 : Retourner le resultat
        top_features = shap_explanations[:3]
        result = {
            "score_id": score_id,
            "patient_id": patient_id,
            "date": target_date.isoformat(),
            "score": score,
            "alert_level": alert_level,
            "model_version": self._model_version,
            "confidence": confidence,
            "feature_vector_id": feature_vector_id,
            "shap_explanations": shap_explanations,
            "top_features": [
                {"feature": f["feature"], "message": f["message"]}
                for f in top_features
            ],
        }

        logger.info(
            "Pipeline termine pour patient=%s : score=%.2f, alerte=%d, "
            "top_features=%s",
            patient_id,
            score,
            alert_level,
            [f["feature"] for f in top_features],
        )

        return result

    # ── Explication a posteriori d'un score existant ─────────────────────

    async def explain_score(
        self,
        score_id: str,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """
        Obtenir l'explication detaillee d'un score de risque existant.

        Recupere le score et son vecteur de features associe depuis la base,
        puis regenere les explications SHAP avec des messages en francais.

        Args:
            score_id: Identifiant du score de risque.
            db: Session asynchrone SQLAlchemy.

        Returns:
            Dictionnaire contenant :
                - score_id: Identifiant du score
                - patient_id: Identifiant du patient
                - date: Date du scoring
                - score: Score de risque
                - alert_level: Niveau d'alerte
                - shap_explanations: Liste complete des explications
                - top_features: Top 3 features avec messages FR
                - summary_fr: Resume en francais

        Raises:
            ValueError: Si le score_id est introuvable.
        """
        logger.info("Explication demandee pour score_id=%s", score_id)

        # Recuperer le score existant
        stmt = select(RiskScore).where(RiskScore.id == score_id)
        result = await db.execute(stmt)
        risk_score = result.scalar_one_or_none()

        if risk_score is None:
            raise ValueError(f"Score introuvable avec l'identifiant {score_id}")

        # Charger le vecteur de features (toujours, pour exposer les déviations
        # Z-score lisibles — cf. Couche 1, MODEL_DESIGN.md).
        feature_vector: dict[str, float] = {}
        fv_stmt = select(FeatureVector).where(
            FeatureVector.id == risk_score.feature_vector_id
        )
        fv_result = await db.execute(fv_stmt)
        feature_vector_obj = fv_result.scalar_one_or_none()
        if feature_vector_obj is not None:
            feature_vector = json.loads(feature_vector_obj.vector_json)

        # Si les valeurs SHAP sont deja stockees, les reutiliser
        if risk_score.shap_values:
            shap_explanations = risk_score.shap_values
        elif feature_vector:
            shap_explanations = self._compute_shap_values(feature_vector)
        else:
            raise ValueError(
                f"Vecteur de features introuvable pour le score {score_id}"
            )

        top_features = shap_explanations[:3] if shap_explanations else []
        deviations = _readable_deviations(feature_vector)

        # Generer le resume en francais
        summary_fr = self._generate_summary_fr(
            risk_score.score, risk_score.alert_level, top_features
        )

        return {
            "score_id": score_id,
            "patient_id": risk_score.patient_id,
            "date": risk_score.date.isoformat() if risk_score.date else None,
            "score": risk_score.score,
            "alert_level": risk_score.alert_level,
            "model_version": risk_score.model_version,
            "confidence": risk_score.confidence,
            "shap_explanations": shap_explanations,
            "top_features": [
                {"feature": f["feature"], "message": f["message"]}
                for f in top_features
            ],
            # Couche 1 : déviations du baseline individuel (Z-score), lisibles.
            # Rend tangible « ce patient s'écarte de SON normal » (rechute).
            "deviations": deviations,
            "summary_fr": summary_fr,
        }

    def _generate_summary_fr(
        self,
        score: float,
        alert_level: int,
        top_features: list[dict[str, Any]],
    ) -> str:
        """
        Generer un resume en francais de l'analyse de risque.

        Args:
            score: Score de risque.
            alert_level: Niveau d'alerte.
            top_features: Top features contributives.

        Returns:
            Resume lisible en francais.
        """
        level_labels = {
            0: "faible",
            1: "modere",
            2: "eleve",
            3: "critique",
        }
        level_str = level_labels.get(alert_level, "inconnu")

        summary = (
            f"Score de risque : {score:.1f}/100 (niveau {level_str}). "
        )

        if top_features:
            summary += "Principaux facteurs : "
            messages = [f["message"] for f in top_features[:3]]
            summary += " ; ".join(messages) + "."

        return summary


# ── Instance globale du pipeline ──────────────────────────────────────────────

# Initialisation paresseuse pour permettre la configuration avant le chargement
_pipeline_instance: Optional[ScoringPipeline] = None


def get_pipeline(model_path: Optional[Path] = None) -> ScoringPipeline:
    """
    Obtenir l'instance globale du pipeline de scoring.

    Cree l'instance au premier appel (initialisation paresseuse).

    Args:
        model_path: Chemin optionnel vers le modele XGBoost.

    Returns:
        Instance du ScoringPipeline.
    """
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = ScoringPipeline(model_path=model_path)
    return _pipeline_instance
