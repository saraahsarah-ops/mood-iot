"""
Mood-IoT : Moteur d'escalade des alertes selon le niveau de risque.

Niveaux d'escalade :
  - Niveau 0 (score < 40)   : rien
  - Niveau 1 (score 40-60)  : coaching IA -> Claude genere un message -> FCM push patient
  - Niveau 2 (score 60-80)  : alerte psychiatre -> WS + SMS + FCM + Email au psychiatre
  - Niveau 3 (score 80-100) : urgence -> tout Niveau 2 + appel vocal + auto-teleconsultation
                               + SMS au contact d'urgence

Les notifications et les journaux d'escalade sont persistes en PostgreSQL.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import (
    EscalationLog,
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
    Patient,
    PatientPsychiatrist,
    TeleconsultSession,
    TeleconsultTrigger,
    TeleconsultStatus,
    User,
)
from urllib.parse import quote

from src.notification.channels import (
    claude_coaching,
    fcm_channel,
    get_email_channel,
    get_sms_channel,
    ws_channel,
)
from src.shared.config import settings

logger = logging.getLogger("mood_iot.notification.escalation")


class EscalationEngine:
    """Moteur d'escalade des alertes selon le niveau de risque."""

    # ------------------------------------------------------------------ #
    #  Point d'entree principal
    # ------------------------------------------------------------------ #

    async def process_alert(
        self,
        patient_id: str,
        score: float,
        alert_level: int,
        risk_score_id: str,
        shap_explanations: list[str],
        db: AsyncSession,
    ) -> dict:
        """
        Traite une alerte selon son niveau.

        Args:
            patient_id: identifiant unique du patient.
            score: score de risque (0-100).
            alert_level: niveau d'escalade (0, 1, 2 ou 3).
            risk_score_id: identifiant du score de risque associe.
            shap_explanations: liste des explications SHAP en francais.
            db: session de base de donnees async.

        Returns:
            Dictionnaire recapitulatif : channels_used, resultats par canal.
        """
        logger.info(
            "Traitement de l'alerte pour le patient %s - score=%.1f, niveau=%d",
            patient_id,
            score,
            alert_level,
        )

        if alert_level == 0:
            logger.info("Niveau 0 : aucune action requise pour le patient %s", patient_id)
            return {"alert_level": 0, "channels_used": [], "actions": {}}

        # --- Recuperation des donnees du patient ---
        patient = await self._get_patient(patient_id, db)
        if not patient:
            logger.error("Patient %s introuvable en base de donnees", patient_id)
            return {"alert_level": alert_level, "error": "patient_introuvable"}

        # --- Dispatch selon le niveau ---
        if alert_level == 1:
            return await self._handle_level_1(patient, score, risk_score_id, shap_explanations, db)
        elif alert_level == 2:
            return await self._handle_level_2(patient, score, risk_score_id, shap_explanations, db)
        elif alert_level == 3:
            return await self._handle_level_3(patient, score, risk_score_id, shap_explanations, db)
        else:
            logger.warning("Niveau d'escalade inconnu : %d", alert_level)
            return {"alert_level": alert_level, "error": "niveau_inconnu"}

    # ------------------------------------------------------------------ #
    #  Niveau 1 : Coaching IA
    # ------------------------------------------------------------------ #

    async def _send_patient_coaching(
        self,
        patient: Patient,
        score: float,
        risk_score_id: str,
        shap_explanations: list[str],
        db: AsyncSession,
    ) -> dict:
        """Génère une recommandation de coaching IA (Claude) -> push FCM au
        patient + persistance (type coaching_ia). Utilisé à TOUS les niveaux
        (1, 2, 3) : le patient reçoit toujours une recommandation, le plus
        important étant le niveau 1.
        """
        patient_context = {
            "score": score,
            "shap_top3": shap_explanations[:3],
            "patient_first_name": patient.first_name,
        }
        coaching_message = await claude_coaching.generate_coaching(patient_context)

        fcm_ok = await fcm_channel.send_push(
            device_token=patient.device_token_fcm or "",
            title="Mood-IoT : Conseil bien-etre",
            body=coaching_message,
            data={"type": "coaching_ia", "risk_score_id": risk_score_id},
        )

        notification = Notification(
            id=str(uuid4()),
            patient_id=str(patient.id),
            recipient_user_id=(
                str(patient.user_id)
                if getattr(patient, "user_id", None)
                else str(patient.id)
            ),
            title="Coaching IA",
            body=coaching_message,
            type=NotificationType.coaching_ia,
            level=1,
            channel=NotificationChannel.push_fcm,
            status=NotificationStatus.pending,
            risk_score_id=risk_score_id,
        )
        db.add(notification)
        await db.flush()
        logger.info("Coaching IA persiste pour le patient %s", patient.id)
        return {
            "coaching_genere": True,
            "coaching_message": coaching_message,
            "fcm_patient": fcm_ok,
        }

    async def _handle_level_1(
        self,
        patient: Patient,
        score: float,
        risk_score_id: str,
        shap_explanations: list[str],
        db: AsyncSession,
    ) -> dict:
        """Niveau 1 (40-60) : Coaching IA via Claude -> FCM push au patient."""
        logger.info("Niveau 1 - Coaching IA pour le patient %s", patient.id)
        resultats = await self._send_patient_coaching(
            patient, score, risk_score_id, shap_explanations, db
        )
        return {
            "alert_level": 1,
            "channels_used": ["claude_coaching", "fcm_patient"],
            "actions": resultats,
        }

    # ------------------------------------------------------------------ #
    #  Niveau 2 : Alerte psychiatre
    # ------------------------------------------------------------------ #

    async def _handle_level_2(
        self,
        patient: Patient,
        score: float,
        risk_score_id: str,
        shap_explanations: list[str],
        db: AsyncSession,
    ) -> dict:
        """Niveau 2 (60-80) : Alerte psychiatre -> WS + SMS + FCM + Email."""
        logger.info("Niveau 2 - Alerte psychiatre pour le patient %s", patient.id)
        resultats: dict[str, bool] = {}

        # --- Recuperation du psychiatre referent ---
        psychiatrist = await self._get_psychiatrist(str(patient.id), db)
        if not psychiatrist:
            logger.error("Aucun psychiatre referent pour le patient %s", patient.id)
            return {
                "alert_level": 2,
                "channels_used": [],
                "actions": {},
                "error": "psychiatre_introuvable",
            }

        explications_texte = "\n".join(f"- {e}" for e in shap_explanations[:3])
        alerte_titre = f"Alerte Niveau 2 : {patient.first_name} {patient.last_name}"
        alerte_corps = (
            f"Score de risque : {score:.0f}/100\n"
            f"Patient : {patient.first_name} {patient.last_name}\n"
            f"Facteurs principaux :\n{explications_texte}"
        )

        # --- 1. WebSocket vers le dashboard ---
        ws_data = {
            "type": "alerte_psychiatre",
            "level": 2,
            "patient_id": str(patient.id),
            "patient_name": f"{patient.first_name} {patient.last_name}",
            "score": score,
            "risk_score_id": risk_score_id,
            "shap_explanations": shap_explanations[:3],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        ws_ok = await ws_channel.broadcast_alert(str(psychiatrist.id), ws_data)
        resultats["websocket"] = ws_ok

        # --- 2. SMS au psychiatre ---
        sms_message = (
            f"[Mood-IoT ALERTE] Patient {patient.first_name} {patient.last_name} - "
            f"Score {score:.0f}/100. Consultez le dashboard pour plus de details."
        )
        sms_ok = await get_sms_channel().send_sms(
            to_phone=psychiatrist.phone or "",
            message=sms_message,
        )
        resultats["sms_psychiatre"] = sms_ok

        # --- 3. FCM push au psychiatre ---
        fcm_ok = await fcm_channel.send_push(
            device_token=psychiatrist.device_token_fcm or "",
            title=alerte_titre,
            body=f"Score de risque : {score:.0f}/100 - Action requise",
            data={"type": "alerte_psychiatre", "risk_score_id": risk_score_id, "level": "2"},
        )
        resultats["fcm_psychiatre"] = fcm_ok

        # --- 4. Email au psychiatre via SES ---
        html_body = self._build_alert_email_html(patient, psychiatrist, score, shap_explanations, level=2)
        email_ok = await get_email_channel().send_email(
            to_email=psychiatrist.email or "",
            subject=alerte_titre,
            html_body=html_body,
        )
        resultats["email_psychiatre"] = email_ok

        # --- Persistance de la notification ---
        notif_id = str(uuid4())
        notification = Notification(
            id=notif_id,
            patient_id=str(patient.id),
            recipient_user_id=str(psychiatrist.id),
            title=alerte_titre,
            body=alerte_corps,
            type=NotificationType.alerte_psychiatre,
            level=2,
            channel=NotificationChannel.websocket,
            status=NotificationStatus.pending,
            risk_score_id=risk_score_id,
        )
        db.add(notification)
        await db.flush()
        logger.info("Notification d'alerte psychiatre persistee (id : %s)", notif_id)

        # Le patient reçoit AUSSI une recommandation de coaching au niveau 2
        # (et donc au niveau 3 qui passe par ici) — le coaching n'est pas
        # réservé au niveau 1.
        coaching = await self._send_patient_coaching(
            patient, score, risk_score_id, shap_explanations, db
        )
        resultats.update(coaching)

        return {
            "alert_level": 2,
            "channels_used": [
                "websocket",
                "sms_psychiatre",
                "fcm_psychiatre",
                "email_psychiatre",
                "claude_coaching",
                "fcm_patient",
            ],
            "actions": resultats,
            "notification_id": notif_id,
        }

    # ------------------------------------------------------------------ #
    #  Niveau 3 : Urgence
    # ------------------------------------------------------------------ #

    async def _handle_level_3(
        self,
        patient: Patient,
        score: float,
        risk_score_id: str,
        shap_explanations: list[str],
        db: AsyncSession,
    ) -> dict:
        """
        Niveau 3 (80-100) : Urgence.
        Tout le Niveau 2 + appel vocal + auto-teleconsultation + SMS contact d'urgence.
        """
        logger.info("URGENCE - Niveau 3 pour le patient %s (score=%.1f)", patient.id, score)

        # --- Executer d'abord tout le Niveau 2 ---
        level2_result = await self._handle_level_2(patient, score, risk_score_id, shap_explanations, db)
        resultats: dict[str, bool] = dict(level2_result.get("actions", {}))

        # --- Recuperation du psychiatre (deja valide par level2) ---
        psychiatrist = await self._get_psychiatrist(str(patient.id), db)

        # NB : pas d'appel vocal — Mood-IoT n'utilise que SMS + email +
        # notifications in-app/dashboard. (L'alerte niveau 2 a déjà notifié le
        # psychiatre par SMS/email/push/WebSocket.)

        # --- 6. Creation automatique d'une session de teleconsultation (dans 2h) ---
        teleconsult_id = str(uuid4())
        scheduled_at = datetime.now(timezone.utc) + timedelta(hours=2)
        jitsi_room = f"mood-iot-urgence-{teleconsult_id[:8]}"
        lien_jitsi = f"{settings.JITSI_SERVER_URL.rstrip('/')}/{jitsi_room}"

        teleconsult = TeleconsultSession(
            id=teleconsult_id,
            patient_id=str(patient.id),
            psychiatrist_id=str(psychiatrist.id) if psychiatrist else str(uuid4()),
            trigger=TeleconsultTrigger.alert_level3,
            risk_score_id=risk_score_id,
            jitsi_room_id=jitsi_room,
            status=TeleconsultStatus.scheduled,
            scheduled_at=scheduled_at,
        )
        db.add(teleconsult)
        await db.flush()
        resultats["teleconsultation_creee"] = True
        logger.info(
            "Teleconsultation d'urgence planifiee a %s (id : %s)",
            scheduled_at.isoformat(),
            teleconsult_id,
        )

        # --- 6b. Notifier le patient de sa teleconsultation d'urgence ---
        # Le flux manuel previent deja le patient ; on fait de meme ici pour
        # que le patient soit informe du RDV auto-planifie (notif + push FCM).
        try:
            patient_notif = Notification(
                patient_id=str(patient.id),
                risk_score_id=risk_score_id,
                type=NotificationType.rdv_rappel,
                level=1,
                channel=NotificationChannel.push_fcm,
                title="Teleconsultation d'urgence programmee",
                body=(
                    f"Une teleconsultation a ete programmee a "
                    f"{scheduled_at.strftime('%H:%M')} UTC. "
                    f"Lien de connexion : {lien_jitsi}"
                ),
                recipient_user_id=patient.user_id,
                status=NotificationStatus.sent,
                sent_at=datetime.now(timezone.utc),
            )
            # Savepoint : un echec ici ne doit pas annuler l'escalade.
            async with db.begin_nested():
                db.add(patient_notif)
            push_patient_ok = await fcm_channel.send_push(
                device_token=getattr(patient, "device_token_fcm", None) or "",
                title="Teleconsultation d'urgence",
                body=(
                    f"Une teleconsultation est prevue a "
                    f"{scheduled_at.strftime('%H:%M')} UTC."
                ),
                data={"type": "rdv_rappel", "teleconsult_id": teleconsult_id},
            )
            resultats["notification_patient_teleconsult"] = push_patient_ok
        except Exception:
            logger.exception(
                "Echec notification patient (teleconsultation d'urgence) pour %s",
                patient.id,
            )
            resultats["notification_patient_teleconsult"] = False

        # --- 7. SMS au contact d'urgence du patient ---
        emergency_phone = getattr(patient, "emergency_contact_phone", None) or ""
        if emergency_phone:
            sms_urgence = (
                f"[Mood-IoT URGENCE] L'etat de {patient.first_name} {patient.last_name} "
                "necessite une attention immediate. Une teleconsultation d'urgence a ete "
                f"planifiee a {scheduled_at.strftime('%H:%M')} UTC. "
                "Merci de contacter le patient ou le service de soins."
            )
            sms_urgence_ok = await get_sms_channel().send_sms(
                to_phone=emergency_phone,
                message=sms_urgence,
            )
            resultats["sms_contact_urgence"] = sms_urgence_ok
        else:
            resultats["sms_contact_urgence"] = False
            logger.warning(
                "Contact d'urgence non renseigne pour le patient %s - SMS non envoye",
                patient.id,
            )

        # --- 8. Email d'URGENCE au psychiatre (format HTML + lien téléconsult) ---
        # Le niveau 2 a déjà envoyé l'email « Alerte » ; ici on envoie l'email
        # « URGENCE » (rouge) qui contient en plus le lien de la téléconsultation.
        if psychiatrist:
            html_urgence = self._build_alert_email_html(
                patient,
                psychiatrist,
                score,
                shap_explanations,
                level=3,
                teleconsult_link=lien_jitsi,
                teleconsult_time=scheduled_at.strftime("%H:%M"),
            )
            email_urgence_ok = await get_email_channel().send_email(
                to_email=psychiatrist.email or "",
                subject=f"URGENCE Mood-IoT : {patient.first_name} {patient.last_name}",
                html_body=html_urgence,
            )
            resultats["email_urgence_psychiatre"] = email_urgence_ok

        # --- Persistance du journal d'escalade ---
        # Note : EscalationLog ORM a : notification_id, from_level, to_level, reason
        # On cree le log apres la notification de niveau 3 pour avoir le notification_id
        # Le log est cree plus bas, apres la notification

        # --- Notification de niveau 3 ---
        notif3_id = str(uuid4())
        notification = Notification(
            id=notif3_id,
            patient_id=str(patient.id),
            recipient_user_id=str(psychiatrist.id) if psychiatrist else str(patient.id),
            title=f"URGENCE - {patient.first_name} {patient.last_name}",
            body=(
                f"Score critique : {score:.0f}/100. "
                f"Teleconsultation planifiee a {scheduled_at.strftime('%H:%M')} UTC. "
                "SMS, email et notifications envoyes."
            ),
            type=NotificationType.urgence,
            level=3,
            channel=NotificationChannel.websocket,
            status=NotificationStatus.pending,
            risk_score_id=risk_score_id,
        )
        db.add(notification)
        await db.flush()
        logger.info("Notification d'urgence persistee (id : %s)", notif3_id)

        # --- Journal d'escalade ---
        escalation_log = EscalationLog(
            id=str(uuid4()),
            notification_id=notif3_id,
            from_level=2,
            to_level=3,
            reason=f"Score critique {score:.0f}/100 - escalade automatique niveau 3",
        )
        db.add(escalation_log)
        await db.flush()
        logger.info("Journal d'escalade de niveau 3 persiste")

        all_channels = (
            level2_result.get("channels_used", [])
            + ["teleconsultation", "email_urgence", "sms_contact_urgence"]
        )

        return {
            "alert_level": 3,
            "channels_used": all_channels,
            "actions": resultats,
            "teleconsult_session_id": teleconsult_id,
            "teleconsult_scheduled_at": scheduled_at.isoformat(),
        }

    # ------------------------------------------------------------------ #
    #  Methodes utilitaires
    # ------------------------------------------------------------------ #

    async def _get_patient(self, patient_id: str, db: AsyncSession) -> Patient | None:
        """Recupere un patient depuis la base de donnees."""
        result = await db.execute(select(Patient).where(Patient.id == patient_id))
        return result.scalars().first()

    async def _get_psychiatrist(self, patient_id: str, db: AsyncSession) -> User | None:
        """Recupere le psychiatre referent d'un patient."""
        result = await db.execute(
            select(User)
            .join(
                PatientPsychiatrist,
                PatientPsychiatrist.psychiatrist_id == User.id,
            )
            .where(PatientPsychiatrist.patient_id == patient_id)
        )
        return result.scalars().first()

    def _build_alert_email_html(
        self,
        patient: Patient,
        psychiatrist: User,
        score: float,
        shap_explanations: list[str],
        level: int,
        teleconsult_link: str | None = None,
        teleconsult_time: str | None = None,
    ) -> str:
        """Construit le corps HTML de l'email d'alerte.

        Si `teleconsult_link` est fourni (niveau 3), un bloc « téléconsultation
        d'urgence » avec le lien de connexion est ajouté à l'email.
        """
        couleur_niveau = {2: "#e67e22", 3: "#e74c3c"}.get(level, "#3498db")
        label_niveau = {2: "Alerte", 3: "URGENCE"}.get(level, "Information")

        explications_html = "".join(f"<li>{e}</li>" for e in shap_explanations[:3])

        # Bloc téléconsultation d'urgence (niveau 3 uniquement).
        teleconsult_html = ""
        if teleconsult_link:
            horaire = f" (prévue à {teleconsult_time} UTC)" if teleconsult_time else ""
            teleconsult_html = f"""
                <div style="background: #fdecea; border: 1px solid {couleur_niveau};
                            border-radius: 8px; padding: 16px; margin: 16px 0;">
                    <p style="margin: 0 0 8px; font-weight: bold; color: {couleur_niveau};">
                        Téléconsultation d'urgence planifiée{horaire}
                    </p>
                    <p style="margin: 0 0 12px; font-size: 14px;">
                        Une session de téléconsultation a été créée automatiquement
                        pour ce patient. Rejoignez-la directement :
                    </p>
                    <p style="text-align: center; margin: 8px 0;">
                        <a href="{teleconsult_link}"
                           style="background: {couleur_niveau}; color: #ffffff;
                                  text-decoration: none; padding: 12px 30px;
                                  border-radius: 8px; font-weight: bold;
                                  display: inline-block; font-size: 15px;">
                            Rejoindre la téléconsultation
                        </a>
                    </p>
                    <p style="margin: 8px 0 0; font-size: 12px; color: #666; word-break: break-all;">
                        Lien : {teleconsult_link}
                    </p>
                </div>"""

        # Le nom du médecin n'est pas porté par User (il vit dans doctor_profiles).
        # On reste défensif pour ne pas planter si l'attribut est absent.
        nom_medecin = getattr(psychiatrist, "last_name", None)
        salutation = f"Dr. {nom_medecin}" if nom_medecin else "Docteur"

        # Lien profond vers la fiche du patient critique dans le dashboard.
        nom_patient = f"{patient.first_name} {patient.last_name}"
        dashboard_link = (
            f"{settings.DASHBOARD_URL.rstrip('/')}/patient"
            f"?id={patient.id}&name={quote(nom_patient)}"
        )

        return f"""
        <!DOCTYPE html>
        <html lang="fr">
        <head><meta charset="UTF-8"></head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
            <div style="background: {couleur_niveau}; color: white; padding: 16px; border-radius: 8px 8px 0 0;">
                <h2 style="margin: 0;">Mood-IoT - {label_niveau} Niveau {level}</h2>
            </div>
            <div style="border: 1px solid #ddd; padding: 20px; border-radius: 0 0 8px 8px;">
                <p>Bonjour {salutation},</p>
                <p>Un score de risque <strong>eleve ({score:.0f}/100)</strong> a ete detecte
                   pour votre patient :</p>
                <table style="width: 100%; border-collapse: collapse; margin: 12px 0;">
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Patient</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">
                            {patient.first_name} {patient.last_name}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ddd;"><strong>Score</strong></td>
                        <td style="padding: 8px; border: 1px solid #ddd;">{score:.0f} / 100</td>
                    </tr>
                </table>
                <p><strong>Facteurs identifies :</strong></p>
                <ul>{explications_html}</ul>
                {teleconsult_html}
                <p>Veuillez consulter le dashboard Mood-IoT pour plus de details et prendre
                   les mesures appropriees.</p>
                <p style="text-align: center; margin: 24px 0;">
                    <a href="{dashboard_link}"
                       style="background: {couleur_niveau}; color: #ffffff; text-decoration: none;
                              padding: 12px 30px; border-radius: 8px; font-weight: bold;
                              display: inline-block; font-size: 15px;">
                        Ouvrir la fiche du patient
                    </a>
                </p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p style="font-size: 12px; color: #888;">
                    Cet email a ete genere automatiquement par le systeme Mood-IoT.
                </p>
            </div>
        </body>
        </html>
        """


# ---------------------------------------------------------------------------
# Singleton du moteur d'escalade
# ---------------------------------------------------------------------------

escalation_engine = EscalationEngine()
