from pydantic import BaseModel


class DuplicateIdentificationRequest(BaseModel):
    title: str
    description: str | None = None
    severity: str | None = None
    serviceId: str | None = None
    zone: str | None = None


class DuplicateSuggestion(BaseModel):
    id: str | None = None
    subject: str | None = None
    severity: str | None = None
    status: str | None = None
    serviceId: str | None = None
    zone: str | None = None
    matchPercentage: int
    createdAt: str | None = None
    resolvedAt: str | None = None


class DuplicateIdentificationResponse(BaseModel):
    data: list[DuplicateSuggestion]