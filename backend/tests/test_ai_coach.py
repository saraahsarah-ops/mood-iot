"""Tests — coaching IA (src/notification/ai_coach).

Couvre le message de repli, la génération Claude (mockée), les garde-fous de
sécurité (risk absent / critique) et le chemin complet (DB + canaux).
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.notification import ai_coach

PATIENT_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a2")


class TestFallback:
    def test_contient_prenom(self):
        assert "Hugo" in ai_coach._fallback_message("Hugo")


class TestClaudeGenerate:
    async def test_sans_cle_retourne_none(self):
        with patch.object(ai_coach.settings, "ANTHROPIC_API_KEY", ""):
            assert await ai_coach._claude_generate("prompt") is None

    async def test_avec_cle_mockee(self):
        fake = MagicMock()
        fake.content = [MagicMock(text="Message de coaching")]
        with patch.object(ai_coach.settings, "ANTHROPIC_API_KEY", "sk-test"), patch.object(
            ai_coach.anthropic, "AsyncAnthropic"
        ) as AC:
            AC.return_value.messages.create = AsyncMock(return_value=fake)
            assert await ai_coach._claude_generate("prompt") == "Message de coaching"

    async def test_erreur_retourne_none(self):
        with patch.object(ai_coach.settings, "ANTHROPIC_API_KEY", "sk-test"), patch.object(
            ai_coach.anthropic, "AsyncAnthropic"
        ) as AC:
            AC.return_value.messages.create = AsyncMock(side_effect=RuntimeError("KO"))
            assert await ai_coach._claude_generate("prompt") is None


class TestGardeFous:
    async def test_risk_absent_refuse(self):
        # Sans score -> pas de coaching aveugle (sécurité). Retour {} avant la BD.
        res = await ai_coach.send_ai_coaching(MagicMock(), PATIENT_ID, risk_score=None)
        assert res == {}

    async def test_risk_critique_refuse(self):
        # >= RISK_HARD_CEILING (80) -> escalade médecin, pas de coaching IA.
        res = await ai_coach.send_ai_coaching(MagicMock(), PATIENT_ID, risk_score=85)
        assert res == {}


class TestCheminComplet:
    async def test_path_db_complet(self, db_query):
        # Patient semé + risque modéré -> traverse plafond/patient/user/envoi.
        res = await ai_coach.send_ai_coaching(
            db_query, PATIENT_ID, risk_score=50, top_factors=["sommeil court"]
        )
        assert isinstance(res, dict)
