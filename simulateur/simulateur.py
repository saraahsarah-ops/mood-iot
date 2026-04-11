import csv
import math
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

# ---------------------------------------------------------------------------
# Coordonnées GPS
# ---------------------------------------------------------------------------

# Domicile propre à chaque patiente (Paris / IDF)
DOMICILES = {
    "Sophie": (48.8566, 2.3522),   # Paris 1er — centre
    "Marie":  (48.8710, 2.3340),   # Paris 9e — Opéra
    "Léa":    (48.8520, 2.3680),   # Paris 12e — Bastille
    "Anna":   (48.8650, 2.3180),   # Paris 8e — Saint-Lazare
}

# Lieux du quotidien (hors domicile)
LIEUX_POOL = {
    "travail":    (48.8738, 2.2950),   # La Défense
    "commerce":   (48.8330, 2.3708),   # Paris 13e
    "parc":       (48.8462, 2.3372),   # Jardin du Luxembourg
    "gare":       (48.8448, 2.3735),   # Gare de Lyon
    "restaurant": (48.8606, 2.3376),   # Châtelet
    "sport":      (48.8794, 2.3575),   # Buttes-Chaumont
    "amis":       (48.8867, 2.3431),   # Montmartre
}
LIEUX_NOMS = list(LIEUX_POOL.keys())

# ---------------------------------------------------------------------------
# Plages de valeurs
# ---------------------------------------------------------------------------

NORMAL = {
    "pas":                (7000, 10000),
    "sommeil_heures":     (6.5,  8.5),
    "battements_coeur":   (60,   75),
    "temps_ecran_heures": (2.0,  4.0),
    "luminosite_pct":     (40,   70),
}

RECHUTE_INSOMNIE = {
    "pas":                (1000, 3000),
    "sommeil_heures":     (3.0,  5.0),
    "battements_coeur":   (85,   100),
    "temps_ecran_heures": (7.0,  10.0),
    "luminosite_pct":     (10,   20),
}

RECHUTE_HYPERSOMNIE = {
    "pas":                (1000, 3000),
    "sommeil_heures":     (10.0, 14.0),
    "battements_coeur":   (85,   100),
    "temps_ecran_heures": (7.0,  10.0),
    "luminosite_pct":     (10,   20),
}

# ---------------------------------------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------------------------------------

def interpolate(a_min, a_max, b_min, b_max, t):
    """Valeur aléatoire dans la plage interpolée A→B selon t, avec bruit ±5 %."""
    low  = a_min + (b_min - a_min) * t
    high = a_max + (b_max - a_max) * t
    val  = random.uniform(low, high)
    return val + val * random.uniform(-0.05, 0.05)


def haversine(lat1, lon1, lat2, lon2):
    """Distance en mètres entre deux points GPS (formule de Haversine)."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def lieux_distincts(coords, tolerance=500):
    """Nombre de lieux distincts dans une liste de (lat, lon), tolérance 500 m."""
    groupes = []
    for lat, lon in coords:
        if not any(haversine(lat, lon, glat, glon) < tolerance for glat, glon in groupes):
            groupes.append((lat, lon))
    return len(groupes)


def gps_jour(patiente, t):
    """
    Génère la liste des coordonnées GPS visitées dans la journée.

    Jours normaux  (t=None) : domicile + 2-5 autres lieux.
    Rechute t=0→1           : retour progressif vers le domicile.
    Au jour 21 (t=1)        : domicile uniquement.
    Chaque coordonnée reçoit un bruit GPS ±30 m (~0.0003°).
    """
    domicile = DOMICILES[patiente]

    if t is None:
        n_autres = random.randint(2, 5)
        choix    = random.sample(LIEUX_NOMS, n_autres)
        coords   = [domicile] + [LIEUX_POOL[l] for l in choix]
    else:
        # 2-5 autres lieux en baseline → 0 en rechute complète
        n_max = max(0, round(4 - 4 * t))   # 4 → 0
        n_min = max(0, round(2 - 2 * t))   # 2 → 0
        if n_min > n_max:
            n_min = n_max
        n_autres = random.randint(n_min, n_max)
        if n_autres > 0:
            choix  = random.sample(LIEUX_NOMS, n_autres)
            coords = [domicile] + [LIEUX_POOL[l] for l in choix]
        else:
            coords = [domicile]

    # Bruit GPS réaliste ±30 m
    return [
        (round(lat + random.uniform(-0.0003, 0.0003), 6),
         round(lon + random.uniform(-0.0003, 0.0003), 6))
        for lat, lon in coords
    ]


# ---------------------------------------------------------------------------
# Génération ligne par ligne
# ---------------------------------------------------------------------------

def generer_ligne(patiente, profil, jour, d):
    """Génère une ligne de données pour un jour donné (1-indexé)."""
    t     = None if jour <= 7 else (jour - 8) / 13.0
    tv    = 0 if t is None else t
    cible = RECHUTE_INSOMNIE if profil == "insomnie" else RECHUTE_HYPERSOMNIE

    pas     = max(0,    int(interpolate(*NORMAL["pas"],                *cible["pas"],                tv)))
    sommeil = max(0.0,  min(24.0, round(interpolate(*NORMAL["sommeil_heures"],   *cible["sommeil_heures"],  tv), 2)))
    bpm     = max(40,   min(200,  int(interpolate(*NORMAL["battements_coeur"],   *cible["battements_coeur"],tv))))
    ecran   = max(0.0,  min(24.0, round(interpolate(*NORMAL["temps_ecran_heures"],*cible["temps_ecran_heures"],tv), 2)))
    lumino  = max(0,    min(100,  int(interpolate(*NORMAL["luminosite_pct"],     *cible["luminosite_pct"],  tv))))

    coords        = gps_jour(patiente, t)
    nb_lieux      = lieux_distincts(coords)
    coordonnees_s = "|".join(f"{lat},{lon}" for lat, lon in coords)

    return {
        "patiente":           patiente,
        "jour":               jour,
        "date":               str(d),
        "pas":                pas,
        "sommeil_heures":     sommeil,
        "battements_coeur":   bpm,
        "nb_lieux_visites":   nb_lieux,
        "coordonnees_jour":   coordonnees_s,
        "temps_ecran_heures": ecran,
        "luminosite_pct":     lumino,
    }


# ---------------------------------------------------------------------------
# Génération des données
# ---------------------------------------------------------------------------

lignes = []
for patiente, profil in PATIENTES.items():
    for jour in range(1, 22):
        d = DATE_DEBUT + timedelta(days=jour - 1)
        lignes.append(generer_ligne(patiente, profil, jour, d))

# ---------------------------------------------------------------------------
# Sauvegarde CSV
# ---------------------------------------------------------------------------

COLONNES = [
    "patiente", "jour", "date",
    "pas", "sommeil_heures", "battements_coeur",
    "nb_lieux_visites", "coordonnees_jour",
    "temps_ecran_heures", "luminosite_pct",
]

with open("donnees.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=COLONNES)
    writer.writeheader()
    writer.writerows(lignes)

print("Fichier donnees.csv genere.\n")

# ---------------------------------------------------------------------------
# Résumé comparatif
# ---------------------------------------------------------------------------

METRICS = [
    "pas", "sommeil_heures", "battements_coeur",
    "nb_lieux_visites", "temps_ecran_heures", "luminosite_pct",
]

print(f"{'Patiente':<10} {'Metrique':<25} {'Moy. J1-7':>10} {'Moy. J8-21':>12} {'Delta':>9}")
print("-" * 70)

for patiente in PATIENTES:
    donnees_p = [l for l in lignes if l["patiente"] == patiente]
    baseline  = [l for l in donnees_p if l["jour"] <= 7]
    rechute   = [l for l in donnees_p if l["jour"] >  7]

    for m in METRICS:
        moy_b = sum(l[m] for l in baseline) / len(baseline)
        moy_r = sum(l[m] for l in rechute)  / len(rechute)
        delta = moy_r - moy_b
        signe = "+" if delta >= 0 else ""
        print(f"{patiente:<10} {m:<25} {moy_b:>10.2f} {moy_r:>12.2f} {signe+f'{delta:.2f}':>9}")

    # Exemples de coordonnées : jour 1 vs jour 21
    j1  = next(l for l in donnees_p if l["jour"] == 1)
    j21 = next(l for l in donnees_p if l["jour"] == 21)
    print(f"{'':10} {'  GPS J1  (nb='+str(j1['nb_lieux_visites'])+')':<25} {j1['coordonnees_jour'][:40]}...")
    print(f"{'':10} {'  GPS J21 (nb='+str(j21['nb_lieux_visites'])+')':<25} {j21['coordonnees_jour'][:40]}...")
    print()
