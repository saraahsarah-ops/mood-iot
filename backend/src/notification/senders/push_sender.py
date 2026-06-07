"""
Envoi de notifications push via Expo Push API.

Expo joue le rôle de wrapper unifié sur FCM (Android) + APNs (iOS). Le
token Expo est récupéré côté app mobile via `Notifications.getExpoPushTokenAsync()`
et stocké dans `notification_preferences.push_token`.

Documentation : https://docs.expo.dev/push-notifications/sending-notifications/
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional

import httpx

logger = logging.getLogger("mood_iot.notification.push")


@dataclass
class PushSendResult:
    success: bool
    provider_id: Optional[str] = None
    error: Optional[str] = None


async def send_push(
    *,
    push_token: str,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
    sound: str = "default",
    priority: str = "high",
) -> PushSendResult:
    """
    Envoie un push via Expo Push API.

    `push_token` doit être un Expo Push Token (commence par `ExponentPushToken[]`).
    """
    if not push_token.startswith("ExponentPushToken[") and not push_token.startswith(
        "ExpoPushToken["
    ):
        logger.warning("Push token format invalide : %s...", push_token[:32])
        return PushSendResult(success=False, error="invalid_token_format")

    payload = {
        "to": push_token,
        "title": title,
        "body": body,
        "sound": sound,
        "priority": priority,
        "data": data or {},
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://exp.host/--/api/v2/push/send",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Accept-Encoding": "gzip, deflate",
                },
                content=json.dumps(payload),
            )
        if resp.status_code >= 400:
            logger.error(
                "Expo Push KO: HTTP %s — %s",
                resp.status_code, resp.text[:200],
            )
            return PushSendResult(
                success=False, error=f"http_{resp.status_code}"
            )
        # Expo retourne {"data": {"status": "ok" | "error", "id": "..."}}
        data_resp = resp.json().get("data", {})
        if data_resp.get("status") == "ok":
            return PushSendResult(success=True, provider_id=data_resp.get("id"))
        return PushSendResult(
            success=False, error=data_resp.get("message", "unknown")
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Expo Push exception: %s", exc)
        return PushSendResult(success=False, error=str(exc))
