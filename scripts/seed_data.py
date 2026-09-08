"""Seed one development record for each application table.

Run from the repository root after applying Alembic migrations:

    .venv\\Scripts\\python.exe scripts\\seed_data.py

The script is idempotent for the sample identifiers and can be run repeatedly
without creating duplicate sample rows.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.auth import security
from backend.auth import service as auth_service
from backend.database.database import SessionLocal
from backend.database.models import RefreshToken
from backend.database.repositories import (
    AgentExecutionRepository,
    BlastRadiusRepository,
    CommanderRepository,
    DuplicateIdentificationRepository,
    IncidentAnalysisRepository,
    IncidentCommanderRepository,
    IncidentPerformanceMetricRepository,
    IncidentRepository,
    ModelFallbackRepository,
    ResolutionIntelligenceRepository,
    StakeholderReportRepository,
    UserRepository,
    WarRoomRepository,
)


SAMPLE_USER_EMAIL = "sample.user@example.com"
SAMPLE_USERNAME = "sample_user"
SAMPLE_COMMANDER_EMAIL = "sample.commander@example.com"
SAMPLE_INCIDENT_NUMBER = "INC-SAMPLE-001"
SAMPLE_MATCHED_INCIDENT_NUMBER = "INC-SAMPLE-002"
SAMPLE_PASSWORD = "Sample password for development only!"


def _get_or_create_sample_user(db):
    user = UserRepository.get_by_email(db, SAMPLE_USER_EMAIL)
    if user is not None:
        return user

    return UserRepository.create(
        db,
        username=SAMPLE_USERNAME,
        email=SAMPLE_USER_EMAIL,
        password_hash=security.hash_password(SAMPLE_PASSWORD),
        is_verified=True,
    )


def _get_or_create_sample_incident(
    db,
    *,
    incident_number: str,
    subject: str,
    short_description: str,
):
    incident = IncidentRepository.get_by_number(db, incident_number)
    if incident is not None:
        return incident

    return IncidentRepository.create(
        db,
        incident_number=incident_number,
        user_email=SAMPLE_USER_EMAIL,
        subject=subject,
        short_description=short_description,
        description=(
            "Development sample data for testing the incident-management "
            "database and APIs."
        ),
        zone="Development",
        service_name="Sample Incident Service",
        source="seed",
    )


def _seed_refresh_token(db, user_id: str) -> None:
    """Create one sample refresh-token row without printing the token."""
    existing = db.execute(
        select(RefreshToken).where(RefreshToken.user_id == user_id)
    ).scalars().first()

    if existing is not None:
        return

    user = UserRepository.get_by_id(db, user_id)
    if user is None:
        raise RuntimeError("Sample user was not found while seeding tokens.")

    # issue_token_pair creates the server-side refresh-token row. The raw
    # token is intentionally not printed or stored by this seed script.
    auth_service.issue_token_pair(
        db,
        user=user,
        user_agent="seed-data",
        ip_address="127.0.0.1",
    )


def seed_sample_data() -> None:
    db = SessionLocal()

    try:
        user = _get_or_create_sample_user(db)

        commander = CommanderRepository.get_or_create(
            db,
            name="Sample Commander",
            email=SAMPLE_COMMANDER_EMAIL,
        )

        incident = _get_or_create_sample_incident(
            db,
            incident_number=SAMPLE_INCIDENT_NUMBER,
            subject="Sample database outage",
            short_description="Sample database connectivity incident",
        )

        matched_incident = _get_or_create_sample_incident(
            db,
            incident_number=SAMPLE_MATCHED_INCIDENT_NUMBER,
            subject="Sample related database incident",
            short_description="Sample related database timeout incident",
        )

        if IncidentCommanderRepository.get_active_assignment(
            db,
            incident_id=incident.incident_id,
            commander_id=commander.commander_id,
        ) is None:
            IncidentCommanderRepository.create(
                db,
                incident_id=incident.incident_id,
                commander_id=commander.commander_id,
                is_primary=True,
            )

        if IncidentAnalysisRepository.get_first_for_incident(
            db,
            incident.incident_id,
        ) is None:
            IncidentAnalysisRepository.create(
                db,
                incident_id=incident.incident_id,
                intent="service outage",
                severity_prediction="high",
            )

        if DuplicateIdentificationRepository.get_first_for_incident(
            db,
            incident.incident_id,
        ) is None:
            DuplicateIdentificationRepository.create(
                db,
                incident_id=incident.incident_id,
                matched_incident_id=matched_incident.incident_id,
                similarity_score=Decimal("0.9200"),
                decision="duplicate",
                detection_method="vector_search",
            )

        if BlastRadiusRepository.get_first_for_incident(
            db,
            incident.incident_id,
        ) is None:
            BlastRadiusRepository.create(
                db,
                incident_id=incident.incident_id,
                affected_service="Sample Payment Service",
                affected_component="Sample Payment API",
                dependency_type="downstream",
                impact_level="high",
                correlation_score=Decimal("0.8800"),
                confidence_score=Decimal("0.9100"),
                evidence="Sample timeout events correlate with payment failures.",
            )

        if ResolutionIntelligenceRepository.get_first_for_incident(
            db,
            incident.incident_id,
        ) is None:
            ResolutionIntelligenceRepository.create(
                db,
                incident_id=incident.incident_id,
                resolver_team="Sample Platform Team",
                recommended_resolution="Restart the sample payment dependency.",
                resolution_source="seed",
            )

        war_room = WarRoomRepository.get_first_for_incident(
            db,
            incident.incident_id,
        )
        if war_room is None:
            war_room = WarRoomRepository.create(
                db,
                incident_id=incident.incident_id,
                meeting_id="sample-teams-meeting-001",
                meeting_url="https://teams.example.test/sample-meeting-001",
            )

        if IncidentPerformanceMetricRepository.get_first_for_incident(
            db,
            incident.incident_id,
        ) is None:
            IncidentPerformanceMetricRepository.create(
                db,
                incident_id=incident.incident_id,
            )

        execution = AgentExecutionRepository.get_first_for_incident(
            db,
            incident.incident_id,
        )
        if execution is None:
            execution = AgentExecutionRepository.create(
                db,
                incident_id=incident.incident_id,
                agent_name="sample-investigation-agent",
                model_name="sample-model",
                model_type="chat",
            )

        if ModelFallbackRepository.get_first_for_execution(
            db,
            execution.execution_id,
        ) is None:
            ModelFallbackRepository.create(
                db,
                execution_id=execution.execution_id,
                model_name="sample-model",
                fallback_level="primary",
                success=True,
            )

        if StakeholderReportRepository.get_first_for_incident(
            db,
            incident.incident_id,
        ) is None:
            meeting_id = war_room.meeting_id
            if meeting_id is None:
                raise RuntimeError(
                    "Sample war room is missing its meeting_id."
                )

            StakeholderReportRepository.create(
                db,
                incident_id=incident.incident_id,
                meeting_id=meeting_id,
                report_type="incident_summary",
            )

        db.commit()

        # The existing auth service commits its token record internally.
        _seed_refresh_token(db, user.id)

        print("Sample data is ready.")
        print(f"Incident: {incident.incident_number} ({incident.incident_id})")
        print(f"Matched incident: {matched_incident.incident_number}")
        print(f"Commander: {commander.name} ({commander.commander_id})")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_sample_data()
