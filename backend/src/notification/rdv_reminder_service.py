"""
Service métier pour les rappels RDV.

Orchestration :
    1. Récupère le RDV + le patient + ses préférences
    2. Construit le contexte de rendu (RdvContext)
    3. Pour chaque canal activé, rend le template FR et appelle le sender
    4. Persiste un enregistrement `notifications` + `rdv_reminder_log`
       (idempotence — pas de doublon par (session_id, kind, channel))
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.notification.senders.email_sender import send_email
from src.notification.senders.push_sender import send_push
from src.notification.senders.sms_sender import send_sms
from src.notification.templates.fr.rdv_reminder import (
    RdvContext,
    email_html,
    email_subject,
    push_body,
    push_title,
    sms_body,
)
from src.shared.config import settings
from src.shared.models import (
    DoctorProfile,
    Notification,
    NotificationChannel,
    NotificationPreference,
    NotificationStatus,
    NotificationType,
    Patient,
    RdvReminderLog,
    TeleconsultSession,
    User,
)

logger = logging.getLogger("mood_iot.notification.rdv")

ReminderKind = Literal["24h", "1h", "now"]


def _jitsi_url(session: TeleconsultSession) -> str:
    base = settings.JITSI_SERVER_URL.rstrip("/")
    room = session.jitsi_room_id or f"moodiot-{session.id}"
    return f"{base}/{room}"


async def _send_one_channel(
    *,
    db: AsyncSession,
    session: TeleconsultSession,
    kind: ReminderKind,
    channel: NotificationChannel,
    ctx: RdvContext,
    prefs: NotificationPreference,
    recipient: User,
    patient_row: Patient,
) -> bool:
    """Envoie le rappel sur un canal et persiste les traces. Retourne True si OK."""

    # 1. Idempotence : déjà envoyé ?
    existing = await db.execute(
        select(RdvReminderLog).where(
            and_(
                RdvReminderLog.session_id == session.id,
                RdvReminderLog.reminder_kind == kind,
                RdvReminderLog.channel == channel.value,
            )
        )
    )
    if existing.scalar_one_or_none() is not None:
        logger.debug(
            "Rappel %s/%s déjà envoyé pour session %s — skip",
            kind, channel.value, session.id,
        )
        return False

    # 2. Crée le Notification (status pending)
    title = push_title(kind, ctx)
    body = push_body(kind, ctx)
    notif = Notification(
        patient_id=patient_row.id,
        type=NotificationType.rdv_rappel,
        level=1,
        channel=channel,
        title=title,
        body=body,
        recipient_user_id=recipient.id,
        status=NotificationStatus.pending,
    )
    db.add(notif)
    await db.flush()

    # 3. Délègue au sender approprié
    success = False
    provider_id = None
    if channel == NotificationChannel.push_fcm:
        if not prefs.push_token:
            logger.info("Pas de push_token pour user %s — skip push", recipient.id)
            notif.status = NotificationStatus.failed
        else:
            result = await send_push(
                push_token=prefs.push_token,
                title=title,
                body=body,
                data={
                    "type": "rdv_rappel",
                    "session_id": str(session.id),
                    "scheduled_at": session.scheduled_at.isoformat() if session.scheduled_at else "",
                },
            )
            success = result.success
            provider_id = result.provider_id

    elif channel == NotificationChannel.sms:
        if not prefs.phone_e164:
            logger.info("Pas de phone_e164 pour user %s — skip sms", recipient.id)
            notif.status = NotificationStatus.failed
        else:
            result = await send_sms(to=prefs.phone_e164, body=sms_body(kind, ctx))
            success = result.success
            provider_id = result.provider_id

    elif channel == NotificationChannel.email:
        if not recipient.email:
            logger.info("Pas d'email pour user %s — skip email", recipient.id)
            notif.status = NotificationStatus.failed
        else:
            result = await send_email(
                to=recipient.email,
                subject=email_subject(kind, ctx),
                html=email_html(kind, ctx),
            )
            success = result.success
            provider_id = result.provider_id

    # 4. Met à jour le status notification + log
    if success:
        notif.status = NotificationStatus.sent
        notif.sent_at = datetime.now()
        log = RdvReminderLog(
            session_id=session.id,
            reminder_kind=kind,
            channel=channel.value,
            notification_id=notif.id,
        )
        db.add(log)
    else:
        notif.status = NotificationStatus.failed

    await db.flush()
    logger.info(
        "Rappel RDV envoyé : session=%s kind=%s channel=%s success=%s id=%s",
        session.id, kind, channel.value, success, provider_id,
    )
    return success


async def send_reminder(
    db: AsyncSession,
    session_id: UUID,
    kind: ReminderKind,
) -> dict[str, bool]:
    """
    Envoie un rappel sur tous les canaux activés pour ce patient.

    Retourne un dict {channel_value: success}.
    """
    # 1. Charge la session + patient + médecin + prefs
    res = await db.execute(
        select(TeleconsultSession).where(TeleconsultSession.id == session_id)
    )
    session = res.scalar_one_or_none()
    if session is None or session.scheduled_at is None:
        logger.warning("send_reminder: session %s introuvable ou sans date", session_id)
        return {}

    res = await db.execute(select(Patient).where(Patient.id == session.patient_id))
    patient_row = res.scalar_one_or_none()
    if patient_row is None:
        logger.warning("send_reminder: patient %s introuvable", session.patient_id)
        return {}

    res = await db.execute(select(User).where(User.id == patient_row.user_id))
    recipient = res.scalar_one_or_none()
    if recipient is None:
        logger.warning("send_reminder: user du patient introuvable")
        return {}

    res = await db.execute(
        select(DoctorProfile).where(DoctorProfile.user_id == session.psychiatrist_id)
    )
    doctor = res.scalar_one_or_none()
    if doctor:
        # Strip an existing "Dr"/"Dr." prefix to avoid "Dr Dr. Martin Dupont"
        # quand la BDD stocke deja le titre dans first_name.
        first = doctor.first_name.lstrip()
        for prefix in ("Dr.", "Dr "):
            if first.lower().startswith(prefix.lower()):
                first = first[len(prefix):].lstrip()
                break
        doctor_name = f"{first} {doctor.last_name}".strip()
    else:
        doctor_name = "votre psychiatre"
    speciality = doctor.speciality if doctor else "Psychiatrie"

    # 2. Préférences (crée si manquantes)
    res = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == recipient.id)
    )
    prefs = res.scalar_one_or_none()
    if prefs is None:
        prefs = NotificationPreference(user_id=recipient.id)
        db.add(prefs)
        await db.flush()

    # 3. Construit le contexte de rendu
    ctx = RdvContext(
        first_name=patient_row.first_name,
        doctor_name=doctor_name,
        scheduled_at=session.scheduled_at,
        speciality=speciality,
        jitsi_url=_jitsi_url(session),
        reason=session.reason or "",
    )

    # 4. Envoie sur les canaux activés
    results: dict[str, bool] = {}
    channels = [
        (NotificationChannel.push_fcm, prefs.push_enabled),
        (NotificationChannel.sms, prefs.sms_enabled),
        (NotificationChannel.email, prefs.email_enabled),
    ]
    for ch, enabled in channels:
        if not enabled:
            continue
        ok = await _send_one_channel(
            db=db, session=session, kind=kind, channel=ch,
            ctx=ctx, prefs=prefs, recipient=recipient, patient_row=patient_row,
        )
        results[ch.value] = ok

    await db.commit()
    return results
