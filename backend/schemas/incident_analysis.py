"""Validation model for one incident-analysis history entry."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class IncidentAnalysisRecord(BaseModel):
    """One AI analysis result stored in an incident's history list."""

    analysis_id: str | None = None
    intent: str | None = None
    intent_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    severity_prediction: str | None = None
    severity_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    business_impact: str | None = None
    risk_score: Decimal | None = Field(default=None, ge=0)
    next_best_action: str | None = None
    root_cause_hypothesis: str | None = None
    confidence_score: Decimal | None = Field(default=None, ge=0, le=1)
    author_input_score: Decimal | None = Field(default=None, ge=0, le=1)
    resolution_evaluation_score: Decimal | None = Field(default=None, ge=0, le=1)
    recommendation_status: str | None = None
    analyzed_at: datetime | None = None
