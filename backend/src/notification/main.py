"""
Mood-IoT : Service de Notifications (port 8004).
Envoi et gestion des alertes selon les niveaux d'escalade.
Connecte a PostgreSQL via SQLAlchemy async + WebSocket temps reel.

Niveaux d'escalade :
  - Level 1 (score 40-60)  : coaching IA (Claude API)
  - Level 2 (score 60-80)  : alerte psychiatre (WS + SMS + FCM + Email)
  - Level 3 (score 80-100) : urgence (tout Level 2 + appel + teleconsult auto)
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.config import settings
from src.shared.auth import get_current_user, require_role
from src.shared.database import get_db
from src.shared.models import (
    Notification,
    EscalationLog,
    NotificationType,
    NotificationChannel as NotifChannelEnum,
    NotificationStatus,
)
from src.notification.escalation import EscalationEngine
from src.notification.channels import ws_channel

logger = logging.getLogger("mood_iot.notification")

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Mood-IoT Notification Service",
    version="2.0.0",
    description="Service de notifications avec escalade reelle et WebSocket",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Modeles Pydantic
# ---------------------------------------------------------------------------


class SendNotificationRequest(BaseModel):
    patient_id: str
    score: Optional[float] = Field(None, ge=0, le=100)
    alert_level: Optional[int] = Field(None, ge=0, le=3)
    risk_score_id: Optional[str] = None
    shap_explanations: Optional[list[str]] = None
    title: Optional[str] = Field(None, max_length=255)
    body: Optional[str] = Field(None, max_length=2000)


class NotificationResponse(BaseModel):
    id: str
    patient_id: str
    type: str
    level: int
    channel: str
    title: str
    body: str
    recipient_user_id: str
    status: str
    sent_at: Optional[str]
    read_at: Optional[str]
    created_at: str


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    total: int
    unread: int


class AcknowledgeResponse(BaseModel):
    id: str
    status: str
    read_at: str


class UnreadCountResponse(BaseModel):
    patient_id: str
    unread_count: int


class EscalationSummary(BaseModel):
    alert_level: int
    channels_used: list[str]
    notifications_created: int
    success: bool

class AIAnalysisResponse(BaseModel):
    patient_id: str
    analysis: str
    generated_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _notif_to_response(n: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=str(n.id),
        patient_id=str(n.patient_id),
        type=n.type.value if hasattr(n.type, "value") else str(n.type),
        level=n.level,
        channel=n.channel.value if hasattr(n.channel, "value") else str(n.channel),
        title=n.title,
        body=n.body,
        recipient_user_id=str(n.recipient_user_id),
        status=n.status.value if hasattr(n.status, "value") else str(n.status),
        sent_at=n.sent_at.isoformat() if n.sent_at else None,
        read_at=n.read_at.isoformat() if n.read_at else None,
        created_at=n.created_at.isoformat() if n.created_at else "",
    )


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------


_rdv_scheduler = None  # type: ignore[var-annotated]


@app.on_event("startup")
async def on_startup():
    global _rdv_scheduler
    logger.info("Service Notification demarre sur le port 8004")
    logger.info("Seuils d'escalade : %s", settings.scoring_thresholds_tuple)
    # Demarrage du scheduler des rappels RDV (J-1 / H-1 / H0)
    try:
        from src.notification.rdv_scheduler import start_scheduler
        _rdv_scheduler = start_scheduler()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Echec du demarrage du scheduler RDV : %s", exc)


@app.on_event("shutdown")
async def on_shutdown():
    global _rdv_scheduler
    if _rdv_scheduler is not None:
        try:
            _rdv_scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
@app.get("/notifications/health")
async def health():
    return {"status": "healthy", "service": "notification"}


@app.post(
    "/notifications/send",
    response_model=EscalationSummary,
    status_code=status.HTTP_201_CREATED,
)
async def send_notification(
    payload: SendNotificationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Envoyer une notification.
    Si un score est fourni, l'escalade est declenchee automatiquement.
    """
    if payload.score is not None and payload.alert_level is not None and payload.alert_level >= 1:
        # Escalade automatique
        engine = EscalationEngine()
        result = await engine.process_alert(
            patient_id=payload.patient_id,
            score=payload.score,
            alert_level=payload.alert_level,
            risk_score_id=payload.risk_score_id or "",
            shap_explanations=payload.shap_explanations or [],
            db=db,
        )

        return EscalationSummary(
            alert_level=payload.alert_level,
            channels_used=result.get("channels_used", []),
            notifications_created=result.get("notifications_created", 0),
            success=result.get("success", False),
        )

    # Notification manuelle (pas d'escalade)
    if not payload.title or not payload.body:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="titre et corps requis pour une notification manuelle",
        )

    notif = Notification(
        patient_id=payload.patient_id,
        type=NotificationType.system,
        level=1,
        channel=NotifChannelEnum.websocket,
        title=payload.title,
        body=payload.body,
        recipient_user_id=current_user["user_id"],
        status=NotificationStatus.sent,
        sent_at=datetime.now(timezone.utc),
    )
    db.add(notif)
    await db.commit()
    await db.refresh(notif)

    logger.info("Notification manuelle creee: %s", notif.id)

    return EscalationSummary(
        alert_level=0,
        channels_used=["manual"],
        notifications_created=1,
        success=True,
    )


@app.get("/notifications/all", response_model=NotificationListResponse)
async def list_all_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Lister toutes les notifications du psychiatre connecte."""
    user_id = current_user["user_id"]
    query = select(Notification).where(Notification.recipient_user_id == user_id)

    if unread_only:
        query = query.where(Notification.status != NotificationStatus.read)

    # Total
    count_q = select(func.count(Notification.id)).where(
        Notification.recipient_user_id == user_id
    )
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Non lues
    unread_q = select(func.count(Notification.id)).where(
        and_(
            Notification.recipient_user_id == user_id,
            Notification.status != NotificationStatus.read,
        )
    )
    unread_result = await db.execute(unread_q)
    unread = unread_result.scalar() or 0

    # Resultats pagines
    query = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    rows = result.scalars().all()

    return NotificationListResponse(
        notifications=[_notif_to_response(n) for n in rows],
        total=total,
        unread=unread,
    )


@app.get("/notifications/{patient_id}", response_model=NotificationListResponse)
async def list_notifications(
    patient_id: str,
    unread_only: bool = Query(False),
    notification_type: Optional[str] = Query(None, description="Filtrer par type: coaching_ia, alerte_psychiatre, urgence, system"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Lister les notifications d'un patient."""
    query = select(Notification).where(Notification.patient_id == patient_id)

    if unread_only:
        query = query.where(Notification.status != NotificationStatus.read)

    if notification_type:
        try:
            ntype = NotificationType(notification_type)
            query = query.where(Notification.type == ntype)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Type invalide: {notification_type}",
            )

    # Total
    count_q = select(func.count(Notification.id)).where(
        Notification.patient_id == patient_id
    )
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Non lues
    unread_q = select(func.count(Notification.id)).where(
        and_(
            Notification.patient_id == patient_id,
            Notification.status != NotificationStatus.read,
        )
    )
    unread_result = await db.execute(unread_q)
    unread = unread_result.scalar() or 0

    # Resultats pagines
    query = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    rows = result.scalars().all()

    return NotificationListResponse(
        notifications=[_notif_to_response(n) for n in rows],
        total=total,
        unread=unread,
    )


@app.put(
    "/notifications/{notification_id}/acknowledge",
    response_model=AcknowledgeResponse,
)
async def acknowledge_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Marquer une notification comme lue."""
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )
    notification = result.scalar_one_or_none()

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification introuvable",
        )

    now = datetime.now(timezone.utc)
    notification.status = NotificationStatus.read
    notification.read_at = now
    await db.commit()

    # Audit log
    from src.shared.audit import log_action
    await log_action(
        db,
        user_id=current_user.get("user_id"),
        action="acknowledge_notification",
        resource="notification",
        resource_id=notification_id,
        details={"patient_id": str(notification.patient_id)},
    )

    logger.info("Notification %s marquee comme lue", notification_id)

    return AcknowledgeResponse(
        id=notification_id,
        status="read",
        read_at=now.isoformat(),
    )


@app.delete(
    "/notifications/{notification_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Supprimer une notification."""
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )
    notification = result.scalar_one_or_none()

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification introuvable",
        )

    # Audit log
    from src.shared.audit import log_action
    await log_action(
        db,
        user_id=current_user.get("user_id"),
        action="delete_notification",
        resource="notification",
        resource_id=notification_id,
        details={"patient_id": str(notification.patient_id)},
    )

    await db.delete(notification)
    await db.commit()

    logger.info("Notification %s supprimee", notification_id)

    return {"id": notification_id, "deleted": True}


@app.get(
    "/notifications/unread-count/{patient_id}",
    response_model=UnreadCountResponse,
)
async def unread_count(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Compter les notifications non lues d'un patient."""
    result = await db.execute(
        select(func.count(Notification.id)).where(
            and_(
                Notification.patient_id == patient_id,
                Notification.status != NotificationStatus.read,
            )
        )
    )
    count = result.scalar() or 0

    return UnreadCountResponse(patient_id=patient_id, unread_count=count)

@app.post(
    "/notifications/ai-analysis/{patient_id}",
    response_model=AIAnalysisResponse,
)
async def generate_ai_analysis(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("psychiatre", "admin")),
):
    """Genere une synthese clinique IA (historique appels, notes, messages)."""
    import anthropic
    from src.shared.models import Patient, TeleconsultSession, SessionNote, Message, MoodEntry

    # Get patient
    pat_res = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = pat_res.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient introuvable")

    # Get notes
    sess_res = await db.execute(select(TeleconsultSession).where(TeleconsultSession.patient_id == patient_id))
    session_ids = [s.id for s in sess_res.scalars().all()]
    notes = []
    if session_ids:
        notes_res = await db.execute(select(SessionNote).where(SessionNote.session_id.in_(session_ids)).order_by(SessionNote.created_at.asc()))
        notes = notes_res.scalars().all()

    # Get messages
    msg_res = await db.execute(select(Message).where((Message.sender_id == patient.user_id) | (Message.recipient_id == patient.user_id)).order_by(Message.sent_at.asc()))
    messages = msg_res.scalars().all()

    # Get mood entries
    mood_res = await db.execute(select(MoodEntry).where(MoodEntry.patient_id == patient_id).order_by(MoodEntry.submitted_at.desc()).limit(10))
    moods = list(reversed(mood_res.scalars().all()))

    # Build prompt
    prompt = f"Patient: {patient.first_name} {patient.last_name}\n"
    prompt += "--- Dernieres entrees d'humeur (PHQ-9) ---\n"
    for m in moods:
        prompt += f"[{m.submitted_at.strftime('%Y-%m-%d') if m.submitted_at else 'N/A'}] Score PHQ-9: {m.phq9_score}/27. Notes: {m.notes or 'Aucune'}\n"
    
    prompt += "\n--- Notes Cliniques ---\n"
    for n in notes:
        prompt += f"[{n.created_at.strftime('%Y-%m-%d') if n.created_at else 'N/A'}] Note: {n.content}\n"

    prompt += "\n--- Messages ---\n"
    for m in messages:
        sender = "Patient" if str(m.sender_id) == str(patient.user_id) else "Psychiatre"
        prompt += f"[{m.sent_at.strftime('%Y-%m-%d %H:%M') if m.sent_at else 'N/A'}] {sender}: {m.content}\n"

    prompt += "\nTu es un assistant medical expert. En te basant sur cet historique, redige une synthese clinique complete en francais. Identifie les tendances de l'humeur, les points cles des notes cliniques, et tire des conclusions sur l'evolution du patient. Fournis des recommandations de suivi."

    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        return AIAnalysisResponse(
            patient_id=patient_id,
            analysis="L'API IA n'est pas configuree (ANTHROPIC_API_KEY manquante). Voici un resumé factuel des données :\n" + prompt,
            generated_at=datetime.now(timezone.utc).isoformat()
        )

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system="Tu es un assistant psychiatrique. Tu reponds toujours de maniere professionnelle, structuree, et en francais.",
            messages=[{"role": "user", "content": prompt}],
        )
        analysis = response.content[0].text
    except Exception as exc:
        logger.error(f"Erreur IA: {exc}")
        analysis = "Une erreur est survenue lors de la generation de l'analyse."

    return AIAnalysisResponse(
        patient_id=patient_id,
        analysis=analysis,
        generated_at=datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# WebSocket — alertes en temps reel pour le dashboard psychiatre
# ---------------------------------------------------------------------------


@app.websocket("/notifications/ws/{user_id}")
async def websocket_alerts(websocket: WebSocket, user_id: str):
    """
    Connexion WebSocket pour recevoir les alertes en temps reel.
    Utilise par le dashboard du psychiatre.
    """
    await websocket.accept()
    ws_channel.register(user_id, websocket)
    logger.info("WebSocket connecte pour user %s", user_id)

    try:
        while True:
            # Garder la connexion ouverte, attendre les messages du client
            data = await websocket.receive_text()
            # Le client peut envoyer un "ping" pour keep-alive
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_channel.unregister(user_id)
        logger.info("WebSocket deconnecte pour user %s", user_id)


# ===========================================================================
# Rappels RDV multicanal (Phase 2.3)
# ===========================================================================


from src.notification.rdv_reminder_service import send_reminder as _send_rdv_reminder


class RdvReminderResponse(BaseModel):
    session_id: str
    kind: str  # "24h" | "1h" | "now"
    results: dict[str, bool]


@app.post(
    "/notifications/rdv/{session_id}/reminder/{kind}",
    response_model=RdvReminderResponse,
)
async def trigger_rdv_reminder(
    session_id: str,
    kind: str,  # "24h" | "1h" | "now"
    current_user: dict = Depends(require_role("admin", "psychiatre")),
    db: AsyncSession = Depends(get_db),
):
    """
    Déclenche manuellement un rappel RDV (utilisé pour les tests + l'admin
    qui veut renvoyer un rappel raté). En prod, le scheduler appelle la même
    fonction métier.
    """
    if kind not in ("24h", "1h", "now"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="kind doit être '24h', '1h' ou 'now'",
        )
    from uuid import UUID as _UUID
    results = await _send_rdv_reminder(db, _UUID(session_id), kind)  # type: ignore[arg-type]
    return RdvReminderResponse(
        session_id=session_id, kind=kind, results=results
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.notification.main:app", host="0.0.0.0", port=8004, reload=True)
