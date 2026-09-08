from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IncidentCreate(BaseModel):
    """Request body for creating an incident."""

    incident_number: str = Field(min_length=1, max_length=50)
    subject: str = Field(min_length=1, max_length=500)
    category: str = Field(default="uncategorized", max_length=100)
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
    category: str
    short_description: str
    description: str
    zone: str
    service_name: str
    severity: str | None
    intent: str | None
    intent_confidence: float | None
    severity_prediction: str | None
    severity_confidence: float | None
    business_impact: str | None
    risk_score: float | None
    next_best_action: str | None
    root_cause_hypothesis: str | None
    confidence_score: float | None
    author_input_score: float | None
    resolution_evaluation_score: float | None
    recommendation_status: str | None
    analysis_created_at: datetime | None
    analysis_history: list[dict]
    status: str
    source: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
