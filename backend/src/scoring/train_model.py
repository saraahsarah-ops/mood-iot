"""
Mood-IoT : Entrainement du modele XGBoost de scoring de risque
================================================================
Utilise les donnees du simulateur (donnees.csv) pour entrainer un modele
XGBoost qui predit le score de risque (0-100) a partir des Z-scores.

Flux :
  1. Charger donnees.csv (4 patientes x 21 jours = 84 lignes)
  2. Mapper les colonnes du simulateur vers le schema daily_aggregates
  3. Calculer les baselines (mean/std) sur les 7 premiers jours (baseline)
  4. Calculer les Z-scores pour chaque jour
  5. Construire les features (Z-scores + trend + is_weekend)
  6. Generer les labels de risque (0-100) via la progression simulee
  7. Entrainer XGBoost avec cross-validation
  8. Evaluer (RMSE, MAE, R2, classification en 4 niveaux)
  9. Sauvegarder le modele dans models/xgboost_risk_model.json

Usage :
  cd backend/src/scoring
  python train_model.py
"""

import csv
import math
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from statistics import mean, stdev

import numpy as np

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SIMULATEUR_CSV = Path(__file__).resolve().parent.parent.parent.parent / "simulateur" / "donnees.csv"
MODEL_OUTPUT = Path(__file__).resolve().parent.parent.parent / "models" / "xgboost_risk_model.json"
METRICS_OUTPUT = MODEL_OUTPUT.parent / "training_metrics.json"

# Mapping : colonnes simulateur -> metriques pipeline
COLUMN_MAP = {
    "battements_coeur":   "heart_rate_avg",
    "sommeil_heures":     "sleep_duration_min",  # heures -> minutes
    "pas":                "step_count",
    "nb_lieux_visites":   "gps_radius_km",       # proxy : nb lieux -> km
    "temps_ecran_heures": "screen_time_min",      # heures -> minutes
}

# Z-score feature names (must match pipeline ZSCORE_COLUMN_MAPPING)
ZSCORE_NAMES = {
    "heart_rate_avg":     "z_heart_rate",
    "sleep_duration_min": "z_sleep_duration",
    "step_count":         "z_step_count",
    "gps_radius_km":      "z_gps_radius",
    "screen_time_min":    "z_screen_time",
}

# Jours de baseline (1-7), rechute (8-21)
BASELINE_DAYS = 7
TOTAL_DAYS = 21

# Seuils de score (meme que pipeline)
THRESHOLDS = (40, 60, 80)


def classify_risk(score: float) -> str:
    if score < THRESHOLDS[0]:
        return "low"
    elif score < THRESHOLDS[1]:
        return "moderate"
    elif score < THRESHOLDS[2]:
        return "high"
    else:
        return "critical"


# ---------------------------------------------------------------------------
# 1. Charger et mapper les donnees du simulateur
# ---------------------------------------------------------------------------

def load_simulator_data() -> list[dict]:
    """Charge donnees.csv et convertit en format daily_aggregates."""
    print(f"[1/9] Chargement de {SIMULATEUR_CSV}...")

    if not SIMULATEUR_CSV.exists():
        print(f"  ERREUR : {SIMULATEUR_CSV} introuvable.")
        print(f"  Lancez d'abord : cd simulateur && python simulateur.py")
        sys.exit(1)

    rows = []
    with open(SIMULATEUR_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            mapped = {
                "patiente": row["patiente"],
                "jour": int(row["jour"]),
                "date": row["date"],
                "heart_rate_avg": float(row["battements_coeur"]),
                "sleep_duration_min": float(row["sommeil_heures"]) * 60,  # h -> min
                "step_count": float(row["pas"]),
                "gps_radius_km": float(row["nb_lieux_visites"]) * 1.5,   # proxy
                "screen_time_min": float(row["temps_ecran_heures"]) * 60, # h -> min
            }
            rows.append(mapped)

    patients = set(r["patiente"] for r in rows)
    print(f"  -> {len(rows)} lignes, {len(patients)} patientes: {patients}")
    return rows


# ---------------------------------------------------------------------------
# 2. Calculer les baselines par patiente (jours 1-7)
# ---------------------------------------------------------------------------

def compute_baselines(rows: list[dict]) -> dict:
    """Calcule mean/std pour chaque metrique sur les 7 premiers jours."""
    print("[2/9] Calcul des baselines (jours 1-7)...")

    metrics = ["heart_rate_avg", "sleep_duration_min", "step_count",
               "gps_radius_km", "screen_time_min"]
    patients = sorted(set(r["patiente"] for r in rows))
    baselines = {}

    for patient in patients:
        baseline_rows = [r for r in rows if r["patiente"] == patient and r["jour"] <= BASELINE_DAYS]
        baselines[patient] = {}
        for metric in metrics:
            values = [r[metric] for r in baseline_rows]
            m = mean(values)
            s = stdev(values) if len(values) > 1 else 1e-6
            s = max(s, 1e-6)  # eviter division par zero
            baselines[patient][metric] = {"mean": m, "std": s}

    for patient in patients:
        print(f"  {patient}:")
        for metric, stats in baselines[patient].items():
            print(f"    {metric:25s} mean={stats['mean']:8.2f}  std={stats['std']:6.2f}")

    return baselines


# ---------------------------------------------------------------------------
# 3. Calculer les Z-scores
# ---------------------------------------------------------------------------

def compute_zscores(rows: list[dict], baselines: dict) -> list[dict]:
    """Calcule les Z-scores pour chaque jour de chaque patiente."""
    print("[3/9] Calcul des Z-scores...")

    enriched = []
    for row in rows:
        patient = row["patiente"]
        bl = baselines[patient]
        features = {}

        for metric, z_name in ZSCORE_NAMES.items():
            val = row[metric]
            m = bl[metric]["mean"]
            s = bl[metric]["std"]
            z = (val - m) / s
            features[z_name] = round(z, 4)

        # Features que le pipeline genere mais que le simulateur n'a pas
        # -> on les derive des donnees existantes avec du bruit realiste
        # z_hrv : correle negativement avec heart_rate (quand HR monte, HRV baisse)
        features["z_hrv"] = round(-features["z_heart_rate"] * 0.8 + np.random.normal(0, 0.3), 4)
        # z_sleep_quality : correle avec sleep_duration (mauvais sommeil = courte duree)
        features["z_sleep_quality"] = round(features["z_sleep_duration"] * 0.7 + np.random.normal(0, 0.2), 4)
        # z_call_frequency : diminue en rechute (isolation sociale), correle avec step_count
        features["z_call_frequency"] = round(features["z_step_count"] * 0.5 + np.random.normal(0, 0.3), 4)

        features["trend_7d"] = 0.0
        features["trend_14d"] = 0.0
        features["is_weekend"] = 1.0 if date.fromisoformat(row["date"]).weekday() >= 5 else 0.0

        enriched.append({
            "patiente": patient,
            "jour": row["jour"],
            "date": row["date"],
            "features": features,
        })

    return enriched


# ---------------------------------------------------------------------------
# 4. Calculer les tendances (trend_7d, trend_14d)
# ---------------------------------------------------------------------------

def add_trends(enriched: list[dict], labels: dict):
    """Ajoute les tendances 7j et 14j basees sur les scores precedents."""
    print("[4/9] Calcul des tendances 7j/14j...")

    patients = sorted(set(r["patiente"] for r in enriched))

    for patient in patients:
        patient_rows = sorted(
            [r for r in enriched if r["patiente"] == patient],
            key=lambda x: x["jour"]
        )
        scores_so_far = []
        for row in patient_rows:
            key = (patient, row["jour"])
            score = labels.get(key, 0.0)
            scores_so_far.append(score)

            if len(scores_so_far) >= 2:
                # trend_7d
                window_7 = scores_so_far[-min(7, len(scores_so_far)):]
                if len(window_7) >= 2:
                    x = np.arange(len(window_7))
                    slope = np.polyfit(x, window_7, 1)[0]
                    row["features"]["trend_7d"] = round(float(slope), 4)

                # trend_14d
                window_14 = scores_so_far[-min(14, len(scores_so_far)):]
                if len(window_14) >= 2:
                    x = np.arange(len(window_14))
                    slope = np.polyfit(x, window_14, 1)[0]
                    row["features"]["trend_14d"] = round(float(slope), 4)


# ---------------------------------------------------------------------------
# 5. Generer les labels de risque
# ---------------------------------------------------------------------------

def generate_labels(rows: list[dict]) -> dict:
    """
    Genere un score de risque (0-100) pour chaque jour.

    Strategie :
      - Jours 1-7 (baseline) : score bas 5-25 (profil sain)
      - Jours 8-14 (debut rechute) : montee progressive 25-55
      - Jours 15-21 (rechute avancee) : score eleve 55-90
    """
    print("[5/9] Generation des labels de risque...")

    labels = {}
    patients = sorted(set(r["patiente"] for r in rows))

    for patient in patients:
        patient_rows = [r for r in rows if r["patiente"] == patient]
        for row in patient_rows:
            jour = row["jour"]

            if jour <= 7:
                # Baseline : score bas avec un peu de variation
                base = 10 + (jour - 1) * 2
                noise = np.random.uniform(-3, 3)
                score = max(2.0, min(35.0, base + noise))
            elif jour <= 14:
                # Transition : montee progressive
                t = (jour - 8) / 6.0  # 0 -> 1
                base = 25 + t * 30
                noise = np.random.uniform(-4, 4)
                score = max(20.0, min(65.0, base + noise))
            else:
                # Rechute : score eleve
                t = (jour - 15) / 6.0  # 0 -> 1
                base = 55 + t * 30
                noise = np.random.uniform(-5, 5)
                score = max(45.0, min(95.0, base + noise))

            labels[(patient, jour)] = round(score, 2)

    # Resume
    for patient in patients:
        scores_bl = [labels[(patient, j)] for j in range(1, 8)]
        scores_re = [labels[(patient, j)] for j in range(15, 22)]
        print(f"  {patient}: baseline avg={mean(scores_bl):.1f}, "
              f"rechute avg={mean(scores_re):.1f}")

    return labels


# ---------------------------------------------------------------------------
# 6. Construire X, y pour l'entrainement
# ---------------------------------------------------------------------------

def build_dataset(enriched: list[dict], labels: dict):
    """Construit les matrices X et y pour XGBoost."""
    print("[6/9] Construction du dataset X, y...")

    feature_names = sorted(enriched[0]["features"].keys())
    X = []
    y = []
    meta = []

    for row in enriched:
        key = (row["patiente"], row["jour"])
        if key in labels:
            x_row = [row["features"].get(f, 0.0) for f in feature_names]
            X.append(x_row)
            y.append(labels[key])
            meta.append(key)

    X = np.array(X, dtype=np.float64)
    y = np.array(y, dtype=np.float64)

    print(f"  -> X shape: {X.shape}, y shape: {y.shape}")
    print(f"  -> Features: {feature_names}")
    print(f"  -> y range: [{y.min():.1f}, {y.max():.1f}], mean={y.mean():.1f}")

    return X, y, feature_names, meta


# ---------------------------------------------------------------------------
# 7. Entrainer XGBoost avec cross-validation
# ---------------------------------------------------------------------------

def train_xgboost(X, y, feature_names):
    """Entraine un XGBRegressor avec 5-fold CV."""
    print("[7/9] Entrainement XGBoost...")

    try:
        import xgboost as xgb
        from sklearn.model_selection import cross_val_score, KFold
        from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    except ImportError as e:
        print(f"  ERREUR : {e}")
        print("  Installez : pip install xgboost scikit-learn")
        sys.exit(1)

    # Hyperparametres
    params = {
        "n_estimators": 200,
        "max_depth": 4,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "objective": "reg:squarederror",
        "random_state": 42,
    }

    model = xgb.XGBRegressor(**params)

    # Cross-validation 5-fold
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores_rmse = []
    cv_scores_mae = []

    print("  Cross-validation 5-fold :")
    for fold, (train_idx, val_idx) in enumerate(kf.split(X), 1):
        X_train, X_val = X[train_idx], X[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]

        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

        y_pred = model.predict(X_val)
        y_pred = np.clip(y_pred, 0, 100)

        rmse = np.sqrt(mean_squared_error(y_val, y_pred))
        mae = mean_absolute_error(y_val, y_pred)
        cv_scores_rmse.append(rmse)
        cv_scores_mae.append(mae)
        print(f"    Fold {fold}: RMSE={rmse:.2f}, MAE={mae:.2f}")

    print(f"  -> CV RMSE: {np.mean(cv_scores_rmse):.2f} (+/- {np.std(cv_scores_rmse):.2f})")
    print(f"  -> CV MAE:  {np.mean(cv_scores_mae):.2f} (+/- {np.std(cv_scores_mae):.2f})")

    # Entrainer le modele final sur toutes les donnees
    print("  Entrainement final sur toutes les donnees...")
    model.fit(X, y, verbose=False)
    y_pred_all = np.clip(model.predict(X), 0, 100)

    rmse_final = np.sqrt(mean_squared_error(y, y_pred_all))
    mae_final = mean_absolute_error(y, y_pred_all)
    r2_final = r2_score(y, y_pred_all)

    print(f"  -> Final: RMSE={rmse_final:.2f}, MAE={mae_final:.2f}, R2={r2_final:.4f}")

    # Feature importance
    importances = model.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]
    print("\n  Feature importance :")
    for i in sorted_idx:
        bar = "#" * int(importances[i] * 40)
        print(f"    {feature_names[i]:20s} {importances[i]:.4f}  {bar}")

    # Classification en 4 niveaux
    y_class_true = [classify_risk(s) for s in y]
    y_class_pred = [classify_risk(s) for s in y_pred_all]
    accuracy = sum(t == p for t, p in zip(y_class_true, y_class_pred)) / len(y)
    print(f"\n  Classification accuracy (4 niveaux): {accuracy:.1%}")

    # Matrice de confusion
    levels = ["low", "moderate", "high", "critical"]
    print(f"\n  {'':12s} {'Predicted':>40s}")
    print(f"  {'':12s}", end="")
    for l in levels:
        print(f" {l:>9s}", end="")
    print()
    for true_level in levels:
        print(f"  {true_level:12s}", end="")
        for pred_level in levels:
            count = sum(1 for t, p in zip(y_class_true, y_class_pred)
                        if t == true_level and p == pred_level)
            print(f" {count:>9d}", end="")
        print()

    metrics = {
        "cv_rmse_mean": round(float(np.mean(cv_scores_rmse)), 4),
        "cv_rmse_std": round(float(np.std(cv_scores_rmse)), 4),
        "cv_mae_mean": round(float(np.mean(cv_scores_mae)), 4),
        "final_rmse": round(float(rmse_final), 4),
        "final_mae": round(float(mae_final), 4),
        "final_r2": round(float(r2_final), 4),
        "classification_accuracy": round(float(accuracy), 4),
        "n_samples": int(len(y)),
        "n_features": int(X.shape[1]),
        "feature_names": feature_names,
        "feature_importances": {feature_names[i]: round(float(importances[i]), 4)
                                for i in sorted_idx},
        "hyperparameters": params,
        "trained_at": datetime.now().isoformat(),
    }

    return model, metrics


# ---------------------------------------------------------------------------
# 8. Sauvegarder le modele
# ---------------------------------------------------------------------------

def save_model(model, metrics):
    """Sauvegarde le modele XGBoost et les metriques."""
    print("[8/9] Sauvegarde du modele...")

    MODEL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(MODEL_OUTPUT))
    print(f"  -> Modele: {MODEL_OUTPUT}")

    with open(METRICS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"  -> Metriques: {METRICS_OUTPUT}")


# ---------------------------------------------------------------------------
# 9. Comparaison avec le modele heuristique
# ---------------------------------------------------------------------------

def compare_with_heuristic(enriched, labels):
    """Compare les scores heuristiques avec les labels reels."""
    print("[9/9] Comparaison heuristique vs labels...")

    WEIGHTS = {
        "z_sleep_duration": 0.20,
        "z_sleep_quality": 0.15,
        "z_heart_rate": 0.15,
        "z_hrv": 0.15,
        "z_step_count": 0.10,
        "z_gps_radius": 0.10,
        "z_screen_time": 0.10,
        "z_call_frequency": 0.05,
    }

    heuristic_scores = []
    true_scores = []

    for row in enriched:
        key = (row["patiente"], row["jour"])
        if key not in labels:
            continue

        fv = row["features"]
        weighted_sum = 0.0
        total_weight = 0.0

        for z_name, weight in WEIGHTS.items():
            z_val = fv.get(z_name)
            if z_val is not None:
                weighted_sum += abs(z_val) * weight
                total_weight += weight

        if total_weight > 0:
            mean_abs_z = weighted_sum / total_weight
            score = 100.0 / (1.0 + math.exp(-1.2 * (mean_abs_z - 1.5)))
        else:
            score = 50.0

        heuristic_scores.append(score)
        true_scores.append(labels[key])

    h = np.array(heuristic_scores)
    t = np.array(true_scores)

    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    rmse_h = np.sqrt(mean_squared_error(t, h))
    mae_h = mean_absolute_error(t, h)
    r2_h = r2_score(t, h)

    print(f"  Heuristique: RMSE={rmse_h:.2f}, MAE={mae_h:.2f}, R2={r2_h:.4f}")

    h_class = [classify_risk(s) for s in h]
    t_class = [classify_risk(s) for s in t]
    acc_h = sum(a == b for a, b in zip(h_class, t_class)) / len(t_class)
    print(f"  Heuristique accuracy (4 niveaux): {acc_h:.1%}")

    return {"rmse": round(float(rmse_h), 4), "mae": round(float(mae_h), 4),
            "r2": round(float(r2_h), 4), "accuracy": round(float(acc_h), 4)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("  MOOD-IOT : Entrainement XGBoost Risk Scoring Model")
    print("=" * 70)
    print()

    np.random.seed(42)

    # Pipeline
    rows = load_simulator_data()
    baselines = compute_baselines(rows)
    labels = generate_labels(rows)
    enriched = compute_zscores(rows, baselines)
    add_trends(enriched, labels)
    X, y, feature_names, meta = build_dataset(enriched, labels)
    model, metrics = train_xgboost(X, y, feature_names)
    save_model(model, metrics)

    print()
    heuristic_metrics = compare_with_heuristic(enriched, labels)

    # Resume final
    print()
    print("=" * 70)
    print("  RESUME")
    print("=" * 70)
    print(f"  XGBoost  -> RMSE={metrics['final_rmse']:.2f}, "
          f"R2={metrics['final_r2']:.4f}, "
          f"Accuracy={metrics['classification_accuracy']:.1%}")
    print(f"  Heurist. -> RMSE={heuristic_metrics['rmse']:.2f}, "
          f"R2={heuristic_metrics['r2']:.4f}, "
          f"Accuracy={heuristic_metrics['accuracy']:.1%}")

    if metrics['final_rmse'] < heuristic_metrics['rmse']:
        improvement = (1 - metrics['final_rmse'] / heuristic_metrics['rmse']) * 100
        print(f"\n  XGBoost gagne : {improvement:.1f}% meilleur que l'heuristique")
    else:
        print(f"\n  L'heuristique est meilleur. Verifier les donnees d'entrainement.")

    print(f"\n  Modele sauvegarde dans : {MODEL_OUTPUT}")
    print(f"  Le pipeline le chargera automatiquement au prochain demarrage.")
    print("=" * 70)


if __name__ == "__main__":
    main()
