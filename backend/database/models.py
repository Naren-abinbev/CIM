from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Numeric,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Commander(Base):
    """Person who can be associated with one or more incidents."""

    __tablename__ = "commanders"

    commander_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    incident_links: Mapped[list["IncidentCommander"]] = relationship(
        back_populates="commander",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Commander commander_id={self.commander_id!r} name={self.name!r}>"


class User(Base):
    """
    Application user account.

    Passwords are never stored in plaintext.
    Only the bcrypt hash is persisted.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )

    username: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(32),
        default="user",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id!r} username={self.username!r}>"


class IncidentMaster(Base):
    """
    Primary record for an incident submitted through the application.

    The model uses SQLAlchemy types that work with SQLite during local
    development and can be migrated to Azure SQL later.
    """

    __tablename__ = "incident_master"

    incident_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )

    incident_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    user_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    subject: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    short_description: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    zone: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    service_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    severity: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="submitted",
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<IncidentMaster incident_id={self.incident_id!r} "
            f"incident_number={self.incident_number!r}>"
        )


class IncidentCommander(Base):
    """Assignment history linking incidents and commanders."""

    __tablename__ = "incident_commanders"

    incident_commander_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )

    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incident_master.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    commander_id: Mapped[str] = mapped_column(
        ForeignKey("commanders.commander_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    unassigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    incident: Mapped[IncidentMaster] = relationship()
    commander: Mapped[Commander] = relationship(
        back_populates="incident_links",
    )

    def __repr__(self) -> str:
        return (
            f"<IncidentCommander incident_id={self.incident_id!r} "
            f"commander_id={self.commander_id!r}>"
        )


class IncidentAnalysis(Base):
    """
    AI-generated analysis for an incident.

    Analysis is stored separately from IncidentMaster so that an incident can
    be analyzed repeatedly while preserving each analysis result.
    """

    __tablename__ = "incident_analysis"

    analysis_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )

    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incident_master.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    intent: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    intent_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    severity_prediction: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    severity_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    business_impact: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    risk_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    next_best_action: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    root_cause_hypothesis: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    blast_radius: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    confidence_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    author_input_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    resolution_evaluation_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    recommendation_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    incident: Mapped[IncidentMaster] = relationship()

    def __repr__(self) -> str:
        return (
            f"<IncidentAnalysis analysis_id={self.analysis_id!r} "
            f"incident_id={self.incident_id!r}>"
        )


class DuplicateIdentification(Base):
    """
    Result of evaluating whether an incident duplicates another incident.

    Each evaluation is stored as a separate record so the same incident pair
    can be evaluated again using a different retrieval or decision process.
    """

    __tablename__ = "duplicate_identification"

    duplicate_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )

    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incident_master.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    matched_incident_id: Mapped[str] = mapped_column(
        ForeignKey("incident_master.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    similarity_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
    )

    evaluation_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    decision: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    detection_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<DuplicateIdentification duplicate_id={self.duplicate_id!r} "
            f"incident_id={self.incident_id!r} "
            f"matched_incident_id={self.matched_incident_id!r}>"
        )


class BlastRadius(Base):
    """
    Service or component affected by an incident.

    One incident can have multiple blast-radius records, with one row for
    each affected service or component identified by the analysis.
    """

    __tablename__ = "blast_radius"

    blast_radius_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )

    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incident_master.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    affected_service: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    affected_component: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    dependency_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    impact_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    correlation_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
    )

    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
    )

    evidence: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<BlastRadius blast_radius_id={self.blast_radius_id!r} "
            f"incident_id={self.incident_id!r}>"
        )


class ResolutionIntelligence(Base):
    """
    AI-generated and implemented resolution details for an incident.

    Resolution recommendations and the final implemented resolution are kept
    in the same record so the recommendation can be compared with the result.
    """

    __tablename__ = "resolution_intelligence"

    resolution_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )

    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incident_master.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    resolver_team: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    resolver_user: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    recommended_resolution: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    actual_resolution: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    rollback_recommendation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    root_cause: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    resolution_source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    resolution_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    resolution_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<ResolutionIntelligence resolution_id={self.resolution_id!r} "
            f"incident_id={self.incident_id!r}>"
        )


class WarRoom(Base):
    """
    Metadata for a Microsoft Teams incident war room.

    Large artifacts such as transcripts, recordings, and logbooks remain in
    Blob Storage. This table stores only their storage references.
    """

    __tablename__ = "war_room"

    war_room_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )

    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incident_master.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    meeting_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    meeting_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="created",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    transcript_blob_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    recording_blob_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    logbook_blob_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<WarRoom war_room_id={self.war_room_id!r} "
            f"incident_id={self.incident_id!r}>"
        )


class IncidentPerformanceMetric(Base):
    """
    Lifecycle timestamps and duration metrics for an incident.

    Metric values can be updated as detection, acknowledgement, war-room,
    resolution, and completion events occur.
    """

    __tablename__ = "incident_performance_metrics"

    metric_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )

    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incident_master.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    detected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    war_room_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    resolution_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    mttd_seconds: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    mtta_seconds: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    mttr_seconds: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<IncidentPerformanceMetric metric_id={self.metric_id!r} "
            f"incident_id={self.incident_id!r}>"
        )


class AgentExecution(Base):
    """
    Execution-level observability record for an AI agent.

    Stores model usage, timing, scores, and failure information for each
    major agent execution associated with an incident.
    """

    __tablename__ = "agent_execution"

    execution_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )

    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incident_master.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    agent_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    model_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    model_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    execution_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="running",
    )

    input_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    output_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    total_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    latency_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    confidence_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    evaluation_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    judge_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    reasoning_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<AgentExecution execution_id={self.execution_id!r} "
            f"incident_id={self.incident_id!r} "
            f"agent_name={self.agent_name!r}>"
        )


class ModelFallback(Base):
    """
    Record of a model attempt made during an agent execution.

    Multiple records can belong to one agent execution when the application
    moves from a primary model to a warm or cold fallback model.
    """

    __tablename__ = "model_fallback"

    model_execution_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )

    execution_id: Mapped[str] = mapped_column(
        ForeignKey("agent_execution.execution_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    model_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    fallback_level: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    latency_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<ModelFallback model_execution_id={self.model_execution_id!r} "
            f"execution_id={self.execution_id!r} "
            f"model_name={self.model_name!r}>"
        )


class StakeholderReport(Base):
    """
    Metadata for a generated stakeholder report.

    The report content is stored in Blob Storage; this table stores its
    incident/meeting association, type, storage reference, and notification
    delivery status.
    """

    __tablename__ = "stakeholder_report"

    report_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )

    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incident_master.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    meeting_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    report_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    report_blob_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    notification_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )

    def __repr__(self) -> str:
        return (
            f"<StakeholderReport report_id={self.report_id!r} "
            f"incident_id={self.incident_id!r} "
            f"report_type={self.report_type!r}>"
        )


class RefreshToken(Base):
    """
    Server-side refresh-token session record.

    Only a cryptographic hash of the raw token is stored.
    The raw refresh token exists only on the client.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    token_hash: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=False,
    )

    token_family: Mapped[str] = mapped_column(
        String(36),
        index=True,
        nullable=False,
    )

    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    replaced_by_token_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    user: Mapped[User] = relationship(
        back_populates="refresh_tokens",
    )

    def __repr__(self) -> str:
        return (
            f"<RefreshToken id={self.id!r} "
            f"family={self.token_family!r}>"
        )
