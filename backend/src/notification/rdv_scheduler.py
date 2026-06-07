"""
Scheduler des rappels RDV.

Toutes les 5 minutes, scanne les téléconsultations programmées dans une
fenêtre [now − 5 min, now + 25 h] et déclenche les rappels qui tombent
dans une fenêtre tolérante (± 5 min autour de J-1, H-1, H0).

Idempotence garantie côté `rdv_reminder_service` (table rdv_reminder_log).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import and_, select

from src.notification.rdv_reminder_service import send_reminder
from src.shared.database import get_db_session
from src.shared.models import TeleconsultSession, TeleconsultStatus

logger = logging.getLogger("mood_iot.scheduler")

# Tolérance autour des cibles J-1 / H-1 / H0
WINDOW = timedelta(minutes=5)


async def _scan_and_send() -> None:
    """Itère sur les RDV à venir dans 25h et envoie les rappels dus."""
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(hours=25)
    async for db in get_db_session():
        res = await db.execute(
            select(TeleconsultSession).where(
                and_(
                    TeleconsultSession.status == TeleconsultStatus.scheduled,
                    TeleconsultSession.scheduled_at.isnot(None),
                    TeleconsultSession.scheduled_at >= now - WINDOW,
                    TeleconsultSession.scheduled_at <= horizon,
                )
            )
        )
        sessions = res.scalars().all()

        for s in sessions:
            sched = s.scheduled_at
            assert sched is not None
            delta = sched - now

            if abs(delta - timedelta(hours=24)) <= WINDOW:
                kind = "24h"
            elif abs(delta - timedelta(hours=1)) <= WINDOW:
                kind = "1h"
            elif abs(delta) <= WINDOW:
                kind = "now"
            else:
                continue

            try:
                results = await send_reminder(db, s.id, kind)  # type: ignore[arg-type]
                logger.info(
                    "Rappel %s envoyé pour session %s : %s",
                    kind, s.id, results,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Erreur lors de l'envoi du rappel %s pour session %s : %s",
                    kind, s.id, exc,
                )
        # Une seule itération de l'async generator
        break


def start_scheduler() -> AsyncIOScheduler:
    """Démarre le scheduler — à appeler depuis le service notification au boot."""
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        _scan_and_send,
        IntervalTrigger(minutes=5),
        id="rdv_reminders_scan",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=30),
    )
    scheduler.start()
    logger.info("Scheduler rappels RDV démarré (toutes les 5 minutes)")
    return scheduler
