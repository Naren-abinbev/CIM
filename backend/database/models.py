from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    text,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.ext.mutable import MutableList
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

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    original_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    incident_assignments: Mapped[list["IncidentCommander"]] = relationship(
        back_populates="commander",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Commander commander_id={self.commander_id!r} email={self.email!r}>"


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

    def __repr__(self) -> str:
        return f"<User id={self.id!r} username={self.username!r}>"


class IncidentMaster(Base):
    """
    Primary record for an incident submitted through the application.

    The model uses SQLAlchemy types that work with SQLite during local
    development and can be migrated to Azure SQL later.
    """

    __tablename__ = "incident_master"
    __table_args__ = (
        CheckConstraint("length(trim(category)) > 0", name="ck_incident_master_category_not_blank"),
        CheckConstraint("length(trim(status)) > 0", name="ck_incident_master_status_not_blank"),
        CheckConstraint("length(trim(source)) > 0", name="ck_incident_master_source_not_blank"),
    )

    incident_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            name="fk_incident_master_user_id_users",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
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

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="uncategorized",
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

    intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    intent_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    severity_prediction: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    severity_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    business_impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    next_best_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause_hypothesis: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    confidence_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    author_input_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    resolution_evaluation_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    recommendation_status: Mapped[str | None] = mapped_column(
        String(30), nullable=True, default="pending"
    )
    analysis_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    analysis_history: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON),
        nullable=False,
        default=list,
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

    user: Mapped[User | None] = relationship()
    commander_assignments: Mapped[list["IncidentCommander"]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<IncidentMaster incident_id={self.incident_id!r} "
            f"incident_number={self.incident_number!r}>"
        )


class IncidentCommander(Base):
    """Assignment history linking incidents and commanders."""

    __tablename__ = "incident_commanders"
    __table_args__ = (
        Index(
            "uq_incident_commanders_active_primary",
            "incident_id",
            unique=True,
            sqlite_where=text("is_primary = 1 AND unassigned_at IS NULL"),
        ),
        UniqueConstraint(
            "assignment_id",
            name="uq_incident_commanders_assignment_id",
        ),
    )

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

    assignment_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
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

    incident: Mapped[IncidentMaster] = relationship(
        back_populates="commander_assignments",
    )
    commander: Mapped[Commander] = relationship(
        back_populates="incident_assignments",
    )

    def __repr__(self) -> str:
        return (
            f"<IncidentCommander incident_id={self.incident_id!r} "
            f"commander_id={self.commander_id!r}>"
        )


class WarRoom(Base):
    """
    Metadata for a Microsoft Teams incident war room.

    Large artifacts such as transcripts, recordings, and logbooks remain in
    Blob Storage. This table stores only their storage references.
    """

    __tablename__ = "war_room"
    __table_args__ = (
        UniqueConstraint("incident_id", name="uq_war_room_incident_id"),
    )

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
    __table_args__ = (
        UniqueConstraint(
            "incident_id",
            name="uq_incident_performance_metrics_incident_id",
        ),
    )

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


class AgentExecutionLog(Base):
    """
    JSON history of all executions for an agent and incident.

    The execution-specific data is intentionally kept only in
    ``execution_history``. Each invocation, retry, or fallback attempt is one
    JSON object appended to that list.
    """

    __tablename__ = "agent_execution_log"
    __table_args__ = (
        UniqueConstraint(
            "incident_id",
            "agent_id",
            name="uq_agent_execution_log_incident_agent",
        ),
    )

    agent_execution_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_new_uuid,
    )

    incident_id: Mapped[str] = mapped_column(
        ForeignKey("incident_master.incident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    agent_id: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    execution_history: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON),
        nullable=False,
        default=list,
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

    def __repr__(self) -> str:
        return (
            f"<AgentExecutionLog agent_execution_id={self.agent_execution_id!r} "
            f"incident_id={self.incident_id!r} "
            f"agent_id={self.agent_id!r}>"
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
