"""Seed one development record for each application table.

Run from the repository root after applying Alembic migrations:

    .venv\\Scripts\\python.exe scripts\\seed_data.py

The script is idempotent for the sample identifiers and can be run repeatedly
without creating duplicate sample rows.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.auth import security
from backend.core.agent_registry import get_agent_id
from backend.database.database import SessionLocal
from backend.schemas.agent_execution import AgentExecutionRecord
from backend.database.repositories import (
    AgentExecutionLogRepository,
    CommanderRepository,
    IncidentCommanderRepository,
    IncidentPerformanceMetricRepository,
    IncidentRepository,
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
    user_id: str,
    incident_number: str,
    subject: str,
    category: str,
    short_description: str,
):
    incident = IncidentRepository.get_by_number(db, incident_number)
    if incident is not None:
        return incident

    return IncidentRepository.create(
        db,
        incident_number=incident_number,
        user_email=SAMPLE_USER_EMAIL,
        user_id=user_id,
        subject=subject,
        category=category,
        short_description=short_description,
        description=(
            "Development sample data for testing the incident-management "
            "database and APIs."
        ),
        zone="Development",
        service_name="Sample Incident Service",
        source="seed",
    )


def seed_sample_data() -> None:
    db = SessionLocal()

    try:
        user = _get_or_create_sample_user(db)

        commander = CommanderRepository.get_or_create(
            db,
            email=SAMPLE_COMMANDER_EMAIL,
            original_user_id=user.id,
        )

        incident = _get_or_create_sample_incident(
            db,
            user_id=user.id,
            incident_number=SAMPLE_INCIDENT_NUMBER,
            subject="Sample database outage",
            category="infrastructure",
            short_description="Sample database connectivity incident",
        )

        matched_incident = _get_or_create_sample_incident(
            db,
            user_id=user.id,
            incident_number=SAMPLE_MATCHED_INCIDENT_NUMBER,
            subject="Sample related database incident",
            category="infrastructure",
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
                assignment_id="sample-assignment-001",
                is_primary=True,
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

        sample_agent_id = get_agent_id("sample-investigation-agent")
        execution = AgentExecutionLogRepository.get_for_incident_and_agent(
            db,
            incident.incident_id,
            sample_agent_id,
        )
        if execution is None:
            execution = AgentExecutionLogRepository.create(
                db,
                incident_id=incident.incident_id,
                agent_id=sample_agent_id,
            )

        if not execution.execution_history:
            AgentExecutionLogRepository.append_execution_record(
                db,
                record=execution,
                execution_record=AgentExecutionRecord(
                    attempt=1,
                    model_name="sample-model",
                    model_type="chat",
                    fallback_level="primary",
                    fallback_used=False,
                    success=True,
                    execution_status="completed",
                    input_tokens=120,
                    output_tokens=80,
                    total_tokens=200,
                    latency_ms=450,
                    confidence_score=0.91,
                    evaluation_score=0.88,
                    judge_score=0.90,
                ),
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
        print("Sample data is ready.")
        print(f"Incident: {incident.incident_number} ({incident.incident_id})")
        print(f"Matched incident: {matched_incident.incident_number}")
        print(f"Commander: {commander.email} ({commander.commander_id})")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_sample_data()
