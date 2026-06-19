"""
Mood-IoT : Configuration partagée entre tous les microservices.
Lit les variables d'environnement (voir .env.example).
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Variables d'environnement chargées automatiquement depuis .env."""

    # ── Service ────────────────────────────────────────────────────────────
    SERVICE_NAME: str = "gateway"
    SERVICE_PORT: int = 8000
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "DEBUG"

    # ── PostgreSQL ─────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://mood_user:mood_secret_2026@localhost:5432/mood_iot"

    # ── Redis ──────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Keycloak (source de vérité identité) ───────────────────────────────
    # Issuer = URL publique du realm. Le JWKS est dérivé depuis cette base.
    KEYCLOAK_ISSUER: str = ""  # e.g. https://auth.moodiot.fr/realms/moodiot
    KEYCLOAK_JWKS_URI: str = ""  # e.g. ${ISSUER}/protocol/openid-connect/certs
    KEYCLOAK_TOKEN_ENDPOINT: str = ""  # ${ISSUER}/protocol/openid-connect/token
    KEYCLOAK_AUDIENCE: str = "mobile-app,dashboard-medecin,backend-services"
    # Service-account client utilisé par le backend pour l'Admin API (optionnel)
    KEYCLOAK_ADMIN_CLIENT_ID: str = ""
    KEYCLOAK_ADMIN_CLIENT_SECRET: str = ""

    # ── JWT legacy (conservé seulement pour signer les tokens internes
    #    inter-services courts. NE PAS l'utiliser pour authentifier les
    #    clients : Keycloak est la source de vérité). ─────────────────────────
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"

    # ── AWS ─────────────────────────────────────────────────────────────────
    AWS_REGION: str = "eu-west-3"
    AWS_ENDPOINT_URL: str | None = None

    # ── ML Scoring ──────────────────────────────────────────────────────────
    SCORING_THRESHOLDS: str = "40/60/80"
    MODEL_S3_BUCKET: str = "mood-iot-models"
    SCORING_DISABLE_XGBOOST: bool = False

    # ── Notifications ───────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    # API Key Twilio (recommandé : révocable indépendamment des credentials
    # primaires). Si renseignée, prioritaire sur TWILIO_AUTH_TOKEN.
    TWILIO_API_KEY_SID: str = ""
    TWILIO_API_KEY_SECRET: str = ""
    TWILIO_FROM_PHONE: str = ""
    # Data residency (ex. compte Irlande : region=ie1, edge=dublin).
    # Laisser vide pour les comptes globaux (US1).
    TWILIO_REGION: str = ""
    TWILIO_EDGE: str = ""
    FCM_CREDENTIALS_JSON: str = "{}"
    SES_FROM_EMAIL: str = "noreply@mood-iot.fr"
    RESEND_API_KEY: str = ""

    # ── Jitsi ───────────────────────────────────────────────────────────────
    JITSI_SERVER_URL: str = "https://meet.jit.si"
    JITSI_JWT_SECRET: str = "change-me"
    JITSI_APP_ID: str = "mood-iot"

    # ── Chiffrement (RGPD — donnees sensibles) ────────────────────────────
    ENCRYPTION_KEY: str = ""
    FILE_UPLOAD_DIR: str = "/tmp/mood-iot-certifications"

    @property
    def scoring_thresholds_tuple(self) -> tuple[int, int, int]:
        """Parse '40/60/80' → (40, 60, 80)."""
        parts = self.SCORING_THRESHOLDS.split("/")
        return int(parts[0]), int(parts[1]), int(parts[2])

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
