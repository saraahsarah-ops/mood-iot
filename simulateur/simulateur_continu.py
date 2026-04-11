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

DATE_DEBUT       = datetime(2026, 4, 1, 0, 0, 0)
INTERVAL         = timedelta(minutes=5)
SLOTS_PAR_JOUR   = 288   # 24h x 12 slots/h


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_t(jour):
    """Facteur de degradation : 0.0 au jour 8, 1.0 au jour 21. None si baseline."""
    if jour <= 7:
        return None
    return (jour - 8) / 13.0


def jitter(val, pct=0.03):
    """Bruit relatif de +/- pct."""
    return val * (1 + random.uniform(-pct, pct))


def interp(a_min, a_max, b_min, b_max, t):
    """Valeur aleatoire dans la plage interpolee entre A (t=0) et B (t=1)."""
    low  = a_min + (b_min - a_min) * t
    high = a_max + (b_max - a_max) * t
    return jitter(random.uniform(low, high))


# ---------------------------------------------------------------------------
# Battements de coeur
# ---------------------------------------------------------------------------

def bpm_pour_slot(heure, t):
    """
    Nuit (23h-7h) : repos 50-60 bpm (independant de la rechute).
    Journee normale  : 60-75 bpm.
    Journee rechute  : 85-100 bpm (progression selon t).
    """
    nuit = (heure >= 23 or heure < 7)
    if nuit:
        return int(max(40, jitter(random.uniform(50, 60))))

    if t is None:
        return int(max(40, interp(60, 75, 60, 75, 0)))
    else:
        return int(max(40, interp(60, 75, 85, 100, t)))


# ---------------------------------------------------------------------------
# Lieux GPS : fenetres de deplacement dans la journee
# ---------------------------------------------------------------------------

def mouvements_du_jour(jour, t):
    """
    Renvoie un set de slots (0-287) marques comme deplacement (lieux=1).
    Journee normale : 3-6 deplacements.
    Rechute         : 0-1 deplacement (progressif).
    Chaque deplacement couvre une fenetre de 15-30 min (3-6 slots).
    Deplacements uniquement entre 7h et 23h (slots 84-275).
    """
    if t is None:
        n = random.randint(3, 6)
    else:
        # de 3-6 en baseline vers 0-1 en rechute complete
        n_max = max(0, round(6 - 5 * t))   # 6 -> 1
        n_min = max(0, round(3 - 3 * t))   # 3 -> 0
        if n_min > n_max:
            n_min = n_max
        n = random.randint(n_min, n_max)

    slots_dispo = list(range(84, 276))   # 7h*12 .. 23h*12
    actifs = set()

    for _ in range(n):
        if not slots_dispo:
            break
        centre = random.choice(slots_dispo)
        duree  = random.randint(3, 6)    # 15-30 min
        debut  = max(0, centre - duree // 2)
        for s in range(debut, min(SLOTS_PAR_JOUR, debut + duree)):
            actifs.add(s)
        # Evite de superposer les prochains deplacements
        slots_dispo = [s for s in slots_dispo if abs(s - centre) > duree + 12]

    return actifs


# ---------------------------------------------------------------------------
# Luminosite
# ---------------------------------------------------------------------------

def luminosite_pour_slot(heure, t):
    """
    Nuit (23h-7h) : 0-5%.
    Journee normale  : 40-70%.
    Journee rechute  : 10-20% (proxy exposition lumiere naturelle).
    """
    nuit = (heure >= 23 or heure < 7)
    if nuit:
        return int(max(0, min(100, jitter(random.uniform(0, 5)))))

    if t is None:
        return int(max(0, min(100, interp(40, 70, 40, 70, 0))))
    else:
        return int(max(0, min(100, interp(40, 70, 10, 20, t))))


# ---------------------------------------------------------------------------
# Generation principale
# ---------------------------------------------------------------------------

lignes = []

for patiente in PATIENTES:
    for jour in range(1, 22):
        t = get_t(jour)
        deplacements = mouvements_du_jour(jour, t)

        for slot in range(SLOTS_PAR_JOUR):
            dt    = DATE_DEBUT + timedelta(days=jour - 1, minutes=slot * 5)
            heure = dt.hour

            bpm    = bpm_pour_slot(heure, t)
            lieux  = 1 if slot in deplacements else 0
            lumino = luminosite_pour_slot(heure, t)

            lignes.append({
                "patiente":          patiente,
                "datetime":          dt.strftime("%Y-%m-%d %H:%M:%S"),
                "battements_coeur":  bpm,
                "lieux_visites_gps": lieux,
                "luminosite_pct":    lumino,
            })

# ---------------------------------------------------------------------------
# Sauvegarde CSV
# ---------------------------------------------------------------------------

COLONNES = [
    "patiente", "datetime",
    "battements_coeur", "lieux_visites_gps", "luminosite_pct",
]

output = "donnees_continu.csv"
with open(output, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=COLONNES)
    writer.writeheader()
    writer.writerows(lignes)

# ---------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------

total = len(lignes)
print(f"Fichier '{output}' genere : {total} lignes "
      f"({len(PATIENTES)} patientes x 21 jours x {SLOTS_PAR_JOUR} slots).\n")

print("5 premieres lignes :")
print(f"{'Patiente':<10} {'Datetime':<22} {'BPM':>5} {'Lieux':>6} {'Lumino':>7}")
print("-" * 55)
for l in lignes[:5]:
    print(f"{l['patiente']:<10} {l['datetime']:<22} "
          f"{l['battements_coeur']:>5} {l['lieux_visites_gps']:>6} "
          f"{l['luminosite_pct']:>7}")
