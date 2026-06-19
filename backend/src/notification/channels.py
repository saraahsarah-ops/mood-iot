"""
Mood-IoT : Canaux de notification concrets pour le systeme d'escalade.

Ce module implemente les integrations reelles avec les services externes :
  - Claude API (Anthropic) pour le coaching IA
  - Firebase Cloud Messaging (FCM) pour les notifications push
  - Twilio pour les SMS et appels vocaux
  - Amazon SES pour les emails
  - WebSocket pour la diffusion en temps reel vers le dashboard psychiatre
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic
import boto3
import firebase_admin
from firebase_admin import credentials as fb_credentials, messaging as fb_messaging
from twilio.rest import Client as TwilioClient

from src.shared.config import settings

logger = logging.getLogger("mood_iot.notification.channels")

# ---------------------------------------------------------------------------
# Canal 1 : Coaching IA via Claude (Anthropic)
# ---------------------------------------------------------------------------


class ClaudeCoachingChannel:
    """Niveau 1 : Genere un message de coaching IA via Claude API."""

    _SYSTEM_PROMPT = (
        "Tu es un assistant bienveillant specialise en sante mentale. "
        "Tu generes des messages de coaching doux et motivants en francais "
        "pour des patients suivis dans un programme de telepsychiatrie. "
        "Le ton doit etre chaleureux, empathique et encourageant. "
        "Ne fais jamais de diagnostic. Limite-toi a 3-4 phrases courtes."
    )

    def __init__(self) -> None:
        self._api_key = settings.ANTHROPIC_API_KEY
        if self._api_key:
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
        else:
            self._client = None
            logger.warning(
                "ANTHROPIC_API_KEY non configuree - le coaching IA utilisera un message par defaut"
            )

    async def generate_coaching(self, patient_context: dict) -> str:
        """
        Genere un message de coaching personnalise via Claude.

        Args:
            patient_context: dictionnaire contenant :
                - score (float) : score de risque du patient
                - shap_top3 (list[str]) : les 3 principales explications SHAP en francais
                - patient_first_name (str) : prenom du patient

        Returns:
            Message de coaching en francais.
        """
        prenom = patient_context.get("patient_first_name", "")
        score = patient_context.get("score", 0)
        shap_top3 = patient_context.get("shap_top3", [])

        # --- Cle API absente : message par defaut ---
        if not self._client:
            logger.info("Coaching IA : utilisation du message par defaut (cle API absente)")
            return (
                f"Bonjour {prenom}, nous avons remarque quelques signaux. "
                "N'oubliez pas de prendre soin de vous aujourd'hui. "
                "Respirez profondement et accordez-vous un moment de calme."
            )

        # --- Construction du prompt utilisateur ---
        explications = "\n".join(f"- {e}" for e in shap_top3) if shap_top3 else "Aucune explication disponible."
        user_prompt = (
            f"Le patient s'appelle {prenom}. "
            f"Son score de bien-etre actuel est de {score:.0f}/100 (plus le score est eleve, plus le risque est important). "
            f"Les principaux facteurs identifies sont :\n{explications}\n\n"
            "Genere un court message de coaching bienveillant et motivant en francais "
            "pour l'aider a se sentir mieux, sans mentionner le score numerique."
        )

        try:
            response = await self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                system=self._SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            message = response.content[0].text.strip()
            logger.info("Coaching IA genere avec succes pour le patient %s", prenom)
            return message

        except Exception as exc:
            logger.error("Erreur lors de la generation du coaching IA : %s", exc)
            # Fallback en cas d'erreur API
            return (
                f"Bonjour {prenom}, prenez un moment pour vous aujourd'hui. "
                "Chaque petit pas compte. Vous n'etes pas seul(e)."
            )


# ---------------------------------------------------------------------------
# Canal 2 : Push notification via Firebase Cloud Messaging (FCM)
# ---------------------------------------------------------------------------


class FCMChannel:
    """Push notification via Firebase Cloud Messaging."""

    def __init__(self) -> None:
        self._initialized = False
        creds_json = settings.FCM_CREDENTIALS_JSON

        if not creds_json or creds_json == "{}":
            logger.warning(
                "FCM_CREDENTIALS_JSON vide - les notifications push seront desactivees"
            )
            return

        try:
            creds_dict = json.loads(creds_json)
            cred = fb_credentials.Certificate(creds_dict)
            # Eviter la double initialisation de l'app Firebase
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            self._initialized = True
            logger.info("Canal FCM initialise avec succes")
        except Exception as exc:
            logger.error("Impossible d'initialiser Firebase Admin : %s", exc)

    async def send_push(
        self,
        device_token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> bool:
        """
        Envoie une notification push via FCM.

        Args:
            device_token: jeton FCM du destinataire.
            title: titre de la notification.
            body: corps de la notification.
            data: donnees supplementaires (optionnel).

        Returns:
            True si l'envoi a reussi, False sinon.
        """
        if not self._initialized:
            logger.warning("FCM non initialise - notification push ignoree")
            return False

        if not device_token:
            logger.warning("Jeton FCM manquant - notification push ignoree")
            return False

        message = fb_messaging.Message(
            notification=fb_messaging.Notification(title=title, body=body),
            data=data or {},
            token=device_token,
        )

        try:
            response = fb_messaging.send(message)
            logger.info("Notification push envoyee avec succes (id : %s)", response)
            return True
        except Exception as exc:
            logger.error("Erreur lors de l'envoi de la notification push : %s", exc)
            return False


# ---------------------------------------------------------------------------
# Canal 3 : SMS et appels vocaux via Twilio
# ---------------------------------------------------------------------------


class TwilioChannel:
    """SMS et appels via Twilio."""

    def __init__(self) -> None:
        self._account_sid = settings.TWILIO_ACCOUNT_SID
        self._auth_token = settings.TWILIO_AUTH_TOKEN
        self._api_key_sid = settings.TWILIO_API_KEY_SID
        self._api_key_secret = settings.TWILIO_API_KEY_SECRET
        self._from_phone = settings.TWILIO_FROM_PHONE
        self._client: TwilioClient | None = None

        if not self._account_sid:
            logger.warning(
                "TWILIO_ACCOUNT_SID non configure - SMS et appels desactives"
            )
            return

        # Data residency : ex. compte Irlande → region=ie1, edge=dublin.
        client_kwargs: dict[str, str] = {}
        if settings.TWILIO_REGION:
            client_kwargs["region"] = settings.TWILIO_REGION
        if settings.TWILIO_EDGE:
            client_kwargs["edge"] = settings.TWILIO_EDGE

        try:
            if self._api_key_sid and self._api_key_secret:
                # API Key (recommandé) : Client(api_key_sid, api_key_secret, account_sid)
                self._client = TwilioClient(
                    self._api_key_sid,
                    self._api_key_secret,
                    self._account_sid,
                    **client_kwargs,
                )
                logger.info("Canal Twilio initialise (API Key)")
            else:
                # Credentials primaires : Client(account_sid, auth_token)
                self._client = TwilioClient(
                    self._account_sid, self._auth_token, **client_kwargs
                )
                logger.info("Canal Twilio initialise (Auth Token)")
        except Exception as exc:
            logger.error("Impossible d'initialiser le client Twilio : %s", exc)

    async def send_sms(self, to_phone: str, message: str) -> bool:
        """
        Envoie un SMS via Twilio.

        Args:
            to_phone: numero de telephone du destinataire (format E.164).
            message: contenu du SMS.

        Returns:
            True si l'envoi a reussi, False sinon.
        """
        if not self._client:
            logger.warning("Client Twilio non initialise - SMS ignore")
            return False

        if not to_phone:
            logger.warning("Numero de telephone manquant - SMS ignore")
            return False

        try:
            msg = self._client.messages.create(
                body=message,
                from_=self._from_phone,
                to=to_phone,
            )
            logger.info("SMS envoye avec succes (SID : %s)", msg.sid)
            return True
        except Exception as exc:
            logger.error("Erreur lors de l'envoi du SMS a %s : %s", to_phone, exc)
            return False

    async def make_call(self, to_phone: str, twiml_message: str) -> bool:
        """
        Effectue un appel vocal via Twilio avec un message TwiML.

        Args:
            to_phone: numero de telephone du destinataire (format E.164).
            twiml_message: message a lire au destinataire (sera encapsule en TwiML <Say>).

        Returns:
            True si l'appel a ete initie avec succes, False sinon.
        """
        if not self._client:
            logger.warning("Client Twilio non initialise - appel ignore")
            return False

        if not to_phone:
            logger.warning("Numero de telephone manquant - appel ignore")
            return False

        twiml = (
            f'<Response><Say language="fr-FR" voice="alice">'
            f"{twiml_message}"
            f"</Say></Response>"
        )

        try:
            call = self._client.calls.create(
                twiml=twiml,
                from_=self._from_phone,
                to=to_phone,
            )
            logger.info("Appel vocal initie avec succes (SID : %s)", call.sid)
            return True
        except Exception as exc:
            logger.error("Erreur lors de l'appel vocal a %s : %s", to_phone, exc)
            return False


# ---------------------------------------------------------------------------
# Canal 4 : Email via Amazon SES
# ---------------------------------------------------------------------------


class SESChannel:
    """Email via Amazon SES."""

    def __init__(self) -> None:
        self._from_email = settings.SES_FROM_EMAIL
        self._region = settings.AWS_REGION

        try:
            ses_kwargs: dict[str, Any] = {
                "service_name": "ses",
                "region_name": self._region,
            }
            if settings.AWS_ENDPOINT_URL:
                ses_kwargs["endpoint_url"] = settings.AWS_ENDPOINT_URL

            self._client = boto3.client(**ses_kwargs)
            logger.info("Canal SES initialise (region : %s)", self._region)
        except Exception as exc:
            self._client = None
            logger.error("Impossible d'initialiser le client SES : %s", exc)

    async def send_email(self, to_email: str, subject: str, html_body: str) -> bool:
        """
        Envoie un email via Amazon SES.

        Args:
            to_email: adresse email du destinataire.
            subject: objet de l'email.
            html_body: corps HTML de l'email.

        Returns:
            True si l'envoi a reussi, False sinon.
        """
        if not self._client:
            logger.warning("Client SES non initialise - email ignore")
            return False

        if not to_email:
            logger.warning("Adresse email manquante - email ignore")
            return False

        try:
            response = self._client.send_email(
                Source=self._from_email,
                Destination={"ToAddresses": [to_email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                    },
                },
            )
            message_id = response.get("MessageId", "inconnu")
            logger.info("Email envoye avec succes a %s (MessageId : %s)", to_email, message_id)
            return True
        except Exception as exc:
            logger.error("Erreur lors de l'envoi de l'email a %s : %s", to_email, exc)
            return False


# ---------------------------------------------------------------------------
# Canal 5 : WebSocket temps reel vers le dashboard psychiatre
# ---------------------------------------------------------------------------


class WebSocketChannel:
    """Diffusion en temps reel vers le dashboard psychiatre."""

    def __init__(self) -> None:
        # Dictionnaire des connexions WebSocket actives par identifiant psychiatre
        # Cle : psychiatrist_id, Valeur : ensemble de connexions WebSocket
        self._connections: dict[str, set[Any]] = {}

    def register(self, psychiatrist_id: str, websocket: Any) -> None:
        """Enregistre une nouvelle connexion WebSocket pour un psychiatre."""
        self._connections.setdefault(psychiatrist_id, set()).add(websocket)
        logger.info(
            "WebSocket enregistre pour le psychiatre %s (%d connexion(s) active(s))",
            psychiatrist_id,
            len(self._connections[psychiatrist_id]),
        )

    def unregister(self, psychiatrist_id: str, websocket: Any) -> None:
        """Supprime une connexion WebSocket pour un psychiatre."""
        if psychiatrist_id in self._connections:
            self._connections[psychiatrist_id].discard(websocket)
            if not self._connections[psychiatrist_id]:
                del self._connections[psychiatrist_id]
            logger.info("WebSocket deconnecte pour le psychiatre %s", psychiatrist_id)

    async def broadcast_alert(self, psychiatrist_id: str, alert_data: dict) -> bool:
        """
        Diffuse une alerte a toutes les connexions WebSocket d'un psychiatre.

        Args:
            psychiatrist_id: identifiant du psychiatre destinataire.
            alert_data: donnees de l'alerte a diffuser.

        Returns:
            True si au moins une connexion a recu l'alerte, False sinon.
        """
        connections = self._connections.get(psychiatrist_id, set())

        if not connections:
            logger.warning(
                "Aucune connexion WebSocket active pour le psychiatre %s - alerte non diffusee",
                psychiatrist_id,
            )
            return False

        payload = json.dumps(alert_data, ensure_ascii=False, default=str)
        envoyees = 0
        deconnectees: list[Any] = []

        for ws in connections:
            try:
                await ws.send_text(payload)
                envoyees += 1
            except Exception as exc:
                logger.warning(
                    "Echec d'envoi WebSocket pour le psychiatre %s : %s",
                    psychiatrist_id,
                    exc,
                )
                deconnectees.append(ws)

        # Nettoyage des connexions defaillantes
        for ws in deconnectees:
            self._connections[psychiatrist_id].discard(ws)

        logger.info(
            "Alerte diffusee a %d/%d connexion(s) du psychiatre %s",
            envoyees,
            len(connections),
            psychiatrist_id,
        )
        return envoyees > 0


# ---------------------------------------------------------------------------
# Canal 6 : Email via Resend (alternative gratuite a SES)
# ---------------------------------------------------------------------------


class ResendChannel:
    """Email via Resend.com (100 emails/jour gratuits)."""

    def __init__(self) -> None:
        self._api_key = getattr(settings, "RESEND_API_KEY", "") or ""
        self._from_email = settings.SES_FROM_EMAIL
        if self._api_key:
            logger.info("Canal Resend initialise (from : %s)", self._from_email)
        else:
            logger.info("RESEND_API_KEY absente - canal Resend desactive")

    async def send_email(self, to_email: str, subject: str, html_body: str) -> bool:
        """Envoie un email via l'API Resend."""
        if not self._api_key:
            logger.warning("RESEND_API_KEY absente - email ignore")
            return False

        if not to_email:
            logger.warning("Adresse email manquante - email ignore")
            return False

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": self._from_email,
                        "to": [to_email],
                        "subject": subject,
                        "html": html_body,
                    },
                    timeout=10.0,
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    logger.info("Email Resend envoye a %s (id : %s)", to_email, data.get("id"))
                    return True
                else:
                    logger.error("Resend erreur %d : %s", resp.status_code, resp.text)
                    return False
        except Exception as exc:
            logger.error("Erreur Resend vers %s : %s", to_email, exc)
            return False


# ---------------------------------------------------------------------------
# Singletons des canaux (initialises une seule fois au demarrage)
# ---------------------------------------------------------------------------

claude_coaching = ClaudeCoachingChannel()
fcm_channel = FCMChannel()
twilio_channel = TwilioChannel()
ses_channel = SESChannel()
resend_channel = ResendChannel()
ws_channel = WebSocketChannel()


def get_email_channel():
    """Retourne le canal email actif : Resend si configure, sinon SES."""
    if resend_channel._api_key:
        return resend_channel
    return ses_channel
