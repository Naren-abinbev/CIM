"""Validation model for one item in an agent execution history list."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class AgentExecutionRecord(BaseModel):
    """One agent attempt, retry, or fallback stored in JSON."""

    attempt: int = Field(..., ge=1)
    model_name: str
    model_type: str | None = None
    fallback_level: str = "primary"
    fallback_used: bool = False
    success: bool
    execution_status: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)
    retry_count: int = Field(default=0, ge=0)
    confidence_score: Decimal | None = Field(default=None, ge=0, le=1)
    evaluation_score: Decimal | None = Field(default=None, ge=0, le=1)
    judge_score: Decimal | None = Field(default=None, ge=0, le=1)
    reasoning_summary: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
