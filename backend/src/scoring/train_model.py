"""
Mood-IoT : Entrainement du modele XGBoost de scoring de risque
================================================================
Utilise le dataset Depresjon (Simula Research Lab) — donnees cliniques
reelles d'actigraphie (55 patients, ~14 jours) avec scores MADRS.

Source : https://datasets.simula.no/depresjon/
Licence : CC BY 4.0 / CC0-1.0

Flux :
  1. Charger les CSV d'actigraphie (1 fichier/patient, 1 mesure/minute)
  2. Agreger par jour : activite moyenne, variance, sommeil, rythme circadien
  3. Mapper MADRS (0-60) -> score de risque (0-100)
  4. Calculer les baselines (mean/std) par patient
  5. Calculer les Z-scores pour chaque jour
  6. Construire les features (Z-scores + trend + is_weekend)
  7. Entrainer XGBoost avec cross-validation
  8. Evaluer (RMSE, MAE, R2, classification en 4 niveaux)
  9. Sauvegarder le modele dans models/xgboost_risk_model.json

Usage :
  cd backend
  python -m src.scoring.train_model
"""

import math
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean, stdev
from collections import defaultdict

import numpy as np

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "depresjon" / "data"
SCORES_CSV = DATA_DIR / "scores.csv"
MODEL_OUTPUT = Path(__file__).resolve().parent.parent.parent / "models" / "xgboost_risk_model.json"
METRICS_OUTPUT = MODEL_OUTPUT.parent / "training_metrics.json"

# Seuils de score (meme que pipeline)
THRESHOLDS = (40, 60, 80)

# Heures de "nuit" pour estimer sommeil (23h-7h)
NIGHT_START = 23
NIGHT_END = 7

# Features attendues par le pipeline (11 features, ordre alphabetique)
PIPELINE_FEATURES = sorted([
    "is_weekend", "trend_14d", "trend_7d",
    "z_call_frequency", "z_gps_radius", "z_heart_rate",
    "z_hrv", "z_screen_time", "z_sleep_duration",
    "z_sleep_quality", "z_step_count",
])


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
# 1. Charger les scores MADRS
# ---------------------------------------------------------------------------

def load_madrs_scores() -> dict:
    """Charge scores.csv et retourne {patient_id: {'madrs1': x, 'madrs2': y, 'days': n, 'group': str}}."""
    print(f"[1/9] Chargement des scores MADRS depuis {SCORES_CSV}...")

    import csv
    scores = {}
    with open(SCORES_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pid = row["number"].strip()
            group = "condition" if pid.startswith("condition") else "control"
            madrs1 = float(row["madrs1"]) if row["madrs1"].strip() not in ("NA", "") else 0.0
            madrs2 = float(row["madrs2"]) if row["madrs2"].strip() not in ("NA", "") else 0.0
            days = int(row["days"])
            scores[pid] = {
                "madrs1": madrs1,
                "madrs2": madrs2,
                "days": days,
                "group": group,
            }

    n_cond = sum(1 for v in scores.values() if v["group"] == "condition")
    n_ctrl = sum(1 for v in scores.values() if v["group"] == "control")
    print(f"  -> {len(scores)} patients ({n_cond} depresses, {n_ctrl} controles)")
    print(f"  -> MADRS condition: {[s['madrs1'] for s in scores.values() if s['group']=='condition']}")
    return scores


# ---------------------------------------------------------------------------
# 2. Charger et agreger les CSV d'actigraphie par jour
# ---------------------------------------------------------------------------

def load_and_aggregate_actigraphy(madrs_scores: dict) -> list[dict]:
    """
    Charge les CSV d'actigraphie et agrege par jour.

    A partir de l'activite par minute, on derive :
      - activity_mean    : activite moyenne du jour (proxy pas/step_count)
      - activity_std     : variabilite de l'activite (proxy HRV)
      - night_activity   : activite nocturne 23h-7h (proxy inverse de qualite sommeil)
      - sleep_proxy_min  : minutes avec activite=0 la nuit (proxy duree sommeil)
      - day_activity     : activite diurne 8h-22h (proxy mobilite/gps)
      - screen_proxy     : minutes avec faible activite diurne (proxy screen_time)
      - peak_hour_ratio  : ratio activite matin/apres-midi (proxy rythme circadien)
      - active_minutes   : minutes avec activite > 0 (proxy appels/interactions)
    """
    print("[2/9] Chargement et agregation de l'actigraphie par jour...")

    import csv
    all_rows = []
    patients_loaded = 0

    for pid, info in madrs_scores.items():
        group = info["group"]
        csv_path = DATA_DIR / group / f"{pid}.csv"
        if not csv_path.exists():
            print(f"  WARN: {csv_path} introuvable, skip")
            continue

        # Lire les donnees par minute
        daily = defaultdict(list)
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = row.get("timestamp", "")
                activity = row.get("activity", "0")
                if not ts or activity in ("", "NA"):
                    continue
                try:
                    dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                    act_val = float(activity)
                except (ValueError, TypeError):
                    continue
                daily[dt.date()].append((dt.hour, act_val))

        # Agreger par jour
        for day_date, minutes in sorted(daily.items()):
            if len(minutes) < 600:  # au moins 10h de donnees
                continue

            hours = [m[0] for m in minutes]
            activities = [m[1] for m in minutes]

            # Activite globale
            activity_mean = np.mean(activities)
            activity_std = np.std(activities) if len(activities) > 1 else 0.0

            # Nuit (23h-7h) : proxy sommeil
            night_acts = [a for h, a in minutes if h >= NIGHT_START or h < NIGHT_END]
            night_activity = np.mean(night_acts) if night_acts else 0.0
            sleep_proxy_min = sum(1 for a in night_acts if a == 0)  # minutes immobiles la nuit

            # Jour (8h-22h) : proxy mobilite
            day_acts = [a for h, a in minutes if NIGHT_END <= h < NIGHT_START]
            day_activity = np.mean(day_acts) if day_acts else 0.0

            # Screen proxy : minutes avec faible activite diurne (<50)
            screen_proxy = sum(1 for a in day_acts if 0 < a < 50)

            # Rythme circadien : matin (6-12) vs apres-midi (12-18)
            morning = [a for h, a in minutes if 6 <= h < 12]
            afternoon = [a for h, a in minutes if 12 <= h < 18]
            morning_avg = np.mean(morning) if morning else 0.0
            afternoon_avg = np.mean(afternoon) if afternoon else 1.0
            peak_ratio = morning_avg / max(afternoon_avg, 1.0)

            # Minutes actives (proxy interactions sociales)
            active_minutes = sum(1 for a in activities if a > 0)

            all_rows.append({
                "patient_id": pid,
                "date": day_date,
                "group": info["group"],
                "madrs1": info["madrs1"],
                "madrs2": info["madrs2"],
                # Metriques agregees
                "activity_mean": round(activity_mean, 2),
                "activity_std": round(activity_std, 2),
                "night_activity": round(night_activity, 2),
                "sleep_proxy_min": sleep_proxy_min,
                "day_activity": round(day_activity, 2),
                "screen_proxy": screen_proxy,
                "peak_ratio": round(peak_ratio, 4),
                "active_minutes": active_minutes,
            })

        patients_loaded += 1

    print(f"  -> {patients_loaded} patients charges, {len(all_rows)} jours-patients")
    return all_rows


# ---------------------------------------------------------------------------
# 3. Mapper les metriques vers le schema pipeline
# ---------------------------------------------------------------------------

def map_to_pipeline_metrics(rows: list[dict]) -> list[dict]:
    """
    Mappe les metriques d'actigraphie vers les colonnes du pipeline.

    Mapping :
      activity_mean   -> step_count (proxy : mouvement general)
      activity_std    -> heart_rate_variability (proxy : variabilite physiologique)
      night_activity  -> heart_rate_avg (proxy inverse : agitation nocturne)
      sleep_proxy_min -> sleep_duration_min
      day_activity    -> gps_radius_km (proxy : mobilite exterieure)
      screen_proxy    -> screen_time_min (proxy : sedentarite diurne)
      peak_ratio      -> sleep_quality_score (proxy : rythme circadien regulier)
      active_minutes  -> call_count (proxy : engagement social)
    """
    print("[3/9] Mapping des metriques vers le schema pipeline...")

    mapped = []
    for row in rows:
        mapped.append({
            "patient_id": row["patient_id"],
            "date": row["date"],
            "group": row["group"],
            "madrs1": row["madrs1"],
            "madrs2": row["madrs2"],
            # Metriques mappees
            "heart_rate_avg": row["night_activity"],     # agitation nocturne -> HR eleve = stress
            "heart_rate_variability": row["activity_std"],
            "sleep_duration_min": row["sleep_proxy_min"],
            "sleep_quality_score": row["peak_ratio"] * 10,  # normalise 0-10
            "step_count": row["activity_mean"],
            "gps_radius_km": row["day_activity"] / 100,     # normalise en km
            "screen_time_min": row["screen_proxy"],
            "call_count": row["active_minutes"] / 60,       # normalise en heures
        })

    print(f"  -> {len(mapped)} lignes mappees")
    return mapped


# ---------------------------------------------------------------------------
# 4. Calculer les baselines par patient
# ---------------------------------------------------------------------------

def compute_baselines(rows: list[dict]) -> dict:
    """Calcule mean/std pour chaque metrique sur toutes les donnees du patient."""
    print("[4/9] Calcul des baselines par patient...")

    metrics = ["heart_rate_avg", "heart_rate_variability", "sleep_duration_min",
               "sleep_quality_score", "step_count", "gps_radius_km",
               "screen_time_min", "call_count"]

    patients = sorted(set(r["patient_id"] for r in rows))
    baselines = {}

    for patient in patients:
        patient_rows = [r for r in rows if r["patient_id"] == patient]
        baselines[patient] = {}
        for metric in metrics:
            values = [r[metric] for r in patient_rows if r[metric] is not None]
            if len(values) < 2:
                baselines[patient][metric] = {"mean": 0.0, "std": 1e-6}
                continue
            m = mean(values)
            s = stdev(values)
            s = max(s, 1e-6)
            baselines[patient][metric] = {"mean": m, "std": s}

    print(f"  -> Baselines calculees pour {len(patients)} patients")
    return baselines


# ---------------------------------------------------------------------------
# 5. Calculer les Z-scores et features
# ---------------------------------------------------------------------------

METRIC_TO_ZSCORE = {
    "heart_rate_avg":           "z_heart_rate",
    "heart_rate_variability":   "z_hrv",
    "sleep_duration_min":       "z_sleep_duration",
    "sleep_quality_score":      "z_sleep_quality",
    "step_count":               "z_step_count",
    "gps_radius_km":            "z_gps_radius",
    "screen_time_min":          "z_screen_time",
    "call_count":               "z_call_frequency",
}


def compute_features(rows: list[dict], baselines: dict) -> list[dict]:
    """Calcule Z-scores + is_weekend pour chaque jour."""
    print("[5/9] Calcul des Z-scores et features...")

    enriched = []
    for row in rows:
        pid = row["patient_id"]
        bl = baselines[pid]
        features = {}

        for metric, z_name in METRIC_TO_ZSCORE.items():
            val = row[metric]
            m = bl[metric]["mean"]
            s = bl[metric]["std"]
            z = (val - m) / s
            features[z_name] = round(z, 4)

        features["trend_7d"] = 0.0
        features["trend_14d"] = 0.0
        features["is_weekend"] = 1.0 if row["date"].weekday() >= 5 else 0.0

        enriched.append({
            "patient_id": pid,
            "date": row["date"],
            "group": row["group"],
            "madrs1": row["madrs1"],
            "madrs2": row["madrs2"],
            "features": features,
        })

    return enriched


# ---------------------------------------------------------------------------
# 6. Generer les labels : MADRS -> score 0-100
# ---------------------------------------------------------------------------

def generate_labels(enriched: list[dict]) -> dict:
    """
    Convertit MADRS (0-60) en score de risque (0-100).

    MADRS :
      0-6   : normal          -> score 0-15
      7-19  : depression legere -> score 15-40
      20-34 : depression moderee -> score 40-70
      35-60 : depression severe  -> score 70-100

    Pour les controles (MADRS=0) : score bas avec variation naturelle.
    Pour les patients : interpolation MADRS1 -> MADRS2 sur les jours.
    """
    print("[6/9] Generation des labels (MADRS -> score 0-100)...")

    def madrs_to_score(madrs: float) -> float:
        """Conversion non-lineaire MADRS -> score 0-100."""
        if madrs <= 6:
            return (madrs / 6.0) * 15.0
        elif madrs <= 19:
            return 15.0 + ((madrs - 6.0) / 13.0) * 25.0
        elif madrs <= 34:
            return 40.0 + ((madrs - 19.0) / 15.0) * 30.0
        else:
            return 70.0 + ((madrs - 34.0) / 26.0) * 30.0

    labels = {}
    patients = sorted(set(r["patient_id"] for r in enriched))

    for patient in patients:
        patient_rows = sorted(
            [r for r in enriched if r["patient_id"] == patient],
            key=lambda x: x["date"]
        )
        n_days = len(patient_rows)
        madrs1 = patient_rows[0]["madrs1"]
        madrs2 = patient_rows[0]["madrs2"]

        for i, row in enumerate(patient_rows):
            # Interpolation lineaire entre MADRS debut et fin
            t = i / max(n_days - 1, 1)
            madrs_interp = madrs1 + (madrs2 - madrs1) * t

            # Convertir en score 0-100
            base_score = madrs_to_score(madrs_interp)

            # Ajouter variation quotidienne realiste (+/- 5)
            noise = np.random.normal(0, 3)
            score = np.clip(base_score + noise, 0, 100)

            labels[(patient, row["date"])] = round(float(score), 2)

    # Resume par groupe
    cond_scores = [v for k, v in labels.items() if k[0].startswith("condition")]
    ctrl_scores = [v for k, v in labels.items() if k[0].startswith("control")]
    print(f"  -> Condition : mean={np.mean(cond_scores):.1f}, "
          f"range=[{np.min(cond_scores):.0f}, {np.max(cond_scores):.0f}]")
    print(f"  -> Control   : mean={np.mean(ctrl_scores):.1f}, "
          f"range=[{np.min(ctrl_scores):.0f}, {np.max(ctrl_scores):.0f}]")

    return labels


# ---------------------------------------------------------------------------
# 7. Ajouter les tendances
# ---------------------------------------------------------------------------

def add_trends(enriched: list[dict], labels: dict):
    """Ajoute trend_7d et trend_14d bases sur l'evolution des scores."""
    print("[7/9] Calcul des tendances 7j/14j...")

    patients = sorted(set(r["patient_id"] for r in enriched))

    for patient in patients:
        patient_rows = sorted(
            [r for r in enriched if r["patient_id"] == patient],
            key=lambda x: x["date"]
        )
        scores_so_far = []
        for row in patient_rows:
            key = (patient, row["date"])
            score = labels.get(key, 0.0)
            scores_so_far.append(score)

            if len(scores_so_far) >= 2:
                window_7 = scores_so_far[-min(7, len(scores_so_far)):]
                if len(window_7) >= 2:
                    x = np.arange(len(window_7))
                    slope = np.polyfit(x, window_7, 1)[0]
                    row["features"]["trend_7d"] = round(float(slope), 4)

                window_14 = scores_so_far[-min(14, len(scores_so_far)):]
                if len(window_14) >= 2:
                    x = np.arange(len(window_14))
                    slope = np.polyfit(x, window_14, 1)[0]
                    row["features"]["trend_14d"] = round(float(slope), 4)


# ---------------------------------------------------------------------------
# 8. Construire dataset et entrainer
# ---------------------------------------------------------------------------

def build_dataset(enriched: list[dict], labels: dict):
    """Construit les matrices X, y."""
    print("[8/9] Construction du dataset et entrainement...")

    feature_names = PIPELINE_FEATURES
    X = []
    y = []

    for row in enriched:
        key = (row["patient_id"], row["date"])
        if key in labels:
            x_row = [row["features"].get(f, 0.0) for f in feature_names]
            X.append(x_row)
            y.append(labels[key])

    X = np.array(X, dtype=np.float64)
    y = np.array(y, dtype=np.float64)

    print(f"  -> X shape: {X.shape}, y shape: {y.shape}")
    print(f"  -> Features: {feature_names}")
    print(f"  -> y range: [{y.min():.1f}, {y.max():.1f}], mean={y.mean():.1f}")

    return X, y, feature_names


def train_xgboost(X, y, feature_names):
    """Entraine un XGBRegressor avec 5-fold CV."""
    try:
        import xgboost as xgb
        from sklearn.model_selection import KFold
        from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    except ImportError as e:
        print(f"  ERREUR : {e}")
        print("  Installez : pip install xgboost scikit-learn")
        sys.exit(1)

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
    cv_rmse = []
    cv_mae = []

    print("\n  Cross-validation 5-fold :")
    for fold, (train_idx, val_idx) in enumerate(kf.split(X), 1):
        X_tr, X_val = X[train_idx], X[val_idx]
        y_tr, y_val = y[train_idx], y[val_idx]

        model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
        y_pred = np.clip(model.predict(X_val), 0, 100)

        rmse = np.sqrt(mean_squared_error(y_val, y_pred))
        mae = mean_absolute_error(y_val, y_pred)
        cv_rmse.append(rmse)
        cv_mae.append(mae)
        print(f"    Fold {fold}: RMSE={rmse:.2f}, MAE={mae:.2f}")

    print(f"  -> CV RMSE: {np.mean(cv_rmse):.2f} (+/- {np.std(cv_rmse):.2f})")
    print(f"  -> CV MAE:  {np.mean(cv_mae):.2f} (+/- {np.std(cv_mae):.2f})")

    # Modele final
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

    # Classification 4 niveaux
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
        "dataset": "Depresjon (Simula Research Lab)",
        "dataset_url": "https://datasets.simula.no/depresjon/",
        "cv_rmse_mean": round(float(np.mean(cv_rmse)), 4),
        "cv_rmse_std": round(float(np.std(cv_rmse)), 4),
        "cv_mae_mean": round(float(np.mean(cv_mae)), 4),
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
        "label_source": "MADRS scores (clinician-rated)",
        "trained_at": datetime.now().isoformat(),
    }

    return model, metrics


# ---------------------------------------------------------------------------
# 9. Sauvegarde + comparaison heuristique
# ---------------------------------------------------------------------------

def save_model(model, metrics):
    """Sauvegarde le modele et les metriques."""
    print("[9/9] Sauvegarde du modele...")
    MODEL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(MODEL_OUTPUT))
    print(f"  -> Modele: {MODEL_OUTPUT}")

    with open(METRICS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"  -> Metriques: {METRICS_OUTPUT}")


def compare_with_heuristic(enriched, labels):
    """Compare le heuristique avec les labels."""
    print("\n  Comparaison avec le modele heuristique :")

    WEIGHTS = {
        "z_sleep_duration": 0.20, "z_sleep_quality": 0.15,
        "z_heart_rate": 0.15, "z_hrv": 0.15,
        "z_step_count": 0.10, "z_gps_radius": 0.10,
        "z_screen_time": 0.10, "z_call_frequency": 0.05,
    }

    h_scores, t_scores = [], []
    for row in enriched:
        key = (row["patient_id"], row["date"])
        if key not in labels:
            continue

        fv = row["features"]
        ws = sum(abs(fv.get(z, 0)) * w for z, w in WEIGHTS.items())
        tw = sum(WEIGHTS.values())
        maz = ws / tw
        score = 100.0 / (1.0 + math.exp(-1.2 * (maz - 1.5)))

        h_scores.append(score)
        t_scores.append(labels[key])

    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    h, t = np.array(h_scores), np.array(t_scores)
    rmse_h = np.sqrt(mean_squared_error(t, h))
    r2_h = r2_score(t, h)

    h_class = [classify_risk(s) for s in h]
    t_class = [classify_risk(s) for s in t]
    acc_h = sum(a == b for a, b in zip(h_class, t_class)) / len(t_class)

    print(f"  Heuristique: RMSE={rmse_h:.2f}, R2={r2_h:.4f}, Accuracy={acc_h:.1%}")
    return {"rmse": round(float(rmse_h), 4), "r2": round(float(r2_h), 4),
            "accuracy": round(float(acc_h), 4)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("  MOOD-IOT : Entrainement XGBoost — Dataset Depresjon (clinique)")
    print("=" * 70)
    print()

    np.random.seed(42)

    # Verifier que le dataset existe
    if not DATA_DIR.exists():
        print(f"ERREUR: Dataset non trouve dans {DATA_DIR}")
        print("Telechargez-le : kaggle datasets download -d arashnic/the-depression-dataset")
        sys.exit(1)

    # Pipeline
    madrs = load_madrs_scores()
    rows = load_and_aggregate_actigraphy(madrs)
    mapped = map_to_pipeline_metrics(rows)
    baselines = compute_baselines(mapped)
    enriched = compute_features(mapped, baselines)
    labels = generate_labels(enriched)
    add_trends(enriched, labels)
    X, y, feature_names = build_dataset(enriched, labels)
    model, metrics = train_xgboost(X, y, feature_names)
    save_model(model, metrics)

    heuristic_metrics = compare_with_heuristic(enriched, labels)

    # Resume
    print()
    print("=" * 70)
    print("  RESUME")
    print("=" * 70)
    print(f"  Dataset   : Depresjon (55 patients, donnees cliniques reelles)")
    print(f"  Samples   : {metrics['n_samples']}")
    print(f"  XGBoost   -> CV RMSE={metrics['cv_rmse_mean']:.2f}, "
          f"R2={metrics['final_r2']:.4f}, "
          f"Accuracy={metrics['classification_accuracy']:.1%}")
    print(f"  Heurist.  -> RMSE={heuristic_metrics['rmse']:.2f}, "
          f"R2={heuristic_metrics['r2']:.4f}, "
          f"Accuracy={heuristic_metrics['accuracy']:.1%}")

    if metrics['cv_rmse_mean'] < heuristic_metrics['rmse']:
        print(f"\n  XGBoost gagne sur la cross-validation!")
    else:
        print(f"\n  L'heuristique performe mieux. Considerer le mode hybride.")

    print(f"\n  Modele sauvegarde: {MODEL_OUTPUT}")
    print("=" * 70)


if __name__ == "__main__":
    main()
