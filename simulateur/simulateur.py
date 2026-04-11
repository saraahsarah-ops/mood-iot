import csv
import random
from datetime import date, timedelta

random.seed(42)

PATIENTES = {
    "Sophie": "insomnie",
    "Marie":  "hypersomnie",
    "Léa":    "insomnie",
    "Anna":   "hypersomnie",
}

DATE_DEBUT = date(2026, 4, 1)

# Plages normales (baseline jours 1-7)
NORMAL = {
    "pas":                (7000, 10000),
    "sommeil_heures":     (6.5,  8.5),
    "battements_coeur":   (60,   75),
    "lieux_visites_gps":  (3,    6),
    "temps_ecran_heures": (2.0,  4.0),
    "luminosite_pct":     (40,   70),
}

# Plages cibles en rechute (fin des 7 jours de dégradation)
RECHUTE_INSOMNIE = {
    "pas":                (1000, 3000),
    "sommeil_heures":     (3.0,  5.0),
    "battements_coeur":   (85,   100),
    "lieux_visites_gps":  (0,    1),
    "temps_ecran_heures": (7.0,  10.0),
    "luminosite_pct":     (10,   20),
}

RECHUTE_HYPERSOMNIE = {
    "pas":                (1000, 3000),
    "sommeil_heures":     (10.0, 14.0),
    "battements_coeur":   (85,   100),
    "lieux_visites_gps":  (0,    1),
    "temps_ecran_heures": (7.0,  10.0),
    "luminosite_pct":     (10,   20),
}


def interpolate(a_min, a_max, b_min, b_max, t):
    """
    Interpole entre la plage [a_min, a_max] et [b_min, b_max].
    t=0 → valeur dans la plage A, t=1 → valeur dans la plage B.
    Renvoie un float dans la plage interpolée avec du bruit léger.
    """
    low  = a_min + (b_min - a_min) * t
    high = a_max + (b_max - a_max) * t
    val  = random.uniform(low, high)
    # Bruit relatif de ±5 %
    bruit = val * random.uniform(-0.05, 0.05)
    return val + bruit


def generer_ligne(patiente, profil, jour, d):
    """Génère une ligne de données pour un jour donné (1-indexed)."""
    if jour <= 7:
        # Baseline : valeurs normales
        pas      = int(interpolate(*NORMAL["pas"],                *NORMAL["pas"],                0))
        sommeil  = round(interpolate(*NORMAL["sommeil_heures"],   *NORMAL["sommeil_heures"],     0), 2)
        bpm      = int(interpolate(*NORMAL["battements_coeur"],   *NORMAL["battements_coeur"],   0))
        lieux    = int(interpolate(*NORMAL["lieux_visites_gps"],  *NORMAL["lieux_visites_gps"],  0))
        ecran    = round(interpolate(*NORMAL["temps_ecran_heures"],*NORMAL["temps_ecran_heures"],0), 2)
        lumino   = int(interpolate(*NORMAL["luminosite_pct"],     *NORMAL["luminosite_pct"],     0))
    else:
        # Rechute : dégradation progressive
        # t va de 0 (debut du jour 8) a 1 (fin du jour 21)
        t = (jour - 8) / 13.0  # 0 le jour 8, 1 le jour 21
        cible = RECHUTE_INSOMNIE if profil == "insomnie" else RECHUTE_HYPERSOMNIE

        pas      = int(interpolate(*NORMAL["pas"],                *cible["pas"],                 t))
        sommeil  = round(interpolate(*NORMAL["sommeil_heures"],   *cible["sommeil_heures"],      t), 2)
        bpm      = int(interpolate(*NORMAL["battements_coeur"],   *cible["battements_coeur"],    t))
        lieux    = int(interpolate(*NORMAL["lieux_visites_gps"],  *cible["lieux_visites_gps"],   t))
        ecran    = round(interpolate(*NORMAL["temps_ecran_heures"],*cible["temps_ecran_heures"], t), 2)
        lumino   = int(interpolate(*NORMAL["luminosite_pct"],     *cible["luminosite_pct"],      t))

    # Garde les valeurs dans des bornes physiquement cohérentes
    pas     = max(0,   pas)
    sommeil = max(0.0, min(24.0, sommeil))
    bpm     = max(40,  min(200,  bpm))
    lieux   = max(0,   lieux)
    ecran   = max(0.0, min(24.0, ecran))
    lumino  = max(0,   min(100,  lumino))

    return {
        "patiente":           patiente,
        "jour":               jour,
        "date":               str(d),
        "pas":                pas,
        "sommeil_heures":     sommeil,
        "battements_coeur":   bpm,
        "lieux_visites_gps":  lieux,
        "temps_ecran_heures": ecran,
        "luminosite_pct":     lumino,
    }


# --- Génération des données ---
lignes = []
for patiente, profil in PATIENTES.items():
    for jour in range(1, 22):
        d = DATE_DEBUT + timedelta(days=jour - 1)
        lignes.append(generer_ligne(patiente, profil, jour, d))

# --- Sauvegarde CSV ---
COLONNES = [
    "patiente", "jour", "date",
    "pas", "sommeil_heures", "battements_coeur",
    "lieux_visites_gps", "temps_ecran_heures", "luminosite_pct",
]

with open("donnees.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=COLONNES)
    writer.writeheader()
    writer.writerows(lignes)

print("Fichier donnees.csv genere avec succes.\n")

# --- Résumé comparatif ---
METRICS = [
    "pas", "sommeil_heures", "battements_coeur",
    "lieux_visites_gps", "temps_ecran_heures", "luminosite_pct",
]

print(f"{'Patiente':<10} {'Metrique':<25} {'Moy. J1-7':>10} {'Moy. J8-21':>12} {'Delta':>8}")
print("-" * 68)

for patiente in PATIENTES:
    donnees_p = [l for l in lignes if l["patiente"] == patiente]
    baseline  = [l for l in donnees_p if l["jour"] <= 7]
    rechute   = [l for l in donnees_p if l["jour"] > 7]

    for m in METRICS:
        moy_b = sum(l[m] for l in baseline) / len(baseline)
        moy_r = sum(l[m] for l in rechute)  / len(rechute)
        delta = moy_r - moy_b
        signe = "+" if delta >= 0 else ""
        print(f"{patiente:<10} {m:<25} {moy_b:>10.2f} {moy_r:>12.2f} {signe+f'{delta:.2f}':>8}")
    print()
