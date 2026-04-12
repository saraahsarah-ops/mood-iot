"""
Mood-IoT : Service de Notifications (port 8004).
Envoi et gestion des alertes selon les niveaux d'escalade.

Niveaux d'escalade :
  - Level 1 (score 40-60)  : coaching IA
  - Level 2 (score 60-80)  : alerte psychiatre
  - Level 3 (score 80-100) : urgence
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.shared.config import settings
from src.shared.auth import get_current_user, require_role
from src.shared.database import get_db

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Mood-IoT Notification Service",
    version="1.0.0",
    description="Service de notifications et alertes d'escalade",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Escalation configuration
# ---------------------------------------------------------------------------

THRESHOLDS = settings.scoring_thresholds_tuple  # (40, 60, 80)


class EscalationLevel(int, Enum):
    level_1 = 1  # 40-60 : coaching IA
    level_2 = 2  # 60-80 : alerte psychiatre
    level_3 = 3  # 80-100 : urgence


class NotificationChannel(str, Enum):
    push = "push"
    email = "email"
    sms = "sms"
    in_app = "in_app"


class NotificationPriority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


ESCALATION_CONFIG = {
    EscalationLevel.level_1: {
        "label": "Coaching IA",
        "channels": [NotificationChannel.in_app, NotificationChannel.push],
        "priority": NotificationPriority.normal,
        "description": "Score moderee (40-60) - suggestions de coaching IA",
    },
    EscalationLevel.level_2: {
        "label": "Alerte Psychiatre",
        "channels": [
            NotificationChannel.in_app,
            NotificationChannel.push,
            NotificationChannel.email,
        ],
        "priority": NotificationPriority.high,
        "description": "Score eleve (60-80) - notification au psychiatre referent",
    },
    EscalationLevel.level_3: {
        "label": "Urgence",
        "channels": [
            NotificationChannel.in_app,
            NotificationChannel.push,
            NotificationChannel.email,
            NotificationChannel.sms,
        ],
        "priority": NotificationPriority.urgent,
        "description": "Score critique (80-100) - protocole d'urgence active",
    },
}


def _determine_escalation(score: float) -> Optional[EscalationLevel]:
    if score >= THRESHOLDS[2]:
        return EscalationLevel.level_3
    elif score >= THRESHOLDS[1]:
        return EscalationLevel.level_2
    elif score >= THRESHOLDS[0]:
        return EscalationLevel.level_1
    return None


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SendNotificationRequest(BaseModel):
    patient_id: str
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=2000)
    channel: NotificationChannel = NotificationChannel.in_app
    priority: NotificationPriority = NotificationPriority.normal
    score: Optional[float] = Field(None, ge=0, le=100, description="Score de risque associe")
    metadata: Optional[dict] = None


class NotificationResponse(BaseModel):
    id: str
    patient_id: str
    title: str
    body: str
    channel: str
    priority: str
    escalation_level: Optional[int]
    escalation_label: Optional[str]
    acknowledged: bool
    acknowledged_at: Optional[str]
    created_at: str


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    total: int
    unread: int


class AcknowledgeResponse(BaseModel):
    id: str
    acknowledged: bool
    acknowledged_at: str


# ---------------------------------------------------------------------------
# In-memory store (placeholder)
# ---------------------------------------------------------------------------

_notifications_db: dict[str, dict] = {}
_patient_notifications: dict[str, list[str]] = {}

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post(
    "/notifications/send",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_notification(
    payload: SendNotificationRequest,
    current_user: dict = Depends(get_current_user),
):
    """Envoyer une notification. L'escalade est determinee automatiquement si un score est fourni."""
    escalation_level = None
    escalation_label = None

    if payload.score is not None:
        level = _determine_escalation(payload.score)
        if level is not None:
            escalation_level = level.value
            config = ESCALATION_CONFIG[level]
            escalation_label = config["label"]
            # Override priority based on escalation
            payload.priority = config["priority"]

            # TODO: send through all channels defined in config["channels"]
            # - Push: FCM (settings.FCM_CREDENTIALS_JSON)
            # - Email: SES (settings.SES_FROM_EMAIL)
            # - SMS: Twilio (settings.TWILIO_*)
            # - In-app: store in DB

    notif_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    notification = {
        "id": notif_id,
        "patient_id": payload.patient_id,
        "title": payload.title,
        "body": payload.body,
        "channel": payload.channel.value,
        "priority": payload.priority.value,
        "escalation_level": escalation_level,
        "escalation_label": escalation_label,
        "acknowledged": False,
        "acknowledged_at": None,
        "created_at": now,
    }

    _notifications_db[notif_id] = notification
    _patient_notifications.setdefault(payload.patient_id, []).append(notif_id)

    # TODO: persist to PostgreSQL, dispatch to actual channels
    return NotificationResponse(**notification)


@app.get("/notifications/{patient_id}", response_model=NotificationListResponse)
async def list_notifications(
    patient_id: str,
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """Lister les notifications d'un patient."""
    notif_ids = _patient_notifications.get(patient_id, [])
    all_notifs = [_notifications_db[nid] for nid in notif_ids]

    if unread_only:
        all_notifs = [n for n in all_notifs if not n["acknowledged"]]

    unread_count = sum(1 for n in all_notifs if not n["acknowledged"])
    page_data = all_notifs[-limit:]

    return NotificationListResponse(
        notifications=[NotificationResponse(**n) for n in page_data],
        total=len(all_notifs),
        unread=unread_count,
    )


@app.put(
    "/notifications/{notification_id}/acknowledge",
    response_model=AcknowledgeResponse,
)
async def acknowledge_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Marquer une notification comme lue."""
    notification = _notifications_db.get(notification_id)
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification introuvable",
        )

    now = datetime.now(timezone.utc).isoformat()
    notification["acknowledged"] = True
    notification["acknowledged_at"] = now

    return AcknowledgeResponse(
        id=notification_id,
        acknowledged=True,
        acknowledged_at=now,
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.notification.main:app", host="0.0.0.0", port=8004, reload=True)
