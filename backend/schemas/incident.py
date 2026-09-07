from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IncidentCreate(BaseModel):
    """Request body for creating an incident."""

    incident_number: str = Field(min_length=1, max_length=50)
    subject: str = Field(min_length=1, max_length=500)
    short_description: str = Field(min_length=1, max_length=1000)
    description: str = Field(min_length=1)
    zone: str = Field(min_length=1, max_length=100)
    service_name: str = Field(min_length=1, max_length=200)
    source: str = Field(default="application", max_length=50)


class IncidentResponse(BaseModel):
    """Response returned after reading or creating an incident."""

    model_config = ConfigDict(from_attributes=True)

    incident_id: str
    incident_number: str
    user_email: str
    subject: str
    short_description: str
    description: str
    zone: str
    service_name: str
    severity: str | None
    status: str
    source: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
