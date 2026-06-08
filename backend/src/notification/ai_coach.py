"""
Service métier pour les recommandations IA (Phase 2.6).

Orchestre :
    1. Récupère le patient + ses préférences de notification
    2. Construit le contexte (top 3 anomalies via SHAP si disponible,
       ou message générique)
    3. Génère un message court FR via Claude Haiku 4.5 (modèle économique
       choisi pour le throughput attendu — ~1c€/recommandation)
    4. Envoie via les canaux activés (push + email) en utilisant le même
       pipeline que les rappels RDV (Phase 2.3).
    5. Persiste dans la table `notifications` (type=coaching_ia).

Garde-fous santé :
- Le system prompt interdit explicitement tout diagnostic.
- Disclaimer obligatoire dans tous les templates FR.
- Pas d'envoi si le risque dépasse un seuil critique (escalade médecin
  via le module `escalation` à la place).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.notification.senders.email_sender import send_email
from src.notification.senders.push_sender import send_push
from src.notification.templates.fr.ai_coaching import (
    CoachingContext,
    email_html,
    email_subject,
    push_body,
    push_title,
)
from src.shared.config import settings
from src.shared.models import (
    Notification,
    NotificationChannel,
    NotificationPreference,
    NotificationStatus,
    NotificationType,
    Patient,
    User,
)

logger = logging.getLogger("mood_iot.notification.ai_coach")

# Garde-fou : si le risque ≥ 80, on n'envoie PAS au patient — escalade au médecin
RISK_HARD_CEILING = 80

# Modèle Anthropic — Haiku 4.5 (rapide + économique pour des messages courts FR)
CLAUDE_MODEL = "claude-haiku-4-5"

# System prompt — verrouille le style + interdit les diagnostics
SYSTEM_PROMPT = (
    "Tu es un coach bienveillant pour une application de suivi du bien-être "
    "(Mood-IoT). Tu écris UNIQUEMENT en français.\n\n"
    "RÈGLES STRICTES :\n"
    "1. Ne fais JAMAIS de diagnostic médical, même implicite.\n"
    "2. N'utilise jamais les mots 'maladie', 'dépression', 'pathologie', "
    "'trouble', 'symptôme'.\n"
    "3. Ne cite jamais le score de risque numérique.\n"
    "4. Ton chaleureux, empathique, à la 2ᵉ personne du singulier ou avec "
    "le prénom de la personne.\n"
    "5. Suggestions concrètes et actionnables sur l'hygiène de vie : sommeil, "
    "marche, hydratation, respiration, contact social, exposition au soleil.\n"
    "6. Reste court : 2-3 phrases, maximum 60 mots.\n"
    "7. Si tu mentionnes une difficulté, formule-la avec douceur : "
    "'des nuits un peu courtes', 'beaucoup d'écran', 'peu de pas'."
)


async def _claude_generate(prompt: str) -> Optional[str]:
    """Génère un message court via Claude. Retourne None si KO ou pas de clé."""
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY absente — pas de génération IA")
        return None
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        return text or None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Erreur Claude : %s", exc)
        return None


def _fallback_message(first_name: str) -> str:
    """Message de secours si Claude est indisponible."""
    return (
        f"Bonjour {first_name}, prenez un moment pour respirer profondément "
        "aujourd'hui. Une petite marche dehors, même 10 minutes, peut faire "
        "beaucoup de bien."
    )


async def send_ai_coaching(
    db: AsyncSession,
    patient_id: UUID,
    *,
    risk_score: Optional[float] = None,
    top_factors: Optional[list[str]] = None,
    explanation: str = "",
) -> dict[str, bool]:
    """
    Génère une recommandation IA et l'envoie au patient via les canaux activés.

    Args:
        patient_id: UUID du patient (table patients).
        risk_score: score 0-100 (optionnel) — sert au garde-fou + au prompt.
        top_factors: liste FR des 3 principaux facteurs SHAP, par ex.
            ["sommeil court", "ritmo cardiaco élevé", "peu de pas"].
        explanation: phrase courte ajoutée à l'email (optionnel).

    Returns:
        Dict {channel_value: success}.
    """
    # 1. Garde-fou critique : pas de coaching IA si risque trop élevé
    if risk_score is not None and risk_score >= RISK_HARD_CEILING:
        logger.info(
            "Risque %s ≥ %s — escalade médecin, pas de coaching IA",
            risk_score, RISK_HARD_CEILING,
        )
        return {}

    # 2. Charge patient + user + préférences
    res = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = res.scalar_one_or_none()
    if patient is None:
        logger.warning("send_ai_coaching: patient %s introuvable", patient_id)
        return {}

    res = await db.execute(select(User).where(User.id == patient.user_id))
    recipient = res.scalar_one_or_none()
    if recipient is None:
        logger.warning("send_ai_coaching: user du patient introuvable")
        return {}

    res = await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == recipient.id
        )
    )
    prefs = res.scalar_one_or_none()
    if prefs is None:
        prefs = NotificationPreference(user_id=recipient.id)
        db.add(prefs)
        await db.flush()

    # 3. Génère le message via Claude
    factors_text = ""
    if top_factors:
        factors_text = (
            "Les signaux récents les plus marqués sont :\n"
            + "\n".join(f"- {f}" for f in top_factors)
        )
    user_prompt = (
        f"Le prénom de la personne est {patient.first_name}.\n"
        f"{factors_text}\n\n"
        "Écris un court message bienveillant (2-3 phrases, 60 mots max) "
        "pour l'accompagner dans sa journée. Pas de diagnostic. "
        "Suggère 1 action concrète d'hygiène de vie."
    )

    coaching_text = await _claude_generate(user_prompt)
    if not coaching_text:
        coaching_text = _fallback_message(patient.first_name)

    ctx = CoachingContext(
        first_name=patient.first_name,
        coaching_text=coaching_text,
        explanation=explanation,
    )

    # 4. Dispatcher sur les canaux activés
    results: dict[str, bool] = {}
    channels = [
        (NotificationChannel.push_fcm, prefs.push_enabled),
        (NotificationChannel.email, prefs.email_enabled),
    ]
    for channel, enabled in channels:
        if not enabled:
            continue
        success = await _send_one(
            db=db, channel=channel, ctx=ctx, prefs=prefs,
            recipient=recipient, patient=patient,
        )
        results[channel.value] = success

    await db.commit()
    return results


async def _send_one(
    *,
    db: AsyncSession,
    channel: NotificationChannel,
    ctx: CoachingContext,
    prefs: NotificationPreference,
    recipient: User,
    patient: Patient,
) -> bool:
    """Envoie sur un canal + persiste une ligne notifications."""
    title = push_title(ctx)
    body = push_body(ctx)
    notif = Notification(
        patient_id=patient.id,
        type=NotificationType.coaching_ia,
        level=1,
        channel=channel,
        title=title,
        body=body,
        recipient_user_id=recipient.id,
        status=NotificationStatus.pending,
    )
    db.add(notif)
    await db.flush()

    success = False
    if channel == NotificationChannel.push_fcm:
        if not prefs.push_token:
            logger.info("Pas de push_token pour user %s — skip", recipient.id)
            notif.status = NotificationStatus.failed
        else:
            result = await send_push(
                push_token=prefs.push_token,
                title=title,
                body=body,
                data={"type": "ai_coaching"},
            )
            success = result.success
    elif channel == NotificationChannel.email:
        if not recipient.email:
            notif.status = NotificationStatus.failed
        else:
            result = await send_email(
                to=recipient.email,
                subject=email_subject(ctx),
                html=email_html(ctx),
            )
            success = result.success

    if success:
        notif.status = NotificationStatus.sent
        notif.sent_at = datetime.now()
    else:
        notif.status = NotificationStatus.failed

    await db.flush()
    return success
