from __future__ import annotations

from sqlalchemy.orm import Session

from backend.database.models import IncidentMaster
from backend.database.repositories import IncidentRepository
from backend.schemas.incident import IncidentCreate


class IncidentAlreadyExistsError(Exception):
    """Raised when an incident number already exists."""


class IncidentNotFoundError(Exception):
    """Raised when an incident cannot be found."""


def create_incident(
    db: Session,
    *,
    payload: IncidentCreate,
    user_email: str,
) -> IncidentMaster:
    """Validate business rules and create an incident record."""
    existing = IncidentRepository.get_by_number(
        db,
        payload.incident_number,
    )
    if existing is not None:
        raise IncidentAlreadyExistsError(
            f"Incident number '{payload.incident_number}' already exists."
        )

    return IncidentRepository.create(
        db,
        incident_number=payload.incident_number,
        user_email=user_email,
        subject=payload.subject,
        short_description=payload.short_description,
        description=payload.description,
        zone=payload.zone,
        service_name=payload.service_name,
        source=payload.source,
    )


def get_incident_by_number(
    db: Session,
    *,
    incident_number: str,
) -> IncidentMaster:
    """Return an incident by its external/reference number."""
    incident = IncidentRepository.get_by_number(db, incident_number)
    if incident is None:
        raise IncidentNotFoundError(
            f"Incident number '{incident_number}' was not found."
        )
    return incident
