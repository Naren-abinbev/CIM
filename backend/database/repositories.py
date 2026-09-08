from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.schemas.agent_execution import AgentExecutionRecord
from backend.schemas.incident_analysis import IncidentAnalysisRecord
from backend.database.models import (
    AgentExecutionLog,
    Commander,
    IncidentCommander,
    IncidentMaster,
    IncidentPerformanceMetric,
    StakeholderReport,
    User,
    WarRoom,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRepository:
    """Persistence operations for User records."""

    @staticmethod
    def get_by_id(db: Session, user_id: str) -> User | None:
        return db.get(User, user_id)

    @staticmethod
    def get_by_username(db: Session, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_email(db: Session, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create(
        db: Session,
        *,
        username: str,
        email: str,
        password_hash: str,
        role: str = "user",
        is_verified: bool = False,
    ) -> User:
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
            is_verified=is_verified,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_last_login(db: Session, user: User) -> None:
        user.last_login_at = _utcnow()
        db.commit()

    @staticmethod
    def set_active(db: Session, user: User, active: bool) -> None:
        user.is_active = active
        db.commit()


class CommanderRepository:
    """Persistence operations for Commander records."""

    @staticmethod
    def get_by_id(db: Session, commander_id: str) -> Commander | None:
        return db.get(Commander, commander_id)

    @staticmethod
    def get_by_email(db: Session, email: str) -> Commander | None:
        stmt = select(Commander).where(Commander.email == email)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_or_create(
        db: Session,
        *,
        email: str,
        original_user_id: str | None = None,
    ) -> Commander:
        commander = CommanderRepository.get_by_email(db, email)
        if commander is not None:
            if original_user_id is not None and commander.original_user_id is None:
                commander.original_user_id = original_user_id
            db.flush()
            return commander

        commander = Commander(
            email=email,
            original_user_id=original_user_id,
        )
        db.add(commander)
        db.flush()
        return commander


class IncidentRepository:
    """Persistence operations for IncidentMaster records."""

    @staticmethod
    def get_by_id(db: Session, incident_id: str) -> IncidentMaster | None:
        return db.get(IncidentMaster, incident_id)

    @staticmethod
    def get_by_number(
        db: Session,
        incident_number: str,
    ) -> IncidentMaster | None:
        stmt = select(IncidentMaster).where(
            IncidentMaster.incident_number == incident_number
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create(
        db: Session,
        *,
        incident_number: str,
        user_email: str,
        subject: str,
        short_description: str,
        description: str,
        zone: str,
        service_name: str,
        source: str,
        category: str = "uncategorized",
        user_id: str | None = None,
    ) -> IncidentMaster:
        incident = IncidentMaster(
            incident_number=incident_number,
            user_id=user_id,
            user_email=user_email,
            subject=subject,
            category=category,
            short_description=short_description,
            description=description,
            zone=zone,
            service_name=service_name,
            source=source,
        )
        db.add(incident)
        db.flush()
        return incident

    @staticmethod
    def append_analysis_record(
        db: Session,
        *,
        incident: IncidentMaster,
        analysis_record: IncidentAnalysisRecord,
    ) -> IncidentMaster:
        """Append an analysis result without replacing prior analysis history."""
        history = list(incident.analysis_history or [])
        history.append(analysis_record.model_dump(mode="json", exclude_none=True))
        incident.analysis_history = history
        incident.analysis_created_at = analysis_record.analyzed_at or _utcnow()

        # Keep the dedicated columns as a convenient projection of the latest
        # analysis while retaining every result in analysis_history.
        latest = analysis_record.model_dump(exclude_none=True)
        for field in (
            "intent",
            "intent_confidence",
            "severity_prediction",
            "severity_confidence",
            "business_impact",
            "risk_score",
            "next_best_action",
            "root_cause_hypothesis",
            "confidence_score",
            "author_input_score",
            "resolution_evaluation_score",
            "recommendation_status",
        ):
            if field in latest:
                setattr(incident, field, latest[field])
        db.flush()
        return incident


class IncidentCommanderRepository:
    """Persistence operations for incident/commander assignments."""

    @staticmethod
    def get_active_assignment(
        db: Session,
        *,
        incident_id: str,
        commander_id: str,
    ) -> IncidentCommander | None:
        stmt = select(IncidentCommander).where(
            IncidentCommander.incident_id == incident_id,
            IncidentCommander.commander_id == commander_id,
            IncidentCommander.unassigned_at.is_(None),
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create(
        db: Session,
        *,
        incident_id: str,
        commander_id: str,
        assignment_id: str | None = None,
        is_primary: bool = False,
    ) -> IncidentCommander:
        assignment = IncidentCommander(
            incident_id=incident_id,
            commander_id=commander_id,
            assignment_id=assignment_id,
            is_primary=is_primary,
        )
        db.add(assignment)
        db.flush()
        return assignment


class WarRoomRepository:
    """Persistence operations for WarRoom records."""

    @staticmethod
    def get_first_for_incident(
        db: Session,
        incident_id: str,
    ) -> WarRoom | None:
        stmt = select(WarRoom).where(WarRoom.incident_id == incident_id)
        return db.execute(stmt).scalars().first()

    @staticmethod
    def create(
        db: Session,
        *,
        incident_id: str,
        meeting_id: str,
        meeting_url: str,
    ) -> WarRoom:
        record = WarRoom(
            incident_id=incident_id,
            meeting_id=meeting_id,
            meeting_url=meeting_url,
            status="created",
        )
        db.add(record)
        db.flush()
        return record


class IncidentPerformanceMetricRepository:
    """Persistence operations for incident performance metrics."""

    @staticmethod
    def get_first_for_incident(
        db: Session,
        incident_id: str,
    ) -> IncidentPerformanceMetric | None:
        stmt = select(IncidentPerformanceMetric).where(
            IncidentPerformanceMetric.incident_id == incident_id
        )
        return db.execute(stmt).scalars().first()

    @staticmethod
    def create(
        db: Session,
        *,
        incident_id: str,
    ) -> IncidentPerformanceMetric:
        record = IncidentPerformanceMetric(incident_id=incident_id)
        db.add(record)
        db.flush()
        return record


class AgentExecutionLogRepository:
    """Persistence operations for agent execution logs."""

    @staticmethod
    def get_for_incident_and_agent(
        db: Session,
        incident_id: str,
        agent_id: str,
    ) -> AgentExecutionLog | None:
        stmt = select(AgentExecutionLog).where(
            AgentExecutionLog.incident_id == incident_id,
            AgentExecutionLog.agent_id == agent_id,
        )
        return db.execute(stmt).scalars().first()

    @staticmethod
    def create(
        db: Session,
        *,
        incident_id: str,
        agent_id: str,
    ) -> AgentExecutionLog:
        record = AgentExecutionLog(
            incident_id=incident_id,
            agent_id=agent_id,
            execution_history=[],
        )
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def append_execution_record(
        db: Session,
        *,
        record: AgentExecutionLog,
        execution_record: AgentExecutionRecord,
    ) -> AgentExecutionLog:
        history = list(record.execution_history or [])
        history.append(execution_record.model_dump(mode="json"))
        record.execution_history = history
        record.updated_at = datetime.now(timezone.utc)
        db.flush()
        return record


class StakeholderReportRepository:
    """Persistence operations for stakeholder reports."""

    @staticmethod
    def get_first_for_incident(
        db: Session,
        incident_id: str,
    ) -> StakeholderReport | None:
        stmt = select(StakeholderReport).where(
            StakeholderReport.incident_id == incident_id
        )
        return db.execute(stmt).scalars().first()

    @staticmethod
    def create(
        db: Session,
        *,
        incident_id: str,
        meeting_id: str,
        report_type: str,
    ) -> StakeholderReport:
        record = StakeholderReport(
            incident_id=incident_id,
            meeting_id=meeting_id,
            report_type=report_type,
            notification_status="pending",
        )
        db.add(record)
        db.flush()
        return record
