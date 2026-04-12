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

    # ── JWT ─────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── AWS ─────────────────────────────────────────────────────────────────
    AWS_REGION: str = "eu-west-3"
    AWS_ENDPOINT_URL: str | None = None

    # ── MQTT ────────────────────────────────────────────────────────────────
    MQTT_BROKER_URL: str = "mqtt://localhost:1883"
    MQTT_TOPIC_PREFIX: str = "mood-iot"

    # ── ML Scoring ──────────────────────────────────────────────────────────
    SCORING_THRESHOLDS: str = "40/60/80"
    MODEL_S3_BUCKET: str = "mood-iot-models"

    # ── Notifications ───────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_PHONE: str = ""
    FCM_CREDENTIALS_JSON: str = "{}"
    SES_FROM_EMAIL: str = "noreply@mood-iot.fr"

    # ── Jitsi ───────────────────────────────────────────────────────────────
    JITSI_SERVER_URL: str = "https://meet.jit.si"
    JITSI_JWT_SECRET: str = "change-me"
    JITSI_APP_ID: str = "mood-iot"

    @property
    def scoring_thresholds_tuple(self) -> tuple[int, int, int]:
        """Parse '40/60/80' → (40, 60, 80)."""
        parts = self.SCORING_THRESHOLDS.split("/")
        return int(parts[0]), int(parts[1]), int(parts[2])

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
