from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import (
    AgentExecution,
    BlastRadius,
    Commander,
    DuplicateIdentification,
    IncidentAnalysis,
    IncidentCommander,
    IncidentMaster,
    IncidentPerformanceMetric,
    ModelFallback,
    RefreshToken,
    ResolutionIntelligence,
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


class RefreshTokenRepository:
    """Persistence operations for RefreshToken records."""

    @staticmethod
    def get_by_hash(db: Session, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create(
        db: Session,
        *,
        user_id: str,
        token_hash: str,
        token_family: str,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> RefreshToken:
        record = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            token_family=token_family,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def revoke(
        db: Session,
        record: RefreshToken,
        *,
        replaced_by_token_id: str | None = None,
    ) -> None:
        record.revoked_at = _utcnow()
        record.replaced_by_token_id = replaced_by_token_id
        db.commit()

    @staticmethod
    def revoke_family(db: Session, token_family: str) -> None:
        """
        Revoke every token in a family.

        Used when refresh-token reuse is detected.
        """
        stmt = select(RefreshToken).where(
            RefreshToken.token_family == token_family,
            RefreshToken.revoked_at.is_(None),
        )
        records = db.execute(stmt).scalars().all()

        now = _utcnow()

        for record in records:
            record.revoked_at = now

        db.commit()

    @staticmethod
    def touch_last_used(db: Session, record: RefreshToken) -> None:
        record.last_used_at = _utcnow()
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
        name: str,
        email: str,
    ) -> Commander:
        commander = CommanderRepository.get_by_email(db, email)
        if commander is not None:
            return commander

        commander = Commander(name=name, email=email)
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
    ) -> IncidentMaster:
        incident = IncidentMaster(
            incident_number=incident_number,
            user_email=user_email,
            subject=subject,
            short_description=short_description,
            description=description,
            zone=zone,
            service_name=service_name,
            source=source,
        )
        db.add(incident)
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
        is_primary: bool = False,
    ) -> IncidentCommander:
        assignment = IncidentCommander(
            incident_id=incident_id,
            commander_id=commander_id,
            is_primary=is_primary,
        )
        db.add(assignment)
        db.flush()
        return assignment


class IncidentAnalysisRepository:
    """Persistence operations for IncidentAnalysis records."""

    @staticmethod
    def get_first_for_incident(
        db: Session,
        incident_id: str,
    ) -> IncidentAnalysis | None:
        stmt = select(IncidentAnalysis).where(
            IncidentAnalysis.incident_id == incident_id
        )
        return db.execute(stmt).scalars().first()

    @staticmethod
    def create(
        db: Session,
        *,
        incident_id: str,
        intent: str,
        severity_prediction: str,
    ) -> IncidentAnalysis:
        analysis = IncidentAnalysis(
            incident_id=incident_id,
            intent=intent,
            severity_prediction=severity_prediction,
            recommendation_status="pending",
        )
        db.add(analysis)
        db.flush()
        return analysis


class DuplicateIdentificationRepository:
    """Persistence operations for duplicate-identification records."""

    @staticmethod
    def get_first_for_incident(
        db: Session,
        incident_id: str,
    ) -> DuplicateIdentification | None:
        stmt = select(DuplicateIdentification).where(
            DuplicateIdentification.incident_id == incident_id
        )
        return db.execute(stmt).scalars().first()

    @staticmethod
    def create(
        db: Session,
        *,
        incident_id: str,
        matched_incident_id: str,
        similarity_score: Decimal,
        decision: str,
        detection_method: str,
    ) -> DuplicateIdentification:
        duplicate = DuplicateIdentification(
            incident_id=incident_id,
            matched_incident_id=matched_incident_id,
            similarity_score=similarity_score,
            decision=decision,
            detection_method=detection_method,
        )
        db.add(duplicate)
        db.flush()
        return duplicate


class BlastRadiusRepository:
    """Persistence operations for BlastRadius records."""

    @staticmethod
    def get_first_for_incident(
        db: Session,
        incident_id: str,
    ) -> BlastRadius | None:
        stmt = select(BlastRadius).where(BlastRadius.incident_id == incident_id)
        return db.execute(stmt).scalars().first()

    @staticmethod
    def create(
        db: Session,
        *,
        incident_id: str,
        affected_service: str,
        affected_component: str,
        dependency_type: str,
        impact_level: str,
        correlation_score: Decimal,
        confidence_score: Decimal,
        evidence: str,
    ) -> BlastRadius:
        record = BlastRadius(
            incident_id=incident_id,
            affected_service=affected_service,
            affected_component=affected_component,
            dependency_type=dependency_type,
            impact_level=impact_level,
            correlation_score=correlation_score,
            confidence_score=confidence_score,
            evidence=evidence,
        )
        db.add(record)
        db.flush()
        return record


class ResolutionIntelligenceRepository:
    """Persistence operations for resolution records."""

    @staticmethod
    def get_first_for_incident(
        db: Session,
        incident_id: str,
    ) -> ResolutionIntelligence | None:
        stmt = select(ResolutionIntelligence).where(
            ResolutionIntelligence.incident_id == incident_id
        )
        return db.execute(stmt).scalars().first()

    @staticmethod
    def create(
        db: Session,
        *,
        incident_id: str,
        resolver_team: str,
        recommended_resolution: str,
        resolution_source: str,
    ) -> ResolutionIntelligence:
        record = ResolutionIntelligence(
            incident_id=incident_id,
            resolver_team=resolver_team,
            recommended_resolution=recommended_resolution,
            resolution_source=resolution_source,
            resolution_status="pending",
        )
        db.add(record)
        db.flush()
        return record


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


class AgentExecutionRepository:
    """Persistence operations for agent execution records."""

    @staticmethod
    def get_first_for_incident(
        db: Session,
        incident_id: str,
    ) -> AgentExecution | None:
        stmt = select(AgentExecution).where(
            AgentExecution.incident_id == incident_id
        )
        return db.execute(stmt).scalars().first()

    @staticmethod
    def create(
        db: Session,
        *,
        incident_id: str,
        agent_name: str,
        model_name: str,
        model_type: str,
    ) -> AgentExecution:
        record = AgentExecution(
            incident_id=incident_id,
            agent_name=agent_name,
            model_name=model_name,
            model_type=model_type,
            execution_status="completed",
        )
        db.add(record)
        db.flush()
        return record


class ModelFallbackRepository:
    """Persistence operations for model fallback attempts."""

    @staticmethod
    def get_first_for_execution(
        db: Session,
        execution_id: str,
    ) -> ModelFallback | None:
        stmt = select(ModelFallback).where(
            ModelFallback.execution_id == execution_id
        )
        return db.execute(stmt).scalars().first()

    @staticmethod
    def create(
        db: Session,
        *,
        execution_id: str,
        model_name: str,
        fallback_level: str,
        success: bool,
    ) -> ModelFallback:
        record = ModelFallback(
            execution_id=execution_id,
            model_name=model_name,
            fallback_level=fallback_level,
            success=success,
        )
        db.add(record)
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
