import csv
import random
from datetime import datetime, timedelta

random.seed(99)

PATIENTES = {
    "Sophie": "insomnie",
    "Marie":  "hypersomnie",
    "Lea":    "insomnie",
    "Anna":   "hypersomnie",
}

DATE_DEBUT     = datetime(2026, 4, 1, 0, 0, 0)
SLOTS_PAR_JOUR = 288   # 24 h × 12 slots/h  (1 slot = 5 min)

# ---------------------------------------------------------------------------
# Coordonnées GPS
# ---------------------------------------------------------------------------

DOMICILES = {
    "Sophie": (48.8566, 2.3522),   # Paris 1er
    "Marie":  (48.8710, 2.3340),   # Paris 9e — Opéra
    "Lea":    (48.8520, 2.3680),   # Paris 12e — Bastille
    "Anna":   (48.8650, 2.3180),   # Paris 8e — Saint-Lazare
}

LIEUX_POOL = {
    "travail":    (48.8738, 2.2950),
    "commerce":   (48.8330, 2.3708),
    "parc":       (48.8462, 2.3372),
    "gare":       (48.8448, 2.3735),
    "restaurant": (48.8606, 2.3376),
    "sport":      (48.8794, 2.3575),
    "amis":       (48.8867, 2.3431),
}
LIEUX_NOMS = list(LIEUX_POOL.keys())

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_t(jour):
    """t=0.0 au jour 8, t=1.0 au jour 21, None pour la baseline."""
    if jour <= 7:
        return None
    return (jour - 8) / 13.0


def jitter(val, pct=0.03):
    return val * (1 + random.uniform(-pct, pct))


def interp(a_min, a_max, b_min, b_max, t):
    low  = a_min + (b_min - a_min) * t
    high = a_max + (b_max - a_max) * t
    return jitter(random.uniform(low, high))


# ---------------------------------------------------------------------------
# Battements de cœur
# ---------------------------------------------------------------------------

def bpm_pour_slot(heure, t):
    """Nuit 50-60 bpm. Journée normale 60-75. Journée rechute 85-100."""
    if heure >= 23 or heure < 7:
        return int(max(40, jitter(random.uniform(50, 60))))
    if t is None:
        return int(max(40, interp(60, 75, 60, 75, 0)))
    return int(max(40, interp(60, 75, 85, 100, t)))


# ---------------------------------------------------------------------------
# Luminosité
# ---------------------------------------------------------------------------

def luminosite_pour_slot(heure, t):
    """Nuit 0-5 %. Journée normale 40-70 %. Journée rechute 10-20 %."""
    if heure >= 23 or heure < 7:
        return int(max(0, min(100, jitter(random.uniform(0, 5)))))
    if t is None:
        return int(max(0, min(100, interp(40, 70, 40, 70, 0))))
    return int(max(0, min(100, interp(40, 70, 10, 20, t))))


# ---------------------------------------------------------------------------
# Plan GPS de la journée
# ---------------------------------------------------------------------------

def plan_gps_journee(patiente, jour, t):
    """
    Renvoie une liste de 288 tuples (lat, lon) — un par slot de 5 min.

    Jours normaux  : la patiente quitte son domicile pour 3-6 destinations.
    Rechute t→1    : elle reste de plus en plus chez elle.
    Au jour 21     : quasi immobile à son domicile toute la journée.

    Modélisation :
    - Nuit (0h-7h, slots 0-83)   : domicile
    - Journée (7h-23h, 84-275)   : destinations intercalées par segments
    - Soirée (23h-24h, 276-287)  : domicile
    Chaque slot reçoit un bruit GPS ±20 m (~0.0002°) pour le réalisme.
    """
    domicile = DOMICILES[patiente]

    # Nombre de sorties selon la dégradation
    if t is None:
        n_sorties = random.randint(3, 6)
    else:
        n_max = max(0, round(5 - 5 * t))   # 5 → 0
        n_min = max(0, round(3 - 3 * t))   # 3 → 0
        if n_min > n_max:
            n_min = n_max
        n_sorties = random.randint(n_min, n_max)

    # Construction du planning slot par slot
    # Initialisation : tout au domicile
    planning = [domicile] * SLOTS_PAR_JOUR

    if n_sorties > 0:
        destinations = random.sample(LIEUX_NOMS, min(n_sorties, len(LIEUX_NOMS)))

        # Slots de journée : 7h (84) → 23h (276)
        DAY_START, DAY_END = 84, 276
        day_len   = DAY_END - DAY_START
        # On divise la journée en n_sorties+1 segments (départ/retour domicile inclus)
        seg       = day_len // (n_sorties + 1)

        for i, dest_nom in enumerate(destinations):
            dest  = LIEUX_POOL[dest_nom]
            # Centre du séjour dans le segment i+1
            c_start = DAY_START + (i + 1) * seg
            c_end   = c_start + seg
            sejour_debut  = random.randint(c_start, max(c_start, c_end - 30))
            sejour_duree  = random.randint(18, 48)   # 1h30 à 4h
            for s in range(sejour_debut, min(DAY_END, sejour_debut + sejour_duree)):
                planning[s] = dest

    # Bruit GPS ±20 m
    return [
        (round(lat + random.uniform(-0.0002, 0.0002), 6),
         round(lon + random.uniform(-0.0002, 0.0002), 6))
        for lat, lon in planning
    ]


# ---------------------------------------------------------------------------
# Génération principale
# ---------------------------------------------------------------------------

lignes = []

for patiente in PATIENTES:
    for jour in range(1, 22):
        t        = get_t(jour)
        gps_plan = plan_gps_journee(patiente, jour, t)

        for slot in range(SLOTS_PAR_JOUR):
            dt    = DATE_DEBUT + timedelta(days=jour - 1, minutes=slot * 5)
            heure = dt.hour
            lat, lon = gps_plan[slot]

            lignes.append({
                "patiente":         patiente,
                "datetime":         dt.strftime("%Y-%m-%d %H:%M:%S"),
                "battements_coeur": bpm_pour_slot(heure, t),
                "latitude":         lat,
                "longitude":        lon,
                "luminosite_pct":   luminosite_pour_slot(heure, t),
            })

# ---------------------------------------------------------------------------
# Sauvegarde CSV
# ---------------------------------------------------------------------------

COLONNES = [
    "patiente", "datetime",
    "battements_coeur", "latitude", "longitude", "luminosite_pct",
]

OUTPUT = "donnees_continu.csv"
with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=COLONNES)
    writer.writeheader()
    writer.writerows(lignes)

# ---------------------------------------------------------------------------
# Résumé
# ---------------------------------------------------------------------------

total = len(lignes)
print(f"Fichier '{OUTPUT}' genere : {total} lignes "
      f"({len(PATIENTES)} patientes x 21 jours x {SLOTS_PAR_JOUR} slots).\n")

# Variance GPS par jour : écart-type de latitude (proxy de mobilité)
print("Resume mobilite GPS (ecart-type latitude par periode) :")
print(f"{'Patiente':<10} {'Moy std-lat J1-7':>18} {'Moy std-lat J8-21':>19} {'Delta':>8}")
print("-" * 58)

import statistics

for patiente in PATIENTES:
    data_p = [l for l in lignes if l["patiente"] == patiente]

    def std_lat_jour(jour_num):
        slots = [l["latitude"] for l in data_p
                 if l["datetime"].startswith(
                     (DATE_DEBUT + timedelta(days=jour_num - 1)).strftime("%Y-%m-%d"))]
        return statistics.stdev(slots) if len(slots) > 1 else 0

    std_base   = sum(std_lat_jour(j) for j in range(1, 8))  / 7
    std_rechute= sum(std_lat_jour(j) for j in range(8, 22)) / 14
    delta = std_rechute - std_base
    signe = "+" if delta >= 0 else ""
    print(f"{patiente:<10} {std_base:>18.6f} {std_rechute:>19.6f} {signe+f'{delta:.6f}':>8}")

print()
print("5 premieres lignes :")
print(f"{'Patiente':<10} {'Datetime':<22} {'BPM':>5} {'Lat':>10} {'Lon':>10} {'Lumino':>7}")
print("-" * 68)
for l in lignes[:5]:
    print(f"{l['patiente']:<10} {l['datetime']:<22} "
          f"{l['battements_coeur']:>5} {l['latitude']:>10.6f} "
          f"{l['longitude']:>10.6f} {l['luminosite_pct']:>7}")
