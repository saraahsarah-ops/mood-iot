"""
Mood-IoT : Service Teleconsultation (port 8005).
Gestion des sessions de teleconsultation via Jitsi Meet.
Connecte a PostgreSQL via SQLAlchemy async.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.config import settings
from src.shared.auth import get_current_user, require_role
from src.shared.database import get_db
from src.shared.models import (
    TeleconsultSession,
    SessionNote,
    TeleconsultTrigger,
    TeleconsultStatus,
    AlertFeedback,
)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Mood-IoT Teleconsult Service",
    version="2.0.0",
    description="Service de teleconsultation avec integration Jitsi Meet — PostgreSQL",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class SessionStatus(str, Enum):
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class CreateSessionRequest(BaseModel):
    patient_id: str
    psychiatre_id: str
    scheduled_at: str = Field(..., description="Date/heure planifiee ISO 8601")
    duration_minutes: int = Field(30, ge=10, le=120)
    reason: Optional[str] = Field(None, max_length=500)


class SessionResponse(BaseModel):
    id: str
    patient_id: str
    psychiatre_id: str
    status: str
    scheduled_at: str
    duration_minutes: int
    reason: Optional[str]
    jitsi_room_name: Optional[str]
    jitsi_url: Optional[str]
    started_at: Optional[str]
    ended_at: Optional[str]
    created_at: str


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int


class JoinSessionResponse(BaseModel):
    session_id: str
    jitsi_url: str
    jitsi_room_name: str
    jitsi_jwt: Optional[str]
    message: str


class EndSessionRequest(BaseModel):
    summary: Optional[str] = Field(None, max_length=2000)


class SessionNoteCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    note_type: str = Field(
        "general",
        description="Type : general | observation | prescription | follow_up",
    )
    is_private: bool = Field(
        False,
        description="Notes privees visibles uniquement par le psychiatre",
    )


class SessionNoteResponse(BaseModel):
    id: str
    session_id: str
    author_id: str
    content: str
    note_type: str
    is_private: bool
    created_at: str


# ---------------------------------------------------------------------------
# Status mapping between API and DB enums
# ---------------------------------------------------------------------------

_STATUS_TO_DB = {
    "scheduled": TeleconsultStatus.scheduled,
    "in_progress": TeleconsultStatus.in_progress,
    "completed": TeleconsultStatus.completed,
    "cancelled": TeleconsultStatus.cancelled,
}

_STATUS_FROM_DB = {v: k for k, v in _STATUS_TO_DB.items()}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_jitsi_room(session_id: str) -> str:
    """Generate a unique Jitsi room name."""
    return f"mood-iot-{session_id[:8]}"


def _generate_jitsi_url(room_name: str) -> str:
    """Build the full Jitsi URL."""
    return f"{settings.JITSI_SERVER_URL}/{room_name}"


def _generate_jitsi_jwt(room_name: str, user_id: str, role: str) -> str:
    """Generate a JWT token for Jitsi authentication."""
    import time
    from jose import jwt as jose_jwt

    now = int(time.time())
    payload = {
        "aud": "jitsi",
        "iss": settings.JITSI_APP_ID,
        "sub": settings.JITSI_SERVER_URL.replace("https://", ""),
        "room": room_name,
        "exp": now + 7200,  # 2 heures
        "iat": now,
        "context": {
            "user": {
                "id": user_id,
                "name": user_id,
                "affiliation": "owner" if role == "psychiatre" else "member",
            },
        },
        "moderator": role == "psychiatre",
    }
    return jose_jwt.encode(payload, settings.JITSI_JWT_SECRET, algorithm="HS256")


def _session_to_response(s: TeleconsultSession) -> SessionResponse:
    """Convert a TeleconsultSession ORM object to SessionResponse."""
    db_status = s.status.value if hasattr(s.status, "value") else str(s.status)
    api_status = _STATUS_FROM_DB.get(s.status, db_status)

    return SessionResponse(
        id=str(s.id),
        patient_id=str(s.patient_id),
        psychiatre_id=str(s.psychiatrist_id),
        status=api_status,
        scheduled_at=s.scheduled_at.isoformat() if s.scheduled_at else "",
        duration_minutes=s.duration_min or 30,
        reason=None,  # DB model doesn't have a reason field
        jitsi_room_name=s.jitsi_room_id,
        jitsi_url=_generate_jitsi_url(s.jitsi_room_id) if s.jitsi_room_id else None,
        started_at=s.started_at.isoformat() if s.started_at else None,
        ended_at=s.ended_at.isoformat() if s.ended_at else None,
        created_at=s.created_at.isoformat() if s.created_at else "",
    )


# ---------------------------------------------------------------------------
# Endpoints - Sessions
# ---------------------------------------------------------------------------


@app.post(
    "/teleconsult/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    payload: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("psychiatre", "admin")),
):
    """Creer une session de teleconsultation."""
    session_id = str(uuid4())
    room_name = _generate_jitsi_room(session_id)

    session = TeleconsultSession(
        id=session_id,
        patient_id=payload.patient_id,
        psychiatrist_id=payload.psychiatre_id,
        trigger=TeleconsultTrigger.scheduled,
        jitsi_room_id=room_name,
        status=TeleconsultStatus.scheduled,
        scheduled_at=datetime.fromisoformat(payload.scheduled_at),
        duration_min=payload.duration_minutes,
    )
    db.add(session)
    await db.flush()

    return _session_to_response(session)


@app.get("/teleconsult/sessions", response_model=SessionListResponse)
async def list_sessions(
    patient_id: Optional[str] = Query(None),
    session_status: Optional[SessionStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Lister les sessions de teleconsultation."""
    query = select(TeleconsultSession)

    # Filter by user role
    if current_user["role"] == "patient":
        query = query.where(TeleconsultSession.patient_id == current_user["user_id"])
    elif current_user["role"] == "psychiatre":
        query = query.where(TeleconsultSession.psychiatrist_id == current_user["user_id"])

    # Additional filters
    if patient_id:
        query = query.where(TeleconsultSession.patient_id == patient_id)
    if session_status:
        db_status = _STATUS_TO_DB.get(session_status.value)
        if db_status:
            query = query.where(TeleconsultSession.status == db_status)

    # Count
    count_q = select(func.count(TeleconsultSession.id))
    if current_user["role"] == "psychiatre":
        count_q = count_q.where(
            TeleconsultSession.psychiatrist_id == current_user["user_id"]
        )
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    query = query.order_by(TeleconsultSession.scheduled_at.desc()).limit(limit)
    result = await db.execute(query)
    sessions = result.scalars().all()

    return SessionListResponse(
        sessions=[_session_to_response(s) for s in sessions],
        total=total,
    )


@app.post(
    "/teleconsult/sessions/{session_id}/join",
    response_model=JoinSessionResponse,
)
async def join_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Rejoindre une session - retourne l'URL Jitsi."""
    result = await db.execute(
        select(TeleconsultSession).where(TeleconsultSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session introuvable",
        )

    # Verify participant
    if (
        current_user["user_id"] != str(session.patient_id)
        and current_user["user_id"] != str(session.psychiatrist_id)
        and current_user["role"] != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'etes pas participant de cette session",
        )

    if session.status == TeleconsultStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette session est terminee",
        )

    if session.status == TeleconsultStatus.cancelled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette session a ete annulee",
        )

    # Start session if first to join
    room_name = session.jitsi_room_id
    jitsi_url = _generate_jitsi_url(room_name)

    if session.status == TeleconsultStatus.scheduled:
        session.status = TeleconsultStatus.in_progress
        session.started_at = datetime.now(timezone.utc)
        await db.flush()

    jitsi_jwt = _generate_jitsi_jwt(
        room_name, current_user["user_id"], current_user["role"]
    )

    return JoinSessionResponse(
        session_id=session_id,
        jitsi_url=jitsi_url,
        jitsi_room_name=room_name,
        jitsi_jwt=jitsi_jwt,
        message="Session rejointe avec succes",
    )


@app.put("/teleconsult/sessions/{session_id}/end", response_model=SessionResponse)
async def end_session(
    session_id: str,
    payload: Optional[EndSessionRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("psychiatre", "admin")),
):
    """Terminer une session de teleconsultation."""
    result = await db.execute(
        select(TeleconsultSession).where(TeleconsultSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session introuvable",
        )

    if session.status == TeleconsultStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session deja terminee",
        )

    now = datetime.now(timezone.utc)
    session.status = TeleconsultStatus.completed
    session.ended_at = now

    # Calculate actual duration
    if session.started_at:
        session.duration_min = int((now - session.started_at).total_seconds() / 60)

    # Store summary as a note if provided
    if payload and payload.summary:
        note = SessionNote(
            session_id=session_id,
            psychiatrist_id=current_user["user_id"],
            content=payload.summary,
        )
        db.add(note)

    await db.flush()

    return _session_to_response(session)


# ---------------------------------------------------------------------------
# Endpoints - Session Notes
# ---------------------------------------------------------------------------


@app.post(
    "/teleconsult/sessions/{session_id}/notes",
    response_model=SessionNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_session_note(
    session_id: str,
    payload: SessionNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Ajouter une note a une session de teleconsultation."""
    result = await db.execute(
        select(TeleconsultSession).where(TeleconsultSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session introuvable",
        )

    # Verify participant
    if (
        current_user["user_id"] != str(session.patient_id)
        and current_user["user_id"] != str(session.psychiatrist_id)
        and current_user["role"] != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'etes pas participant de cette session",
        )

    # Only psychiatre/admin can create private notes
    if payload.is_private and current_user["role"] not in ("psychiatre", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seul le psychiatre peut creer des notes privees",
        )

    note = SessionNote(
        session_id=session_id,
        psychiatrist_id=current_user["user_id"],
        content=payload.content,
    )
    db.add(note)
    await db.flush()

    return SessionNoteResponse(
        id=str(note.id),
        session_id=session_id,
        author_id=current_user["user_id"],
        content=payload.content,
        note_type=payload.note_type,
        is_private=payload.is_private,
        created_at=note.created_at.isoformat() if note.created_at else datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/teleconsult/health")
async def health():
    return {"status": "healthy", "service": "teleconsult"}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.teleconsult.main:app", host="0.0.0.0", port=8005, reload=True)
