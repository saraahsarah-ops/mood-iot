"""
Mood-IoT : Service Teleconsultation (port 8005).
Gestion des sessions de teleconsultation via Jitsi Meet.
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
    title="Mood-IoT Teleconsult Service",
    version="1.0.0",
    description="Service de teleconsultation avec integration Jitsi Meet",
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
# In-memory store (placeholder)
# ---------------------------------------------------------------------------

_sessions_db: dict[str, dict] = {}
_session_notes_db: dict[str, list[dict]] = {}

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
    """Generate a JWT token for Jitsi authentication. TODO: use real JWT signing."""
    # TODO: sign with settings.JITSI_JWT_SECRET using python-jose
    return f"placeholder-jitsi-jwt-{room_name}-{user_id}"


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
    current_user: dict = Depends(require_role("psychiatre", "admin")),
):
    """Creer une session de teleconsultation."""
    session_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    room_name = _generate_jitsi_room(session_id)

    session = {
        "id": session_id,
        "patient_id": payload.patient_id,
        "psychiatre_id": payload.psychiatre_id,
        "status": SessionStatus.scheduled.value,
        "scheduled_at": payload.scheduled_at,
        "duration_minutes": payload.duration_minutes,
        "reason": payload.reason,
        "jitsi_room_name": room_name,
        "jitsi_url": None,  # Generated on join
        "started_at": None,
        "ended_at": None,
        "created_at": now,
    }

    _sessions_db[session_id] = session

    # TODO: persist to PostgreSQL, send notification to patient
    return SessionResponse(**session)


@app.get("/teleconsult/sessions", response_model=SessionListResponse)
async def list_sessions(
    patient_id: Optional[str] = Query(None),
    session_status: Optional[SessionStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """Lister les sessions de teleconsultation."""
    sessions = list(_sessions_db.values())

    # Filter by user role
    if current_user["role"] == "patient":
        sessions = [s for s in sessions if s["patient_id"] == current_user["user_id"]]
    elif current_user["role"] == "psychiatre":
        sessions = [s for s in sessions if s["psychiatre_id"] == current_user["user_id"]]

    # Additional filters
    if patient_id:
        sessions = [s for s in sessions if s["patient_id"] == patient_id]
    if session_status:
        sessions = [s for s in sessions if s["status"] == session_status.value]

    return SessionListResponse(
        sessions=[SessionResponse(**s) for s in sessions[-limit:]],
        total=len(sessions),
    )


@app.post(
    "/teleconsult/sessions/{session_id}/join",
    response_model=JoinSessionResponse,
)
async def join_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Rejoindre une session - retourne l'URL Jitsi."""
    session = _sessions_db.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session introuvable",
        )

    # Verify participant
    if (
        current_user["user_id"] != session["patient_id"]
        and current_user["user_id"] != session["psychiatre_id"]
        and current_user["role"] != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'etes pas participant de cette session",
        )

    if session["status"] == SessionStatus.completed.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette session est terminee",
        )

    if session["status"] == SessionStatus.cancelled.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette session a ete annulee",
        )

    # Start session if first to join
    room_name = session["jitsi_room_name"]
    jitsi_url = _generate_jitsi_url(room_name)

    if session["status"] == SessionStatus.scheduled.value:
        session["status"] = SessionStatus.in_progress.value
        session["started_at"] = datetime.now(timezone.utc).isoformat()

    session["jitsi_url"] = jitsi_url

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
    current_user: dict = Depends(require_role("psychiatre", "admin")),
):
    """Terminer une session de teleconsultation."""
    session = _sessions_db.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session introuvable",
        )

    if session["status"] == SessionStatus.completed.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session deja terminee",
        )

    now = datetime.now(timezone.utc).isoformat()
    session["status"] = SessionStatus.completed.value
    session["ended_at"] = now

    # Store summary as a note if provided
    if payload and payload.summary:
        note_id = str(uuid4())
        note = {
            "id": note_id,
            "session_id": session_id,
            "author_id": current_user["user_id"],
            "content": payload.summary,
            "note_type": "general",
            "is_private": False,
            "created_at": now,
        }
        _session_notes_db.setdefault(session_id, []).append(note)

    return SessionResponse(**session)


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
    current_user: dict = Depends(get_current_user),
):
    """Ajouter une note a une session de teleconsultation."""
    session = _sessions_db.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session introuvable",
        )

    # Verify participant
    if (
        current_user["user_id"] != session["patient_id"]
        and current_user["user_id"] != session["psychiatre_id"]
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

    note_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    note = {
        "id": note_id,
        "session_id": session_id,
        "author_id": current_user["user_id"],
        "content": payload.content,
        "note_type": payload.note_type,
        "is_private": payload.is_private,
        "created_at": now,
    }

    _session_notes_db.setdefault(session_id, []).append(note)

    # TODO: persist to PostgreSQL
    return SessionNoteResponse(**note)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.teleconsult.main:app", host="0.0.0.0", port=8005, reload=True)
