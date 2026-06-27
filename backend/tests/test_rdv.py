"""Tests — rappels de rendez-vous (src/notification/rdv_reminder_service)."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from src.notification import rdv_reminder_service as rdv
from src.shared.models import TeleconsultSession, TeleconsultStatus, TeleconsultTrigger

PATIENT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a2")
PSY_USER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000b1")


class TestSendReminderGuards:
    async def test_session_introuvable(self):
        db = MagicMock()
        result_none = MagicMock()
        result_none.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_none)
        res = await rdv.send_reminder(db, uuid.uuid4(), "24h")
        assert res == {}


class TestSendReminderComplet:
    async def test_path_db_complet(self, db_query):
        # Crée une session pour le patient/psychiatre semés, puis envoie le rappel.
        session_id = uuid.uuid4()
        db_query.add(
            TeleconsultSession(
                id=session_id,
                patient_id=PATIENT_ID,
                psychiatrist_id=PSY_USER_ID,
                trigger=TeleconsultTrigger.scheduled,
                jitsi_room_id="moodiot-rdv-test",
                status=TeleconsultStatus.scheduled,
                scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
                duration_min=30,
                reason="Suivi",
            )
        )
        await db_query.commit()

        res = await rdv.send_reminder(db_query, session_id, "24h")
        assert isinstance(res, dict)
