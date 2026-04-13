"""
Mood-IoT : Utilitaire d'audit logging.
Enregistre les actions dans la table audit_log.
"""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.models import AuditLog

logger = logging.getLogger("mood_iot.audit")


async def log_action(
    db: AsyncSession,
    *,
    user_id: Optional[str] = None,
    action: str,
    resource: str,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    """
    Enregistrer une action dans le journal d'audit.

    Args:
        db: Session de base de donnees.
        user_id: UUID de l'utilisateur (peut etre None pour les actions systeme).
        action: Type d'action (ex: "login", "compute_score", "acknowledge_notification").
        resource: Type de ressource concernee (ex: "patient", "notification", "risk_score").
        resource_id: UUID de la ressource concernee.
        ip_address: Adresse IP du client.
        details: Informations supplementaires en JSON.
    """
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            ip_address=ip_address,
            details=details,
        )
        db.add(entry)
        await db.flush()
        logger.debug(
            "Audit: %s %s/%s par user=%s",
            action, resource, resource_id, user_id,
        )
    except Exception as e:
        logger.warning("Erreur audit log (non bloquante): %s", e)
