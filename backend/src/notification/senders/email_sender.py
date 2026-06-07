"""
Envoi d'emails transactionnels via Resend.

Le domaine `mood-iot.fr` est vérifié chez Resend (SPF + DKIM + MX). Le
remitente par défaut est `Mood-IoT <info@mood-iot.fr>`. Pour la migration
HDS-only-EU, on basculera vers Brevo en Phase 2.8 sans changer cette
interface.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from src.shared.config import settings

logger = logging.getLogger("mood_iot.notification.email")


@dataclass
class EmailSendResult:
    success: bool
    provider_id: Optional[str] = None
    error: Optional[str] = None


async def send_email(
    *,
    to: str,
    subject: str,
    html: str,
    sender_email: str = "info@mood-iot.fr",
    sender_name: str = "Mood-IoT",
) -> EmailSendResult:
    """Envoie un email via l'API Resend."""
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY non défini — envoi email ignoré")
        return EmailSendResult(success=False, error="resend_api_key_missing")

    payload = {
        "from": f"{sender_name} <{sender_email}>",
        "to": [to],
        "subject": subject,
        "html": html,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mood-IoT/1.0",
                },
                content=json.dumps(payload),
            )
        if resp.status_code >= 400:
            logger.error(
                "Resend KO: HTTP %s — %s", resp.status_code, resp.text[:200]
            )
            return EmailSendResult(success=False, error=f"http_{resp.status_code}")
        data = resp.json()
        return EmailSendResult(success=True, provider_id=data.get("id"))
    except Exception as exc:  # noqa: BLE001 — best-effort, on log et retourne
        logger.exception("Resend exception: %s", exc)
        return EmailSendResult(success=False, error=str(exc))
