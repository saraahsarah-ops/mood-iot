"""
Simulateur de patients pour démo / tests Mood-IoT.

Peuple la base avec :
  - Marie (patiente réelle, liée au compte Keycloak — se connecte sur l'app)
  - Dr Martin (psychiatre réel, lié au compte Keycloak — se connecte au dashboard)
  - 4 patients synthétiques (visibles dans le dashboard du médecin)
  - ~30 jours de daily_aggregates par patient avec des profils variés :
      * sain        : sommeil/activité stables
      * à risque    : sommeil court, peu d'activité
      * EN RECHUTE  : commence normal puis se dégrade (le Z-score le détecte)
  - baselines + scores calculés via le pipeline réel

Exécution (DANS le conteneur ml-scoring) :
  docker compose -f docker-compose.prod.yml --env-file .env.prod \
      exec -T ml-scoring python -m qa.simulate_patients
"""

import asyncio
import random
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select, delete

from src.shared.database import AsyncSessionLocal
from src.shared.models import (
    User, Patient, DoctorProfile, PatientPsychiatrist, DailyAggregate,
    UserRole, Gender,
)
from src.scoring.pipeline import get_pipeline
from src.scoring.main import _compute_and_store_baselines

# IDs Keycloak réels (créés précédemment)
MARIE_KC = "3ba53982-507c-4cc3-9c74-9e3542d35e35"
MARTIN_KC = "e2d7043a-37ea-4cff-877d-e6b5fe92af5f"

N_DAYS = 30
random.seed(42)


def _profile_day(profile: str, day_index: int, n_days: int) -> dict:
    """Génère les métriques d'un jour selon le profil clinique."""
    # progression 0→1 sur la période (pour la rechute)
    t = day_index / max(n_days - 1, 1)

    if profile == "sain":
        sleep = random.gauss(450, 20)        # ~7h30
        quality = random.gauss(80, 5)
        steps = random.gauss(9000, 1200)
    elif profile == "risque":
        sleep = random.gauss(370, 25)        # ~6h
        quality = random.gauss(58, 8)
        steps = random.gauss(5200, 900)
    elif profile == "rechute":
        # Normal les 2/3 du temps, puis dégradation marquée sur le dernier tiers
        if t < 0.66:
            sleep = random.gauss(445, 20)
            quality = random.gauss(78, 5)
            steps = random.gauss(8800, 1000)
        else:
            deg = (t - 0.66) / 0.34          # 0→1 sur le dernier tiers
            sleep = random.gauss(445 - 130 * deg, 20)   # le sommeil s'effondre
            quality = random.gauss(78 - 35 * deg, 6)
            steps = random.gauss(8800 - 4500 * deg, 900)  # l'activité chute
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


async def _create_patient(db, *, user, first, last, gender, profile, dob):
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
    return patient, profile


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
    # Purge éventuelle pour idempotence
    await db.execute(delete(DailyAggregate).where(DailyAggregate.patient_id == patient_id))
    today = date.today()
    for i in range(N_DAYS):
        d = today - timedelta(days=N_DAYS - 1 - i)
        m = _profile_day(profile, i, N_DAYS)
        db.add(DailyAggregate(
            id=uuid4(), patient_id=patient_id, date=d,
            source_platform="simulator",
            synced_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            **m,
        ))
    await db.flush()


async def main():
    async with AsyncSessionLocal() as db:
        # 1. Dr Martin (psychiatre réel)
        martin_user = await _get_or_create_user(
            db, email="dr.martin@example.test", role=UserRole.psychiatre,
            keycloak_id=MARTIN_KC,
        )
        res = await db.execute(select(DoctorProfile).where(DoctorProfile.user_id == martin_user.id))
        if res.scalar_one_or_none() is None:
            db.add(DoctorProfile(
                id=uuid4(), user_id=martin_user.id,
                first_name="Paul", last_name="Martin", speciality="Psychiatrie",
                created_at=datetime.now(timezone.utc),
            ))
            await db.flush()

        # 2. Patients : Marie (réelle) + synthétiques
        roster = [
            ("marie.dupont@example.test", MARIE_KC, "Marie", "Dupont", Gender.F, "rechute", date(1995, 3, 12)),
            ("paul.bernard@sim.test",     None,     "Paul", "Bernard", Gender.M, "sain",    date(1988, 7, 5)),
            ("lea.moreau@sim.test",       None,     "Léa", "Moreau",   Gender.F, "risque",  date(2000, 11, 23)),
            ("hugo.petit@sim.test",       None,     "Hugo", "Petit",   Gender.M, "rechute", date(1992, 1, 30)),
            ("emma.roux@sim.test",        None,     "Emma", "Roux",    Gender.F, "neutre",  date(1998, 9, 17)),
        ]

        patients = []
        for email, kc, first, last, gender, profile, dob in roster:
            role = UserRole.patient
            user = await _get_or_create_user(db, email=email, role=role, keycloak_id=kc)
            patient, prof = await _create_patient(
                db, user=user, first=first, last=last, gender=gender, profile=profile, dob=dob,
            )
            await _assign(db, patient.id, martin_user.id)
            await _gen_aggregates(db, patient.id, prof)
            patients.append((patient, prof, first))

        await db.commit()
        print(f"[OK] {len(patients)} patients + Dr Martin créés, {N_DAYS} jours de données chacun.")

        # 3. Baselines + scores via le pipeline réel
        pipeline = get_pipeline()
        for patient, prof, first in patients:
            try:
                await _compute_and_store_baselines(str(patient.id), db)
            except Exception as e:
                print(f"  baseline {first}: {e}")
            # Score sur les 3 derniers jours
            for back in (2, 1, 0):
                d = date.today() - timedelta(days=back)
                try:
                    r = await pipeline.compute_score(str(patient.id), d, db)
                    if back == 0:
                        print(f"  {first:6s} ({prof:8s}) → score={r['score']:.0f} alert={r['alert_level']}")
                except Exception as e:
                    print(f"  score {first} {d}: {e}")
            await db.commit()

        print("[DONE] Simulation terminée.")


if __name__ == "__main__":
    asyncio.run(main())
