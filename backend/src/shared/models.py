"""
Mood-IoT : Modeles ORM SQLAlchemy 2 pour les 17 tables du schema PostgreSQL.

Organisation :
  - Zone 1 : Authentification (users, refresh_tokens, audit_log)
  - Zone 2 : Patients (patients, patient_psychiatrist, consents, mood_entries, alert_thresholds)
  - Zone 3 : ML Scoring (baselines, daily_aggregates, feature_vectors, model_versions, risk_scores)
  - Zone 4 : Notifications & Teleconsultation (notifications, escalation_log,
             teleconsult_sessions, session_notes)
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as PgEnum
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# Base declarative
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Classe de base pour tous les modeles ORM Mood-IoT."""
    pass


# ---------------------------------------------------------------------------
# Enumerations Python (mappees sur les types ENUM PostgreSQL)
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    """Role de l'utilisateur dans la plateforme."""
    patient = "patient"
    psychiatre = "psychiatre"
    admin = "admin"


class Gender(str, enum.Enum):
    """Genre du patient."""
    M = "M"
    F = "F"
    autre = "autre"


class BaselineStatus(str, enum.Enum):
    """Statut du calcul de la baseline du patient."""
    pending = "pending"
    collecting = "collecting"
    ready = "ready"


class ConsentType(str, enum.Enum):
    """Type de consentement accorde par le patient."""
    data_collection = "data_collection"
    data_sharing = "data_sharing"
    research = "research"
    notifications = "notifications"


class NotificationType(str, enum.Enum):
    """Type de notification envoyee."""
    coaching_ia = "coaching_ia"
    alerte_psychiatre = "alerte_psychiatre"
    urgence = "urgence"
    system = "system"


class NotificationChannel(str, enum.Enum):
    """Canal d'envoi de la notification."""
    push_fcm = "push_fcm"
    sms = "sms"
    email = "email"
    websocket = "websocket"
    call = "call"


class NotificationStatus(str, enum.Enum):
    """Statut de livraison de la notification."""
    pending = "pending"
    sent = "sent"
    delivered = "delivered"
    read = "read"
    failed = "failed"


class TeleconsultTrigger(str, enum.Enum):
    """Declencheur de la teleconsultation."""
    scheduled = "scheduled"
    alert_level3 = "alert_level3"
    manual = "manual"


class TeleconsultStatus(str, enum.Enum):
    """Statut de la session de teleconsultation."""
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    no_show = "no_show"


class AlertFeedback(str, enum.Enum):
    """Retour du psychiatre sur la pertinence de l'alerte."""
    confirmed_crisis = "confirmed_crisis"
    false_alarm = "false_alarm"
    partially_relevant = "partially_relevant"


# ============================================================================
# ZONE 1 — Authentification
# ============================================================================

class User(Base):
    """Utilisateur de la plateforme (patient, psychiatre ou admin)."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        PgEnum(UserRole, name="user_role", create_type=True), nullable=False
    )
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # -- Relations --
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")
    patient_profile: Mapped[Optional["Patient"]] = relationship(
        back_populates="user", uselist=False
    )


class RefreshToken(Base):
    """Jeton de rafraichissement lie a un utilisateur et un appareil."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    device_info: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # -- Relations --
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


class AuditLog(Base):
    """Journal d'audit des actions effectuees sur la plateforme."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    ip_address: Mapped[Optional[str]] = mapped_column(INET, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # -- Relations --
    user: Mapped[Optional["User"]] = relationship(back_populates="audit_logs")


# ============================================================================
# ZONE 2 — Patients
# ============================================================================

class Patient(Base):
    """Profil clinique d'un patient lie a un compte utilisateur."""

    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[Gender]] = mapped_column(
        PgEnum(Gender, name="gender", create_type=True), nullable=True
    )
    diagnosis: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    treatment_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    device_token_fcm: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    smartwatch_model: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    baseline_status: Mapped[BaselineStatus] = mapped_column(
        PgEnum(BaselineStatus, name="baseline_status", create_type=True),
        default=BaselineStatus.pending,
    )
    baseline_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # -- Relations --
    user: Mapped["User"] = relationship(back_populates="patient_profile")
    psychiatrist_assignments: Mapped[list["PatientPsychiatrist"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    consents: Mapped[list["Consent"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    mood_entries: Mapped[list["MoodEntry"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    alert_thresholds: Mapped[list["AlertThreshold"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    baselines: Mapped[list["Baseline"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    daily_aggregates: Mapped[list["DailyAggregate"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    feature_vectors: Mapped[list["FeatureVector"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    risk_scores: Mapped[list["RiskScore"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    teleconsult_sessions: Mapped[list["TeleconsultSession"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )


class PatientPsychiatrist(Base):
    """Association entre un patient et un psychiatre (N:M avec attributs)."""

    __tablename__ = "patient_psychiatrist"
    __table_args__ = (
        UniqueConstraint("patient_id", "psychiatrist_id", name="uq_patient_psychiatrist"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    psychiatrist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # -- Relations --
    patient: Mapped["Patient"] = relationship(back_populates="psychiatrist_assignments")
    psychiatrist: Mapped["User"] = relationship(foreign_keys=[psychiatrist_id])


class Consent(Base):
    """Consentement accorde ou revoque par un patient."""

    __tablename__ = "consents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    consent_type: Mapped[ConsentType] = mapped_column(
        PgEnum(ConsentType, name="consent_type", create_type=True), nullable=False
    )
    is_granted: Mapped[bool] = mapped_column(Boolean, default=False)
    granted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ip_address: Mapped[Optional[str]] = mapped_column(INET, nullable=True)

    # -- Relations --
    patient: Mapped["Patient"] = relationship(back_populates="consents")


class MoodEntry(Base):
    """Saisie d'humeur quotidienne par le patient (PHQ-9 + note subjective)."""

    __tablename__ = "mood_entries"
    __table_args__ = (
        CheckConstraint("phq9_score >= 0 AND phq9_score <= 27", name="ck_phq9_range"),
        CheckConstraint(
            "mood_rating >= 1 AND mood_rating <= 10", name="ck_mood_rating_range"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    phq9_score: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    mood_rating: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # -- Relations --
    patient: Mapped["Patient"] = relationship(back_populates="mood_entries")


class AlertThreshold(Base):
    """Seuils d'alerte personnalises par metrique pour un patient."""

    __tablename__ = "alert_thresholds"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric_name: Mapped[str] = mapped_column(String(50), nullable=False)
    z_score_warning: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    z_score_alert: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    z_score_critical: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    set_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # -- Relations --
    patient: Mapped["Patient"] = relationship(back_populates="alert_thresholds")
    set_by_user: Mapped[Optional["User"]] = relationship(foreign_keys=[set_by])


# ============================================================================
# ZONE 3 — ML Scoring
# ============================================================================

class Baseline(Base):
    """Statistiques de reference (baseline) par metrique pour un patient."""

    __tablename__ = "baselines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    metric_name: Mapped[str] = mapped_column(String(50), nullable=False)
    mean_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    std_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sample_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    window_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    window_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # -- Relations --
    patient: Mapped["Patient"] = relationship(back_populates="baselines")


class DailyAggregate(Base):
    """Agregats journaliers des donnees capteurs pour un patient."""

    __tablename__ = "daily_aggregates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    heart_rate_avg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    heart_rate_variability: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    sleep_duration_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sleep_quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    step_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gps_radius_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_locations_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    screen_time_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    call_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    call_duration_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_platform: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # -- Relations --
    patient: Mapped["Patient"] = relationship(back_populates="daily_aggregates")


class FeatureVector(Base):
    """Vecteur de caracteristiques (z-scores) calcule quotidiennement."""

    __tablename__ = "feature_vectors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    z_heart_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    z_hrv: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    z_sleep_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    z_sleep_quality: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    z_step_count: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    z_gps_radius: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    z_screen_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    z_call_frequency: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trend_7d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trend_14d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_weekend: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    vector_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # -- Relations --
    patient: Mapped["Patient"] = relationship(back_populates="feature_vectors")
    risk_scores: Mapped[list["RiskScore"]] = relationship(
        back_populates="feature_vector"
    )


class ModelVersion(Base):
    """Version d'un modele ML deploye (artefact S3, metriques, promotion)."""

    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    version: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    algorithm: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    s3_artifact_path: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    training_samples: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metrics_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    promoted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RiskScore(Base):
    """Score de risque quotidien calcule par le modele ML."""

    __tablename__ = "risk_scores"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_risk_score_range"),
        CheckConstraint(
            "alert_level >= 0 AND alert_level <= 3", name="ck_alert_level_range"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    alert_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    feature_vector_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("feature_vectors.id", ondelete="SET NULL"),
        nullable=True,
    )
    shap_values: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # -- Relations --
    patient: Mapped["Patient"] = relationship(back_populates="risk_scores")
    feature_vector: Mapped[Optional["FeatureVector"]] = relationship(
        back_populates="risk_scores"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="risk_score"
    )
    teleconsult_sessions: Mapped[list["TeleconsultSession"]] = relationship(
        back_populates="risk_score"
    )


# ============================================================================
# ZONE 4 — Notifications & Teleconsultation
# ============================================================================

class Notification(Base):
    """Notification envoyee a un utilisateur (patient ou psychiatre)."""

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("level >= 1 AND level <= 3", name="ck_notification_level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    risk_score_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_scores.id", ondelete="SET NULL"),
        nullable=True,
    )
    type: Mapped[NotificationType] = mapped_column(
        PgEnum(NotificationType, name="notification_type", create_type=True),
        nullable=False,
    )
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    channel: Mapped[NotificationChannel] = mapped_column(
        PgEnum(NotificationChannel, name="notification_channel", create_type=True),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[NotificationStatus] = mapped_column(
        PgEnum(NotificationStatus, name="notification_status", create_type=True),
        default=NotificationStatus.pending,
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # -- Relations --
    patient: Mapped["Patient"] = relationship(back_populates="notifications")
    risk_score: Mapped[Optional["RiskScore"]] = relationship(
        back_populates="notifications"
    )
    recipient: Mapped["User"] = relationship(foreign_keys=[recipient_user_id])
    escalation_logs: Mapped[list["EscalationLog"]] = relationship(
        back_populates="notification", cascade="all, delete-orphan"
    )


class EscalationLog(Base):
    """Historique des escalades de niveau pour une notification."""

    __tablename__ = "escalation_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    notification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_level: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    to_level: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    escalated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # -- Relations --
    notification: Mapped["Notification"] = relationship(
        back_populates="escalation_logs"
    )


class TeleconsultSession(Base):
    """Session de teleconsultation via Jitsi entre patient et psychiatre."""

    __tablename__ = "teleconsult_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
    )
    psychiatrist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    trigger: Mapped[TeleconsultTrigger] = mapped_column(
        PgEnum(TeleconsultTrigger, name="teleconsult_trigger", create_type=True),
        nullable=False,
    )
    risk_score_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_scores.id", ondelete="SET NULL"),
        nullable=True,
    )
    jitsi_room_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    jitsi_jwt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[TeleconsultStatus] = mapped_column(
        PgEnum(TeleconsultStatus, name="teleconsult_status", create_type=True),
        default=TeleconsultStatus.scheduled,
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # -- Relations --
    patient: Mapped["Patient"] = relationship(back_populates="teleconsult_sessions")
    psychiatrist: Mapped["User"] = relationship(foreign_keys=[psychiatrist_id])
    risk_score: Mapped[Optional["RiskScore"]] = relationship(
        back_populates="teleconsult_sessions"
    )
    notes: Mapped[list["SessionNote"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class SessionNote(Base):
    """Notes cliniques redigees par le psychiatre apres une teleconsultation."""

    __tablename__ = "session_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teleconsult_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    psychiatrist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    alert_feedback: Mapped[Optional[AlertFeedback]] = mapped_column(
        PgEnum(AlertFeedback, name="alert_feedback", create_type=True), nullable=True
    )
    treatment_adjustment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # -- Relations --
    session: Mapped["TeleconsultSession"] = relationship(back_populates="notes")
    psychiatrist: Mapped["User"] = relationship(foreign_keys=[psychiatrist_id])
