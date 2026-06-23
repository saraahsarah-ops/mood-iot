"""
Simulateur de patients pour démo / tests QA Mood-IoT.

Stratégie « Niveau 1 : même base, tout marqué » :
  - Marie (PATIENTE RÉELLE) : compte Keycloak + profil + assignation au médecin,
    mais AUCUNE donnée simulée — ses métriques proviennent des vrais capteurs de
    son téléphone (Health Connect, source_platform != 'simulator'). Sert à voir
    le système fonctionner avec des données réelles.
  - 4 patients DÉMO (@sim.test) : 30 jours de daily_aggregates synthétiques,
    tous marqués source_platform='simulator' → distinguables et nettoyables.
  - Dr Martin (psychiatre réel) : voit les 5 patients dans son dashboard.

Tout ce qui est simulé est marqué (source_platform='simulator' + email @sim.test),
donc `--clean` peut tout retirer sans toucher aux vraies données (Marie, Martin).

Exécution (DANS le conteneur ml-scoring) :
  # Peupler (Marie réelle + 4 démos)
  docker compose -f docker-compose.prod.yml --env-file .env.prod \
      exec -T ml-scoring python -m qa.simulate_patients
  # Nettoyer uniquement les données simulées
  docker compose -f docker-compose.prod.yml --env-file .env.prod \
      exec -T ml-scoring python -m qa.simulate_patients --clean
  # Démo sans téléphone : donner aussi des données simulées à Marie
  docker compose ... exec -T ml-scoring python -m qa.simulate_patients --marie-demo
"""

import argparse
import asyncio
import random
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import delete, select

from src.shared.database import AsyncSessionLocal
from src.shared.models import (
    DailyAggregate,
    DoctorProfile,
    Gender,
    Patient,
    PatientPsychiatrist,
    User,
    UserRole,
)
from src.scoring.main import _compute_and_store_baselines
from src.scoring.pipeline import get_pipeline

# IDs Keycloak réels (créés précédemment)
MARIE_KC = "3ba53982-507c-4cc3-9c74-9e3542d35e35"
MARTIN_KC = "e2d7043a-37ea-4cff-877d-e6b5fe92af5f"

MARTIN_EMAIL = "dr.martin@example.test"
MARIE_EMAIL = "marie.dupont@example.test"

# Marqueur des données simulées (par opposition aux vrais capteurs téléphone).
SIM_PLATFORM = "simulator"

N_DAYS = 30
random.seed(42)

# Patients DÉMO uniquement (synthétiques). Marie est gérée à part (réelle).
DEMO_ROSTER = [
    # (email,                  first,   last,      gender,    profile,   dob)
    ("paul.bernard@sim.test",  "Paul",  "Bernard", Gender.M,  "sain",    date(1988, 7, 5)),
    ("lea.moreau@sim.test",    "Léa",   "Moreau",  Gender.F,  "risque",  date(2000, 11, 23)),
    ("hugo.petit@sim.test",    "Hugo",  "Petit",   Gender.M,  "rechute", date(1992, 1, 30)),
    ("emma.roux@sim.test",     "Emma",  "Roux",    Gender.F,  "neutre",  date(1998, 9, 17)),
]


def _profile_day(profile: str, day_index: int, n_days: int) -> dict:
    """Génère les métriques d'un jour selon le profil clinique."""
    t = day_index / max(n_days - 1, 1)

    if profile == "sain":
        sleep = random.gauss(450, 20)
        quality = random.gauss(80, 5)
        steps = random.gauss(9000, 1200)
    elif profile == "risque":
        sleep = random.gauss(370, 25)
        quality = random.gauss(58, 8)
        steps = random.gauss(5200, 900)
    elif profile == "rechute":
        if t < 0.66:
            sleep = random.gauss(445, 20)
            quality = random.gauss(78, 5)
            steps = random.gauss(8800, 1000)
        else:
            deg = (t - 0.66) / 0.34
            sleep = random.gauss(445 - 130 * deg, 20)
            quality = random.gauss(78 - 35 * deg, 6)
            steps = random.gauss(8800 - 4500 * deg, 900)
    else:  # neutre
        sleep = random.gauss(420, 30)
        quality = random.gauss(70, 8)
        steps = random.gauss(7500, 1500)

    return {
        "sleep_duration_min": max(180, sleep),
        "sleep_quality_score": min(100, max(10, quality)),
        "step_count": int(max(500, steps)),
        "heart_rate_avg": random.gauss(70, 5),
        "heart_rate_variability": random.gauss(45, 8),
        "screen_time_min": random.gauss(300, 60),
        "call_count": random.randint(0, 8),
    }


async def _get_or_create_user(db, *, email, role, keycloak_id=None):
    res = await db.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()
    if user:
        return user
    user = User(
        id=uuid4(), email=email, role=role,
        is_active=True, registration_status="approved",
        keycloak_user_id=keycloak_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    return user


async def _get_or_create_patient(db, *, user, first, last, gender, dob):
    res = await db.execute(select(Patient).where(Patient.user_id == user.id))
    patient = res.scalar_one_or_none()
    if patient is None:
        patient = Patient(
            id=uuid4(), user_id=user.id, first_name=first, last_name=last,
            date_of_birth=dob, gender=gender,
            baseline_status="ready",
            created_at=datetime.now(timezone.utc),
        )
        db.add(patient)
        await db.flush()
    return patient


async def _assign(db, patient_id, psychiatrist_user_id, primary=True):
    res = await db.execute(
        select(PatientPsychiatrist).where(
            PatientPsychiatrist.patient_id == patient_id,
            PatientPsychiatrist.psychiatrist_id == psychiatrist_user_id,
        )
    )
    if res.scalar_one_or_none() is None:
        db.add(PatientPsychiatrist(
            id=uuid4(), patient_id=patient_id,
            psychiatrist_id=psychiatrist_user_id,
            is_primary=primary, assigned_at=datetime.now(timezone.utc),
        ))
        await db.flush()


async def _gen_aggregates(db, patient_id, profile):
    """Génère N_DAYS de données SIMULÉES (marquées source_platform='simulator')."""
    # Purge des seules données simulées de ce patient (idempotence) — ne touche
    # jamais aux vraies données capteur.
    await db.execute(
        delete(DailyAggregate).where(
            DailyAggregate.patient_id == patient_id,
            DailyAggregate.source_platform == SIM_PLATFORM,
        )
    )
    today = date.today()
    for i in range(N_DAYS):
        d = today - timedelta(days=N_DAYS - 1 - i)
        m = _profile_day(profile, i, N_DAYS)
        db.add(DailyAggregate(
            id=uuid4(), patient_id=patient_id, date=d,
            source_platform=SIM_PLATFORM,
            synced_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            **m,
        ))
    await db.flush()


async def _score_patient(db, pipeline, patient_id, label, profile):
    """Calcule baselines + scores des 3 derniers jours via le pipeline réel."""
    try:
        await _compute_and_store_baselines(str(patient_id), db)
    except Exception as e:  # noqa: BLE001
        print(f"  baseline {label}: {e}")
    last = None
    # Scores sur toute la fenêtre (N_DAYS) pour que la courbe d'évolution
    # affiche l'historique complet, pas seulement les 3 derniers jours.
    for back in range(N_DAYS - 1, -1, -1):
        d = date.today() - timedelta(days=back)
        try:
            last = await pipeline.compute_score(str(patient_id), d, db)
        except Exception as e:  # noqa: BLE001
            print(f"  score {label} {d}: {e}")
    if last:
        print(f"  {label:6s} ({profile:8s}) → score={last['score']:.0f} alert={last['alert_level']}")


async def seed(marie_demo: bool) -> None:
    """Peuple la base : Dr Martin + Marie (réelle) + 4 patients démo."""
    async with AsyncSessionLocal() as db:
        # 1. Dr Martin (psychiatre réel)
        martin_user = await _get_or_create_user(
            db, email=MARTIN_EMAIL, role=UserRole.psychiatre, keycloak_id=MARTIN_KC,
        )
        res = await db.execute(
            select(DoctorProfile).where(DoctorProfile.user_id == martin_user.id)
        )
        if res.scalar_one_or_none() is None:
            db.add(DoctorProfile(
                id=uuid4(), user_id=martin_user.id,
                first_name="Paul", last_name="Martin", speciality="Psychiatrie",
                created_at=datetime.now(timezone.utc),
            ))
            await db.flush()

        # 2. Marie — PATIENTE RÉELLE : compte + profil + assignation, mais PAS de
        #    données simulées (ses métriques viennent de son téléphone).
        marie_user = await _get_or_create_user(
            db, email=MARIE_EMAIL, role=UserRole.patient, keycloak_id=MARIE_KC,
        )
        marie = await _get_or_create_patient(
            db, user=marie_user, first="Marie", last="Dupont",
            gender=Gender.F, dob=date(1995, 3, 12),
        )
        await _assign(db, marie.id, martin_user.id)
        if marie_demo:
            await _gen_aggregates(db, marie.id, "rechute")

        # 3. Patients DÉMO (synthétiques)
        demos = []
        for email, first, last, gender, profile, dob in DEMO_ROSTER:
            user = await _get_or_create_user(db, email=email, role=UserRole.patient)
            patient = await _get_or_create_patient(
                db, user=user, first=first, last=last, gender=gender, dob=dob,
            )
            await _assign(db, patient.id, martin_user.id)
            await _gen_aggregates(db, patient.id, profile)
            demos.append((patient, profile, first))

        await db.commit()
        marie_note = "avec données démo" if marie_demo else "RÉELLE (capteurs téléphone)"
        print(f"[OK] Dr Martin + Marie ({marie_note}) + {len(demos)} patients démo créés.")

        # 4. Scores via le pipeline réel
        pipeline = get_pipeline()
        if marie_demo:
            await _score_patient(db, pipeline, marie.id, "Marie", "rechute")
            await db.commit()
        for patient, profile, first in demos:
            await _score_patient(db, pipeline, patient.id, first, profile)
            await db.commit()

        print("[DONE] Simulation terminée.")


async def clean() -> None:
    """Retire UNIQUEMENT les données simulées (jamais Marie/Martin réels)."""
    async with AsyncSessionLocal() as db:
        # a) Toutes les daily_aggregates marquées 'simulator' (y compris celles
        #    données à Marie via --marie-demo).
        res = await db.execute(
            delete(DailyAggregate).where(DailyAggregate.source_platform == SIM_PLATFORM)
        )
        n_aggr = res.rowcount or 0

        # b) Les patients/users de démo (@sim.test). Supprimer le User cascade
        #    sur Patient → scores/baselines/feature_vectors/assignations.
        emails = [r[0] for r in DEMO_ROSTER]
        res2 = await db.execute(
            delete(User).where(User.email.in_(emails))
        )
        n_users = res2.rowcount or 0

        await db.commit()
        print(f"[CLEAN] {n_aggr} agrégat(s) simulé(s) supprimé(s), "
              f"{n_users} patient(s) démo supprimé(s). Marie et Dr Martin conservés.")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Simulateur de patients QA Mood-IoT")
    p.add_argument(
        "--clean", action="store_true",
        help="Retire les données simulées (agrégats + patients démo), garde Marie/Martin.",
    )
    p.add_argument(
        "--marie-demo", action="store_true",
        help="Donne aussi des données simulées à Marie (démo sans téléphone réel).",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    if args.clean:
        asyncio.run(clean())
    else:
        asyncio.run(seed(marie_demo=args.marie_demo))


if __name__ == "__main__":
    main()
