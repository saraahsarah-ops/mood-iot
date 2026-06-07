"""
Envoi de SMS via Twilio.

En Phase 2.8 (déploiement HDS), on basculera vers OVH SMS pour la
souveraineté EU. L'interface `send_sms(...)` reste identique.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from src.shared.config import settings

logger = logging.getLogger("mood_iot.notification.sms")


@dataclass
class SmsSendResult:
    success: bool
    provider_id: Optional[str] = None
    error: Optional[str] = None


async def send_sms(*, to: str, body: str) -> SmsSendResult:
    """Envoie un SMS via Twilio Programmable Messaging."""
    if not (
        settings.TWILIO_ACCOUNT_SID
        and settings.TWILIO_AUTH_TOKEN
        and settings.TWILIO_FROM_PHONE
    ):
        logger.warning("Twilio creds manquants — envoi SMS ignoré")
        return SmsSendResult(success=False, error="twilio_creds_missing")

    # Import paresseux : Twilio SDK est lourd, on n'importe qu'à l'usage
    try:
        from twilio.rest import Client  # type: ignore
        from twilio.base.exceptions import TwilioRestException  # type: ignore
    except ImportError:
        logger.warning("Module Twilio non installé — envoi SMS ignoré")
        return SmsSendResult(success=False, error="twilio_module_missing")

    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            from_=settings.TWILIO_FROM_PHONE,
            to=to,
            body=body,
        )
        return SmsSendResult(success=True, provider_id=msg.sid)
    except TwilioRestException as exc:
        logger.error("Twilio KO: code=%s msg=%s", exc.code, exc.msg)
        return SmsSendResult(success=False, error=f"twilio_{exc.code}")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Twilio exception: %s", exc)
        return SmsSendResult(success=False, error=str(exc))
