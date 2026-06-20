"""
Mood-IoT : Entrainement du modele XGBoost de scoring de risque (v2 — honnête)
============================================================================
Dataset : Depresjon (Simula Research Lab) — actigraphie clinique réelle de
55 patients (~14 jours), étiquetée par scores MADRS (cotés par un clinicien).
Source : https://datasets.simula.no/depresjon/  ·  Licence : CC BY 4.0 / CC0

CHANGEMENTS vs v1 (cf. AUDIT_FINDINGS.md §2) — corrige 3 défauts méthodologiques :
  1. PAS de mapping inventé : on n'invente plus heart_rate/HRV/GPS à partir de
     l'actigraphie. On entraîne UNIQUEMENT sur les signaux réellement présents
     (activité, sommeil, rythme circadien). 6 features honnêtes au lieu de 11.
  2. PAS de bruit synthétique : les labels = MADRS interpolé (sans np.random).
  3. PAS de data leakage : les tendances (trend_7d/14d) sont calculées sur
     l'ACTIVITÉ (z_step_count), jamais sur le label. + validation GroupKFold
     par patient (pas de fuite inter-jours d'un même patient) et test set
     holdout indépendant pour des métriques honnêtes.

Flux :
  1. Charger scores MADRS + actigraphie (1 mesure/minute)
  2. Agréger par jour : activité, sommeil (inactivité nocturne), rythme circadien
  3. Baselines (mean/std) par patient → Z-scores
  4. Labels : MADRS (0-60) → risque (0-100), interpolé, SANS bruit
  5. Tendances calculées sur l'activité (anti-leakage)
  6. Split PAR PATIENT (train/test holdout) + GroupKFold CV sur le train
  7. Entraîner XGBoost, évaluer sur le TEST set (patients jamais vus)
  8. Sauvegarder modèle + métriques honnêtes

Usage :
  cd backend && python -m src.scoring.train_model
"""

import json
import sys
from datetime import datetime
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

THRESHOLDS = (40, 60, 80)
NIGHT_START = 23  # heures de "nuit" pour estimer le sommeil (23h-7h)
NIGHT_END = 7

# Part des PATIENTS réservée au test holdout (jamais vus à l'entraînement)
TEST_PATIENT_FRACTION = 0.2
RANDOM_SEED = 42

# ── Features du modèle (6, honnêtes — uniquement dérivées de l'actigraphie) ──
# Ces 3 z-scores correspondent à des signaux que Health Connect fournit AUSSI
# en production (pas → activité, sommeil, qualité/rythme) → cohérence train/infér.
# trend_* sont calculées sur l'activité (pas sur le label) → pas de leakage.
MODEL_FEATURES = sorted([
    "is_weekend",
    "trend_7d",
    "trend_14d",
    "z_step_count",       # activité (Depresjon: activity_mean ; prod: steps)
    "z_sleep_duration",   # sommeil  (Depresjon: inactivité nocturne ; prod: sleep)
    "z_sleep_quality",    # rythme circadien (Depresjon: peak_ratio ; prod: qualité)
])


def classify_risk(score: float) -> str:
    if score < THRESHOLDS[0]:
        return "low"
    elif score < THRESHOLDS[1]:
        return "moderate"
    elif score < THRESHOLDS[2]:
        return "high"
    return "critical"


# ---------------------------------------------------------------------------
# 1. Charger les scores MADRS
# ---------------------------------------------------------------------------

def load_madrs_scores() -> dict:
    """Charge scores.csv → {pid: {madrs1, madrs2, days, group}}."""
    print(f"[1/8] Chargement des scores MADRS depuis {SCORES_CSV}...")
    import csv

    scores = {}
    with open(SCORES_CSV, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = row["number"].strip()
            group = "condition" if pid.startswith("condition") else "control"
            madrs1 = float(row["madrs1"]) if row["madrs1"].strip() not in ("NA", "") else 0.0
            madrs2 = float(row["madrs2"]) if row["madrs2"].strip() not in ("NA", "") else 0.0
            scores[pid] = {
                "madrs1": madrs1,
                "madrs2": madrs2,
                "days": int(row["days"]) if row["days"].strip() not in ("NA", "") else 0,
                "group": group,
            }

    n_cond = sum(1 for v in scores.values() if v["group"] == "condition")
    n_ctrl = sum(1 for v in scores.values() if v["group"] == "control")
    print(f"  -> {len(scores)} patients ({n_cond} déprimés, {n_ctrl} contrôles)")
    return scores


# ---------------------------------------------------------------------------
# 2. Charger et agréger l'actigraphie par jour (signaux RÉELS uniquement)
# ---------------------------------------------------------------------------

def load_and_aggregate_actigraphy(madrs_scores: dict) -> list[dict]:
    """
    Agrège l'actigraphie par jour. On ne dérive QUE des signaux réels :
      - activity_mean   : activité moyenne (proxy direct du niveau d'activité/pas)
      - sleep_proxy_min : minutes immobiles la nuit (proxy durée de sommeil)
      - peak_ratio      : ratio activité matin/après-midi (proxy rythme circadien)
    Aucune invention de fréquence cardiaque / HRV / GPS.
    """
    print("[2/8] Agrégation de l'actigraphie par jour...")
    import csv

    all_rows = []
    patients_loaded = 0

    for pid, info in madrs_scores.items():
        csv_path = DATA_DIR / info["group"] / f"{pid}.csv"
        if not csv_path.exists():
            print(f"  WARN: {csv_path} introuvable, skip")
            continue

        daily = defaultdict(list)
        with open(csv_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
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

        for day_date, minutes in sorted(daily.items()):
            if len(minutes) < 600:  # au moins ~10h de données ce jour
                continue

            activities = [a for _, a in minutes]
            activity_mean = float(np.mean(activities))

            # Sommeil : minutes immobiles entre 23h et 7h
            night_acts = [a for h, a in minutes if h >= NIGHT_START or h < NIGHT_END]
            sleep_proxy_min = sum(1 for a in night_acts if a == 0)

            # Rythme circadien : activité matin (6-12) vs après-midi (12-18)
            morning = [a for h, a in minutes if 6 <= h < 12]
            afternoon = [a for h, a in minutes if 12 <= h < 18]
            morning_avg = float(np.mean(morning)) if morning else 0.0
            afternoon_avg = float(np.mean(afternoon)) if afternoon else 1.0
            peak_ratio = morning_avg / max(afternoon_avg, 1.0)

            all_rows.append({
                "patient_id": pid,
                "date": day_date,
                "group": info["group"],
                "madrs1": info["madrs1"],
                "madrs2": info["madrs2"],
                # Signaux réels (mappés honnêtement aux features de production)
                "activity_mean": round(activity_mean, 2),       # → z_step_count
                "sleep_proxy_min": sleep_proxy_min,             # → z_sleep_duration
                "circadian": round(peak_ratio * 10, 4),         # → z_sleep_quality
            })

        patients_loaded += 1

    print(f"  -> {patients_loaded} patients, {len(all_rows)} jours-patients")
    return all_rows


# ---------------------------------------------------------------------------
# 3. Baselines par patient + Z-scores
# ---------------------------------------------------------------------------

# Métrique brute → nom du z-score (feature du modèle)
RAW_TO_ZSCORE = {
    "activity_mean": "z_step_count",
    "sleep_proxy_min": "z_sleep_duration",
    "circadian": "z_sleep_quality",
}


def compute_baselines(rows: list[dict]) -> dict:
    """mean/std par patient pour chaque métrique brute."""
    print("[3/8] Calcul des baselines par patient...")
    patients = sorted(set(r["patient_id"] for r in rows))
    baselines = {}
    for patient in patients:
        prows = [r for r in rows if r["patient_id"] == patient]
        baselines[patient] = {}
        for raw in RAW_TO_ZSCORE:
            values = [r[raw] for r in prows if r[raw] is not None]
            if len(values) < 2:
                baselines[patient][raw] = {"mean": 0.0, "std": 1e-6}
            else:
                baselines[patient][raw] = {
                    "mean": mean(values), "std": max(stdev(values), 1e-6)
                }
    return baselines


def compute_features(rows: list[dict], baselines: dict) -> list[dict]:
    """Z-scores des signaux réels + is_weekend (trends ajoutés plus tard)."""
    print("[4/8] Calcul des Z-scores...")
    enriched = []
    for row in rows:
        bl = baselines[row["patient_id"]]
        features = {}
        for raw, z_name in RAW_TO_ZSCORE.items():
            m, s = bl[raw]["mean"], bl[raw]["std"]
            features[z_name] = round((row[raw] - m) / s, 4)
        features["is_weekend"] = 1.0 if row["date"].weekday() >= 5 else 0.0
        features["trend_7d"] = 0.0   # rempli par add_activity_trends
        features["trend_14d"] = 0.0
        enriched.append({
            "patient_id": row["patient_id"],
            "date": row["date"],
            "group": row["group"],
            "madrs1": row["madrs1"],
            "madrs2": row["madrs2"],
            "features": features,
        })
    return enriched


# ---------------------------------------------------------------------------
# 4. Labels : MADRS → score 0-100 (SANS bruit synthétique)
# ---------------------------------------------------------------------------

def madrs_to_score(madrs: float) -> float:
    """MADRS (0-60) → score 0-100, non-linéaire (seuils cliniques standards)."""
    if madrs <= 6:        # normal
        return (madrs / 6.0) * 15.0
    elif madrs <= 19:     # légère
        return 15.0 + ((madrs - 6.0) / 13.0) * 25.0
    elif madrs <= 34:     # modérée
        return 40.0 + ((madrs - 19.0) / 15.0) * 30.0
    return 70.0 + ((madrs - 34.0) / 26.0) * 30.0  # sévère


def generate_labels(enriched: list[dict]) -> dict:
    """
    Label = MADRS interpolé linéairement (madrs1→madrs2) sur les jours, converti
    en score 0-100. AUCUN bruit aléatoire (contrairement à v1).
    """
    print("[5/8] Génération des labels (MADRS → 0-100, sans bruit)...")
    labels = {}
    for patient in sorted(set(r["patient_id"] for r in enriched)):
        prows = sorted(
            [r for r in enriched if r["patient_id"] == patient],
            key=lambda x: x["date"],
        )
        n = len(prows)
        madrs1, madrs2 = prows[0]["madrs1"], prows[0]["madrs2"]
        for i, row in enumerate(prows):
            t = i / max(n - 1, 1)
            madrs_interp = madrs1 + (madrs2 - madrs1) * t
            labels[(patient, row["date"])] = round(madrs_to_score(madrs_interp), 2)

    cond = [v for k, v in labels.items() if k[0].startswith("condition")]
    ctrl = [v for k, v in labels.items() if k[0].startswith("control")]
    if cond:
        print(f"  -> Condition : moy={np.mean(cond):.1f} [{np.min(cond):.0f},{np.max(cond):.0f}]")
    if ctrl:
        print(f"  -> Contrôle  : moy={np.mean(ctrl):.1f} [{np.min(ctrl):.0f},{np.max(ctrl):.0f}]")
    return labels


# ---------------------------------------------------------------------------
# 5. Tendances calculées sur l'ACTIVITÉ (anti data-leakage)
# ---------------------------------------------------------------------------

def add_activity_trends(enriched: list[dict]) -> None:
    """
    trend_7d / trend_14d = pente de régression de z_step_count (l'ACTIVITÉ)
    sur les 7/14 derniers jours. CRUCIAL : on n'utilise PAS le label (contrairement
    à v1 qui dérivait la tendance du score → fuite). Aucune info de y n'entre ici.
    """
    print("[6/8] Tendances 7j/14j sur l'activité (anti-leakage)...")
    for patient in sorted(set(r["patient_id"] for r in enriched)):
        prows = sorted(
            [r for r in enriched if r["patient_id"] == patient],
            key=lambda x: x["date"],
        )
        activity_so_far: list[float] = []
        for row in prows:
            activity_so_far.append(row["features"]["z_step_count"])
            for window, key in ((7, "trend_7d"), (14, "trend_14d")):
                w = activity_so_far[-min(window, len(activity_so_far)):]
                if len(w) >= 2:
                    slope = float(np.polyfit(np.arange(len(w)), w, 1)[0])
                    row["features"][key] = round(slope, 4)


# ---------------------------------------------------------------------------
# 6. Dataset + split PAR PATIENT
# ---------------------------------------------------------------------------

def build_dataset(enriched: list[dict], labels: dict):
    """Construit X, y, groups (patient_id) pour GroupKFold."""
    print("[7/8] Construction du dataset...")
    X, y, groups = [], [], []
    for row in enriched:
        key = (row["patient_id"], row["date"])
        if key in labels:
            X.append([row["features"].get(f, 0.0) for f in MODEL_FEATURES])
            y.append(labels[key])
            groups.append(row["patient_id"])
    X = np.array(X, dtype=np.float64)
    y = np.array(y, dtype=np.float64)
    groups = np.array(groups)
    print(f"  -> X={X.shape}, features={MODEL_FEATURES}")
    print(f"  -> y range=[{y.min():.1f}, {y.max():.1f}], moy={y.mean():.1f}")
    return X, y, groups


# ---------------------------------------------------------------------------
# 7. Entraînement + évaluation honnête (GroupKFold + test holdout)
# ---------------------------------------------------------------------------

def train_and_evaluate(X, y, groups):
    """
    Évaluation honnête :
      - test holdout : 20% des PATIENTS, jamais vus à l'entraînement
      - GroupKFold sur le train (folds par patient, pas de fuite inter-jours)
      - métriques rapportées sur le TEST set (généralisation réelle)
    """
    print("[8/8] Entraînement + évaluation (GroupKFold + test holdout)...")
    import xgboost as xgb
    from sklearn.model_selection import GroupKFold, GroupShuffleSplit
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

    params = {
        "n_estimators": 200, "max_depth": 4, "learning_rate": 0.05,
        "subsample": 0.8, "colsample_bytree": 0.8,
        "reg_alpha": 0.1, "reg_lambda": 1.0,
        "objective": "reg:squarederror", "random_state": RANDOM_SEED,
    }

    # 1) Split par patient : test holdout
    gss = GroupShuffleSplit(n_splits=1, test_size=TEST_PATIENT_FRACTION, random_state=RANDOM_SEED)
    train_idx, test_idx = next(gss.split(X, y, groups))
    X_tr, X_te = X[train_idx], X[test_idx]
    y_tr, y_te = y[train_idx], y[test_idx]
    g_tr = groups[train_idx]
    n_tr_pat = len(set(g_tr))
    n_te_pat = len(set(groups[test_idx]))
    print(f"  -> Train: {len(X_tr)} jours / {n_tr_pat} patients | "
          f"Test holdout: {len(X_te)} jours / {n_te_pat} patients")

    # 2) GroupKFold CV sur le train (par patient)
    n_splits = min(5, n_tr_pat)
    gkf = GroupKFold(n_splits=n_splits)
    cv_rmse, cv_mae = [], []
    print(f"  GroupKFold {n_splits}-fold (par patient) :")
    for fold, (tr_i, val_i) in enumerate(gkf.split(X_tr, y_tr, g_tr), 1):
        m = xgb.XGBRegressor(**params)
        m.fit(X_tr[tr_i], y_tr[tr_i], verbose=False)
        pred = np.clip(m.predict(X_tr[val_i]), 0, 100)
        rmse = float(np.sqrt(mean_squared_error(y_tr[val_i], pred)))
        mae = float(mean_absolute_error(y_tr[val_i], pred))
        cv_rmse.append(rmse)
        cv_mae.append(mae)
        print(f"    Fold {fold}: RMSE={rmse:.2f}, MAE={mae:.2f}")
    print(f"  -> CV RMSE: {np.mean(cv_rmse):.2f} (+/- {np.std(cv_rmse):.2f})")

    # 3) Modèle final entraîné sur tout le train, évalué sur le TEST holdout
    model = xgb.XGBRegressor(**params)
    model.fit(X_tr, y_tr, verbose=False)
    pred_te = np.clip(model.predict(X_te), 0, 100)
    test_rmse = float(np.sqrt(mean_squared_error(y_te, pred_te)))
    test_mae = float(mean_absolute_error(y_te, pred_te))
    test_r2 = float(r2_score(y_te, pred_te))
    print(f"\n  ===== MÉTRIQUES SUR TEST HOLDOUT (patients jamais vus) =====")
    print(f"  RMSE={test_rmse:.2f} | MAE={test_mae:.2f} | R²={test_r2:.4f}")

    # Classification 4 niveaux sur le test
    cls_true = [classify_risk(s) for s in y_te]
    cls_pred = [classify_risk(s) for s in pred_te]
    test_acc = sum(t == p for t, p in zip(cls_true, cls_pred)) / len(y_te)
    print(f"  Accuracy 4 niveaux (test): {test_acc:.1%}")

    # Importance des features
    importances = model.feature_importances_
    order = np.argsort(importances)[::-1]
    print("\n  Importance des features :")
    for i in order:
        print(f"    {MODEL_FEATURES[i]:18s} {importances[i]:.4f}  {'#' * int(importances[i]*40)}")

    metrics = {
        "dataset": "Depresjon (Simula Research Lab)",
        "dataset_url": "https://datasets.simula.no/depresjon/",
        "methodology": "GroupKFold par patient + test holdout 20% patients ; "
                       "labels MADRS sans bruit ; trends sur activité (anti-leakage) ; "
                       "features = signaux actigraphie réels uniquement",
        "n_patients_train": int(n_tr_pat),
        "n_patients_test": int(n_te_pat),
        "n_samples_train": int(len(X_tr)),
        "n_samples_test": int(len(X_te)),
        "n_features": int(X.shape[1]),
        "feature_names": MODEL_FEATURES,
        "cv_rmse_mean": round(float(np.mean(cv_rmse)), 4),
        "cv_rmse_std": round(float(np.std(cv_rmse)), 4),
        "test_rmse": round(test_rmse, 4),
        "test_mae": round(test_mae, 4),
        "test_r2": round(test_r2, 4),
        "test_classification_accuracy": round(float(test_acc), 4),
        "feature_importances": {MODEL_FEATURES[i]: round(float(importances[i]), 4) for i in order},
        "hyperparameters": params,
        "label_source": "MADRS (clinician-rated), interpolé sans bruit",
        "trained_at": datetime.now().isoformat(),
    }
    return model, metrics


def save_model(model, metrics):
    print(f"  Sauvegarde → {MODEL_OUTPUT}")
    MODEL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(MODEL_OUTPUT))
    with open(METRICS_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(f"  Métriques → {METRICS_OUTPUT}")


def main():
    if not SCORES_CSV.exists():
        print(f"ERREUR : dataset introuvable à {DATA_DIR}")
        print("Téléchargez Depresjon et placez-le dans data/depresjon/data/")
        sys.exit(1)

    madrs = load_madrs_scores()
    rows = load_and_aggregate_actigraphy(madrs)
    if not rows:
        print("ERREUR : aucune donnée d'actigraphie chargée.")
        sys.exit(1)
    baselines = compute_baselines(rows)
    enriched = compute_features(rows, baselines)
    labels = generate_labels(enriched)
    add_activity_trends(enriched)
    X, y, groups = build_dataset(enriched, labels)
    model, metrics = train_and_evaluate(X, y, groups)
    save_model(model, metrics)
    print("\n✅ Entraînement terminé. Modèle honnête prêt.")


if __name__ == "__main__":
    main()
