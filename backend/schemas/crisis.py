from pydantic import BaseModel, Field
from typing import List
from datetime import datetime


# ==========================================
# AGE
# ==========================================

class Age(BaseModel):
    value: int
    unit: str


# ==========================================
# COMMANDER
# ==========================================

class Commander(BaseModel):
    id: str
    name: str


# ==========================================
# CRISIS RESPONSE
# ==========================================

class CrisisResponse(BaseModel):

    id: str

    title: str

    severity: str

    businessImpact: str

    status: str

    service: str

    zone: str

    age: Age

    commander: Commander

    createdAt: datetime

    updatedAt: datetime


# ==========================================
# PAGINATION
# ==========================================

class PaginationResponse(BaseModel):

    page: int

    pageSize: int

    totalItems: int

    totalPages: int

    hasNextPage: bool

    hasPreviousPage: bool


# ==========================================
# FINAL RESPONSE
# ==========================================

class CrisisListResponse(BaseModel):

    data: List[CrisisResponse]

    pagination: PaginationResponse


class CrisisAnalysisRequest(BaseModel):
    report: str
    crisis_type: str | None = None
    top_k: int = Field(default=3, ge=1, le=10)


class CrisisAnalysisResponse(BaseModel):
    summary: str
    relevant_documents: List[str]
    immediate_actions: List[str]